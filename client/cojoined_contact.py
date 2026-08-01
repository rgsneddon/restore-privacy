"""Single client contact for co-joined residual node (VPN + rpAI + Perccent).

Clients use one residual host:port for Connect; Ned/rpAI and Perccent ride
private hooks on the same monopin host (ui_port), not separate peer lists.
"""

from __future__ import annotations

from typing import Any

try:
    from .endpoint import DEFAULT_ENDPOINT, PRODUCT_NODE_HOST, PRODUCT_NODE_PORT
except ImportError:  # pragma: no cover — plain path import in unit tests
    from endpoint import (  # type: ignore
        DEFAULT_ENDPOINT,
        PRODUCT_NODE_HOST,
        PRODUCT_NODE_PORT,
    )

# Default UI port for private co-joined hooks on residual monopin hosts.
COJOINED_UI_PORT = 8080


def cojoined_single_contact(
    *,
    host: str | None = None,
    port: int | None = None,
    ui_port: int | None = None,
) -> dict[str, Any]:
    """Return the one residual contact for the co-joined node stack.

    Pure helper — no network. Matches product monopin defaults when args omitted.
    """
    h = (host if host is not None else PRODUCT_NODE_HOST or DEFAULT_ENDPOINT.host).strip()
    p = int(port if port is not None else PRODUCT_NODE_PORT or DEFAULT_ENDPOINT.port)
    ui = int(ui_port if ui_port is not None else COJOINED_UI_PORT)
    return {
        "host": h,
        "port": p,
        "ui_port": ui,
        "contact": f"{h}:{p}",
        "cojoined": True,
        "roles": ("vpn", "rpai", "perccent"),
        "hooks": {
            "vpn": {"scheme": "residual-udp", "host": h, "port": p},
            "rpai": {"scheme": "http-private", "path": "/api/private/rpai", "port": ui},
            "perccent": {
                "scheme": "http-private",
                "path": "/api/private/perc",
                "port": ui,
            },
        },
        "note": (
            "One residual monopin contact. VPN HELLO uses host:port; "
            "Ned/rpAI and Perccent use private UI hooks on the same host."
        ),
    }


def primary_residual_endpoint() -> tuple[str, int]:
    """(host, port) for residual Connect — single point of contact."""
    c = cojoined_single_contact()
    return str(c["host"]), int(c["port"])
