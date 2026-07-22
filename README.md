# Restore Privacy

**Restore Privacy Tunnel (RPT)** — a custom-built VPN **client** for private connectivity.  
Restore Privacy is built from the ground up using unashamed vibe coding methods and wholly a product of SuperGrok Heavy Grok-Build and Russell G Sneddon's explicit instructions - Regular audits are scripted to run intermittently.

| | |
|--|--|
| **Get the app** | [Status & paid downloads](https://restoreprivacy.online/) (catalog **v0.3.7**, £2.45 per package) |
| **Privacy** | [PRIVACY_POLICY.md](PRIVACY_POLICY.md) |
| **License** | [LICENSE](LICENSE) (proprietary full copyright) |
| **Credits** | [CREDITS.md](CREDITS.md) |
| **Security audit** | [AUDIT.md](AUDIT.md) |

---

## What you get

- Production node: **`82.221.101.241:44044`** (UDP RPT2), hosted in **Iceland** on **FlokiNET** under **strict Icelandic privacy** norms — **as far as we can be assured** from the host’s public statements (**“No invasive logs”**; no third-party tenant traffic/pattern sharing; resource-usage monitoring only — https://flokinet.is/privacy/, https://flokinet.is/vps/)
- **Manual Connect / Disconnect** with optional seamless power-up via **Settings**
  - **Run at device startup** (Windows sign-in / Android boot — opt-in)
  - **Autoconnect on launch** (opt-in; defaults off)
  - **Settings** links to the **most recent audit**, **privacy policy**, and **end user licence**
- System tray identity **Privacy Restored** (Windows) with product **logo** icons
- Privacy message:  
  `lightweight vpn to restore your privacy - no user data is retained - your privacy is restored`
- **Full-device VPN** when the OS grants VPN permission (Windows UAC / Wintun dual `/1`, Android VPN consent, Apple Packet Tunnel when signed)
- Residual public IP uses the **VPN node** only when full-tunnel routes are active (**honest status** otherwise)
- **Close / minimize** keeps the tunnel running until **Disconnect** or **Quit**
- **Disconnect / Quit** restores residual routes and product firewall state so the device returns to normal internet (Windows dual `/1` teardown + scoped **RPT-FW** cleanup; Linux TUN/routes teardown)
- **Windows Defender Firewall** product rules are **scoped allows only** (node UDP + program) — not unscoped blocks; kill-switch remains opt-in
- **Restore Internet** failsafe in every catalog installer (network restore + complete product removal) — see warning below
- Public payment portal with seamless flow to downloadable installer package
- **No third-party geo lookup** on Connect (admission is cryptographic only)
- Connect uses the standard **HELLO** residual path (**flyclient** fast-path removed in catalog **v0.3.7**)
- **Node-only** optional **zram + LUKS2** encrypted RAM volume for host data (`node/install_zram_luks.sh`) — **not** client encryption; residual Connect unchanged
- Optional node **LUKS2 disk** data-at-rest (`node/install_disk_encryption.sh`) — at-rest only
- Session **PFS** (ephemeral X25519) on residual HELLO for all product clients (Python Windows/Linux, Android, iOS/macOS Packet Tunnel)
- **Layer obfuscation** (QUIC-mimic outer wrap around RPT frames) **on by default on every residual path** (`RPT_OBFS=0` to opt out on Python; native product constants default on) — mitigation, not DPI-undetectability
- **Product traffic shaping** (padding / send jitter / cover) **on by default on every residual path** — Windows/Linux Python (`RPT_TRAFFIC_SHAPE=0` to opt out), Android VPN service, and Apple Packet Tunnel (pad bucket 128, cover ~2s, jitter ≤40ms)
- **No product kill switch by default** (firewall/iptables block rules and Android `setBlocking` are off; opt in only with `RPT_KILL_SWITCH=1`); tunnel DNS only (`10.88.0.1`, no public DNS fallbacks); IPv4 residual honesty still applies
- Multi-hop residual is **opt-in** (`RPT_MULTIHOP_ENABLED=1`): residual Connect dials the **exit** hop (Romania **185.146.232.107**); default remains **single-hop** Iceland entry — **residual-via-exit** routing is implemented (not hop-list-only)
- Status site ([restoreprivacy.online](https://restoreprivacy.online/)) shows a **live entry-node clear timer** (Node A / entry only, ~7d) — exit is **never** wiped by the weekly service (stays up for residual failover)
- **Weekly entry node wipe/rebuild** (~7d): exclusive single-instance lock; clients **auto residual-failover to exit** while entry drains, then **prefer re-entry** when entry is healthy again (not zero packet-loss; not concurrent exit wipe)
- Security audit documents **per-installer AUDIT STATE** (Green / Amber / Red) for catalog packages — [AUDIT.md](AUDIT.md)
- **Proprietary full copyright** end-user licence ([LICENSE](LICENSE)): client packages **AS IS**, use only to run a device on Restore Privacy VPN; **no** architecture copy/transmission

---

## How to install and use

**Current catalog (v0.3.7):** paid installers on https://restoreprivacy.online/ via Stripe (**not** free permanent GitHub release downloads). Homepage download section shows a large green **ONLY £2.45 per month** callout under **Download client v0.3.7**, then the trial/pay box: **your monthly subscription begins after your 7 day trial** — **pay on Stripe, then download starts automatically (licence key and download links are emailed to you separately)**. Email still delivers **keygen + PPI + download link** (**USE THIS KEYGEN TO UNLOCK YOUR RESTORE PRIVACY TRIAL**). Apps: Install → accept licence → enter keygen; Connect only while subscription active. Weekly wipe UI is **entry-only** (no dual Node A/B wipe countdown on the homepage).  
The product source repository is **private**; free permanent GitHub release downloads are not offered. After payment the status site delivers the installer once (authenticated proxy).

> **STRONG DISCLAIMER — PAYMENT REQUIRED FOR CONNECT:** Access to **Connect** and residual VPN use requires **successful payment**. If payment **fails at any time** (failed checkout, failed charge, refund, dispute, or revoked entitlement), the ability to **Connect with the Restore Privacy app is cancelled** for that purchase/install until a successful payment is completed.

**Unlock Connect after payment:** the thank-you page shows your Checkout **session id** (`cs_…`) and auto-downloads `payment_entitlement.json`. In the app open **Settings → Payment entitlement**, paste the session id, and press **Verify payment / unlock Connect** (or place `payment_entitlement.json` in the product data folder). On every Connect the app re-checks the status host so a later refund/failure cancels Connect for that install.

| Platform | Package |
|----------|---------|
| Windows | `restore-privacy-client-0.3.7-windows-x64-setup.exe` |
| Android | `restore-privacy-client-0.3.7-android.apk` |
| macOS | `restore-privacy-client-0.3.7-macos.zip` *(Developer ID signed + notarized)* |
| iOS | `restore-privacy-client-0.3.7-ios.zip` *(Team-signed sideload)* |
| Ubuntu / Linux | `restore-privacy-client-0.3.7-linux-x64.tar.gz` |

### Windows

1. On the [status downloads page](https://restoreprivacy.online/), pay **£2.45** for **Windows** and download **`restore-privacy-client-0.3.7-windows-x64-setup.exe`** (one-time link after payment).
2. Run the installer (PE self-extracting package: frozen runtime + Wintun — no separate Python install). The package may extract as a portable tree or install under LocalAppData.
3. Open **Settings → Payment entitlement**, paste the Checkout session id from the thank-you page (or import `payment_entitlement.json`), and **Verify payment** so Connect is allowed.
4. Press **Connect** and approve **UAC** when prompted so residual public IP uses the VPN node. Scoped **Windows Defender Firewall** allows (node UDP + program) may be applied for residual Connect.
5. Optional: **Settings** → startup / autoconnect (defaults **off**); legal links to audit / privacy / licence.
6. **Disconnect** / **Quit** tears down dual `/1` residual routes so ordinary internet works again. For **complete removal**, use **Restore Internet** (see warning below).

### Android

1. On the [status downloads page](https://restoreprivacy.online/), pay **£2.45** for **Android** and download **`restore-privacy-client-0.3.7-android.apk`** (one-time link after payment).
2. Install the APK (allow install from unknown sources if your device asks). Catalog APK includes residual wire (**PFS + outer obfs**).
3. Open **Restore Privacy** → **Settings → Payment entitlement**, paste the Checkout session id and **Verify payment**.
4. Press **Connect**, and grant **VPN** permission when prompted.
5. Optional: **Settings** → startup / autoconnect (defaults off). Minimize keeps the VPN service running until **Disconnect**.
6. For complete removal, open the in-package **Restore Internet** guidance and uninstall via system Settings.

### Ubuntu and derivatives (Linux Mint, Pop!_OS, …)

Supported floor: **Ubuntu 20.04 LTS** and later (including 22.04 / 24.04 LTS).

1. On the [status downloads page](https://restoreprivacy.online/), pay **£2.45** for **Linux** and download **`restore-privacy-client-0.3.7-linux-x64.tar.gz`** (one-time link after payment).
2. Unpack and run the bundled installer:
   ```bash
   tar xzf restore-privacy-client-0.3.7-linux-x64.tar.gz
   cd restore-privacy-*-linux   # package folder name from the archive
   bash install.sh
   ```
3. Run **`sudo ./bin/privacy-restored`** for residual public IP (TUN + dual `/1` routes).
4. Failsafe: **`sudo bash "./Restore Internet"`** restores normal internet and removes the product (see warning below).

### macOS

Published **v0.3.7** macOS builds are **Developer ID signed and notarized**.

1. On the [status downloads page](https://restoreprivacy.online/), pay **£2.45** for **macOS** and download **`restore-privacy-client-0.3.7-macos.zip`** (one-time link after payment).
2. Unzip and open **`restore_privacy_client.app`**.
3. Press **Connect** and approve the **VPN configuration** prompt.
4. Residual public IP only changes when the Packet Tunnel is **active**. Host-only HELLO is **diagnostic** only. Residual public-IP via Packet Tunnel on a developer Mac still needs **Team residual re-sign** (`scripts/sign_macos_residual_team.py`) — the public Developer ID zip alone is not full host-NE residual (see `client_app/APPLE_HANDOFF_0.3.7.md`). **Disconnect** / **Quit** stops the system VPN.
5. Failsafe: run **`Restore Internet.command`** in the package (or follow VPN Settings cleanup) — see warning below.

### iOS

Published **v0.3.7** iOS packages are **Team-signed sideload** zips (not App Store).

1. On the [status downloads page](https://restoreprivacy.online/), pay **£2.45** for **iOS** and download **`restore-privacy-client-0.3.7-ios.zip`** (one-time link after payment).
2. Install **`Runner.app`** with device tooling; press **Connect** and grant **VPN** permission.
3. Residual public IP only changes when the Packet Tunnel is **active**.
4. Complete removal: follow **`Restore Internet.txt`** (Settings → VPN / Delete App) — see warning below.

### VPN APP Shop

https://restoreprivacy.online/

- **Pay £2.45** buttons for Windows, Android, macOS, iOS, Linux — catalog **v0.3.7**  
- Installers are delivered **after payment** (single-use link); the product repo is private  
- **No** public live session / connected-client counter  
- A browser tab cannot run full system VPN

### Restore Internet (failsafe) — BIG WARNING

Every catalog installer includes a **Restore Internet** failsafe (Windows/Linux
runnable script; macOS `.command`; iOS/Android guidance). Use it only when you
need residual internet restored **and** complete product removal.

> **WARNING:** Running **Restore Internet** will **ERASE ALL** parts of
> **Restore Privacy** from the device (app, tunnel residual, shortcuts, product
> secrets). You may **not** be able to automatically re-download your
> subscription app afterward. Contact **russell.gray.sneddon@gmail.com** to
> obtain a new download link.

---

## Privacy, license, credits, and audit

| Document | Link |
|----------|------|
| **Privacy policy** | [PRIVACY_POLICY.md](PRIVACY_POLICY.md) |
| **License** | [LICENSE](LICENSE) (proprietary full copyright) |
| **Credits** | [CREDITS.md](CREDITS.md) |
| **Code & policy audit** | [AUDIT.md](AUDIT.md) |

Core promises: **no user-info logs** by design, **minimal public status** (title + downloads + **entry-only clear timer** for Node A / entry weekly wipe — **no exit wipe countdown**; exit stays up for residual failover — **no live client count**), **device keys** (not a shared client private key), **honest residual** only when full tunnel is up, **no third-party geo** on Connect. Product residual paths on **all platforms** (Windows, Linux, Android, iOS, macOS) enable **outer-layer obfuscation** and **padding / jitter / cover** by default; **kill-switch is not applied by default**. **Disconnect / Quit** restores residual routes (no intentional blackhole after normal teardown). **Restore Internet** is a full wipe failsafe (not ordinary Disconnect). Multi-hop residual is **opt-in** (`RPT_MULTIHOP_ENABLED=1`): residual dials the Romania exit when multi-hop is active (routing implemented); default remains single-hop Iceland entry. **Weekly entry wipe** (~7d) with exit residual failover while entry drains. Licence is **proprietary full copyright** (not MIT for original code). Node tunnel DNS uses **DoT** upstream. Production node VPS: **Iceland / FlokiNET** — **as far as we can be assured** from host public statements, **no invasive logs** of users connecting to the node (privacy §3.1 / §4).

---

## Threat model

Short user-education summary. Full policy language: **[PRIVACY_POLICY.md — Threat model](PRIVACY_POLICY.md)**. Scenario detail for operators/auditors: **[AUDIT.md §4.6](AUDIT.md)** (VPS compromise, traffic analysis by ISP, client device seizure).

### What it protects against

- **Residual public IP** uses the VPN node when full tunnel is actually up (honest status otherwise).
- **No user-info logs** on the product node path; **no public live client count**.
- **Per-device keys** (not a shared installer private key).
- **Mitigations** for coarse traffic fingerprints: outer obfuscation + padding/jitter/cover (default on **all** product residual DATA paths) — **not** a claim of DPI-undetectability.
- **Tunnel-only DNS** (`10.88.0.1`) while residual capture is active; **IPv4 residual honesty** when full tunnel is up. Kill-switch firewall blocks are **not** applied by default (opt-in only: `RPT_KILL_SWITCH=1`).
- **PFS** (ephemeral X25519) so long-term key compromise later should not reconstruct past session AEAD keys from the public transcript alone.

### What it does **not** protect against

- **Endpoint correlation** — sites still know you via logins, cookies, and browser fingerprints; many users share one node egress IP.
- **Behavioral analysis** — observers can still study when you connect and rough usage patterns.
- **VPS / provider IP metadata** — product node is **FlokiNET** in **Iceland** (strict Icelandic privacy norms); **as far as we can be assured** from FlokiNET’s public statements the host does **not** retain invasive connection logs of users connecting to the node. Other providers (CDN/status, home ISP, destinations) may still log. Node OS compromise remains a residual risk.
- **Traffic analysis by ISP** beyond mitigations — you still appear to use a VPN; opt-in multi-hop residual uses the Romania exit when enabled
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

**Product ship (v0.3.7):** Paid installers on **[status downloads](https://restoreprivacy.online/)** (macOS Developer ID notarized; iOS Team-signed). Source repo is private. Production node **82.221.101.241:44044** (**Iceland**, **FlokiNET** VPS; host public **no invasive logs** stance as far as we can be assured — see privacy policy).

**Self-host (one shot):** `sudo bash scripts/selfhost_node.sh` — node install + tunnel DNS + host privacy. Deploy remote: `python scripts/deploy_rpt_node.py` (`RPT_SSH_HOST`, `RPT_SSH_USER`, key). Details: [sundries.txt](sundries.txt).

**Tunnel DNS / host privacy:** [node/install_dns.sh](node/install_dns.sh), [node/install_host_privacy.sh](node/install_host_privacy.sh).

**Data at rest (LUKS / dm-crypt):** [node/install_disk_encryption.sh](node/install_disk_encryption.sh) — `check` / `dry-run` / confirmed `format`. Combines with **no-logs** and [shutdown wipe](node/install_shutdown_wipe.sh) (runtime scrub on stop; optional aggressive secrets wipe). Honesty: FDE protects locked disks only; does not erase provider snapshots.

**Ram-only node volume (zram + LUKS2):** [node/install_zram_luks.sh](node/install_zram_luks.sh) — `check` / `dry-run` / `status` / confirm-gated `format` (`RPT_ZRAM_LUKS_CONFIRM=yes`). **Node-host only** — clients never install LUKS/zram; residual Connect is unchanged. Honesty: encrypted RAM-backed volume, not full live-root secrecy, not client FDE, not erasure of VPS provider snapshots/netflow.

**Weekly entry wipe/rebuild (exclusive; exit failover):** [scripts/weekly_entry_rebuild.py](scripts/weekly_entry_rebuild.py) — **~7d** timed **entry-only** snapshot/rebuild (`--dry-run` by default). Exclusive lock ([node/rebuild_lock.py](node/rebuild_lock.py)) refuses a second concurrent wipe and **never** wipes exit/both from this service. **Pre-wipe gates** ([node/wipe_preflight.py](node/wipe_preflight.py)): live path **fail-closed** unless **exit residual** and **entry node** health both pass (UDP response and/or ICMP for exit; local listen/status for entry). After rebuild, **mandatory package reinstall** via selfhost. Clients auto residual-failover to **exit** while entry drains, and **prefer re-entry** when entry is healthy again ([client/multihop.py](client/multihop.py) `select_residual_endpoint`). Public homepage **entry-only** clear timer: [status_page/node_wipe_countdown.py](status_page/node_wipe_countdown.py) (exit wipe countdown removed; weekly service never rebuilds exit). Generic plan: [scripts/ephemeral_node.py](scripts/ephemeral_node.py). Timer: [scripts/install_ephemeral_timer.sh](scripts/install_ephemeral_timer.sh). Live requires `RPT_EPHEMERAL_CONFIRM=yes`. Does not erase provider backups/netflow; re-ship **public** node pin if keys rotate.

**Release scripts:** `scripts/build_release_0.3.7.py`. **Windows multihop PE** (x64 only): `scripts/build_windows_multihop.py` / `scripts\build_windows_multihop.bat` — handoff [`client/windows/WINDOWS_HANDOFF_0.3.7.md`](client/windows/WINDOWS_HANDOFF_0.3.7.md). Apple handoff: [`client_app/APPLE_HANDOFF_0.3.7.md`](client_app/APPLE_HANDOFF_0.3.7.md). Release notes: [`scripts/RELEASE_NOTES_0.3.7.md`](scripts/RELEASE_NOTES_0.3.7.md). Catalog **0.3.7** Windows paid package embeds multihop residual-via-exit (opt-in `RPT_MULTIHOP_ENABLED=1`).

```bash
# Windows GUI (requires system Python)
python -m client.windows

# Windows multihop residual installer (run on Windows x64)
python scripts/build_windows_multihop.py

# Ubuntu / Mint GUI from source (needs system cryptography)
sudo PYTHONPATH=. python3 -m client.linux

# Linux installer package with baked-in crypto wheels (re-run each release)
python scripts/package_linux.py  # manylinux wheels for CPython 3.8–3.12; re-run each release

# Release packages (current tag)
python scripts/build_release_0.3.7.py
```

**Node wipe reinstall (entry ≠ exit):** [docs/NODE_WIPE_REINSTALL.md](docs/NODE_WIPE_REINSTALL.md) — weekly timed wipe is **entry-only** with mandatory full selfhost reinstall; exit is manual/failover.
