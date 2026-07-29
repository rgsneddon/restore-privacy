#!/usr/bin/env bash
# Open the Team residual NE macOS app for residual Connect testing.
#
# Public Developer ID catalog zips intentionally omit host packet-tunnel-provider
# (AMFI). Residual Connect on a developer Mac requires the residual-team copy.
#
# Usage (from monorepo root):
#   ./scripts/open_macos_residual_connect.sh
#   ./scripts/open_macos_residual_connect.sh --skip-resign
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP_SRC="$ROOT/client_app/build/macos/Build/Products/Release/restore_privacy_client.app"
RT="$ROOT/client_app/build/macos/Build/Products/Release/restore_privacy_client.residual-team.app"

if [[ ! -d "$APP_SRC" ]]; then
  echo "Missing $APP_SRC" >&2
  echo "Run: cd client_app && flutter build macos --release" >&2
  exit 1
fi

if [[ "${1:-}" != "--skip-resign" ]]; then
  echo "Team residual NE re-sign → residual-team.app …"
  python3 "$ROOT/scripts/apple_ship_gates.py" --residual-team-only
fi

if [[ ! -d "$RT" ]]; then
  echo "Missing residual-team app after re-sign: $RT" >&2
  exit 1
fi

# Fail closed if host still lacks NE entitlement
if ! codesign -d --entitlements :- "$RT" 2>/dev/null | grep -q packet-tunnel-provider; then
  echo "ERROR: residual-team host still missing packet-tunnel-provider" >&2
  exit 1
fi

echo "Opening residual-team (has packet-tunnel-provider). Allow VPN if prompted."
echo "If paid: enter keygen from fulfilment email, then Connect."
open "$RT"
echo "OK $RT"
