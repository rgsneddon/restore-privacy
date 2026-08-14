# Restore Privacy Client (Flutter)

Cross-platform UI for the **Restore Privacy Suite**: residual **RPT2** tunnel
(custom protocol — not WireGuard/OpenVPN), optional Perccent wallet (**%**),
Evolve (**EVOLVE**), and **rpAI** (GOD).

Product onboarding (KEYGEN, optional Suite account, GOD):
**[SUITE.md](SUITE.md)** · **[docs/SUITE_ACCOUNT_AND_RPAI.md](../docs/SUITE_ACCOUNT_AND_RPAI.md)**.

| Platform | Status |
|----------|--------|
| **Android** | Full VpnService path shipped |
| **Windows** | Native Python + installer (separate); Flutter Windows is UI-only unless extended |
| **iOS / macOS** | **RPT2 Packet Tunnel + channel shipped** — sign Network Extension with Apple Developer team for full-system VPN |

## Shared config

- Endpoint / full tunnel / auto-connect: `lib/rpt_config.dart`  
- Method channel: `restore_privacy/vpn` (`lib/vpn_controller.dart`)  
- Theme / privacy message string: `lib/theme.dart`  
- Optional Suite account (post-KEYGEN, deferrable): `lib/suite_account.dart`,
  `lib/suite_account_prompt.dart`, `lib/suite_account_apply.dart`  
- rpAI / GOD scripted guide: `lib/suite_ned_guide.dart`, `lib/suite_rpai_tab.dart`  

**Connect never consults Suite account flags** — only licence + KEYGEN
(`LicenceGate.mayConnect`). One Suite identity covers **%** and **EVOLVE**;
**Not now — use VPN only** defers registration. Deferred users resume from
rpAI (**Continue wallet & analyser setup**); registered users get **Offer how-to**
with **Continue…** parts and an optional VPN tour.  


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

