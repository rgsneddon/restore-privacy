# Restore Privacy

**Restore Privacy Tunnel (RPT)** — a custom-built VPN **client** for private connectivity.  
**Not** WireGuard, OpenVPN, IPsec, or any other pre-existing VPN product.

| | |
|--|--|
| **Get the app** | [Download v0.1.4](https://github.com/rgsneddon/restore-privacy/releases/tag/0.1.4) · [Status & downloads](https://restore-privacy-status.onrender.com/) |
| **Privacy** | [PRIVACY_POLICY.md](PRIVACY_POLICY.md) |
| **License** | [LICENSE](LICENSE) (MIT) |
| **Credits** | [CREDITS.md](CREDITS.md) |

---

## What you get

- Sleek **manual Connect / Disconnect** Windows client (no cold auto-connect)
- System tray identity **Privacy Restored** with the product **logo** icon
- Scrolling message:  
  `lightweight vpn to restore your privacy - no user data is retained - your privacy is restored`
- **Full-device VPN** when the OS grants VPN permission (Windows UAC / Wintun dual `/1`, Android VPN consent, Apple Packet Tunnel when signed)
- Windows residual public IP uses the **VPN node** only when full-tunnel routes are active (honest status otherwise)
- **Close** hides the window (VPN keeps running until **Disconnect** or **Quit** on Windows)
- Live status page with **currently connected** client count and installers

---

## How to install and use

Download packages from the **[0.1.4 release](https://github.com/rgsneddon/restore-privacy/releases/tag/0.1.4)**  
or use the buttons on https://restore-privacy-status.onrender.com/

| Platform | Package |
|----------|---------|
| Windows | `restore-privacy-client-0.1.4-windows-x64-setup.exe` |
| Android | `restore-privacy-client-0.1.4-android.apk` |
| macOS | `restore-privacy-client-0.1.4-macos.zip` *(optional / prior if not rebuilt)* |
| iOS | `restore-privacy-client-0.1.4-ios.zip` *(optional / prior if not rebuilt)* |

### Windows

1. Download the **Windows installer (.exe)** from the release or status page.
2. Run **`restore-privacy-client-0.1.4-windows-x64-setup.exe`**.  
   It installs the full client (**bundled runtime + Wintun + dependencies** — **no separate Python install**), creates **Privacy Restored** shortcuts with the **logo** icon, and can launch the app.
3. Press **Connect** and approve **UAC** when prompted so residual public IP uses the VPN node (dual `/1` + Wintun).
4. Use the system tray (**Privacy Restored**) or taskbar to restore the window; **Disconnect** or **Quit** stops the tunnel.

### Android

1. Download the **APK** from the release or status page.
2. Install the APK (allow install from unknown sources if your device asks).
3. Open **Restore Privacy** and grant **VPN** permission when prompted.
4. Connect via the app UI (VPN service when permission is granted).

### macOS

Release packages may ship the **public** node key (`node_elgamal.pub`) so the client can open a HELLO. Each install **generates its own Ed25519 device key on first run** and stores it only on the device — packages do **not** ship a shared `client_ed25519.priv`. Never ship `node_elgamal.priv`.

1. Download **`restore-privacy-client-0.1.4-macos.zip`** from the release or status page (when published).
2. Unzip and open **`restore_privacy_client.app`** (notarized Developer ID builds open without Gatekeeper malware blocks).
3. Full-system VPN uses the embedded **Packet Tunnel** Network Extension when Team-signed.  
   Developer checklist: [`client_app/APPLE_BUILD.md`](client_app/APPLE_BUILD.md) · [`client_app/macos/BUILD_ON_MAC.md`](client_app/macos/BUILD_ON_MAC.md).

### iOS

1. Download **`restore-privacy-client-0.1.4-ios.zip`** when published (sideload tooling, not App Store).
2. Install onto a device with a development or enterprise signing workflow; grant **VPN** permission when prompted.  
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

From source (requires system Python):

```bash
python -m client.windows
```

Windows release build:

```bash
python scripts/build_release_0.1.4.py
```
