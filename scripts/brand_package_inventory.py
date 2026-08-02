#!/usr/bin/env python3
"""Full-brand installer inventory for admin Helsinki push (Suite + rpOS + apps + extras).

Pure inventory of completed installer slots under ``releases/``. Used by
``host_paid_assets_vps`` / operator admin so Push Suite packages is not limited
to the five client platforms.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def _suite_version() -> str:
    try:
        sys_path_status = ROOT / "status_page"
        import sys

        if str(sys_path_status) not in sys.path:
            sys.path.insert(0, str(sys_path_status))
        from downloads import RELEASE_VERSION

        return str(RELEASE_VERSION).strip() or "1.0.7"
    except Exception:
        return "1.0.7"


def list_brand_installer_packages(
    *,
    suite_version: str | None = None,
    repo_root: Path | None = None,
) -> list[dict[str, Any]]:
    """Return ordered brand installer slots (pure relative to monorepo layout).

    Each row:
      kind, product, platform, filename, relative_path, version,
      min_bytes, required (bool)
    """
    root = Path(repo_root) if repo_root else ROOT
    ver = (suite_version or "").strip() or _suite_version()
    rows: list[dict[str, Any]] = []

    # --- Suite client platforms (catalog monopin) ---
    try:
        import sys

        sp = str(root / "status_page")
        if sp not in sys.path:
            sys.path.insert(0, sp)
        from downloads import list_catalog_platform_packages

        for p in list_catalog_platform_packages(version=ver):
            rows.append(
                {
                    "kind": "suite_client",
                    "product": "Restore Privacy Suite",
                    "platform": p["platform"],
                    "filename": p["filename"],
                    "relative_path": p["relative_path"],
                    "version": p["version"],
                    "min_bytes": 1_000_000,
                    "required": True,
                }
            )
    except Exception:
        # Fallback hard names if downloads unavailable
        for plat, suffix in (
            ("windows", "windows-x64-setup.exe"),
            ("android", "android.apk"),
            ("macos", "macos.zip"),
            ("ios", "ios.zip"),
            ("linux", "linux-x64.tar.gz"),
        ):
            fname = f"restore-privacy-client-{ver}-{suffix}"
            rows.append(
                {
                    "kind": "suite_client",
                    "product": "Restore Privacy Suite",
                    "platform": plat,
                    "filename": fname,
                    "relative_path": f"{ver}/{fname}",
                    "version": ver,
                    "min_bytes": 1_000_000,
                    "required": True,
                }
            )

    # --- Browser / Rx multi-platform (Suite monopin; valid expandable archives) ---
    try:
        import sys as _sys

        _sp = str(root / "scripts")
        if _sp not in _sys.path:
            _sys.path.insert(0, _sp)
        from package_browser_rx import platform_package_matrix as _rx_matrix

        for slot in _rx_matrix(ver):
            rows.append(
                {
                    "kind": "browser",
                    "product": str(slot.get("product") or "Rx Privacy Browser"),
                    "platform": str(slot.get("platform") or "browser"),
                    "filename": str(slot["filename"]),
                    "relative_path": str(slot["relative_path"]),
                    "version": ver,
                    "min_bytes": 1_000,
                    "required": bool(slot.get("default_download")),
                    "format": str(slot.get("format") or "zip"),
                }
            )
    except Exception:
        for plat, fname in (
            ("chromium", f"restore-privacy-browser-extension-{ver}.zip"),
            ("default", f"restore-privacy-rx-browser-{ver}.zip"),
            ("macos", f"restore-privacy-rx-browser-{ver}-macos.zip"),
            ("windows", f"restore-privacy-rx-browser-{ver}-windows.zip"),
            ("linux-x86_64", f"restore-privacy-rx-browser-{ver}-linux-x86_64.tar.gz"),
            ("linux-aarch64", f"restore-privacy-rx-browser-{ver}-linux-aarch64.tar.gz"),
            ("ios", f"restore-privacy-rx-browser-{ver}-ios.zip"),
            ("android", f"restore-privacy-rx-browser-{ver}-android.zip"),
        ):
            rows.append(
                {
                    "kind": "browser",
                    "product": "Rx Privacy Browser",
                    "platform": plat,
                    "filename": fname,
                    "relative_path": f"{ver}/{fname}",
                    "version": ver,
                    "min_bytes": 1_000,
                    "required": plat == "default",
                }
            )

    # --- rpOS desktop packages (current monopin includes RxShell CLI) ---
    try:
        import sys as _sys

        _scripts = str(root / "scripts")
        if _scripts not in _sys.path:
            _sys.path.insert(0, _scripts)
        from package_rpos import RPOS_VERSION as _rpos_ver_src

        rpos_ver = str(_rpos_ver_src).strip() or "0.2.1"
    except Exception:
        rpos_ver = "0.2.1"
    for plat, fname in (
        ("windows", f"rpos-{rpos_ver}-windows-x64.zip"),
        ("macos", f"rpos-{rpos_ver}-macos.zip"),
        ("linux-x86_64", f"rpos-{rpos_ver}-linux-x86_64.tar.gz"),
        ("linux-aarch64", f"rpos-{rpos_ver}-linux-aarch64.tar.gz"),
    ):
        rows.append(
            {
                "kind": "rpos",
                "product": "rpOS",
                "platform": plat,
                "filename": fname,
                "relative_path": f"rpos/{rpos_ver}/{fname}",
                "version": rpos_ver,
                "min_bytes": 1_000,
                "required": False,
                "features": ["RxShell"],
            }
        )

    # --- Free bundled Pens · Tables · Slides ---
    apps_ver = "0.1.1"
    for brand, key in (("Pens", "pens"), ("Tables", "tables"), ("Slides", "slides")):
        fname = f"{key}-{apps_ver}-installer.zip"
        rows.append(
            {
                "kind": "rpos_app",
                "product": brand,
                "platform": key,
                "filename": fname,
                "relative_path": f"rpos-apps/{apps_ver}/{fname}",
                "version": apps_ver,
                "min_bytes": 500,
                "required": False,
            }
        )

    # --- Node installer multi-platform ---
    node_ver = "1.0.1"
    for plat, fname in (
        ("linux", f"restore-privacy-node-installer-{node_ver}-linux-x64.tar.gz"),
        ("macos", f"restore-privacy-node-installer-{node_ver}-macos.zip"),
        ("windows", f"restore-privacy-node-installer-{node_ver}-windows-x64.zip"),
        ("android", f"restore-privacy-node-installer-{node_ver}-android.zip"),
        ("ios", f"restore-privacy-node-installer-{node_ver}-ios.zip"),
    ):
        rows.append(
            {
                "kind": "node_installer",
                "product": "Node Installer",
                "platform": plat,
                "filename": fname,
                "relative_path": f"node-installer/{node_ver}/{fname}",
                "version": node_ver,
                "min_bytes": 1_000,
                "required": False,
            }
        )

    # --- Node Operator Linux ---
    op_ver = "1.0.1"
    op_name = f"restore-privacy-node-operator-{op_ver}-linux-x64.tar.gz"
    rows.append(
        {
            "kind": "node_operator",
            "product": "Node Operator",
            "platform": "linux",
            "filename": op_name,
            "relative_path": f"node-operator/{op_ver}/{op_name}",
            "version": op_ver,
            "min_bytes": 1_000,
            "required": False,
        }
    )

    # --- rpMail + rpOffice desktop installers ---
    mail_ver = "0.1.1"
    for key, product in (("rpmail", "rpMail"), ("rpoffice", "rpOffice")):
        for plat, fname in (
            ("windows", f"{key}-{mail_ver}-windows.zip"),
            ("macos", f"{key}-{mail_ver}-macos.zip"),
            ("linux-x86_64", f"{key}-{mail_ver}-linux-x86_64.tar.gz"),
            ("linux-aarch64", f"{key}-{mail_ver}-linux-aarch64.tar.gz"),
        ):
            rows.append(
                {
                    "kind": key,
                    "product": product,
                    "platform": plat,
                    "filename": fname,
                    "relative_path": f"{key}/{mail_ver}/{fname}",
                    "version": mail_ver,
                    "min_bytes": 500,
                    "required": False,
                }
            )

    return rows


def brand_package_kinds() -> list[str]:
    return sorted({r["kind"] for r in list_brand_installer_packages()})


def resolve_local_path(
    row: dict[str, Any],
    *,
    repo_root: Path | None = None,
) -> Path | None:
    """First existing non-empty file for a brand inventory row."""
    root = Path(repo_root) if repo_root else ROOT
    rel = str(row.get("relative_path") or "")
    fname = str(row.get("filename") or "")
    ver = str(row.get("version") or "")
    candidates = [
        root / "releases" / rel,
        root / "status_page" / "assets" / ver / fname,
        root / "status_page" / "assets" / str(row.get("version") or "") / fname,
    ]
    # Suite layout also stages under catalog version even for brand extras
    try:
        sv = _suite_version()
        candidates.append(root / "status_page" / "assets" / sv / fname)
        candidates.append(root / "releases" / sv / fname)
    except Exception:
        pass
    for c in candidates:
        try:
            if c.is_file() and c.stat().st_size > 0:
                return c
        except OSError:
            continue
    return None


def inventory_with_presence(
    *,
    suite_version: str | None = None,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Inventory + present/staged flags for admin table."""
    root = Path(repo_root) if repo_root else ROOT
    rows_src = list_brand_installer_packages(
        suite_version=suite_version, repo_root=root
    )
    suite_ver = (suite_version or "").strip() or _suite_version()
    out_rows: list[dict[str, Any]] = []
    for row in rows_src:
        found = resolve_local_path(row, repo_root=root)
        size = int(found.stat().st_size) if found else 0
        # Stage dest: assets/{suite_ver}/ for flat Helsinki layout
        staged = root / "status_page" / "assets" / suite_ver / row["filename"]
        out_rows.append(
            {
                **row,
                "present": found is not None,
                "path": str(found) if found else "",
                "size": size,
                "staged": staged.is_file() and staged.stat().st_size > 0,
                "staged_path": str(staged),
                "status": "pending",
                "progress": 0,
            }
        )
    return {
        "ok": True,
        "suite_version": suite_ver,
        "packages": out_rows,
        "present_count": sum(1 for r in out_rows if r["present"]),
        "staged_count": sum(1 for r in out_rows if r["staged"]),
        "total": len(out_rows),
        "kinds": sorted({r["kind"] for r in out_rows}),
    }


if __name__ == "__main__":
    import json

    print(json.dumps(inventory_with_presence(), indent=2))
