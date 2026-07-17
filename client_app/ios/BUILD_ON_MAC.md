# iOS — build on Mac later

This Flutter project already includes an `ios/` folder from `flutter create`.

## On your Mac

```bash
cd client_app
flutter pub get
open ios/Runner.xcworkspace   # or: flutter build ios
```

## Product behavior to keep

- Auto-connect on launch (see `lib/main.dart` → `VpnController.autoConnectOnLaunch`)
- Retro UI: dark blue banner `#000080`, black background, white text
- Scrolling string exactly:  
  `lightweight vpn to restore your privacy - no user data is retained - your privacy is restored`
- Full tunnel via Network Extension (`NEPacketTunnelProvider`) — **you must add** an iOS Packet Tunnel extension target in Xcode (not signable from Windows).

## Keys

Copy authorized secrets onto the device/keychain from the node:

- `/opt/restore-privacy/secrets/client_ed25519.priv`
- `/opt/restore-privacy/secrets/node_elgamal.pub`

Never commit private keys. Wire them into the Network Extension using the same RPT2 handshake as `client/connect.py` / `node/handshake.py`.

## Signing

Requires Apple Developer account + provisioning profiles. Not performed on Windows.
