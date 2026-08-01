#!/usr/bin/env python3
"""Windows large-drive brand mirror — plan + optional apply for all brand assets.

Duplicates the Restore Privacy monorepo tree and every brand inventory installer
onto a configurable Windows larger-drive destination (env ``RPT_WINDOWS_DRIVE``
or ``--dest``). Pure planning is unit-tested without a live Windows host.

Usage::

  # Plan only (default dry-run) — lists all brand slots + monorepo destination
  python scripts/windows_brand_mirror.py plan
  python scripts/windows_brand_mirror.py plan --dest D:/RestorePrivacyMirror

  # Apply when the large drive is mounted/reachable
  export RPT_WINDOWS_DRIVE=/Volumes/WindowsData/RestorePrivacy
  python scripts/windows_brand_mirror.py apply --dest "$RPT_WINDOWS_DRIVE"

  # Manifest/checklist text for vault breadcrumbs
  python scripts/windows_brand_mirror.py checklist
  python scripts/windows_brand_mirror.py manifest

Environment:
  RPT_WINDOWS_DRIVE   Root on the Windows larger drive (no Mac-only default required)
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "status_page"))

# Monorepo paths that prove a working tree after mirror (relative to repo root).
MONOREPO_MARKERS: tuple[str, ...] = (
    "client/VERSION",
    "scripts/breadcrumbs_vault.py",
    "scripts/brand_package_inventory.py",
    "scripts/windows_brand_mirror.py",
    "status_page/downloads.py",
    "README.md",
)

# Top-level monorepo dirs/files to copy (exclude heavy/local-only noise).
# Brand installers are copied slot-by-slot into releases/ (not a full historic tree).
MONOREPO_TOP_LEVEL: tuple[str, ...] = (
    "client",
    "client_app",
    "scripts",
    "status_page",
    "product",
    "node",
    "node_operator",
    "perc_chain",
    "rpos",
    "browser_extension",
    "beam_privacy_dapp",
    "docs",
    "public_site",
    "tests",
    "README.md",
    "LICENSE",
    "requirements.txt",
    "CREDITS.md",
    "PRIVACY_POLICY.md",
    "AUDIT.md",
    "sundries.txt",
    "render.yaml",
)

SKIP_DIR_NAMES = frozenset(
    {
        ".git",
        ".venv",
        ".venv-brand",
        ".venv-nodeop",
        "__pycache__",
        "node_modules",
        ".dart_tool",
        "build",
        ".gradle",
        ".idea",
        ".DS_Store",
    }
)


def current_monopin() -> str:
    try:
        from downloads import current_catalog_version

        return str(current_catalog_version()).strip() or "0.0.0"
    except Exception:
        pin = (ROOT / "client" / "VERSION").read_text(encoding="utf-8").strip()
        return pin or "0.0.0"


def windows_drive_root(explicit: str | Path | None = None) -> Path | None:
    """Resolve configurable Windows large-drive root (env or arg). None if unset."""
    raw = ""
    if explicit is not None and str(explicit).strip():
        raw = str(explicit).strip()
    else:
        raw = (
            os.environ.get("RPT_WINDOWS_DRIVE", "").strip()
            or os.environ.get("RPT_WINDOWS_LARGE_DRIVE", "").strip()
        )
    if not raw:
        return None
    return Path(raw).expanduser()


def monorepo_dest_name() -> str:
    return "restore-privacy"


def list_brand_slots(
    *,
    suite_version: str | None = None,
    repo_root: Path | None = None,
) -> list[dict[str, Any]]:
    """All brand installer slots (delegates to brand_package_inventory)."""
    from brand_package_inventory import list_brand_installer_packages

    return list_brand_installer_packages(
        suite_version=suite_version, repo_root=repo_root or ROOT
    )


def _source_for_row(
    row: dict[str, Any],
    *,
    repo_root: Path,
) -> Path | None:
    from brand_package_inventory import resolve_local_path

    return resolve_local_path(row, repo_root=repo_root)


def build_windows_mirror_plan(
    *,
    monopin: str | None = None,
    repo_root: Path | None = None,
    dest_root: Path | str | None = None,
) -> dict[str, Any]:
    """Pure plan: monorepo + every brand inventory slot → large-drive destinations.

    Does not perform I/O beyond reading inventory presence under *repo_root*.
    ``dest_root`` may be None (plan still lists relative dests under a placeholder).
    """
    root = Path(repo_root) if repo_root else ROOT
    pin = (monopin or current_monopin()).strip()
    dest = windows_drive_root(dest_root)
    dest_label = str(dest) if dest is not None else "{RPT_WINDOWS_DRIVE}"
    repo_dest_rel = monorepo_dest_name()
    repo_dest = (dest / repo_dest_rel) if dest is not None else None

    brand_rows: list[dict[str, Any]] = []
    copy_pairs: list[dict[str, Any]] = []
    missing_source: list[str] = []
    present_source = 0
    duplicated = 0

    # Monorepo tree pair (logical)
    mono_src = str(root)
    mono_dest = (
        str(repo_dest)
        if repo_dest is not None
        else f"{dest_label}/{repo_dest_rel}"
    )
    copy_pairs.append(
        {
            "kind": "monorepo_tree",
            "src": mono_src,
            "dest": mono_dest,
            "relative": repo_dest_rel,
            "required": True,
        }
    )

    for marker in MONOREPO_MARKERS:
        src_m = root / marker
        dest_m = (
            (repo_dest / marker)
            if repo_dest is not None
            else Path(dest_label) / repo_dest_rel / marker
        )
        src_ok = src_m.is_file() or src_m.is_dir()
        dest_ok = dest_m.is_file() if dest is not None else False
        copy_pairs.append(
            {
                "kind": "monorepo_marker",
                "src": str(src_m),
                "dest": str(dest_m),
                "relative": f"{repo_dest_rel}/{marker}",
                "source_present": src_ok,
                "dest_present": dest_ok,
                "required": True,
            }
        )

    for row in list_brand_slots(suite_version=pin, repo_root=root):
        found = _source_for_row(row, repo_root=root)
        rel = str(row.get("relative_path") or row.get("filename") or "")
        # Destination always under mirrored monorepo releases/
        dest_rel = f"{repo_dest_rel}/releases/{rel}"
        dest_path = (
            (dest / dest_rel)
            if dest is not None
            else Path(dest_label) / dest_rel
        )
        src_present = found is not None
        if src_present:
            present_source += 1
        else:
            missing_source.append(str(row.get("filename") or rel))
        dest_present = False
        if dest is not None and dest_path.is_file() and dest_path.stat().st_size > 0:
            dest_present = True
            duplicated += 1
        entry = {
            "kind": row.get("kind"),
            "product": row.get("product"),
            "platform": row.get("platform"),
            "filename": row.get("filename"),
            "relative_path": rel,
            "version": row.get("version"),
            "required": bool(row.get("required")),
            "source_present": src_present,
            "source_path": str(found) if found else "",
            "dest_rel": dest_rel,
            "dest_path": str(dest_path),
            "dest_present": dest_present,
            "duplicated": dest_present and src_present,
        }
        brand_rows.append(entry)
        if src_present and found is not None:
            copy_pairs.append(
                {
                    "kind": "brand_package",
                    "src": str(found),
                    "dest": str(dest_path),
                    "relative": dest_rel,
                    "filename": row.get("filename"),
                    "brand_kind": row.get("kind"),
                    "required": bool(row.get("required")),
                }
            )

    kinds = sorted({str(r.get("kind") or "") for r in brand_rows})
    return {
        "schema": "rpt.windows_brand_mirror.v1",
        "monopin": pin,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "dest_root": dest_label,
        "dest_configured": dest is not None,
        "dest_reachable": bool(dest is not None and dest.exists()),
        "repo_dest": mono_dest,
        "repo_dest_name": repo_dest_rel,
        "monorepo_markers": list(MONOREPO_MARKERS),
        "brand_packages": brand_rows,
        "brand_slot_count": len(brand_rows),
        "brand_kinds": kinds,
        "present_source_count": present_source,
        "missing_source": missing_source,
        "missing_source_count": len(missing_source),
        "duplicated_on_dest": duplicated,
        "copy_pairs": copy_pairs,
        "native_pe_build": {
            "required": True,
            "script": "scripts/build_windows_multihop.py",
            "output": f"releases/{pin}/restore-privacy-client-{pin}-windows-x64-setup.exe",
            "upload": f"paid_assets/{pin}/",
        },
        "operator_notes": [
            "Set RPT_WINDOWS_DRIVE to the large Windows drive root (or pass --dest).",
            "Mirror monorepo + all brand installers before native PE rebuild.",
            "Native PE seal must run on Windows; replace carry-forward PE before final ship.",
            "After PE build, re-run brand mirror apply so the large drive holds the seal.",
            f"Helsinki breadcrumbs: dist/breadcrumbs/current/WINDOWS_HANDOFF.md (monopin {pin}).",
        ],
    }


def render_windows_brand_checklist(plan: dict[str, Any] | None = None, **kwargs: Any) -> str:
    """Human-readable Windows operator checklist (all brand slots + large-drive mirror)."""
    p = plan or build_windows_mirror_plan(**kwargs)
    pin = p.get("monopin")
    lines = [
        f"# Windows brand breadcrumbs checklist — monopin {pin}",
        "",
        f"Generated: {p.get('generated_at')}",
        f"Large-drive dest: `{p.get('dest_root')}` "
        f"(configured={p.get('dest_configured')}, reachable={p.get('dest_reachable')})",
        f"Monorepo mirror path: `{p.get('repo_dest')}`",
        "",
        "## Operator mandate",
        "",
        f"- Duplicate the **full monorepo** and **every brand installer slot** onto the "
        f"Windows larger drive (`RPT_WINDOWS_DRIVE` / `--dest`).",
        f"- **Native PE seal** for monopin **{pin}** on this Windows machine "
        f"(`scripts\\\\build_windows_multihop.py`).",
        f"- Upload sealed PE (+ brand packages as needed) to Helsinki "
        f"`paid_assets/{pin}/`.",
        "",
        "## Large-drive mirror",
        "",
        "```powershell",
        "# Prefer env on the large drive root, e.g. D:\\RestorePrivacyMirror",
        f"$env:RPT_WINDOWS_DRIVE = \"D:\\RestorePrivacyMirror\"",
        "python scripts\\windows_brand_mirror.py plan",
        "python scripts\\windows_brand_mirror.py apply --dest $env:RPT_WINDOWS_DRIVE",
        "```",
        "",
        f"Brand slots in inventory: **{p.get('brand_slot_count')}** "
        f"(kinds: {', '.join(p.get('brand_kinds') or [])})",
        f"Present on source host: **{p.get('present_source_count')}** / "
        f"{p.get('brand_slot_count')}  ·  Missing source: "
        f"**{p.get('missing_source_count')}**  ·  Already on dest: "
        f"**{p.get('duplicated_on_dest')}**",
        "",
        "## Brand inventory (all installer slots)",
        "",
        "| Kind | Product | Platform | Filename | Source | Dest |",
        "|------|---------|----------|----------|--------|------|",
    ]
    for row in p.get("brand_packages") or []:
        src = "yes" if row.get("source_present") else "MISSING"
        dst = "yes" if row.get("dest_present") else "—"
        lines.append(
            f"| {row.get('kind')} | {row.get('product')} | {row.get('platform')} | "
            f"`{row.get('filename')}` | {src} | {dst} |"
        )
    pe = p.get("native_pe_build") or {}
    lines.extend(
        [
            "",
            "## Native Windows PE seal",
            "",
            f"- Script: `{pe.get('script')}`",
            f"- Output: `{pe.get('output')}`",
            f"- Upload target: `{pe.get('upload')}`",
            "",
            "```powershell",
            "cd " + str(p.get("repo_dest") or "C:\\path\\to\\restore-privacy"),
            "git pull",
            "python scripts\\build_windows_multihop.py",
            f"$env:RPT_SSH_HOST=\"135.181.152.10\"",
            f"$env:RPT_SSH_USER=\"root\"",
            f"$env:RPT_SSH_KEY=\"$HOME\\.ssh\\id_ed25519_restore_privacy_eu\"",
            f"python scripts\\host_paid_assets_vps.py --stage --upload "
            f"--version {pin} --force --install-serve",
            "```",
            "",
            "## Steps",
            "",
            "1. Mount/set large drive → `RPT_WINDOWS_DRIVE`",
            "2. `python scripts\\windows_brand_mirror.py apply` (repos + brand binaries)",
            "3. Verify monorepo markers + brand files on the drive",
            "4. Build native PE; re-apply mirror so the seal lands on the large drive",
            "5. Upload to Helsinki; `python scripts\\breadcrumbs_vault.py stage` / publish",
            "",
            "## Notes",
            "",
        ]
    )
    for n in p.get("operator_notes") or []:
        lines.append(f"- {n}")
    lines.append("")
    return "\n".join(lines)


def render_windows_handoff_brand_section(plan: dict[str, Any] | None = None, **kwargs: Any) -> str:
    """Markdown section appended to WINDOWS_HANDOFF for brand-wide + large-drive mirror."""
    p = plan or build_windows_mirror_plan(**kwargs)
    pin = p.get("monopin")
    kinds = ", ".join(p.get("brand_kinds") or [])
    return f"""

---

## Brand-wide large-drive mirror (all installer slots)

The Windows **larger drive** must hold a working monorepo copy **and** every brand
asset from the inventory — not only the Suite Windows setup.exe.

| | |
|--|--|
| **Env** | `RPT_WINDOWS_DRIVE` (or `--dest`) = large-drive root |
| **Monorepo dest** | `{{RPT_WINDOWS_DRIVE}}/{monorepo_dest_name()}` |
| **Brand slots** | **{p.get('brand_slot_count')}** ({kinds}) |
| **Monopin** | **{pin}** |

```powershell
$env:RPT_WINDOWS_DRIVE = "D:\\RestorePrivacyMirror"   # larger drive
python scripts\\windows_brand_mirror.py plan
python scripts\\windows_brand_mirror.py apply --dest $env:RPT_WINDOWS_DRIVE
```

Inventory kinds covered: suite_client, browser/Rx, rpos, rpos_app (Pens/Tables/Slides),
node_installer, node_operator, rpmail, rpoffice.

Full checklist: vault `WINDOWS_BRAND_CHECKLIST.md` / `windows_brand_mirror.json`
(after `python scripts\\breadcrumbs_vault.py stage`).

Native PE remains required: `scripts\\build_windows_multihop.py` →
`releases\\{pin}\\restore-privacy-client-{pin}-windows-x64-setup.exe`.
"""


def plan_inventory_filenames(plan: dict[str, Any] | None = None, **kwargs: Any) -> set[str]:
    """Set of brand inventory filenames present in a mirror plan (for tests)."""
    p = plan or build_windows_mirror_plan(**kwargs)
    return {str(r.get("filename") or "") for r in (p.get("brand_packages") or []) if r.get("filename")}


def apply_mirror_plan(
    plan: dict[str, Any] | None = None,
    *,
    dest_root: Path | str | None = None,
    dry_run: bool = True,
    repo_root: Path | None = None,
    monopin: str | None = None,
) -> dict[str, Any]:
    """Copy monorepo top-level + present brand packages per plan.

    Default is dry-run (no writes). When applying, *dest_root* or plan dest must
    exist (or be creatable).
    """
    root = Path(repo_root) if repo_root else ROOT
    p = plan or build_windows_mirror_plan(
        monopin=monopin, repo_root=root, dest_root=dest_root
    )
    dest = windows_drive_root(dest_root if dest_root is not None else p.get("dest_root"))
    if dest is None or str(dest) in ("{RPT_WINDOWS_DRIVE}",):
        return {
            "ok": False,
            "dry_run": dry_run,
            "error": "dest not configured — set RPT_WINDOWS_DRIVE or pass --dest",
            "copied": [],
            "skipped": [],
        }

    actions: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    repo_dest = dest / monorepo_dest_name()

    def _copy_file(src: Path, dst: Path) -> None:
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not dry_run:
            shutil.copy2(src, dst)

    # Monorepo top-level
    for name in MONOREPO_TOP_LEVEL:
        src = root / name
        if not src.exists():
            skipped.append({"kind": "monorepo_missing", "path": str(src)})
            continue
        dst = repo_dest / name
        if src.is_file():
            actions.append({"kind": "file", "src": str(src), "dest": str(dst)})
            if not dry_run:
                _copy_file(src, dst)
        elif src.is_dir():
            actions.append({"kind": "dir", "src": str(src), "dest": str(dst)})
            if not dry_run:
                if dst.exists():
                    # Merge copy: walk and copy files, skip noise
                    for dirpath, dirnames, filenames in os.walk(src):
                        dirnames[:] = [d for d in dirnames if d not in SKIP_DIR_NAMES]
                        rel = Path(dirpath).relative_to(src)
                        target_dir = dst / rel
                        target_dir.mkdir(parents=True, exist_ok=True)
                        for fn in filenames:
                            if fn in SKIP_DIR_NAMES:
                                continue
                            s = Path(dirpath) / fn
                            d = target_dir / fn
                            try:
                                shutil.copy2(s, d)
                            except OSError:
                                pass
                else:
                    def _ignore(directory: str, names: list[str]) -> set[str]:
                        return {n for n in names if n in SKIP_DIR_NAMES}

                    shutil.copytree(src, dst, ignore=_ignore, dirs_exist_ok=True)

    # Brand packages that are present on source
    for row in p.get("brand_packages") or []:
        if not row.get("source_present"):
            skipped.append(
                {
                    "kind": "brand_source_missing",
                    "filename": row.get("filename"),
                }
            )
            continue
        src = Path(str(row.get("source_path") or ""))
        # Always place under mirrored monorepo releases/
        rel = str(row.get("relative_path") or "")
        dst = repo_dest / "releases" / rel
        if not src.is_file():
            skipped.append({"kind": "brand_source_gone", "filename": row.get("filename")})
            continue
        actions.append(
            {
                "kind": "brand_package",
                "src": str(src),
                "dest": str(dst),
                "filename": row.get("filename"),
            }
        )
        if not dry_run:
            _copy_file(src, dst)

    # Re-evaluate presence on dest after apply
    post = build_windows_mirror_plan(monopin=p.get("monopin"), repo_root=root, dest_root=dest)
    return {
        "ok": True,
        "dry_run": dry_run,
        "dest_root": str(dest),
        "repo_dest": str(repo_dest),
        "copied_count": len(actions),
        "skipped_count": len(skipped),
        "copied": actions,
        "skipped": skipped,
        "post_plan": {
            "brand_slot_count": post.get("brand_slot_count"),
            "duplicated_on_dest": post.get("duplicated_on_dest"),
            "present_source_count": post.get("present_source_count"),
            "dest_reachable": post.get("dest_reachable"),
        },
    }


def write_releases_breadcrumbs(
    *,
    monopin: str | None = None,
    repo_root: Path | None = None,
) -> Path:
    """Write releases/{monopin}/WINDOWS_BREADCRUMBS.md with brand-wide checklist."""
    root = Path(repo_root) if repo_root else ROOT
    pin = (monopin or current_monopin()).strip()
    plan = build_windows_mirror_plan(monopin=pin, repo_root=root)
    text = render_windows_brand_checklist(plan)
    out = root / "releases" / pin / "WINDOWS_BREADCRUMBS.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Windows large-drive brand mirror (all brand assets + monorepo)"
    )
    ap.add_argument(
        "command",
        choices=("plan", "apply", "checklist", "manifest", "write-releases"),
        help="plan=JSON plan; apply=copy; checklist=md; manifest=JSON; write-releases=WINDOWS_BREADCRUMBS.md",
    )
    ap.add_argument(
        "--dest",
        default="",
        help="Windows large-drive root (else RPT_WINDOWS_DRIVE)",
    )
    ap.add_argument("--version", default="", help="Monopin (default: live catalog)")
    ap.add_argument(
        "--execute",
        action="store_true",
        help="With apply: actually copy (default is dry-run)",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="With apply: force dry-run (default without --execute)",
    )
    args = ap.parse_args(argv)
    ver = (args.version or "").strip() or None
    dest = (args.dest or "").strip() or None

    if args.command == "plan":
        plan = build_windows_mirror_plan(monopin=ver, dest_root=dest)
        print(json.dumps(plan, indent=2))
        return 0
    if args.command == "manifest":
        plan = build_windows_mirror_plan(monopin=ver, dest_root=dest)
        print(json.dumps(plan, indent=2))
        return 0
    if args.command == "checklist":
        print(render_windows_brand_checklist(monopin=ver, dest_root=dest))
        return 0
    if args.command == "write-releases":
        path = write_releases_breadcrumbs(monopin=ver)
        print(f"wrote {path}")
        return 0
    if args.command == "apply":
        dry = True
        if args.execute and not args.dry_run:
            dry = False
        result = apply_mirror_plan(dest_root=dest, monopin=ver, dry_run=dry)
        print(json.dumps({k: v for k, v in result.items() if k != "copied"}, indent=2))
        if result.get("copied") and dry:
            print(f"dry_run_actions={len(result['copied'])}", file=sys.stderr)
        if not result.get("ok"):
            return 1
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
