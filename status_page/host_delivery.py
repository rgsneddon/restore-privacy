"""Short-lived Helsinki paid-asset host delivery (browser pulls multi-MB installers).

Status host validates a paid download grant, then mints a time-limited signed
URL so the **browser** fetches from the Helsinki paid-assets store directly.
That avoids Render double-proxy of 15–50 MB packages (the main slowness).

The long-lived ``RPT_ASSET_FETCH_TOKEN`` is used only as an HMAC key / server
header secret — it is **never** placed in browser-visible permanent links.
Signed query tokens expire (default 15 minutes) and are bound to
``version`` + ``filename``.

Env:
  RPT_HOST_DELIVERY     default on when Helsinki base + fetch token set; ``0`` disables
  RPT_HOST_DELIVERY_TTL_SEC  default 900
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import time
from typing import Any
from urllib.parse import urlencode


DEFAULT_HOST_DELIVERY_TTL_SEC = 900
# Max TTL clamp (2 hours) so a misconfig cannot mint week-long public links
MAX_HOST_DELIVERY_TTL_SEC = 7200


def host_delivery_ttl_sec() -> int:
    raw = (os.environ.get("RPT_HOST_DELIVERY_TTL_SEC") or "").strip()
    if not raw:
        return DEFAULT_HOST_DELIVERY_TTL_SEC
    try:
        n = int(raw)
    except ValueError:
        return DEFAULT_HOST_DELIVERY_TTL_SEC
    return max(60, min(n, MAX_HOST_DELIVERY_TTL_SEC))


def host_delivery_enabled() -> bool:
    """True when operator wants browser→Helsinki delivery and config is present."""
    flag = (os.environ.get("RPT_HOST_DELIVERY") or "").strip().lower()
    if flag in ("0", "false", "no", "off"):
        return False
    if flag in ("1", "true", "yes", "on"):
        return True
    # Default: on when both base + signing secret resolve
    return bool(host_delivery_secret() and host_delivery_base_url())


def host_delivery_secret() -> str:
    """HMAC key for delivery tokens (same material as VPS fetch token)."""
    try:
        from payments import vps_asset_fetch_token  # type: ignore
    except Exception:  # noqa: BLE001
        try:
            from status_page.payments import vps_asset_fetch_token  # type: ignore
        except Exception:  # noqa: BLE001
            vps_asset_fetch_token = None  # type: ignore
    if vps_asset_fetch_token is not None:
        try:
            return (vps_asset_fetch_token() or "").strip()
        except Exception:  # noqa: BLE001
            pass
    for key in ("RPT_ASSET_FETCH_TOKEN", "RPT_VPS_ASSET_TOKEN"):
        val = (os.environ.get(key) or "").strip()
        if val:
            return val
    return ""


def host_delivery_base_url() -> str:
    try:
        from payments import vps_asset_base_url  # type: ignore
    except Exception:  # noqa: BLE001
        try:
            from status_page.payments import vps_asset_base_url  # type: ignore
        except Exception:  # noqa: BLE001
            return (os.environ.get("RPT_VPS_ASSET_BASE") or "").strip().rstrip("/")
    try:
        return (vps_asset_base_url() or "").strip().rstrip("/")
    except Exception:  # noqa: BLE001
        return (os.environ.get("RPT_VPS_ASSET_BASE") or "").strip().rstrip("/")


def delivery_message(
    *,
    version: str,
    filename: str,
    exp: int | str,
    nonce: str,
) -> bytes:
    """Canonical message for HMAC (must match Helsinki serve)."""
    ver = (version or "").strip()
    name = (filename or "").strip()
    return f"{ver}\n{name}\n{exp}\n{nonce}".encode("utf-8")


def mint_delivery_signature(
    *,
    version: str,
    filename: str,
    exp: int | str,
    nonce: str,
    secret: str,
) -> str:
    """Hex HMAC-SHA256 over :func:`delivery_message`."""
    key = (secret or "").encode("utf-8")
    if not key:
        return ""
    return hmac.new(
        key,
        delivery_message(version=version, filename=filename, exp=exp, nonce=nonce),
        hashlib.sha256,
    ).hexdigest()


def verify_delivery_signature(
    *,
    version: str,
    filename: str,
    exp: int | str,
    nonce: str,
    sig: str,
    secret: str,
    now: float | None = None,
) -> bool:
    """True when signature matches and exp is still in the future."""
    if not (secret and sig and nonce and version and filename):
        return False
    try:
        exp_i = int(exp)
    except (TypeError, ValueError):
        return False
    t = time.time() if now is None else float(now)
    if exp_i < int(t):
        return False
    # Reject absurd future exp (clock skew + max TTL)
    if exp_i > int(t) + MAX_HOST_DELIVERY_TTL_SEC + 120:
        return False
    expected = mint_delivery_signature(
        version=version,
        filename=filename,
        exp=exp_i,
        nonce=nonce,
        secret=secret,
    )
    if not expected:
        return False
    return hmac.compare_digest(expected, (sig or "").strip().lower()) or hmac.compare_digest(
        expected, (sig or "").strip()
    )


def safe_catalog_version_and_filename(
    filename: str,
    *,
    version: str | None = None,
) -> tuple[str, str] | None:
    """Return (version, basename) only for current catalog packages."""
    try:
        from payments import _safe_catalog_filename  # type: ignore
    except Exception:  # noqa: BLE001
        try:
            from status_page.payments import _safe_catalog_filename  # type: ignore
        except Exception:  # noqa: BLE001
            return None
    name = _safe_catalog_filename(filename)
    if not name:
        return None
    try:
        from downloads import RELEASE_VERSION  # type: ignore
    except Exception:  # noqa: BLE001
        try:
            from status_page.downloads import RELEASE_VERSION  # type: ignore
        except Exception:  # noqa: BLE001
            RELEASE_VERSION = ""
    ver = (version or RELEASE_VERSION or "").strip()
    if not ver or ver not in name:
        # Require monopin substring in filename (same as Helsinki pin filter)
        return None
    return ver, name


def build_host_delivery_url(
    filename: str,
    *,
    version: str | None = None,
    secret: str | None = None,
    base_url: str | None = None,
    ttl_sec: int | None = None,
    now: float | None = None,
    nonce: str | None = None,
) -> str | None:
    """Build signed Helsinki URL for a catalog installer, or None if refused.

    Pure enough for unit tests when *secret* / *base_url* / *now* are injected.
    """
    pair = safe_catalog_version_and_filename(filename, version=version)
    if not pair:
        return None
    ver, name = pair
    sec = (secret if secret is not None else host_delivery_secret()).strip()
    base = (base_url if base_url is not None else host_delivery_base_url()).strip().rstrip(
        "/"
    )
    if not sec or not base:
        return None
    ttl = int(ttl_sec if ttl_sec is not None else host_delivery_ttl_sec())
    ttl = max(60, min(ttl, MAX_HOST_DELIVERY_TTL_SEC))
    t0 = time.time() if now is None else float(now)
    exp = int(t0) + ttl
    n = (nonce or secrets.token_hex(8)).strip()
    if not n:
        return None
    sig = mint_delivery_signature(
        version=ver, filename=name, exp=exp, nonce=n, secret=sec
    )
    if not sig:
        return None
    q = urlencode({"exp": str(exp), "n": n, "sig": sig})
    return f"{base}/{ver}/{name}?{q}"


def host_delivery_plan(
    filename: str,
    *,
    force_enabled: bool | None = None,
) -> dict[str, Any] | None:
    """If host delivery should be used for *filename*, return plan dict.

    Keys: ``url``, ``version``, ``filename``, ``source`` (= ``helsinki_host``).
    Returns None when disabled, misconfigured, or filename not catalog-safe.
    """
    enabled = host_delivery_enabled() if force_enabled is None else bool(force_enabled)
    if not enabled:
        return None
    url = build_host_delivery_url(filename)
    if not url:
        return None
    pair = safe_catalog_version_and_filename(filename)
    if not pair:
        return None
    ver, name = pair
    return {
        "url": url,
        "version": ver,
        "filename": name,
        "source": "helsinki_host",
    }
