# Apple platforms prep (iOS + macOS)

Build and sign on a **Mac** with Xcode. This Windows checkout only prepares sources, icons, docs, and native stubs.

| Platform | UI | Full-system VPN |
|----------|----|-----------------|
| **iOS** | Flutter `Runner` | **Packet Tunnel** Network Extension (`NEPacketTunnelProvider`) |
| **macOS** | Flutter `Runner` | **Network Extension** (Packet Tunnel) and/or System Extension |

## Shared product rules (do not change)

| Item | Value / location |
|------|------------------|
| Endpoint | `82.221.101.241:44044` UDP (`lib/rpt_config.dart`) |
| Protocol | **RPT2** (not WireGuard / OpenVPN) Ã¢â‚¬â€ see `client/connect.py`, `node/handshake.py` |
| Method channel | **`restore_privacy/vpn`** Ã¢â‚¬â€ methods `connect`, `disconnect` (see `lib/vpn_controller.dart`) |
| Connect args | `host`, `port`, `fullTunnel`, `sessionName`, `route`, `autoConnect` |
| Result map | `{ ok, message, vpnIp?, fullTunnelActive?, hostOnlySession? }` Ã¢â‚¬â€ use `lib/connect_status.dart` |
| Residual public IP | Changes **only** when OS Packet Tunnel is `.connected`. Host-side RPT2 HELLO alone is diagnostic (`ok: false`). |
| UI | Retro: banner `#000080`, black bg, white text; scrolling privacy string in `lib/theme.dart` |
| Auto-connect | On launch (`RptConfig.autoConnectOnLaunch`) |
| Full tunnel | `0.0.0.0/0` intent |
| UK IP gate | **Removed** (0.1.9): no public-IP geo admission; device keys + RPT2 crypto only |
| Brand icons | Already under `ios/.../AppIcon.appiconset` and `macos/.../AppIcon.appiconset` |

## Secrets (never commit `*.priv`)

Required admission files (product client, **not** node private key):

- `client_ed25519.priv` Ã¢â‚¬â€ 32 raw bytes  
- `node_elgamal.pub` Ã¢â‚¬â€ node ElGamal public key bytes  

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
# example Ã¢â‚¬â€ from a machine that can SSH to the node
scp root@82.221.101.241:/opt/restore-privacy/secrets/client_ed25519.priv \
    root@82.221.101.241:/opt/restore-privacy/secrets/node_elgamal.pub \
    ~/.restore-privacy/secrets/
```

## On your MacBook Ã¢â‚¬â€ quick start

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

- [ios/BUILD_ON_MAC.md](ios/BUILD_ON_MAC.md) Ã¢â‚¬â€ Packet Tunnel + signing  
- [macos/BUILD_ON_MAC.md](macos/BUILD_ON_MAC.md) Ã¢â‚¬â€ Network Extension + notarization  

Native prep stubs (drag into Xcode targets as described in those docs):

- `ios/NativePrep/` Ã¢â‚¬â€ method channel + Packet Tunnel skeleton  
- `macos/NativePrep/` Ã¢â‚¬â€ method channel + Packet Tunnel skeleton  
- `ios/NativePrep/RPT_PROTOCOL.md` Ã¢â‚¬â€ handshake/DATA outline for Swift  

## What is already implemented (this tree)

1. Shared Swift **RPT2 engine** under `apple_shared/Rpt2/` (also copied into `ios/NativePrep/Rpt2` and `macos/NativePrep/Rpt2`) with unit tests: `cd client_app/apple_shared/Rpt2 && swift test`.  
2. **Packet Tunnel** targets (`ios/PacketTunnel`, `macos/PacketTunnel`) implementing UK gate Ã¢â€ â€™ secrets Ã¢â€ â€™ handshake Ã¢â€ â€™ full-tunnel settings Ã¢â€ â€™ packetFlow/UDP DATA + keepalive.  
3. Host method channel `restore_privacy/vpn` registered from iOS `AppDelegate` / macOS `MainFlutterWindow`; product connect succeeds **only** when Packet Tunnel is active. Host-side RPT2 HELLO is diagnostic-only (never a false Ã¢â‚¬Å“ConnectedÃ¢â‚¬Â that leaves residual ISP IP unchanged).  
4. Secrets helpers load **only** `client_ed25519.priv` + `node_elgamal.pub` (never `node_elgamal.priv`).

## Network Extension entitlements (in-repo)

Host + Packet Tunnel plists already declare the real product IDs:

| ID | Value |
|----|--------|
| Host bundle | `com.restoreprivacy.restorePrivacyClient` |
| Packet Tunnel | `com.restoreprivacy.restorePrivacyClient.PacketTunnel` |
| App Group | `group.com.restoreprivacy.shared` |
| Team | `SFCBP95595` |

| File | Keys |
|------|------|
| `macos/Runner/DebugProfile.entitlements` | `packet-tunnel-provider` + App Group (+ sandbox) — Team-signed Xcode path |
| `macos/Runner/Release.entitlements` | same (Xcode Release / Team-signed) |
| `macos/Runner/DeveloperID.entitlements` | **Distribution host:** Flutter CS + network + App Group; **no** host `networkextension` (AMFI kills DevID host with NE without a matching profile — open fails POSIX 163 / exit 137) |
| `ios/Runner/Runner.entitlements` | `packet-tunnel-provider` + App Group (wired via `CODE_SIGN_ENTITLEMENTS`) |
| `macos/PacketTunnel/PacketTunnel.entitlements` | `packet-tunnel-provider` + App Group (appex keeps NE for Developer ID) |
| `ios/PacketTunnel/PacketTunnel.entitlements` | same |

`scripts/sign_and_notarize_macos.py` prefers `DeveloperID.entitlements` for the host
app, strips development `embedded.provisionprofile`s, and signs the Packet Tunnel
appex with `PacketTunnel.entitlements`.

### Residual Packet Tunnel on this Mac (Team sign)

Public **Developer ID** zips omit host Network Extension so the app **opens** for all
downloaders (restricted NE without a matching DevID profile is AMFI-killed). Residual
public IP still requires host + appex `packet-tunnel-provider` authorized by a **Mac
Team Provisioning Profile**:

```bash
# After flutter build macos --release
python3 scripts/sign_macos_residual_team.py \
  --app client_app/build/macos/Build/Products/Release/restore_privacy_client.app
open client_app/build/macos/Build/Products/Release/restore_privacy_client.app
# Connect → approve System Settings → Network → VPN & Filters if prompted
```

Host uses `Runner/TeamResidual.entitlements` (NE + allow-jit only — do **not** combine
NE with `allow-unsigned-executable-memory` or `disable-library-validation`).

Packet Tunnel targets are configured for **Team signing** (`CODE_SIGNING_ALLOWED = YES`, `CODE_SIGNING_REQUIRED = YES`, team `SFCBP95595`). The old ad-hoc re-sign step only runs when signing is explicitly disabled.

## Operator checklist Ã¢â‚¬â€ enable real Packet Tunnel VPN

Do these **in order**. Entitlement *files* are already patched; you still must register them with Apple and sign with your Team.

### 1. Developer portal ([developer.apple.com](https://developer.apple.com) Ã¢â€ â€™ Identifiers)

1. Sign in with the team that owns **SFCBP95595** (or your team if you change IDs).
2. **App Groups** Ã¢â€ â€™ create/register: `group.com.restoreprivacy.shared`.
3. **App ID** `com.restoreprivacy.restorePrivacyClient` (host):
   - Capability **Network Extensions** Ã¢â€ â€™ enable **Packet Tunnel**
   - Capability **App Groups** Ã¢â€ â€™ select `group.com.restoreprivacy.shared`
4. **App ID** `com.restoreprivacy.restorePrivacyClient.PacketTunnel` (extension):
   - Same **Network Extensions Ã¢â€ â€™ Packet Tunnel**
   - Same **App Groups** entry
5. If Xcode uses Automatic Signing, it will create Development profiles after step 2. For Mac distribution outside the Mac App Store, also ensure Developer ID + Network Extension is allowed for that App ID when Apple requires it.

### 2. Xcode Ã¢â‚¬â€ pick Team (both platforms)

```bash
cd client_app
open macos/Runner.xcworkspace   # macOS
# and/or
open ios/Runner.xcworkspace     # iOS
```

For **Runner** and **PacketTunnel** on each platform:

1. **Signing & Capabilities** Ã¢â€ â€™ Team **SFCBP95595** (Russell Sneddon).
2. **Automatically manage signing** = ON.
3. Confirm capabilities appear (Network Extensions / Packet Tunnel, App Groups). If Xcode offers to Ã¢â‚¬Å“fixÃ¢â‚¬Â entitlements mismatches, prefer keeping the repo plists above.
4. Confirm provider bundle id stays `com.restoreprivacy.restorePrivacyClient.PacketTunnel` (matches `RptVpnChannel.providerBundleId`).

### 3. PacketTunnel target (already in the repo)

The **PacketTunnel** app extension is already created and embedded:

| Item | Value |
|------|--------|
| Bundle ID | `com.restoreprivacy.restorePrivacyClient.PacketTunnel` |
| Provider class | `PacketTunnelProvider` (`NativePrep/PacketTunnelProvider.swift`) |
| Entitlements | `PacketTunnel/PacketTunnel.entitlements` (NE + App Group) |
| Code signing | `CODE_SIGNING_ALLOWED = YES`, team `SFCBP95595` |
| Embed | Runner Ã¢â€ â€™ **Embed Foundation Extensions** Ã¢â€ â€™ `PacketTunnel.appex` |

**You only need to:** open the workspace, pick Team on Runner + PacketTunnel (Automatic Signing), and ensure the portal App ID for `.PacketTunnel` exists with Network Extensions + App Group. If Xcode shows a profile error, fix the portal App ID Ã¢â‚¬â€ do not create a second Packet Tunnel target.

### 4. Secrets the extension can read

```bash
mkdir -p ~/.restore-privacy/secrets
# product client key + node public key only (never node_elgamal.priv):
cp /path/to/client_ed25519.priv /path/to/node_elgamal.pub ~/.restore-privacy/secrets/
```

Prefer App Group after first successful run:

`~/Library/Group Containers/group.com.restoreprivacy.shared/secrets/`

Or inject into a release `.app` / `Runner.app`:

```bash
python3 scripts/inject_apple_secrets.py --app path/to/restore_privacy_client.app
python3 scripts/inject_apple_secrets.py --app path/to/Runner.app --ios
```

### 5. Build and run

**macOS**

```bash
cd client_app
flutter run -d macos
# or release:
flutter build macos --release
```

Approve the **VPN configuration** / network extension system prompt when it appears.

**iOS** (physical device; Simulator is not enough for full VPN)

```bash
cd client_app
flutter run -d <device-id>
```

Approve the VPN permission sheet. Trust the developer certificate under Settings if needed.

### 6. Confirm residual public IP actually changed

| Check | Expected |
|-------|----------|
| App status | `Connected Ã¢â‚¬â€ tunnel IP 10.88.0.x` **and** system VPN indicator on |
| macOS menu bar / iOS status bar | VPN active |
| Browser / `curl ifconfig.me` | **Not** your home residual IP (node egress) |
| If Packet Tunnel failed | Honest `ok: false` residual-IP message (not a false Ã¢â‚¬Å“ConnectedÃ¢â‚¬Â) |

Inspect signed entitlements:

```bash
codesign -d --entitlements - path/to/restore_privacy_client.app
codesign -d --entitlements - path/to/.../PacketTunnel.appex
```

Both host and extension should list `packet-tunnel-provider` and the App Group.

### 7. Distribute (optional)

- **macOS downloads:** Developer ID + notarize (`scripts/sign_and_notarize_macos.py`).
- **iOS:** device / TestFlight / App Store with VPN privacy justification.

## Success criteria on Mac / iPhone

- Flutter UI launches and auto-connects.  
- Channel `restore_privacy/vpn` returns success only when Packet Tunnel is active (`fullTunnelActive`).  
- Full tunnel: residual public IP exits via the RPT node when connected.  
- No `node_elgamal.priv` in the app bundle.

## Gatekeeper (macOS downloads)

Published macOS zips must be **Developer ID signed and notarized** so users are not blocked by
*Apple could not verify Ã¢â‚¬Å“restore_privacy_clientÃ¢â‚¬Â is free of malwareÃ¢â‚¬Â¦*

```bash
python3 scripts/sign_and_notarize_macos.py \
  --app client_app/build/macos/Build/Products/Release/restore_privacy_client.app \
  --zip releases/0.1.3/restore-privacy-client-0.1.3-macos.zip
```

See [macos/BUILD_ON_MAC.md](macos/BUILD_ON_MAC.md) Ã‚Â§ Gatekeeper.
