#!/usr/bin/env bash
# Single-click RESTORE entry (Unix) — advisories then confirm then dry-run wipe + install.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# When shipped inside package: stage_top/RESTORE_click.sh or bin/
PKG="$(cd "$(dirname "$0")" && pwd)"
# Prefer package root (parent of bin/ or installer/)
if [[ -d "$PKG/rpos/installer" ]]; then
  BASE="$PKG"
elif [[ -d "$PKG/../rpos/installer" ]]; then
  BASE="$(cd "$PKG/.." && pwd)"
elif [[ -d "$PKG/../../rpos/installer" ]]; then
  BASE="$(cd "$PKG/../.." && pwd)"
else
  BASE="$ROOT"
fi
export PYTHONPATH="${BASE}${PYTHONPATH:+:$PYTHONPATH}"
cd "$BASE"
echo "Launching Ned-aware RESTORE path..."
python3 -m rpos.installer advisories
echo ""
echo "Type RESTORE to confirm absolute wipe intent + install (or Ctrl-C):"
read -r CONFIRM
python3 -m rpos.installer restore --yes-advisories --confirm "$CONFIRM"
echo ""
echo "Ned will guide first setup (timezone, language, rpMail email)."
python3 -m rpos.installer oobe --smoke
