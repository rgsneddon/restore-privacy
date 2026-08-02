#!/bin/sh
# Copy product residual PUBLIC ElGamal pins into the built .app (and PacketTunnel).
# Never ships node_elgamal.priv or shared client_ed25519.priv.
# Invoked from Xcode Runner build phase so Debug/flutter run matches Release inject.
set -e
APP="${TARGET_BUILD_DIR}/${FULL_PRODUCT_NAME}"
if [ ! -d "$APP" ]; then
  echo "inject_residual_pubs: app not found yet: $APP (skip)"
  exit 0
fi

# SRCROOT = client_app/macos
REPO_ROOT="$(cd "${SRCROOT}/../.." && pwd)"
SCRIPT="${REPO_ROOT}/scripts/inject_apple_secrets.py"
RUNNER_SECRETS="${SRCROOT}/Runner/secrets"

if [ ! -f "$SCRIPT" ]; then
  echo "error: missing $SCRIPT" >&2
  exit 1
fi

# Prefer repo product/ via inject script; optional --source Runner/secrets if product absent.
SOURCE_ARGS=""
if [ -d "$RUNNER_SECRETS" ] && [ -f "$RUNNER_SECRETS/node_elgamal.pub" ]; then
  SOURCE_ARGS="--source $RUNNER_SECRETS"
fi

echo "inject_residual_pubs: $APP"
# shellcheck disable=SC2086
/usr/bin/python3 "$SCRIPT" --app "$APP" $SOURCE_ARGS

# Fail closed if DE pin still missing (default residual host).
DE_PIN="$APP/Contents/Resources/secrets/de_node_elgamal.pub"
NODE_PIN="$APP/Contents/Resources/secrets/node_elgamal.pub"
if [ ! -f "$DE_PIN" ] || [ ! -f "$NODE_PIN" ]; then
  echo "error: inject left Resources/secrets without de_node_elgamal.pub / node_elgamal.pub" >&2
  ls -la "$APP/Contents/Resources/secrets" 2>&1 || true
  exit 1
fi
# Never allow node private key in package
if [ -f "$APP/Contents/Resources/secrets/node_elgamal.priv" ]; then
  echo "error: node_elgamal.priv must not be packaged" >&2
  exit 1
fi
echo "inject_residual_pubs: OK de=$(wc -c < "$DE_PIN") node=$(wc -c < "$NODE_PIN") bytes"
