"""Consultant workspace: client profiles and engagement workflow fields (Phase 202).

The only approved write path to ``clients``, and to the engagement workflow columns, as declared in
``peak.persistence.allowlist.WORKSPACE_WRITE_COLUMNS``. Placed beside ``peak.accounts`` and called
only by the consultant API. No controlled writer is used or changed here.
"""

from .service import (  # noqa: F401
    WorkspaceError,
    create_client,
    create_engagement,
    get_client,
    get_engagement,
    list_clients,
    list_consultant_options,
    list_engagements,
    update_client,
    update_engagement,
)
