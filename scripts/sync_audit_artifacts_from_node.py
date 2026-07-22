#!/usr/bin/env python3
"""Pull security audit artifacts from the entry node into this repo (operator).

The hardened ``rpt-security-audit`` oneshot writes **local** AUDIT.md +
``security_audit_latest.json`` on the node only (no outbound git/HTTP publish).
Public homepage countdown reads ``status_page/static/security_audit_latest.json``
from the status host deploy — so without this sync (or an equivalent publish),
the public ``generated_at`` goes stale while the node timer still runs.

Usage (from a machine with SSH access)::

  python scripts/sync_audit_artifacts_from_node.py
  RPT_SSH_HOST=82.221.101.241 RPT_SSH_USER=raskul python scripts/sync_audit_artifacts_from_node.py

Does not upload secrets. Copies only:
  - status_page/static/security_audit_latest.json
  - AUDIT.md → repo root + status_page/public/AUDIT.md (+ status_page/AUDIT.md)
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HOST = "82.221.101.241"
DEFAULT_USER = "raskul"
REMOTE_JSON = "/opt/restore-privacy/status_page/static/security_audit_latest.json"
REMOTE_AUDIT = "/opt/restore-privacy/AUDIT.md"


def _ssh_base() -> list[str]:
    host = os.environ.get("RPT_SSH_HOST", DEFAULT_HOST).strip() or DEFAULT_HOST
    user = os.environ.get("RPT_SSH_USER", DEFAULT_USER).strip() or DEFAULT_USER
    key = os.environ.get("RPT_SSH_KEY", "").strip()
    remote = f"{user}@{host}"
    cmd = ["scp", "-o", "BatchMode=yes", "-o", "ConnectTimeout=30"]
    if key:
        cmd.extend(["-i", key])
    else:
        # Prefer product VPS key if present
        cand = Path.home() / ".ssh" / "id_ed25519_restore_privacy_vps"
        if cand.is_file():
            cmd.extend(["-i", str(cand)])
    return cmd, remote


def main() -> int:
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

    print("[sync-audit] done — commit + deploy status host so public countdown advances")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
