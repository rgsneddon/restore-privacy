# Apple platforms prep (iOS + macOS)

Build and sign on a **Mac** with Xcode. This Windows checkout only prepares sources, icons, docs, and native stubs.

| Platform | UI | Full-system VPN |
|----------|----|-----------------|
| **iOS** | Flutter `Runner` | **Packet Tunnel** Network Extension (`NEPacketTunnelProvider`) |
| **macOS** | Flutter `Runner` | **Network Extension** (Packet Tunnel) and/or System Extension |

## Shared product rules (do not change)

| Item | Value / location |
|------|------------------|
| Endpoint | `104.156.224.47:44044` UDP (`lib/rpt_config.dart`) |
| Protocol | **RPT2** (not WireGuard / OpenVPN) — see `client/connect.py`, `node/handshake.py` |
| Method channel | **`restore_privacy/vpn`** — methods `connect`, `disconnect` (see `lib/vpn_controller.dart`) |
| Connect args | `host`, `port`, `fullTunnel`, `sessionName`, `route`, `autoConnect` |
| Result map | `{ ok: bool, message: String, vpnIp?: String }` — use `lib/connect_status.dart` |
| UI | Retro: banner `#000080`, black bg, white text; scrolling privacy string in `lib/theme.dart` |
| Auto-connect | On launch (`RptConfig.autoConnectOnLaunch`) |
| Full tunnel | `0.0.0.0/0` intent |
| UK IP gate | Client-side: only United Kingdom public IPs (mirror `client/uk_gate.py` / Android `UkIpGate.kt`) |
| Brand icons | Already under `ios/.../AppIcon.appiconset` and `macos/.../AppIcon.appiconset` |

## Secrets (never commit `*.priv`)

Required admission files (product client, **not** node private key):

- `client_ed25519.priv` — 32 raw bytes  
- `node_elgamal.pub` — node ElGamal public key bytes  

**Do not** ship `node_elgamal.priv` in any app or extension.

Suggested placement on Mac:

```text
# App-group container or extension resource (preferred for Packet Tunnel):
~/Library/Group Containers/<TEAMID>.com.restoreprivacy.shared/secrets/

# Or developer copy for local runs:
~/.restore-privacy/secrets/client_ed25519.priv
~/.restore-privacy/secrets/node_elgamal.pub
```

Copy from the VPN node (operator machine only):

```bash
# example — from a machine that can SSH to the node
scp root@104.156.224.47:/opt/restore-privacy/secrets/client_ed25519.priv \
    root@104.156.224.47:/opt/restore-privacy/secrets/node_elgamal.pub \
    ~/.restore-privacy/secrets/
```

## On your MacBook — quick start

```bash
git clone <your-repo-url> restore_privacy   # or pull latest
cd restore_privacy/client_app
flutter pub get

# iOS
open ios/Runner.xcworkspace
# or: flutter build ios --no-codesign   then sign in Xcode

# macOS
flutter run -d macos
# or: flutter build macos
```

Then follow:

- [ios/BUILD_ON_MAC.md](ios/BUILD_ON_MAC.md) — Packet Tunnel + signing  
- [macos/BUILD_ON_MAC.md](macos/BUILD_ON_MAC.md) — Network Extension + notarization  

Native prep stubs (drag into Xcode targets as described in those docs):

- `ios/NativePrep/` — method channel + Packet Tunnel skeleton  
- `macos/NativePrep/` — method channel + Packet Tunnel skeleton  
- `ios/NativePrep/RPT_PROTOCOL.md` — handshake/DATA outline for Swift  

## What is already implemented (this tree)

1. Shared Swift **RPT2 engine** under `apple_shared/Rpt2/` (also copied into `ios/NativePrep/Rpt2` and `macos/NativePrep/Rpt2`) with unit tests: `cd client_app/apple_shared/Rpt2 && swift test`.  
2. **Packet Tunnel** targets (`ios/PacketTunnel`, `macos/PacketTunnel`) implementing UK gate → secrets → handshake → full-tunnel settings → packetFlow/UDP DATA + keepalive.  
3. Host method channel `restore_privacy/vpn` registered from iOS `AppDelegate` / macOS `MainFlutterWindow`; starts NE when available, otherwise runs the real host-side RPT2 connect sequence (not a permanent stub).  
4. Secrets helpers load **only** `client_ed25519.priv` + `node_elgamal.pub` (never `node_elgamal.priv`).

## What you must finish for device VPN (Apple Developer)

1. Apple Developer team + App IDs with **Network Extensions** entitlement.  
2. Enable App Groups + Packet Tunnel entitlements on Runner + PacketTunnel (see `NativePrep/Runner.entitlements.example` and `PacketTunnel/PacketTunnel.entitlements`).  
3. Load secrets into a location the extension can read (App Group recommended).  
4. Code sign, Archive, distribute / notarize.

## Success criteria on Mac

- Flutter UI launches and auto-connects.  
- Channel `restore_privacy/vpn` returns real session results (not “extension not configured”).  
- Full tunnel: device traffic exits via the RPT node when connected.  
- No `node_elgamal.priv` in the app bundle.

## Gatekeeper (macOS downloads)

Published macOS zips must be **Developer ID signed and notarized** so users are not blocked by
*Apple could not verify “restore_privacy_client” is free of malware…*

```bash
python3 scripts/sign_and_notarize_macos.py \
  --app client_app/build/macos/Build/Products/Release/restore_privacy_client.app \
  --zip releases/0.1.0/restore-privacy-client-0.1.0-macos.zip
```

See [macos/BUILD_ON_MAC.md](macos/BUILD_ON_MAC.md) § Gatekeeper.
