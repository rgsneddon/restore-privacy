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

Shared secret (same value on Iceland entry, Romania exit, Germany, and any future peers):

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
| `RPT_CAPACITY_TOKEN` | Node + client | Shared secret for private capacity endpoint |
| `RPT_NODE_MAX_SESSIONS` | Node | Soft max for utilization math (default 256) |
| `RPT_CAPACITY_PROBE_URLS` | Client | JSON host→URL map (optional) |
| `RPT_CAPACITY_PROBE_TIMEOUT` | Client | Probe timeout seconds (default ~1.5) |

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
