# Restore Privacy Client (Flutter)

Cross-platform UI for the **RPT2** tunnel (custom protocol — not WireGuard/OpenVPN).

| Platform | Status |
|----------|--------|
| **Android** | Full VpnService path shipped |
| **Windows** | Native Python + installer (separate); Flutter Windows is UI-only unless extended |
| **iOS / macOS** | **RPT2 Packet Tunnel + channel shipped** — sign Network Extension with Apple Developer team for full-system VPN |

## Shared config

- Endpoint / full tunnel / auto-connect: `lib/rpt_config.dart`  
- Method channel: `restore_privacy/vpn` (`lib/vpn_controller.dart`)  
- Theme / privacy message string: `lib/theme.dart`  

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

## Android build dependencies

From repo root on Windows:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_android_build.ps1
``` 

Requires Flutter (C:\src\flutter), JDK 17, and Android SDK under %LOCALAPPDATA%\Android\Sdk.

