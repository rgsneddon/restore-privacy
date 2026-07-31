# Restore Privacy Suite v 1.0.0

Unified product shell over residual VPN, Perccent wallet, and Evolve Chronoflux.

## Tabs

| Tab | Label | Surface |
|-----|-------|---------|
| 0 | **VPN** | Residual tunnel home (`TunnelHome`) |
| 1 | **%** | Perccent / MY PERC wallet (`WalletBootstrapScreen` via path dep `perccent_wallet`) |
| 2 | **EVOLVE** | Full Evolve app (`AppBootstrapScreen` via path dep `evolve`) |

Tab switch uses `IndexedStack` — no process relaunch.

## Version monopin

- Display: **Restore Privacy Suite v 1.0.0**
- Sources: `lib/suite_version.dart`, `lib/rpt_config.dart`, `pubspec.yaml`, `../client/VERSION`, catalog `status_page/downloads.py`

## Perccent chain (Helsinki)

**evolve-perc-internet (Render) is paused to save money.** Do not re-enable it by default.

| Item | Value |
|------|--------|
| Host | `135.181.152.10` |
| Public rendezvous | `https://135.181.152.10.sslip.io/perc` |
| Health | `GET https://135.181.152.10.sslip.io/perc/health` |
| Backend | `127.0.0.1:9478` + systemd `rpt-perc-chain.service` |
| Config asset | `assets/config/perc_network.json` |

## Redeploy

From monorepo root (`restore-privacy/`):

```bash
# Suite catalog + perc_chain package (no SSH)
python3 scripts/package_restore_privacy_suite.py --list
python3 scripts/package_restore_privacy_suite.py --stage --dry-run
python3 scripts/package_restore_privacy_suite.py --stage
python3 scripts/package_restore_privacy_suite.py --build-commands

# Chain only
python3 scripts/deploy_perc_chain_helsinki.py --package --dry-run
python3 scripts/deploy_perc_chain_helsinki.py --local-run --port 9478
python3 scripts/deploy_perc_chain_helsinki.py --package --upload --install-service
```

Platform build commands (one each): see `--build-commands` output for windows, android, macos, ios, linux.
