#!/usr/bin/env python3
"""Stage a Linux x64 installer package with app Python deps baked in.

Produces:
  releases/<version>/restore-privacy-client-<version>-linux-x64.tar.gz

Layout inside the archive:
  restore-privacy-<version>-linux/
    client/ node/ secrets/ requirements.txt
    wheels/          # manylinux cryptography + deps (offline pip)
    install.sh       # creates private .venv from wheels, desktop launcher
    bin/privacy-restored  # launcher using .venv after install
    LINUX_INSTALL.md

Users do not need ``pip install cryptography`` or ``apt install python3-cryptography``
for the app library stack — install.sh uses only the bundled wheels.

Remaining host OS floor (not baked): python3, python3-venv, python3-tk, iproute2, TUN, root.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path
from typing import List

ROOT = Path(__file__).resolve().parents[1]


def _resolve_package_version() -> tuple[str, bool, Path, str]:
    """Return (version, free_tier, out_dir, archive_filename).

    Free tier (``RPT_FREE_TIER=1``): permanent pin **3.3.3**, output under
    ``releases/free/3.3.3/`` with free naming. Optional ``RPT_PRODUCT_VERSION``
    overrides the paid pin only (not free).
    """
    free = (os.environ.get("RPT_FREE_TIER") or "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
        "free",
    )
    if free:
        ver = "3.3.3"
        out = ROOT / "releases" / "free" / ver
        name = f"restore-privacy-client-free-{ver}-linux-x64.tar.gz"
        return ver, True, out, name
    paid_pin = (ROOT / "client" / "VERSION").read_text(encoding="utf-8").strip()
    ver = (os.environ.get("RPT_PRODUCT_VERSION") or paid_pin).strip() or paid_pin
    out = ROOT / "releases" / ver
    name = f"restore-privacy-client-{ver}-linux-x64.tar.gz"
    return ver, False, out, name


VERSION, FREE_TIER, OUT, NAME = _resolve_package_version()

# manylinux tags + CPython versions covered by Ubuntu 20.04–24.04 (3.8–3.12)
_PY_VERSIONS = ("38", "39", "310", "311", "312")
_PLATFORMS = (
    "manylinux2014_x86_64",
    "manylinux_2_17_x86_64",
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download_linux_wheels(dest: Path) -> List[Path]:
    """Download manylinux wheels for requirements into ``dest`` (offline install)."""
    dest.mkdir(parents=True, exist_ok=True)
    req = ROOT / "requirements.txt"
    # Pin a known-good crypto range that has broad manylinux abi3 wheels
    specs = [
        "cryptography>=41,<46",
        "cffi>=1.14",
        "pycparser",
    ]
    if req.is_file():
        # Prefer reading requirements.txt but keep cffi/pycparser explicit
        text = req.read_text(encoding="utf-8")
        for line in text.splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "cryptography" not in line.lower():
                specs.append(line)

    env = os.environ.copy()
    # Avoid user site noise
    env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"

    errors: List[str] = []
    ok_any = False
    for pyver in _PY_VERSIONS:
        for plat in _PLATFORMS:
            cmd = [
                sys.executable,
                "-m",
                "pip",
                "download",
                *specs,
                "-d",
                str(dest),
                "--only-binary=:all:",
                "--python-version",
                pyver,
                "--platform",
                plat,
                "--implementation",
                "cp",
            ]
            r = subprocess.run(
                cmd,
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                env=env,
                timeout=300,
            )
            if r.returncode == 0:
                ok_any = True
                # Keep trying more py versions so multi-LTS cffi tags accumulate
                break
            errors.append(f"py{pyver}/{plat}: {(r.stderr or r.stdout or '')[-300:]}")

    # Also grab pure-python / abi3-friendly tags with a looser platform once
    if not ok_any:
        cmd = [
            sys.executable,
            "-m",
            "pip",
            "download",
            "cryptography>=41,<46",
            "cffi",
            "pycparser",
            "-d",
            str(dest),
            "--only-binary=:all:",
            "--python-version",
            "39",
            "--platform",
            "manylinux2014_x86_64",
            "--implementation",
            "cp",
        ]
        r = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, env=env, timeout=300)
        if r.returncode != 0:
            raise RuntimeError(
                "Failed to download manylinux wheels.\n" + "\n".join(errors[-8:])
            )

    wheels = sorted(dest.glob("*.whl"))
    crypto = [
        w
        for w in wheels
        if w.name.startswith("cryptography-") and "manylinux" in w.name
    ]
    if not crypto:
        raise RuntimeError(
            "Failed to download manylinux cryptography wheels. "
            f"Last errors:\n" + "\n".join(errors[-6:])
        )
    cffi = [w for w in wheels if w.name.startswith("cffi-")]
    if not cffi:
        raise RuntimeError("Failed to download cffi wheels for Linux")
    return wheels


def write_install_sh(stage: Path) -> None:
    """Offline installer: private venv from bundled wheels + launcher.

    Default: install in the extracted package directory (portable).
    System layout: ``RPT_SYSTEM_INSTALL=1`` as root → ``/opt/restore-privacy``
    (see ``client.install_paths.default_linux_install_dir``).
    Bundle always includes ``Restore Internet`` failsafe next to the client launcher.
    """
    content = r'''#!/usr/bin/env bash
# Restore Privacy Linux installer — uses BUNDLED wheels only (no network pip).
# Remaining system packages (python3, venv, tk, ip): installed via apt if missing.
# Standard system path: RPT_SYSTEM_INSTALL=1 sudo bash install.sh → /opt/restore-privacy
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
VENV="$ROOT/.venv"
WHEELS="$ROOT/wheels"
REQ="$ROOT/requirements.txt"

echo "=== Restore Privacy Linux installer (deps baked in) ==="
echo "Package root: $ROOT"
# Standard system install root (optional): /opt/restore-privacy when run as root
# with RPT_SYSTEM_INSTALL=1; default remains this portable package directory.
if [[ "${RPT_SYSTEM_INSTALL:-}" == "1" ]] && [[ "$(id -u)" -eq 0 ]]; then
  SYS_ROOT="${RPT_INSTALL_DIR:-/opt/restore-privacy}"
  echo "System install mode → $SYS_ROOT"
  mkdir -p "$SYS_ROOT"
  # shellcheck disable=SC2086
  cp -a "$ROOT"/. "$SYS_ROOT"/ 2>/dev/null || true
  ROOT="$SYS_ROOT"
  VENV="$ROOT/.venv"
  WHEELS="$ROOT/wheels"
  REQ="$ROOT/requirements.txt"
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 is required (Ubuntu 20.04+). sudo apt-get install -y python3"
  exit 1
fi

PY_OK="$(python3 -c 'import sys; print(1 if sys.version_info >= (3, 8) else 0)')"
if [[ "$PY_OK" != "1" ]]; then
  echo "ERROR: Need Python 3.8+ (Ubuntu 20.04 LTS or newer)."
  exit 1
fi

# System floor only — app deps come from wheels/
need_apt=0
command -v ip >/dev/null 2>&1 || need_apt=1
python3 -c "import venv" 2>/dev/null || need_apt=1
python3 -c "import tkinter" 2>/dev/null || need_apt=1
if [[ "$need_apt" -eq 1 ]]; then
  if command -v apt-get >/dev/null 2>&1; then
    echo "Installing system packages: python3-venv python3-tk iproute2..."
    sudo apt-get update -y
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
      python3-venv python3-tk iproute2 || true
  fi
fi

if ! python3 -c "import venv" 2>/dev/null; then
  echo "ERROR: python3-venv missing. sudo apt-get install -y python3-venv"
  exit 1
fi
if ! python3 -c "import tkinter" 2>/dev/null; then
  echo "ERROR: python3-tk missing (GUI). sudo apt-get install -y python3-tk"
  exit 1
fi
if ! command -v ip >/dev/null 2>&1; then
  echo "ERROR: ip (iproute2) missing. sudo apt-get install -y iproute2"
  exit 1
fi

if [[ ! -d "$WHEELS" ]] || ! ls "$WHEELS"/*.whl >/dev/null 2>&1; then
  echo "ERROR: bundled wheels/ missing — corrupt package. Re-download the release tar.gz."
  exit 1
fi

echo "Creating private virtualenv at $VENV (offline install from wheels/)..."
rm -rf "$VENV"
python3 -m venv "$VENV"
# shellcheck disable=SC1091
source "$VENV/bin/activate"
python -m pip install --upgrade pip --no-index --find-links="$WHEELS" 2>/dev/null || true
# Offline only — never hits PyPI
if [[ -f "$REQ" ]]; then
  python -m pip install --no-index --find-links="$WHEELS" -r "$REQ"
else
  python -m pip install --no-index --find-links="$WHEELS" cryptography cffi pycparser
fi

# Verify cryptography from venv (not system)
python -c "import cryptography; print('cryptography', cryptography.__version__, 'OK (bundled)')"

# Secrets (entry + exit pubs for multi-hop residual; never private keys)
SECRETS_DIR="${HOME}/.restore-privacy/secrets"
mkdir -p "$SECRETS_DIR"
for pub in node_elgamal.pub exit_node_elgamal.pub us_node_elgamal.pub; do
  if [[ -f "$ROOT/product/$pub" ]]; then
    cp -f "$ROOT/product/$pub" "$SECRETS_DIR/"
    echo "Installed $pub from product/ to $SECRETS_DIR"
  elif [[ -f "$ROOT/secrets/$pub" ]]; then
    cp -f "$ROOT/secrets/$pub" "$SECRETS_DIR/"
    echo "Installed $pub from secrets/ to $SECRETS_DIR"
  fi
done

# Ensure launcher is executable
chmod +x "$ROOT/bin/privacy-restored" 2>/dev/null || true
chmod +x "$ROOT/bin/restore-internet" 2>/dev/null || true
chmod +x "$ROOT/Restore Internet" 2>/dev/null || true
chmod +x "$ROOT/install.sh" 2>/dev/null || true

# Desktop entry → bundled launcher
APPS="${HOME}/.local/share/applications"
mkdir -p "$APPS"
cat > "$APPS/privacy-restored.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Privacy Restored
Comment=Restore Privacy VPN (Linux installer package)
Exec=pkexec env DISPLAY=\$DISPLAY XAUTHORITY=\$XAUTHORITY $ROOT/bin/privacy-restored
Path=$ROOT
Terminal=false
Categories=Network;Security;
EOF
echo "Desktop entry: $APPS/privacy-restored.desktop"

# Restore Internet failsafe (network restore + uninstall)
cat > "$APPS/restore-internet.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Restore Internet
Comment=WARNING: erases ALL Restore Privacy; contact rus@restoreprivacy.online for a new download link
Exec=pkexec env DISPLAY=\$DISPLAY XAUTHORITY=\$XAUTHORITY bash "$ROOT/Restore Internet"
Path=$ROOT
Terminal=true
Categories=Network;Security;
EOF
echo "Failsafe desktop entry: $APPS/restore-internet.desktop"

if [[ ! -e /dev/net/tun ]]; then
  echo "Loading tun module..."
  sudo modprobe tun || true
fi

echo ""
echo "Install complete. App Python deps are in $VENV (from bundled wheels)."
echo "  Run GUI (root for full tunnel):"
echo "    sudo $ROOT/bin/privacy-restored"
echo "  Or: $ROOT/bin/privacy-restored   # will request elevation on Connect"
'''
    (stage / "install.sh").write_text(content.replace("\r\n", "\n"), encoding="utf-8")


def write_launcher(stage: Path, *, free_tier: bool = False) -> None:
    bin_dir = stage / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    launcher = bin_dir / "privacy-restored"
    free_exports = ""
    if free_tier:
        free_exports = (
            "export RPT_FREE_TIER=1\n"
            "export RPT_PRODUCT_VERSION=3.3.3\n"
            "# Free 3.3.3: lean Iceland residual; privacy-scale Settings locked off\n"
            "export RPT_TRAFFIC_SHAPE=0\n"
            "export RPT_OBFS=0\n"
            "export RPT_MULTIHOP_ENABLED=0\n"
        )
    launcher.write_text(
        f"""#!/usr/bin/env bash
# Launch Restore Privacy using the private venv created by install.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV_PY="$ROOT/.venv/bin/python"
if [[ ! -x "$VENV_PY" ]]; then
  echo "Private venv missing. Run once: bash $ROOT/install.sh" >&2
  exit 1
fi
export PYTHONPATH="$ROOT${{PYTHONPATH:+:$PYTHONPATH}}"
{free_exports}cd "$ROOT"
exec "$VENV_PY" -m client.linux "$@"
""".replace(
            "\r\n", "\n"
        ),
        encoding="utf-8",
    )


def write_restore_internet(stage: Path) -> None:
    """Ship user-facing Restore Internet failsafe (residual restore + uninstall)."""
    src = ROOT / "client" / "linux" / "Restore Internet"
    dest = stage / "Restore Internet"
    if src.is_file():
        shutil.copy2(src, dest)
    else:
        dest.write_text(
            "#!/usr/bin/env bash\n"
            "echo 'Restore Internet failsafe missing from package sources.'\n"
            "exit 1\n",
            encoding="utf-8",
        )
    dest.chmod(dest.stat().st_mode | 0o111)
    # Symlink-friendly name without spaces for scripts
    alias = stage / "bin" / "restore-internet"
    alias.parent.mkdir(parents=True, exist_ok=True)
    alias.write_text(
        "#!/usr/bin/env bash\n"
        'exec bash "$(cd "$(dirname "$0")/.." && pwd)/Restore Internet" "$@"\n',
        encoding="utf-8",
    )
    alias.chmod(alias.stat().st_mode | 0o111)
    # Desktop entry for discoverability
    desk = stage / "Restore Internet.desktop"
    desk.write_text(
        f"""[Desktop Entry]
Type=Application
Name=Restore Internet
Comment=WARNING: erases ALL Restore Privacy; contact rus@restoreprivacy.online for a new download link
Exec=pkexec env DISPLAY=$DISPLAY XAUTHORITY=$XAUTHORITY bash "{stage.name}/Restore Internet"
Terminal=true
Categories=Network;Security;
""",
        encoding="utf-8",
    )


def write_docs(stage: Path) -> None:
    (stage / "LINUX_INSTALL.md").write_text(
        f"""# Restore Privacy {VERSION} — Linux installer package

## What is baked in
- Client + node modules
- **manylinux wheels** for `cryptography` (+ `cffi`, `pycparser`) under `wheels/`
- Offline installer `install.sh` that creates a **private** `.venv` from those wheels
- Launcher `bin/privacy-restored` that always uses that venv

You do **not** need `apt install python3-cryptography` or network `pip install`
for the app’s Python crypto stack.

### Supported wheeled Python ABIs (x86_64)
The packager downloads **manylinux2014 / manylinux_2_17** wheels for **CPython 3.8, 3.9, 3.10, 3.11, and 3.12**
(see ``_PY_VERSIONS`` / ``_PLATFORMS`` in ``scripts/package_linux.py``).
``cryptography`` is typically **abi3** (one wheel covers many Python versions);
``cffi`` is often **version-specific** — the archive includes multiple ``cp3x`` tags when available.

**Publishers:** re-run ``python scripts/package_linux.py`` on **every** release so wheels
match current PyPI tags. Do not reuse an old ``wheels/`` directory across major crypto upgrades.

## Still provided by the OS
- `python3` + `python3-venv` + `python3-tk` (GUI)
- `iproute2` (`ip` for dual /1 routes)
- Kernel TUN (`/dev/net/tun`) and **root** for full-tunnel residual IP

## Install (Ubuntu 20.04+ / Mint / Pop!_OS)
```bash
tar xzf restore-privacy-client-{VERSION}-linux-x64.tar.gz
cd restore-privacy-{VERSION}-linux
bash install.sh
sudo ./bin/privacy-restored
```

Press **Connect**. Residual public IP changes only when TUN + dual /1 are active.

## Restore Internet (failsafe)

### BIG WARNING

**Running Restore Internet will ERASE ALL parts of Restore Privacy from this
device** (app, tunnel residual, shortcuts, product secrets). You may **NOT** be
able to automatically re-download your subscription app afterward. Contact
**rus@restoreprivacy.online** to obtain a new download link.

If residual routes leave the machine offline, or you want **complete removal**:

```bash
sudo bash "./Restore Internet"
# or after install:
sudo ./bin/restore-internet
```

This removes dual `/1` residual routes, product kill-switch iptables (if any),
stops the app, and deletes the install tree + `~/.restore-privacy` secrets.
""",
        encoding="utf-8",
    )
    (stage / "LINUX_UBUNTU.md").write_text(
        f"See LINUX_INSTALL.md for the bake-in installer package ({VERSION}).\n",
        encoding="utf-8",
    )
    (stage / "LINUX_MINT.md").write_text(
        f"See LINUX_INSTALL.md — same package for Mint and Ubuntu ({VERSION}).\n",
        encoding="utf-8",
    )


def package_has_baked_deps(stage_or_extract: Path) -> bool:
    """Structural check used by tests: wheels + install entry present."""
    wheels = stage_or_extract / "wheels"
    if not wheels.is_dir():
        return False
    if not any(wheels.glob("cryptography-*.whl")):
        return False
    if not (stage_or_extract / "install.sh").is_file():
        return False
    if not (stage_or_extract / "bin" / "privacy-restored").is_file():
        return False
    inst = (stage_or_extract / "install.sh").read_text(encoding="utf-8")
    if "--no-index" not in inst or "wheels" not in inst:
        return False
    launch = (stage_or_extract / "bin" / "privacy-restored").read_text(encoding="utf-8")
    if ".venv" not in launch or "client.linux" not in launch:
        return False
    return True


def main() -> int:
    # Re-resolve in case env changed after import (tests / free builder).
    global VERSION, FREE_TIER, OUT, NAME
    VERSION, FREE_TIER, OUT, NAME = _resolve_package_version()
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
        for rel in (
            "client",
            "node",
            "requirements.txt",
            "README.md",
            "PRIVACY_POLICY.md",
            "LICENSE",
        ):
            src = ROOT / rel
            if not src.exists():
                continue
            dst = stage / rel
            if src.is_dir():
                shutil.copytree(src, dst, ignore=ignore, dirs_exist_ok=True)
            else:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)

        # Pin packaged client/VERSION to this archive's version (free stays 3.3.3).
        ver_file = stage / "client" / "VERSION"
        ver_file.parent.mkdir(parents=True, exist_ok=True)
        ver_file.write_text(VERSION + "\n", encoding="utf-8")
        if FREE_TIER:
            (stage / "FREE_TIER").write_text("1\n", encoding="utf-8")
            (stage / "DO_NOT_PUBLISH.txt").write_text(
                "Free tier 3.3.3 — local only. Not for GH/VPS paid catalog.\n",
                encoding="utf-8",
            )

        sec = stage / "secrets"
        sec.mkdir(exist_ok=True)
        # Entry + exit ElGamal pubs (public only) for single-hop / multi-hop residual
        for name, candidates in (
            (
                "node_elgamal.pub",
                (
                    ROOT / "product" / "node_elgamal.pub",
                    ROOT / "secrets" / "node_elgamal.pub",
                ),
            ),
            (
                "exit_node_elgamal.pub",
                (
                    ROOT / "product" / "exit_node_elgamal.pub",
                    ROOT / "secrets" / "exit_node_elgamal.pub",
                ),
            ),
        ):
            for src in candidates:
                if src.is_file() and src.stat().st_size >= 32:
                    shutil.copy2(src, sec / name)
                    break
        # Also ship product/ tree pubs when present (load_node prefers product/)
        prod = stage / "product"
        prod.mkdir(exist_ok=True)
        for name in ("node_elgamal.pub", "exit_node_elgamal.pub"):
            src = ROOT / "product" / name
            if src.is_file():
                shutil.copy2(src, prod / name)

        wheels_dir = stage / "wheels"
        print("Downloading manylinux wheels (cryptography stack)…")
        wheels = download_linux_wheels(wheels_dir)
        print(f"  {len(wheels)} wheel file(s) in wheels/")

        write_install_sh(stage)
        write_launcher(stage, free_tier=FREE_TIER)
        write_restore_internet(stage)
        write_docs(stage)

        # Keep ubuntu/mint script names as thin pointers to install.sh
        for name in ("install_linux_ubuntu.sh", "install_linux_mint.sh"):
            (stage / name).write_text(
                "#!/usr/bin/env bash\n"
                'exec bash "$(cd "$(dirname "$0")" && pwd)/install.sh" "$@"\n',
                encoding="utf-8",
            )

        for p in stage.rglob("*.priv"):
            raise RuntimeError(f"refusing private key in package: {p}")

        if not package_has_baked_deps(stage):
            raise RuntimeError("package layout missing baked-in deps markers")

        if dest.exists():
            dest.unlink()
        with tarfile.open(dest, "w:gz") as tf:
            tf.add(stage, arcname=stage.name)

    size = dest.stat().st_size
    print(f"linux package: {dest} ({size} bytes)")
    print(f"sha256: {sha256_file(dest)}")
    # Bake-in package should be much larger than bare source (~50KB)
    if size < 500_000:
        print("WARNING: package smaller than expected for wheeled bundle", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
