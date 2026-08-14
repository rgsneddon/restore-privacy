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


def is_browser_safe_https_url(url: str) -> bool:
    """True only for ``https://`` absolute URLs safe for an HTTPS shop page.

    Chrome shows “can't be downloaded securely” when an HTTPS page (e.g.
    restoreprivacy.online) redirects or links to an ``http://`` installer.
    Server-side proxy fetch may still use HTTP loopback to the store; browser
    302 must never use plain HTTP.
    """
    u = (url or "").strip()
    if not u.lower().startswith("https://"):
        return False
    # Reject credentials-in-URL and empty host
    try:
        from urllib.parse import urlparse

        p = urlparse(u)
    except Exception:  # noqa: BLE001
        return False
    if (p.scheme or "").lower() != "https":
        return False
    if not (p.hostname or "").strip():
        return False
    if p.username or p.password:
        return False
    return True


def browser_host_base_url(base: str | None = None) -> str | None:
    """Return a Helsinki base usable for **browser** delivery, or None.

    Requires HTTPS. HTTP-only bases (e.g. ``http://host:8081/paid-assets`` from
    ``RPT_VPS_ASSET_HOST``) are refused so callers fall back to same-origin stream.
    """
    raw = (base if base is not None else host_delivery_base_url()).strip().rstrip("/")
    if not raw:
        return None
    # Normalize missing scheme is not enough — only accept https
    if raw.lower().startswith("http://"):
        return None
    if not raw.lower().startswith("https://"):
        # bare host: not enough for browser delivery
        return None
    if not is_browser_safe_https_url(raw + "/"):
        # is_browser_safe needs path-tolerant check
        if not is_browser_safe_https_url(raw):
            return None
    return raw


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
    """True when operator wants browser→Helsinki delivery and config is present.

    Requires an **HTTPS** base so the HTTPS shop never 302s to plain HTTP
    (Chrome “can't be downloaded securely”).
    """
    flag = (os.environ.get("RPT_HOST_DELIVERY") or "").strip().lower()
    if flag in ("0", "false", "no", "off"):
        return False
    if flag in ("1", "true", "yes", "on"):
        # Still require secret + HTTPS base even when forced on
        return bool(host_delivery_secret() and browser_host_base_url())
    # Default: on when secret + HTTPS browser base resolve
    return bool(host_delivery_secret() and browser_host_base_url())


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
        from downloads import RELEASE_VERSION, version_for_catalog_filename  # type: ignore
    except Exception:  # noqa: BLE001
        try:
            from status_page.downloads import (  # type: ignore
                RELEASE_VERSION,
                version_for_catalog_filename,
            )
        except Exception:  # noqa: BLE001
            RELEASE_VERSION = ""
            version_for_catalog_filename = None  # type: ignore
    mapped = ""
    if callable(version_for_catalog_filename):
        try:
            mapped = str(version_for_catalog_filename(name) or "").strip()
        except Exception:  # noqa: BLE001
            mapped = ""
    ver = (version or mapped or RELEASE_VERSION or "").strip()
    if not ver or ver not in name:
        # Require the Downloads Map version (or fallback pin) in the basename
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
    require_https: bool = True,
) -> str | None:
    """Build signed Helsinki URL for a catalog installer, or None if refused.

    Pure enough for unit tests when *secret* / *base_url* / *now* are injected.
    When *require_https* is True (default), plain ``http://`` bases are refused
    so browsers on an HTTPS shop never receive mixed-content download URLs.
    """
    pair = safe_catalog_version_and_filename(filename, version=version)
    if not pair:
        return None
    ver, name = pair
    sec = (secret if secret is not None else host_delivery_secret()).strip()
    if base_url is not None:
        base = (base_url or "").strip().rstrip("/")
        if require_https:
            if not base.lower().startswith("https://") or not is_browser_safe_https_url(
                base if "://" in base else f"https://{base}/"
            ):
                # Explicit inject: only accept https absolute base
                if not base.lower().startswith("https://"):
                    return None
    else:
        base = browser_host_base_url() if require_https else (
            host_delivery_base_url().strip().rstrip("/") or None
        )
        if not base:
            return None
    if not sec or not base:
        return None
    if require_https and not is_browser_safe_https_url(f"{base}/{ver}/{name}"):
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
    out = f"{base}/{ver}/{name}?{q}"
    if require_https and not is_browser_safe_https_url(out):
        return None
    return out


def host_delivery_plan(
    filename: str,
    *,
    force_enabled: bool | None = None,
    probe: bool = False,
    urlopen: Any | None = None,
    probe_timeout: float = 8.0,
) -> dict[str, Any] | None:
    """If host delivery should be used for *filename*, return plan dict.

    Keys: ``url``, ``version``, ``filename``, ``source`` (= ``helsinki_host``).
    Returns None when disabled, misconfigured, or filename not catalog-safe.

    When *probe* is True, mint a URL and require a quick Helsinki reachability
    check (first byte). On probe failure return None so the status host can fall
    back to ``open_release_asset`` proxy/local path.
    """
    if force_enabled is None:
        enabled = host_delivery_enabled()
    else:
        # Forced on still needs HTTPS base + secret for browser safety
        enabled = bool(force_enabled) and bool(
            host_delivery_secret() and browser_host_base_url()
        )
        if force_enabled and not enabled:
            # Allow unit tests that inject via build_host_delivery_url mocks
            enabled = bool(force_enabled)
    if not enabled:
        return None
    url = build_host_delivery_url(filename, require_https=True)
    if not url or not is_browser_safe_https_url(url):
        return None
    pair = safe_catalog_version_and_filename(filename)
    if not pair:
        return None
    ver, name = pair
    if probe and not probe_host_asset_reachable(
        url, urlopen=urlopen, timeout=probe_timeout
    ):
        return None
    return {
        "url": url,
        "version": ver,
        "filename": name,
        "source": "helsinki_host",
    }


def probe_host_asset_reachable(
    url: str,
    *,
    urlopen: Any | None = None,
    timeout: float = 8.0,
) -> bool:
    """True if *url* responds with HTTP 200/206 and at least one body byte.

    Used before 302 so a dead Helsinki store falls back to status-host proxy.
    *urlopen* is injectable for unit tests.
    """
    import urllib.request

    target = (url or "").strip()
    if not target.startswith("http://") and not target.startswith("https://"):
        return False
    open_url = urlopen or urllib.request.urlopen
    try:
        req = urllib.request.Request(
            target,
            headers={
                "User-Agent": "restore-privacy-host-delivery-probe",
                "Range": "bytes=0-0",
            },
            method="GET",
        )
        with open_url(req, timeout=float(timeout)) as resp:
            code = int(getattr(resp, "status", None) or resp.getcode() or 0)
            if code not in (200, 206):
                return False
            chunk = resp.read(1)
            return bool(chunk)
    except Exception:  # noqa: BLE001
        return False


def probe_vps_catalog_asset(
    filename: str,
    *,
    version: str | None = None,
    urlopen: Any | None = None,
    timeout: float = 12.0,
) -> bool:
    """True when Helsinki serves *filename* for the catalog pin (token header).

    Server-side probe used by free Suite download so a flaky signed-URL probe
    does not claim "not on the store" when the file is present and the shared
    fetch token matches.
    """
    import urllib.request

    name = (filename or "").strip()
    if not name or ".." in name or "/" in name or "\\" in name:
        return False
    try:
        from payments import vps_asset_fetch_token, vps_asset_url  # type: ignore
    except Exception:  # noqa: BLE001
        try:
            from status_page.payments import (  # type: ignore
                vps_asset_fetch_token,
                vps_asset_url,
            )
        except Exception:  # noqa: BLE001
            return False
    token = (vps_asset_fetch_token() or "").strip()
    if not token:
        return False
    try:
        target = vps_asset_url(name, version=version)
    except Exception:  # noqa: BLE001
        return False
    open_url = urlopen or urllib.request.urlopen
    try:
        req = urllib.request.Request(
            target,
            headers={
                "User-Agent": "restore-privacy-suite-free-probe",
                "X-RPT-Asset-Token": token,
                "Range": "bytes=0-0",
            },
            method="GET",
        )
        with open_url(req, timeout=float(timeout)) as resp:
            code = int(getattr(resp, "status", None) or resp.getcode() or 0)
            if code not in (200, 206):
                return False
            return bool(resp.read(1))
    except Exception:  # noqa: BLE001
        return False


def suite_free_delivery_plan(
    filename: str,
    *,
    probe: bool = True,
    soft_redirect: bool = True,
    urlopen: Any | None = None,
    probe_timeout: float = 12.0,
) -> dict[str, Any] | None:
    """Plan free Suite installer delivery (no paid grant).

    Prefers a short-lived **HTTPS** Helsinki signed URL so the browser pulls the
    multi-MB package directly. When *probe* is True, prefer a token probe of the
    catalog object; if that fails but *soft_redirect* is True and a signed URL
    can still be minted, return the redirect anyway (browser→Helsinki often
    works when Render→Helsinki probe is flaky). Returns None when no delivery
    plan is possible (caller should try ``open_release_asset`` then 502).
    """
    name = (filename or "").strip()
    if not name:
        return None
    if not host_delivery_enabled() and not (
        host_delivery_secret() and browser_host_base_url()
    ):
        # Still allow mint when secret+base present even if flag off via default
        if not (host_delivery_secret() and browser_host_base_url()):
            return None
    url = build_host_delivery_url(name, require_https=True)
    if not url or not is_browser_safe_https_url(url):
        return None
    pair = safe_catalog_version_and_filename(name)
    if not pair:
        return None
    ver, safe_name = pair
    store_ok = False
    if probe:
        store_ok = probe_vps_catalog_asset(
            safe_name,
            version=ver,
            urlopen=urlopen,
            timeout=probe_timeout,
        )
        if not store_ok:
            store_ok = probe_host_asset_reachable(
                url, urlopen=urlopen, timeout=min(probe_timeout, 10.0)
            )
    if store_ok or soft_redirect or not probe:
        return {
            "url": url,
            "version": ver,
            "filename": safe_name,
            "source": "helsinki_host",
            "store_probed": bool(store_ok),
        }
    return None


def is_signed_helsinki_delivery_url(url: str) -> bool:
    """True when *url* is an **HTTPS** paid-assets signed delivery link (not free GitHub)."""
    u = (url or "").strip()
    if not is_browser_safe_https_url(u):
        return False
    low = u.lower()
    if "github.com" in low:
        return False
    if "/paid-assets/" not in low:
        return False
    # Must carry short-lived signature params (not a bare permanent path)
    if "sig=" not in low or "exp=" not in low:
        return False
    return True
