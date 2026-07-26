# Release 0.4.7

## Catalog
- Product monopin **0.4.7** (`client/VERSION`, `status_page/downloads.py`, Flutter `productVersion` / pubspec)
- Residual catalog peers unchanged: **IS** `82.221.101.241:44044`, **RO** `185.146.232.107:44044`, **DE** `167.233.224.5:44044` (user-selectable entry; multi-hop residual-via-exit when enabled)
- Monthly **£2.45** / yearly GBP anchors unchanged
- Public status remains **title-only** (no live client count)

## What changed since 0.4.6 (human cadence)

### macOS client (native rebuild required)
- **Keygen sheet dismisses** after a valid unlock (`paymentAllowsConnect`); invalid keys keep the sheet open with failure feedback
- **Window stays open after Connect** — no auto hide-to-tray / minimize on product residual success
- Packet Tunnel **pre-register** before Connect; prepare debounce only stamps success after tunnel save
- **Open VPN settings** control remains after open-settings feedback; System Settings opens on NE permission failures (`NEVPNErrorDomain` / residual not carrying)

### Operator / status host
- Payment DB migrate hardened against lock false-empty overwrite
- Licence and paid-grant history kept durable across path changes
- AUDIT UK ping matrix ordering and live host RTT preference (docs/status host)

### Clients (this pin)
- Version monopin **0.4.7** across catalog filenames and Flutter pins
- Behaviour parity with 0.4.6 residual + Settings lean defaults (optional scale off by default)

## Platform build honesty

| Platform | 0.4.7 status |
|----------|----------------|
| **Windows** | Carry-forward / pin rewrite from **0.4.6** multihop PE unless rebuilt on Windows |
| **Linux** | Rebuild via `package_linux.py` when tools present; else CF from 0.4.6 + VERSION/pub rewrite |
| **Android** | Residual-wire APK carry-forward from 0.4.6 when Flutter APK rebuild not run |
| **macOS** | **Native** Flutter **0.4.7** — Developer ID + **notarized + stapled** (notary `955cc8b1-aa51-45ec-8169-f9cc9fbc1950`) — see `client_app/APPLE_HANDOFF_0.4.7.md` |
| **iOS** | **Native** Flutter **0.4.7** — Apple Distribution **Team-signed** sideload — same handoff |
| **Browser extension** | MV3 zip pin **0.4.7** when staged from `browser_extension/` |

Never claim notarized packages that this process did not produce.

## Operator
```bash
python scripts/build_release_0.4.7.py
# Mac only for real Apple packages:
#   see client_app/APPLE_HANDOFF_0.4.7.md
python scripts/host_paid_assets_vps.py --stage --upload --version 0.4.7 --force
gh release create 0.4.7 releases/0.4.7/* --title "0.4.7" --notes-file scripts/RELEASE_NOTES_0.4.7.md
```

## GitHub breadcrumbs (Apple)
- Branch / tag: **0.4.7** (or `release-0.4.7`)
- Handoff: `client_app/APPLE_HANDOFF_0.4.7.md`
- Assets (after Mac rebuild): `restore-privacy-client-0.4.7-macos.zip`, `restore-privacy-client-0.4.7-ios.zip`
- Flutter: `version: 0.4.7+1`, `RptConfig.productVersion = '0.4.7'`
