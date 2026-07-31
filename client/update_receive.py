"""Client-side receive path for residual node operator update-push directives.

Desktop/mobile UIs may surface ``store`` as an upgrade banner. Pure helpers —
no status-host paid download mint.
"""

from __future__ import annotations

from typing import Any

# Re-export shipped node receive/apply so client trees share one path.
try:
    from node.update_push import (
        apply_client_update_directive,
        client_receive_update_directives,
        parse_update_push_json,
    )
except ImportError:  # pragma: no cover
    from update_push import (  # type: ignore
        apply_client_update_directive,
        client_receive_update_directives,
        parse_update_push_json,
    )

try:
    from node.protocol import MsgType, parse_update_push, peek_type
except ImportError:  # pragma: no cover
    from protocol import MsgType, parse_update_push, peek_type  # type: ignore


def handle_residual_update_frame(data: bytes) -> dict[str, Any]:
    """If *data* is UPDATE_PUSH, parse and apply; else return not_update."""
    t = peek_type(data)
    if t != MsgType.UPDATE_PUSH:
        return {"ok": False, "error": "not_update_push", "store": None}
    _sid, payload = parse_update_push(data)
    blob = parse_update_push_json(payload)
    return apply_client_update_directive(blob)


__all__ = [
    "apply_client_update_directive",
    "client_receive_update_directives",
    "handle_residual_update_frame",
    "parse_update_push_json",
]
