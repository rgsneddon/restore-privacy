# Restore Privacy

**Restore Privacy Tunnel (RPT)** — a custom-built VPN **client** for private connectivity.  
**Not** WireGuard, OpenVPN, IPsec, or any other pre-existing VPN product.

| | |
|--|--|
| **Get the app** | [Download v0.0.9](https://github.com/rgsneddon/restore-privacy/releases/tag/0.0.9) · [Status & downloads](https://restore-privacy-status.onrender.com/) |
| **Privacy** | [PRIVACY_POLICY.md](PRIVACY_POLICY.md) |
| **License** | [LICENSE](LICENSE) (MIT) |
| **Credits** | [CREDITS.md](CREDITS.md) |

---

## What you get

- A simple **retro** client window (dark blue banner, black background, white text)
- **Auto-connect** when you open the app (no separate “Connect” step)
- Scrolling message:  
  `lightweight vpn to restore your privacy - no user data is retained - your privacy is restored`
- Full-device VPN on supported platforms (Windows / Android), subject to OS permissions
- Live status page with **currently connected** client count and installers

---

## How to install and use

### Windows

1. Download the **Windows installer (.exe)** from the [0.0.9 release](https://github.com/rgsneddon/restore-privacy/releases/tag/0.0.9)  
   or use the button on https://restore-privacy-status.onrender.com/
2. Run **`restore-privacy-client-0.0.9-windows-x64-setup.exe`**.  
   It installs the full client (bundled runtime + dependencies — **no separate Python install**), creates shortcuts, and launches the app.
3. For full system VPN, run **Restore Privacy** as Administrator (Start Menu or Desktop shortcut → right-click → Run as administrator).
4. The app **connects automatically** on launch.

### Android

1. Download the **APK** from the [0.0.9 release](https://github.com/rgsneddon/restore-privacy/releases/tag/0.0.9)  
   or the status page.
2. Install the APK (allow install from unknown sources if your device asks).
3. Open **Restore Privacy** and grant **VPN** permission when prompted.
4. The app **connects automatically** on launch.

### iOS / macOS (prep — finish on a Mac)

Scaffold + MacBook checklist: **`client_app/APPLE_BUILD.md`**.  
Packet Tunnel Network Extension, secrets, and signing are Mac-only (stubs under `client_app/ios/NativePrep` and `macos/NativePrep`).

### iOS / macOS notes

Signed store installers are not published from the Windows build host yet.  
If you build on a Mac, see `client_app/ios/BUILD_ON_MAC.md` and `client_app/macos/BUILD_ON_MAC.md`.

### Status page

https://restore-privacy-status.onrender.com/

- Live **currently connected clients** count (updates without reloading the page)
- **Download** buttons for the client packages
- **Connect via web** explains that a browser tab cannot run full system VPN, and links you to the real apps

---

## Privacy, license, and credits

- **Privacy:** designed for **no user-info logs** and no public exposure of client identity — full detail in [PRIVACY_POLICY.md](PRIVACY_POLICY.md).
- **License:** original project code is **MIT** — [LICENSE](LICENSE).
- **Credits:** Wintun, cryptography, Bouncy Castle, Flutter, and other utilised parts — [CREDITS.md](CREDITS.md).

---

## Operators / developers

Node deploy, ports, secrets, from-source builds, and tests are documented in **[sundries.txt](sundries.txt)** — not required for normal client use.
