"""Exclusive rebuild / wipe lock — never two node instances at once.

Fleet wipedown is **sequential** across peer residual countries (Iceland first,
then Romania, then new catalog peers). Each wipe holds this exclusive lock for
one country role (``entry``/``is``/``ro``/…). Concurrent multi-node wipe is
refused. Legacy bulk roles ``exit``/``both``/``all`` are still refused so two
nodes cannot be wiped as one operation.

Lock file (default ``$INSTALL_ROOT/var/rpt-rebuild.lock``) is JSON::

    {
      "role": "entry" | "is" | "ro" | …,
      "pid": 1234,
      "state": "draining" | "rebuilding" | "held",
      "started_at": "...",
      "hostname": "..."
    }

Honesty: this is host-local mutual exclusion, not a distributed consensus
across two VPS boxes. Operators must not run a second wipe from another host
without coordinating (fleet planner enforces IS→RO order at the orchestrator).
"""

from __future__ import annotations

import json
import os
import socket
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

DEFAULT_INSTALL_ROOT = os.environ.get("RPT_INSTALL_ROOT", "/opt/restore-privacy")
LOCK_REL = Path("var") / "rpt-rebuild.lock"
# Legacy + country codes: single peer wipe only (never bulk multi-node roles)
# Single-peer roles: legacy entry + catalog country codes (IS, RO, DE, …)
ALLOWED_ROLES = frozenset({"entry", "is", "ro", "de"})
# Bulk multi-node wipe roles refused (use sequential fleet planner instead)
FORBIDDEN_WEEKLY_ROLES = frozenset({"exit", "both", "all"})


def lock_path(install_root: str | Path | None = None) -> Path:
    root = Path(install_root or DEFAULT_INSTALL_ROOT)
    return root / LOCK_REL


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class RebuildLockState:
    """Parsed lock file contents."""

    role: str
    pid: int
    state: str  # held | draining | rebuilding
    started_at: str
    hostname: str
    path: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "pid": self.pid,
            "state": self.state,
            "started_at": self.started_at,
            "hostname": self.hostname,
            "path": self.path,
        }

    @property
    def entry_draining(self) -> bool:
        """True when this host is mid-wipe (any peer role) — clients should failover."""
        return self.state in (
            "draining",
            "rebuilding",
            "held",
        )


def read_lock(install_root: str | Path | None = None) -> Optional[RebuildLockState]:
    """Return current lock or None if absent/invalid."""
    path = lock_path(install_root)
    try:
        if not path.is_file():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return None
        role = str(data.get("role") or "").strip().lower()
        if not role:
            return None
        return RebuildLockState(
            role=role,
            pid=int(data.get("pid") or 0),
            state=str(data.get("state") or "held").strip().lower(),
            started_at=str(data.get("started_at") or ""),
            hostname=str(data.get("hostname") or ""),
            path=str(path),
        )
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None


def is_locked(install_root: str | Path | None = None) -> bool:
    return read_lock(install_root) is not None


def _normalize_lock_role(role: str) -> str:
    r = (role or "").strip().lower()
    if r in ("iceland",):
        return "is"
    if r in ("romania",):
        return "ro"
    return r


def is_allowed_rebuild_role(role: str) -> bool:
    """True for single-peer wipe roles (entry/IS/RO or future catalog codes)."""
    role_n = _normalize_lock_role(role)
    if role_n in FORBIDDEN_WEEKLY_ROLES:
        return False
    if role_n in ALLOWED_ROLES:
        return True
    # Future catalog country codes (2–3 letter) — single peer only
    if 2 <= len(role_n) <= 3 and role_n.isalpha():
        return True
    return False


def acquire_rebuild_lock(
    role: str = "entry",
    *,
    install_root: str | Path | None = None,
    state: str = "held",
    pid: Optional[int] = None,
    force: bool = False,
) -> tuple[bool, str, Optional[RebuildLockState]]:
    """Acquire exclusive rebuild lock.

    Returns (ok, message, state). Second concurrent acquire **fails closed**.
    Fleet wipe uses one country role at a time (IS then RO then new peers).
    Bulk roles ``exit``/``both``/``all`` are refused.
    """
    role_n = _normalize_lock_role(role)
    if role_n in FORBIDDEN_WEEKLY_ROLES or not is_allowed_rebuild_role(role_n):
        return (
            False,
            f"refusing rebuild lock for role={role!r} "
            f"(single peer only; sequential fleet wipe — never exit/both/all concurrent)",
            None,
        )
    path = lock_path(install_root)
    existing = read_lock(install_root)
    if existing is not None and not force:
        return (
            False,
            f"rebuild already active: role={existing.role} state={existing.state} "
            f"pid={existing.pid} started={existing.started_at} "
            f"(never run two node wipe/rebuild instances at once)",
            existing,
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    st = RebuildLockState(
        role=role_n,
        pid=int(pid if pid is not None else os.getpid()),
        state=(state or "held").strip().lower() or "held",
        started_at=_utc_now(),
        hostname=socket.gethostname(),
        path=str(path),
    )
    # Atomic-ish write: write temp then replace
    tmp = path.with_suffix(path.suffix + f".{st.pid}.tmp")
    payload = {
        "role": st.role,
        "pid": st.pid,
        "state": st.state,
        "started_at": st.started_at,
        "hostname": st.hostname,
    }
    try:
        # Re-check after mkdir (race)
        if not force and path.is_file() and read_lock(install_root) is not None:
            return (
                False,
                "rebuild lock race: already held (exclusive single-instance)",
                read_lock(install_root),
            )
        tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        os.replace(str(tmp), str(path))
    except OSError as exc:
        try:
            tmp.unlink(missing_ok=True)  # type: ignore[call-arg]
        except TypeError:
            try:
                if tmp.is_file():
                    tmp.unlink()
            except OSError:
                pass
        return False, f"failed to write rebuild lock: {exc}", None
    return True, f"acquired rebuild lock role={st.role} state={st.state}", st


def update_rebuild_lock_state(
    state: str,
    *,
    install_root: str | Path | None = None,
) -> tuple[bool, str]:
    """Update lock state (e.g. draining → rebuilding) without releasing."""
    cur = read_lock(install_root)
    if cur is None:
        return False, "no rebuild lock held"
    ok, msg, _ = acquire_rebuild_lock(
        cur.role,
        install_root=install_root,
        state=state,
        pid=cur.pid,
        force=True,
    )
    return ok, msg


def release_rebuild_lock(
    *,
    install_root: str | Path | None = None,
    expected_pid: Optional[int] = None,
) -> tuple[bool, str]:
    """Release exclusive lock. Optional pid check for safety."""
    path = lock_path(install_root)
    cur = read_lock(install_root)
    if cur is None:
        return True, "no lock present"
    if expected_pid is not None and cur.pid and cur.pid != int(expected_pid):
        return (
            False,
            f"refusing release: lock pid={cur.pid} != expected={expected_pid}",
        )
    try:
        path.unlink()
        return True, "released rebuild lock"
    except OSError as exc:
        return False, f"failed to release lock: {exc}"


def entry_is_draining_for_clients(
    install_root: str | Path | None = None,
) -> bool:
    """True when clients should treat entry as unavailable (rebuild in progress).

    Note: remote clients do not see this file unless published; client failover
    primarily uses connect-time health preference + HELLO failure failover.
    """
    cur = read_lock(install_root)
    return bool(cur and cur.entry_draining)
