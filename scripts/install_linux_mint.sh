#!/usr/bin/env bash
# Install Restore Privacy client on Linux Mint / Ubuntu-family.
# Usage (from repo root or extracted tarball):
#   bash scripts/install_linux_mint.sh
#   # or after unpacking the release tar.gz:
#   bash install_linux_mint.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." 2>/dev/null && pwd)"
if [[ ! -f "$ROOT/client/linux/__main__.py" ]]; then
  # Running from tarball layout where install script sits next to client/
  ROOT="$(cd "$(dirname "$0")" && pwd)"
fi

echo "=== Restore Privacy - Linux Mint install ==="
echo "Root: $ROOT"

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required. On Mint: sudo apt install python3 python3-tk python3-pip"
  exit 1
fi

# Ensure apt is available for deps
need_apt=0
if ! python3 -c "import tkinter" 2>/dev/null; then need_apt=1; fi
if ! python3 -c "import cryptography" 2>/dev/null; then need_apt=1; fi
if [[ "$need_apt" -eq 1 ]]; then
  echo "Installing Python deps (python3-tk, python3-cryptography) via apt..."
  sudo apt-get update -y
  # cryptography is required by client.connect at import time
  sudo apt-get install -y python3-tk python3-cryptography python3-pip
fi

# Prefer distro package; fall back to pip for cryptography if still missing
if ! python3 -c "import cryptography" 2>/dev/null; then
  echo "Installing cryptography via pip..."
  if [[ -f "$ROOT/requirements.txt" ]]; then
    python3 -m pip install --user -r "$ROOT/requirements.txt" || \
      sudo python3 -m pip install -r "$ROOT/requirements.txt"
  else
    python3 -m pip install --user "cryptography>=41" || \
      sudo python3 -m pip install "cryptography>=41"
  fi
fi

if ! python3 -c "import cryptography" 2>/dev/null; then
  echo "ERROR: cryptography module still missing. Install: sudo apt install python3-cryptography"
  exit 1
fi
if ! python3 -c "import tkinter" 2>/dev/null; then
  echo "ERROR: tkinter still missing. Install: sudo apt install python3-tk"
  exit 1
fi
echo "Python deps OK (tkinter + cryptography)"

# TUN module
if [[ ! -e /dev/net/tun ]]; then
  echo "Loading tun module..."
  sudo modprobe tun || true
fi

# Optional: admission public key into user secrets
SECRETS_DIR="${HOME}/.restore-privacy/secrets"
mkdir -p "$SECRETS_DIR"
if [[ -f "$ROOT/secrets/node_elgamal.pub" ]]; then
  cp -f "$ROOT/secrets/node_elgamal.pub" "$SECRETS_DIR/"
  echo "Installed node public key to $SECRETS_DIR"
fi
# Never copy shared client_ed25519.priv - generated on first run

# Desktop launcher
APPS="${HOME}/.local/share/applications"
mkdir -p "$APPS"
cat > "$APPS/privacy-restored.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Privacy Restored
Comment=Restore Privacy VPN client
Exec=pkexec env DISPLAY=\$DISPLAY XAUTHORITY=\$XAUTHORITY python3 -m client.linux
Path=$ROOT
Terminal=false
Categories=Network;Security;
EOF
echo "Desktop entry: $APPS/privacy-restored.desktop"

echo ""
echo "Install complete."
echo "  GUI (full tunnel needs root):  cd $ROOT && sudo python3 -m client.linux"
echo "  Or:  pkexec env DISPLAY=\$DISPLAY XAUTHORITY=\$XAUTHORITY python3 -m client.linux"
echo "Press Connect after launch. Residual public IP changes only with root + dual /1 routes."
