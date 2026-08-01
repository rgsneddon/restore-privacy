"""Settings-gated CHECK BREADCRUMBS → client self-update path.

When the user enables **CHECK BREADCRUMBS** in Settings, the client may fetch
Helsinki breadcrumbs/current (or a local fixture) and apply a pending update
directive via :mod:`client.update_receive`. When the flag is off, no auto
self-update runs.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable, Mapping, Optional

# Exact Settings label (product string — grepped by tests).
CHECK_BREADCRUMBS_LABEL = "CHECK BREADCRUMBS"
KEY_CHECK_BREADCRUMBS = "check_breadcrumbs"

DEFAULT_BREADCRUMBS_BASE = "https://135.181.152.10.sslip.io/breadcrumbs"
DEFAULT_MANIFEST_PATH = "current/manifest.json"

TransportFn = Callable[[str, dict[str, str], float], str]


def check_breadcrumbs_enabled(settings: Any) -> bool:
    """True when Settings allows CHECK BREADCRUMBS opt-in path."""
    if settings is None:
        return False
    if isinstance(settings, Mapping):
        return bool(settings.get(KEY_CHECK_BREADCRUMBS) or settings.get("checkBreadcrumbs"))
    for attr in (
        KEY_CHECK_BREADCRUMBS,
        "check_breadcrumbs",
        "checkBreadcrumbs",
    ):
        if hasattr(settings, attr):
            return bool(getattr(settings, attr))
    return False


def breadcrumbs_base_url(env: Mapping[str, str] | None = None) -> str:
    e = env if env is not None else os.environ
    return (
        str(e.get("RPT_BREADCRUMBS_BASE") or "").strip()
        or DEFAULT_BREADCRUMBS_BASE
    ).rstrip("/")


def _default_transport(url: str, headers: dict[str, str], timeout_s: float) -> str:
    req = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:  # noqa: S310
        return resp.read().decode("utf-8", errors="replace")


def fetch_breadcrumbs_manifest(
    *,
    base_url: str | None = None,
    rel_path: str = DEFAULT_MANIFEST_PATH,
    token: str | None = None,
    transport: TransportFn | None = None,
    timeout_s: float = 8.0,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """GET breadcrumbs manifest JSON (token-gated Helsinki vault)."""
    e = env if env is not None else os.environ
    tok = (token if token is not None else str(
        e.get("RPT_BREADCRUMB_TOKEN") or e.get("RPT_ASSET_FETCH_TOKEN") or ""
    ).strip())
    base = (base_url or breadcrumbs_base_url(e)).rstrip("/")
    url = f"{base}/{rel_path.lstrip('/')}"
    headers = {"Accept": "application/json"}
    if tok:
        headers["X-RPT-Asset-Token"] = tok
    fn = transport or _default_transport
    try:
        body = fn(url, headers, float(timeout_s))
        data = json.loads(body)
        if not isinstance(data, dict):
            return {"ok": False, "error": "invalid manifest JSON", "manifest": None}
        return {"ok": True, "error": "", "manifest": data, "url": url}
    except urllib.error.HTTPError as exc:
        return {"ok": False, "error": f"HTTP {exc.code}", "manifest": None, "url": url}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)[:200], "manifest": None, "url": url}


def load_local_breadcrumbs_manifest(path: Path | str) -> dict[str, Any]:
    """Load a local manifest.json (tests / offline stage)."""
    p = Path(path)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"ok": False, "error": "invalid JSON", "manifest": None}
        return {"ok": True, "error": "", "manifest": data, "path": str(p)}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)[:200], "manifest": None}


def monopin_from_manifest(manifest: Mapping[str, Any] | None) -> str:
    if not manifest:
        return ""
    return str(manifest.get("monopin") or manifest.get("version") or "").strip()


def download_url_for_monopin(
    monopin: str,
    *,
    platform: str = "",
    breadcrumbs_base: str | None = None,
) -> str:
    """Best-effort product download notes URL for an update directive."""
    pin = (monopin or "").strip()
    base = (breadcrumbs_base or DEFAULT_BREADCRUMBS_BASE).rstrip("/")
    # Paid download still goes through status host after payment; breadcrumbs
    # point operators/clients at the monopin vault + public shop.
    if pin:
        return f"https://restoreprivacy.online/?monopin={pin}"
    return "https://restoreprivacy.online/"


def apply_breadcrumbs_update(
    *,
    settings: Any,
    product_version: str,
    manifest: Mapping[str, Any] | None = None,
    platform: str = "",
    force: bool = False,
) -> dict[str, Any]:
    """If CHECK BREADCRUMBS is on, store pending update when vault monopin differs.

    *force* is for tests only (still requires check enabled unless settings
    explicitly allow).
    """
    from client.update_receive import apply_client_update_directive

    enabled = check_breadcrumbs_enabled(settings)
    if not enabled:
        return {
            "ok": True,
            "skipped": True,
            "reason": "CHECK BREADCRUMBS off",
            "store": None,
            "label": CHECK_BREADCRUMBS_LABEL,
        }
    pin = monopin_from_manifest(manifest)
    cur = (product_version or "").strip()
    if not pin:
        return {
            "ok": False,
            "skipped": False,
            "error": "manifest missing monopin",
            "store": None,
            "label": CHECK_BREADCRUMBS_LABEL,
        }
    if pin == cur and not force:
        return {
            "ok": True,
            "skipped": True,
            "reason": f"already on monopin {cur}",
            "monopin": pin,
            "store": None,
            "label": CHECK_BREADCRUMBS_LABEL,
        }
    url = download_url_for_monopin(pin, platform=platform)
    applied = apply_client_update_directive(
        {
            "version": pin,
            "url": url,
            "message": f"CHECK BREADCRUMBS: monopin {pin} available",
            "kind": "rpt_client_update",
        }
    )
    return {
        "ok": bool(applied.get("ok")),
        "skipped": False,
        "monopin": pin,
        "product_version": cur,
        "store": applied.get("store"),
        "error": applied.get("error") or "",
        "label": CHECK_BREADCRUMBS_LABEL,
    }


def check_breadcrumbs_and_apply(
    *,
    settings: Any,
    product_version: str,
    platform: str = "",
    local_manifest_path: Path | str | None = None,
    transport: TransportFn | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Full Settings path: gate → load/fetch manifest → apply pending update."""
    if not check_breadcrumbs_enabled(settings):
        return {
            "ok": True,
            "skipped": True,
            "reason": "CHECK BREADCRUMBS off",
            "store": None,
            "label": CHECK_BREADCRUMBS_LABEL,
        }
    if local_manifest_path:
        fetched = load_local_breadcrumbs_manifest(local_manifest_path)
    else:
        fetched = fetch_breadcrumbs_manifest(transport=transport, env=env)
    if not fetched.get("ok"):
        return {
            "ok": False,
            "skipped": False,
            "error": fetched.get("error") or "fetch failed",
            "store": None,
            "label": CHECK_BREADCRUMBS_LABEL,
        }
    return apply_breadcrumbs_update(
        settings=settings,
        product_version=product_version,
        manifest=fetched.get("manifest"),
        platform=platform,
    )


def load_product_settings_for_breadcrumbs() -> Any:
    """Load Windows or Linux product settings (desktop client path)."""
    import sys as _sys

    if _sys.platform == "win32":
        from client.windows.settings_store import load_settings

        return load_settings()
    if _sys.platform.startswith("linux"):
        from client.linux.settings_store import load_settings

        return load_settings()
    # macOS desktop may use Windows-style local prefs or none — try Windows path first
    try:
        from client.windows.settings_store import load_settings

        return load_settings()
    except Exception:  # noqa: BLE001
        return None


def default_product_version() -> str:
    """Read monorepo client/VERSION when present; else catalog-ish default."""
    try:
        from pathlib import Path as _P

        # client/breadcrumbs_check.py → parents[1] = monorepo root when installed in-tree
        root = _P(__file__).resolve().parents[1]
        ver_path = root / "client" / "VERSION"
        if ver_path.is_file():
            return ver_path.read_text(encoding="utf-8").strip() or "1.0.1"
    except Exception:  # noqa: BLE001
        pass
    return "1.0.1"


def run_check_breadcrumbs_for_product(
    *,
    settings: Any | None = None,
    product_version: str | None = None,
    platform: str = "",
    local_manifest_path: Path | str | None = None,
    transport: TransportFn | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Production entry: load settings if needed, then gate → fetch → apply.

    Called from Settings when the user enables CHECK BREADCRUMBS, and from the
    residual Connect success path when the flag is already on.
    """
    s = settings if settings is not None else load_product_settings_for_breadcrumbs()
    ver = (product_version or "").strip() or default_product_version()
    plat = (platform or "").strip()
    if not plat:
        import sys as _sys

        if _sys.platform == "win32":
            plat = "windows"
        elif _sys.platform.startswith("linux"):
            plat = "linux"
        elif _sys.platform == "darwin":
            plat = "macos"
    return check_breadcrumbs_and_apply(
        settings=s,
        product_version=ver,
        platform=plat,
        local_manifest_path=local_manifest_path,
        transport=transport,
        env=env,
    )


def on_check_breadcrumbs_setting_changed(
    enabled: bool,
    *,
    settings: Any | None = None,
    product_version: str | None = None,
    platform: str = "",
    local_manifest_path: Path | str | None = None,
    transport: TransportFn | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Settings toggle handler: off → no-op; on → run full check/apply path.

    *settings* when provided should already reflect the new *enabled* value
    (caller persists prefs first, then calls this).
    """
    if not enabled:
        return {
            "ok": True,
            "skipped": True,
            "reason": "CHECK BREADCRUMBS off",
            "store": None,
            "label": CHECK_BREADCRUMBS_LABEL,
        }
    if settings is None:
        settings = {KEY_CHECK_BREADCRUMBS: True}
    elif isinstance(settings, Mapping):
        settings = dict(settings)
        settings[KEY_CHECK_BREADCRUMBS] = True
    else:
        try:
            setattr(settings, KEY_CHECK_BREADCRUMBS, True)
        except Exception:  # noqa: BLE001
            pass
        try:
            setattr(settings, "check_breadcrumbs", True)
        except Exception:  # noqa: BLE001
            pass
    return run_check_breadcrumbs_for_product(
        settings=settings,
        product_version=product_version,
        platform=platform,
        local_manifest_path=local_manifest_path,
        transport=transport,
        env=env,
    )
