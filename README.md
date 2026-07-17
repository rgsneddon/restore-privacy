# Restore Privacy

Custom-built **VPN node** and **client tunnel** — **Restore Privacy Tunnel (RPT)**.  
**Not** WireGuard, OpenVPN, IPsec, or any other pre-existing VPN product.

| | |
|--|--|
| **Status page** | https://restore-privacy-status.onrender.com/ |
| **Downloads (v0.0.1)** | [GitHub Release 0.0.1](https://github.com/rgsneddon/restore-privacy/releases/tag/0.0.1) |
| **Privacy policy** | [PRIVACY_POLICY.md](PRIVACY_POLICY.md) |
| **License** | [LICENSE](LICENSE) (MIT) |
| **Credits** | [CREDITS.md](CREDITS.md) |

---

## How to use (quick start)

### 1. Download a client (recommended)

1. Open the status page: https://restore-privacy-status.onrender.com/  
   (or the [0.0.1 release](https://github.com/rgsneddon/restore-privacy/releases/tag/0.0.1)).
2. Under **Download client v0.0.1**, choose your platform:
   - **Windows (x64) — full client package** — zip with launcher + sources + Wintun DLL  
   - **Windows (x64) — standalone package** — larger PyInstaller bundle  
   - **Android — APK installer**
3. **Windows:** unzip → right-click `RestorePrivacy.bat` → **Run as administrator** (needed for full system VPN).  
   Install [Python 3](https://www.python.org/downloads/) if using the non-standalone zip, then  
   `pip install -r requirements.txt`.  
   The window auto-connects on launch (retro Win 3.1-style UI).
4. **Android:** install the APK → open the app → grant **VPN** permission once when prompted.  
   The app auto-connects on launch.
5. **iOS / macOS:** packages are not signed on the Windows build host. On a Mac, follow  
   `client_app/ios/BUILD_ON_MAC.md` and `client_app/macos/BUILD_ON_MAC.md`.

> **Secrets:** public installers do **not** ship private admission keys. Operators place  
> `client_ed25519.priv` and `node_elgamal.pub` under `secrets/` (see node deploy).  
> Without valid keys, the cryptographic handshake will not admit the client.

### 2. Run the Windows client from source

```bash
git clone https://github.com/rgsneddon/restore-privacy.git
cd restore-privacy
pip install -r requirements.txt
# optional: copy operator secrets into ./secrets/
python -m client.windows
```

- UI: dark blue banner, black background, white text  
- Scrolling line:  
  `lightweight vpn to restore your privacy - no user data is retained - your privacy is restored`  
- **Auto-connect** on launch (no separate Connect button required)  
- Full VPN: run elevated so Wintun can create an adapter and install routes

### 3. Run the Android client from source

```bash
cd client_app
flutter pub get
flutter run
# or
flutter build apk --release
```

### 4. Use the public status page

- Live **currently connected** client count (not a lifetime total)  
- Count updates in the browser without a full page reload  
- Download buttons for release packages  

URL: https://restore-privacy-status.onrender.com/

### 5. Deploy or operate the VPN node (operators)

On a Linux host (example endpoint used by this project: `104.156.224.47`):

```bash
# From a machine with SSH access — password via env, never commit it
export RPT_SSH_HOST=YOUR_SERVER_IP
export RPT_SSH_USER=root
export RPT_SSH_PASSWORD='...'   # do not commit
pip install paramiko cryptography
python scripts/deploy_rpt_node.py
```

Or on the server:

```bash
# After copying the node/ tree to /opt/restore-privacy/node
bash /opt/restore-privacy/node/install.sh
```

| Port | Purpose |
|------|---------|
| **UDP 44044** | RPT tunnel |
| **TCP 8080** | Node status UI (title + current client count) |

Node properties:

| Property | Behavior |
|----------|----------|
| Admission | Authorized RPT client keys only (ElGamal + Pedersen + Ed25519) |
| Crypto | Custom RPT2 data plane (ChaCha20-Poly1305 after handshake) |
| Relay | TUN + IP forward + MASQUERADE |
| Privacy | No user-info / session activity log files by design — see [PRIVACY_POLICY.md](PRIVACY_POLICY.md) |

### 6. Run tests (developers)

```bash
pip install -r requirements.txt
python -m unittest discover -s tests -v
```

---

## Repository layout

| Path | Role |
|------|------|
| `node/` | RPT VPN **node** (server) |
| `client/` | Shared client connect path + **Windows** retro UI |
| `client_app/` | **Flutter** Android/iOS/macOS/Windows scaffolds |
| `status_page/` | Public status + download links (Render) |
| `scripts/` | Deploy / release helpers |
| `PRIVACY_POLICY.md` | Full privacy policy |
| `LICENSE` | MIT license for original code |
| `CREDITS.md` | Credits for utilised third-party parts |

---

## Privacy, license, and credits

- **Privacy:** we design for **no user-info logs** and **no public exposure of client identity**—details and limits in [PRIVACY_POLICY.md](PRIVACY_POLICY.md).  
- **License:** original project code is **MIT** — [LICENSE](LICENSE).  
- **Credits:** Wintun, cryptography, Bouncy Castle, Flutter, and other utilised parts — [CREDITS.md](CREDITS.md).

---

## Security note

An open no-auth UDP VPN would be abusable; this product uses **cryptographic admission** for the Restore Privacy client. Protect authorized client private keys. The VPS and status host operators may still see network-level metadata under their own policies (see privacy policy limits).
