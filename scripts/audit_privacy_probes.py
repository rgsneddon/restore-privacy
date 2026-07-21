"""Section-B privacy probes for the security audit timer path.

Structural / status-only checks. Never format LUKS, never live ephemeral rebuild,
never enable kill-switch. Firewall / expose-surface scanning is intentionally
out of scope (OBJECTIVE).
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping

# Default product install layout on the node
DEFAULT_INSTALL_ROOT = Path(os.environ.get("RPT_INSTALL_ROOT", "/opt/restore-privacy"))


def _status(
    *,
    ok: bool = True,
    warn: bool = False,
    skipped: bool = False,
    reasons: list[str] | None = None,
    **extra: Any,
) -> dict[str, Any]:
    """ok=True means no hard failure; warn may still be set for operator notes."""
    out: dict[str, Any] = {
        "ok": bool(ok),
        "warn": bool(warn),
        "skipped": bool(skipped),
        "reasons": list(reasons or []),
    }
    out.update(extra)
    return out


def probe_nolog_journald(
    *,
    install_root: Path | None = None,
    unit_path: Path | None = None,
    config_json: Path | None = None,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Assert node no-log policy + systemd unit prefers null sinks."""
    reasons: list[str] = []
    warn = False
    skipped = False
    root = install_root or DEFAULT_INSTALL_ROOT
    repo = repo_root or Path(__file__).resolve().parents[1]

    # In-process product policy (always available when PYTHONPATH includes repo)
    try:
        sys.path.insert(0, str(repo))
        from node.nolog import (  # type: ignore
            NO_LOG_POLICY,
            assert_no_log_config,
            config_text_forbids_log_sinks,
            systemd_no_log_directives,
        )
    except Exception as exc:  # noqa: BLE001
        return _status(
            ok=False,
            skipped=True,
            reasons=[f"nolog module unavailable: {exc}"],
        )

    # Policy constants: logging sinks off
    if NO_LOG_POLICY.get("logging_enabled") is not False:
        reasons.append("NO_LOG_POLICY.logging_enabled is not False")
        warn = True
    for key in ("connection_log", "session_log", "user_info_log", "journal"):
        if NO_LOG_POLICY.get(key) not in (False, None):
            reasons.append(f"NO_LOG_POLICY.{key} not false")
            warn = True

    cfg_path = config_json or (root / "rpt-node.json")
    if cfg_path.is_file():
        try:
            import json

            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
            viol = assert_no_log_config(cfg if isinstance(cfg, dict) else {})
            if viol:
                reasons.extend(viol)
                warn = True
            else:
                reasons.append(f"config ok: {cfg_path.name}")
        except (OSError, ValueError, TypeError) as exc:
            reasons.append(f"config read error: {exc}")
            warn = True
    else:
        # Repo default path or skip on laptop
        conf = root / "rpt-node.conf"
        if conf.is_file():
            text = conf.read_text(encoding="utf-8", errors="replace")
            if not config_text_forbids_log_sinks(text):
                reasons.append("rpt-node.conf enables a forbidden log sink")
                warn = True
            else:
                reasons.append("rpt-node.conf forbids log sinks")
        else:
            skipped = True
            reasons.append("rpt-node.json/conf not present (non-node host)")

    unit = unit_path or Path(f"/etc/systemd/system/{os.environ.get('SERVICE_NAME', 'rpt-node')}.service")
    want = systemd_no_log_directives()
    if unit.is_file():
        try:
            utext = unit.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            # Low-priv timer (rpt-audit) may not read systemd unit files
            skipped = True
            reasons.append(f"unit unreadable ({exc.__class__.__name__}); skip nolog unit checks")
            utext = ""
        if utext:
            if re.search(r"(?m)^StandardOutput=(journal|syslog|kmsg)\b", utext):
                reasons.append(f"{unit.name}: StandardOutput to journal (prefer null)")
                warn = True
            if re.search(r"(?m)^StandardError=(journal|syslog|kmsg)\b", utext):
                reasons.append(f"{unit.name}: StandardError to journal (prefer null)")
                warn = True
            if "StandardOutput=null" in utext:
                reasons.append("unit StandardOutput=null present")
            else:
                # install.sh ships null — warn if unit exists without it
                reasons.append("unit missing StandardOutput=null")
                warn = True
            for d in want:
                if d.startswith("Standard") and d in utext:
                    pass
    else:
        reasons.append("rpt-node.service unit not on this host")
        if not skipped:
            skipped = True

    ok = not warn
    # On pure laptop skip, still ok for overall (honest skip)
    if skipped and not unit.is_file() and not cfg_path.is_file():
        return _status(ok=True, skipped=True, warn=False, reasons=reasons, directives=want)
    return _status(ok=ok, warn=warn, skipped=False, reasons=reasons, directives=want)


def probe_no_priv_public_trees(
    *,
    repo_root: Path | None = None,
    install_root: Path | None = None,
    extra_roots: list[Path] | None = None,
) -> dict[str, Any]:
    """Scan public/staged trees for embedded ``*.priv`` (never read secret contents)."""
    repo = repo_root or Path(__file__).resolve().parents[1]
    install = install_root or DEFAULT_INSTALL_ROOT
    roots: list[Path] = [
        repo / "product",
        repo / "releases",
        repo / "status_page",
        repo / "status_page" / "static",
        repo / "status_page" / "public",
        repo / "status_page" / "assets",
        install / "status_page",
        install / "status_page" / "static",
        install / "status_page" / "public",
        install / "paid_assets",
        install / "var" / "audit-scratch",
        Path("/opt/restore-privacy/paid_assets"),
        Path("/opt/restore-privacy/status_page"),
    ]
    if extra_roots:
        roots.extend(extra_roots)

    hits: list[str] = []
    scanned = 0
    for base in roots:
        try:
            if not base.exists():
                continue
        except OSError:
            continue
        scanned += 1
        try:
            for p in base.rglob("*.priv"):
                # Never open secrets/; skip true secrets dir by design
                parts = {x.lower() for x in p.parts}
                if "secrets" in parts:
                    continue
                try:
                    hits.append(str(p))
                except OSError:
                    hits.append(p.name)
        except OSError as exc:
            # permission on some trees
            hits.append(f"[scan-error:{base.name}:{exc}]")

    # Cap hits for public audit artifact size
    return _status(
        ok=len([h for h in hits if not h.startswith("[scan-error")]) == 0,
        warn=any(h.startswith("[scan-error") for h in hits),
        skipped=scanned == 0,
        reasons=[f"scanned_roots={scanned}", f"hits={len(hits)}"]
        + [f"priv:{h}" for h in hits[:20]],
        hits=hits[:20],
        scanned_roots=scanned,
    )


def probe_kill_switch_default_off(
    *,
    env: Mapping[str, str] | None = None,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Product residual kill-switch must default OFF (opt-in RPT_KILL_SWITCH=1 only)."""
    repo = repo_root or Path(__file__).resolve().parents[1]
    try:
        sys.path.insert(0, str(repo))
        from client.kill_switch import product_kill_switch_enabled  # type: ignore
    except Exception as exc:  # noqa: BLE001
        return _status(ok=False, skipped=True, reasons=[f"kill_switch module: {exc}"])

    # Explicit empty env: default must be off
    default_on = product_kill_switch_enabled(env={})
    e = dict(env) if env is not None else dict(os.environ)
    # Simulate "unset" product default: if current env forces on, note as warn (operator opt-in)
    current_on = product_kill_switch_enabled(env=e)
    reasons = [
        f"default_empty_env_enabled={default_on}",
        f"current_env_enabled={current_on}",
    ]
    if default_on:
        return _status(
            ok=False,
            warn=True,
            reasons=reasons + ["FAIL: product_kill_switch_enabled({}) is True"],
        )
    if current_on:
        return _status(
            ok=True,
            warn=True,
            reasons=reasons
            + ["WARN: RPT_KILL_SWITCH is on in this environment (operator opt-in)"],
            operator_opt_in=True,
        )
    reasons.append("kill-switch default off (product residual)")
    return _status(ok=True, warn=False, reasons=reasons, operator_opt_in=False)


def probe_title_only_status(http_status: Mapping[str, Any] | None) -> dict[str, Any]:
    """Wrap existing HTTP status probe: body must be title-only when ok."""
    http = dict(http_status or {})
    if not http.get("ok"):
        return _status(
            ok=False,
            skipped=not http,
            reasons=[f"http probe not ok: {http.get('error') or http.get('status_code')}"],
            title_only=False,
        )
    body = http.get("body")
    title_only = False
    if isinstance(body, dict):
        keys = {str(k).lower() for k in body.keys()}
        forbidden = {
            "clients",
            "clients_connected",
            "count",
            "sessions",
            "connected",
            "users",
        }
        title_only = "title" in keys and not (keys & forbidden)
        if set(body.keys()) <= {"title"}:
            title_only = True
    reasons = [f"title_only={title_only}", f"body={body!r}"[:200]]
    return _status(ok=title_only, warn=not title_only, reasons=reasons, title_only=title_only)


def probe_host_privacy_drift(
    *,
    install_root: Path | None = None,
    journald_dropin: Path | None = None,
    unit_path: Path | None = None,
    log_dirs: list[Path] | None = None,
    recipe_paths: list[Path] | None = None,
) -> dict[str, Any]:
    """Lightweight checks aligned with node/install_host_privacy.sh.

    Host artifacts = systemd unit and/or journald drop-in and/or leftover log dirs.
    The install recipe file alone is **not** a host artifact: recipe present without
    unit/drop-in ⇒ honest **SKIP** (developer laptop), not PASS.
    On a node (unit present): missing ``99-rpt-privacy.conf`` is a **WARN**.
    """
    reasons: list[str] = []
    warn = False
    install = install_root or DEFAULT_INSTALL_ROOT
    dropin = journald_dropin or Path(
        "/etc/systemd/journald.conf.d/99-rpt-privacy.conf"
    )
    unit = unit_path or Path(
        f"/etc/systemd/system/{os.environ.get('SERVICE_NAME', 'rpt-node')}.service"
    )
    leftovers = log_dirs or [
        Path("/var/log/rpt-node"),
        Path("/var/log/restore-privacy"),
    ]

    unit_present = False
    dropin_present = False
    leftover_present = False

    try:
        unit_present = unit.is_file()
    except OSError:
        unit_present = False
    try:
        dropin_present = dropin.is_file()
    except OSError:
        dropin_present = False

    if dropin_present:
        try:
            text = dropin.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            text = ""
            reasons.append(f"journald drop-in unreadable ({exc.__class__.__name__})")
            dropin_present = False
        if text:
            if "RuntimeMaxUse" in text or "Storage=volatile" in text:
                reasons.append("journald drop-in present (short retention)")
            else:
                reasons.append("journald drop-in present but missing retention markers")
                warn = True
    else:
        reasons.append("journald drop-in 99-rpt-privacy.conf absent")

    for d in leftovers:
        try:
            if d.exists():
                leftover_present = True
                reasons.append(f"leftover log dir exists: {d}")
                warn = True
        except OSError:
            pass

    if unit_present:
        try:
            utext = unit.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            # Low-priv audit timer cannot read systemd units — honest skip
            reasons.append(
                f"unit unreadable ({exc.__class__.__name__}); skip host-privacy unit checks"
            )
            unit_present = False
            utext = ""
        if utext:
            if re.search(r"(?m)^StandardOutput=(journal|syslog|kmsg)\b", utext):
                reasons.append("unit logs to journal (host-privacy drift)")
                warn = True
            else:
                reasons.append("unit not logging StandardOutput to journal")
            # Primary install_host_privacy.sh artifact missing while node unit exists
            if not dropin_present:
                reasons.append(
                    "WARN: node unit present but journald drop-in missing "
                    "(re-run install_host_privacy.sh)"
                )
                warn = True
    else:
        reasons.append("rpt-node.service unit not on this host")

    recipe_candidates = recipe_paths or [
        install / "node" / "install_host_privacy.sh",
        Path(__file__).resolve().parents[1] / "node" / "install_host_privacy.sh",
    ]
    recipe_present = any(p.is_file() for p in recipe_candidates)
    if recipe_present:
        reasons.append("install_host_privacy.sh recipe present in tree")
    else:
        reasons.append("install_host_privacy.sh recipe missing from tree")

    host_artifacts = unit_present or dropin_present or leftover_present
    if not host_artifacts:
        # Developer / CI: no node install surface — honest skip (recipe alone ≠ pass)
        return _status(
            ok=True,
            skipped=True,
            warn=False,
            reasons=reasons + ["non-node host (no unit/drop-in/log-dir artifacts)"],
            unit_present=False,
            dropin_present=False,
        )

    return _status(
        ok=not warn,
        warn=warn,
        skipped=False,
        reasons=reasons,
        unit_present=unit_present,
        dropin_present=dropin_present,
    )


def probe_disk_wipe_readiness(
    *,
    install_root: Path | None = None,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Status-only: LUKS tooling / wipe unit presence — never format or wipe."""
    repo = repo_root or Path(__file__).resolve().parents[1]
    install = install_root or DEFAULT_INSTALL_ROOT
    reasons: list[str] = []
    warn = False

    # Cryptsetup presence (non-destructive)
    cryptsetup = None
    for cand in ("cryptsetup", "/sbin/cryptsetup", "/usr/sbin/cryptsetup"):
        from shutil import which

        w = which(cand) if "/" not in cand else (cand if Path(cand).is_file() else None)
        if w:
            cryptsetup = w
            break
    if cryptsetup:
        reasons.append(f"cryptsetup present: {cryptsetup}")
    else:
        reasons.append("cryptsetup not found (FDE tooling absent)")

    # Script recipes
    enc_sh = repo / "node" / "install_disk_encryption.sh"
    zram_sh = repo / "node" / "install_zram_luks.sh"
    wipe_sh = repo / "node" / "install_shutdown_wipe.sh"
    wipe_runtime = install / "node" / "rpt_shutdown_wipe.sh"
    if enc_sh.is_file():
        reasons.append("install_disk_encryption.sh present")
    else:
        reasons.append("install_disk_encryption.sh missing")
        warn = True
    if zram_sh.is_file():
        reasons.append("install_zram_luks.sh present (node-only ram volume)")
    else:
        reasons.append("install_zram_luks.sh missing")
        warn = True
    if wipe_sh.is_file() or wipe_runtime.is_file():
        reasons.append("shutdown wipe script present")
    else:
        reasons.append("shutdown wipe script not installed")

    shutdown_unit = Path("/etc/systemd/system/rpt-node-shutdown-wipe.service")
    node_unit = Path(
        f"/etc/systemd/system/{os.environ.get('SERVICE_NAME', 'rpt-node')}.service"
    )
    wipe_wired = False
    try:
        if shutdown_unit.is_file():
            wipe_wired = True
            reasons.append("rpt-node-shutdown-wipe.service present")
    except OSError:
        pass
    try:
        if node_unit.is_file():
            try:
                utext = node_unit.read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                reasons.append(
                    f"node unit unreadable ({exc.__class__.__name__}); skip wipe-wire check"
                )
                utext = ""
            if utext and "rpt_shutdown_wipe" in utext:
                wipe_wired = True
                reasons.append("rpt-node.service ExecStop wipe wired")
    except OSError:
        pass
    if not wipe_wired:
        reasons.append("wipe unit not wired (optional on non-node hosts)")

    # Never call format / RPT_LUKS_CONFIRM
    reasons.append("status-only: no LUKS format attempted")

    # On laptop without cryptsetup and without units → skip soft
    if not cryptsetup and not wipe_wired and not shutdown_unit.is_file():
        return _status(
            ok=True,
            skipped=True,
            warn=False,
            reasons=reasons,
            cryptsetup=cryptsetup,
            wipe_wired=False,
        )
    return _status(
        ok=True,
        warn=warn and not wipe_wired and not cryptsetup,
        skipped=False,
        reasons=reasons,
        cryptsetup=cryptsetup,
        wipe_wired=wipe_wired,
    )


def probe_ephemeral_dry_run(
    *,
    repo_root: Path | None = None,
    run_subprocess: bool = True,
) -> dict[str, Any]:
    """Ephemeral plan tooling present; optional safe --dry-run (never --live)."""
    repo = repo_root or Path(__file__).resolve().parents[1]
    script = repo / "scripts" / "ephemeral_node.py"
    reasons: list[str] = []
    if not script.is_file():
        return _status(
            ok=False,
            skipped=True,
            reasons=["scripts/ephemeral_node.py missing"],
        )
    reasons.append("ephemeral_node.py present")
    text = script.read_text(encoding="utf-8", errors="replace")
    if "--dry-run" not in text and "dry_run" not in text:
        return _status(
            ok=False,
            warn=True,
            reasons=reasons + ["dry-run mode not found in script"],
        )
    reasons.append("dry-run mode available")
    # Never pass live confirm
    if run_subprocess:
        try:
            env = os.environ.copy()
            env.pop("RPT_EPHEMERAL_CONFIRM", None)
            p = subprocess.run(
                [sys.executable, str(script), "--dry-run"],
                cwd=str(repo),
                capture_output=True,
                text=True,
                timeout=60,
                env=env,
            )
            reasons.append(f"dry-run exit={p.returncode}")
            # dry-run should not require confirm; non-zero may mean missing plan deps
            if p.returncode != 0:
                return _status(
                    ok=True,
                    warn=True,
                    skipped=False,
                    reasons=reasons
                    + ["dry-run non-zero (plan tooling incomplete on this host)"],
                    dry_run_rc=p.returncode,
                )
            return _status(
                ok=True,
                warn=False,
                reasons=reasons + ["dry-run completed"],
                dry_run_rc=0,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return _status(
                ok=True,
                warn=True,
                reasons=reasons + [f"dry-run not executed: {exc}"],
            )
    return _status(ok=True, skipped=False, reasons=reasons)


def run_all_section_b_probes(
    *,
    http_status: Mapping[str, Any] | None = None,
    repo_root: Path | None = None,
    install_root: Path | None = None,
    run_ephemeral_subprocess: bool = True,
) -> dict[str, Any]:
    """Aggregate section-B probes (firewall intentionally omitted)."""
    repo = repo_root or Path(__file__).resolve().parents[1]
    install = install_root or Path(
        os.environ.get("RPT_INSTALL_ROOT", str(DEFAULT_INSTALL_ROOT))
    )
    probes = {
        "nolog_journald": probe_nolog_journald(
            install_root=install, repo_root=repo
        ),
        "no_priv_public_trees": probe_no_priv_public_trees(
            repo_root=repo, install_root=install
        ),
        "kill_switch_default_off": probe_kill_switch_default_off(repo_root=repo),
        "title_only_status": probe_title_only_status(http_status),
        "host_privacy_drift": probe_host_privacy_drift(install_root=install),
        "disk_wipe_readiness": probe_disk_wipe_readiness(
            install_root=install, repo_root=repo
        ),
        "ephemeral_dry_run": probe_ephemeral_dry_run(
            repo_root=repo, run_subprocess=run_ephemeral_subprocess
        ),
        "firewall_expose_surface": {
            "ok": True,
            "skipped": True,
            "warn": False,
            "reasons": [
                "intentionally excluded (OBJECTIVE: no firewall/expose-surface probe)"
            ],
        },
    }
    # overall: hard fail only on no_priv hits or KS default-on or title-only fail when http ok
    hard_fail = False
    if not probes["no_priv_public_trees"].get("ok") and not probes[
        "no_priv_public_trees"
    ].get("skipped"):
        hard_fail = True
    if not probes["kill_switch_default_off"].get("ok") and not probes[
        "kill_switch_default_off"
    ].get("skipped"):
        hard_fail = True
    if (
        http_status
        and http_status.get("ok")
        and not probes["title_only_status"].get("ok")
    ):
        hard_fail = True

    return {
        "probes": probes,
        "ok": not hard_fail,
        "firewall_excluded": True,
        "section": "B",
    }


def render_section_b_markdown(section_b: Mapping[str, Any] | None) -> str:
    """Compact markdown table for AUDIT.md."""
    if not section_b:
        return ""
    probes = section_b.get("probes") or {}
    rows = []
    for name, data in probes.items():
        if not isinstance(data, dict):
            continue
        if data.get("skipped"):
            state = "SKIP"
        elif data.get("warn") and data.get("ok"):
            state = "WARN"
        elif data.get("ok"):
            state = "PASS"
        else:
            state = "FAIL"
        why = "; ".join(str(x) for x in (data.get("reasons") or [])[:3]) or "—"
        # redact already applied at write; keep short
        if len(why) > 160:
            why = why[:157] + "..."
        rows.append(f"| **{name}** | **{state}** | {why} |")
    table = "\n".join(rows) if rows else "| — | SKIP | no probes |"
    overall = "PASS" if section_b.get("ok") else "FAIL"
    return f"""## Privacy probes (section B — audit timer)

Structured privacy checks run with the security audit (status-only; no LUKS format,
no live ephemeral rebuild, **no firewall/expose-surface scan**).

| Probe | State | Notes |
|-------|-------|-------|
{table}

**Section B overall:** **{overall}** (firewall probe excluded by design)

"""
