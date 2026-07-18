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

1. Select **Runner** → **Signing & Capabilities**.  
2. Choose your **Team**.  
3. Set a unique **Bundle Identifier** (e.g. `com.yourorg.restoreprivacy`).  
4. Add capability **Network Extensions** → Packet Tunnel (host app).  
5. Enable **App Groups** (e.g. `group.com.yourorg.restoreprivacy`) for secrets sharing with the extension.

## 3. Add Packet Tunnel extension target

1. **File → New → Target → Network Extension → Packet Tunnel Provider**.  
2. Name e.g. `PacketTunnel` (bundle id `…restoreprivacy.tunnel`).  
3. Drag in prep sources from `ios/NativePrep/`:
   - `PacketTunnelProvider.swift` → **PacketTunnel** target  
   - `RptVpnChannel.swift` → **Runner** target  
   - Optionally `RptSecrets.swift` into both (App Group access)  
4. Wire method channel registration (see `RptVpnChannel.swift` header comments).  
5. Extension **Info.plist**: `NEProviderClasses` / Packet Tunnel class name = `PacketTunnelProvider`.  
6. Extension entitlements: Packet Tunnel + same **App Group**.

Until the extension is complete, `RptVpnChannel` returns a clear map:

```json
{ "ok": false, "message": "iOS Packet Tunnel not yet configured — …" }
```

so Flutter UI does not hang (same contract as `lib/vpn_controller.dart`).

## 4. Method channel contract (must match Flutter)

| | |
|--|--|
| Channel | `restore_privacy/vpn` |
| Methods | `connect`, `disconnect` |
| `connect` args | `host`, `port`, `fullTunnel`, `sessionName`, `route`, `autoConnect` |
| Success result | `{ "ok": true, "message": "…", "vpnIp": "10.88.0.x" }` |
| Failure result | `{ "ok": false, "message": "…" }` |

Defaults: host/port from `lib/rpt_config.dart` (`104.156.224.47`, `44044`).

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
- Scrolling string (exact):  
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
- Packet Tunnel target already has `CODE_SIGN_ENTITLEMENTS = PacketTunnel/PacketTunnel.entitlements` (packet-tunnel + App Group).  
- Local/CI builds set `CODE_SIGNING_ALLOWED = NO` on PacketTunnel when no NE provisioning profile exists; for device VPN set `CODE_SIGNING_ALLOWED = YES`, choose Team, and **Embed Foundation Extensions** so `PacketTunnel.appex` is inside the host app.  
- TestFlight / App Store: App Store Connect, privacy nutrition labels, VPN justification.

## 9. Smoke checklist on device

- [ ] App launches, auto-connect runs  
- [ ] VPN permission sheet appears  
- [ ] Status shows session OK / VPN IP or clear error  
- [ ] Full tunnel: traffic exits via node when connected  
- [ ] Disconnect returns to normal routing  
- [ ] Bundle does not contain `node_elgamal.priv`
