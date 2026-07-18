#!/usr/bin/env python3
"""Deploy RPT node over SSH. Password via RPT_SSH_PASSWORD only (never commit)."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

try:
    import paramiko
except ImportError:
    print("paramiko required: pip install paramiko", file=sys.stderr)
    raise SystemExit(2)

ROOT = Path(__file__).resolve().parents[1]
NODE_DIR = ROOT / "node"


def main() -> int:
    host = os.environ.get("RPT_SSH_HOST", "104.156.224.47")
    user = os.environ.get("RPT_SSH_USER", "root")
    password = os.environ.get("RPT_SSH_PASSWORD")
    if not password:
        print("RPT_SSH_PASSWORD not set", file=sys.stderr)
        return 2

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"connecting {user}@{host} ...")
    client.connect(
        hostname=host,
        username=user,
        password=password,
        timeout=30,
        allow_agent=False,
        look_for_keys=False,
    )

    def run(cmd: str, timeout: int = 300) -> tuple[int, str]:
        print(f"$ {cmd}")
        _, stdout, stderr = client.exec_command(cmd, timeout=timeout)
        out = stdout.read().decode("utf-8", "replace")
        err = stderr.read().decode("utf-8", "replace")
        code = stdout.channel.recv_exit_status()
        if out:
            print(out, end="" if out.endswith("\n") else "\n")
        if err:
            print(err, end="" if err.endswith("\n") else "\n", file=sys.stderr)
        return code, out + err

    run("mkdir -p /opt/restore-privacy/node /opt/restore-privacy/secrets")
    sftp = client.open_sftp()
    for path in NODE_DIR.glob("*.py"):
        remote = f"/opt/restore-privacy/node/{path.name}"
        print(f"put {path.name}")
        sftp.put(str(path), remote)
    sftp.put(str(NODE_DIR / "install.sh"), "/opt/restore-privacy/node/install.sh")
    sftp.close()

    run("chmod +x /opt/restore-privacy/node/install.sh")
    code, _ = run("bash /opt/restore-privacy/node/install.sh", timeout=600)
    if code != 0:
        print(f"install failed exit={code}", file=sys.stderr)
        client.close()
        return code or 1

    time.sleep(2)
    # Explicitly ensure boot enable even if install.sh was old on disk
    run("systemctl daemon-reload; systemctl enable rpt-node.service")
    for c in [
        "systemctl is-active rpt-node.service || true",
        "systemctl is-enabled rpt-node.service || true",
        "systemctl show rpt-node.service -p UnitFileState -p ActiveState -p Restart -p WantedBy --no-pager || true",
        "ss -ulnp | grep 44044 || true",
        "ss -tlnp | grep 8080 || true",
        "sysctl net.ipv4.ip_forward",
        "iptables -t nat -S POSTROUTING | grep -i masquerade || true",
        "ip addr show rpt0 || true",
        "curl -s http://127.0.0.1:8080/api/status || true",
        "test ! -d /var/log/rpt-node && echo no_rpt_log_dir=ok",
        "grep -E 'OnlyRestorePrivacyClient|CollectUserData|ConnectionLog|UITitle' /opt/restore-privacy/rpt-node.conf || true",
        "test -f /opt/restore-privacy/secrets/node_elgamal.pub && echo node_pub=ok",
        "test -f /opt/restore-privacy/secrets/client_ed25519.pub && echo client_pub=ok",
        "test -f /opt/restore-privacy/secrets/client_ed25519.priv && echo client_priv_present=ok",
        "grep -E 'Restart=|WantedBy=|network-online' /etc/systemd/system/rpt-node.service || true",
    ]:
        run(c)

    # Fail deploy if not boot-enabled (VPS reboot would leave node down)
    code, out = run("systemctl is-enabled rpt-node.service")
    if "enabled" not in out.strip().splitlines()[-1:]:
        # is-enabled prints "enabled" alone when OK
        if out.strip() != "enabled":
            print(f"ERROR: rpt-node not enabled for boot (is-enabled={out!r})", file=sys.stderr)
            client.close()
            return 1

    client.close()
    print("deploy complete (boot-enabled)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
