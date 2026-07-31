"""Operator update-push directives for connected residual clients.

Node operator GUI (or admin API) enqueues a version/url payload per client or
broadcast; clients pull via :func:`take_update_directives` / receive handler.
Not the status-host paid download mint path.
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Sequence


@dataclass(frozen=True)
class UpdateDirective:
    """Minimal product update payload pushed to residual clients."""

    version: str
    url: str = ""
    message: str = ""
    created_at: float = 0.0
    target_client_id: str = ""  # empty = broadcast to all connected

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": str(self.version or "").strip(),
            "url": str(self.url or "").strip(),
            "message": str(self.message or "").strip(),
            "created_at": float(self.created_at or 0.0),
            "target_client_id": str(self.target_client_id or "").strip(),
            "kind": "rpt_client_update",
        }

    @classmethod
    def from_dict(cls, d: MappingLike) -> "UpdateDirective":
        blob = dict(d or {})
        return cls(
            version=str(blob.get("version") or "").strip(),
            url=str(blob.get("url") or "").strip(),
            message=str(blob.get("message") or "").strip(),
            created_at=float(blob.get("created_at") or 0.0),
            target_client_id=str(blob.get("target_client_id") or "").strip(),
        )


# typing without importing Mapping at runtime cost for from_dict
MappingLike = Any


def validate_update_directive(
    *,
    version: str,
    url: str = "",
    message: str = "",
    target_client_id: str = "",
    now: float | None = None,
) -> tuple[bool, str, UpdateDirective | None]:
    """Pure validation for operator push forms."""
    ver = (version or "").strip()
    if len(ver) < 1:
        return False, "version required", None
    if len(ver) > 64:
        return False, "version too long", None
    u = (url or "").strip()
    if u and not (u.startswith("https://") or u.startswith("http://") or u.startswith("/")):
        return False, "url must be http(s) or path", None
    if len(u) > 2000:
        return False, "url too long", None
    msg = (message or "").strip()
    if len(msg) > 500:
        return False, "message too long", None
    t = float(now if now is not None else time.time())
    d = UpdateDirective(
        version=ver,
        url=u,
        message=msg,
        created_at=t,
        target_client_id=(target_client_id or "").strip(),
    )
    return True, "", d


class UpdatePushQueue:
    """Per-client and broadcast pending update directives (in-memory)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # client_id -> list of directive dicts
        self._pending: dict[str, list[dict[str, Any]]] = {}
        self._broadcast: list[dict[str, Any]] = []
        # delivery log for operator / tests (not public status)
        self._delivered: list[dict[str, Any]] = []

    def push(
        self,
        directive: UpdateDirective,
        *,
        connected_client_ids: Sequence[str] | None = None,
    ) -> dict[str, Any]:
        """Enqueue *directive* for target or all *connected_client_ids*."""
        d = directive if isinstance(directive, UpdateDirective) else UpdateDirective.from_dict(directive)
        payload = d.to_dict()
        if not payload["version"]:
            return {"ok": False, "error": "version required", "delivered_to": []}
        targets: list[str] = []
        with self._lock:
            tid = payload["target_client_id"]
            if tid:
                targets = [tid]
                self._pending.setdefault(tid, []).append(dict(payload))
            else:
                ids = [
                    str(c or "").strip()
                    for c in (connected_client_ids or [])
                    if str(c or "").strip()
                ]
                if not ids:
                    # No live sessions — keep as broadcast for later joiners
                    self._broadcast.append(dict(payload))
                    targets = ["*broadcast*"]
                else:
                    for cid in ids:
                        self._pending.setdefault(cid, []).append(dict(payload))
                    targets = list(ids)
            for cid in targets:
                self._delivered.append(
                    {
                        "client_id": cid,
                        "version": payload["version"],
                        "url": payload["url"],
                        "at": payload["created_at"],
                    }
                )
        return {
            "ok": True,
            "error": "",
            "delivered_to": targets,
            "directive": payload,
            "count": len(targets),
        }

    def pending_for(self, client_id: str) -> list[dict[str, Any]]:
        cid = (client_id or "").strip()
        with self._lock:
            own = list(self._pending.get(cid) or [])
            bcast = [dict(x) for x in self._broadcast]
        return bcast + own

    def take_for_client(self, client_id: str) -> list[dict[str, Any]]:
        """Atomically fetch and clear pending directives for *client_id*."""
        cid = (client_id or "").strip()
        with self._lock:
            own = list(self._pending.pop(cid, []) or [])
            bcast = [dict(x) for x in self._broadcast]
            # Broadcast remains until explicitly cleared; clients get a copy each take
        return bcast + own

    def clear_broadcast(self) -> None:
        with self._lock:
            self._broadcast.clear()

    def delivery_log(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._delivered)


_GLOBAL_Q: UpdatePushQueue | None = None
_GQ_LOCK = threading.Lock()


def global_update_queue() -> UpdatePushQueue:
    global _GLOBAL_Q
    with _GQ_LOCK:
        if _GLOBAL_Q is None:
            _GLOBAL_Q = UpdatePushQueue()
        return _GLOBAL_Q


def reset_global_update_queue_for_tests() -> UpdatePushQueue:
    global _GLOBAL_Q
    with _GQ_LOCK:
        _GLOBAL_Q = UpdatePushQueue()
        return _GLOBAL_Q


def operator_push_update(
    *,
    version: str,
    url: str = "",
    message: str = "",
    target_client_id: str = "",
    connected_client_ids: Sequence[str] | None = None,
    queue: UpdatePushQueue | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    """Shipped operator push entry (GUI and tests call this)."""
    ok, err, d = validate_update_directive(
        version=version,
        url=url,
        message=message,
        target_client_id=target_client_id,
        now=now,
    )
    if not ok or d is None:
        return {"ok": False, "error": err or "invalid", "delivered_to": []}
    q = queue if queue is not None else global_update_queue()
    return q.push(d, connected_client_ids=connected_client_ids)


def client_receive_update_directives(
    client_id: str,
    *,
    queue: UpdatePushQueue | None = None,
) -> list[dict[str, Any]]:
    """Client-side pull of pending update directives (shipped receive path)."""
    q = queue if queue is not None else global_update_queue()
    return q.take_for_client(client_id)


def apply_client_update_directive(payload: dict[str, Any] | None) -> dict[str, Any]:
    """Pure client handler: validate and normalize a received update payload.

    Product UI may show an upgrade banner from the returned ``store`` dict.
    """
    if not payload or not isinstance(payload, dict):
        return {"ok": False, "error": "empty", "store": None}
    d = UpdateDirective.from_dict(payload)
    if not d.version:
        return {"ok": False, "error": "version required", "store": None}
    store = {
        "pending_update_version": d.version,
        "pending_update_url": d.url,
        "pending_update_message": d.message,
        "pending_update_at": d.created_at,
        "kind": "rpt_client_update",
    }
    return {"ok": True, "error": "", "store": store, "directive": d.to_dict()}


def pack_update_push_json(directive: UpdateDirective | dict[str, Any]) -> bytes:
    """JSON body for residual control frame / admin channel."""
    if isinstance(directive, UpdateDirective):
        blob = directive.to_dict()
    else:
        blob = UpdateDirective.from_dict(directive).to_dict()
    return json.dumps(blob, separators=(",", ":"), sort_keys=True).encode("utf-8")


def parse_update_push_json(data: bytes | str) -> dict[str, Any]:
    if isinstance(data, bytes):
        text = data.decode("utf-8", errors="replace")
    else:
        text = str(data or "")
    blob = json.loads(text or "{}")
    if not isinstance(blob, dict):
        raise ValueError("update push JSON must be object")
    return UpdateDirective.from_dict(blob).to_dict()
