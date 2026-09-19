"""The Phase 202 client write-path invariant, shared by the harnesses that assert it.

Before Phase 202 those harnesses asserted ``clients`` was "never writable by any path". Phase 202
changed that rule explicitly: ``clients`` is still unreachable by every controlled writer, and its
only approved write path is the consultant workspace service, restricted to named actions and
columns. This predicate states the replacement rule in one place.
"""

from __future__ import annotations


def clients_written_only_by_workspace() -> bool:
    """True when ``clients`` is reachable by the workspace path alone, narrowly, and nothing else."""
    from peak.persistence.allowlist import (
        ALLOWED_ANCHOR_CREATION_PAIRS,
        CLIENT_PROFILE_COLUMNS,
        WORKSPACE_FORBIDDEN_COLUMNS,
        WORKSPACE_WRITE_COLUMNS,
        is_allowed_table,
        is_allowed_workspace_write,
        is_prohibited_table,
        is_workspace_only_table,
    )

    client_pairs = {action: cols for (table, action), cols in WORKSPACE_WRITE_COLUMNS.items()
                    if table == "clients"}
    return (
        # every controlled-writer path is still denied
        is_workspace_only_table("clients")
        and is_prohibited_table("clients")
        and not is_allowed_table("clients")
        and not any(table == "clients" for table, _ in ALLOWED_ANCHOR_CREATION_PAIRS)
        # the workspace path is exactly create + update of the client profile columns
        and set(client_pairs) == {"create_client_profile", "update_client_profile"}
        and client_pairs["update_client_profile"] == CLIENT_PROFILE_COLUMNS
        and client_pairs["create_client_profile"] == CLIENT_PROFILE_COLUMNS | {"id"}
        and not any(cols & WORKSPACE_FORBIDDEN_COLUMNS for cols in WORKSPACE_WRITE_COLUMNS.values())
        # and nothing else through it: no delete, no other action, no governance column
        and not is_allowed_workspace_write("clients", "delete_client", {"id"})
        and not is_allowed_workspace_write("clients", "update_client_profile", {"owner_id"})
        and not is_allowed_workspace_write("clients", "create_draft", {"organization_label"})
    )
