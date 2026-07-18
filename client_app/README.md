# Restore Privacy Client (Flutter)

Cross-platform UI for the **RPT2** tunnel (custom protocol — not WireGuard/OpenVPN).

| Platform | Status |
|----------|--------|
| **Android** | Full VpnService path shipped |
| **Windows** | Native Python + installer (separate); Flutter Windows is UI-only unless extended |
| **iOS / macOS** | **Prep ready** — finish Packet Tunnel + signing on a **Mac** |

## Shared config

- Endpoint / full tunnel / auto-connect: `lib/rpt_config.dart`  
- Method channel: `restore_privacy/vpn` (`lib/vpn_controller.dart`)  
- Theme / scrolling privacy string: `lib/theme.dart`  

## Apple (MacBook)

Start here: **[APPLE_BUILD.md](APPLE_BUILD.md)**

- [ios/BUILD_ON_MAC.md](ios/BUILD_ON_MAC.md)  
- [macos/BUILD_ON_MAC.md](macos/BUILD_ON_MAC.md)  
- Native stubs: `ios/NativePrep/`, `macos/NativePrep/`  

## Android

```bash
cd client_app
flutter pub get
flutter build apk --release
```

## Secrets

Never commit `*.priv`. Product keys: `client_ed25519.priv` + `node_elgamal.pub` only.  
See Apple docs and Android inject path under `client_app/android`.
