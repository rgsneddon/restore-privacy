#!/usr/bin/env bash
# Install Restore Privacy client on Ubuntu and derivatives
# (Ubuntu 20.04 LTS+, Linux Mint, Pop!_OS, elementary, Kubuntu, …).
#
# Usage (from repo root or extracted tarball):
#   bash scripts/install_linux_ubuntu.sh
#   bash install_linux_ubuntu.sh    # tarball root
#   bash install_linux_mint.sh     # alias — same recipe
#
# Support floor: Ubuntu 20.04 LTS (Python 3.8+) and newer.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." 2>/dev/null && pwd)"
if [[ ! -f "$ROOT/client/linux/__main__.py" ]]; then
  # Tarball layout: install script next to client/
  ROOT="$(cd "$(dirname "$0")" && pwd)"
fi

echo "=== Restore Privacy - Ubuntu / Linux install ==="
echo "Root: $ROOT"
echo "Support: Ubuntu 20.04 LTS+ and derivatives (Mint, Pop!_OS, …)"

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required. On Ubuntu/Mint:"
  echo "  sudo apt-get update && sudo apt-get install -y python3 python3-pip"
  exit 1
fi

# Python floor 3.8 (Ubuntu 20.04)
PY_MINOR="$(python3 -c 'import sys; print("%d.%d" % (sys.version_info[0], sys.version_info[1]))')"
PY_OK="$(python3 -c 'import sys; print(1 if sys.version_info >= (3, 8) else 0)')"
if [[ "$PY_OK" != "1" ]]; then
  echo "ERROR: Python $PY_MINOR is too old (need 3.8+ for Ubuntu 20.04+ support)."
  exit 1
fi
echo "Python $PY_MINOR OK"

# --- apt packages (names stable across Ubuntu 20.04–24.04) ---
need_apt=0
command -v ip >/dev/null 2>&1 || need_apt=1
python3 -c "import tkinter" 2>/dev/null || need_apt=1
python3 -c "import cryptography" 2>/dev/null || need_apt=1

if [[ "$need_apt" -eq 1 ]]; then
  if ! command -v apt-get >/dev/null 2>&1; then
    echo "ERROR: apt-get not found. This installer targets Ubuntu-family (Debian) systems."
    exit 1
  fi
  echo "Installing apt packages: python3-tk python3-cryptography python3-pip iproute2..."
  sudo apt-get update -y
  # iproute2 provides `ip` (routes/TUN setup)
  # python3-cryptography required by client.connect at import time
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
    python3-tk \
    python3-cryptography \
    python3-pip \
    iproute2 \
    || true
fi

# --- cryptography: apt first, then pip with Ubuntu 24.04 PEP 668 handling ---
_pip_install() {
  # Prefer user install; on 23.04+/24.04 externally-managed env needs break flag
  local req="$1"
  if python3 -m pip install --user "$req" 2>/dev/null; then
    return 0
  fi
  if python3 -m pip install --user --break-system-packages "$req" 2>/dev/null; then
    return 0
  fi
  if sudo python3 -m pip install "$req" 2>/dev/null; then
    return 0
  fi
  sudo python3 -m pip install --break-system-packages "$req" 2>/dev/null
}

if ! python3 -c "import cryptography" 2>/dev/null; then
  echo "cryptography not importable after apt; trying pip..."
  if [[ -f "$ROOT/requirements.txt" ]]; then
    _pip_install "-r $ROOT/requirements.txt" || \
      python3 -m pip install --user -r "$ROOT/requirements.txt" || \
      python3 -m pip install --user --break-system-packages -r "$ROOT/requirements.txt" || \
      sudo python3 -m pip install -r "$ROOT/requirements.txt" || \
      sudo python3 -m pip install --break-system-packages -r "$ROOT/requirements.txt" || true
  else
    _pip_install "cryptography>=41" || true
  fi
fi

if ! python3 -c "import cryptography" 2>/dev/null; then
  echo "ERROR: cryptography still missing."
  echo "  sudo apt-get install -y python3-cryptography"
  echo "  # or: pip3 install --user cryptography"
  exit 1
fi
if ! python3 -c "import tkinter" 2>/dev/null; then
  echo "ERROR: tkinter still missing. Install: sudo apt-get install -y python3-tk"
  exit 1
fi
if ! command -v ip >/dev/null 2>&1; then
  echo "ERROR: ip (iproute2) missing. Install: sudo apt-get install -y iproute2"
  exit 1
fi
echo "Deps OK: python3 + tkinter + cryptography + iproute2"

# TUN module (standard on Ubuntu desktop/server kernels)
if [[ ! -e /dev/net/tun ]]; then
  echo "Loading tun module..."
  sudo modprobe tun || true
fi
if [[ ! -e /dev/net/tun ]]; then
  echo "WARNING: /dev/net/tun missing after modprobe. Full tunnel will fail until TUN is available."
fi

# Admission public key only (device Ed25519 generated on first run)
SECRETS_DIR="${HOME}/.restore-privacy/secrets"
mkdir -p "$SECRETS_DIR"
if [[ -f "$ROOT/secrets/node_elgamal.pub" ]]; then
  cp -f "$ROOT/secrets/node_elgamal.pub" "$SECRETS_DIR/"
  echo "Installed node public key to $SECRETS_DIR"
fi

# Desktop launcher (Ubuntu / Mint / GNOME / Cinnamon / etc.)
APPS="${HOME}/.local/share/applications"
mkdir -p "$APPS"
# PYTHONPATH so module import works regardless of cwd
cat > "$APPS/privacy-restored.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Privacy Restored
Comment=Restore Privacy VPN (Ubuntu / Linux)
Exec=env PYTHONPATH=$ROOT pkexec env DISPLAY=\$DISPLAY XAUTHORITY=\$XAUTHORITY PYTHONPATH=$ROOT python3 -m client.linux
Path=$ROOT
Terminal=false
Categories=Network;Security;
Keywords=VPN;Privacy;Ubuntu;
EOF
echo "Desktop entry: $APPS/privacy-restored.desktop"

# Smoke: module import (no GUI)
if ! PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}" python3 -c "import client.linux; import client.connect" 2>/dev/null; then
  echo "WARNING: import check failed. From $ROOT run: PYTHONPATH=$ROOT python3 -m client.linux"
else
  echo "Import check OK (client.linux + client.connect)"
fi

echo ""
echo "Install complete (Ubuntu-family)."
echo "  Full tunnel (root):  cd $ROOT && sudo PYTHONPATH=$ROOT python3 -m client.linux"
echo "  Or with polkit GUI:  PYTHONPATH=$ROOT pkexec env DISPLAY=\$DISPLAY XAUTHORITY=\$XAUTHORITY PYTHONPATH=$ROOT python3 -m client.linux"
echo "Press Connect after launch. Residual public IP changes only with root + dual /1 routes."
