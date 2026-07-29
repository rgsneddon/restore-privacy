#!/usr/bin/env python3
"""Collect per-device product installers and host them on the Helsinki store.

Enumerates the shipped catalog (one package per platform: windows, android,
macos, ios, linux), stages files under ``status_page/assets/{VERSION}/``, and
optionally uploads to the **dedicated Helsinki** paid-asset host (default
``135.181.152.10``) at::

  /opt/restore-privacy/paid_assets/{VERSION}/{filename}

The Iceland residual monopin (``82.221.101.241``) is **node-only** — do not use
it as the installer CDN. Status host (Render) proxies paid downloads from the
Helsinki store (``open_release_asset`` + ``RPT_ASSET_FETCH_TOKEN``).

Usage::

  # List catalog only (no I/O beyond reading constants)
  python scripts/host_paid_assets_vps.py --list

  # Stage from releases/{VERSION} or existing status_page/assets into paid layout
  python scripts/host_paid_assets_vps.py --stage

  # Upload to Helsinki store + install/restart token-gated serve (needs SSH)
  export RPT_SSH_HOST=135.181.152.10 RPT_SSH_USER=root
  export RPT_SSH_KEY=~/.ssh/id_ed25519_20260725
  export RPT_ASSET_FETCH_TOKEN='long-random-secret'
  python scripts/host_paid_assets_vps.py --stage --upload --install-serve

  # Dry-run upload plan
  python scripts/host_paid_assets_vps.py --upload --dry-run

  # Remove paid-assets tree + unit from Iceland residual node (node-only cleanup)
  export RPT_SSH_HOST=82.221.101.241 RPT_SSH_USER=raskul RPT_SSH_SUDO=1
  export RPT_SSH_KEY=~/.ssh/id_ed25519_restore_privacy_vps
  python scripts/host_paid_assets_vps.py --remove-iceland-paid-assets

Environment (SSH):
  RPT_SSH_HOST  default Helsinki store host (payments.DEFAULT_VPS_ASSET_HOST)
  RPT_SSH_USER  default root
  RPT_SSH_KEY / RPT_SSH_PASSWORD
  RPT_ASSET_FETCH_TOKEN  shared secret for store HTTP serve + Render fetch
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


def _assert_macos_cfbundle(path: Path, monopin: str) -> None:
    """Fail closed: paid macOS zip host CFBundle must equal catalog monopin."""
    from apple_package_audit import require_macos_zip_matches_monopin

    ver = require_macos_zip_matches_monopin(path, monopin)
    print(f"macos CFBundleShortVersionString={ver} matches monopin {monopin}")


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
        if p["platform"] == "macos":
            _assert_macos_cfbundle(dst, ver)
        staged.append(dst)
        print(f"staged platform={p['platform']} {dst} ({dst.stat().st_size} bytes)")
    # refuse privs
    for p in dst_dir.rglob("*.priv"):
        raise RuntimeError(f"refusing to stage private key: {p}")
    return staged


def _ssh_target() -> tuple[str, str, str | None, Path | None]:
    """Return (host, user, password_or_None, key_path_or_None)."""
    host = os.environ.get("RPT_SSH_HOST", DEFAULT_VPS_ASSET_HOST).strip() or DEFAULT_VPS_ASSET_HOST
    user = os.environ.get("RPT_SSH_USER", "root").strip() or "root"
    password = os.environ.get("RPT_SSH_PASSWORD")
    key = os.environ.get("RPT_SSH_KEY", "").strip()
    key_path = Path(key).expanduser() if key else None
    if key_path is None or not key_path.is_file():
        home = Path.home() / ".ssh"
        for name in (
            "id_ed25519_20260725",  # Helsinki store
            "id_ed25519_restore_privacy_vps",  # Iceland residual node
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
            "~/.ssh/id_ed25519_20260725 or id_ed25519_restore_privacy_vps)"
        )
    return host, user, password, key_path


# Iceland residual monopin — node-only; paid installers live on Helsinki.
ICELAND_RESIDUAL_SSH_HOST = "82.221.101.241"
ICELAND_PAID_ASSETS_ROOT = "/opt/restore-privacy/paid_assets"


def remove_iceland_paid_assets(*, dry_run: bool = False) -> int:
    """Stop paid-asset serve on Iceland residual host and delete installer tree.

    Does **not** touch residual node software, keys, or wipe timers — only the
    paid_assets directory and ``rpt-paid-assets`` systemd unit.
    """
    host = (
        os.environ.get("RPT_SSH_HOST", ICELAND_RESIDUAL_SSH_HOST).strip()
        or ICELAND_RESIDUAL_SSH_HOST
    )
    # Force Iceland residual defaults for this op unless operator overrode user/key
    if not os.environ.get("RPT_SSH_HOST", "").strip():
        os.environ["RPT_SSH_HOST"] = ICELAND_RESIDUAL_SSH_HOST
    if not os.environ.get("RPT_SSH_USER", "").strip():
        os.environ["RPT_SSH_USER"] = "raskul"
    if not os.environ.get("RPT_SSH_SUDO", "").strip():
        os.environ["RPT_SSH_SUDO"] = "1"

    remote_root = ICELAND_PAID_ASSETS_ROOT
    unit = UNIT_NAME
    print(f"iceland_cleanup host={host} root={remote_root} unit={unit}")
    if dry_run:
        print("dry-run: would stop/disable unit, remove unit file, rm -rf paid_assets")
        return 0

    host, user, password, key_path = _ssh_target()
    use_openssh = password is None and key_path is not None and _openssh_available()
    script = (
        f"set -e; "
        f"systemctl stop {unit} 2>/dev/null || true; "
        f"systemctl disable {unit} 2>/dev/null || true; "
        f"rm -f /etc/systemd/system/{unit}; "
        f"systemctl daemon-reload 2>/dev/null || true; "
        f"rm -rf {remote_root}; "
        f"echo REMOVED_ROOT; "
        f"test ! -e {remote_root} && echo paid_assets_absent=yes || echo paid_assets_absent=no; "
        f"systemctl is-active {unit} 2>/dev/null || echo unit_inactive; "
        f"ss -lntp 2>/dev/null | grep -E ':8081|:44044' || true; "
        f"pgrep -af 'rpt|node|serve_paid' 2>/dev/null | head -20 || true"
    )
    if use_openssh:
        assert key_path is not None
        code, out = _ssh_run_openssh(
            script, host=host, user=user, key_path=key_path, sudo=True
        )
        print(out)
        if code != 0:
            print(f"ERROR iceland cleanup failed code={code}", file=sys.stderr)
            return 1
        if "paid_assets_absent=yes" not in out and "REMOVED_ROOT" not in out:
            # tolerate partial if tree already gone
            if "paid_assets_absent=no" in out:
                print("ERROR paid_assets still present", file=sys.stderr)
                return 1
        print(f"iceland_cleanup_ok host={host}")
        return 0

    client, host, user = _ssh_connect()
    use_sudo = _want_sudo(user)
    try:
        code, out = _run(client, script, sudo=use_sudo, user=user)
        print(out)
        if code != 0:
            return 1
        print(f"iceland_cleanup_ok host={host}")
        return 0
    finally:
        client.close()


def _ssh_connect():
    try:
        import paramiko
    except ImportError as e:
        raise SystemExit("paramiko required: pip install paramiko") from e

    host, user, password, key_path = _ssh_target()
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    kw: dict = {
        "hostname": host,
        "username": user,
        "timeout": 60,
        "banner_timeout": 60,
        "auth_timeout": 60,
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


def _openssh_available() -> bool:
    from shutil import which

    return bool(which("scp") and which("ssh"))


def _scp_put_file(
    local: Path,
    remote: str,
    *,
    host: str,
    user: str,
    key_path: Path | None,
) -> None:
    """Upload one file via OpenSSH scp (more reliable for multi‑MB installers)."""
    import subprocess

    cmd = [
        "scp",
        "-o",
        "StrictHostKeyChecking=accept-new",
        "-o",
        "ServerAliveInterval=30",
        "-o",
        "ServerAliveCountMax=12",
        "-o",
        "ConnectTimeout=45",
    ]
    if key_path is not None:
        cmd.extend(["-i", str(key_path)])
    cmd.extend([str(local), f"{user}@{host}:{remote}"])
    print(f"$ scp {local.name} -> {user}@{host}:{remote}")
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    if proc.returncode != 0:
        msg = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(f"scp failed code={proc.returncode}: {msg}")


def _want_sudo(user: str, *, force: bool = False) -> bool:
    if force:
        return True
    return os.environ.get("RPT_SSH_SUDO", "").strip().lower() in (
        "1",
        "true",
        "yes",
    ) or user != "root"


def _run(client, cmd: str, *, sudo: bool, user: str) -> tuple[int, str]:
    use_sudo = _want_sudo(user, force=sudo)
    if use_sudo and not cmd.strip().startswith("sudo "):
        # Run the whole pipeline as root via bash -lc
        import shlex

        cmd = f"sudo -n bash -lc {shlex.quote(cmd)}"
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


def _ssh_run_openssh(
    cmd: str,
    *,
    host: str,
    user: str,
    key_path: Path,
    sudo: bool = False,
) -> tuple[int, str]:
    """Run a remote shell command via OpenSSH (fresh connection each call)."""
    import shlex
    import subprocess

    if sudo or _want_sudo(user):
        remote = f"sudo -n bash -lc {shlex.quote(cmd)}"
    else:
        remote = f"bash -lc {shlex.quote(cmd)}"
    argv = [
        "ssh",
        "-o",
        "StrictHostKeyChecking=accept-new",
        "-o",
        "ServerAliveInterval=30",
        "-o",
        "ConnectTimeout=45",
        "-i",
        str(key_path),
        f"{user}@{host}",
        remote,
    ]
    print(f"$ ssh {user}@{host} {remote[:120]}{'…' if len(remote) > 120 else ''}")
    proc = subprocess.run(argv, capture_output=True, text=True, timeout=600)
    out = (proc.stdout or "") + (proc.stderr or "")
    if proc.stdout:
        print(proc.stdout, end="" if proc.stdout.endswith("\n") else "\n")
    if proc.stderr:
        print(proc.stderr, end="" if proc.stderr.endswith("\n") else "\n", file=sys.stderr)
    return proc.returncode, out


def _remote_size_openssh(
    remote_path: str,
    *,
    host: str,
    user: str,
    key_path: Path,
) -> int | None:
    code, out = _ssh_run_openssh(
        f"if test -f {remote_path}; then stat -c%s {remote_path}; else echo MISSING; fi",
        host=host,
        user=user,
        key_path=key_path,
        sudo=True,
    )
    if code != 0:
        return None
    for line in (out or "").splitlines():
        line = line.strip()
        if line.isdigit():
            return int(line)
    return None


def _upload_one_installer_openssh(
    local: Path,
    remote_final: str,
    *,
    host: str,
    user: str,
    key_path: Path,
    skip_if_present: bool = True,
) -> None:
    """Upload one installer with OpenSSH scp + size verify (fresh connections)."""
    expected = local.stat().st_size
    if skip_if_present:
        existing = _remote_size_openssh(
            remote_final, host=host, user=user, key_path=key_path
        )
        if existing == expected:
            print(f"  skip (already on VPS) {local.name} bytes={expected}")
            return
    # Absolute home path (tilde breaks under sudo bash -lc).
    home = "/root" if user == "root" else f"/home/{user}"
    home_tmp = f"{home}/rpt-paid-upload-{local.name}"
    last_err: Exception | None = None
    for attempt in range(1, 4):
        try:
            print(
                f"  scp attempt {attempt}: {local.name} ({expected} bytes) "
                f"-> {user}@{host}:{home_tmp}"
            )
            _scp_put_file(
                local, home_tmp, host=host, user=user, key_path=key_path
            )
            # Verify as user first (file is owned by scp user), then root-move to /opt.
            code, out = _ssh_run_openssh(
                f"set -e; "
                f"test -f {home_tmp}; "
                f"SZ=$(stat -c%s {home_tmp}); "
                f"test \"$SZ\" -eq {expected}; "
                f"echo size_ok=$SZ",
                host=host,
                user=user,
                key_path=key_path,
                sudo=False,
            )
            if code != 0:
                raise RuntimeError(f"size verify failed code={code}: {out}")
            code, out = _ssh_run_openssh(
                f"set -e; "
                f"mkdir -p $(dirname {remote_final}); "
                f"mv -f {home_tmp} {remote_final}; "
                f"chmod 644 {remote_final}; "
                f"chown root:root {remote_final} || true; "
                f"stat -c%s {remote_final}",
                host=host,
                user=user,
                key_path=key_path,
                sudo=True,
            )
            if code != 0:
                raise RuntimeError(f"remote install failed code={code}: {out}")
            print(f"  remote_ok {local.name} bytes={expected}")
            return
        except Exception as e:  # noqa: BLE001
            last_err = e
            print(f"  upload attempt {attempt} failed: {e}", file=sys.stderr)
            try:
                _ssh_run_openssh(
                    f"rm -f {home_tmp}",
                    host=host,
                    user=user,
                    key_path=key_path,
                    sudo=False,
                )
            except Exception:  # noqa: BLE001
                pass
    raise RuntimeError(f"upload failed after retries: {local.name}: {last_err}")


def install_serve_only(
    *,
    version: str | None = None,
) -> int:
    """Install/restart token-gated HTTP serve without re-uploading packages."""
    host, user, password, key_path = _ssh_target()
    if password is not None or key_path is None or not _openssh_available():
        print("install-serve-only requires OpenSSH key auth", file=sys.stderr)
        return 1
    remote_root = os.environ.get(
        "RPT_VPS_ASSET_REMOTE_ROOT", DEFAULT_VPS_ASSET_REMOTE_ROOT
    ).strip() or DEFAULT_VPS_ASSET_REMOTE_ROOT
    ver = (version or RELEASE_VERSION).strip()
    # Verify at least one package exists remotely
    sample = list_packages(ver)[0]
    remote_sample = f"{remote_root.rstrip('/')}/{ver}/{sample['filename']}"
    sz = _remote_size_openssh(
        remote_sample, host=host, user=user, key_path=key_path
    )
    if not sz or sz < 1_000_000:
        print(
            f"ERROR: remote packages missing under {remote_root}/{ver}/ "
            f"(run --upload first). sample={remote_sample} size={sz}",
            file=sys.stderr,
        )
        return 1
    if not SERVE_SCRIPT_LOCAL.is_file():
        print(f"missing {SERVE_SCRIPT_LOCAL}", file=sys.stderr)
        return 1
    home = "/root" if user == "root" else f"/home/{user}"
    tmp_serve = f"{home}/serve_paid_assets.py"
    _scp_put_file(
        SERVE_SCRIPT_LOCAL, tmp_serve, host=host, user=user, key_path=key_path
    )
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
    import base64

    b64 = base64.b64encode(unit.encode("utf-8")).decode("ascii")
    code, out = _ssh_run_openssh(
        f"set -e; "
        f"mv -f {tmp_serve} {SERVE_SCRIPT_REMOTE}; "
        f"chmod +x {SERVE_SCRIPT_REMOTE}; "
        f"echo {b64} | base64 -d > /tmp/{UNIT_NAME}; "
        f"mv /tmp/{UNIT_NAME} /etc/systemd/system/{UNIT_NAME}; "
        f"systemctl daemon-reload; "
        f"systemctl enable {UNIT_NAME}; "
        f"systemctl restart {UNIT_NAME}; "
        f"systemctl is-active {UNIT_NAME}",
        host=host,
        user=user,
        key_path=key_path,
        sudo=True,
    )
    if code != 0:
        print(f"ERROR install-serve failed: {out}", file=sys.stderr)
        return 1
    print(f"serve: http://{host}:{port}{VPS_ASSET_HTTP_PREFIX}/{{version}}/{{file}}")
    print("Render env: RPT_VPS_ASSET_BASE + RPT_ASSET_FETCH_TOKEN")
    print(f"token_len={len(token)}")
    print(f"install-serve complete host={host} version={ver}")
    return 0


def upload_packages(
    *,
    version: str | None = None,
    dry_run: bool = False,
    install_serve: bool = False,
    force: bool = False,
) -> int:
    pkgs = list_packages(version)
    ver = pkgs[0]["version"]
    local_dir = STATUS / "assets" / ver
    remote_root = os.environ.get(
        "RPT_VPS_ASSET_REMOTE_ROOT", DEFAULT_VPS_ASSET_REMOTE_ROOT
    ).strip() or DEFAULT_VPS_ASSET_REMOTE_ROOT
    remote_ver = f"{remote_root.rstrip('/')}/{ver}"
    host_default = DEFAULT_VPS_ASSET_HOST

    print(f"upload plan: {len(pkgs)} files -> {host_default}:{remote_ver}/")
    for p in pkgs:
        print(f"  {p['platform']}: {p['filename']}")

    if dry_run:
        print("dry-run: no SSH")
        return 0

    for p in pkgs:
        f = local_dir / p["filename"]
        if not f.is_file() or f.stat().st_size < 1_000_000:
            print(f"missing or tiny local stage: {f}", file=sys.stderr)
            print("Run with --stage first.", file=sys.stderr)
            return 1
        if p["platform"] == "macos":
            try:
                _assert_macos_cfbundle(f, ver)
            except (RuntimeError, FileNotFoundError, ValueError) as e:
                print(f"ERROR: {e}", file=sys.stderr)
                return 1

    host, user, password, key_path = _ssh_target()
    use_openssh = (
        password is None and key_path is not None and _openssh_available()
    )

    if use_openssh:
        assert key_path is not None
        print(f"transport=openssh key={key_path}")
        code, _ = _ssh_run_openssh(
            f"mkdir -p {remote_ver} && chown -R {user}:{user} {remote_root}",
            host=host,
            user=user,
            key_path=key_path,
            sudo=True,
        )
        if code != 0:
            print("ERROR: could not prepare remote paid_assets dir", file=sys.stderr)
            return 1
        for p in pkgs:
            local = local_dir / p["filename"]
            remote = f"{remote_ver}/{p['filename']}"
            print(
                f"upload platform={p['platform']} file={p['filename']} "
                f"({local.stat().st_size} bytes)"
            )
            try:
                _upload_one_installer_openssh(
                    local,
                    remote,
                    host=host,
                    user=user,
                    key_path=key_path,
                    skip_if_present=not force,
                )
            except Exception as e:  # noqa: BLE001
                print(f"ERROR platform={p['platform']}: {e}", file=sys.stderr)
                return 1
        if install_serve:
            if not SERVE_SCRIPT_LOCAL.is_file():
                print(f"missing {SERVE_SCRIPT_LOCAL}", file=sys.stderr)
                return 1
            home = "/root" if user == "root" else f"/home/{user}"
            tmp_serve = f"{home}/serve_paid_assets.py"
            _scp_put_file(
                SERVE_SCRIPT_LOCAL,
                tmp_serve,
                host=host,
                user=user,
                key_path=key_path,
            )
            token = os.environ.get("RPT_ASSET_FETCH_TOKEN", "").strip()
            if not token:
                token = secrets.token_urlsafe(32)
                print(
                    f"generated RPT_ASSET_FETCH_TOKEN (set on Render too): {token}",
                    file=sys.stderr,
                )
            port = os.environ.get(
                "RPT_VPS_ASSET_PORT", str(DEFAULT_VPS_ASSET_PORT)
            ).strip()
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
            import base64

            b64 = base64.b64encode(unit.encode("utf-8")).decode("ascii")
            code, out = _ssh_run_openssh(
                f"set -e; "
                f"mv -f {tmp_serve} {SERVE_SCRIPT_REMOTE}; "
                f"chmod +x {SERVE_SCRIPT_REMOTE}; "
                f"echo {b64} | base64 -d > /tmp/{UNIT_NAME}; "
                f"mv /tmp/{UNIT_NAME} /etc/systemd/system/{UNIT_NAME}; "
                f"systemctl daemon-reload; "
                f"systemctl enable {UNIT_NAME}; "
                f"systemctl restart {UNIT_NAME}; "
                f"systemctl is-active {UNIT_NAME}",
                host=host,
                user=user,
                key_path=key_path,
                sudo=True,
            )
            if code != 0:
                print(f"ERROR install-serve failed: {out}", file=sys.stderr)
                return 1
            print(
                f"serve: http://{host}:{port}{VPS_ASSET_HTTP_PREFIX}/{{version}}/{{file}}"
            )
            print("Render env: RPT_VPS_ASSET_BASE + RPT_ASSET_FETCH_TOKEN")
            print(f"token_len={len(token)}")
        print(f"upload complete host={host} version={ver}")
        return 0

    # Password / paramiko fallback path
    client, host, user = _ssh_connect()
    use_sudo = _want_sudo(user)
    try:
        _run(client, f"mkdir -p {remote_ver}", sudo=use_sudo, user=user)
        if use_sudo:
            _run(
                client,
                f"chown -R {user}:{user} {remote_root}",
                sudo=True,
                user=user,
            )
        for p in pkgs:
            local = local_dir / p["filename"]
            remote = f"{remote_ver}/{p['filename']}"
            print(
                f"upload platform={p['platform']} file={p['filename']} "
                f"({local.stat().st_size} bytes)"
            )
            sftp = client.open_sftp()
            try:
                sftp.put(str(local), remote)
                st = sftp.stat(remote)
                if st.st_size != local.stat().st_size:
                    print(
                        f"ERROR size mismatch remote={st.st_size} local={local.stat().st_size}",
                        file=sys.stderr,
                    )
                    return 1
                print(f"  remote_ok {p['platform']} bytes={st.st_size}")
            finally:
                sftp.close()
        if install_serve:
            print(
                "install-serve requires OpenSSH key path in this build; "
                "re-run with RPT_SSH_KEY set",
                file=sys.stderr,
            )
            return 1
        print(f"upload complete host={host} version={ver}")
        return 0
    finally:
        client.close()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=(
            "Stage per-device installers and host them on the Helsinki paid store "
            "(not the Iceland residual node)"
        )
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
        help="Upload staged packages to Helsinki paid_assets path",
    )
    ap.add_argument(
        "--install-serve",
        action="store_true",
        help="Install/restart token-gated HTTP serve on store host (with --upload)",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="With --upload or --remove-iceland-paid-assets: print plan only (no SSH)",
    )
    ap.add_argument(
        "--force",
        action="store_true",
        help="Re-upload even when remote size already matches local",
    )
    ap.add_argument(
        "--install-serve-only",
        action="store_true",
        help="Only install/restart the token-gated store HTTP serve (no package upload)",
    )
    ap.add_argument(
        "--remove-iceland-paid-assets",
        action="store_true",
        help=(
            "On Iceland residual host: stop/disable rpt-paid-assets and delete "
            "/opt/restore-privacy/paid_assets only (node-only cleanup)"
        ),
    )
    args = ap.parse_args(argv)
    ver = (args.version or "").strip() or None

    if args.remove_iceland_paid_assets:
        return remove_iceland_paid_assets(dry_run=args.dry_run)

    if args.install_serve_only:
        return install_serve_only(version=ver)

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
            version=ver,
            dry_run=args.dry_run,
            install_serve=args.install_serve,
            force=args.force,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
