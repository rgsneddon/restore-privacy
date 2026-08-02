#!/usr/bin/env python3
"""Package and (re)deploy perc_chain internet node for Helsinki / any host.

Restore Privacy Suite v1.0.5 — evolve-perc-internet (Render) is **paused to
save money**. Default public endpoint is Helsinki ``135.181.152.10:9478``.

Dry-run and local package production work without SSH. Live upload is optional
when keys exist.

Usage::

  python3 scripts/deploy_perc_chain_helsinki.py --package --dry-run
  python3 scripts/deploy_perc_chain_helsinki.py --local-run --port 9478
  python3 scripts/deploy_perc_chain_helsinki.py --package --upload --install-service
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHAIN_SRC = ROOT / "perc_chain"
DEFAULT_HOST = "135.181.152.10"
DEFAULT_PORT = 9478
DEFAULT_REMOTE_ROOT = "/opt/restore-privacy/perc_chain"
UNIT_NAME = "rpt-perc-chain.service"
SUITE_VERSION = "1.0.5"
PAUSED_RENDER = "evolve-perc-internet.onrender.com"

# evolve-perc-internet (Render) is paused to save money — never default to it.
# Public path is nginx /perc on sslip.io (cloud firewall blocks raw :9478).
DEFAULT_PUBLIC_ENDPOINT = f"https://{DEFAULT_HOST}.sslip.io/perc"


def _stage_dir(out: Path) -> Path:
    """Copy chain sources into a stage tree (no node_modules / data)."""
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    for name in (
        "package.json",
        "package-lock.json",
        "Dockerfile",
        "src",
        "public",
        "fixtures",
        "deploy",
        "DEPLOY_HELSINKI.md",
    ):
        src = CHAIN_SRC / name
        if not src.exists():
            continue
        dest = out / name
        if src.is_dir():
            shutil.copytree(src, dest)
        else:
            shutil.copy2(src, dest)
    env = out / "helsinki.env"
    env.write_text(
        "\n".join(
            [
                f"# Restore Privacy Suite v{SUITE_VERSION}",
                f"# {PAUSED_RENDER} is paused to save money.",
                f"PORT={DEFAULT_PORT}",
                f"PERC_RENDEZVOUS_PORT={DEFAULT_PORT}",
                "PERC_BIND_HOST=127.0.0.1",
                f"PERC_DATA_DIR={DEFAULT_REMOTE_ROOT}/data",
                f"PERC_PUBLIC_ENDPOINT={DEFAULT_PUBLIC_ENDPOINT}",
                "PERC_UPSTREAM_RENDEZVOUS_URL=https://evolve-perc-internet.onrender.com",
                "PERC_SEED_USERNAME=evolve_seed_node",
                "PERC_CHAIN_GENESIS_REVISION=2",
                "NODE_ENV=production",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return out


def package_tarball(dest: Path | None = None) -> Path:
    """Build installable tarball under dist/ (or [dest])."""
    dist = dest or (ROOT / "dist" / "suite" / SUITE_VERSION)
    dist.mkdir(parents=True, exist_ok=True)
    tarball = dist / f"rpt-perc-chain-{SUITE_VERSION}-helsinki.tar.gz"
    with tempfile.TemporaryDirectory(prefix="rpt-perc-chain-") as tmp:
        stage = _stage_dir(Path(tmp) / "perc_chain")
        with tarfile.open(tarball, "w:gz") as tar:
            tar.add(stage, arcname="perc_chain")
    meta = {
        "product": "Restore Privacy Suite",
        "version": SUITE_VERSION,
        "component": "perc_chain",
        "host_default": DEFAULT_HOST,
        "port": DEFAULT_PORT,
        "public_endpoint": DEFAULT_PUBLIC_ENDPOINT,
        "paused_render": PAUSED_RENDER,
        "paused_note": "evolve-perc-internet is paused to save money",
        "tarball": str(tarball.name),
        "remote_root": DEFAULT_REMOTE_ROOT,
    }
    (dist / "perc_chain_package.json").write_text(
        json.dumps(meta, indent=2) + "\n", encoding="utf-8"
    )
    print(f"package={tarball}")
    print(f"meta={dist / 'perc_chain_package.json'}")
    return tarball


def dry_run_plan() -> dict:
    plan = {
        "action": "deploy_perc_chain_helsinki",
        "suite_version": SUITE_VERSION,
        "source": str(CHAIN_SRC),
        "remote_host": os.environ.get("RPT_SSH_HOST", DEFAULT_HOST),
        "remote_root": DEFAULT_REMOTE_ROOT,
        "public_endpoint": DEFAULT_PUBLIC_ENDPOINT,
        "unit": UNIT_NAME,
        "paused_render": PAUSED_RENDER,
        "note": "evolve-perc-internet is paused to save money",
        "ssh_required_for_upload": True,
        "local_package_ok_without_ssh": True,
    }
    print(json.dumps(plan, indent=2))
    return plan


def local_run(port: int = DEFAULT_PORT, timeout_s: float = 25.0) -> dict:
    """Start internet node on loopback and assert /health."""
    if not (CHAIN_SRC / "src" / "internet_node.js").is_file():
        raise SystemExit(f"missing chain source: {CHAIN_SRC}")
    data_dir = ROOT / "dist" / "suite" / SUITE_VERSION / "perc_chain_local_data"
    data_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update(
        {
            "PORT": str(port),
            "PERC_RENDEZVOUS_PORT": str(port),
            "PERC_BIND_HOST": "127.0.0.1",
            "PERC_DATA_DIR": str(data_dir),
            "PERC_PUBLIC_ENDPOINT": f"http://127.0.0.1:{port}",
            "PERC_SEED_USERNAME": "evolve_seed_node",
            "PERC_CHAIN_GENESIS_REVISION": "2",
        }
    )
    proc = subprocess.Popen(
        [sys.executable and "node", "src/internet_node.js"],
        cwd=str(CHAIN_SRC),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    health_url = f"http://127.0.0.1:{port}/health"
    deadline = time.time() + timeout_s
    last_err: str | None = None
    body: dict | None = None
    try:
        while time.time() < deadline:
            if proc.poll() is not None:
                out = proc.stdout.read() if proc.stdout else ""
                raise SystemExit(f"perc_chain exited early rc={proc.returncode}\n{out}")
            try:
                with urllib.request.urlopen(health_url, timeout=2) as resp:
                    body = json.loads(resp.read().decode("utf-8"))
                    break
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
                last_err = str(e)
                time.sleep(0.4)
        if body is None:
            raise SystemExit(f"health timeout: {last_err}")
        if not body.get("ok"):
            raise SystemExit(f"health not ok: {body}")
        result = {
            "ok": True,
            "health": body,
            "url": health_url,
            "public_endpoint_default": DEFAULT_PUBLIC_ENDPOINT,
            "paused_render": PAUSED_RENDER,
            "suite_version": SUITE_VERSION,
        }
        print(json.dumps(result, indent=2))
        return result
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def _ssh_base() -> list[str]:
    host = os.environ.get("RPT_SSH_HOST", DEFAULT_HOST)
    user = os.environ.get("RPT_SSH_USER", "root")
    key = os.environ.get("RPT_SSH_KEY", "").strip()
    cmd = ["ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=accept-new"]
    if key:
        cmd.extend(["-i", os.path.expanduser(key)])
    cmd.append(f"{user}@{host}")
    return cmd


def upload_and_install(tarball: Path, install_service: bool) -> None:
    host = os.environ.get("RPT_SSH_HOST", DEFAULT_HOST)
    user = os.environ.get("RPT_SSH_USER", "root")
    key = os.environ.get("RPT_SSH_KEY", "").strip()
    scp = ["scp", "-o", "BatchMode=yes"]
    if key:
        scp.extend(["-i", os.path.expanduser(key)])
    remote_tar = f"/tmp/{tarball.name}"
    scp.extend([str(tarball), f"{user}@{host}:{remote_tar}"])
    print("scp:", " ".join(scp))
    subprocess.check_call(scp)
    # Extract package sources without wiping durable ledger under data/.
    # Tarball has no data/ entries; never rm -rf data or the chain restarts from genesis.
    remote_cmds = [
        f"mkdir -p {DEFAULT_REMOTE_ROOT}",
        f"mkdir -p {DEFAULT_REMOTE_ROOT}/data",
        # Snapshot ledger path before extract (safety if a future package ships data/)
        f"if [ -f {DEFAULT_REMOTE_ROOT}/data/seed_ledger.json ]; then "
        f"cp -a {DEFAULT_REMOTE_ROOT}/data/seed_ledger.json "
        f"{DEFAULT_REMOTE_ROOT}/data/seed_ledger.json.pre_deploy; fi",
        f"tar -xzf {remote_tar} -C /opt/restore-privacy --strip-components=0",
        # Restore durable ledger if extract ever clobbered it
        f"if [ ! -s {DEFAULT_REMOTE_ROOT}/data/seed_ledger.json ] && "
        f"[ -s {DEFAULT_REMOTE_ROOT}/data/seed_ledger.json.pre_deploy ]; then "
        f"mv -f {DEFAULT_REMOTE_ROOT}/data/seed_ledger.json.pre_deploy "
        f"{DEFAULT_REMOTE_ROOT}/data/seed_ledger.json; fi",
        f"mkdir -p {DEFAULT_REMOTE_ROOT}/data",
        f"cd {DEFAULT_REMOTE_ROOT} && (test -f package-lock.json && npm ci --omit=dev || npm install --omit=dev)",
        f"test -f {DEFAULT_REMOTE_ROOT}/helsinki.env || true",
    ]
    if install_service:
        remote_cmds.extend(
            [
                f"cp -f {DEFAULT_REMOTE_ROOT}/deploy/rpt-perc-chain.service /etc/systemd/system/{UNIT_NAME}",
                "systemctl daemon-reload",
                f"systemctl enable {UNIT_NAME}",
                # Ensure suite store + reverse proxy also boot with the host.
                "systemctl enable nginx.service 2>/dev/null || true",
                "systemctl enable rpt-paid-assets.service 2>/dev/null || true",
                f"systemctl restart {UNIT_NAME}",
                f"systemctl --no-pager --full status {UNIT_NAME} || true",
                f"systemctl is-enabled {UNIT_NAME}",
                f"systemctl is-active {UNIT_NAME}",
                f"curl -fsS {DEFAULT_PUBLIC_ENDPOINT}/health || curl -fsS http://127.0.0.1:{DEFAULT_PORT}/health || true",
            ]
        )
    ssh = _ssh_base() + [" && ".join(remote_cmds)]
    print("ssh remote install…")
    subprocess.check_call(ssh)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--package", action="store_true", help="Build tarball under dist/suite/1.0.0")
    p.add_argument("--dry-run", action="store_true", help="Print plan only (no SSH)")
    p.add_argument("--local-run", action="store_true", help="Run node locally and hit /health")
    p.add_argument("--port", type=int, default=DEFAULT_PORT)
    p.add_argument("--upload", action="store_true", help="SCP tarball to Helsinki (needs SSH)")
    p.add_argument(
        "--install-service",
        action="store_true",
        help="With --upload: install systemd unit and start",
    )
    args = p.parse_args(argv)

    if not CHAIN_SRC.is_dir():
        print(f"ERROR: missing {CHAIN_SRC}", file=sys.stderr)
        return 2

    if args.dry_run and not args.package and not args.local_run:
        dry_run_plan()
        return 0

    tarball: Path | None = None
    if args.package or args.upload:
        if args.dry_run:
            dry_run_plan()
            print(f"would_package_from={CHAIN_SRC}")
            print(f"would_write=dist/suite/{SUITE_VERSION}/rpt-perc-chain-{SUITE_VERSION}-helsinki.tar.gz")
            return 0
        tarball = package_tarball()

    if args.local_run:
        local_run(port=args.port)
        return 0

    if args.upload:
        if tarball is None:
            tarball = package_tarball()
        try:
            upload_and_install(tarball, install_service=args.install_service)
        except (subprocess.CalledProcessError, FileNotFoundError, OSError) as e:
            print(f"SSH upload skipped/failed (local package still valid): {e}", file=sys.stderr)
            print("ssh_absent_or_failed=1")
            return 0

    if not (args.package or args.dry_run or args.local_run or args.upload):
        p.print_help()
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
