# Release 0.5.0

## Catalog monopin
- Product monopin **0.5.0**
- **Default residual entry: United States** (`5.161.242.85:44044`, pin `usa_node_elgamal.pub`)
- Selectable peers remain **IS** / **RO** / **US**

## Security audit timer
- Public audit countdown period is **1 day** (was ~4 hours)
- Countdown display is **days, hours, minutes, seconds** (`Dd HH:MM:SS`)
- Last-run timestamp is the honest `generated_at` from `scripts/run_security_audit.py --write`

## Apple packages
- macOS: Developer ID + notarize when secrets present
- iOS: Team-signed sideload when secrets present
- Built from current tree at monopin **0.5.0**

## Operator
```bash
python scripts/build_release_0.5.0.py --apple-only
# or full catalog (Apple native + non-Apple carry-forward from 0.4.10):
python scripts/build_release_0.5.0.py
RPT_SSH_USER=raskul RPT_SSH_SUDO=1 python scripts/host_paid_assets_vps.py --stage --upload --version 0.5.0 --force
```
