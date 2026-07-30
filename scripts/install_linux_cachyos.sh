#!/usr/bin/env bash
# CachyOS (Arch-based) install alias — same recipe as install_linux_arch.sh
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
if [[ -f "$HERE/install_linux_arch.sh" ]]; then
  exec bash "$HERE/install_linux_arch.sh" "$@"
fi
if [[ -f "$HERE/../scripts/install_linux_arch.sh" ]]; then
  exec bash "$HERE/../scripts/install_linux_arch.sh" "$@"
fi
echo "install_linux_arch.sh not found next to $0" >&2
exit 1
