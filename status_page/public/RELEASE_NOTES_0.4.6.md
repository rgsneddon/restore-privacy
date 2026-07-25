# Release 0.4.6

## Catalog
- Product monopin **0.4.6** (`client/VERSION`, `status_page/downloads.py`, Flutter `productVersion` / pubspec)
- Residual catalog peers unchanged: **IS** `82.221.101.241:44044`, **RO** `185.146.232.107:44044`, **DE** `167.233.224.5:44044` (user-selectable entry; multi-hop residual-via-exit when enabled)
- Monthly **£2.45** / yearly GBP anchors unchanged
- Public status remains **title-only** (no live client count)

## What changed since 0.4.5 (human cadence)

### Product / public web
- Homepage wipe box: **ALL NODES DATA CLEARED IN** countdown + sequential fleet wipe blurb (honest multi-node clear)
- Settings explainer / public chrome updates from the deploy-settings track as already on the status host
- Public **AUDIT** page: solid **RAG colour swatches** (green/amber/red) instead of broken square glyphs when source markdown had encoding glitches

### Operator / admin (not public live counts)
- Admin **fleet node usage** panel (bandwidth used vs capability) when `RPT_CAPACITY_TOKEN` is set on the status host and residual peers
- Durable `RPT_CAPACITY_TOKEN` + optional `RPT_NODE_BANDWIDTH_CAP_BPS` install path on residual nodes; product budgets IS/RO **100 Mbps**, DE **200 Mbps**
- RO Mac finalize handoff: `docs/RO_CAPACITY_MAC_FINALIZE.md` (SSH apply when Windows keys cannot reach RO)
- Render blueprint placeholders for capacity probe env (`render.yaml`; token never committed)

### Clients (this pin)
- Version monopin **0.4.6** across Windows PE / Linux package / Flutter / catalog filenames
- Behaviour parity with 0.4.5 residual + Settings lean defaults (optional scale off by default)

## Platform build honesty (this Windows operator host)

| Platform | 0.4.6 status |
|----------|----------------|
| **Windows** | Native multihop PE via `scripts/build_windows_multihop.py` when rebuild succeeds; else CF pin from 0.4.5 with honest note |
| **Linux** | Rebuild via `package_linux.py` when tools present; else CF from 0.4.5 + VERSION/pub rewrite |
| **Android** | Residual-wire APK carry-forward from 0.4.5 (or wire-complete prior) when Flutter APK rebuild not run |
| **macOS** | **CF filename pin** from 0.4.5 until Mac DevID + notarize rebuild — see `client_app/APPLE_HANDOFF_0.4.6.md` |
| **iOS** | **CF filename pin** from 0.4.5 until Mac Team-signed rebuild — same handoff |
| **Browser extension** | MV3 zip pin **0.4.6** when staged from `browser_extension/` |

Never claim notarized Apple packages or a native PE that this host did not produce.

## Operator
```bash
python scripts/build_release_0.4.6.py
# Mac only for real Apple packages:
#   see client_app/APPLE_HANDOFF_0.4.6.md
python scripts/host_paid_assets_vps.py --stage --upload --version 0.4.6 --force
gh release create 0.4.6 releases/0.4.6/* --title "0.4.6" --notes-file scripts/RELEASE_NOTES_0.4.6.md
```

## GitHub breadcrumbs (Apple)
- Branch / tag: **0.4.6** (or `release-0.4.6`)
- Handoff: `client_app/APPLE_HANDOFF_0.4.6.md`
- Assets (after Mac rebuild): `restore-privacy-client-0.4.6-macos.zip`, `restore-privacy-client-0.4.6-ios.zip`
- Flutter: `version: 0.4.6+1`, `RptConfig.productVersion = '0.4.6'`
