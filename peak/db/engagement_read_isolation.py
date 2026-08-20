"""Phase 57 — the read-side isolation primitive for engagement classification.

Phase 56 recorded classification on the ``engagements`` row (``engagement_category``,
``real_client_data``, ``client_accessible``, ``capsule_publication_authorized``). Those columns
were a **contract with no enforcement**: nothing consumed them, because no read path existed yet.

This module is that enforcement, added **before** the first read path rather than after — so a
future client-facing read has a correct primitive to reach for instead of hand-rolling a filter and
getting it subtly wrong.

**The default is exclusion.** :data:`ReadMode.CLIENT_FACING` admits only engagements that are
``real_client``, ``client_accessible``, and ``real_client_data`` — an ``internal_test`` record can
never satisfy it, because Phase 56 forbids that combination at write time. Seeing an internal test
engagement requires asking for it explicitly, via :data:`ReadMode.INTERNAL_ADMIN`.

**A reserved ``client_id`` is not the access control.** ``99999`` and the reserved prefixes make an
internal test record obvious at a glance, and this module *does* exclude them from client-facing
reads — but as **defence in depth, never as the mechanism**. The mechanism is the classification
columns. A row that somehow carried a reserved id with ``client_accessible=true`` is still refused,
and a row with an ordinary id but ``engagement_category=internal_test`` is refused too. Neither
check is load-bearing alone.

**Publication eligibility is not visibility.** They are separate questions with separate predicates.
An engagement may be publication-eligible while being invisible to every client — that is exactly
what an internal test engagement authorised for capsule publication looks like.

Side-effect boundary: this module **opens no database connection**, creates or modifies no record,
imports and invokes no writer, executes no raw SQL, and reads no environment variable. It builds
predicates and SQLAlchemy filter clauses; the caller owns the session. Every predicate works on any
row-like object with the classification attributes, so it is usable without SQLAlchemy at all.

See docs/PHASE57_INTERNAL_TEST_READ_ISOLATION.md.
"""

from __future__ import annotations

from typing import Optional

from peak.persistence.governance import (
    ENGAGEMENT_CATEGORY_INTERNAL_TEST,
    ENGAGEMENT_CATEGORY_REAL_CLIENT,
    is_reserved_internal_test_client_id,
)

from .models import Engagement


class ReadMode:
    """The audiences an engagement read can be performed for (str constants; no Enum needed)."""

    #: A real client reading their own data. Internal test engagements are never included.
    CLIENT_FACING = "client_facing"
    #: An internal/admin view. Includes internal test engagements **only** when explicitly asked.
    INTERNAL_ADMIN = "internal_admin"


ALL_READ_MODES = (ReadMode.CLIENT_FACING, ReadMode.INTERNAL_ADMIN)

#: The mode a caller gets when it says nothing. Exclusion is the default, deliberately.
DEFAULT_READ_MODE = ReadMode.CLIENT_FACING


def _attr(row, name):
    return getattr(row, name, None)


# --------------------------------------------------------------------------- row predicates


def is_client_visible(row) -> bool:
    """True only if ``row`` may be shown to a real client.

    Requires **all** of: ``engagement_category == real_client``, ``client_accessible`` true,
    ``real_client_data`` true, and a ``client_id`` outside the reserved internal-test namespace.
    The last is defence in depth — the classification columns are the control.
    """
    if row is None:
        return False
    if _attr(row, "engagement_category") != ENGAGEMENT_CATEGORY_REAL_CLIENT:
        return False
    if _attr(row, "client_accessible") is not True:
        return False
    if _attr(row, "real_client_data") is not True:
        return False
    # Defence in depth: a reserved namespace must never reach a client, even if the flags on the
    # row somehow disagree with the category.
    if is_reserved_internal_test_client_id(_attr(row, "client_id")):
        return False
    return True


def is_internal_test(row) -> bool:
    """True if ``row`` is classified as an internal test/training engagement."""
    return row is not None and _attr(row, "engagement_category") == \
        ENGAGEMENT_CATEGORY_INTERNAL_TEST


def is_visible_in_mode(row, mode: str = DEFAULT_READ_MODE,
                       include_internal_test: bool = False) -> bool:
    """True if ``row`` may be read in ``mode``.

    ``CLIENT_FACING`` ignores ``include_internal_test`` entirely: a client-facing read can never
    opt into internal test visibility, so the flag cannot be used to widen it by mistake.
    ``INTERNAL_ADMIN`` shows real client engagements always, and internal test engagements **only**
    when ``include_internal_test`` is explicitly true.
    """
    if row is None:
        return False
    if mode == ReadMode.CLIENT_FACING:
        return is_client_visible(row)
    if mode == ReadMode.INTERNAL_ADMIN:
        if is_internal_test(row):
            return include_internal_test is True
        return _attr(row, "engagement_category") == ENGAGEMENT_CATEGORY_REAL_CLIENT
    # An unrecognised mode is refused, never silently treated as permissive.
    return False


def is_publication_eligible(row) -> bool:
    """True only if an internal test engagement's capsules may be published.

    The compound rule, checked together: ``internal_test`` **and** ``real_client_data`` false
    **and** ``client_accessible`` false **and** ``capsule_publication_authorized`` true. No single
    condition is sufficient, and this says nothing about client visibility — a publication-eligible
    engagement is, by construction, invisible to every client.
    """
    if row is None:
        return False
    return (_attr(row, "engagement_category") == ENGAGEMENT_CATEGORY_INTERNAL_TEST
            and _attr(row, "real_client_data") is False
            and _attr(row, "client_accessible") is False
            and _attr(row, "capsule_publication_authorized") is True)


# --------------------------------------------------------------------------- query filters
#
# These build SQLAlchemy filter clauses only. They open no connection and execute nothing; the
# caller supplies and owns the session and query.


def client_visible_filter():
    """A SQLAlchemy clause admitting only client-visible engagements."""
    return (
        (Engagement.engagement_category == ENGAGEMENT_CATEGORY_REAL_CLIENT)
        & (Engagement.client_accessible.is_(True))
        & (Engagement.real_client_data.is_(True))
    )


def internal_admin_filter(include_internal_test: bool = False):
    """A SQLAlchemy clause for an internal/admin read.

    Without ``include_internal_test`` this is the real-client-category clause; internal test
    engagements enter only when the caller explicitly asks for them.
    """
    real_client = Engagement.engagement_category == ENGAGEMENT_CATEGORY_REAL_CLIENT
    if not include_internal_test:
        return real_client
    return real_client | (Engagement.engagement_category == ENGAGEMENT_CATEGORY_INTERNAL_TEST)


def publication_eligible_filter():
    """A SQLAlchemy clause for publication-eligible internal test engagements (compound rule)."""
    return (
        (Engagement.engagement_category == ENGAGEMENT_CATEGORY_INTERNAL_TEST)
        & (Engagement.real_client_data.is_(False))
        & (Engagement.client_accessible.is_(False))
        & (Engagement.capsule_publication_authorized.is_(True))
    )


def read_filter_for_mode(mode: str = DEFAULT_READ_MODE,
                         include_internal_test: bool = False):
    """The filter clause for ``mode``.

    ``CLIENT_FACING`` never widens on ``include_internal_test``. An unrecognised mode raises
    rather than returning a permissive clause — failing closed is the point of this module.
    """
    if mode == ReadMode.CLIENT_FACING:
        return client_visible_filter()
    if mode == ReadMode.INTERNAL_ADMIN:
        return internal_admin_filter(include_internal_test=include_internal_test)
    raise ValueError(f"unrecognised read mode: {mode!r}")


def apply_read_isolation(query, mode: str = DEFAULT_READ_MODE,
                         include_internal_test: bool = False,
                         client_id: Optional[str] = None):
    """Return ``query`` narrowed by the read-isolation clause for ``mode``.

    ``client_id`` is an optional *additional* tenant narrowing. It is deliberately not sufficient
    on its own and never replaces the classification clause: scoping a query to one client does
    not make an internal test record safe to show. Executes nothing — the caller owns the session.
    """
    narrowed = query.filter(read_filter_for_mode(mode, include_internal_test))
    if client_id is not None:
        narrowed = narrowed.filter(Engagement.client_id == client_id)
    return narrowed
