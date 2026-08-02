# Cut Render umbilical — Helsinki perc_chain (operator one-liners)

**Scope:** Remove dual-seed pull from `evolve-perc-internet.onrender.com` on the
Helsinki store host only. Clients already use Helsinki as rendezvous; this cut
stops the node from merging/pulling upstream from Render.

**Important:** Older `internet_node.js` hard-defaulted upstream to Render when
`PERC_UPSTREAM_RENDEZVOUS_URL` was unset. Deploy a build with `isDisabledUpstream`
and set `PERC_UPSTREAM_RENDEZVOUS_URL=none` (the cut script does both checks).

**Not in scope:** `restore-privacy-status` Render shop/admin, GitHub
`rgsneddon/evolve`, Flutter client config, or pausing/deleting the Render service.

| Live path | Value |
|-----------|--------|
| Host | `135.181.152.10` |
| SSH | `ssh -i ~/.ssh/id_ed25519_restore_privacy_eu root@135.181.152.10` |
| Env | `/opt/restore-privacy/perc_chain/helsinki.env` |
| Unit | `rpt-perc-chain.service` |
| Nginx snippet | `/etc/nginx/snippets/rpt-perc-chain.conf` → `proxy_pass http://127.0.0.1:9478/` |
| Public health | `https://135.181.152.10.sslip.io/perc/health` |

**Client `rendezvousUrl` (already Helsinki — no change required):**

- `https://135.181.152.10.sslip.io/perc` in Evolve / evolve-apple / MY PERC / suite
  `assets/config/perc_network.json` (or `PERC_RENDEZVOUS_URL` dart-define).

---

## 0) Optional pre-cut baseline (laptop)

```bash
curl -sS -m 10 "https://135.181.152.10.sslip.io/perc/health"
ssh -i ~/.ssh/id_ed25519_restore_privacy_eu root@135.181.152.10 \
  'grep PERC_UPSTREAM /opt/restore-privacy/perc_chain/helsinki.env || true'
```

---

## 1) Env edit — drop onrender upstream (SSH one-liner)

Removes any line containing `PERC_UPSTREAM_RENDEZVOUS_URL` (including
`https://evolve-perc-internet.onrender.com`). Leaves `PORT`, `PERC_PUBLIC_ENDPOINT`,
`PERC_DATA_DIR`, seed/genesis keys untouched. Backs up first.

```bash
ssh -i ~/.ssh/id_ed25519_restore_privacy_eu root@135.181.152.10 'set -euo pipefail
ENV=/opt/restore-privacy/perc_chain/helsinki.env
test -f "$ENV"
cp -a "$ENV" "${ENV}.bak.$(date -u +%Y%m%dT%H%M%SZ)"
grep -vE "^[[:space:]]*PERC_UPSTREAM_RENDEZVOUS_URL=" "$ENV" \
  | grep -vE "https?://[^[:space:]]*onrender\.com" \
  | grep -vE "^#.*onrender\.com" > "${ENV}.tmp"
{ echo "# Render dual-seed umbilical cut — no PERC_UPSTREAM_RENDEZVOUS_URL"; cat "${ENV}.tmp"; } > "${ENV}.tmp2"
mv "${ENV}.tmp2" "$ENV"; rm -f "${ENV}.tmp"
# Assert umbilical gone and required keys still present
! grep -E "^[[:space:]]*PERC_UPSTREAM_RENDEZVOUS_URL=" "$ENV"
! grep -E "https?://[^[:space:]]*onrender\.com" "$ENV"
grep -qE "^PORT=9478" "$ENV"
grep -qE "^PERC_PUBLIC_ENDPOINT=https://135\.181\.152\.10\.sslip\.io/perc" "$ENV"
grep -qE "^PERC_DATA_DIR=/opt/restore-privacy/perc_chain/data" "$ENV"
grep -qE "^PERC_SEED_USERNAME=" "$ENV"
echo "helsinki.env: UPSTREAM removed OK"
cat "$ENV"
'
```

---

## 2) Nginx — confirm local-only proxy (no Render change expected)

Live snippet already only proxies `http://127.0.0.1:9478/`. The only “onrender”
string is a **comment**. No functional nginx edit is required; these one-liners
**verify** that and reload only if you touched config.

```bash
ssh -i ~/.ssh/id_ed25519_restore_privacy_eu root@135.181.152.10 'set -euo pipefail
SNIP=/etc/nginx/snippets/rpt-perc-chain.conf
test -f "$SNIP"
# Must proxy loopback node only
grep -q "proxy_pass http://127.0.0.1:9478/" "$SNIP"
# No live onrender upstream URL in nginx config (comments mentioning the old name are OK to strip optionally)
if grep -RniE "https?://[^[:space:]]*onrender\.com" /etc/nginx/ 2>/dev/null; then
  echo "ERROR: live onrender URL found under /etc/nginx — remove it, then nginx -t && systemctl reload nginx" >&2
  exit 1
fi
# Optional: neutralize comment only (cosmetic; safe)
sed -i.bak-cut "s/evolve-perc-internet paused — Helsinki default/Helsinki default — no Render upstream/" "$SNIP" || true
nginx -t && systemctl reload nginx
echo "nginx: local :9478 proxy only OK"
'
```

If you **only** want a no-op confirm (no sed/reload):

```bash
ssh -i ~/.ssh/id_ed25519_restore_privacy_eu root@135.181.152.10 \
  'grep "proxy_pass http://127.0.0.1:9478/" /etc/nginx/snippets/rpt-perc-chain.conf && \
   ! grep -RniE "https?://[^[:space:]]*onrender\.com" /etc/nginx/ && echo nginx_ok'
```

---

## 3) Restart unit + verify health + env-grep

```bash
ssh -i ~/.ssh/id_ed25519_restore_privacy_eu root@135.181.152.10 'set -euo pipefail
systemctl restart rpt-perc-chain.service
systemctl is-active --quiet rpt-perc-chain.service
# Live env must not carry UPSTREAM key or onrender URL
! grep -E "^[[:space:]]*PERC_UPSTREAM_RENDEZVOUS_URL=" /opt/restore-privacy/perc_chain/helsinki.env
! grep -E "https?://[^[:space:]]*onrender\.com" /opt/restore-privacy/perc_chain/helsinki.env
# Loopback health after restart
for i in 1 2 3 4 5 6 7 8 9 10; do
  if curl -sS -m 3 "http://127.0.0.1:9478/health" | grep -q "\"ok\":true"; then break; fi
  sleep 1
done
curl -sS -m 5 "http://127.0.0.1:9478/health"
echo
echo "unit+env verify OK"
'
```

Public verify (laptop — after restart):

```bash
curl -sS -m 10 "https://135.181.152.10.sslip.io/perc/health" | tee /tmp/helsinki_health_postcut.json
python3 - <<'PY'
import json,sys
j=json.load(open("/tmp/helsinki_health_postcut.json"))
assert j.get("ok") is True, j
assert j.get("ledgerReady") is True, j
assert int(j.get("blockHeight") or 0) > 0, j
print("public_health_ok height=", j["blockHeight"], "tip=", j.get("tipHash","")[:16])
PY
ssh -i ~/.ssh/id_ed25519_restore_privacy_eu root@135.181.152.10 \
  '! grep -E "^[[:space:]]*PERC_UPSTREAM_RENDEZVOUS_URL=" /opt/restore-privacy/perc_chain/helsinki.env && \
   ! grep -E "https?://[^[:space:]]*onrender\\.com" /opt/restore-privacy/perc_chain/helsinki.env && echo env_cut_ok'
```

---

## 4) All-in-one (env cut + nginx confirm + restart + local health)

```bash
ssh -i ~/.ssh/id_ed25519_restore_privacy_eu root@135.181.152.10 'bash -s' \
  < perc_chain/deploy/cut_render_upstream.sh

```

Then re-run the public `curl` verify from section 3 on your laptop.

---

## Re-deploy

`scripts/deploy_perc_chain_helsinki.py` now stages
`PERC_UPSTREAM_RENDEZVOUS_URL=none` (solo Helsinki). Re-deploy no longer re-attaches
Render. To deliberately dual-seed again, set a real upstream URL in `helsinki.env`.

## Shipped script

Same procedure as a single file:

```bash
# From restore-privacy monorepo root (does not apply until you pipe to SSH)
cat perc_chain/deploy/cut_render_upstream.sh
ssh -i ~/.ssh/id_ed25519_restore_privacy_eu root@135.181.152.10 'bash -s' \
  < perc_chain/deploy/cut_render_upstream.sh
```

