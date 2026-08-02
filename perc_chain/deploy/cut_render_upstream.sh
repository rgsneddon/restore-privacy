#!/usr/bin/env bash
# Cut PERC dual-seed umbilical to evolve-perc-internet.onrender.com on Helsinki.
# Safe to re-run. Run ON the host as root, or:
#   ssh -i ~/.ssh/id_ed25519_restore_privacy_eu root@135.181.152.10 'bash -s' < perc_chain/deploy/cut_render_upstream.sh
#
# Does NOT touch: restore-privacy-status Render shop, GitHub evolve, client JSON.
set -euo pipefail

ENV="${RPT_PERC_ENV:-/opt/restore-privacy/perc_chain/helsinki.env}"
SNIP="${RPT_NGINX_SNIP:-/etc/nginx/snippets/rpt-perc-chain.conf}"
UNIT="${RPT_PERC_UNIT:-rpt-perc-chain.service}"
PUBLIC_HEALTH="${RPT_PUBLIC_HEALTH:-https://135.181.152.10.sslip.io/perc/health}"

echo "== cut_render_upstream: env =="
test -f "$ENV"
cp -a "$ENV" "${ENV}.bak.$(date -u +%Y%m%dT%H%M%SZ)"
# Drop UPSTREAM key lines + any live onrender URL assignments; keep other keys.
grep -vE '^[[:space:]]*PERC_UPSTREAM_RENDEZVOUS_URL=' "$ENV" \
  | grep -vE 'https?://[^[:space:]]*onrender\.com' \
  > "${ENV}.tmp"
# Replace stale dual-seed comment with cut note (comment-only onrender mentions go away).
grep -vE '^#.*onrender\.com' "${ENV}.tmp" > "${ENV}.tmp2" || true
{
  echo "# Render dual-seed umbilical cut — no PERC_UPSTREAM_RENDEZVOUS_URL"
  cat "${ENV}.tmp2"
} > "${ENV}.tmp3"
mv "${ENV}.tmp3" "$ENV"
rm -f "${ENV}.tmp" "${ENV}.tmp2"
if grep -E '^[[:space:]]*PERC_UPSTREAM_RENDEZVOUS_URL=' "$ENV"; then
  echo "ERROR: PERC_UPSTREAM_RENDEZVOUS_URL still present in $ENV" >&2
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

echo "== cut_render_upstream: nginx snippet (local :9478 only) =="
test -f "$SNIP"
grep -q 'proxy_pass http://127.0.0.1:9478/' "$SNIP"
# Live host: scan full nginx tree. Lab/test: only the snippet file (RPT_NGINX_ROOT).
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
echo "CUT_RENDER_UPSTREAM_DONE"
echo "Public verify from laptop: curl -sS -m 10 '$PUBLIC_HEALTH'"
