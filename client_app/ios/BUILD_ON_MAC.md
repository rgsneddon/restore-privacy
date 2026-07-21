# iOS — build on MacBook

Flutter `ios/` scaffold is ready. Full-system VPN requires a **Packet Tunnel** Network Extension (`NEPacketTunnelProvider`) — sign and test on Mac only.

## 1. Open and fetch packages

```bash
cd client_app
flutter pub get
open ios/Runner.xcworkspace
```

Or CLI:

```bash
flutter build ios --no-codesign   # then sign/archive in Xcode
# device run (after signing):
flutter run -d <ios-device>
```

## 2. Bundle ID & signing (Xcode)

**Already in-repo:**

| Bundle | ID |
|--------|-----|
| Host | `com.restoreprivacy.restorePrivacyClient` |
| PacketTunnel | `com.restoreprivacy.restorePrivacyClient.PacketTunnel` |
| App Group | `group.com.restoreprivacy.shared` |
| Host entitlements | `Runner/Runner.entitlements` (NE + App Group; `CODE_SIGN_ENTITLEMENTS` wired) |
| Extension entitlements | `PacketTunnel/PacketTunnel.entitlements` |
| Team | `SFCBP95595` |

**Your steps:** portal App IDs (host + `.PacketTunnel`) → Xcode Team + Automatic Signing on Runner and PacketTunnel → run on a device. PacketTunnel Team signing is already enabled in the project. Full ordered list: [APPLE_BUILD.md — Operator checklist](../APPLE_BUILD.md#operator-checklist--enable-real-packet-tunnel-vpn).

## 3. Packet Tunnel extension target

The **PacketTunnel** target already exists (`NativePrep/PacketTunnelProvider.swift` + Embed Foundation Extensions). Keep bundle id `com.restoreprivacy.restorePrivacyClient.PacketTunnel` in sync with `RptVpnChannel.providerBundleId`.

## 4. Method channel contract (must match Flutter)

| | |
|--|--|
| Channel | `restore_privacy/vpn` |
| Methods | `connect`, `disconnect` |
| `connect` args | `host`, `port`, `fullTunnel`, `sessionName`, `route`, `autoConnect` |
| Success result | `{ "ok": true, "message": "…", "vpnIp": "10.88.0.x" }` |
| Failure result | `{ "ok": false, "message": "…" }` |

Defaults: host/port from `lib/rpt_config.dart` (`82.221.101.241`, `44044`).

**Residual public IP:** product “Connected” requires Packet Tunnel `.connected`. A host-side RPT2 HELLO alone is diagnostic (`ok: false`) and does **not** change your ISP egress IP — enable Network Extension signing/entitlements for full-system VPN.

## 5. Secrets

Copy into the **App Group** container (or Keychain accessible to the extension):

- `client_ed25519.priv` (32 bytes)  
- `node_elgamal.pub`  

**Never** include `node_elgamal.priv`.

See `NativePrep/RptSecrets.swift` for path helper stubs.

## 6. Product behavior to preserve

- Auto-connect on launch (`lib/main.dart` → `VpnController.autoConnectOnLaunch`)  
- Retro UI: dark blue `#000080`, black bg, white text  
- Privacy message string (exact):  
  `lightweight vpn to restore your privacy - no user data is retained - your privacy is restored`  
- Full tunnel `0.0.0.0/0` via the Packet Tunnel settings  
- UK public-IP gate before handshake (mirror Android `UkIpGate` / Python `client/uk_gate.py`)  
- Brand **AppIcon** already under `Runner/Assets.xcassets/AppIcon.appiconset/`

## 7. Protocol reference

Implement RPT2 in Swift inside the extension (not in Dart):

| Step | Python reference |
|------|------------------|
| CLIENT_HELLO / SERVER_HELLO | `client/connect.py`, `node/handshake.py` |
| Frame magic / types | `node/protocol.py` (`RPT2`, DATA=0x03, KEEPALIVE=0x04) |
| Sealed DATA loop | `client/dataplane.py` |
| Outline for Apple | `ios/NativePrep/RPT_PROTOCOL.md` |

## 8. Signing & distribution

- Development: paid Apple Developer team + device UDID.  
- Packet Tunnel has `CODE_SIGN_ENTITLEMENTS = PacketTunnel/PacketTunnel.entitlements` (packet-tunnel + App Group).  
- `CODE_SIGNING_ALLOWED = YES` with team `SFCBP95595`; `PacketTunnel.appex` is embedded in Runner.  
- TestFlight / App Store: App Store Connect, privacy nutrition labels, VPN justification.

## 9. Smoke checklist on device

- [ ] App launches, auto-connect runs  
- [ ] VPN permission sheet appears  
- [ ] Status shows session OK / VPN IP or clear error  
- [ ] Full tunnel: traffic exits via node when connected  
- [ ] Disconnect returns to normal routing  
- [ ] Bundle does not contain `node_elgamal.priv`
