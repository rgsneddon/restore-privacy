# perc_chain on Helsinki — Restore Privacy Suite v1.0.1

## Why Helsinki

The paid Render service **`evolve-perc-internet.onrender.com` is paused to save money**.
Do **not** re-enable it by default. The suite and wallet/evolve clients use the
Helsinki-hosted perc_chain internet node as the default rendezvous.

| Item | Value |
|------|--------|
| Host | `135.181.152.10` (Helsinki store / suite chain) |
| Remote root | `/opt/restore-privacy/perc_chain` |
| Backend port | `9478` (loopback; behind nginx) |
| Public health | `GET https://135.181.152.10.sslip.io/perc/health` |
| Public endpoint env | `PERC_PUBLIC_ENDPOINT=https://135.181.152.10.sslip.io/perc` |

Client config: `assets/config/perc_network.json` → `rendezvousUrl` =
`https://135.181.152.10.sslip.io/perc` (or `--dart-define=PERC_RENDEZVOUS_URL=...`).

Raw `:9478` is not opened at the cloud edge; nginx `/perc/` on 80/443/8081 is the public path.

## Redeploy (any host)

From the monorepo root (`restore-privacy/`):

```bash
# Package + dry-run (no SSH required)
python3 scripts/deploy_perc_chain_helsinki.py --package --dry-run

# Local run (bind 127.0.0.1 for health check)
python3 scripts/deploy_perc_chain_helsinki.py --local-run --port 9478

# Live install on Helsinki (needs SSH keys)
export RPT_SSH_HOST=135.181.152.10 RPT_SSH_USER=root
export RPT_SSH_KEY=~/.ssh/id_ed25519_restore_privacy_eu
python3 scripts/deploy_perc_chain_helsinki.py --package --upload --install-service
```

Docker (when available):

```bash
cd perc_chain
docker build -t rpt-perc-chain:1.0.1 .
docker run -d --name rpt-perc-chain -p 9478:9478 \
  -e PERC_PUBLIC_ENDPOINT=http://135.181.152.10:9478 \
  -v /opt/restore-privacy/perc_chain/data:/var/data \
  rpt-perc-chain:1.0.1
```

## Operator note

**evolve-perc-internet is paused to save money.** Point suite clients at Helsinki
(or an env override). Re-enabling Render requires an explicit operator decision
and is out of the default suite path.
