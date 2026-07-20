# Restore Privacy

**Restore Privacy Tunnel (RPT)** — a custom-built VPN **client** for private connectivity.  
**Not** WireGuard, OpenVPN, IPsec, or any other pre-existing VPN product.

| | |
|--|--|
| **Get the app** | [Download v0.2.3](https://github.com/rgsneddon/restore-privacy/releases/tag/0.2.3) · [Status & downloads](https://restore-privacy-status.onrender.com/) |
| **Privacy** | [PRIVACY_POLICY.md](PRIVACY_POLICY.md) |
| **License** | [LICENSE](LICENSE) (MIT) |
| **Credits** | [CREDITS.md](CREDITS.md) |
| **Security audit** | [audit.md](audit.md) |

---

## What you get

- Production node: **`82.221.101.241:44044`** (UDP RPT2)
- **Manual Connect / Disconnect** with optional seamless power-up via **Settings**
  - **Run at device startup** (Windows sign-in / Android boot — opt-in)
  - **Autoconnect on launch** (opt-in; defaults off)
  - **Settings** links to the **most recent audit**, **privacy policy**, and **end user licence**
- System tray identity **Privacy Restored** (Windows) with product **logo** icons
- Scrolling message:  
  `lightweight vpn to restore your privacy - no user data is retained - your privacy is restored`
- **Full-device VPN** when the OS grants VPN permission (Windows UAC / Wintun dual `/1`, Android VPN consent, Apple Packet Tunnel when signed)
- Residual public IP uses the **VPN node** only when full-tunnel routes are active (**honest status** otherwise)
- **Close / minimize** keeps the tunnel running until **Disconnect** or **Quit**
- Public status page with **download installers only** (no live client count)
- **No third-party geo lookup** on Connect (admission is cryptographic only)
- Session **PFS** (ephemeral X25519) on the Python client/node handshake path
- **Layer obfuscation** (QUIC-mimic outer wrap around RPT frames) **on by default** (`RPT_OBFS=0` to opt out) — mitigation, not DPI-undetectability
- **Product traffic shaping** (padding / send jitter / cover) **on by default** for Windows/Linux Python DATA path (`RPT_TRAFFIC_SHAPE=0` to opt out)
- **Kill switch** on product full tunnel: block non-tunnel egress while connected (`RPT_KILL_SWITCH=0` to opt out); IPv6 ISP path blocked; tunnel DNS only (`10.88.0.1`, no public DNS fallbacks)
- Multi-hop hop *lists* may be configured for planning — **not residual multi-hop** until a real relay path ships
- Native Android/Apple engines may lag Python pad/cover/PFS/obfs wire extensions (documented honestly)

---

## How to install and use

Download packages from the **[0.2.3 release](https://github.com/rgsneddon/restore-privacy/releases/tag/0.2.3)**  
or use the buttons on https://restore-privacy-status.onrender.com/

| Platform | Package |
|----------|---------|
| Windows | `restore-privacy-client-0.2.3-windows-x64-setup.exe` |
| Android | `restore-privacy-client-0.2.3-android.apk` |
| macOS | `restore-privacy-client-0.2.3-macos.zip` *(prep zip / sign on Mac — see below)* |
| iOS | `restore-privacy-client-0.2.3-ios.zip` *(prep zip / sign on Mac — see below)* |
| Ubuntu / Linux | `restore-privacy-client-0.2.3-linux-x64.tar.gz` *(installer package; crypto deps baked in)* |

### Windows

1. Download the **Windows installer (.exe)** from the release or status page.
2. Run **`restore-privacy-client-0.2.3-windows-x64-setup.exe`**.  
   It installs the full client (**bundled runtime + Wintun + dependencies** — **no separate Python install**), creates **Privacy Restored** shortcuts with the **logo** icon, and can launch the app.
3. Press **Connect** and approve **UAC** when prompted so residual public IP uses the VPN node.
4. Optional: open **Settings** and enable **Run at device startup** and/or **Autoconnect on launch** (both default **off**). Settings also links to the audit, privacy policy, and end user licence.
5. Use the system tray (**Privacy Restored**) or taskbar to restore the window; **Disconnect** or **Quit** stops the tunnel.

### Android

1. Download the **APK** from the release or status page.
2. Install the APK (allow install from unknown sources if your device asks).
3. Open **Restore Privacy**, press **Connect**, and grant **VPN** permission when prompted.
4. Optional: **Settings** → startup / autoconnect (defaults off); open audit / privacy / licence links. Minimize keeps the VPN service running until **Disconnect**.

### Ubuntu and derivatives (Linux Mint, Pop!_OS, …)

**Supported floor:** Ubuntu **20.04 LTS and newer** (22.04, 24.04, …) and Mint/Pop built on those bases. Python **3.8+**.

1. Download **`restore-privacy-client-0.2.3-linux-x64.tar.gz`** from the release or status page.
2. Unpack and run the **bundled installer** (crypto wheels baked in — no network `pip install cryptography`):
   ```bash
   tar xzf restore-privacy-client-0.2.3-linux-x64.tar.gz
   cd restore-privacy-0.2.3-linux
   bash install.sh
   ```
3. Run the GUI (**root** needed so residual public IP uses the VPN node):
   ```bash
   sudo ./bin/privacy-restored
   ```
4. Press **Connect**. Status is honest: residual public IP only changes when TUN + dual `/1` routes are active.
5. Details: `LINUX_INSTALL.md` inside the tarball; source: [`client/linux/`](client/linux/).  
   - **Wheeled ABIs:** manylinux wheels for **CPython 3.8–3.12**. Re-run `python scripts/package_linux.py` on every release.

### macOS / iOS (continue on a Mac)

Release zips for **0.2.3** are **prep packages** for sideload / further signing — **Mac work required**. Residual public IP does **not** change until Packet Tunnel / Network Extension is signed and active; host-side HELLO alone is **diagnostic** only.

1. Download **`restore-privacy-client-0.2.3-macos.zip`** or **`restore-privacy-client-0.2.3-ios.zip`**, or clone this repo and open `client_app/` on macOS.
2. Checklist:
   - [`client_app/APPLE_BUILD.md`](client_app/APPLE_BUILD.md)
   - [`client_app/macos/BUILD_ON_MAC.md`](client_app/macos/BUILD_ON_MAC.md)
   - [`client_app/ios/BUILD_ON_MAC.md`](client_app/ios/BUILD_ON_MAC.md)
   - Mac handoff: [`client_app/APPLE_HANDOFF_0.2.3.md`](client_app/APPLE_HANDOFF_0.2.3.md) (or prior `APPLE_HANDOFF_0.2.2.md` if not yet copied)
3. Packages may ship the **public** node key (`node_elgamal.pub`). Each install **generates its own Ed25519 device key on first run**. Packages **do **not** ship a shared** `client_ed25519.priv`. Never ship `node_elgamal.priv`.

### Status page

https://restore-privacy-status.onrender.com/

- **Download** buttons for Windows, Android, macOS, iOS, and Linux (catalog **v0.2.3**)  
- **No** public live session / connected-client counter  
- **Connect via web** (if present in docs) explains that a browser tab cannot run full system VPN  

---

## Privacy, license, credits, and audit

| Document | Link |
|----------|------|
| **Privacy policy** | [PRIVACY_POLICY.md](PRIVACY_POLICY.md) |
| **License** | [LICENSE](LICENSE) (MIT) |
| **Credits** | [CREDITS.md](CREDITS.md) |
| **Code & policy audit** | [audit.md](audit.md) |

Core promises: **no user-info logs** by design, **minimal public status** (title + downloads — **no live client count**), **device keys** (not a shared client private key), **honest residual** only when full tunnel is up, **no third-party geo** on Connect. Product Windows/Linux clients enable **outer-layer obfuscation**, **padding / jitter / cover**, and **kill-switch** by default on residual paths; multi-hop *config* is not residual until a real relay ships. Node tunnel DNS uses **DoT** upstream. VPS providers may still see IP-level metadata (privacy §4).

---

## Threat model

Short user-education summary. Full policy language: **[PRIVACY_POLICY.md — Threat model](PRIVACY_POLICY.md)**. Scenario detail for operators/auditors: **[audit.md §4.6](audit.md)** (VPS compromise, traffic analysis by ISP, client device seizure).

### What it protects against

- **Residual public IP** uses the VPN node when full tunnel is actually up (honest status otherwise).
- **No user-info logs** on the product node path; **no public live client count**.
- **Per-device keys** (not a shared installer private key).
- **Mitigations** for coarse traffic fingerprints: outer obfuscation + padding/jitter/cover (default on product residual DATA path) — **not** a claim of DPI-undetectability.
- **Kill-switch / tunnel DNS / IPv6 ISP block** while residual capture is active.
- **PFS** (ephemeral X25519) so long-term key compromise later should not reconstruct past session AEAD keys from the public transcript alone.

### What it does **not** protect against

- **Endpoint correlation** — sites still know you via logins, cookies, and browser fingerprints; many users share one node egress IP.
- **Behavioral analysis** — observers can still study when you connect and rough usage patterns.
- **VPS / provider IP metadata** — hosters may log network metadata outside app no-log settings.
- **Traffic analysis by ISP** beyond mitigations — you still appear to use a VPN; no multi-hop residual yet.
- **Client device seizure** — local keys, apps, and browser history on an unlocked device are out of scope for the node’s no-log promise.
- Malware, compromised OS, or destination-site tracking.

---

## Operators / developers

Node deploy, ports, secrets, from-source builds, and tests: **[sundries.txt](sundries.txt)**.

**Secrets discipline:** Never commit or force-add `secrets/` (gitignored). Public packages must never include `node_elgamal.priv` or a shared `client_ed25519.priv`. Release scripts run `_assert_no_priv` / strip inject gates — keep those on every tag.

**Node key protection:** `RPT_KEY_BACKEND=file|mock|sealed|tpm` — sealed/TPM-class stores long-term ElGamal under a wrap key so plaintext `.priv` is not required on disk. See `node/key_backend.py`.

**Key rotation:** `python scripts/rotate_node_keys.py --secrets-dir …` updates node long-term material + `product/node_elgamal.pub` pin; clients re-provision **public** only (`reprovision_node_public`). Session **PFS** (X25519) is the product default.

**Post-quantum readiness:** staged hybrid Kyber/ML-KEM hook in `node/pq_hybrid.py` + plan [`docs/PQ_MIGRATION.md`](docs/PQ_MIGRATION.md) (not residual PQ on the wire until dual-wire + real ML-KEM).

**0.2.3 release:** Production node **82.221.101.241:44044**. Settings transparency, licence gate, native wire parity, FDE/ephemeral ops tooling. See [scripts/RELEASE_NOTES_0.2.3.md](scripts/RELEASE_NOTES_0.2.3.md). Prefer upgrading from 0.2.2.

**Self-host (one shot):** `sudo bash scripts/selfhost_node.sh` — node install + tunnel DNS + host privacy. Details: [sundries.txt](sundries.txt).

**Tunnel DNS / host privacy:** [node/install_dns.sh](node/install_dns.sh), [node/install_host_privacy.sh](node/install_host_privacy.sh).

**Data at rest (LUKS / dm-crypt):** [node/install_disk_encryption.sh](node/install_disk_encryption.sh) — `check` / `dry-run` / confirmed `format`. Combines with **no-logs** and [shutdown wipe](node/install_shutdown_wipe.sh) (runtime scrub on stop; optional aggressive secrets wipe). Honesty: FDE protects locked disks only; does not erase provider snapshots.

**Ephemeral / short-lived nodes:** [scripts/ephemeral_node.py](scripts/ephemeral_node.py) — **periodic** VPS **snapshot** and/or **rebuild** plan (`--dry-run` by default). Install timer: [scripts/install_ephemeral_timer.sh](scripts/install_ephemeral_timer.sh). Live rebuild requires `RPT_EPHEMERAL_CONFIRM=yes`. Rebuild re-runs self-host (no-log). Does not erase provider backups/netflow; re-ship **public** node pin if keys rotate.

**Release scripts:** Use **scripts/build_release_0.2.3.py**. Re-run `python scripts/package_linux.py` each tag for manylinux wheels. Apple: [APPLE_HANDOFF_0.2.3.md](client_app/APPLE_HANDOFF_0.2.3.md).

```bash
# Windows GUI (requires system Python)
python -m client.windows

# Ubuntu / Mint GUI from source (needs system cryptography)
sudo PYTHONPATH=. python3 -m client.linux

# Linux installer package with baked-in crypto wheels (re-run each release)
python scripts/package_linux.py

# Release packages (current tag)
python scripts/build_release_0.2.3.py
```
