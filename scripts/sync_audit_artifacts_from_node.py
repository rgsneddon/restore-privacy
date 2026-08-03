#!/usr/bin/env python3
"""Pull security audit artifacts from the audit-timer residual node.

The hardened oneshot writes **local** AUDIT.md + ``security_audit_latest.json``
on the residual timer host (section A: no general outbound). Public homepage
``last audit run`` and ``/AUDIT.md`` read the **status host** deploy — so a
successful timer run must be followed by this pull **and** a publish, or the
page stays on the last operator-commanded stamp.

Default residual timer host is the Iceland monopin (``82.221.101.241``) where
``rpt-security-audit.timer`` is active; override with ``RPT_SSH_HOST``.

Usage (from a machine with SSH access)::

  python scripts/sync_audit_artifacts_from_node.py
  python scripts/sync_audit_artifacts_from_node.py --publish
  # Override peer:
  RPT_SSH_HOST=185.146.232.107 RPT_SSH_USER=raskul python scripts/sync_audit_artifacts_from_node.py

Does not upload secrets. Copies only:
  - status_page/static/security_audit_latest.json
  - AUDIT.md → repo root + status_page/public/AUDIT.md (+ status_page/AUDIT.md)

``--publish`` commits+pushes those artifacts so Render/status redeploys the
new ``generated_at`` (required for timer-expiry public update).
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Default: Iceland residual monopin (active rpt-security-audit.timer as of 1.1.7).
DEFAULT_HOST = "82.221.101.241"
DEFAULT_USER = "raskul"
REMOTE_JSON = "/opt/restore-privacy/status_page/static/security_audit_latest.json"
REMOTE_AUDIT = "/opt/restore-privacy/AUDIT.md"


def _ssh_base() -> tuple[list[str], str]:
    host = os.environ.get("RPT_SSH_HOST", DEFAULT_HOST).strip() or DEFAULT_HOST
    user = os.environ.get("RPT_SSH_USER", DEFAULT_USER).strip() or DEFAULT_USER
    key = os.environ.get("RPT_SSH_KEY", "").strip()
    remote = f"{user}@{host}"
    cmd = ["scp", "-o", "BatchMode=yes", "-o", "ConnectTimeout=30"]
    if key:
        cmd.extend(["-i", key])
    else:
        # Prefer VPS (IS) then hop (RO) then EU (DE/Helsinki)
        for name in (
            "id_ed25519_restore_privacy_vps",
            "id_ed25519_restore_privacy_hop",
            "id_ed25519_restore_privacy_eu",
        ):
            cand = Path.home() / ".ssh" / name
            if cand.is_file():
                cmd.extend(["-i", str(cand)])
                break
    return cmd, remote


def pull_audit_artifacts() -> int:
    """SCP timer-written artifacts into the monorepo status_page tree."""
    scp, remote = _ssh_base()
    dest_json = ROOT / "status_page" / "static" / "security_audit_latest.json"
    dest_audit = ROOT / "AUDIT.md"
    dest_json.parent.mkdir(parents=True, exist_ok=True)

    print(f"[sync-audit] {remote}:{REMOTE_JSON} -> {dest_json}")
    r1 = subprocess.run(
        scp + [f"{remote}:{REMOTE_JSON}", str(dest_json)],
        capture_output=True,
        text=True,
    )
    if r1.returncode != 0:
        print(r1.stderr or r1.stdout, file=sys.stderr)
        return r1.returncode or 1

    print(f"[sync-audit] {remote}:{REMOTE_AUDIT} -> {dest_audit}")
    r2 = subprocess.run(
        scp + [f"{remote}:{REMOTE_AUDIT}", str(dest_audit)],
        capture_output=True,
        text=True,
    )
    if r2.returncode != 0:
        print(r2.stderr or r2.stdout, file=sys.stderr)
        return r2.returncode or 1

    # Mirrors for public docs / status package
    pub = ROOT / "status_page" / "public" / "AUDIT.md"
    sp = ROOT / "status_page" / "AUDIT.md"
    pub.parent.mkdir(parents=True, exist_ok=True)
    text = dest_audit.read_bytes()
    pub.write_bytes(text)
    sp.write_bytes(text)
    print(f"[sync-audit] mirrored AUDIT.md -> {pub} and {sp}")

    try:
        import json

        data = json.loads(dest_json.read_text(encoding="utf-8"))
        print(f"[sync-audit] generated_at={data.get('generated_at')}")
    except Exception as exc:  # noqa: BLE001
        print(f"[sync-audit] warn: could not parse JSON: {exc}", file=sys.stderr)

    return 0


def publish_pulled_artifacts() -> int:
    """Git-publish pulled audit artifacts (status host deploy surface)."""
    sys.path.insert(0, str(ROOT / "scripts"))
    from publish_timer_audit_to_status import publish_local_audit_to_git

    pub = publish_local_audit_to_git()
    print(f"[sync-audit] publish={pub}")
    if not pub.get("ok"):
        print(pub.get("error") or "publish failed", file=sys.stderr)
        return 4
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--publish",
        action="store_true",
        help="After pull, commit+push audit artifacts so public last-run advances",
    )
    args = ap.parse_args(argv)
    rc = pull_audit_artifacts()
    if rc != 0:
        return rc
    if args.publish:
        return publish_pulled_artifacts()
    print(
        "[sync-audit] done — pass --publish (or run publish_timer_audit_to_status) "
        "so status-host last-run advances without a manual operator audit command"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
