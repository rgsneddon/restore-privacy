#!/usr/bin/env python3
"""Publish timer-written audit artifacts so the public last-run advances.

The residual-node security audit timer (``rpt-security-audit.timer``) writes
``AUDIT.md`` + ``security_audit_latest.json`` **locally** only (section A:
no general outbound). Public homepage ``last audit run`` and ``/AUDIT.md``
read the status-host deploy surface — without this step they stay stuck on
the last *operator* publish.

This module is the **scheduled** bridge:

1. **Pull agent** (preferred): ``python3 scripts/sync_audit_artifacts_from_node.py --publish``
   pulls from the residual timer host then commits+pushes status_page artifacts.
2. **Post-write on node** (optional, constrained): when
   ``RPT_AUDIT_STATUS_SSH`` is set, scp **only** audit JSON + AUDIT.md to a
   remote that the status process can serve or that a pull agent mirrors.

Pure helpers below are unit-tested; I/O paths are the real shipped functions
used by the timer/publish wiring.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"

# Public-facing artifacts only (never secrets)
AUDIT_ARTIFACT_REL = (
    "AUDIT.md",
    "status_page/AUDIT.md",
    "status_page/public/AUDIT.md",
    "status_page/static/security_audit_latest.json",
)


def audit_artifact_paths(root: Path | None = None) -> list[Path]:
    r = root or ROOT
    return [r / rel for rel in AUDIT_ARTIFACT_REL]


def generated_at_from_json_file(path: Path | str) -> str | None:
    """Return ``generated_at`` from a security_audit_latest.json path (or None)."""
    p = Path(path)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    raw = data.get("generated_at")
    if not raw:
        return None
    return str(raw).strip() or None


def artifacts_ready_for_publish(root: Path | None = None) -> dict[str, Any]:
    """Check required audit files exist and JSON has generated_at."""
    r = root or ROOT
    paths = audit_artifact_paths(r)
    missing = [str(p) for p in paths if not p.is_file()]
    json_path = r / "status_page" / "static" / "security_audit_latest.json"
    gen = generated_at_from_json_file(json_path) if json_path.is_file() else None
    return {
        "ok": not missing and bool(gen),
        "missing": missing,
        "generated_at": gen,
        "json_path": str(json_path),
    }


def timer_write_then_publish_expected_steps() -> list[str]:
    """Ordered steps the product timer path must perform for public update."""
    return [
        "run_security_audit_write",  # --write AUDIT + security_audit_latest.json
        "publish_or_pull_to_status",  # scp/git or pull agent --publish
        "status_serves_new_generated_at",
    ]


def publish_local_audit_to_git(
    *,
    root: Path | None = None,
    commit: bool = True,
    push: bool = True,
) -> dict[str, Any]:
    """Commit + push audit artifacts so Render/status host redeploys last-run.

    Reuses ``run_security_audit.publish_audit_artifacts`` (same ship path as
    operator ``--publish``).
    """
    r = root or ROOT
    check = artifacts_ready_for_publish(r)
    if not check["ok"]:
        return {
            "ok": False,
            "published": False,
            "error": f"artifacts not ready: {check}",
            "steps": [{"action": "artifacts_ready", **check}],
        }
    # Import real publisher from the audit runner (shipped entry).
    sys.path.insert(0, str(SCRIPTS))
    import run_security_audit as rsa  # noqa: WPS433

    # Temporarily set ROOT context if runner uses module-level ROOT
    return rsa.publish_audit_artifacts(commit=commit, push=push)


def pull_from_timer_node_and_publish(
    *,
    publish: bool = True,
) -> dict[str, Any]:
    """Pull residual timer artifacts then publish to status deploy surface."""
    out: dict[str, Any] = {"ok": False, "steps": [], "error": None}
    sync = SCRIPTS / "sync_audit_artifacts_from_node.py"
    if not sync.is_file():
        out["error"] = f"missing {sync}"
        return out
    r = subprocess.run(
        [sys.executable, str(sync)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    out["steps"].append(
        {
            "action": "sync_from_node",
            "ok": r.returncode == 0,
            "stdout": (r.stdout or "")[-800:],
            "stderr": (r.stderr or "")[-400:],
        }
    )
    if r.returncode != 0:
        out["error"] = r.stderr or r.stdout or f"sync rc={r.returncode}"
        return out
    if not publish:
        out["ok"] = True
        out["published"] = False
        return out
    pub = publish_local_audit_to_git()
    out["steps"].append({"action": "publish_git", **pub})
    out["ok"] = bool(pub.get("ok"))
    out["published"] = bool(pub.get("published"))
    out["error"] = pub.get("error")
    out["generated_at"] = artifacts_ready_for_publish().get("generated_at")
    return out


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--pull-and-publish",
        action="store_true",
        help="Pull from residual timer host then git-publish for status host",
    )
    ap.add_argument(
        "--publish-only",
        action="store_true",
        help="Git-publish already-local audit artifacts (no pull)",
    )
    ap.add_argument(
        "--check",
        action="store_true",
        help="Print artifacts_ready JSON and exit 0/1",
    )
    args = ap.parse_args(argv)
    if args.check:
        c = artifacts_ready_for_publish()
        print(json.dumps(c, indent=2))
        return 0 if c.get("ok") else 1
    if args.pull_and_publish:
        r = pull_from_timer_node_and_publish(publish=True)
        print(json.dumps(r, indent=2, default=str))
        return 0 if r.get("ok") else 2
    if args.publish_only:
        r = publish_local_audit_to_git()
        print(json.dumps(r, indent=2, default=str))
        return 0 if r.get("ok") else 3
    ap.print_help()
    return 64


if __name__ == "__main__":
    raise SystemExit(main())
