# Release 0.4.5

## Catalog
- Product monopin **0.4.5** (`client/VERSION`, `status_page/downloads.py`, Flutter `productVersion` / pubspec)
- Windows residual PE rebuilt on Windows x64 (multihop freeze) with current tree: dark/light mode beside settings cog, Settings wheel/trackpad scroll, Quit status + off-UI-thread residual teardown, price-banner font alignment on status host
- Settings lean defaults unchanged (startup/autoconnect/shape/obfs/multihop off; residual core always on)
- Monthly **£2.45** / yearly GBP anchors unchanged

## Platform build honesty (this Windows operator host)

| Platform | 0.4.5 status |
|----------|----------------|
| **Windows** | **Native multihop PE** via `scripts/build_windows_multihop.py` (MZ, pin 0.4.5) |
| **Linux** | Rebuilt via `package_linux.py` when tools present; else CF from 0.4.4 + VERSION pin |
| **Android** | Residual-wire APK **carry-forward** from 0.4.4 filename pin (Flutter SDK may be absent) |
| **macOS** | **Native Flutter rebuild** + **Developer ID** signed + **notarized/stapled** (notary id `dcb07f98-7b2b-45c2-8173-ee4865df464e`; see `client_app/APPLE_HANDOFF_0.4.5.md`) |
| **iOS** | **Native Flutter rebuild** + **Apple Distribution Team-signed** sideload zip (`CFBundleShortVersionString` 0.4.5) |
| **Browser extension** | MV3 zip pin **0.4.5** from `browser_extension/` when staged |

Never claim notarized Apple packages or a native PE that this host did not produce.

## Operator
```bash
python scripts/build_release_0.4.5.py
# Mac only for real Apple packages:
#   see client_app/APPLE_HANDOFF_0.4.5.md
gh release create 0.4.5 releases/0.4.5/* --title "0.4.5" --notes-file scripts/RELEASE_NOTES_0.4.5.md
python scripts/host_paid_assets_vps.py --stage --version 0.4.5
```

## GitHub breadcrumbs (Apple)
- Tag / release: **0.4.5**
- Assets: `restore-privacy-client-0.4.5-macos.zip`, `restore-privacy-client-0.4.5-ios.zip`
- Handoff: `client_app/APPLE_HANDOFF_0.4.5.md`
- Flutter: `version: 0.4.5+1`, `RptConfig.productVersion = '0.4.5'`