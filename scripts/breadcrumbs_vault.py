#!/usr/bin/env python3
"""Helsinki breadcrumbs vault — Apple + Windows brand-mirror task source of truth.

Replaces the **GitHub handoff pull** as the MacBook's primary “what needs
updating?” queue. Source code may still live in the private repo; **task
breadcrumbs** (monopin, honesty flags, checklist, APPLE_HANDOFF + Windows
brand-wide large-drive mirror) live on the Helsinki store host.

Layout on Helsinki::

  /opt/restore-privacy/breadcrumbs/
    current/                 # always the live monopin snapshot
      manifest.json
      honesty.json
      checklist.md
      APPLE_HANDOFF.md
      WINDOWS_HANDOFF.md
      WINDOWS_BRAND_CHECKLIST.md
      windows_brand_mirror.json
    {VERSION}/               # pinned copy of the same snapshot

Fetch (token-gated, same secret class as paid-assets)::

  curl -fsS -H "X-RPT-Asset-Token: $RPT_ASSET_FETCH_TOKEN" \\
    "https://135.181.152.10.sslip.io/breadcrumbs/current/manifest.json"

Usage::

  # Build vault under dist/breadcrumbs/{VERSION}/
  python scripts/breadcrumbs_vault.py stage

  # Stage + SSH publish to Helsinki
  export RPT_SSH_HOST=135.181.152.10 RPT_SSH_USER=root
  export RPT_SSH_KEY=~/.ssh/id_ed25519_20260725
  python scripts/breadcrumbs_vault.py publish

  # MacBook check (local stage or live fetch)
  python scripts/breadcrumbs_vault.py check
  python scripts/breadcrumbs_vault.py check --fetch

Environment:
  RPT_BREADCRUMBS_BASE   default https://135.181.152.10.sslip.io/breadcrumbs
  RPT_ASSET_FETCH_TOKEN  same token as paid-assets (or RPT_BREADCRUMB_TOKEN)
  RPT_SSH_*              for publish (Helsinki store host)
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
STATUS = ROOT / "status_page"
sys.path.insert(0, str(STATUS))
sys.path.insert(0, str(ROOT / "scripts"))

DEFAULT_BREADCRUMBS_REMOTE_ROOT = "/opt/restore-privacy/breadcrumbs"
DEFAULT_BREADCRUMBS_BASE = "https://135.181.152.10.sslip.io/breadcrumbs"
DEFAULT_SSH_HOST = "135.181.152.10"
HTTP_PREFIX = "/breadcrumbs"


def current_monopin() -> str:
    """Live catalog monopin from downloads.RELEASE_VERSION / client/VERSION."""
    try:
        from downloads import current_catalog_version

        return current_catalog_version()
    except Exception:
        pin = (ROOT / "client" / "VERSION").read_text(encoding="utf-8").strip()
        return pin or "0.0.0"


def _find_apple_zip(platform: str, monopin: str) -> Path | None:
    """Locate staged/catalog zip for macos or ios if present."""
    fname = f"restore-privacy-client-{monopin}-{platform}.zip"
    if platform == "macos":
        fname = f"restore-privacy-client-{monopin}-macos.zip"
    elif platform == "ios":
        fname = f"restore-privacy-client-{monopin}-ios.zip"
    cands = [
        STATUS / "assets" / monopin / fname,
        ROOT / "releases" / monopin / fname,
    ]
    for p in cands:
        if p.is_file() and p.stat().st_size > 1000:
            return p
    return None


def inspect_platform_honesty(platform: str, monopin: str) -> dict[str, Any]:
    """Build honesty record for macOS or iOS from zip audit when available."""
    plat = platform.strip().lower()
    out: dict[str, Any] = {
        "platform": plat,
        "monopin": monopin,
        "package_present": False,
        "bundle_version": None,
        "status": "unknown",
        "needs_work": True,
        "notes": "",
    }
    path = _find_apple_zip(plat, monopin)
    if path is None:
        out["status"] = "missing_package"
        out["needs_work"] = True
        out["notes"] = (
            f"No local {plat} catalog zip for monopin {monopin}; "
            "Mac rebuild/sign required before publish."
        )
        return out

    out["package_present"] = True
    out["path"] = str(path)
    out["size"] = path.stat().st_size
    try:
        from apple_package_audit import inspect_apple_zip

        audit = inspect_apple_zip(path, platform=plat)
        ver = audit.get("primary_version")
        out["bundle_version"] = ver
        out["plist_paths"] = audit.get("plist_paths") or []
        if ver == monopin:
            out["status"] = "native_monopin"
            out["needs_work"] = False
            out["notes"] = (
                f"CFBundle/marketing version {ver} matches monopin {monopin}."
            )
        elif ver:
            out["status"] = "carry_forward_or_lag"
            out["needs_work"] = True
            out["notes"] = (
                f"Internal version {ver!r} != monopin {monopin!r} — "
                f"native rebuild/seal needed for honest {plat}."
            )
        else:
            out["status"] = "unreadable_plist"
            out["needs_work"] = True
            out["notes"] = "Could not read CFBundle from zip; treat as needs work."
    except Exception as exc:  # noqa: BLE001
        out["status"] = "audit_error"
        out["needs_work"] = True
        out["notes"] = f"audit failed: {exc}"[:200]
    return out


def _windows_brand_mirror_snapshot(*, monopin: str) -> dict[str, Any]:
    """Brand-wide Windows large-drive mirror fields for the vault manifest."""
    try:
        from windows_brand_mirror import build_windows_mirror_plan

        plan = build_windows_mirror_plan(monopin=monopin)
        return {
            "schema": plan.get("schema"),
            "brand_slot_count": plan.get("brand_slot_count"),
            "brand_kinds": plan.get("brand_kinds"),
            "present_source_count": plan.get("present_source_count"),
            "missing_source_count": plan.get("missing_source_count"),
            "dest_root": plan.get("dest_root"),
            "dest_configured": plan.get("dest_configured"),
            "repo_dest": plan.get("repo_dest"),
            "native_pe_build": plan.get("native_pe_build"),
            "brand_filenames": [
                str(r.get("filename") or "")
                for r in (plan.get("brand_packages") or [])
                if r.get("filename")
            ],
            "operator_cli": (
                "python scripts/windows_brand_mirror.py plan|apply "
                "--dest $RPT_WINDOWS_DRIVE"
            ),
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "schema": "rpt.windows_brand_mirror.v1",
            "error": str(exc)[:200],
            "brand_slot_count": 0,
            "brand_filenames": [],
        }


def build_vault_manifest(*, monopin: str | None = None) -> dict[str, Any]:
    """Assemble the live breadcrumbs vault snapshot (pure-ish JSON)."""
    pin = (monopin or current_monopin()).strip()
    macos = inspect_platform_honesty("macos", pin)
    ios = inspect_platform_honesty("ios", pin)
    actions: list[str] = []
    if macos.get("needs_work"):
        actions.append("rebuild_macos_native_seal")
    if ios.get("needs_work"):
        actions.append("rebuild_ios_team_sign")
    if not actions:
        actions.append("none_apple_up_to_date")

    handoff_rel = f"client_app/APPLE_HANDOFF_{pin}.md"
    handoff_path = ROOT / handoff_rel
    windows_mirror = _windows_brand_mirror_snapshot(monopin=pin)
    win_actions: list[str] = [
        "mirror_monorepo_and_brand_assets_to_large_drive",
        "rebuild_windows_native_pe_seal",
        f"upload_paid_assets_{pin}",
        # Architecture observe (VPN-only product truth) — see WINDOWS_HANDOFF
        "observe_first_run_licence_keygen_or_trial_before_vpn",
        "observe_72h_keygen_free_trial_then_pay",
        "observe_vpn_only_shell_no_evolve_wallet_rpai_chrome",
        "observe_quit_lower_left_disconnect_then_exit",
        "observe_tray_text_privacy_comma_restored",
        # Parity with macOS 1.1.9 dual device-key bug (host HELLO vs tunnel identity)
        "observe_single_device_ed25519_across_home_and_localappdata_secrets",
        "observe_full_tunnel_not_host_only_hello_after_node_ip_assigned",
        "report_dual_identity_hashes_if_connect_fails_with_node_ip",
    ]

    return {
        "schema": "rpt.breadcrumbs.v1",
        "monopin": pin,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_of_truth": "helsinki_breadcrumbs_vault",
        "github_breadcrumb_flow": "deprecated",
        "github_note": (
            "Do not use private GitHub APPLE_HANDOFF pull as the primary "
            "Mac task queue. Fetch this vault instead. Source code may still "
            "live in the private repo."
        ),
        "helsinki_host": DEFAULT_SSH_HOST,
        "breadcrumbs_base": os.environ.get(
            "RPT_BREADCRUMBS_BASE", DEFAULT_BREADCRUMBS_BASE
        ).strip()
        or DEFAULT_BREADCRUMBS_BASE,
        "platforms": {"macos": macos, "ios": ios},
        "macbook_actions": actions,
        "windows_actions": win_actions,
        "windows_brand_mirror": windows_mirror,
        "needs_any_apple_work": bool(macos.get("needs_work") or ios.get("needs_work")),
        "handoff_file": handoff_rel if handoff_path.is_file() else None,
        "checklist": [
            f"BUILT (this build monopin {pin}): Windows setup.exe, Linux tar.gz, "
            f"Android APK as restore-privacy-client-{pin}-* (this host). "
            f"Apple packages not sealed here — Mac rebuild/sign required.",
            f"UPDATE THESE DOCS to monopin {pin}: client_app/APPLE_HANDOFF_{pin}.md, "
            f"scripts/RELEASE_NOTES_{pin}.md, PRIVACY_POLICY.md, AUDIT.md, "
            f"status_page/settings_explainer.py (Settings guide), "
            f"status_page/downloads.py RELEASE_VERSION, client/VERSION.",
            f"PUBLISH ALL to the version number of this build ({pin}): stage/upload "
            f"every platform package under paid_assets/{pin}/ and status_page/assets/{pin}/ "
            f"(Windows + Linux + Android already built; macOS + iOS after native seal). "
            f"No separate commit/version guess — use monopin {pin} everywhere.",
            "1. Fetch vault: breadcrumbs_vault.py check --fetch",
            "2. If macos needs_work: flutter build macos + notarize per APPLE_HANDOFF",
            "3. If ios needs_work: flutter build ios + Team-sign per APPLE_HANDOFF",
            f"4. Stage/upload paid assets for {pin} (Helsinki), then re-publish breadcrumbs",
            "5. Re-run check until needs_any_apple_work is false",
            "6. Windows machine: set RPT_WINDOWS_DRIVE to the large drive; "
            "python scripts/windows_brand_mirror.py apply — monorepo + all brand "
            f"installer slots ({windows_mirror.get('brand_slot_count') or 'N'} packages); "
            "then native PE seal + upload",
            f"7. Windows machine: open client/windows/WINDOWS_HANDOFF_{pin}.md — "
            "full product map: first-run licence (scroll-to-bottom) → KEYGEN or "
            "continue 72h trial (no username/password/seed); residual VPN-only "
            "shell (no Evolve/%/rpAI/Backup chrome); Quit lower-left disconnect-"
            "then-exit; tray text exactly Privacy, Restored; residual IS+DE; "
            "manual free-DL updates only (no UPDATE_PUSH); then native PE seal + "
            f"upload paid_assets/{pin}/",
            "8. Windows machine OBSERVE (macOS 1.1.9 dual-identity parity): after "
            "KEYGEN/trial Connect, hash client_ed25519.priv under "
            "%USERPROFILE%\\.restore-privacy\\secrets and "
            "%LOCALAPPDATA%\\Programs\\RestorePrivacy\\secrets — they must match. "
            "If Connect log shows node assigned 10.88.x but residual/Wintun not "
            "active, report both hash prefixes + log excerpt (not trial-expired "
            "when node IP was assigned). See WINDOWS_HANDOFF section 0b.",
        ],
        "windows_observe_residual_identity": {
            "schema": "rpt.windows_residual_identity_observe.v1",
            "monopin": pin,
            "reason": (
                "macOS 1.1.9 Connect failed when host HELLO used one "
                "client_ed25519.priv (often ~/.restore-privacy, KEYGEN-bound) "
                "while Packet Tunnel used a different App Group key — node IP "
                "assigned but full tunnel stayed disconnected. Windows may have "
                "the same multi-directory secrets search (secrets_loader)."
            ),
            "symptom_not_trial_expired": (
                "Node assigned 10.88.0.x proves residual HELLO admission; "
                "do not treat as trial-expired / buy KEYGEN as primary."
            ),
            "paths_to_hash": [
                r"%USERPROFILE%\.restore-privacy\secrets\client_ed25519.priv",
                r"%LOCALAPPDATA%\Programs\RestorePrivacy\secrets\client_ed25519.priv",
            ],
            "pass_criteria": (
                "At most one active 32-byte device priv; all trusted stores match; "
                "product Connected only with residual capture / Wintun active."
            ),
            "fail_report": [
                "sha256_prefix_home",
                "sha256_prefix_localappdata",
                "node_ip_if_any",
                "connection_log_excerpt",
                "client_version",
            ],
            "handoff": f"client/windows/WINDOWS_HANDOFF_{pin}.md section 0b",
        },
    }


def render_checklist_md(manifest: dict[str, Any]) -> str:
    """Human-readable checklist for the MacBook."""
    pin = manifest.get("monopin")
    lines = [
        f"# Apple breadcrumbs checklist — monopin {pin}",
        "",
        f"Generated: {manifest.get('generated_at')}",
        f"Source of truth: **{manifest.get('source_of_truth')}** "
        f"(GitHub breadcrumb pull: **{manifest.get('github_breadcrumb_flow')}**)",
        "",
        f"## Operator mandate (monopin {pin})",
        "",
        f"- **Built this:** Windows / Linux / Android packages for **{pin}** "
        f"(restore-privacy-client-{pin}-windows-x64-setup.exe, "
        f"…-linux-x64.tar.gz, …-android.apk).",
        f"- **Update these docs:** APPLE_HANDOFF_{pin}.md, RELEASE_NOTES_{pin}.md, "
        f"PRIVACY_POLICY, AUDIT, settings explainer, downloads monopin — all to **{pin}**.",
        f"- **Publish all to the version number of this build ({pin}):** every platform "
        f"installer under paid_assets/{pin}/ and status assets — macOS + iOS after Mac seal. "
        f"Do not invent a different version or wait for a separate commit command.",
        "",
        "## Actions",
    ]
    for a in manifest.get("macbook_actions") or []:
        lines.append(f"- `{a}`")
    lines.append("")
    lines.append("## Platform honesty")
    for plat, rec in (manifest.get("platforms") or {}).items():
        lines.append(
            f"- **{plat}**: status=`{rec.get('status')}` "
            f"needs_work=`{rec.get('needs_work')}` "
            f"bundle=`{rec.get('bundle_version')}` — {rec.get('notes')}"
        )
    lines.append("")
    lines.append("## Steps")
    for step in manifest.get("checklist") or []:
        lines.append(f"- {step}")
    lines.append("")
    lines.append(
        "Fetch: `python3 scripts/breadcrumbs_vault.py check --fetch` "
        "with `RPT_ASSET_FETCH_TOKEN` set."
    )
    lines.append("")
    return "\n".join(lines)


def stage_vault(*, monopin: str | None = None, out_root: Path | None = None) -> Path:
    """Write vault files under dist/breadcrumbs/{monopin}/ and .../current/."""
    pin = (monopin or current_monopin()).strip()
    base = out_root or (ROOT / "dist" / "breadcrumbs")
    ver_dir = base / pin
    cur_dir = base / "current"
    ver_dir.mkdir(parents=True, exist_ok=True)
    cur_dir.mkdir(parents=True, exist_ok=True)

    manifest = build_vault_manifest(monopin=pin)
    honesty = {
        "monopin": pin,
        "platforms": manifest["platforms"],
        "needs_any_apple_work": manifest["needs_any_apple_work"],
        "macbook_actions": manifest["macbook_actions"],
    }
    checklist = render_checklist_md(manifest)

    handoff_src = ROOT / f"client_app/APPLE_HANDOFF_{pin}.md"
    handoff_text = (
        handoff_src.read_text(encoding="utf-8")
        if handoff_src.is_file()
        else (
            f"# APPLE_HANDOFF_{pin}.md missing in monorepo\n\n"
            f"Monopin {pin}. Create handoff then re-publish breadcrumbs.\n"
        )
    )
    # Banner: vault is primary, GH deprecated for task flow
    banner = (
        f"\n\n---\n\n> **Breadcrumbs vault (Helsinki)** is the source of truth "
        f"for “what to update” on this monopin. Do **not** treat a private "
        f"GitHub pull of this file as the primary task queue.\n"
        f"> Fetch: `{DEFAULT_BREADCRUMBS_BASE}/current/manifest.json` "
        f"with `X-RPT-Asset-Token`.\n"
    )
    if "Breadcrumbs vault (Helsinki)" not in handoff_text:
        handoff_text = handoff_text.rstrip() + banner

    # Windows PE follow-up for split-ship (read on Windows machine from Helsinki)
    win_src = ROOT / f"client/windows/WINDOWS_HANDOFF_{pin}.md"
    if not win_src.is_file():
        win_src = ROOT / "client" / "windows" / "WINDOWS_HANDOFF.md"
    win_text = (
        win_src.read_text(encoding="utf-8")
        if win_src.is_file()
        else (
            f"# WINDOWS_HANDOFF_{pin}.md missing\n\n"
            f"Monopin {pin}: build native PE on Windows and upload to "
            f"paid_assets/{pin}/.\n"
        )
    )
    if "Breadcrumbs vault (Helsinki)" not in win_text:
        win_text = win_text.rstrip() + banner

    # Brand-wide large-drive mirror plan + checklist (all installer slots)
    try:
        from windows_brand_mirror import (
            build_windows_mirror_plan,
            render_windows_brand_checklist,
            render_windows_handoff_brand_section,
            write_releases_breadcrumbs,
        )

        win_plan = build_windows_mirror_plan(monopin=pin)
        win_brand_checklist = render_windows_brand_checklist(win_plan)
        brand_section = render_windows_handoff_brand_section(win_plan)
        if "Brand-wide large-drive mirror" not in win_text:
            win_text = win_text.rstrip() + brand_section
        try:
            write_releases_breadcrumbs(monopin=pin)
        except OSError:
            pass
    except Exception as exc:  # noqa: BLE001
        win_plan = {
            "schema": "rpt.windows_brand_mirror.v1",
            "monopin": pin,
            "error": str(exc)[:200],
            "brand_packages": [],
        }
        win_brand_checklist = (
            f"# Windows brand checklist — monopin {pin}\n\n"
            f"Error building brand mirror plan: {exc}\n"
        )

    for dest in (ver_dir, cur_dir):
        (dest / "manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )
        (dest / "honesty.json").write_text(
            json.dumps(honesty, indent=2) + "\n", encoding="utf-8"
        )
        (dest / "checklist.md").write_text(checklist, encoding="utf-8")
        (dest / "APPLE_HANDOFF.md").write_text(handoff_text, encoding="utf-8")
        (dest / "WINDOWS_HANDOFF.md").write_text(win_text, encoding="utf-8")
        (dest / "WINDOWS_BRAND_CHECKLIST.md").write_text(
            win_brand_checklist, encoding="utf-8"
        )
        (dest / "windows_brand_mirror.json").write_text(
            json.dumps(win_plan, indent=2) + "\n", encoding="utf-8"
        )
        observe = manifest.get("windows_observe_residual_identity") or {}
        (dest / "windows_residual_identity_observe.json").write_text(
            json.dumps(observe, indent=2) + "\n", encoding="utf-8"
        )

    # Tidy: remove other monopin dirs under dist/breadcrumbs except current
    for child in list(base.iterdir()):
        if child.is_dir() and child.name not in (pin, "current"):
            shutil.rmtree(child, ignore_errors=True)

    print(f"staged_vault monopin={pin} dir={ver_dir}")
    print(f"needs_any_apple_work={manifest['needs_any_apple_work']}")
    print(f"actions={manifest['macbook_actions']}")
    return ver_dir


def evaluate_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    """Pure Mac-check outcome from a vault manifest dict."""
    plats = manifest.get("platforms") or {}
    macos = plats.get("macos") or {}
    ios = plats.get("ios") or {}
    return {
        "monopin": manifest.get("monopin"),
        "macos_needs_work": bool(macos.get("needs_work")),
        "ios_needs_work": bool(ios.get("needs_work")),
        "needs_any_apple_work": bool(manifest.get("needs_any_apple_work")),
        "macbook_actions": list(manifest.get("macbook_actions") or []),
        "up_to_date": not bool(manifest.get("needs_any_apple_work")),
        "source_of_truth": manifest.get("source_of_truth"),
        "github_breadcrumb_flow": manifest.get("github_breadcrumb_flow"),
    }


def check_local_stage(*, monopin: str | None = None) -> dict[str, Any]:
    """Run check against freshly built vault (or existing dist/breadcrumbs/current)."""
    pin = (monopin or current_monopin()).strip()
    cur = ROOT / "dist" / "breadcrumbs" / "current" / "manifest.json"
    if not cur.is_file():
        stage_vault(monopin=pin)
    data = json.loads(cur.read_text(encoding="utf-8"))
    # Prefer rebuild if monopin drifted
    if str(data.get("monopin") or "") != pin:
        stage_vault(monopin=pin)
        data = json.loads(cur.read_text(encoding="utf-8"))
    return evaluate_manifest(data)


def breadcrumbs_base_url() -> str:
    raw = os.environ.get("RPT_BREADCRUMBS_BASE", DEFAULT_BREADCRUMBS_BASE).strip()
    return (raw or DEFAULT_BREADCRUMBS_BASE).rstrip("/")


def breadcrumbs_fetch_token() -> str:
    for key in (
        "RPT_BREADCRUMB_TOKEN",
        "RPT_ASSET_FETCH_TOKEN",
        "RPT_VPS_ASSET_TOKEN",
    ):
        val = os.environ.get(key, "").strip()
        if val:
            return val
    return ""


def fetch_remote_manifest(*, path: str = "current/manifest.json") -> dict[str, Any]:
    """GET vault manifest from Helsinki (token required)."""
    import urllib.error
    import urllib.request

    token = breadcrumbs_fetch_token()
    if not token:
        raise RuntimeError(
            "Set RPT_ASSET_FETCH_TOKEN (or RPT_BREADCRUMB_TOKEN) to fetch vault"
        )
    url = f"{breadcrumbs_base_url()}/{path.lstrip('/')}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "rpt-breadcrumbs-vault-check",
            "X-RPT-Asset-Token": token,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"vault fetch HTTP {e.code} for {url}") from e
    return json.loads(raw)


def check_remote() -> dict[str, Any]:
    """MacBook entry: fetch live vault and evaluate."""
    return evaluate_manifest(fetch_remote_manifest())


def publish_vault(*, monopin: str | None = None, dry_run: bool = False) -> int:
    """Stage vault and rsync/scp to Helsinki breadcrumbs root."""
    pin = (monopin or current_monopin()).strip()
    local = stage_vault(monopin=pin)
    base = ROOT / "dist" / "breadcrumbs"
    remote_root = os.environ.get(
        "RPT_BREADCRUMBS_REMOTE_ROOT", DEFAULT_BREADCRUMBS_REMOTE_ROOT
    ).strip() or DEFAULT_BREADCRUMBS_REMOTE_ROOT

    print(f"publish plan: {base}/{{current,{pin}}} -> {remote_root}/")
    if dry_run:
        print("dry-run: no SSH")
        return 0

    # Reuse host_paid_assets SSH helpers
    from host_paid_assets_vps import (  # type: ignore
        _openssh_available,
        _scp_put_file,
        _ssh_run_openssh,
        _ssh_target,
    )

    # Prefer Helsinki defaults when env not set
    if not os.environ.get("RPT_SSH_HOST", "").strip():
        os.environ["RPT_SSH_HOST"] = DEFAULT_SSH_HOST
    if not os.environ.get("RPT_SSH_USER", "").strip():
        os.environ["RPT_SSH_USER"] = "root"

    host, user, password, key_path = _ssh_target()
    if password is not None or key_path is None or not _openssh_available():
        print("publish requires OpenSSH key auth to Helsinki", file=sys.stderr)
        return 1

    remote_ver = f"{remote_root.rstrip('/')}/{pin}"
    remote_cur = f"{remote_root.rstrip('/')}/current"
    code, _ = _ssh_run_openssh(
        f"mkdir -p {remote_ver} {remote_cur}",
        host=host,
        user=user,
        key_path=key_path,
        sudo=True,
    )
    if code != 0:
        print("ERROR: could not create remote breadcrumbs dirs", file=sys.stderr)
        return 1

    home = "/root" if user == "root" else f"/home/{user}"
    for name in (
        "manifest.json",
        "honesty.json",
        "checklist.md",
        "APPLE_HANDOFF.md",
        "WINDOWS_HANDOFF.md",
        "WINDOWS_BRAND_CHECKLIST.md",
        "windows_brand_mirror.json",
        "windows_residual_identity_observe.json",
    ):
        local_f = local / name
        if not local_f.is_file():
            continue
        tmp = f"{home}/bc_{name}"
        _scp_put_file(local_f, tmp, host=host, user=user, key_path=key_path)
        for dest in (f"{remote_ver}/{name}", f"{remote_cur}/{name}"):
            c, o = _ssh_run_openssh(
                f"cp -f {tmp} {dest} && chmod 644 {dest}",
                host=host,
                user=user,
                key_path=key_path,
                sudo=True,
            )
            if c != 0:
                print(f"ERROR install {dest}: {o}", file=sys.stderr)
                return 1

    # Tidy remote: only current monopin + current/
    tidy = (
        f"set -e; "
        f"for d in {remote_root}/*; do "
        f"[ -d \"$d\" ] || continue; "
        f"bn=$(basename \"$d\"); "
        f"[ \"$bn\" = '{pin}' ] && continue; "
        f"[ \"$bn\" = 'current' ] && continue; "
        f"rm -rf \"$d\"; echo tidy_removed=$bn; "
        f"done"
    )
    _c, tout = _ssh_run_openssh(
        tidy, host=host, user=user, key_path=key_path, sudo=True
    )
    if tout:
        print(tout)

    print(f"publish_ok host={host} monopin={pin} root={remote_root}")
    print(f"fetch: {breadcrumbs_base_url()}/current/manifest.json")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Helsinki breadcrumbs vault (Apple macOS/iOS task queue)"
    )
    ap.add_argument(
        "command",
        choices=("stage", "publish", "check", "show"),
        help="stage=local vault; publish=SSH to Helsinki; check=report needs work",
    )
    ap.add_argument("--version", default="", help="Monopin (default: live catalog)")
    ap.add_argument(
        "--fetch",
        action="store_true",
        help="With check: pull live vault from Helsinki (needs token)",
    )
    ap.add_argument("--dry-run", action="store_true", help="With publish: no SSH")
    args = ap.parse_args(argv)
    ver = (args.version or "").strip() or None

    if args.command == "stage":
        stage_vault(monopin=ver)
        return 0
    if args.command == "publish":
        return publish_vault(monopin=ver, dry_run=args.dry_run)
    if args.command == "show":
        m = build_vault_manifest(monopin=ver)
        print(json.dumps(m, indent=2))
        return 0
    if args.command == "check":
        if args.fetch:
            try:
                result = check_remote()
            except Exception as e:  # noqa: BLE001
                print(f"ERROR fetch: {e}", file=sys.stderr)
                return 1
        else:
            result = check_local_stage(monopin=ver)
        print(json.dumps(result, indent=2))
        if result.get("up_to_date"):
            print("STATUS: Apple packages up to date for monopin")
            return 0
        print("STATUS: Apple work needed — see macbook_actions", file=sys.stderr)
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
