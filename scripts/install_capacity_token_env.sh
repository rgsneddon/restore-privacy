#!/usr/bin/env bash
# Install durable RPT_CAPACITY_TOKEN for residual node (private capacity probes).
#
# Enables token-gated GET /api/private/capacity on the node UI process env.
# Clients that probe must use the **same** token via RPT_CAPACITY_TOKEN.
#
# Usage (root on residual node):
#   bash scripts/install_capacity_token_env.sh
#   RPT_CAPACITY_TOKEN='your-secret' bash scripts/install_capacity_token_env.sh
#
# Does **not** commit secrets. Generates a token if none provided and none exists.
# Public /api/status stays title-only (no live client counts).
set -euo pipefail

INSTALL_ROOT="${INSTALL_ROOT:-/opt/restore-privacy}"
SERVICE_NAME="${SERVICE_NAME:-rpt-node}"
ENV_DIR="${RPT_CAPACITY_ENV_DIR:-/etc/restore-privacy}"
ENV_FILE="${ENV_DIR}/capacity.env"
DROPIN_DIR="/etc/systemd/system/${SERVICE_NAME}.service.d"
DROPIN_FILE="${DROPIN_DIR}/capacity-token.conf"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "[rpt-capacity] run as root" >&2
  exit 1
fi

mkdir -p "$ENV_DIR" "$DROPIN_DIR"
chmod 755 "$ENV_DIR"

TOKEN="${RPT_CAPACITY_TOKEN:-}"
if [[ -z "$TOKEN" && -f "$ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  set -a
  # shellcheck source=/dev/null
  source "$ENV_FILE" || true
  set +a
  TOKEN="${RPT_CAPACITY_TOKEN:-}"
fi
if [[ -z "$TOKEN" ]]; then
  if command -v openssl >/dev/null 2>&1; then
    TOKEN="$(openssl rand -hex 24)"
  else
    TOKEN="$(head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n')"
  fi
  echo "[rpt-capacity] generated new RPT_CAPACITY_TOKEN (stored in ${ENV_FILE})"
else
  echo "[rpt-capacity] using provided/existing RPT_CAPACITY_TOKEN"
fi

# Optional soft session max + operator bandwidth budget (bits/s) for admin panel.
# RPT_NODE_BANDWIDTH_CAP_BPS is an allowance (not auto-detected NIC line-rate).
MAX_SESSIONS="${RPT_NODE_MAX_SESSIONS:-256}"
BW_CAP="${RPT_NODE_BANDWIDTH_CAP_BPS:-}"

umask 077
{
  echo "# Private residual capacity probe token — do not commit; do not publish."
  echo "# Clients / status admin that call /api/private/capacity need the same RPT_CAPACITY_TOKEN."
  echo "RPT_CAPACITY_TOKEN=${TOKEN}"
  echo "# Soft max sessions for utilization = live / max"
  echo "RPT_NODE_MAX_SESSIONS=${MAX_SESSIONS}"
  if [[ -n "$BW_CAP" ]]; then
    echo "# Operator bandwidth allowance (bits/s) for admin fleet panel used-vs-cap"
    echo "RPT_NODE_BANDWIDTH_CAP_BPS=${BW_CAP}"
  else
    echo "# RPT_NODE_BANDWIDTH_CAP_BPS=100000000  # e.g. 100 Mbps allowance — set when known"
  fi
} >"$ENV_FILE"
chmod 600 "$ENV_FILE"
chown root:root "$ENV_FILE"

cat >"$DROPIN_FILE" <<EOF
# Restore Privacy — private capacity probe token for residual load migration
# Install: scripts/install_capacity_token_env.sh
# Public status remains title-only (no live client count).
[Service]
EnvironmentFile=-${ENV_FILE}
EOF
chmod 644 "$DROPIN_FILE"

systemctl daemon-reload
if systemctl cat "${SERVICE_NAME}.service" >/dev/null 2>&1; then
  # Restart only if service is active (avoid failing on fresh install)
  if systemctl is-active --quiet "${SERVICE_NAME}.service"; then
    systemctl restart "${SERVICE_NAME}.service" || true
    echo "[rpt-capacity] restarted ${SERVICE_NAME}.service"
  else
    echo "[rpt-capacity] ${SERVICE_NAME}.service not active; env will apply on next start"
  fi
else
  echo "[rpt-capacity] ${SERVICE_NAME}.service not installed yet; drop-in ready at ${DROPIN_FILE}"
fi

# Verify authorize helper sees token from env file
export PYTHONPATH="${INSTALL_ROOT}${PYTHONPATH:+:$PYTHONPATH}"
if [[ -x "${INSTALL_ROOT}/venv/bin/python" ]]; then
  PY="${INSTALL_ROOT}/venv/bin/python"
else
  PY="$(command -v python3 || command -v python)"
fi
# shellcheck disable=SC1090
set -a
# shellcheck source=/dev/null
source "$ENV_FILE"
set +a
if "$PY" -c "
from node.private_capacity import authorize_capacity_request, capacity_token_configured
import os
t=capacity_token_configured()
assert t, 'token empty'
ok,_=authorize_capacity_request(authorization_header='Bearer '+t)
assert ok, 'authorize failed'
print('authorize_ok token_len='+str(len(t)))
" 2>/dev/null; then
  echo "[rpt-capacity] helper authorize check: OK"
else
  echo "[rpt-capacity] helper check skipped or failed (PYTHONPATH=${PYTHONPATH})"
fi

echo "[rpt-capacity] private capacity enabled when node UI serves /api/private/capacity"
echo "[rpt-capacity] client: export RPT_CAPACITY_TOKEN='(same secret)' before Connect"
echo "[rpt-capacity] honesty: not a public client counter; fail-soft without token"
