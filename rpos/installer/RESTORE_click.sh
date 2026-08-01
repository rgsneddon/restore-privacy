#!/usr/bin/env bash
# Single-click RESTORE entry (Unix) — advisories, confirm, dry-run wipe, install, Ned interactive OOBE.
set -euo pipefail
PKG="$(cd "$(dirname "$0")" && pwd)"
# Package root may be this dir (RESTORE_click at root) or installer/ subdir
if [[ -d "$PKG/rpos/installer" ]]; then
  BASE="$PKG"
elif [[ -d "$PKG/../rpos/installer" ]]; then
  BASE="$(cd "$PKG/.." && pwd)"
elif [[ -d "$PKG/../../rpos/installer" ]]; then
  BASE="$(cd "$PKG/../.." && pwd)"
else
  BASE="$PKG"
fi
export PYTHONPATH="${BASE}${PYTHONPATH:+:$PYTHONPATH}"
cd "$BASE"
PREFIX="${RPOS_PREFIX:-$HOME/.rpos/install}"
echo "Launching Ned-aware RESTORE path (prefix=$PREFIX)..."
python3 -m rpos.installer advisories
echo ""
read -r -p "Type RESTORE to confirm absolute wipe intent: " CONFIRM
python3 -m rpos.installer restore --yes-advisories --confirm "$CONFIRM" --prefix "$PREFIX"
echo ""
echo "Ned will guide first setup — timezone, language, then your rpMail email."
python3 -m rpos.installer oobe --prefix "$PREFIX"
