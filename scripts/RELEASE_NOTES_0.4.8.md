# Release 0.4.8

## Catalog
- Product monopin **0.4.8** (`client/VERSION`, `status_page/downloads.py`, Flutter `productVersion` / pubspec)
- Residual catalog peers unchanged: **IS** `82.221.101.241:44044`, **RO** `185.146.232.107:44044`, **DE** `167.233.224.5:44044`
- Monthly **£2.45** / yearly GBP anchors unchanged
- Public status remains **title-only** (no live client count)

## What changed since 0.4.7 (human cadence)

### macOS client (native rebuild required)
- **Keygen paste** — Enter-licence and Settings keygen fields accept clipboard paste (Cmd+V / Paste control)
- **Keygen sheet dismisses** on valid unlock; navigator push/pop paired so the modal cannot stick open; auto-verify after paste of a product `RPT-KEY-…`
- VPN prepare / Allow only runs **after** the keygen sheet is fully closed
- **Connect** recreates and **enables** the system Packet Tunnel, then starts it so Network VPN toggles with the app (handles deleted Network configs)
- **Disconnect** stops the system Packet Tunnel (`stopVPNTunnel` + wait) so Network VPN goes down with the app
- Host missing `packet-tunnel-provider` is detected with Team residual re-sign guidance (public DevID omits host NE by design)

### Clients (this pin)
- Version monopin **0.4.8** across catalog filenames and Flutter pins
- Behaviour parity with 0.4.7 residual + Settings lean defaults

## Platform build honesty

| Platform | 0.4.8 status |
|----------|----------------|
| **Windows** | Carry-forward / pin rewrite from **0.4.7** multihop PE unless rebuilt on Windows |
| **Linux** | Rebuild via `package_linux.py` when tools present; else CF from 0.4.7 |
| **Android** | Residual-wire APK carry-forward from 0.4.7 when Flutter APK rebuild not run |
| **macOS** | **Native** Flutter **0.4.8** — Developer ID + **notarized + stapled** (notary `69a13d19-f47e-48bd-9647-404e8872d6de`) — see `client_app/APPLE_HANDOFF_0.4.8.md` |
| **iOS** | **Native** Flutter **0.4.8** — Apple Distribution **Team-signed** sideload; Connect enables + starts system Packet Tunnel, Disconnect stops it (parity with macOS product outcomes; Allow via iOS system VPN prompt / Settings) — same handoff |
| **Browser extension** | MV3 zip pin **0.4.8** when staged from `browser_extension/` |

Public DevID macOS packages omit host Network Extension so the app opens for all downloaders. Residual public IP on a developer Mac still requires Team residual re-sign (`scripts/sign_macos_residual_team.py`). Never claim notarized packages this process did not produce.

## Operator
```bash
python scripts/build_release_0.4.8.py
# Mac only for real Apple packages:
#   see client_app/APPLE_HANDOFF_0.4.8.md
python scripts/host_paid_assets_vps.py --stage --upload --version 0.4.8 --force
# or: scp to restore-privacy-iceland + sudo cp into /opt/restore-privacy/paid_assets/0.4.8/
gh release create 0.4.8 releases/0.4.8/* --title "0.4.8" --notes-file scripts/RELEASE_NOTES_0.4.8.md
```

## GitHub breadcrumbs (Apple)
- Branch / tag: **0.4.8** (or `release-0.4.8`)
- Handoff: `client_app/APPLE_HANDOFF_0.4.8.md`
- Assets: `restore-privacy-client-0.4.8-macos.zip`, `restore-privacy-client-0.4.8-ios.zip`
- Flutter: `version: 0.4.8+1`, `RptConfig.productVersion = '0.4.8'`
