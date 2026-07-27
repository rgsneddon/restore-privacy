# Release 0.5.1

## Catalog monopin
- Product monopin **0.5.1**
- **Default residual entry: United States** (`5.161.242.85:44044`, pin `us_node_elgamal.pub` / product US pub)
- Selectable peers remain **IS** / **RO** / **US** (Germany residual peer remains **retired**)

## This pin (relative to 0.5.0)
- Admin **one-month tester** mint (download + keygen, PPI `TESTER - one month`) under Generate KEYGEN failsafe
- Licence period / auto-renew fail-closed behaviour retained (month/year expire without renew; auto-renew extends only after successful payment)
- Public product tabs (VPN / Browser / Vault) and fleet capacity docs from 0.5.0 lineage

## Platform package honesty (this ship)

| Platform | What is on VPS / paid catalog |
|----------|-------------------------------|
| **Windows** | **Native** multihop PE rebuild for **0.5.1** when built on Windows x64 (`build_windows_multihop` / `build_release_0.5.1.py`) |
| **Linux** | **Native** rebuild for **0.5.1** |
| **Android** | **Carry-forward** residual-wire from **0.5.0** (or **0.4.10** wire), catalog filename **0.5.1** when SDK rebuild absent |
| **macOS** | **Carry-forward** prior Apple zip renamed to **0.5.1**. Filename is catalog pin only — internal `CFBundleShortVersionString` may still be **pre-0.5.1** (e.g. **0.2.3**). **Not** a native Developer ID / notarized 0.5.1 build until Mac handoff |
| **iOS** | **Carry-forward** prior Team-signed zip renamed to **0.5.1**. Internal bundle version may still be pre-0.5.1. **Not** native monopin 0.5.1 until Mac Team-sign rebuild |

## Apple packages (operator honesty)

- When built on a **Mac with secrets**, macOS can be Developer ID + notarize and iOS Team-signed **at monopin 0.5.1** (see `client_app/APPLE_HANDOFF_0.5.1.md`).
- **Current Windows-host publish** stages **honest CF** Apple zips (prior wire + filename pin). Do not treat CF zips as notarized 0.5.1 seals.

## Operator
```bash
# Full catalog on Windows host (native Win/Linux; CF Android/Apple when no Mac rebuild):
python scripts/build_release_0.5.1.py
# Mac Apple-native only (after flutter build + secrets):
python scripts/build_release_0.5.1.py --apple-only
RPT_SSH_USER=raskul RPT_SSH_SUDO=1 python scripts/host_paid_assets_vps.py --stage --upload --version 0.5.1 --force
```
