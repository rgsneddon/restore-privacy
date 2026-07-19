#!/usr/bin/env bash
# Back-compat entry for Linux Mint users — same recipe as Ubuntu-family install.
# Prefer: bash scripts/install_linux_ubuntu.sh
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
if [[ -f "$HERE/install_linux_ubuntu.sh" ]]; then
  exec bash "$HERE/install_linux_ubuntu.sh" "$@"
fi
# Tarball root may only ship one script name
if [[ -f "$HERE/../scripts/install_linux_ubuntu.sh" ]]; then
  exec bash "$HERE/../scripts/install_linux_ubuntu.sh" "$@"
fi
echo "install_linux_ubuntu.sh not found next to $0" >&2
exit 1
