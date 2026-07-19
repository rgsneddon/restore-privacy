#!/usr/bin/env python3
"""Stage a Linux Mint-compatible source tarball for Restore Privacy."""

from __future__ import annotations

import hashlib
import shutil
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = (ROOT / "client" / "VERSION").read_text(encoding="utf-8").strip()
OUT = ROOT / "releases" / VERSION
NAME = f"restore-privacy-client-{VERSION}-linux-x64.tar.gz"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    dest = OUT / NAME
    with tempfile.TemporaryDirectory() as td:
        stage = Path(td) / f"restore-privacy-{VERSION}-linux"
        stage.mkdir()
        ignore = shutil.ignore_patterns(
            "__pycache__",
            "*.pyc",
            "windows",
            "native",
            "*.dll",
            "*.priv",
        )
        for rel in ("client", "node", "requirements.txt", "README.md", "PRIVACY_POLICY.md", "LICENSE"):
            src = ROOT / rel
            if not src.exists():
                continue
            dst = stage / rel
            if src.is_dir():
                shutil.copytree(src, dst, ignore=ignore, dirs_exist_ok=True)
            else:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)

        sec = stage / "secrets"
        sec.mkdir(exist_ok=True)
        pub = ROOT / "secrets" / "node_elgamal.pub"
        if pub.is_file():
            shutil.copy2(pub, sec / "node_elgamal.pub")

        for script_name in (
            "install_linux_ubuntu.sh",
            "install_linux_mint.sh",
        ):
            inst = ROOT / "scripts" / script_name
            if inst.is_file():
                shutil.copy2(inst, stage / script_name)

        (stage / "LINUX_UBUNTU.md").write_text(
            f"""# Restore Privacy {VERSION} - Ubuntu family

## Supported
- **Ubuntu 20.04 LTS and newer** (22.04, 24.04, …)
- Derivatives: **Linux Mint**, Pop!_OS, elementary OS, Kubuntu, Xubuntu, …
- Python **3.8+**, ``iproute2``, kernel TUN

EOL Ubuntu (16.04/18.04) is not guaranteed.

## Requirements
- python3, python3-tk, **python3-cryptography** (or ``pip install -r requirements.txt``)
- **iproute2** (``ip`` command)
- root (sudo/pkexec) for full-tunnel residual public IP

## Install
```bash
bash install_linux_ubuntu.sh
# or (same recipe):
bash install_linux_mint.sh
```
Installs ``python3-tk``, ``python3-cryptography``, ``iproute2``, and handles
Ubuntu 24.04 pip externally-managed environments when needed.

## Run
```bash
cd restore-privacy-{VERSION}-linux
sudo PYTHONPATH=. python3 -m client.linux
```

Press **Connect**. Residual public IP uses the VPN node only when TUN + dual /1
routes are active. **Disconnect** tears down routes and the session.
""",
            encoding="utf-8",
        )
        # Keep historical name pointing at Ubuntu doc
        (stage / "LINUX_MINT.md").write_text(
            f"See LINUX_UBUNTU.md — Mint uses the same install as Ubuntu {VERSION}.\n",
            encoding="utf-8",
        )

        # Refuse if any .priv slipped in
        for p in stage.rglob("*.priv"):
            raise RuntimeError(f"refusing private key in package: {p}")

        if dest.exists():
            dest.unlink()
        with tarfile.open(dest, "w:gz") as tf:
            tf.add(stage, arcname=stage.name)

    print(f"linux package: {dest} ({dest.stat().st_size} bytes)")
    print(f"sha256: {sha256_file(dest)}")
    return 0 if dest.is_file() and dest.stat().st_size > 1000 else 1


if __name__ == "__main__":
    raise SystemExit(main())
