# Restore Privacy

**Restore Privacy Tunnel (RPT)**  -  a custom-built VPN **client** for private connectivity.  
**Not** WireGuard, OpenVPN, IPsec, or any other pre-existing VPN product.

| | |
|--|--|
| **Get the app** | [Download v0.1.8](https://github.com/rgsneddon/restore-privacy/releases/tag/0.1.8)  |  [Status & downloads](https://restore-privacy-status.onrender.com/) |
| **Privacy** | [PRIVACY_POLICY.md](PRIVACY_POLICY.md) |
| **License** | [LICENSE](LICENSE) (MIT) |
| **Credits** | [CREDITS.md](CREDITS.md) |

---

## What you get

- **Manual Connect / Disconnect** with optional seamless power-up via **Settings âš™**
  - **Run at device startup** (Windows sign-in / Android boot  -  opt-in)
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

Download packages from the **[0.1.8 release](https://github.com/rgsneddon/restore-privacy/releases/tag/0.1.8)**  
or use the buttons on https://restore-privacy-status.onrender.com/

| Platform | Package |
|----------|---------|
| Windows | `restore-privacy-client-0.1.8-windows-x64-setup.exe` |
| Android | `restore-privacy-client-0.1.8-android.apk` |
| macOS | `restore-privacy-client-0.1.8-macos.zip` *(prep zip / sign on Mac  -  see below)* |
| iOS | `restore-privacy-client-0.1.8-ios.zip` *(prep zip / sign on Mac  -  see below)* |
| Ubuntu / Linux | `restore-privacy-client-0.1.8-linux-x64.tar.gz` *(installer package; crypto deps baked in)* |

### Windows

1. Download the **Windows installer (.exe)** from the release or status page.
2. Run **`restore-privacy-client-0.1.8-windows-x64-setup.exe`**.  
   It installs the full client (**bundled runtime + Wintun + dependencies**  -  **no separate Python install**), creates **Privacy Restored** shortcuts with the **logo** icon, and can launch the app. The setup window shows standard install progress.
3. Press **Connect** and approve **UAC** when prompted so residual public IP uses the VPN node.
4. Optional: open **âš™ Settings** and enable **Run at device startup** and/or **Autoconnect on launch** for seamless power-up (both default **off**).
5. Use the system tray (**Privacy Restored**) or taskbar to restore the window; **Disconnect** or **Quit** stops the tunnel.

### Android

1. Download the **APK** from the release or status page.
2. Install the APK (allow install from unknown sources if your device asks).
3. Open **Restore Privacy**, press **Connect**, and grant **VPN** permission when prompted.
4. Optional: **âš™ Settings** -> startup / autoconnect (defaults off). Minimize keeps the VPN service running until **Disconnect**.

### Ubuntu and derivatives (Linux Mint, Pop!_OS, …)

**Supported floor:** Ubuntu **20.04 LTS and newer** (22.04, 24.04, …) and Mint/Pop built on those bases. Python **3.8+**. Older EOL Ubuntu (16.04/18.04) is not guaranteed.

1. Download **`restore-privacy-client-0.1.8-linux-x64.tar.gz`** (installer package) from the release or status page.
2. Unpack and run the **bundled installer** (installs app Python deps **from wheels inside the archive** — no network `pip install cryptography`):
   ```bash
   tar xzf restore-privacy-client-0.1.8-linux-x64.tar.gz
   cd restore-privacy-0.1.8-linux
   bash install.sh
   ```
   Creates a private `.venv` from `wheels/`. System packages only if missing: `python3-venv`, `python3-tk`, `iproute2`.
3. Run the GUI (**root** needed so residual public IP uses the VPN node):
   ```bash
   sudo ./bin/privacy-restored
   ```
4. Press **Connect**. Status is honest: residual public IP only changes when TUN + dual `/1` routes are active. **Disconnect** removes routes and stops the session.
5. Details: `LINUX_INSTALL.md` inside the tarball; source path for developers: [`client/linux/`](client/linux/).
   - **Wheeled ABIs:** the release package includes manylinux wheels for **CPython 3.8–3.12** (`cryptography` abi3 + matching `cffi` tags). Re-run `python scripts/package_linux.py` on every release so wheels stay current.

### macOS / iOS (continue on a Mac)

Release zips for **0.1.8** are **prep packages** for sideload / further signing — **Mac work required**. Residual public IP does **not** change until Packet Tunnel / Network Extension is signed and active; host-side HELLO alone is diagnostic only. **Team signing and notarization must be done on a Mac.**

1. Download **`restore-privacy-client-0.1.8-macos.zip`** or **`restore-privacy-client-0.1.8-ios.zip`**, **or** clone this repo and open `client_app/` in Xcode / Flutter on macOS.
2. Developer checklist:  
   - [`client_app/APPLE_BUILD.md`](client_app/APPLE_BUILD.md)  
   - [`client_app/macos/BUILD_ON_MAC.md`](client_app/macos/BUILD_ON_MAC.md)  
   - [`client_app/ios/BUILD_ON_MAC.md`](client_app/ios/BUILD_ON_MAC.md)  
   - Mac handoff notes: [`client_app/APPLE_HANDOFF_0.1.8.md`](client_app/APPLE_HANDOFF_0.1.8.md) (created with the release)
3. Packages may ship the **public** node key (`node_elgamal.pub`). Each install **generates its own Ed25519 device key on first run**. Packages do **not** ship a shared `client_ed25519.priv` (which would allow universal impersonation). Never ship `node_elgamal.priv`.

### Status page

https://restore-privacy-status.onrender.com/

- Live **currently connected clients** count  
- **Download** buttons for Windows, Android, macOS, iOS, and Linux (catalog v0.1.8)  
- **Connect via web** explains that a browser tab cannot run full system VPN  

---

## Privacy, license, and credits

- **Privacy:** [PRIVACY_POLICY.md](PRIVACY_POLICY.md)  
- **License:** **MIT**  -  [LICENSE](LICENSE)  
- **Credits:** [CREDITS.md](CREDITS.md)  

---

## Operators / developers

Node deploy, ports, secrets, from-source builds, and tests: **[sundries.txt](sundries.txt)**.

**Secrets discipline:** Never commit or force-add `secrets/` (gitignored). Public packages must never include `node_elgamal.priv` or a shared `client_ed25519.priv`. Release scripts run `_assert_no_priv` / strip inject gates — keep those on every tag. VPS/CDN operators may still log IP-level traffic under **their** policies (outside product no-log; see `PRIVACY_POLICY.md` §4).

**0.1.9 (source prep):** UK public-IP geo check **removed** from product Connect (Python, Android, Apple). No third-party geo lookup on connect; admission is device keys + node crypto only. Node admission crypto unchanged. See [`scripts/RELEASE_NOTES_0.1.9.md`](scripts/RELEASE_NOTES_0.1.9.md). **Shipped 0.1.8 installers still enforce the old UK check until users upgrade** to a 0.1.9 package.

**Tunnel DNS (source prep):** Full-tunnel clients default DNS to the **node** (`10.88.0.1`), not Cloudflare/Quad9. Operators run [`node/install_dns.sh`](node/install_dns.sh) (Unbound, tunnel-only) on the VPS when the box is up — name resolution while connected needs that service.

**Connect privacy:** Product Connect does **not** call third-party geo/telemetry HTTPS (no phones-home before handshake). Node host quiet-logging prep: [`node/install_host_privacy.sh`](node/install_host_privacy.sh). **Live VPS apply** of DNS + host privacy is the deploy step after this prep.

**Release scripts:** Public download catalog remains **v0.1.8** until 0.1.9 assets are cut. For packaging, copy `scripts/build_release_0.1.8.py` → `build_release_0.1.9.py` and bump catalog/`VERSION`. Historical `build_release_0.*.py` files are archive/history. Always re-run `python scripts/package_linux.py` (or the Linux step inside the current release script) so manylinux wheels are refreshed.

```bash
# Windows GUI (requires system Python)
python -m client.windows

# Ubuntu / Mint GUI from source (needs system cryptography)
sudo PYTHONPATH=. python3 -m client.linux

# Linux installer package with baked-in crypto wheels (re-run each release)
python scripts/package_linux.py

# Release packages (current tag)
python scripts/build_release_0.1.8.py
```
