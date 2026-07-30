#!/usr/bin/env bash
# Install Restore Privacy client on Arch Linux family
# (Arch, **CachyOS**, EndeavourOS, Manjaro, Garuda, Artix, …).
#
# Usage (from repo root or extracted monopin tarball):
#   bash scripts/install_linux_arch.sh
#   bash install_linux_arch.sh              # tarball root
#   bash install_linux_cachyos.sh           # alias — same recipe
#
# Preferred product path: extract restore-privacy-client-*-linux-x64.tar.gz,
# then run install.sh (auto-detects pacman). This script is for source trees
# and explicit Arch/CachyOS operator installs.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." 2>/dev/null && pwd)"
if [[ ! -f "$ROOT/client/linux/__main__.py" ]]; then
  # Tarball layout: install script next to client/
  ROOT="$(cd "$(dirname "$0")" && pwd)"
fi

echo "=== Restore Privacy - Arch / CachyOS install ==="
echo "Root: $ROOT"
echo "Support: Arch Linux family (CachyOS, EndeavourOS, Manjaro, …)"

if ! command -v python3 >/dev/null 2>&1 && ! command -v python >/dev/null 2>&1; then
  echo "python is required. On Arch/CachyOS:"
  echo "  sudo pacman -S --needed python"
  exit 1
fi
# Prefer python3 if present; Arch ships `python` as 3.x
if command -v python3 >/dev/null 2>&1; then
  PY=python3
else
  PY=python
fi

PY_MINOR="$($PY -c 'import sys; print("%d.%d" % (sys.version_info[0], sys.version_info[1]))')"
PY_OK="$($PY -c 'import sys; print(1 if sys.version_info >= (3, 8) else 0)')"
if [[ "$PY_OK" != "1" ]]; then
  echo "ERROR: Python $PY_MINOR is too old (need 3.8+)."
  exit 1
fi
echo "Python $PY_MINOR OK ($PY)"

# --- pacman packages (Arch / CachyOS names) ---
need_pm=0
command -v ip >/dev/null 2>&1 || need_pm=1
$PY -c "import tkinter" 2>/dev/null || need_pm=1
# cryptography: prefer bundled wheels in monopin tarball; system package optional

if [[ "$need_pm" -eq 1 ]]; then
  if ! command -v pacman >/dev/null 2>&1; then
    echo "ERROR: pacman not found. This installer targets Arch-family systems."
    echo "On Ubuntu/Mint use: bash install_linux_ubuntu.sh (or install.sh)."
    exit 1
  fi
  echo "Installing pacman packages: python tk iproute2..."
  sudo pacman -S --needed --noconfirm python tk iproute2 || true
fi

# Monopin tarball: prefer install.sh (bundled manylinux wheels → private .venv)
if [[ -f "$ROOT/install.sh" && -d "$ROOT/wheels" ]]; then
  echo "Monopin package detected — running install.sh (offline wheels)..."
  bash "$ROOT/install.sh"
  exit $?
fi

# Source / repo tree: optional cryptography via pacman or pip
if ! $PY -c "import cryptography" 2>/dev/null; then
  if command -v pacman >/dev/null 2>&1; then
    echo "Installing python-cryptography via pacman (source tree)..."
    sudo pacman -S --needed --noconfirm python-cryptography || true
  fi
fi
if ! $PY -c "import cryptography" 2>/dev/null; then
  echo "Trying pip install cryptography (user)..."
  $PY -m pip install --user "cryptography>=41" 2>/dev/null || \
    $PY -m pip install --user --break-system-packages "cryptography>=41" 2>/dev/null || true
fi

if ! $PY -c "import cryptography" 2>/dev/null; then
  echo "ERROR: cryptography still missing."
  echo "  sudo pacman -S --needed python-cryptography"
  echo "  # or use the paid monopin tar.gz and bash install.sh"
  exit 1
fi
if ! $PY -c "import tkinter" 2>/dev/null; then
  echo "ERROR: tkinter still missing. Install: sudo pacman -S --needed tk"
  exit 1
fi
if ! command -v ip >/dev/null 2>&1; then
  echo "ERROR: ip (iproute2) missing. Install: sudo pacman -S --needed iproute2"
  exit 1
fi

if [[ ! -e /dev/net/tun ]]; then
  echo "Loading tun module..."
  sudo modprobe tun || true
fi

export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
echo ""
echo "Arch/CachyOS host ready."
echo "  Run residual GUI (root for full tunnel):"
echo "    cd $ROOT && sudo PYTHONPATH=$ROOT $PY -m client.linux"
echo "  Or extract the monopin linux-x64.tar.gz and: bash install.sh"
