# Restore Privacy

**Restore Privacy Tunnel (RPT)** â€” a custom-built VPN **client** for private connectivity.  
**Not** WireGuard, OpenVPN, IPsec, or any other pre-existing VPN product.

| | |
|--|--|
| **Get the app** | [Download v0.1.5](https://github.com/rgsneddon/restore-privacy/releases/tag/0.1.5) Â· [Status & downloads](https://restore-privacy-status.onrender.com/) |
| **Privacy** | [PRIVACY_POLICY.md](PRIVACY_POLICY.md) |
| **License** | [LICENSE](LICENSE) (MIT) |
| **Credits** | [CREDITS.md](CREDITS.md) |

---

## What you get

- **Manual Connect / Disconnect** with optional seamless power-up via **Settings âš™**
  - **Run at device startup** (Windows sign-in / Android boot â€” opt-in)
  - **Autoconnect on launch** (opt-in; defaults off)
- System tray identity **Privacy Restored** (Windows) with product **logo** icons
- Scrolling message:  
  `lightweight vpn to restore your privacy - no user data is retained - your privacy is restored`
- **Full-device VPN** when the OS grants VPN permission (Windows UAC / Wintun dual `/1`, Android VPN consent, Apple Packet Tunnel when signed)
- Residual public IP uses the **VPN node** only when full-tunnel routes are active (honest status otherwise)
- **Close / minimize** keeps the tunnel running until **Disconnect** or **Quit**
- Live status page with **currently connected** client count and installers

---

## How to install and use

Download packages from the **[0.1.5 release](https://github.com/rgsneddon/restore-privacy/releases/tag/0.1.5)**  
or use the buttons on https://restore-privacy-status.onrender.com/

| Platform | Package |
|----------|---------|
| Windows | `restore-privacy-client-0.1.5-windows-x64-setup.exe` |
| Android | `restore-privacy-client-0.1.5-android.apk` |
| macOS | `restore-privacy-client-0.1.5-macos.zip` *(prep zip / sign on Mac â€” see below)* |
| iOS | `restore-privacy-client-0.1.5-ios.zip` *(prep zip / sign on Mac â€” see below)* |

### Windows

1. Download the **Windows installer (.exe)** from the release or status page.
2. Run **`restore-privacy-client-0.1.5-windows-x64-setup.exe`**.  
   It installs the full client (**bundled runtime + Wintun + dependencies** â€” **no separate Python install**), creates **Privacy Restored** shortcuts with the **logo** icon, and can launch the app. The setup window shows standard install progress.
3. Press **Connect** and approve **UAC** when prompted so residual public IP uses the VPN node.
4. Optional: open **âš™ Settings** and enable **Run at device startup** and/or **Autoconnect on launch** for seamless power-up (both default **off**).
5. Use the system tray (**Privacy Restored**) or taskbar to restore the window; **Disconnect** or **Quit** stops the tunnel.

### Android

1. Download the **APK** from the release or status page.
2. Install the APK (allow install from unknown sources if your device asks).
3. Open **Restore Privacy**, press **Connect**, and grant **VPN** permission when prompted.
4. Optional: **âš™ Settings** â†’ startup / autoconnect (defaults off). Minimize keeps the VPN service running until **Disconnect**.

### macOS / iOS (continue on a Mac)

Release zips for **0.1.5** stage the Apple client packages for sideload / further signing. **Team signing and notarization must be done on a Mac.**

1. Download **`restore-privacy-client-0.1.5-macos.zip`** or **`restore-privacy-client-0.1.5-ios.zip`**, **or** clone this repo and open `client_app/` in Xcode / Flutter on macOS.
2. Developer checklist:  
   - [`client_app/APPLE_BUILD.md`](client_app/APPLE_BUILD.md)  
   - [`client_app/macos/BUILD_ON_MAC.md`](client_app/macos/BUILD_ON_MAC.md)  
   - [`client_app/ios/BUILD_ON_MAC.md`](client_app/ios/BUILD_ON_MAC.md)  
   - Mac handoff notes: [`client_app/APPLE_HANDOFF_0.1.5.md`](client_app/APPLE_HANDOFF_0.1.5.md) (created with the release)
3. Packages may ship the **public** node key (`node_elgamal.pub`). Each install **generates its own Ed25519 device key on first run**. Never ship `node_elgamal.priv` or a shared `client_ed25519.priv`.

### Status page

https://restore-privacy-status.onrender.com/

- Live **currently connected clients** count  
- **Download** buttons for Windows, Android, macOS, and iOS (catalog v0.1.5)  
- **Connect via web** explains that a browser tab cannot run full system VPN  

---

## Privacy, license, and credits

- **Privacy:** [PRIVACY_POLICY.md](PRIVACY_POLICY.md)  
- **License:** **MIT** â€” [LICENSE](LICENSE)  
- **Credits:** [CREDITS.md](CREDITS.md)  

---

## Operators / developers

Node deploy, ports, secrets, from-source builds, and tests: **[sundries.txt](sundries.txt)**.

```bash
# Windows GUI (requires system Python)
python -m client.windows

# Release packages
python scripts/build_release_0.1.5.py
```
