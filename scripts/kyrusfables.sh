#!/usr/bin/env bash
# kyrusfables — non-interactive skeleton for the full Restore Privacy ship.
# Prefer invoking Grok skill /kyrusfables for honesty gates + docs + git messages.
# This script runs: tests → build_suite → optional host-paid deploy.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PIN="$(tr -d '[:space:]' < client/VERSION)"
BUILD_SCRIPT="scripts/build_suite_${PIN}.py"
HOST_PAID=0
SKIP_BUILD=0
SKIP_TEST=0
DRY=0

usage() {
  cat <<EOF
Usage: scripts/kyrusfables.sh [--dry-run] [--skip-build] [--skip-test] [--host-paid]

  Full operator ship skeleton (pin from client/VERSION).
  For the agent-driven pipeline (git, docs, NE narrative), type: kyrusfables
EOF
}

for a in "$@"; do
  case "$a" in
    --dry-run) DRY=1 ;;
    --skip-build) SKIP_BUILD=1 ;;
    --skip-test) SKIP_TEST=1 ;;
    --host-paid) HOST_PAID=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown arg: $a" >&2; usage; exit 2 ;;
  esac
done

echo "kyrusfables pin=${PIN} root=${ROOT}"

if [[ ! -f "$BUILD_SCRIPT" ]]; then
  echo "missing $BUILD_SCRIPT" >&2
  exit 1
fi

if [[ "$DRY" -eq 1 ]]; then
  echo "[dry-run] would run flutter NE tests, $BUILD_SCRIPT, optional host-paid"
  git status -sb || true
  exit 0
fi

if [[ "$SKIP_TEST" -eq 0 ]]; then
  (
    cd client_app
    flutter test \
      test/macos_settings_and_vpn_ne_test.dart \
      test/macos_vpn_permission_sequence_test.dart \
      test/ios_vpn_prepare_honesty_test.dart \
      test/apple_vpn_prepare_before_connect_test.dart \
      test/connect_status_test.dart
  )
fi

if [[ "$SKIP_BUILD" -eq 0 ]]; then
  if [[ "$HOST_PAID" -eq 1 ]]; then
    python3 "$BUILD_SCRIPT" --host-paid
  else
    python3 "$BUILD_SCRIPT"
  fi
else
  echo "skip-build: artifacts assumed under releases/${PIN}/"
fi

if [[ "$HOST_PAID" -eq 1 && "$SKIP_BUILD" -eq 1 ]]; then
  python3 scripts/host_paid_assets_vps.py --stage --upload --force
fi

echo "kyrusfables script phase done — commit/docs/NE report still via Grok skill"
git status -sb || true
git rev-parse HEAD || true
