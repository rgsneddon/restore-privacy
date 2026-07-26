# Release 0.4.8

## Catalog
- Product monopin **0.4.8** (`client/VERSION`, `status_page/downloads.py`, Flutter `productVersion` / pubspec)
- Residual catalog peers unchanged: **IS** `82.221.101.241:44044`, **RO** `185.146.232.107:44044`, **DE** `167.233.224.5:44044` (user-selectable entry; multi-hop residual-via-exit when enabled)
- Monthly **£2.45** / yearly GBP anchors unchanged
- Public status remains **title-only** (no live client count)

## What changed since 0.4.6 (human cadence)

### Product chrome
- Banner branding: **Virtual Private Network** (no longer “UK VPN”) on desktop + Flutter shells
- **Main-shell country picker** above Connect on Windows, Linux, and Flutter: **Iceland / Romania / Germany** with flag labels; default **IS**; selection drives residual entry

### Windows Connect / Disconnect / Quit (feel faster)
- **Connect warm path:** skip serial status-host bootstrap/refresh when local active + keygen already allows Connect (background refresh still runs); capacity re-probes non-force + parallel peers
- **Disconnect / Quit:** no redundant full residual restore after teardown; post-TUN second pass is routes-only; residual shell cmd timeouts capped at 5s

### Other monorepo work included in this pin
- Stripe custom email domain + DMARC operator helpers/docs
- Capacity migration helpers restored on multihop path (IS/RO/DE catalog)
- Prior 0.4.6 operator/admin fleet usage and public chrome fixes remain

## Platform build honesty

| Platform | 0.4.8 status |
|----------|----------------|
| **Windows** | Native multihop PE via `scripts/build_windows_multihop.py` when rebuild succeeds; else CF pin from **0.4.6** with honest note |
| **Linux** | Rebuild via `package_linux.py` when tools present; else CF from **0.4.6** + VERSION/pub rewrite |
| **Android** | Residual-wire APK rebuild when SDK present; else CF from **0.4.6** |
| **macOS** | Flutter+DevID when Mac+secrets; else **honest CF** from 0.4.6 (Mac must rebuild/notarize for real 0.4.8 seal) |
| **iOS** | Flutter+Team-sign when Mac+secrets; else **honest CF** from 0.4.6 |
| **Browser extension** | MV3 zip pin **0.4.8** when staged from `browser_extension/` |

Never claim notarized packages that this process did not produce.

## Operator
```bash
python scripts/build_release_0.4.8.py
# Mac only for real Apple packages:
#   see client_app/APPLE_HANDOFF_0.4.8.md
python scripts/host_paid_assets_vps.py --stage --upload --version 0.4.8 --force
gh release create 0.4.8 releases/0.4.8/* --title "0.4.8" --notes-file scripts/RELEASE_NOTES_0.4.8.md
```

## GitHub breadcrumbs (Apple)
- Branch / tag: **0.4.8** (or `release-0.4.8`)
- Handoff: `client_app/APPLE_HANDOFF_0.4.8.md`
- Assets: `restore-privacy-client-0.4.8-macos.zip`, `restore-privacy-client-0.4.8-ios.zip`
- Flutter: `version: 0.4.8+1`, `RptConfig.productVersion = '0.4.8'`
