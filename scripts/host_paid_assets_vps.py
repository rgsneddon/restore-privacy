#!/usr/bin/env python3
"""Collect per-device product installers and host them on the Iceland VPS.

Enumerates the shipped catalog (one package per platform: windows, android,
macos, ios, linux), stages files under ``status_page/assets/{VERSION}/``, and
optionally uploads to **82.221.101.241** at::

  /opt/restore-privacy/paid_assets/{VERSION}/{filename}

The status host (Render) completes paid downloads by proxying from that store
(``open_release_asset`` → local or Iceland HTTP with ``RPT_ASSET_FETCH_TOKEN``).

Usage::

  # List catalog only (no I/O beyond reading constants)
  python scripts/host_paid_assets_vps.py --list

  # Stage from releases/{VERSION} or existing status_page/assets into paid layout
  python scripts/host_paid_assets_vps.py --stage

  # Upload to Iceland VPS + install/restart token-gated serve (needs SSH)
  export RPT_SSH_USER=raskul RPT_SSH_SUDO=1 RPT_SSH_KEY=~/.ssh/id_ed25519_restore_privacy_vps
  export RPT_ASSET_FETCH_TOKEN='long-random-secret'
  python scripts/host_paid_assets_vps.py --stage --upload --install-serve

  # Dry-run upload plan
  python scripts/host_paid_assets_vps.py --upload --dry-run

Environment (SSH — same as deploy_rpt_node.py):
  RPT_SSH_HOST  default 82.221.101.241
  RPT_SSH_USER  default root (FlokiNET often raskul + RPT_SSH_SUDO=1)
  RPT_SSH_KEY / RPT_SSH_PASSWORD
  RPT_ASSET_FETCH_TOKEN  shared secret for VPS HTTP serve + Render fetch
"""

from __future__ import annotations

import argparse
import os
import secrets
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "status_page"
sys.path.insert(0, str(STATUS))

from downloads import (  # noqa: E402
    RELEASE_VERSION,
    list_catalog_platform_packages,
)
from payments import (  # noqa: E402
    DEFAULT_VPS_ASSET_HOST,
    DEFAULT_VPS_ASSET_PORT,
    DEFAULT_VPS_ASSET_REMOTE_ROOT,
    VPS_ASSET_HTTP_PREFIX,
    catalog_filenames,
)

SERVE_SCRIPT_LOCAL = ROOT / "node" / "serve_paid_assets.py"
SERVE_SCRIPT_REMOTE = f"{DEFAULT_VPS_ASSET_REMOTE_ROOT}/serve_paid_assets.py"
UNIT_NAME = "rpt-paid-assets.service"


def list_packages(version: str | None = None) -> list[dict[str, str]]:
    """Shipped helper: current catalog version + five platform packages."""
    return list_catalog_platform_packages(version=version)


def print_catalog(version: str | None = None) -> None:
    pkgs = list_packages(version)
    ver = pkgs[0]["version"] if pkgs else (version or RELEASE_VERSION)
    print(f"catalog_version={ver}")
    print(f"platforms={len(pkgs)}")
    for p in pkgs:
        print(
            f"  platform={p['platform']:<8} file={p['filename']} "
            f"rel={p['relative_path']}"
        )


def _candidate_sources(version: str, filename: str) -> list[Path]:
    return [
        STATUS / "assets" / version / filename,
        ROOT / "releases" / version / filename,
        STATUS / "assets" / RELEASE_VERSION / filename.replace(version, RELEASE_VERSION, 1)
        if version != RELEASE_VERSION
        else STATUS / "assets" / RELEASE_VERSION / filename,
    ]


def stage_packages(*, version: str | None = None) -> list[Path]:
    """Copy each platform installer into status_page/assets/{version}/."""
    pkgs = list_packages(version)
    ver = pkgs[0]["version"]
    dst_dir = STATUS / "assets" / ver
    dst_dir.mkdir(parents=True, exist_ok=True)
    staged: list[Path] = []
    for p in pkgs:
        fname = p["filename"]
        src = None
        for cand in _candidate_sources(ver, fname):
            if cand.is_file() and cand.stat().st_size > 0:
                src = cand
                break
        if src is None:
            raise FileNotFoundError(
                f"missing installer for platform={p['platform']}: {fname} "
                f"(looked under status_page/assets/ and releases/)"
            )
        dst = dst_dir / fname
        if src.resolve() != dst.resolve():
            shutil.copy2(src, dst)
        staged.append(dst)
        print(f"staged platform={p['platform']} {dst} ({dst.stat().st_size} bytes)")
    # refuse privs
    for p in dst_dir.rglob("*.priv"):
        raise RuntimeError(f"refusing to stage private key: {p}")
    return staged


def _ssh_connect():
    try:
        import paramiko
    except ImportError as e:
        raise SystemExit("paramiko required: pip install paramiko") from e

    host = os.environ.get("RPT_SSH_HOST", DEFAULT_VPS_ASSET_HOST).strip() or DEFAULT_VPS_ASSET_HOST
    user = os.environ.get("RPT_SSH_USER", "root").strip() or "root"
    password = os.environ.get("RPT_SSH_PASSWORD")
    key = os.environ.get("RPT_SSH_KEY", "").strip()
    key_path = Path(key).expanduser() if key else None
    if key_path is None or not key_path.is_file():
        home = Path.home() / ".ssh"
        for name in (
            "id_ed25519_restore_privacy_vps",
            "id_ed25519",
            "id_rsa",
        ):
            p = home / name
            if p.is_file():
                key_path = p
                break
    if not password and (key_path is None or not key_path.is_file()):
        raise SystemExit(
            "Need RPT_SSH_PASSWORD or SSH key (RPT_SSH_KEY / "
            "~/.ssh/id_ed25519_restore_privacy_vps)"
        )

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    kw: dict = {
        "hostname": host,
        "username": user,
        "timeout": 45,
        "allow_agent": False,
        "look_for_keys": False,
    }
    if password:
        kw["password"] = password
    else:
        kw["key_filename"] = str(key_path)
        print(f"ssh key={key_path}")
    print(f"connecting {user}@{host} …")
    client.connect(**kw)
    return client, host, user


def _run(client, cmd: str, *, sudo: bool, user: str) -> tuple[int, str]:
    use_sudo = sudo or (
        os.environ.get("RPT_SSH_SUDO", "").strip().lower() in ("1", "true", "yes")
        or user != "root"
    )
    if use_sudo and not cmd.strip().startswith("sudo "):
        cmd = f"sudo -n {cmd}"
    print(f"$ {cmd}")
    _, stdout, stderr = client.exec_command(cmd, timeout=600)
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    code = stdout.channel.recv_exit_status()
    if out:
        print(out, end="" if out.endswith("\n") else "\n")
    if err:
        print(err, end="" if err.endswith("\n") else "\n", file=sys.stderr)
    return code, out + err


def upload_packages(
    *,
    version: str | None = None,
    dry_run: bool = False,
    install_serve: bool = False,
) -> int:
    pkgs = list_packages(version)
    ver = pkgs[0]["version"]
    local_dir = STATUS / "assets" / ver
    for p in pkgs:
        f = local_dir / p["filename"]
        if not f.is_file() or f.stat().st_size < 1_000_000:
            print(f"missing or tiny local stage: {f}", file=sys.stderr)
            print("Run with --stage first.", file=sys.stderr)
            return 1

    remote_root = os.environ.get(
        "RPT_VPS_ASSET_REMOTE_ROOT", DEFAULT_VPS_ASSET_REMOTE_ROOT
    ).strip() or DEFAULT_VPS_ASSET_REMOTE_ROOT
    remote_ver = f"{remote_root.rstrip('/')}/{ver}"

    print(f"upload plan: {len(pkgs)} files -> {DEFAULT_VPS_ASSET_HOST}:{remote_ver}/")
    for p in pkgs:
        print(f"  {p['platform']}: {p['filename']}")

    if dry_run:
        print("dry-run: no SSH")
        return 0

    client, host, user = _ssh_connect()
    use_sudo = os.environ.get("RPT_SSH_SUDO", "").strip().lower() in (
        "1",
        "true",
        "yes",
    ) or user != "root"

    try:
        _run(client, f"mkdir -p {remote_ver}", sudo=use_sudo, user=user)
        if use_sudo:
            _run(
                client,
                f"chown -R {user}:{user} {remote_root}",
                sudo=True,
                user=user,
            )
        sftp = client.open_sftp()
        for p in pkgs:
            local = local_dir / p["filename"]
            remote = f"{remote_ver}/{p['filename']}"
            print(f"put {local.name} -> {remote} ({local.stat().st_size} bytes)")
            sftp.put(str(local), remote)
        # Verify remote sizes
        for p in pkgs:
            remote = f"{remote_ver}/{p['filename']}"
            st = sftp.stat(remote)
            if st.st_size < 1_000_000:
                print(f"ERROR remote too small: {remote} size={st.st_size}", file=sys.stderr)
                sftp.close()
                return 1
            print(f"  remote_ok {p['platform']} bytes={st.st_size}")
        if install_serve:
            if not SERVE_SCRIPT_LOCAL.is_file():
                print(f"missing {SERVE_SCRIPT_LOCAL}", file=sys.stderr)
                sftp.close()
                return 1
            print(f"put serve script -> {SERVE_SCRIPT_REMOTE}")
            sftp.put(str(SERVE_SCRIPT_LOCAL), SERVE_SCRIPT_REMOTE)
            _run(client, f"chmod +x {SERVE_SCRIPT_REMOTE}", sudo=use_sudo, user=user)
        sftp.close()

        if install_serve:
            token = os.environ.get("RPT_ASSET_FETCH_TOKEN", "").strip()
            if not token:
                token = secrets.token_urlsafe(32)
                print(
                    f"generated RPT_ASSET_FETCH_TOKEN (set on Render too): {token}",
                    file=sys.stderr,
                )
            port = os.environ.get("RPT_VPS_ASSET_PORT", str(DEFAULT_VPS_ASSET_PORT)).strip()
            unit = f"""[Unit]
Description=Restore Privacy paid asset server (token-gated)
After=network.target

[Service]
Type=simple
Environment=RPT_ASSET_FETCH_TOKEN={token}
Environment=RPT_VPS_ASSET_REMOTE_ROOT={remote_root}
Environment=RPT_VPS_ASSET_PORT={port}
Environment=RPT_VPS_ASSET_BIND=0.0.0.0
ExecStart=/usr/bin/python3 {SERVE_SCRIPT_REMOTE}
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
"""
            # Write unit via temp + sudo mv
            tmp_unit = f"/tmp/{UNIT_NAME}"
            sftp = client.open_sftp()
            with sftp.file(tmp_unit, "w") as rf:
                rf.write(unit)
            sftp.close()
            _run(
                client,
                f"mv {tmp_unit} /etc/systemd/system/{UNIT_NAME} && "
                f"systemctl daemon-reload && "
                f"systemctl enable {UNIT_NAME} && "
                f"systemctl restart {UNIT_NAME} && "
                f"systemctl is-active {UNIT_NAME}",
                sudo=True,
                user=user,
            )
            print(
                f"serve: http://{host}:{port}{VPS_ASSET_HTTP_PREFIX}/{{version}}/{{file}}"
            )
            print("Render env: RPT_VPS_ASSET_BASE + RPT_ASSET_FETCH_TOKEN")
        print(f"upload complete host={host} version={ver}")
        return 0
    finally:
        client.close()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Stage per-device installers and host them on the Iceland VPS"
    )
    ap.add_argument(
        "--version",
        default="",
        help=f"Catalog version (default: shipped RELEASE_VERSION={RELEASE_VERSION})",
    )
    ap.add_argument(
        "--list",
        action="store_true",
        help="Print version + five platform filenames (no stage/upload)",
    )
    ap.add_argument(
        "--stage",
        action="store_true",
        help="Copy each platform package into status_page/assets/{version}/",
    )
    ap.add_argument(
        "--upload",
        action="store_true",
        help="Upload staged packages to Iceland VPS paid_assets path",
    )
    ap.add_argument(
        "--install-serve",
        action="store_true",
        help="Install/restart token-gated HTTP serve on VPS (with --upload)",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="With --upload: print plan only (no SSH)",
    )
    args = ap.parse_args(argv)
    ver = (args.version or "").strip() or None

    if args.list or not (args.stage or args.upload):
        print_catalog(ver)
        if not (args.stage or args.upload):
            return 0

    if args.stage:
        try:
            stage_packages(version=ver)
        except (FileNotFoundError, RuntimeError) as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 1
        # Sanity: catalog filenames match staged
        pkgs = list_packages(ver)
        names = {p["filename"] for p in pkgs}
        if names != set(catalog_filenames()) and (ver is None or ver == RELEASE_VERSION):
            # only enforce exact catalog set for current RELEASE_VERSION
            missing = set(catalog_filenames()) - names
            if missing:
                print(f"ERROR catalog mismatch missing={missing}", file=sys.stderr)
                return 1

    if args.upload:
        return upload_packages(
            version=ver, dry_run=args.dry_run, install_serve=args.install_serve
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
