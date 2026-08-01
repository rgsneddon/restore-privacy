#!/usr/bin/env bash
set -euo pipefail
PKG="$(cd "$(dirname "$0")" && pwd)"
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
echo "Ned: personal setup — timezone, language, rpMail email."
python3 -m rpos.installer oobe --prefix "$PREFIX"
echo ""
echo "Ned: locked guide — Pens, then Tables, then Slides (Desktop launchers)."
python3 -m rpos.installer apps-tour --prefix "$PREFIX"
