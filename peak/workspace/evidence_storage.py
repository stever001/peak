"""Where captured evidence bytes are kept (Phase 220): a deliberately small storage boundary.

A store keeps the **original bytes** of an evidence upload under a server-generated key and gives
them back unchanged. Three operations, nothing else:

- ``put(key, data, media_type)``: store new bytes; refuses to overwrite an existing key;
- ``read(key)``: the exact bytes stored;
- ``exists(key)``.

There is no delete and no listing: evidence is never removed by the application.

Two stores:

- :class:`R2EvidenceStore`: production. A private Cloudflare R2 bucket reached only by the API
  through R2's S3-compatible endpoint (``boto3``). An overwrite is refused by the bucket itself
  (a conditional write, ``If-None-Match: *``).
- :class:`FilesystemEvidenceStore`: local development and tests only. Refused against a MySQL
  runtime database: a web service's local disk is not durable evidence storage.

Capture is **off** wherever no store is configured, including an incomplete R2 configuration.
There is never a fallback from one store to another. See docs/PHASE220_GUIDED_EVIDENCE_CAPTURE.md.
"""

from __future__ import annotations

import logging
import os
import re
import tempfile
from typing import Optional, Protocol

BACKEND_ENV = "PEAK_EVIDENCE_STORAGE_BACKEND"
FILESYSTEM_ROOT_ENV = "PEAK_EVIDENCE_FS_ROOT"
R2_ACCOUNT_ID_ENV = "PEAK_R2_ACCOUNT_ID"
R2_BUCKET_ENV = "PEAK_R2_BUCKET"
R2_ACCESS_KEY_ID_ENV = "PEAK_R2_ACCESS_KEY_ID"
R2_SECRET_ACCESS_KEY_ENV = "PEAK_R2_SECRET_ACCESS_KEY"
R2_ENV = (R2_ACCOUNT_ID_ENV, R2_BUCKET_ENV, R2_ACCESS_KEY_ID_ENV, R2_SECRET_ACCESS_KEY_ENV)

_log = logging.getLogger(__name__)

#: Keys are server-generated (``evidence/<engagement id>/<evidence id>``): lower-case ids and
#: slashes only, so a key can never climb out of the store or name a hidden file.
KEY_PATTERN = re.compile(r"^evidence/[a-z0-9_]{1,64}/[a-z0-9_]{1,64}$")


class EvidenceStoreError(Exception):
    """The store could not keep or return bytes. The message never includes a path or secret."""


class EvidenceStore(Protocol):
    backend: str

    def put(self, key: str, data: bytes, media_type: str) -> None: ...

    def read(self, key: str) -> bytes: ...

    def exists(self, key: str) -> bool: ...


def evidence_key(engagement_id: str, evidence_id: str) -> str:
    key = f"evidence/{engagement_id}/{evidence_id}"
    if not KEY_PATTERN.match(key):
        raise EvidenceStoreError("invalid evidence key")
    return key


class FilesystemEvidenceStore:
    """Bytes under a local directory. For development and tests only, never production."""

    backend = "filesystem"

    def __init__(self, root: str):
        self.root = os.path.realpath(root)

    def _path(self, key: str) -> str:
        if not KEY_PATTERN.match(key):
            raise EvidenceStoreError("invalid evidence key")
        path = os.path.realpath(os.path.join(self.root, *key.split("/")))
        if not path.startswith(self.root + os.sep):
            raise EvidenceStoreError("invalid evidence key")
        return path

    def put(self, key: str, data: bytes, media_type: str) -> None:
        path = self._path(key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".upload-")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(data)
            os.link(tmp, path)  # fails if the key already exists: never overwrite
        except FileExistsError:
            raise EvidenceStoreError("evidence key already exists") from None
        finally:
            os.unlink(tmp)

    def read(self, key: str) -> bytes:
        try:
            with open(self._path(key), "rb") as f:
                return f.read()
        except FileNotFoundError:
            raise EvidenceStoreError("evidence bytes not found") from None

    def exists(self, key: str) -> bool:
        return os.path.isfile(self._path(key))


class R2EvidenceStore:
    """Bytes in a private Cloudflare R2 bucket, through its S3-compatible API. Production store.

    Uses only PutObject (conditional: never overwrites), GetObject and HeadObject. Errors are
    reduced to :class:`EvidenceStoreError` with a fixed message: no endpoint, bucket, key or
    credential reaches a caller, a log line or a traceback chain.
    """

    backend = "r2"

    def __init__(self, account_id: str, bucket: str, access_key_id: str, secret_access_key: str):
        import boto3
        from botocore.config import Config

        self.bucket = bucket
        # Creating a client makes no network call; the first put/read/exists does.
        self._client = boto3.client(
            "s3",
            endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
            region_name="auto",  # R2 has no regions; "auto" is what it expects from S3 clients.
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            config=Config(signature_version="s3v4", connect_timeout=5, read_timeout=30,
                          retries={"max_attempts": 3, "mode": "standard"},
                          # Checksums only where the S3 API requires them. The sha256 recorded
                          # in the row is checked on every read instead.
                          request_checksum_calculation="when_required",
                          response_checksum_validation="when_required"),
        )

    @staticmethod
    def _check(key: str) -> None:
        if not KEY_PATTERN.match(key):
            raise EvidenceStoreError("invalid evidence key")

    @staticmethod
    def _status(exc) -> Optional[int]:
        return getattr(exc, "response", {}).get("ResponseMetadata", {}).get("HTTPStatusCode")

    def put(self, key: str, data: bytes, media_type: str) -> None:
        from botocore.exceptions import BotoCoreError, ClientError

        self._check(key)
        try:
            # If-None-Match: * makes the bucket refuse a key that already exists (412).
            self._client.put_object(Bucket=self.bucket, Key=key, Body=data,
                                    ContentType=media_type, IfNoneMatch="*")
        except ClientError as exc:
            if self._status(exc) in (409, 412):
                raise EvidenceStoreError("evidence key already exists") from None
            raise EvidenceStoreError("evidence storage request failed") from None
        except BotoCoreError:
            raise EvidenceStoreError("evidence storage request failed") from None

    def read(self, key: str) -> bytes:
        from botocore.exceptions import BotoCoreError, ClientError

        self._check(key)
        try:
            return self._client.get_object(Bucket=self.bucket, Key=key)["Body"].read()
        except ClientError as exc:
            if self._status(exc) == 404:
                raise EvidenceStoreError("evidence bytes not found") from None
            raise EvidenceStoreError("evidence storage request failed") from None
        except BotoCoreError:
            raise EvidenceStoreError("evidence storage request failed") from None

    def exists(self, key: str) -> bool:
        from botocore.exceptions import BotoCoreError, ClientError

        self._check(key)
        try:
            self._client.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError as exc:
            if self._status(exc) == 404:
                return False
            raise EvidenceStoreError("evidence storage request failed") from None
        except BotoCoreError:
            raise EvidenceStoreError("evidence storage request failed") from None


def _unavailable(reason: str) -> None:
    # Names variables only, never their values.
    _log.warning("Evidence capture is off: %s", reason)
    return None


def store_from_environment(runtime_database_url: str = "") -> Optional[EvidenceStore]:
    """The configured store, or None (capture off). Never raises on missing configuration.

    ``PEAK_EVIDENCE_STORAGE_BACKEND``: ``r2`` (production), ``filesystem`` (local only) or unset.
    Anything incomplete or unknown turns capture off; nothing falls back to another store.
    """
    kind = os.environ.get(BACKEND_ENV, "").strip().lower()
    if not kind:
        return None
    if kind == "r2":
        values = {name: os.environ.get(name, "").strip() for name in R2_ENV}
        missing = [name for name, value in values.items() if not value]
        if missing:
            return _unavailable(f"{BACKEND_ENV}=r2 but {', '.join(missing)} not set")
        if not re.fullmatch(r"[0-9a-f]{32}", values[R2_ACCOUNT_ID_ENV]):
            return _unavailable(f"{R2_ACCOUNT_ID_ENV} is not an R2 account id")
        try:
            return R2EvidenceStore(*(values[name] for name in R2_ENV))
        except ImportError:
            return _unavailable("boto3 is not installed")
        except Exception:  # noqa: BLE001 - never let a bad value stop the API starting
            return _unavailable("the R2 client could not be created")
    if kind == "filesystem":
        root = os.environ.get(FILESYSTEM_ROOT_ENV, "").strip()
        if not root:
            return _unavailable(f"{BACKEND_ENV}=filesystem but {FILESYSTEM_ROOT_ENV} not set")
        if runtime_database_url.split(":", 1)[0].split("+", 1)[0] in ("mysql", "mariadb"):
            return _unavailable("filesystem storage is refused with a MySQL runtime database")
        return FilesystemEvidenceStore(root)
    return _unavailable(f"{BACKEND_ENV} is not r2 or filesystem")
