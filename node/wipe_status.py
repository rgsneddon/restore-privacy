"""Node residual wipe/drain status for client hop signalling.

Public /api/status stays title-only. Drain/ready is exposed on residual
NODE_STATUS control frames (KEEPALIVE reply) and optional private JSON.
"""

from __future__ import annotations

import os
from typing import Any

from node.protocol import (
    NODE_STATUS_DRAINING,
    NODE_STATUS_READY,
    NODE_STATUS_REBUILDING,
    pack_node_status,
)


def current_wipe_state(install_root: str | None = None) -> dict[str, Any]:
    """Read exclusive rebuild lock → ready|draining|rebuilding for clients.

    Host field is intentionally empty by default: clients treat empty host as
    "this residual" (transport-bound or preferred private poll). Emitting a
    hostname or non-catalog IP used to break monopin equality and suppress
    hop-off/rejoin — avoid that footgun.
    """
    try:
        from node.rebuild_lock import read_lock
    except Exception:  # noqa: BLE001
        return {"state": "ready", "host": "", "role": "", "private": True}
    root = install_root or os.environ.get("INSTALL_ROOT") or "/opt/restore-privacy"
    lock = read_lock(root)
    # Optional monopin only when env pin is set (catalog residual IP).
    host = (os.environ.get("RPT_RESIDUAL_HOST") or os.environ.get("RPT_NODE_HOST") or "").strip()
    if lock is None:
        return {"state": "ready", "host": host, "role": "", "private": True}
    st = (lock.state or "").strip().lower()
    if st == "draining":
        state = "draining"
    elif st in ("rebuilding", "held"):
        state = "rebuilding"
    else:
        state = "draining"
    return {
        "state": state,
        "host": host,
        "role": (lock.role or "").strip().lower(),
        "private": True,
    }


def flags_for_wipe_state(state: str) -> int:
    s = (state or "").strip().lower()
    if s == "rebuilding":
        return NODE_STATUS_REBUILDING | NODE_STATUS_DRAINING
    if s == "draining":
        return NODE_STATUS_DRAINING
    return NODE_STATUS_READY


def pack_current_node_status(
    *,
    session_id: bytes = b"\x00" * 8,
    install_root: str | None = None,
) -> bytes:
    """Wire NODE_STATUS for the current rebuild-lock state."""
    info = current_wipe_state(install_root)
    flags = flags_for_wipe_state(str(info.get("state") or "ready"))
    return pack_node_status(
        flags=flags,
        host=str(info.get("host") or ""),
        role=str(info.get("role") or ""),
        session_id=session_id,
    )
