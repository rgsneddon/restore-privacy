#!/usr/bin/env python3
"""Deploy RPT node over SSH.

Auth (never commit secrets):
  - Preferred: OpenSSH key via RPT_SSH_KEY (or default ~/.ssh/id_ed25519_restore_privacy_vps
    then ~/.ssh/id_ed25519) with RPT_SSH_USER (default root; FlokiNET often uses a sudo user).
  - Or: RPT_SSH_PASSWORD for password auth (look_for_keys=False).

Environment:
  RPT_SSH_HOST     default 82.221.101.241
  RPT_SSH_USER     default root
  RPT_SSH_KEY      path to private key (optional)
  RPT_SSH_PASSWORD password auth (optional if key works)
  RPT_SSH_SUDO     if "1"/true, prefix install commands with sudo -n
"""

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

# Extra non-.py artifacts required for privacy install path
NODE_EXTRA = (
    "install.sh",
    "install_dns.sh",
    "install_host_privacy.sh",
    "unbound-rpt.conf",
)

DEFAULT_HOST = "82.221.101.241"


def _env_truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def _resolve_key_path() -> Path | None:
    explicit = os.environ.get("RPT_SSH_KEY", "").strip()
    if explicit:
        p = Path(explicit).expanduser()
        return p if p.is_file() else None
    home = Path.home() / ".ssh"
    for name in (
        "id_ed25519_restore_privacy_vps",
        "id_ed25519",
        "id_rsa",
    ):
        p = home / name
        if p.is_file():
            return p
    return None


def main() -> int:
    host = os.environ.get("RPT_SSH_HOST", DEFAULT_HOST).strip() or DEFAULT_HOST
    user = os.environ.get("RPT_SSH_USER", "root").strip() or "root"
    password = os.environ.get("RPT_SSH_PASSWORD")
    key_path = _resolve_key_path()
    use_sudo = _env_truthy("RPT_SSH_SUDO") or user != "root"

    if not password and key_path is None:
        print(
            "Need RPT_SSH_PASSWORD or an SSH private key "
            "(RPT_SSH_KEY or ~/.ssh/id_ed25519_restore_privacy_vps)",
            file=sys.stderr,
        )
        return 2

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"connecting {user}@{host} ...")
    connect_kw: dict = {
        "hostname": host,
        "username": user,
        "timeout": 30,
        "allow_agent": False,
    }
    if password:
        connect_kw["password"] = password
        connect_kw["look_for_keys"] = False
    else:
        connect_kw["look_for_keys"] = False
        connect_kw["key_filename"] = str(key_path)
        print(f"using key {key_path}")

    client.connect(**connect_kw)

    def run(cmd: str, timeout: int = 300, *, as_root: bool = False) -> tuple[int, str]:
        if as_root and use_sudo and not cmd.strip().startswith("sudo "):
            cmd = f"sudo -n {cmd}"
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

    # Ensure sudo works non-interactively when needed
    if use_sudo:
        code, _ = run("sudo -n true", timeout=30, as_root=False)
        if code != 0:
            print(
                "ERROR: passwordless sudo required for non-root deploy "
                "(or set RPT_SSH_USER=root with key access)",
                file=sys.stderr,
            )
            client.close()
            return 1

    run("mkdir -p /opt/restore-privacy/node /opt/restore-privacy/secrets", as_root=True)
    # Ensure deploy user can write via sftp into node dir
    run("chmod 755 /opt/restore-privacy /opt/restore-privacy/node", as_root=True)
    if use_sudo:
        run(f"chown -R {user}:{user} /opt/restore-privacy/node", as_root=True)

    def put_text_lf(local: Path, remote: str) -> None:
        """Upload text file with Unix newlines (CRLF breaks ``set -o pipefail``)."""
        data = local.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        with sftp.file(remote, "wb") as rf:
            rf.write(data)

    sftp = client.open_sftp()
    for path in sorted(NODE_DIR.glob("*.py")):
        remote = f"/opt/restore-privacy/node/{path.name}"
        print(f"put {path.name}")
        sftp.put(str(path), remote)
    for name in NODE_EXTRA:
        local = NODE_DIR / name
        if not local.is_file():
            print(f"WARN: missing {local}", file=sys.stderr)
            continue
        remote = f"/opt/restore-privacy/node/{name}"
        print(f"put {name} (lf)")
        put_text_lf(local, remote)
    sftp.close()

    run("chmod +x /opt/restore-privacy/node/install.sh /opt/restore-privacy/node/install_dns.sh /opt/restore-privacy/node/install_host_privacy.sh 2>/dev/null || true", as_root=True)
    code, _ = run("bash /opt/restore-privacy/node/install.sh", timeout=900, as_root=True)
    if code != 0:
        print(f"install failed exit={code}", file=sys.stderr)
        client.close()
        return code or 1

    # Privacy scripts again after TUN may exist
    run("bash /opt/restore-privacy/node/install_dns.sh", timeout=300, as_root=True)
    run("bash /opt/restore-privacy/node/install_host_privacy.sh", timeout=120, as_root=True)

    time.sleep(2)
    run("systemctl daemon-reload; systemctl enable rpt-node.service", as_root=True)
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
        "test -f /opt/restore-privacy/secrets/node_elgamal.pub && echo node_pub=ok",
        "systemctl is-active unbound 2>/dev/null || systemctl is-active unbound.service 2>/dev/null || true",
        "ss -ulnp | grep ':53' || true",
        "grep -E 'interface:|access-control' /etc/unbound/unbound.conf.d/rpt-tunnel.conf 2>/dev/null || true",
        "hostname -I || true",
        "grep -E 'Restart=|WantedBy=|network-online|StandardOutput' /etc/systemd/system/rpt-node.service || true",
    ]:
        run(c, as_root=True)

    code, out = run("systemctl is-enabled rpt-node.service", as_root=True)
    if out.strip() != "enabled":
        print(f"ERROR: rpt-node not enabled for boot (is-enabled={out!r})", file=sys.stderr)
        client.close()
        return 1

    code, out = run("systemctl is-active rpt-node.service", as_root=True)
    if out.strip() != "active":
        print(f"ERROR: rpt-node not active (is-active={out!r})", file=sys.stderr)
        client.close()
        return 1

    client.close()
    print(f"deploy complete host={host} boot-enabled active")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
