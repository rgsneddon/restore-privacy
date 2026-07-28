# Release 0.5.1

## Catalog monopin
- Product monopin **0.5.1**
- **Default residual entry: United States** (`5.161.242.85:44044`)
- Selectable peers remain **IS** / **RO** / **US**

## Highlights
- Admin **one-month tester** mint (download + keygen; PPI `TESTER - one month`) under Generate KEYGEN failsafe
- **Keygen portability:** Active `RPT-KEY-…` re-applies on newer monopin builds (subscription-scoped)
- Licence period / auto-renew fail-closed
- Discrete **Quit** (stop tunnel then exit) on Flutter main connection screen (macOS/iOS)
- **macOS CFBundle always == monopin** — release/stage refuse carry-forward zips with stale `CFBundleShortVersionString`

## Package honesty (this ship — VPS paid assets)

| Platform | What is on VPS / paid catalog |
|----------|-------------------------------|
| **Windows** | **Native** multihop PE rebuild for **0.5.1** (Windows x64 host) or CF until Windows rebuild |
| **Linux** | **Native** rebuild for **0.5.1** when package path runs; else CF with honest notes |
| **Android** | **Carry-forward** residual-wire from prior pin, catalog filename **0.5.1** |
| **macOS** | **Native** monopin **0.5.1** — host `CFBundleShortVersionString` **0.5.1** (DevID + notarize when secrets present). Publish **fails closed** if CFBundle ≠ monopin |
| **iOS** | **Native** monopin **0.5.1** sideload when built on Mac |

## Operator

```bash
# Mac Apple-native (CFBundle gate):
python3 scripts/build_release_0.5.1.py --apple-only
RPT_SSH_USER=raskul RPT_SSH_SUDO=1 python3 scripts/host_paid_assets_vps.py --stage --upload --version 0.5.1 --force
```

## Docs
- `client_app/APPLE_HANDOFF_0.5.1.md`
- `client/windows/WINDOWS_HANDOFF_0.5.1.md`
