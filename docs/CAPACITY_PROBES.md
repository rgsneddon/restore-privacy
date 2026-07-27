# Private residual capacity probes

Clients can automatically residual-dial a freer catalog peer when the preferred
node is **near connection capacity**. That needs a **private** capacity signal —
not a public live client counter.

## Honesty

| Surface | Behavior |
|---------|----------|
| Public `/api/status` / HTML UI | **Title only** — no `live`, `utilization`, or session lists |
| Private `/api/private/capacity` | Token-gated; returns utilization for residual load hints only |
| Without `RPT_CAPACITY_TOKEN` | Probes disabled (empty map; no capacity migration from probes) |
| Probe failure / timeout | Fail-soft — that host is **unknown** (no invented load) |

Not multi-VPS consensus load balancing. Migration applies on **connect / residual
re-select**, not a guaranteed mid-session cutover of all online clients.

## Enable on residual nodes

**Firewall note:** If you enable `ufw`, always allow SSH **before** `--force enable`:

```bash
ufw allow OpenSSH
ufw allow 22/tcp
ufw allow 44044/udp
```

Shared secret (same value on United States, Iceland, Romania, and any future peers):

```bash
# On each residual node (root)
sudo bash scripts/install_capacity_token_env.sh
# Or set explicitly:
# sudo env RPT_CAPACITY_TOKEN='your-long-random-secret' bash scripts/install_capacity_token_env.sh
```

This writes:

- `/etc/restore-privacy/capacity.env` (mode `600`, not for git)
- systemd drop-in `rpt-node.service.d/capacity-token.conf` → `EnvironmentFile=`

Restarts `rpt-node` when active so the UI process sees the token.

Optional node-side soft max for `utilization = live / max`:

```bash
# in capacity.env or process env
RPT_NODE_MAX_SESSIONS=256
```

Optional **operator bandwidth allowance** (bits/s) for the admin fleet panel
(used-vs-cap). This is a product budget, **not** auto-detected NIC line-rate:

```bash
# 100 Mbps = 100000000 ; 200 Mbps = 200000000
sudo env RPT_CAPACITY_TOKEN='…' RPT_NODE_BANDWIDTH_CAP_BPS=100000000 \
  bash scripts/install_capacity_token_env.sh
```

Catalog product budgets (operator reference):

| Peer | Host | Allowance |
|------|------|-----------|
| IS Iceland | `82.221.101.241` | 100 Mbps (`100000000`) |
| RO Romania | `185.146.232.107` | 100 Mbps (`100000000`) |
| US United States | `5.161.242.85` | 200 Mbps (`200000000`) |

**RO still needs operator finalize from a host with SSH** (Mac): copy-paste
install + verify steps in **[RO_CAPACITY_MAC_FINALIZE.md](RO_CAPACITY_MAC_FINALIZE.md)**.
IS/US token env were applied separately; RO was blocked from Windows keys.

## Enable on status host (admin fleet panel)

The private `/admin` fleet usage section probes each catalog peer’s
`/api/private/capacity`. Set the **same** token on the status host (Render
Dashboard → Environment) plus optional cap map so rows show capability even when
a peer omits `bandwidth_cap_bps` in its private payload:

```bash
# Render / status host — never commit the real token
RPT_CAPACITY_TOKEN=<same as residual nodes>
# JSON host or code → bits/s (not secret; product allowances)
RPT_BANDWIDTH_CAP_BPS_MAP={"82.221.101.241":100000000,"185.146.232.107":100000000,"5.161.242.85":200000000,"IS":100000000,"RO":100000000,"US":200000000}
RPT_CAPACITY_PROBE_TIMEOUT=2.5
```

Local token file (operator machine only, not git):
`~/.restore_privacy/capacity_token.txt` (or `%USERPROFILE%\.restore_privacy\capacity_token.txt`).

**Firewall:** residual UI port **8080/tcp** must be reachable from the status host
for live admin rows. Host `ufw allow 8080/tcp` is not enough on Hetzner if a
**Cloud Firewall** still drops 8080 — open 8080/tcp there too (SSH 22 and residual
44044/udp already required). Public `/api/status` stays title-only either way.

## Enable on clients (probe path)

Operator or env-capable Connect processes (not required inside public end-user
installers):

```bash
export RPT_CAPACITY_TOKEN='same-secret-as-nodes'
# optional:
# export RPT_CAPACITY_PROBE_TIMEOUT=1.5
# export RPT_CAPACITY_PROBE_URLS='{"82.221.101.241":"http://82.221.101.241:8080/api/private/capacity",...}'
```

Default URL map (when token is set and `RPT_CAPACITY_PROBE_URLS` is unset):

`http://{catalog-peer-host}:8080/api/private/capacity`

## Env reference

| Variable | Who | Purpose |
|----------|-----|---------|
| `RPT_CAPACITY_TOKEN` | Node + client + status host | Shared secret for private capacity endpoint |
| `RPT_NODE_MAX_SESSIONS` | Node | Soft max for utilization math (default 256) |
| `RPT_NODE_BANDWIDTH_CAP_BPS` | Node | Soft operator bandwidth allowance (bits/s) |
| `RPT_BANDWIDTH_CAP_BPS_MAP` | Status host | JSON host/code → bits/s for admin fleet panel |
| `RPT_CAPACITY_PROBE_URLS` | Client | JSON host→URL map (optional) |
| `RPT_CAPACITY_PROBE_TIMEOUT` | Client / status host | Probe timeout seconds (default ~1.5) |

## Code map

| Path | Role |
|------|------|
| `node/private_capacity.py` | Payload + token authorize |
| `node/ui.py` | `/api/private/capacity` (token) vs public status |
| `client/capacity_probe.py` | Fail-soft probe → host utilization map |
| `client/connect.py` | Probe inject before residual select |
| `client/multihop.py` | Near-capacity residual migration + CLI advisory |
| `scripts/install_capacity_token_env.sh` | Durable node env install |
| `scripts/hop_env.example` | Operator env template (placeholders only) |
| `docs/RO_CAPACITY_MAC_FINALIZE.md` | RO-only Mac SSH finalize handoff |

## Verify (no secret in logs)

```bash
# On node: token file exists and is not world-readable
sudo test -f /etc/restore-privacy/capacity.env && sudo stat -c '%a' /etc/restore-privacy/capacity.env
# Expect 600

# Unauthorized private capacity → 401
curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8080/api/private/capacity
# Expect 401 when token required

# Authorized (token from env file — do not paste into chat/logs)
# source /etc/restore-privacy/capacity.env
# curl -sS -H "Authorization: Bearer $RPT_CAPACITY_TOKEN" http://127.0.0.1:8080/api/private/capacity
```

Public status must stay title-only:

```bash
curl -sS http://127.0.0.1:8080/api/status
# {"title": "RESTORE PRIVACY"} (or product title only)
```
