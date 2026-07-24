# Release 0.4.4

## Catalog
- Product monopin **0.4.4** (`client/VERSION`, `status_page/downloads.py`, Flutter `productVersion` / pubspec)
- Windows residual PE rebuilt on Windows x64 (multihop freeze) with current tree: first-run keygen → settings, neon UI, firewall allows, **kill-switch parked**
- Settings lean defaults unchanged (startup/autoconnect/shape/obfs/multihop off; residual core always on)
- Monthly **£2.45** / yearly GBP anchors unchanged

## Platform build honesty (this Windows operator host)

| Platform | 0.4.4 status |
|----------|----------------|
| **Windows** | **Native multihop PE** via `scripts/build_windows_multihop.py` (MZ, pin 0.4.4) |
| **Linux** | Rebuilt via `package_linux.py` when tools present; else CF from 0.4.2 + VERSION pin |
| **Android** | Residual-wire APK **carry-forward** from 0.4.2 filename pin (Flutter SDK may be absent) |
| **macOS** | **Carry-forward** prior zip as `…-0.4.4-macos.zip` until Mac rebuild + DevID notarize (see `client_app/APPLE_HANDOFF_0.4.4.md`) |
| **iOS** | **Carry-forward** prior zip as `…-0.4.4-ios.zip` until Mac Team-signed rebuild |
| **Browser extension** | MV3 zip pin **0.4.4** from `browser_extension/` when staged |

Never claim notarized Apple packages or a native PE that this host did not produce.

## Operator
```bash
python scripts/build_release_0.4.4.py
# Mac only for real Apple packages:
#   see client_app/APPLE_HANDOFF_0.4.4.md
gh release create 0.4.4 releases/0.4.4/* --title "0.4.4" --notes-file scripts/RELEASE_NOTES_0.4.4.md
python scripts/host_paid_assets_vps.py --stage --version 0.4.4
```

## GitHub breadcrumbs (Apple)
- Tag / release: **0.4.4**
- Assets: `restore-privacy-client-0.4.4-macos.zip`, `restore-privacy-client-0.4.4-ios.zip`
- Handoff: `client_app/APPLE_HANDOFF_0.4.4.md`
- Flutter: `version: 0.4.4+1`, `RptConfig.productVersion = '0.4.4'`
