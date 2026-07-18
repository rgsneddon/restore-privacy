# Restore Privacy

**Restore Privacy Tunnel (RPT)** — a custom-built VPN **client** for private connectivity.  
**Not** WireGuard, OpenVPN, IPsec, or any other pre-existing VPN product.

| | |
|--|--|
| **Get the app** | [Download v0.1.1](https://github.com/rgsneddon/restore-privacy/releases/tag/0.1.1) · [Status & downloads](https://restore-privacy-status.onrender.com/) |
| **Privacy** | [PRIVACY_POLICY.md](PRIVACY_POLICY.md) |
| **License** | [LICENSE](LICENSE) (MIT) |
| **Credits** | [CREDITS.md](CREDITS.md) |

---

## What you get

- A simple **retro** client window (dark blue banner, black background, white text)
- **Auto-connect** when you open the app (no separate “Connect” step)
- Scrolling message:  
  `lightweight vpn to restore your privacy - no user data is retained - your privacy is restored`
- Full-device VPN on **Windows, Android, iOS, and macOS** when the OS grants VPN permission and (on Apple platforms) Network Extension signing is configured
- Live status page with **currently connected** client count and installers for all four platforms

---

## How to install and use

Download packages from the **[0.1.1 release](https://github.com/rgsneddon/restore-privacy/releases/tag/0.1.1)**  
or use the buttons on https://restore-privacy-status.onrender.com/

| Platform | Package |
|----------|---------|
| Windows | `restore-privacy-client-0.1.1-windows-x64-setup.exe` |
| Android | `restore-privacy-client-0.1.1-android.apk` |
| macOS | `restore-privacy-client-0.1.1-macos.zip` |
| iOS | `restore-privacy-client-0.1.1-ios.zip` |

### Windows

1. Download the **Windows installer (.exe)** from the release or status page.
2. Run **`restore-privacy-client-0.1.1-windows-x64-setup.exe`**.  
   It installs the full client (bundled runtime + dependencies — **no separate Python install**), creates shortcuts, and launches the app.
3. For full system VPN, run **Restore Privacy** as Administrator (Start Menu or Desktop shortcut → right-click → Run as administrator), or accept the UAC prompt when the app auto-elevates.
4. The app **connects automatically** on launch.

### Android

1. Download the **APK** from the release or status page.
2. Install the APK (allow install from unknown sources if your device asks).
3. Open **Restore Privacy** and grant **VPN** permission when prompted.
4. The app **connects automatically** on launch.

### macOS

Release packages **bundle product admission keys** (`client_ed25519.priv` + `node_elgamal.pub`) so the client can connect without a separate secrets step. Never ship `node_elgamal.priv`.

1. Download **`restore-privacy-client-0.1.1-macos.zip`** from the release or status page.
2. Unzip and open **`restore_privacy_client.app`** (notarized Developer ID builds open without Gatekeeper malware blocks).
3. The UI **auto-connects** on launch via the native `restore_privacy/vpn` channel.
4. **Full-system VPN** uses the embedded **Packet Tunnel** Network Extension (Team-signed in 0.1.1). Approve the VPN configuration prompt when asked.  
   Developer checklist: [`client_app/APPLE_BUILD.md`](client_app/APPLE_BUILD.md) · [`client_app/macos/BUILD_ON_MAC.md`](client_app/macos/BUILD_ON_MAC.md).

### iOS

1. Download **`restore-privacy-client-0.1.1-ios.zip`** from the release or status page.
2. The zip contains **`Runner.app`** for sideload / device tooling (not an App Store build).
3. Install onto a device with a development or enterprise signing workflow; grant **VPN** permission when prompted.
4. The UI **auto-connects** on launch. Full tunnel uses the Packet Tunnel Network Extension; Team signing and App Groups are required.  
   Developer checklist: [`client_app/APPLE_BUILD.md`](client_app/APPLE_BUILD.md) · [`client_app/ios/BUILD_ON_MAC.md`](client_app/ios/BUILD_ON_MAC.md).

### Status page

https://restore-privacy-status.onrender.com/

- Live **currently connected clients** count (updates without reloading the page)
- **Download** buttons for Windows, Android, macOS, and iOS packages
- **Connect via web** explains that a browser tab cannot run full system VPN, and links you to the real apps

---

## Privacy, license, and credits

- **Privacy:** designed for **no user-info logs** and no public exposure of client identity — full detail in [PRIVACY_POLICY.md](PRIVACY_POLICY.md).
- **License:** original project code is **MIT** — [LICENSE](LICENSE).
- **Credits:** Wintun, cryptography, Bouncy Castle, Flutter, Apple CryptoKit, BigInt, and other utilised parts — [CREDITS.md](CREDITS.md).

---

## Operators / developers

Node deploy, ports, secrets, from-source builds, and tests are documented in **[sundries.txt](sundries.txt)** — not required for normal client use.
