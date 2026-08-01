#!/usr/bin/env python3
"""Planned multi-product architecture inventory (trees + package slots).

Single durable contract for “what programs/apps exist” in the monorepo:
Suite client platforms, residual node path, public status host, rpOS desktop,
Pens · Tables · Slides, browser/Rx companion, node-installer, node-operator,
rpMail/rpOffice brand slots. Consumed by tests and operator checks.

Does **not** invent products outside this list. Optional release binaries may
be empty while path conventions and trees remain required.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

# Live public residual dial peers only (never US/RO, never flyclient hidden).
PUBLIC_RESIDUAL_PEER_CODES: tuple[str, ...] = ("IS", "DE")
RETIRED_RESIDUAL_PEER_CODES: tuple[str, ...] = ("US", "RO")

# Suite free/catalog platforms that must always appear as required package slots.
SUITE_REQUIRED_PLATFORMS: tuple[str, ...] = (
    "windows",
    "android",
    "macos",
    "ios",
    "linux",
)

# Brand inventory kinds that list_brand_installer_packages must emit.
BRAND_PACKAGE_KINDS: tuple[str, ...] = (
    "suite_client",
    "browser",
    "rpos",
    "rpos_app",
    "node_installer",
    "node_operator",
    "rpmail",
    "rpoffice",
)

# Package entry scripts (relative to monorepo root) for inventory kinds.
PACKAGE_ENTRY_SCRIPTS: dict[str, str] = {
    "suite_client": "scripts/package_restore_privacy_suite.py",
    "browser": "scripts/package_browser_rx.py",
    "rpos": "scripts/package_rpos.py",
    "rpos_app": "scripts/package_pts_apps.py",
    "node_installer": "scripts/package_node_installers.py",
    "node_operator": "scripts/package_node_operator_linux.py",
    "rpmail": "scripts/package_rpmail_rpoffice.py",
    "rpoffice": "scripts/package_rpmail_rpoffice.py",
}


def planned_programs(*, repo_root: Path | None = None) -> list[dict[str, Any]]:
    """Ordered planned programs/apps with structural homes and honesty flags.

    Each row:
      id, product, trees (repo-relative dirs/files that must exist),
      package_kind (brand inventory kind or ""), package_entry (script or ""),
      desktop_only, mobile_installable, public_residual_dial,
      proprietary_suite (True → never claim full FOSS for this surface),
      notes
    """
    _ = repo_root  # reserved for future overlays
    return [
        {
            "id": "suite_client",
            "product": "Restore Privacy Suite",
            "trees": ["client_app", "client", "client/connect.py", "client/multihop.py"],
            "package_kind": "suite_client",
            "package_entry": PACKAGE_ENTRY_SCRIPTS["suite_client"],
            "required_platforms": list(SUITE_REQUIRED_PLATFORMS),
            "desktop_only": False,
            "mobile_installable": True,  # Suite clients include iOS/Android
            "public_residual_dial": False,
            "proprietary_suite": True,
            "notes": (
                "Free installers + KEYGEN residual Connect; tabs VPN · % · EVOLVE"
            ),
        },
        {
            "id": "residual_node",
            "product": "Residual node (fleet)",
            "trees": ["node", "node/install.sh", "scripts/selfhost_node.sh", "product"],
            "package_kind": "node_installer",
            "package_entry": PACKAGE_ENTRY_SCRIPTS["node_installer"],
            "required_platforms": [],
            "desktop_only": False,
            "mobile_installable": False,
            "public_residual_dial": True,  # IS/DE catalog only
            "proprietary_suite": False,
            "notes": "Full selfhost/zram+LUKS path for fleet VPS peers only",
        },
        {
            "id": "status_host",
            "product": "Public status host",
            "trees": ["status_page", "status_page/app.py", "status_page/downloads.py", "public_site"],
            "package_kind": "",
            "package_entry": "",
            "required_platforms": [],
            "desktop_only": False,
            "mobile_installable": False,
            "public_residual_dial": False,
            "proprietary_suite": True,
            "notes": "Shop + free Suite download + KEYGEN checkout; no operator console on public Pages",
        },
        {
            "id": "rpos",
            "product": "rpOS",
            "trees": [
                "rpos",
                "rpos/installer",
                "rpos/installer/pipeline.py",
                "rpos/rxshell",
                "rpos/rxshell/__main__.py",
                "rpos/rxshell/runner.py",
                "client/flyclient_hidden_node.py",
            ],
            "package_kind": "rpos",
            "package_entry": PACKAGE_ENTRY_SCRIPTS["rpos"],
            "required_platforms": [],
            "desktop_only": True,
            "mobile_installable": False,
            "public_residual_dial": False,
            "proprietary_suite": False,
            "notes": (
                "Desktop-only RESTORE path (monopin 0.2.0+); RxShell multi-language "
                "CLI; free apps bundle; flyclient hidden multi-hop hook "
                "(not public dial, not full selfhost)"
            ),
        },
        {
            "id": "rxshell",
            "product": "RxShell",
            "trees": [
                "rpos/rxshell",
                "rpos/rxshell/__main__.py",
                "rpos/rxshell/runner.py",
                "rpos/rxshell/repl.py",
            ],
            "package_kind": "rpos",
            "package_entry": PACKAGE_ENTRY_SCRIPTS["rpos"],
            "required_platforms": [],
            "desktop_only": True,
            "mobile_installable": False,
            "public_residual_dial": False,
            "proprietary_suite": False,
            "notes": (
                "PowerShell-type multi-language CLI of rpOS; shell/Python/JS/"
                "PowerShell-style via host runtimes; not full MS PowerShell parity"
            ),
        },
        {
            "id": "rpos_apps",
            "product": "Pens · Tables · Slides",
            "trees": [
                "rpos/apps",
                "rpos/apps/rpoffice",
                "rpos/apps/packages/pens",
                "rpos/apps/packages/tables",
                "rpos/apps/packages/slides",
            ],
            "package_kind": "rpos_app",
            "package_entry": PACKAGE_ENTRY_SCRIPTS["rpos_app"],
            "required_platforms": [],
            "desktop_only": True,
            "mobile_installable": False,
            "public_residual_dial": False,
            "proprietary_suite": False,
            "notes": "Free with rpOS; Desktop launchers after RESTORE",
        },
        {
            "id": "browser_rx",
            "product": "Rx Privacy Browser / extension",
            "trees": ["browser_extension", "browser_extension/manifest.json"],
            "package_kind": "browser",
            "package_entry": PACKAGE_ENTRY_SCRIPTS["browser"],
            "required_platforms": [],
            "desktop_only": False,
            "mobile_installable": False,
            "public_residual_dial": False,
            "proprietary_suite": True,
            "notes": "Suite companion packages under catalog monopin dir",
        },
        {
            "id": "node_operator",
            "product": "Node Operator",
            "trees": ["node_operator", "node_operator/app.py", "node/operator_admin.py"],
            "package_kind": "node_operator",
            "package_entry": PACKAGE_ENTRY_SCRIPTS["node_operator"],
            "required_platforms": [],
            "desktop_only": False,
            "mobile_installable": False,
            "public_residual_dial": False,
            "proprietary_suite": False,
            "notes": "Operator GUI/controller; not public Pages FOSS dump",
        },
        {
            "id": "rpmail",
            "product": "rpMail",
            "trees": ["rpos/sdk/apps/email_client"],
            "package_kind": "rpmail",
            "package_entry": PACKAGE_ENTRY_SCRIPTS["rpmail"],
            "required_platforms": [],
            "desktop_only": True,
            "mobile_installable": False,
            "public_residual_dial": False,
            "proprietary_suite": False,
            "notes": "Brand desktop mail slot (inventory release path rpmail/)",
        },
        {
            "id": "rpoffice",
            "product": "rpOffice",
            "trees": ["rpos/apps/rpoffice", "rpos/sdk/apps/word_processor"],
            "package_kind": "rpoffice",
            "package_entry": PACKAGE_ENTRY_SCRIPTS["rpoffice"],
            "required_platforms": [],
            "desktop_only": True,
            "mobile_installable": False,
            "public_residual_dial": False,
            "proprietary_suite": False,
            "notes": "Brand desktop office slot (inventory release path rpoffice/)",
        },
        {
            "id": "product_family_landings",
            "product": "Browser / Vault schedule landings",
            "trees": ["status_page/product_family.py", "status_page/public_chrome.py"],
            "package_kind": "",
            "package_entry": "",
            "required_platforms": [],
            "desktop_only": False,
            "mobile_installable": False,
            "public_residual_dial": False,
            "proprietary_suite": True,
            "notes": "Style-only landings; omit VPN shop/wipe; Q3 2026/2027 copy",
        },
    ]


def list_brand_kinds_from_packages(
    *,
    suite_version: str | None = None,
    repo_root: Path | None = None,
) -> list[str]:
    """Kinds emitted by shipped brand_package_inventory (real entry point)."""
    import sys

    root = Path(repo_root) if repo_root else ROOT
    scripts = str(root / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    from brand_package_inventory import brand_package_kinds, list_brand_installer_packages

    rows = list_brand_installer_packages(
        suite_version=suite_version, repo_root=root
    )
    kinds = sorted({str(r.get("kind") or "") for r in rows if r.get("kind")})
    # Cross-check helper
    _ = brand_package_kinds()
    return kinds


def validate_architecture(
    *,
    repo_root: Path | None = None,
    suite_version: str | None = None,
) -> dict[str, Any]:
    """Validate trees, brand kinds, package entries, Suite required platforms.

    Returns a report with ok=True only when no structural gaps remain for
    required layout (optional binaries may still be missing).
    """
    root = Path(repo_root) if repo_root else ROOT
    gaps: list[str] = []
    warnings: list[str] = []
    programs = planned_programs(repo_root=root)

    # --- trees ---
    for prog in programs:
        for rel in prog.get("trees") or []:
            p = root / str(rel)
            if not p.exists():
                gaps.append(f"missing_tree:{prog['id']}:{rel}")

    # --- package entry scripts ---
    for prog in programs:
        entry = str(prog.get("package_entry") or "").strip()
        if not entry:
            continue
        if not (root / entry).is_file():
            gaps.append(f"missing_package_entry:{prog['id']}:{entry}")

    # --- brand inventory kinds ---
    try:
        import sys

        scripts = str(root / "scripts")
        if scripts not in sys.path:
            sys.path.insert(0, scripts)
        from brand_package_inventory import list_brand_installer_packages

        rows = list_brand_installer_packages(
            suite_version=suite_version, repo_root=root
        )
    except Exception as exc:  # noqa: BLE001
        gaps.append(f"brand_inventory_import:{exc}")
        rows = []

    kinds = {str(r.get("kind") or "") for r in rows}
    for kind in BRAND_PACKAGE_KINDS:
        if kind not in kinds:
            gaps.append(f"brand_kind_missing:{kind}")

    # Suite required platforms
    suite_plats = {
        str(r.get("platform") or "")
        for r in rows
        if r.get("kind") == "suite_client" and r.get("required")
    }
    for plat in SUITE_REQUIRED_PLATFORMS:
        if plat not in suite_plats:
            gaps.append(f"suite_required_platform_missing:{plat}")

    # Each brand row must have product, platform, relative_path shape
    for r in rows:
        if not str(r.get("product") or "").strip():
            gaps.append(f"empty_product:{r.get('kind')}:{r.get('platform')}")
        if not str(r.get("platform") or "").strip():
            gaps.append(f"empty_platform:{r.get('kind')}:{r.get('filename')}")
        rel = str(r.get("relative_path") or "")
        if not rel or ".." in rel or rel.startswith("/"):
            gaps.append(f"bad_relative_path:{r.get('kind')}:{rel!r}")
        # required suite files must exist when claimed required
        if r.get("required"):
            found = root / "releases" / rel
            if not found.is_file():
                # also accept status_page/assets
                alt = root / "status_page" / "assets" / str(r.get("version") or "") / str(
                    r.get("filename") or ""
                )
                if not alt.is_file():
                    gaps.append(f"required_package_missing:{rel}")

    # Optional slots: record emptiness without failing
    optional_empty: list[str] = []
    for r in rows:
        if r.get("required"):
            continue
        rel = str(r.get("relative_path") or "")
        p = root / "releases" / rel
        if not p.is_file():
            optional_empty.append(rel)

    # Honesty: desktop-only programs must not claim mobile install
    for prog in programs:
        if prog.get("desktop_only") and prog.get("mobile_installable"):
            gaps.append(f"desktop_mobile_contradiction:{prog['id']}")

    # Public residual peers from multihop catalog
    try:
        sys_root = str(root)
        if sys_root not in __import__("sys").path:
            __import__("sys").path.insert(0, sys_root)
        from client.multihop import product_country_catalog

        codes = tuple(n.code for n in product_country_catalog())
        if set(codes) != set(PUBLIC_RESIDUAL_PEER_CODES):
            gaps.append(f"public_catalog_codes:{codes}")
        for bad in RETIRED_RESIDUAL_PEER_CODES:
            if bad in codes:
                gaps.append(f"retired_peer_live:{bad}")
    except Exception as exc:  # noqa: BLE001
        gaps.append(f"public_catalog_import:{exc}")

    return {
        "ok": len(gaps) == 0,
        "gaps": gaps,
        "warnings": warnings,
        "programs": len(programs),
        "brand_rows": len(rows),
        "brand_kinds": sorted(kinds),
        "suite_required_platforms": sorted(suite_plats),
        "optional_empty": optional_empty,
        "public_residual_peers": list(PUBLIC_RESIDUAL_PEER_CODES),
        "retired_residual_peers": list(RETIRED_RESIDUAL_PEER_CODES),
    }


def architecture_summary_text(
    *,
    repo_root: Path | None = None,
    suite_version: str | None = None,
) -> str:
    """Human-readable inventory summary for SCRATCH / operator logs."""
    root = Path(repo_root) if repo_root else ROOT
    report = validate_architecture(repo_root=root, suite_version=suite_version)
    lines = [
        "PLANNED ARCHITECTURE INVENTORY",
        f"ok={report['ok']}",
        f"programs={report['programs']}",
        f"brand_rows={report['brand_rows']}",
        f"brand_kinds={','.join(report['brand_kinds'])}",
        f"suite_required={','.join(report['suite_required_platforms'])}",
        f"public_residual={','.join(report['public_residual_peers'])}",
        f"retired={','.join(report['retired_residual_peers'])}",
        f"optional_empty={len(report['optional_empty'])}",
        "",
        "PROGRAMS",
    ]
    for prog in planned_programs(repo_root=root):
        lines.append(
            f"- {prog['id']}: {prog['product']} "
            f"kind={prog.get('package_kind') or '-'} "
            f"desktop_only={prog.get('desktop_only')} "
            f"entry={prog.get('package_entry') or '-'}"
        )
    if report["gaps"]:
        lines.append("")
        lines.append("GAPS")
        for g in report["gaps"]:
            lines.append(f"  ! {g}")
    if report["optional_empty"]:
        lines.append("")
        lines.append("OPTIONAL_EMPTY (structure ok; binary absent)")
        for rel in report["optional_empty"][:40]:
            lines.append(f"  · {rel}")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    import json
    import sys

    if "--json" in sys.argv:
        print(json.dumps(validate_architecture(), indent=2))
    else:
        print(architecture_summary_text())
        raise SystemExit(0 if validate_architecture()["ok"] else 1)
