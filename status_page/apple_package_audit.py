"""Audit staged Apple catalog zips for monopin productVersion honesty.

Windows hosts cannot notarize; operators often stage placeholder zips under
``status_page/assets/{VERSION}/``. This helper reads CFBundleShortVersionString
from the real zip contents so CI / ops can detect mislabeled packages.
"""

from __future__ import annotations

import plistlib
import zipfile
from pathlib import Path
from typing import Any


def _read_short_version_from_plist_bytes(data: bytes) -> str | None:
    try:
        pl = plistlib.loads(data)
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(pl, dict):
        return None
    ver = pl.get("CFBundleShortVersionString") or pl.get("CFBundleVersion")
    if ver is None:
        return None
    return str(ver).strip() or None


def inspect_apple_zip(path: Path, *, platform: str) -> dict[str, Any]:
    """Return version audit for one macos/ios catalog zip."""
    out: dict[str, Any] = {
        "path": str(path),
        "platform": platform,
        "exists": path.is_file(),
        "size": path.stat().st_size if path.is_file() else 0,
        "bundle_versions": [],
        "primary_version": None,
        "plist_paths": [],
    }
    if not path.is_file():
        out["error"] = "missing"
        return out
    try:
        with zipfile.ZipFile(path) as zf:
            plist_names = [
                n
                for n in zf.namelist()
                if n.endswith("Info.plist")
                and (
                    (platform == "macos" and "restore_privacy_client.app/Contents/Info.plist" in n)
                    or (platform == "ios" and n.endswith("Runner.app/Info.plist"))
                    or n.count("/") <= 3
                )
            ]
            # Prefer main app Info.plist
            preferred = []
            for n in zf.namelist():
                if platform == "macos" and n.endswith(
                    "restore_privacy_client.app/Contents/Info.plist"
                ):
                    preferred.append(n)
                if platform == "ios" and n.endswith("Runner.app/Info.plist"):
                    preferred.append(n)
            names = preferred or plist_names[:3]
            out["plist_paths"] = names
            versions: list[str] = []
            for n in names:
                ver = _read_short_version_from_plist_bytes(zf.read(n))
                if ver:
                    versions.append(ver)
                    out["bundle_versions"].append({"plist": n, "version": ver})
            out["primary_version"] = versions[0] if versions else None
    except Exception as exc:  # noqa: BLE001
        out["error"] = str(exc)[:200]
    return out


def audit_catalog_apple_packages(
    *,
    version: str,
    assets_root: Path | None = None,
) -> dict[str, Any]:
    """Compare staged Apple zips under assets/{version}/ to catalog monopin."""
    root = assets_root or (
        Path(__file__).resolve().parent / "assets" / version
    )
    macos = root / f"restore-privacy-client-{version}-macos.zip"
    ios = root / f"restore-privacy-client-{version}-ios.zip"
    mac = inspect_apple_zip(macos, platform="macos")
    ios_a = inspect_apple_zip(ios, platform="ios")
    mac_ok = mac.get("primary_version") == version
    ios_ok = ios_a.get("primary_version") == version
    missing = (not mac.get("exists")) or (not ios_a.get("exists"))
    if mac_ok and ios_ok:
        honesty = "Apple zips match catalog monopin"
    elif missing:
        honesty = (
            "STAGED APPLE ZIPS MISSING under assets "
            f"(macos_exists={mac.get('exists')} ios_exists={ios_a.get('exists')}) "
            f"expected={version!r}. Re-build on Mac per client_app/APPLE_HANDOFF_"
            f"{version}.md then re-run host_paid_assets_vps.py --upload "
            "(status_page/assets/* is gitignored)."
        )
    else:
        honesty = (
            "STAGED APPLE ZIPS DO NOT MATCH CATALOG MONOPIN — "
            f"macos={mac.get('primary_version')!r} ios={ios_a.get('primary_version')!r} "
            f"expected={version!r}. Re-build on Mac per client_app/APPLE_HANDOFF_"
            f"{version}.md then re-run host_paid_assets_vps.py --upload."
        )
    return {
        "catalog_version": version,
        "assets_root": str(root),
        "macos": mac,
        "ios": ios_a,
        "macos_matches_catalog": mac_ok,
        "ios_matches_catalog": ios_ok,
        "all_match": bool(mac_ok and ios_ok),
        "placeholder_suspected": not (mac_ok and ios_ok),
        "honesty": honesty,
    }
