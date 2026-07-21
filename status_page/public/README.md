# Restore Privacy

**Restore Privacy Tunnel (RPT)** — a custom-built VPN **client** for private connectivity.  
**Not** WireGuard, OpenVPN, IPsec, or any other pre-existing VPN product.

| | |
|--|--|
| **Get the app** | [Status & paid downloads](https://restoreprivacy.online/) (catalog **v0.3.3**, £2.45 per package) |
| **Privacy** | [PRIVACY_POLICY.md](PRIVACY_POLICY.md) |
| **License** | [LICENSE](LICENSE) (MIT) |
| **Credits** | [CREDITS.md](CREDITS.md) |
| **Security audit** | [AUDIT.md](AUDIT.md) |

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
- **No product kill switch by default** (firewall/iptables block rules and Android `setBlocking` are off; opt in only with `RPT_KILL_SWITCH=1`); tunnel DNS only (`10.88.0.1`, no public DNS fallbacks); IPv4 residual honesty still applies
- Multi-hop hop *lists* may be configured for planning — **not residual multi-hop** until a real relay path ships
- Native Android/Apple engines may lag Python pad/cover/PFS/obfs wire extensions (documented honestly)

---

## How to install and use

**Current catalog (v0.3.3):** pay-per-package installers on https://restoreprivacy.online/ (£2.45 GBP via Stripe).  
The product source repository is **private**; free permanent GitHub release downloads are not offered. After payment the status site delivers the installer once (authenticated proxy).

| Platform | Package |
|----------|---------|
| Windows | `restore-privacy-client-0.3.3-windows-x64-setup.exe` |
| Android | `restore-privacy-client-0.3.3-android.apk` |
| macOS | `restore-privacy-client-0.3.3-macos.zip` *(Developer ID signed + notarized)* |
| iOS | `restore-privacy-client-0.3.3-ios.zip` *(Team-signed sideload)* |
| Ubuntu / Linux | `restore-privacy-client-0.3.3-linux-x64.tar.gz` |

### Windows

1. On the [status downloads page](https://restoreprivacy.online/), pay **£2.45** for **Windows** and download **`restore-privacy-client-0.3.3-windows-x64-setup.exe`** (one-time link after payment).
2. Run the installer (bundled runtime + Wintun — no separate Python install).
3. Press **Connect** and approve **UAC** when prompted so residual public IP uses the VPN node.
4. Optional: **Settings** → startup / autoconnect (defaults **off**); legal links to audit / privacy / licence.

### Android

1. On the [status downloads page](https://restoreprivacy.online/), pay **£2.45** for **Android** and download **`restore-privacy-client-0.3.3-android.apk`** (one-time link after payment).
2. Install the APK (allow install from unknown sources if your device asks).
3. Open **Restore Privacy**, press **Connect**, and grant **VPN** permission when prompted.
4. Optional: **Settings** → startup / autoconnect (defaults off). Minimize keeps the VPN service running until **Disconnect**.

### Ubuntu and derivatives (Linux Mint, Pop!_OS, …)

1. On the [status downloads page](https://restoreprivacy.online/), pay **£2.45** for **Linux** and download **`restore-privacy-client-0.3.3-linux-x64.tar.gz`** (one-time link after payment).
2. Unpack and run the bundled installer:
   ```bash
   tar xzf restore-privacy-client-0.3.3-linux-x64.tar.gz
   cd restore-privacy-0.3.0-linux
   bash install.sh
   ```
3. Run **`sudo ./bin/privacy-restored`** for residual public IP (TUN + dual `/1` routes).

### macOS

Published **0.3.0** macOS builds are **Developer ID signed and notarized**.

1. On the [status downloads page](https://restoreprivacy.online/), pay **£2.45** for **macOS** and download **`restore-privacy-client-0.3.3-macos.zip`** (one-time link after payment).
2. Unzip and open **`restore_privacy_client.app`**.
3. Press **Connect** and approve the **VPN configuration** prompt.
4. Residual public IP only changes when the Packet Tunnel is **active**. Host-only HELLO is **diagnostic** only. Residual public-IP via Packet Tunnel on a developer Mac still needs **Team residual re-sign** (`scripts/sign_macos_residual_team.py`) — the public Developer ID zip alone is not full host-NE residual (see `client_app/APPLE_HANDOFF_0.3.3.md`). **Disconnect** / **Quit** stops the system VPN.

### iOS

Published **0.3.0** iOS packages are **Team-signed sideload** zips (not App Store).

1. On the [status downloads page](https://restoreprivacy.online/), pay **£2.45** for **iOS** and download **`restore-privacy-client-0.3.3-ios.zip`** (one-time link after payment).
2. Install **`Runner.app`** with device tooling; press **Connect** and grant **VPN** permission.
3. Residual public IP only changes when the Packet Tunnel is **active**.

### Status page

https://restoreprivacy.online/

- **Pay £2.45** buttons for Windows, Android, macOS, iOS, Linux — catalog **v0.3.3**  
- Installers are delivered **after payment** (single-use link); the product repo is private  
- **No** public live session / connected-client counter  
- A browser tab cannot run full system VPN

---

## Privacy, license, credits, and audit

| Document | Link |
|----------|------|
| **Privacy policy** | [PRIVACY_POLICY.md](PRIVACY_POLICY.md) |
| **License** | [LICENSE](LICENSE) (MIT) |
| **Credits** | [CREDITS.md](CREDITS.md) |
| **Code & policy audit** | [AUDIT.md](AUDIT.md) |

Core promises: **no user-info logs** by design, **minimal public status** (title + downloads — **no live client count**), **device keys** (not a shared client private key), **honest residual** only when full tunnel is up, **no third-party geo** on Connect. Product Windows/Linux clients enable **outer-layer obfuscation** and **padding / jitter / cover** by default on residual paths; **kill-switch is not applied by default**. Multi-hop *config* is not residual until a real relay ships. Node tunnel DNS uses **DoT** upstream. VPS providers may still see IP-level metadata (privacy §4).

---

## Threat model

Short user-education summary. Full policy language: **[PRIVACY_POLICY.md — Threat model](PRIVACY_POLICY.md)**. Scenario detail for operators/auditors: **[AUDIT.md §4.6](AUDIT.md)** (VPS compromise, traffic analysis by ISP, client device seizure).

### What it protects against

- **Residual public IP** uses the VPN node when full tunnel is actually up (honest status otherwise).
- **No user-info logs** on the product node path; **no public live client count**.
- **Per-device keys** (not a shared installer private key).
- **Mitigations** for coarse traffic fingerprints: outer obfuscation + padding/jitter/cover (default on product residual DATA path) — **not** a claim of DPI-undetectability.
- **Tunnel-only DNS** (`10.88.0.1`) while residual capture is active; **IPv4 residual honesty** when full tunnel is up. Kill-switch firewall blocks are **not** applied by default (opt-in only: `RPT_KILL_SWITCH=1`).
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

**Device keys:** packages do **not** ship a shared client private key; each install generates its own Ed25519 device key on first run.

**Secrets discipline:** Never commit or force-add `secrets/` (gitignored). Paid release packages must never include `node_elgamal.priv` or a shared `client_ed25519.priv`. Release scripts run `_assert_no_priv` / strip inject gates — keep those on every tag.

**Node key protection:** `RPT_KEY_BACKEND=file|mock|sealed|tpm` — sealed/TPM-class stores long-term ElGamal under a wrap key so plaintext `.priv` is not required on disk. See `node/key_backend.py`.

**Key rotation:** `python scripts/rotate_node_keys.py --secrets-dir …` updates node long-term material + `product/node_elgamal.pub` pin; clients re-provision **public** only (`reprovision_node_public`). Session **PFS** (X25519) is the product default.

**Post-quantum readiness:** staged hybrid Kyber/ML-KEM hook in `node/pq_hybrid.py` + plan [`docs/PQ_MIGRATION.md`](docs/PQ_MIGRATION.md) (not residual PQ on the wire until dual-wire + real ML-KEM).

**Product ship (v0.3.3):** Paid installers on **[status downloads](https://restoreprivacy.online/)** (macOS Developer ID notarized; iOS Team-signed). Source repo is private. Production node **82.221.101.241:44044**.

**Self-host (one shot):** `sudo bash scripts/selfhost_node.sh` — node install + tunnel DNS + host privacy. Deploy remote: `python scripts/deploy_rpt_node.py` (`RPT_SSH_HOST`, `RPT_SSH_USER`, key). Details: [sundries.txt](sundries.txt).

**Tunnel DNS / host privacy:** [node/install_dns.sh](node/install_dns.sh), [node/install_host_privacy.sh](node/install_host_privacy.sh).

**Data at rest (LUKS / dm-crypt):** [node/install_disk_encryption.sh](node/install_disk_encryption.sh) — `check` / `dry-run` / confirmed `format`. Combines with **no-logs** and [shutdown wipe](node/install_shutdown_wipe.sh) (runtime scrub on stop; optional aggressive secrets wipe). Honesty: FDE protects locked disks only; does not erase provider snapshots.

**Ephemeral / short-lived nodes:** [scripts/ephemeral_node.py](scripts/ephemeral_node.py) — **periodic** VPS **snapshot** and/or **rebuild** plan (`--dry-run` by default). Install timer: [scripts/install_ephemeral_timer.sh](scripts/install_ephemeral_timer.sh). Live rebuild requires `RPT_EPHEMERAL_CONFIRM=yes`. Rebuild re-runs self-host (no-log). Does not erase provider backups/netflow; re-ship **public** node pin if keys rotate.

**Release scripts:** `scripts/build_release_0.3.3.py`. Apple handoff: [`client_app/APPLE_HANDOFF_0.3.3.md`](client_app/APPLE_HANDOFF_0.3.3.md). Release notes: [`scripts/RELEASE_NOTES_0.3.3.md`](scripts/RELEASE_NOTES_0.3.3.md).

```bash
# Windows GUI (requires system Python)
python -m client.windows

# Ubuntu / Mint GUI from source (needs system cryptography)
sudo PYTHONPATH=. python3 -m client.linux

# Linux installer package with baked-in crypto wheels (re-run each release)
python scripts/package_linux.py  # manylinux wheels for CPython 3.8–3.12; re-run each release

# Release packages (current tag)
python scripts/build_release_0.3.3.py
```
