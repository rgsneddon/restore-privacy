#!/usr/bin/env python3
"""Helsinki breadcrumbs vault: poll, hash/diff, optional act — GitHub is NOT the queue.

Source of truth: host 135.181.152.10
  /opt/restore-privacy/breadcrumbs/current/
Optional HTTP: https://135.181.152.10.sslip.io/breadcrumbs/current/
SSH: root + ~/.ssh/id_ed25519_restore_privacy_eu

Cadence (operator): first poll ≥4h after schedule install, then every 4h.
Durable last-seen state: ~/.restore-privacy/helsinki_breadcrumb_state.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

SCHEMA = "rpt.breadcrumbs.v1"
DEFAULT_HOST = "135.181.152.10"
DEFAULT_SSH_USER = "root"
DEFAULT_SSH_KEY = str(Path.home() / ".ssh" / "id_ed25519_restore_privacy_eu")
REMOTE_CURRENT = "/opt/restore-privacy/breadcrumbs/current"
STATE_PATH = Path.home() / ".restore-privacy" / "helsinki_breadcrumb_state.json"
VAULT_FILES = (
    "manifest.json",
    "checklist.md",
    "APPLE_HANDOFF.md",
    "honesty.json",
)


def vault_file_hashes(files: dict[str, str]) -> dict[str, str]:
    """SHA-256 hex of each file body (utf-8), sorted keys for stability."""
    out: dict[str, str] = {}
    for name in sorted(files.keys()):
        body = files[name] if files[name] is not None else ""
        if isinstance(body, bytes):
            raw = body
        else:
            raw = str(body).encode("utf-8")
        out[name] = hashlib.sha256(raw).hexdigest()
    return out


def vault_aggregate_hash(files: dict[str, str]) -> str:
    """Single hash over name=hex pairs (ordered). Pure change-detection key."""
    parts = [f"{k}={v}" for k, v in vault_file_hashes(files).items()]
    blob = "\n".join(parts).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def parse_manifest(text: str) -> dict[str, Any]:
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("manifest must be a JSON object")
    return data


def is_helsinki_sourced(manifest: dict[str, Any]) -> bool:
    """True when manifest declares Helsinki vault as source (not GitHub queue)."""
    sot = str(manifest.get("source_of_truth") or "").lower()
    host = str(manifest.get("helsinki_host") or "")
    gh = str(manifest.get("github_breadcrumb_flow") or "").lower()
    if "helsinki" in sot or host == DEFAULT_HOST:
        return True
    if gh in ("deprecated", "disabled", "off"):
        return host == DEFAULT_HOST or "helsinki" in sot
    return False


def needs_work(manifest: dict[str, Any]) -> bool:
    if manifest.get("needs_any_apple_work") is True:
        return True
    plats = manifest.get("platforms") or {}
    if isinstance(plats, dict):
        for meta in plats.values():
            if isinstance(meta, dict) and meta.get("needs_work") is True:
                return True
    return False


def compare_vault(
    previous_hash: str | None,
    current_files: dict[str, str],
    *,
    manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Pure diff: whether vault changed and whether open work is indicated.

    *previous_hash* None means first baseline (always 'changed' relative to empty).
    """
    cur_hash = vault_aggregate_hash(current_files)
    man = manifest
    if man is None and "manifest.json" in current_files:
        man = parse_manifest(current_files["manifest.json"])
    work = needs_work(man) if man else False
    if previous_hash is None:
        return {
            "status": "baseline",
            "changed": True,
            "previous_hash": None,
            "current_hash": cur_hash,
            "needs_work": work,
            "should_act": work,
        }
    changed = previous_hash != cur_hash
    return {
        "status": "changed" if changed else "unchanged",
        "changed": changed,
        "previous_hash": previous_hash,
        "current_hash": cur_hash,
        "needs_work": work,
        "should_act": bool(changed and work),
    }


def load_state(path: Path = STATE_PATH) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_state(state: dict[str, Any], path: Path = STATE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def fetch_vault_ssh(
    *,
    host: str = DEFAULT_HOST,
    user: str = DEFAULT_SSH_USER,
    key: str = DEFAULT_SSH_KEY,
    remote_dir: str = REMOTE_CURRENT,
) -> dict[str, str]:
    """Fetch vault files via SSH (primary for this laptop)."""
    key_path = Path(key).expanduser()
    files: dict[str, str] = {}
    for name in VAULT_FILES:
        remote = f"{remote_dir.rstrip('/')}/{name}"
        cmd = [
            "ssh",
            "-i",
            str(key_path),
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=20",
            "-o",
            "IdentitiesOnly=yes",
            f"{user}@{host}",
            f"cat {remote}",
        ]
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=60, check=False
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise RuntimeError(f"ssh failed for {name}: {exc}") from exc
        if proc.returncode != 0:
            # optional files may be missing
            if name == "manifest.json":
                raise RuntimeError(
                    f"ssh cat {remote} failed: {proc.stderr.strip() or proc.returncode}"
                )
            continue
        files[name] = proc.stdout
    if "manifest.json" not in files:
        raise RuntimeError("manifest.json missing from Helsinki vault")
    return files


def poll_once(
    *,
    state_path: Path = STATE_PATH,
    host: str = DEFAULT_HOST,
    user: str = DEFAULT_SSH_USER,
    key: str = DEFAULT_SSH_KEY,
    act: bool = False,
    monorepo: Path | None = None,
) -> dict[str, Any]:
    """Fetch vault, compare to durable last hash, optionally act on should_act."""
    files = fetch_vault_ssh(host=host, user=user, key=key)
    man = parse_manifest(files["manifest.json"])
    if not is_helsinki_sourced(man):
        raise RuntimeError(
            f"manifest is not Helsinki-sourced: source_of_truth={man.get('source_of_truth')!r}"
        )
    if str(man.get("github_breadcrumb_flow") or "").lower() not in (
        "deprecated",
        "disabled",
        "off",
        "",
    ):
        # Empty allowed only if source is clearly helsinki
        if "helsinki" not in str(man.get("source_of_truth") or "").lower():
            raise RuntimeError("refusing non-deprecated GitHub breadcrumb flow")

    state = load_state(state_path)
    prev = state.get("aggregate_hash")
    if prev is not None:
        prev = str(prev)
    diff = compare_vault(prev, files, manifest=man)
    result: dict[str, Any] = {
        "polled_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "host": host,
        "diff": diff,
        "monopin": man.get("monopin"),
        "macbook_actions": man.get("macbook_actions") or [],
        "source_of_truth": man.get("source_of_truth"),
        "github_breadcrumb_flow": man.get("github_breadcrumb_flow"),
    }

    work_log: list[str] = []
    if act and diff.get("should_act"):
        work_log = execute_vault_actions(
            man, monorepo=monorepo or Path(__file__).resolve().parents[1]
        )
        result["work"] = work_log
    elif act and not diff.get("changed"):
        result["work"] = ["skipped: vault unchanged"]
    elif act and diff.get("changed") and not diff.get("needs_work"):
        result["work"] = ["skipped: changed but needs_work false"]

    # Always advance durable snapshot after successful poll
    state = {
        "aggregate_hash": diff["current_hash"],
        "file_hashes": vault_file_hashes(files),
        "last_polled_at": result["polled_at"],
        "monopin": man.get("monopin"),
        "needs_work": diff.get("needs_work"),
        "host": host,
        "source": "helsinki_ssh",
    }
    save_state(state, state_path)
    result["state_path"] = str(state_path)
    return result


def execute_vault_actions(
    manifest: dict[str, Any], *, monorepo: Path
) -> list[str]:
    """Run Mac-related actions listed in vault (best-effort; log outcomes)."""
    logs: list[str] = []
    actions = list(manifest.get("macbook_actions") or [])
    monopin = str(manifest.get("monopin") or "").strip()
    plats = manifest.get("platforms") or {}
    if not isinstance(plats, dict):
        plats = {}

    # Prefer concrete needs_work platforms
    if isinstance(plats.get("macos"), dict) and plats["macos"].get("needs_work"):
        if "rebuild_macos_native_seal" not in actions:
            actions.append("rebuild_macos_native_seal")
    if isinstance(plats.get("ios"), dict) and plats["ios"].get("needs_work"):
        if "rebuild_ios_team_sign" not in actions:
            actions.append("rebuild_ios_team_sign")

    for action in actions:
        if action == "rebuild_macos_native_seal":
            logs.append(_run_macos_native_seal(monorepo, monopin))
        elif action == "rebuild_ios_team_sign":
            logs.append(_run_ios_team_sign(monorepo, monopin))
        else:
            logs.append(f"unknown_action:{action}")
    return logs


def _run_macos_native_seal(monorepo: Path, monopin: str) -> str:
    """Flutter macOS release + stage CFBundle gate + upload to Helsinki paid store."""
    app = (
        monorepo
        / "client_app"
        / "build"
        / "macos"
        / "Build"
        / "Products"
        / "Release"
        / "restore_privacy_client.app"
    )
    env = os.environ.copy()
    env.setdefault("RPT_SSH_HOST", DEFAULT_HOST)
    env.setdefault("RPT_SSH_USER", DEFAULT_SSH_USER)
    env.setdefault("RPT_SSH_KEY", DEFAULT_SSH_KEY)
    env.setdefault("RPT_SSH_SUDO", "0")

    steps: list[str] = []
    # Build
    build = subprocess.run(
        ["flutter", "build", "macos", "--release"],
        cwd=str(monorepo / "client_app"),
        capture_output=True,
        text=True,
        timeout=600,
        env=env,
    )
    steps.append(f"flutter_build_macos exit={build.returncode}")
    if build.returncode != 0:
        return "; ".join(steps) + f" err={build.stderr[-400:]}"

    release_script = monorepo / "scripts" / f"build_release_{monopin}.py"
    if not release_script.is_file():
        return f"missing {release_script}"
    rel = subprocess.run(
        [sys.executable, str(release_script), "--apple-only"],
        cwd=str(monorepo),
        capture_output=True,
        text=True,
        timeout=900,
        env=env,
    )
    steps.append(f"build_release_apple_only exit={rel.returncode}")
    if rel.returncode != 0:
        return "; ".join(steps) + f" err={rel.stderr[-500:]}"

    # Upload to Helsinki (paid assets)
    host_script = monorepo / "scripts" / "host_paid_assets_vps.py"
    up = subprocess.run(
        [
            sys.executable,
            str(host_script),
            "--stage",
            "--upload",
            "--version",
            monopin,
            "--force",
        ],
        cwd=str(monorepo),
        capture_output=True,
        text=True,
        timeout=1200,
        env=env,
    )
    steps.append(f"host_paid_assets_upload exit={up.returncode}")
    if up.returncode != 0:
        steps.append(f"upload_err={up.stderr[-400:]}")
    return "; ".join(steps)


def _run_ios_team_sign(monorepo: Path, monopin: str) -> str:
    """Best-effort iOS release build; Team-sign may need secrets."""
    build = subprocess.run(
        ["flutter", "build", "ios", "--release", "--no-codesign"],
        cwd=str(monorepo / "client_app"),
        capture_output=True,
        text=True,
        timeout=600,
    )
    if build.returncode != 0:
        return f"flutter_build_ios exit={build.returncode} err={build.stderr[-400:]}"
    return f"flutter_build_ios exit=0 monopin={monopin} (Team-sign device path may still need operator secrets)"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "command",
        choices=("poll", "diff-self-test", "show-state"),
        help="poll=fetch Helsinki vault; show-state=print durable state",
    )
    ap.add_argument("--act", action="store_true", help="Run vault actions when should_act")
    ap.add_argument("--host", default=DEFAULT_HOST)
    ap.add_argument("--user", default=DEFAULT_SSH_USER)
    ap.add_argument("--key", default=DEFAULT_SSH_KEY)
    ap.add_argument("--state", default=str(STATE_PATH))
    args = ap.parse_args(argv)

    if args.command == "show-state":
        print(json.dumps(load_state(Path(args.state)), indent=2))
        return 0

    if args.command == "diff-self-test":
        # pure offline demo
        a = {"manifest.json": '{"schema":"rpt.breadcrumbs.v1","needs_any_apple_work":false}'}
        b = {"manifest.json": '{"schema":"rpt.breadcrumbs.v1","needs_any_apple_work":true}'}
        h1 = vault_aggregate_hash(a)
        print(json.dumps(compare_vault(None, a), indent=2))
        print(json.dumps(compare_vault(h1, a), indent=2))
        print(json.dumps(compare_vault(h1, b), indent=2))
        return 0

    try:
        result = poll_once(
            state_path=Path(args.state),
            host=args.host,
            user=args.user,
            key=args.key,
            act=args.act,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
