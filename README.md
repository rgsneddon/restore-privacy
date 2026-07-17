# Restore Privacy

**Restore Privacy Tunnel (RPT)** — a custom-built VPN **client** for private connectivity.  
**Not** WireGuard, OpenVPN, IPsec, or any other pre-existing VPN product.

| | |
|--|--|
| **Get the app** | [Download v0.0.1](https://github.com/rgsneddon/restore-privacy/releases/tag/0.0.1) · [Status & downloads](https://restore-privacy-status.onrender.com/) |
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

1. Download **Windows (x64)** from the [0.0.1 release](https://github.com/rgsneddon/restore-privacy/releases/tag/0.0.1)  
   or use the buttons on https://restore-privacy-status.onrender.com/
2. Unzip the package.
3. Right-click **`RestorePrivacy.bat`** → **Run as administrator**  
   (Administrator is required for full system VPN.)
4. If you used the smaller “full client package” (not the standalone zip), install  
   [Python 3](https://www.python.org/downloads/) and run  
   `pip install -r requirements.txt` once from the unzipped folder.
5. The app opens and **connects automatically**.

**Standalone zip:** run the packaged app as Administrator (no separate Python install).

### Android

1. Download the **APK** from the [0.0.1 release](https://github.com/rgsneddon/restore-privacy/releases/tag/0.0.1)  
   or the status page.
2. Install the APK (allow install from unknown sources if your device asks).
3. Open **Restore Privacy** and grant **VPN** permission when prompted.
4. The app **connects automatically** on launch.

### iOS / macOS

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
