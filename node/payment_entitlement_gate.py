"""Node residual HELLO payment entitlement gate.

When enabled, CLIENT_HELLO is admitted only if the device Ed25519 public key
is bound to an active **paid** Connect entitlement **or** an active KEYGEN-free
**device trial** on the status host
(``GET /api/device-entitlement?device_pub=…`` — paid bind first, then 72h trial).

Operators set::

    RPT_REQUIRE_PAYMENT_ENTITLEMENT=1   # product default when gate is on
    RPT_ENTITLEMENT_API_BASE=https://restoreprivacy.online

Lab / unit tests: ``RPT_REQUIRE_PAYMENT_ENTITLEMENT=0`` skips the remote check.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable


def payment_entitlement_required_on_node() -> bool:
    """Whether residual HELLO requires a bound paid device entitlement.

    Product node process sets ``RPT_REQUIRE_PAYMENT_ENTITLEMENT=1`` at startup
    (see :mod:`node.server`). Unit tests leave it unset/off so crypto HELLO
    suites do not need a live status host. Explicit ``0`` disables the gate.
    """
    raw = os.environ.get("RPT_REQUIRE_PAYMENT_ENTITLEMENT", "0").strip().lower()
    if raw in ("0", "false", "no", "off", ""):
        return False
    return True


def entitlement_api_base() -> str:
    base = (os.environ.get("RPT_ENTITLEMENT_API_BASE") or "").strip()
    if not base:
        base = (
            os.environ.get("RPT_PUBLIC_BASE_URL") or "https://restoreprivacy.online"
        ).strip()
    return base.rstrip("/") or "https://restoreprivacy.online"


def device_entitlement_url(device_pub_hex: str, *, base_url: str | None = None) -> str:
    base = (base_url or entitlement_api_base()).rstrip("/")
    q = urllib.parse.urlencode({"device_pub": device_pub_hex})
    return f"{base}/api/device-entitlement?{q}"


def device_pub_hex(client_pub: bytes) -> str:
    return (client_pub or b"").hex().lower()


# Short TTL cache: device_pub_hex -> (allowed, expires_at)
_cache: dict[str, tuple[bool, float]] = {}
_CACHE_TTL_SEC = float(os.environ.get("RPT_ENTITLEMENT_CACHE_SEC", "45") or "45")


def clear_entitlement_cache() -> None:
    _cache.clear()


def fetch_device_entitlement(
    device_pub_hex: str,
    *,
    base_url: str | None = None,
    timeout: float = 4.0,
) -> dict[str, Any]:
    """GET status host device entitlement JSON."""
    pub = (device_pub_hex or "").strip().lower()
    if len(pub) != 64:
        return {"connect_allowed": False, "error": "bad_device_pub"}
    url = device_entitlement_url(pub, base_url=base_url)
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "RestorePrivacy-node-entitlement/0.3.4",
            "Accept": "application/json",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            raw = resp.read().decode("utf-8", errors="replace")
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError, ValueError) as exc:
        return {"connect_allowed": False, "error": str(exc)}
    return {"connect_allowed": False, "error": "bad_response"}


def device_may_connect(
    client_pub: bytes,
    *,
    require: bool | None = None,
    base_url: str | None = None,
    fetch: Callable[[str], dict[str, Any]] | None = None,
    now: float | None = None,
    use_cache: bool = True,
) -> bool:
    """True when residual HELLO may proceed for this device pub.

    Fail-closed when require is True and remote says not allowed or errors.
    """
    req = payment_entitlement_required_on_node() if require is None else bool(require)
    if not req:
        return True
    pub = device_pub_hex(client_pub)
    if len(pub) != 64:
        return False
    t = now if now is not None else time.time()
    if use_cache:
        hit = _cache.get(pub)
        if hit is not None and hit[1] > t:
            return hit[0]
    if fetch is not None:
        remote = fetch(pub)
    else:
        remote = fetch_device_entitlement(pub, base_url=base_url)
    allowed = bool(remote.get("connect_allowed"))
    if use_cache:
        _cache[pub] = (allowed, t + max(5.0, _CACHE_TTL_SEC))
    return allowed


def assert_device_may_connect(
    client_pub: bytes,
    **kwargs: Any,
) -> None:
    """Raise AdmissionError-compatible ValueError when not entitled."""
    if not device_may_connect(client_pub, **kwargs):
        raise PermissionError("payment entitlement required for residual HELLO")
