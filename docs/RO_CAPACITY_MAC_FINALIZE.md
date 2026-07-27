# RO residual: finalize private capacity (Mac SSH)

Operator handoff for **Romania** catalog peer only. Use this from a machine that
already has SSH to RO (e.g. Mac). **Do not commit** real tokens.

| Field | Value |
|-------|--------|
| Peer code | **RO** |
| Host | `185.146.232.107` |
| Residual port | `44044/udp` (product tunnel) |
| UI / private capacity | `http://185.146.232.107:8080/api/private/capacity` |
| Product bandwidth allowance | **100 Mbps** = `RPT_NODE_BANDWIDTH_CAP_BPS=100000000` |
| Soft session max | `RPT_NODE_MAX_SESSIONS=256` (default) |
| Shared secret | Same `RPT_CAPACITY_TOKEN` as **IS** and **DE** (and status host) |

## Status elsewhere (context — not this Mac step)

| Peer | Host | Cap | Capacity token env |
|------|------|-----|--------------------|
| IS | `82.221.101.241` | 100 Mbps | Applied (Windows operator session) |
| US | `5.161.242.85` | 200 Mbps | Applied on-box; external **8080** may still need Hetzner **Cloud Firewall** |
| **RO** | `185.146.232.107` | **100 Mbps** | **This doc — apply from Mac SSH** |

Windows residual keys could not auth to RO (`publickey denied`). Private capacity
from the public internet previously returned **HTTP 404** (old UI without the
private route and/or no token). After apply + restart, authorized probe should
return JSON with `"private": true`.

## 1. Pull this branch on Mac

Primary breadcrumb branch (pushed for this handoff):

```bash
cd /path/to/restore-privacy   # or clone private repo
git fetch origin
git checkout ro-capacity-mac-finalize
git pull origin ro-capacity-mac-finalize
```

Includes `scripts/install_capacity_token_env.sh` with optional
`RPT_NODE_BANDWIDTH_CAP_BPS` and this doc. Full guide:
[CAPACITY_PROBES.md](CAPACITY_PROBES.md).

## 2. Same token as IS/DE (out-of-band — never git)

The production shared secret lives only on operator machines and residual
`/etc/restore-privacy/capacity.env` files — **not** in this repo.

Typical local path (copy between your own machines securely):

```text
~/.restore_privacy/capacity_token.txt
```

On Windows that file was used for IS/DE. On Mac, ensure the **same** 48-char
value is available before install, e.g.:

```bash
# After secure copy from your other machine / password manager:
mkdir -p ~/.restore_privacy
chmod 700 ~/.restore_privacy
# put the secret in ~/.restore_privacy/capacity_token.txt (mode 600)
chmod 600 ~/.restore_privacy/capacity_token.txt
export RPT_CAPACITY_TOKEN="$(tr -d '\r\n' < ~/.restore_privacy/capacity_token.txt)"
# optional integrity check (compare to known sha on your other machine — do not paste full token)
python3 -c "import hashlib,os; t=os.environ['RPT_CAPACITY_TOKEN']; print(hashlib.sha256(t.encode()).hexdigest()[:12], len(t))"
```

If you only have access on-box on **IS** (not the token file), you may read the
token as root from IS and install the **same** value on RO (still never commit):

```bash
# example only — run on a host you already trust as operator
# ssh raskul@82.221.101.241 'sudo grep ^RPT_CAPACITY_TOKEN= /etc/restore-privacy/capacity.env'
```

## 3. SSH to RO and install

Use whatever SSH user/key already works on your Mac (often `raskul` + sudo, or
`root`). From a checkout that has the install script:

```bash
export RO_HOST=185.146.232.107
export RPT_CAPACITY_TOKEN="$(tr -d '\r\n' < ~/.restore_privacy/capacity_token.txt)"

# Upload install helper if the remote tree is old or missing the script:
scp scripts/install_capacity_token_env.sh "${RO_SSH_USER:-raskul}@${RO_HOST}:/tmp/install_capacity_token_env.sh"

ssh "${RO_SSH_USER:-raskul}@${RO_HOST}" 'bash -s' <<EOF
set -euo pipefail
export RPT_CAPACITY_TOKEN='${RPT_CAPACITY_TOKEN}'
export RPT_NODE_BANDWIDTH_CAP_BPS=100000000
export RPT_NODE_MAX_SESSIONS=256
# Prefer tree install if present:
if [[ -f /opt/restore-privacy/scripts/install_capacity_token_env.sh ]]; then
  sudo -E bash /opt/restore-privacy/scripts/install_capacity_token_env.sh
elif [[ -f /tmp/install_capacity_token_env.sh ]]; then
  sudo -E bash /tmp/install_capacity_token_env.sh
else
  echo "missing install_capacity_token_env.sh" >&2
  exit 1
fi
# Open UI port if ufw is active (status host probes :8080)
if command -v ufw >/dev/null && sudo ufw status 2>/dev/null | grep -qi 'Status: active'; then
  sudo ufw allow 8080/tcp comment 'rpt status+private capacity' || true
fi
rm -f /tmp/install_capacity_token_env.sh
EOF
```

What the install script writes (mode `600`):

- `/etc/restore-privacy/capacity.env` — `RPT_CAPACITY_TOKEN`, `RPT_NODE_MAX_SESSIONS`, `RPT_NODE_BANDWIDTH_CAP_BPS`
- systemd drop-in `rpt-node.service.d/capacity-token.conf` → `EnvironmentFile=`
- restarts `rpt-node` when active

## 4. Verify on RO (no secret in logs)

```bash
ssh "${RO_SSH_USER:-raskul}@${RO_HOST}" 'bash -s' <<'EOF'
set -euo pipefail
sudo test -f /etc/restore-privacy/capacity.env
sudo stat -c 'mode=%a' /etc/restore-privacy/capacity.env   # expect 600
# Unauthorized → 401 when token is required
curl -sS -o /dev/null -w 'unauth_http=%{http_code}\n' http://127.0.0.1:8080/api/private/capacity
# Authorized (source env on box — do not paste token)
sudo bash -c 'set -a; source /etc/restore-privacy/capacity.env; set +a
  curl -sS -w "\nauth_http=%{http_code}\n" -H "Authorization: Bearer ${RPT_CAPACITY_TOKEN}" \
    http://127.0.0.1:8080/api/private/capacity
  echo
  echo "bw_cap=${RPT_NODE_BANDWIDTH_CAP_BPS:-unset}"
'
# Public stays title-only
curl -sS http://127.0.0.1:8080/api/status; echo
EOF
```

Expect:

- `unauth_http=401` (or refuse) when token configured
- `auth_http=200` and JSON including `"private": true`, `"capacity"`, `"live"`
- `bw_cap=100000000`
- public body title-only, e.g. `{"title": "RESTORE PRIVACY"}`

External check from Mac:

```bash
export RPT_CAPACITY_TOKEN="$(tr -d '\r\n' < ~/.restore_privacy/capacity_token.txt)"
curl -sS -o /dev/null -w 'unauth=%{http_code}\n' http://185.146.232.107:8080/api/private/capacity
curl -sS -H "Authorization: Bearer ${RPT_CAPACITY_TOKEN}" \
  http://185.146.232.107:8080/api/private/capacity; echo
curl -sS http://185.146.232.107:8080/api/status; echo
```

If private route is still **404**, the running node UI is older than the private
capacity handler — redeploy node code from this branch (`scripts/deploy_rpt_node.py`
with `RPT_SSH_HOST=185.146.232.107`) then re-run install.

## 5. Status host / admin panel (if not already)

Render Dashboard → service **restore-privacy-status** → Environment (secrets never
in git):

```bash
RPT_CAPACITY_TOKEN=<same as residual nodes>
RPT_BANDWIDTH_CAP_BPS_MAP={"82.221.101.241":100000000,"185.146.232.107":100000000,"5.161.242.85":200000000,"IS":100000000,"RO":100000000,"US":200000000}
RPT_CAPACITY_PROBE_TIMEOUT=2.5
```

Blueprint placeholders: `render.yaml` (`RPT_CAPACITY_TOKEN` is `sync: false`).

After RO is healthy, `/admin` fleet usage should show RO **ok** (or live session
fields) instead of HTTP 404 / token-missing.

## Related

- [CAPACITY_PROBES.md](CAPACITY_PROBES.md) — full private capacity guide
- [NODE_WIPE_REINSTALL.md](NODE_WIPE_REINSTALL.md) — re-apply token after wipe
- `scripts/install_capacity_token_env.sh` — durable node install
- `scripts/hop_env.example` — placeholders only
