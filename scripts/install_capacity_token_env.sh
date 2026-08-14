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

# Per-peer product budgets (operator allowance — not auto NIC line-rate):
#   RO: unlimited-class bandwidth, session soft max 256 (legacy)
#   IS: unlimited-class bandwidth, session soft max 512
#   DE: unlimited-class bandwidth (30 TB class), session soft max 1024
#       (dedicated 8 vCPU / 32 GB residual host)
#   US: 200 Mbps fixed budget, session soft max 512
#   SG: unlimited-class bandwidth, session soft max 256
# Override with RPT_NODE_PEER_CODE=IS|DE|US|RO|SG, RPT_NODE_MAX_SESSIONS, RPT_NODE_BANDWIDTH_CAP_BPS.
PEER_CODE="${RPT_NODE_PEER_CODE:-${RPT_PEER_CODE:-}}"
if [[ -z "$PEER_CODE" ]]; then
  # Best-effort: match primary IPv4 to catalog residual hosts
  DETECTED_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
  case "${DETECTED_IP}" in
    82.221.101.241) PEER_CODE=IS ;;
    178.105.187.178) PEER_CODE=DE ;;
    185.146.232.107) PEER_CODE=RO ;;
    5.161.242.85) PEER_CODE=US ;;
    5.223.48.8) PEER_CODE=SG ;;
  esac
fi
PEER_CODE="$(echo "${PEER_CODE}" | tr '[:lower:]' '[:upper:]')"
case "${PEER_CODE}" in
  US)
    DEFAULT_MAX=512
    DEFAULT_BW=200000000
    ;;
  IS)
    DEFAULT_MAX=512
    DEFAULT_BW=""  # unlimited-class (extendable at cost)
    ;;
  DE)
    DEFAULT_MAX=1024
    DEFAULT_BW=""  # unlimited-class (30 TB entitlement; extendable at cost)
    ;;
  RO)
    DEFAULT_MAX=256
    DEFAULT_BW=""  # unlimited-class (extendable at cost)
    ;;
  SG)
    DEFAULT_MAX=256
    DEFAULT_BW=""  # unlimited-class (extendable at cost)
    ;;
  *)
    DEFAULT_MAX=256
    DEFAULT_BW=""
    ;;
esac
MAX_SESSIONS="${RPT_NODE_MAX_SESSIONS:-${DEFAULT_MAX}}"
# Empty DEFAULT_BW + unset env → omit fixed product budget (IS/RO unlimited-class)
if [[ -n "${RPT_NODE_BANDWIDTH_CAP_BPS+x}" ]]; then
  BW_CAP="${RPT_NODE_BANDWIDTH_CAP_BPS}"
else
  BW_CAP="${DEFAULT_BW}"
fi

umask 077
{
  echo "# Private residual capacity probe token — do not commit; do not publish."
  echo "# Clients / status admin that call /api/private/capacity need the same RPT_CAPACITY_TOKEN."
  echo "RPT_CAPACITY_TOKEN=${TOKEN}"
  if [[ -n "$PEER_CODE" ]]; then
    echo "# Catalog peer identity (DE 1024; IS/US 512; RO 256; US + 200 Mbps budget)"
    echo "RPT_NODE_PEER_CODE=${PEER_CODE}"
  fi
  echo "# Soft max sessions for utilization = live / max (product: DE 1024, IS/US 512, RO 256)"
  echo "RPT_NODE_MAX_SESSIONS=${MAX_SESSIONS}"
  if [[ -n "$BW_CAP" ]]; then
    echo "# Operator bandwidth allowance (bits/s) for admin fleet panel used-vs-cap"
    echo "# Product: IS/DE/RO unlimited-class (omit this key); US 200 Mbps (200000000)"
    echo "RPT_NODE_BANDWIDTH_CAP_BPS=${BW_CAP}"
  else
    echo "# No fixed RPT_NODE_BANDWIDTH_CAP_BPS — product unlimited-class for IS/DE/RO"
    echo "# (extendable bandwidth at cost). US install sets 200000000."
  fi
} >"$ENV_FILE"
echo "[rpt-capacity] peer=${PEER_CODE:-unknown} max_sessions=${MAX_SESSIONS} bw_cap_bps=${BW_CAP:-unlimited-class}"
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
