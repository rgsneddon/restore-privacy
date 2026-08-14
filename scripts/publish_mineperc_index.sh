#!/usr/bin/env bash
# Install the mineperc homepage only if it still has the Live miners table.
# Usage: bash scripts/publish_mineperc_index.sh [src.html]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="${1:-$ROOT/perc_chain/mineperc/public/index.html}"
DST="${MINEPERC_WWW_INDEX:-/var/www/mineperc.restoreprivacy.online/index.html}"
for needle in "Live miners" "72 seconds" "miner-body" "/api/stats"; do
  grep -q "$needle" "$SRC" || {
    echo "refuse: $SRC missing $needle — would drop the miner table" >&2
    exit 1
  }
done
if [[ -f "$DST" ]]; then
  chattr -i "$DST" 2>/dev/null || true
fi
mkdir -p "$(dirname "$DST")"
cp "$SRC" "$DST"
chmod 644 "$DST"
chattr +i "$DST" 2>/dev/null || true
echo "published $DST with Live miners / 72 seconds"
