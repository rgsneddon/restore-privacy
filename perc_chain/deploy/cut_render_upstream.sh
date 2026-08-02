#!/usr/bin/env bash
# Cut PERC dual-seed umbilical to evolve-perc-internet.onrender.com on Helsinki.
# Safe to re-run. Run ON the host as root, or:
#   ssh -i ~/.ssh/id_ed25519_restore_privacy_eu root@135.181.152.10 'bash -s' < perc_chain/deploy/cut_render_upstream.sh
#
# Sets PERC_UPSTREAM_RENDEZVOUS_URL=none (explicit disable). Removing the key is
# not enough alone on older builds that hard-defaulted to onrender — deploy a
# current internet_node.js that honors none/off/disabled/empty.
#
# Does NOT touch: restore-privacy-status Render shop, GitHub evolve, client JSON.
set -euo pipefail

ENV="${RPT_PERC_ENV:-/opt/restore-privacy/perc_chain/helsinki.env}"
SNIP="${RPT_NGINX_SNIP:-/etc/nginx/snippets/rpt-perc-chain.conf}"
UNIT="${RPT_PERC_UNIT:-rpt-perc-chain.service}"
PUBLIC_HEALTH="${RPT_PUBLIC_HEALTH:-https://135.181.152.10.sslip.io/perc/health}"
NODE_SRC="${RPT_PERC_NODE_SRC:-/opt/restore-privacy/perc_chain/src/internet_node.js}"

echo "== cut_render_upstream: env =="
test -f "$ENV"
cp -a "$ENV" "${ENV}.bak.$(date -u +%Y%m%dT%H%M%SZ)"
# Drop old UPSTREAM lines + onrender URL assignments; strip stale onrender comments.
grep -vE '^[[:space:]]*PERC_UPSTREAM_RENDEZVOUS_URL=' "$ENV" \
  | grep -vE 'https?://[^[:space:]]*onrender\.com' \
  | grep -vE '^#.*onrender\.com' \
  > "${ENV}.tmp"
{
  echo "# Render dual-seed umbilical cut — solo Helsinki seed"
  cat "${ENV}.tmp"
  echo "PERC_UPSTREAM_RENDEZVOUS_URL=none"
} > "${ENV}.tmp2"
mv "${ENV}.tmp2" "$ENV"
rm -f "${ENV}.tmp"
if ! grep -qE '^PERC_UPSTREAM_RENDEZVOUS_URL=none$' "$ENV"; then
  echo "ERROR: expected PERC_UPSTREAM_RENDEZVOUS_URL=none in $ENV" >&2
  exit 1
fi
if grep -E 'https?://[^[:space:]]*onrender\.com' "$ENV"; then
  echo "ERROR: onrender URL still present in $ENV" >&2
  exit 1
fi
grep -qE '^PORT=9478' "$ENV"
grep -qE '^PERC_PUBLIC_ENDPOINT=https://135\.181\.152\.10\.sslip\.io/perc' "$ENV"
grep -qE '^PERC_DATA_DIR=/opt/restore-privacy/perc_chain/data' "$ENV"
grep -qE '^PERC_SEED_USERNAME=' "$ENV"

echo "== cut_render_upstream: node must not hard-default to onrender =="
if [[ -f "$NODE_SRC" ]]; then
  if grep -n "return 'https://evolve-perc-internet.onrender.com'" "$NODE_SRC"; then
    echo "ERROR: $NODE_SRC still hard-defaults upstream to Render — deploy fixed internet_node.js first" >&2
    exit 1
  fi
  if ! grep -q 'isDisabledUpstream' "$NODE_SRC"; then
    echo "WARN: $NODE_SRC missing isDisabledUpstream — may still pull Render if env key absent" >&2
  fi
fi

echo "== cut_render_upstream: nginx snippet (local :9478 only) =="
test -f "$SNIP"
grep -q 'proxy_pass http://127.0.0.1:9478/' "$SNIP"
NGINX_ROOT="${RPT_NGINX_ROOT:-/etc/nginx}"
if grep -RniE 'https?://[^[:space:]]*onrender\.com' "$NGINX_ROOT" 2>/dev/null; then
  echo "ERROR: live onrender URL under $NGINX_ROOT" >&2
  exit 1
fi

if [[ "${RPT_CUT_RENDER_SKIP_SERVICE:-}" == "1" ]]; then
  echo "CUT_RENDER_UPSTREAM_DONE (env+nginx files only; SKIP_SERVICE=1)"
  exit 0
fi

if command -v nginx >/dev/null 2>&1; then
  nginx -t
  systemctl reload nginx
fi

echo "== cut_render_upstream: restart $UNIT =="
systemctl restart "$UNIT"
systemctl is-active --quiet "$UNIT"

echo "== cut_render_upstream: loopback health =="
ok=0
for _ in 1 2 3 4 5 6 7 8 9 10 11 12; do
  if curl -sS -m 3 "http://127.0.0.1:9478/health" | grep -q '"ok":true'; then
    ok=1
    break
  fi
  sleep 1
done
if [[ "$ok" -ne 1 ]]; then
  echo "ERROR: loopback /health not ok" >&2
  exit 1
fi
curl -sS -m 5 "http://127.0.0.1:9478/health"
echo

# After restart, journal since THIS start must not mention onrender (ignore older boots)
sleep 1
SINCE=$(systemctl show "$UNIT" -p ActiveEnterTimestamp --value 2>/dev/null || true)
if [[ -n "$SINCE" ]] && journalctl -u "$UNIT" --since "$SINCE" --no-pager 2>/dev/null | grep -F 'onrender.com'; then
  echo "ERROR: unit still contacting onrender.com after cut — check internet_node.js deploy" >&2
  exit 1
fi

echo "CUT_RENDER_UPSTREAM_DONE"
echo "Public verify from laptop: curl -sS -m 10 '$PUBLIC_HEALTH'"
