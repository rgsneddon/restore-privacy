# Release 0.5.1

## Catalog monopin
- Product monopin **0.5.1**
- **Default residual entry: United States** (`5.161.242.85:44044`)
- Selectable peers remain **IS** / **RO** / **US**

## Highlights
- Admin **one-month tester** mint (download + keygen; PPI `TESTER - one month`) under Generate KEYGEN failsafe
- **Keygen portability:** Active `RPT-KEY-…` re-applies on newer monopin builds (subscription-scoped)
- Licence period / auto-renew fail-closed (month/year expire without renew; auto-renew extends only after successful payment)
- Discrete **Quit** (stop tunnel then exit) is in the Flutter product tree for the next **native** Apple rebuild; **current paid** Apple zips are CF and may not include it yet

## Package honesty (this ship — VPS paid assets)

| Platform | What is on VPS / paid catalog |
|----------|-------------------------------|
| **Windows** | **Native** multihop PE rebuild for **0.5.1** (Windows x64 host) |
| **Linux** | **Native** rebuild for **0.5.1** |
| **Android** | **Carry-forward** residual-wire from prior pin, catalog filename **0.5.1** |
| **macOS** | **Honest carry-forward** — filename **0.5.1** only. Internal `CFBundleShortVersionString` may still be **pre-0.5.1** (observed **0.2.3**). **Not** Developer ID / notarized native 0.5.1 until Mac handoff rebuild is uploaded |
| **iOS** | **Honest carry-forward** — filename **0.5.1** only. Internal bundle version may still be pre-0.5.1. **Not** native monopin 0.5.1 until Mac Team-sign rebuild is uploaded |

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

## Docs
- `client_app/APPLE_HANDOFF_0.5.1.md`
- `client/windows/WINDOWS_HANDOFF_0.5.1.md`
