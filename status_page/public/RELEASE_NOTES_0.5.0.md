# Release 0.5.0

## Catalog monopin
- Product monopin **0.5.0**
- **Default residual entry: United States** (`5.161.242.85:44044`, pin `us_node_elgamal.pub` / product US pub)
- Selectable peers remain **IS** / **RO** / **US** (Germany residual peer remains **retired**)

## Security audit timer
- Public audit countdown period is **1 day** (was ~4 hours)
- Countdown display is **days, hours, minutes, seconds** (`Dd HH:MM:SS`)
- Last-run timestamp is the honest `generated_at` from `scripts/run_security_audit.py --write`

## Platform package honesty (this ship)

| Platform | What is on VPS / paid catalog |
|----------|-------------------------------|
| **Windows** | **Native** multihop PE rebuild for **0.5.0** (flags, brand taskbar icon, residual attach fixes) |
| **Linux** | **Native** rebuild for **0.5.0** |
| **Android** | **Carry-forward** residual-wire APK from **0.4.10**, catalog filename **0.5.0** |
| **macOS** | **Carry-forward** prior Apple zip renamed to **0.5.0**. Filename is catalog pin only — internal `CFBundleShortVersionString` may still be **pre-0.5.0** (e.g. **0.2.3**). **Not** a native Developer ID / notarized 0.5.0 build until Mac handoff |
| **iOS** | **Carry-forward** prior Team-signed zip renamed to **0.5.0**. Internal bundle version may still be pre-0.5.0. **Not** native monopin 0.5.0 until Mac Team-sign rebuild |

## Apple packages (operator honesty)

- When built on a **Mac with secrets**, macOS can be Developer ID + notarize and iOS Team-signed **at monopin 0.5.0** (see `client_app/APPLE_HANDOFF_0.5.0.md`).
- **Current Windows-host publish** stages **honest CF** Apple zips (prior wire + filename pin). Do not treat CF zips as notarized 0.5.0 seals.

## Operator
```bash
# Full catalog on Windows host (native Win/Linux; CF Android/Apple when no Mac rebuild):
python scripts/build_release_0.5.0.py
# Mac Apple-native only (after flutter build + secrets):
python scripts/build_release_0.5.0.py --apple-only
RPT_SSH_USER=raskul RPT_SSH_SUDO=1 python scripts/host_paid_assets_vps.py --stage --upload --version 0.5.0 --force
```
