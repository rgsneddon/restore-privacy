# Restore Privacy

**Restore Privacy Tunnel (RPT)** is a custom VPN client for private residual connectivity. It is an original product, maintained under **Raskul**’s direction, with regular automated security audits.

| | |
|--|--|
| **Get the app** | [Paid downloads](https://restoreprivacy.online/) — catalog **v0.5.7** (£2.45/month or £27.93/year per platform) |
| **Privacy** | [PRIVACY_POLICY.md](PRIVACY_POLICY.md) |
| **Licence** | [LICENSE](LICENSE) (proprietary full copyright) |
| **Credits** | [CREDITS.md](CREDITS.md) |
| **Security audit** | [AUDIT.md](AUDIT.md) |

---

## At a glance

- **Nodes:** Iceland `82.221.101.241:44044`, Germany `178.105.187.178:44044` (**default residual entry**), United States `5.161.242.85:44044` — residual catalog peers (user-selectable entry; multi-hop exit is Germany). Romania (RO) is deprecated.
- **Connect / Disconnect** by hand. Optional Settings: run at startup, autoconnect on launch (both **off** by default). Settings also links to audit, privacy policy, and licence.
- System tray identity **Privacy Restored** (Windows) with product logo icons.
- Privacy message: `lightweight vpn to restore your privacy - no user data is retained - your privacy is restored`
- Full-device residual IP only when the OS grants VPN permission (Windows UAC + Wintun dual `/1`, Android VPN consent, signed Apple Packet Tunnel). Status is honest when residual is not fully up.
- Close or minimize keeps the tunnel until **Disconnect** or **Quit**. Disconnect restores normal routes and product firewall state (Windows dual `/1` teardown + scoped **RPT-FW** cleanup; Linux TUN/routes teardown).
- Windows product firewall rules are **scoped allows** only (node UDP + program). Kill-switch is **off** unless you set `RPT_KILL_SWITCH=1`.
- **Restore Internet** failsafe in every installer completely removes the product (see warning below).
- Admission is cryptographic (device Ed25519 + node keys) — no third-party geo lookup on Connect.
- Connect uses the standard **HELLO** residual path (**flyclient** fast-path removed in catalog **v0.5.7**).
- **Node-only** optional **zram + LUKS2** encrypted RAM volume (`node/install_zram_luks.sh`) and optional **LUKS2 disk** at-rest (`node/install_disk_encryption.sh`) — not client encryption; residual Connect unchanged.
- Session **PFS** (ephemeral X25519) on residual HELLO for all product clients (Python Windows/Linux, Android, iOS/macOS Packet Tunnel).
- **Outer obfuscation** (QUIC-mimic wrap) and **traffic shaping** (pad / jitter / cover) are **off** by default (lean residual). Turn them on in Settings (`RPT_OBFS=1` / `RPT_TRAFFIC_SHAPE=1` also force on for Python) — mitigations, not “undetectable DPI”. When on: pad bucket 128, cover ~2s, jitter ≤40ms.
- Tunnel DNS only (`10.88.0.1`, no public DNS fallbacks) while residual capture is active.
- Multi-hop residual is **opt-in** (`RPT_MULTIHOP_ENABLED=1`): exit is **Germany (DE)** (product exit monopin). Default is single-hop **Germany** entry. **residual-via-exit** routing is implemented (not hop-list-only).
- Status site shows a **live preferred-entry clear timer** (~7 days). Fleet wipe is **sequential** (IS → DE → US, one peer at a time) — never concurrent multi-node wipe.
- **Weekly** sequential fleet wipe/rebuild (~7d): exclusive lock; clients auto hop to a healthy alternate while a peer drains, then rejoin preferred when ready (not zero packet-loss).
- **Near-capacity residual migration (opt-in):** when `RPT_CAPACITY_TOKEN` is set on residual **nodes** and on **operator/env-capable clients**, Connect can probe a **private** capacity signal and dial a freer catalog peer if the preferred node is near connection capacity (CLI advisory). Public status stays **title-only** — **no live client count**. See [docs/CAPACITY_PROBES.md](docs/CAPACITY_PROBES.md).
- Security audit documents **per-installer AUDIT STATE** (Green / Amber / Red) for catalog packages — [AUDIT.md](AUDIT.md).
- End-user licence is **proprietary full copyright** ([LICENSE](LICENSE)): client packages **AS IS**, use only to run a device on Restore Privacy VPN; no architecture copy/transmission.

---

## Buy, unlock, and Connect

Installers are **paid only** on [restoreprivacy.online](https://restoreprivacy.online/) (Stripe). There are no free permanent GitHub release downloads; the source repo is **private**.

**Current catalog (v0.5.7):** the homepage **Download client** box has device/platform and plan selection — **Monthly VPN plan** £2.45 / **Yearly VPN plan** £27.93 (5% off) — plus **Buy now**, which opens Stripe Checkout. You can also open the plan page at **`/pay`**. Card payment uses Stripe’s hosted checkout (Dashboard branding only — not this site’s full CSS). Email delivers **keygen + PPI + download link** (**USE THIS KEYGEN TO UNLOCK RESTORE PRIVACY**).

1. Pick your **device** and **plan**, then **Buy now** (or open `/pay`).
2. Complete Stripe Checkout. You get a download link valid for **1 hour** (retry if the connection drops) plus email with **keygen** (`RPT-KEY-…`) and **PPI**.
3. Install → **accept the licence** → **enter the keygen** (forced unlock on all platforms). Download alone does **not** unlock residual HELLO.
4. **Connect** while status is **OK** (active subscription + keygen). If payment fails, refunds, or the period ends, status is **EXPIRED** — the app hard-locks with **renew your licence *here*** and a platform-specific Stripe payment portal link until you pay again and re-enter a keygen.

Weekly wipe UI shows the **preferred-entry clear timer** (no dual Node A/B wipe countdown). Fleet wipe is sequential behind the scenes. After payment the status site delivers the installer via a 1-hour download link (authenticated proxy; retry if the connection drops).

> **Payment required for Connect:** residual Connect needs successful payment and keygen unlock while the subscription is active. Failed checkout, failed charge, refund, dispute, or period end → **EXPIRED** until you renew and re-enter a valid keygen.

The app re-checks the status host (`/api/connect-entitlement`) on each Connect so a later failure becomes **EXPIRED** immediately. Settings → Payment entitlement is a fallback unlock path; thank-you may still auto-download `payment_entitlement.json`. Residual errors that look like remote reset/timeout include keygen guidance.

| Platform | Package |
|----------|---------|
| Windows | `restore-privacy-client-0.5.7-windows-x64-setup.exe` *(PE from Windows host — see WINDOWS_HANDOFF_0.5.7 / Helsinki breadcrumbs)* |
| Android | `restore-privacy-client-0.5.7-android.apk` *(**native** monopin 0.5.7; DE pin + IPv4 always-on)* |
| macOS | `restore-privacy-client-0.5.7-macos.zip` *(**native** DevID + notarized; see APPLE_HANDOFF_0.5.7)* |
| iOS | `restore-privacy-client-0.5.7-ios.zip` *(**native** Team-signed sideload; see APPLE_HANDOFF_0.5.7)* |
| Ubuntu / Linux | `restore-privacy-client-0.5.7-linux-x64.tar.gz` *(**native** rebuild)* |
| Browser (Chromium MV3) | browser proxy only, not OS residual TUN |

### Browser extension (Chromium MV3)

1. Get **`restore-privacy-browser-extension.zip`** from the [0.5.1 release assets](https://github.com/rgsneddon/restore-privacy/releases/tag/0.5.5) (or build from `browser_extension/`).
2. Unzip → Chromium/Chrome/Edge **Extensions** → Developer mode → **Load unpacked** → select the extension folder.
3. Use **Connect** / **Disconnect** in the toolbar popup. This is **browser-scoped** (`chrome.proxy` / local SOCKS path) — it does **not** replace paid native residual clients for system residual public IP.
4. Source and honesty notes: [`browser_extension/README.md`](browser_extension/README.md).

### Windows

1. On the [status downloads page](https://restoreprivacy.online/), choose **Monthly £2.45** or **Yearly** for **Windows** and download **`restore-privacy-client-0.5.7-windows-x64-setup.exe`** (one-time link after payment).
2. Run the installer (PE self-extracting package: frozen runtime + Wintun — no separate Python install). Default install is **Program Files\\Restore Privacy** (elevation when required); per-user fallback if Program Files is unwritable.
3. **Accept the end-user licence**, then enter the **keygen** from your fulfilment email (forced unlock dialog). Settings → Payment entitlement is a fallback only. Connect is allowed only when status is **OK** (active subscription **and** keygen activated).
4. Press **Connect** and approve **UAC** when prompted so residual public IP uses the VPN node. Scoped **Windows Defender Firewall** allows (node UDP + program) may be applied for residual Connect.
5. Optional: **Settings** → startup / autoconnect (defaults **off**); legal links to audit / privacy / licence.
6. **Disconnect** / **Quit** tears down dual `/1` residual routes so ordinary internet works again. For **complete removal**, use **Restore Internet** (see warning below).

### Android

1. On the [status downloads page](https://restoreprivacy.online/), choose **Monthly £2.45** or **Yearly** for **Android** and download **`restore-privacy-client-0.5.7-android.apk`** (one-time link after payment).
2. Install the APK (allow install from unknown sources if your device asks). Catalog APK includes residual wire (**PFS + outer obfs**).
3. **Accept the licence**, then enter the **keygen** from email (forced unlock sheet). Connect requires **OK** (active subscription + keygen).
4. Press **Connect**, and grant **VPN** permission when prompted.
5. Optional: **Settings** → startup / autoconnect (defaults off). Minimize keeps the VPN service running until **Disconnect**.
6. For complete removal, open the in-package **Restore Internet** guidance and uninstall via system Settings.

### Ubuntu and derivatives (Linux Mint, Pop!_OS, …)

Supported floor: **Ubuntu 20.04 LTS** and later (including 22.04 / 24.04 LTS).

1. On the [status downloads page](https://restoreprivacy.online/), choose **Monthly £2.45** or **Yearly** for **Linux** and download **`restore-privacy-client-0.5.7-linux-x64.tar.gz`** (one-time link after payment).
2. Unpack and run the bundled installer:

   ```bash
   tar xzf restore-privacy-client-0.5.7-linux-x64.tar.gz
   cd restore-privacy-*-linux   # package folder name from the archive
   bash install.sh
   ```

3. **Accept the licence** and **enter keygen** before Connect. Run **`sudo ./bin/privacy-restored`** for residual public IP (TUN + dual `/1` routes).
4. Failsafe: **`sudo bash "./Restore Internet"`** restores normal internet and removes the product (see warning below).

### macOS

**Monopin 0.5.7 macOS** is on the Helsinki paid store (Developer ID + notarized). See `client_app/APPLE_HANDOFF_0.5.7.md`.

1. On the [status downloads page](https://restoreprivacy.online/), choose **Monthly £2.45** or **Yearly** for **macOS** and download **`restore-privacy-client-0.5.7-macos.zip`** (one-time link after payment).
2. Unzip and open **`restore_privacy_client.app`**.
3. **Accept the licence** and **enter keygen**, then press **Connect** and approve the **VPN configuration** prompt.
4. Residual public IP only changes when the Packet Tunnel is **active**. Host-only HELLO is **diagnostic** only. **Disconnect** / **Quit** stops the system VPN. See `client_app/APPLE_HANDOFF_0.5.7.md`.
5. Failsafe: run **`Restore Internet.command`** in the package (or follow VPN Settings cleanup) — see warning below.

### iOS

**Monopin 0.5.7 iOS** is on the Helsinki paid store (Team-signed sideload). See `client_app/APPLE_HANDOFF_0.5.7.md`.

1. On the [status downloads page](https://restoreprivacy.online/), choose **Monthly £2.45** or **Yearly** for **iOS** and download **`restore-privacy-client-0.5.7-ios.zip`** (one-time link after payment).
2. Install **`Runner.app`** with device tooling; **accept licence**, **enter keygen**, then press **Connect** and grant **VPN** permission.
3. Residual public IP only changes when the Packet Tunnel is **active**.
4. Complete removal: follow **`Restore Internet.txt`** (Settings → VPN / Delete App) — see warning below.

### VPN APP Shop

https://restoreprivacy.online/

- **Monthly £2.45** and **Yearly** pay controls per platform (Windows, Android, macOS, iOS, Linux) — catalog **v0.5.7**
- Installers are delivered **after payment** (link valid for 1 hour, reusable until expiry); the product repo is private
- Connect requires **keygen activation** on an **active** subscription (**OK**); **EXPIRED** shows **renew your licence *here*** with a platform payment portal link
- **No** public live session / connected-client counter
- A browser tab cannot run full system VPN

### Restore Internet (failsafe)

Every catalog installer includes a **Restore Internet** failsafe (Windows/Linux runnable script; macOS `.command`; iOS/Android guidance). Use it only when you need residual internet restored **and** complete product removal.

> **Warning:** Restore Internet **erases all** Restore Privacy material on the device (app, tunnel residual, shortcuts, product secrets). You may not re-download automatically afterward. Contact **rus@restoreprivacy.online** for a new link, or pay again on the status page. Ordinary **Disconnect** is not a full wipe.

### Support logs (on your device only)

Connect/session diagnostics stay **only on your device** in a **hidden** file. The app does **not** upload them. If support asks for logs, export from Settings (**Export log**) or copy the hidden file, then **email it yourself**.

| Platform | Hidden on-device path |
|----------|----------------------|
| **Windows** | `%LOCALAPPDATA%\RestorePrivacy\.rpt_support_log.jsonl` |
| **Linux** | `~/.local/share/restore-privacy/.rpt_support_log.jsonl` (or `$XDG_DATA_HOME/restore-privacy/.rpt_support_log.jsonl`) |

On Windows, enable **View → Hidden items** in File Explorer if the file is not visible. Filename always starts with a dot (`.rpt_support_log.jsonl`). Older installs may still have `connection_log.jsonl` in the same folder until the app migrates it to the hidden name.

---

## Privacy in one page

| Document | Link |
|----------|------|
| **Privacy policy** | [PRIVACY_POLICY.md](PRIVACY_POLICY.md) |
| **Licence** | [LICENSE](LICENSE) (proprietary full copyright) |
| **Credits** | [CREDITS.md](CREDITS.md) |
| **Code & policy audit** | [AUDIT.md](AUDIT.md) |

Core promises: **no user-info logs** by design, **minimal public status** (title + downloads + **preferred-entry clear timer** — **no live client count**), **device keys** (not a shared client private key), **honest residual** only when full tunnel is up, **no third-party geo** on Connect. Product residual paths on **all platforms** (Windows, Linux, Android, iOS, macOS) keep **outer-layer obfuscation** and **padding / jitter / cover** **off by default** (lean residual) until the user turns them **on** in Settings; **kill-switch is not applied by default**. **Disconnect / Quit** restores residual routes (no intentional blackhole after normal teardown). **Restore Internet** is a full wipe failsafe (not ordinary Disconnect). Multi-hop residual is **opt-in** (`RPT_MULTIHOP_ENABLED=1`): exit is a **random non-entry** catalog peer; default is single-hop on the chosen entry. **Weekly sequential fleet wipe** (~7d, IS → DE → US, one peer at a time) with auto hop to a healthy alternate while a peer drains. Licence is **proprietary full copyright** (not MIT for original code). Node tunnel DNS uses **DoT** upstream. Catalog peers: **IS/RO FlokiNET**, **US** residual peer — host public **no invasive logs** stance where published (privacy policy).

---

## Threat model

Short user-education summary. Full policy language: **[PRIVACY_POLICY.md — Threat model](PRIVACY_POLICY.md)**. Scenario detail for operators/auditors: **[AUDIT.md §4.6](AUDIT.md)** (VPS compromise, traffic analysis by ISP, client device seizure).

### What it protects against

- **Residual public IP** uses the VPN node when full tunnel is actually up (honest status otherwise).
- **No user-info logs** on the product node path; **no public live client count**.
- **Per-device keys** (not a shared installer private key).
- **Mitigations** for coarse traffic fingerprints: outer obfuscation + padding/jitter/cover (**off by default**; turn **on** in Settings on residual DATA paths) — **not** a claim of DPI-undetectability.
- **Tunnel-only DNS** (`10.88.0.1`) while residual capture is active; **IPv4 residual honesty** when full tunnel is up. Kill-switch firewall blocks are **not** applied by default (opt-in only: `RPT_KILL_SWITCH=1`).
- **PFS** (ephemeral X25519) so long-term key compromise later should not reconstruct past session AEAD keys from the public transcript alone.

### What it does not protect against

- **Endpoint correlation** — sites still know you via logins, cookies, and browser fingerprints; many users share one node egress IP.
- **Behavioral analysis** — observers can still study when you connect and rough usage patterns.
- **VPS / provider IP metadata** — catalog peers include **FlokiNET** (IS/RO) and the **US** residual host; host public **no invasive logs** stance is not a forensic audit. Other providers (CDN/status, home ISP, destinations) may still log. Node OS compromise remains a residual risk.
- **Traffic analysis by ISP** beyond mitigations — you still appear to use a VPN; opt-in multi-hop residual dials a non-entry catalog peer when enabled.
- **Client device seizure** — local keys, apps, and browser history on an unlocked device are out of scope for the node’s no-log promise.
- Malware, compromised OS, or destination-site tracking.

Detail: privacy policy threat model + [AUDIT.md §4.6](AUDIT.md).

---

## Operators / developers

Node deploy, ports, secrets, from-source builds, and tests: **[sundries.txt](sundries.txt)**.

**Device keys:** packages do **not** ship a shared client private key; each install generates its own Ed25519 device key on first run.

**Secrets discipline:** Never commit or force-add `secrets/` (gitignored). Paid release packages must never include `node_elgamal.priv` or a shared `client_ed25519.priv`. Release scripts run `_assert_no_priv` / strip inject gates — keep those on every tag.

**Node key protection:** `RPT_KEY_BACKEND=file|mock|sealed|tpm` — sealed/TPM-class stores long-term ElGamal under a wrap key so plaintext `.priv` is not required on disk. See `node/key_backend.py`.

**Key rotation:** `python scripts/rotate_node_keys.py --secrets-dir …` updates node long-term material + `product/node_elgamal.pub` pin; clients re-provision **public** only (`reprovision_node_public`). Session **PFS** (X25519) is the product default.

**Post-quantum readiness:** staged hybrid Kyber/ML-KEM hook in `node/pq_hybrid.py` + plan [`docs/PQ_MIGRATION.md`](docs/PQ_MIGRATION.md) (not residual PQ on the wire until dual-wire + real ML-KEM).

**Product ship (v0.5.7):** Paid installers on **[status downloads](https://restoreprivacy.online/)**. **macOS** is **native monopin 0.5.7** Developer ID + notarized (Team **SFCBP95595**); **iOS** Team-signed sideload — see `APPLE_HANDOFF_0.5.7.md`. **Android** and **Linux** are native on this pin; **Windows** PE is built/uploaded from the Windows host (`WINDOWS_HANDOFF_0.5.7.md` + Helsinki breadcrumbs). Catalog residual peers: **IS** / **DE** (default) / **US** — Romania deprecated.

**Self-host (one shot):** `sudo bash scripts/selfhost_node.sh` — node install + tunnel DNS + host privacy. Deploy remote: `python scripts/deploy_rpt_node.py` (`RPT_SSH_HOST`, `RPT_SSH_USER`, key). Details: [sundries.txt](sundries.txt).

**Tunnel DNS / host privacy:** [node/install_dns.sh](node/install_dns.sh), [node/install_host_privacy.sh](node/install_host_privacy.sh).

**Data at rest (LUKS / dm-crypt):** [node/install_disk_encryption.sh](node/install_disk_encryption.sh) — `check` / `dry-run` / confirmed `format`. Combines with **no-logs** and [shutdown wipe](node/install_shutdown_wipe.sh) (runtime scrub on stop; optional aggressive secrets wipe). Honesty: FDE protects locked disks only; does not erase provider snapshots.

**Ram-only node volume (zram + LUKS2):** [node/install_zram_luks.sh](node/install_zram_luks.sh) — `check` / `dry-run` / `status` / confirm-gated `format` (`RPT_ZRAM_LUKS_CONFIRM=yes`). **Node-host only** — clients never install LUKS/zram; residual Connect is unchanged. Honesty: encrypted RAM-backed volume, not full live-root secrecy, not client FDE, not erasure of VPS provider snapshots/netflow.

**Weekly sequential fleet wipe/rebuild:** [node/fleet_wipe.py](node/fleet_wipe.py) + [scripts/weekly_entry_rebuild.py](scripts/weekly_entry_rebuild.py) — **~7d** timed wipe, **one peer at a time** (**IS → DE → US**). Exclusive lock ([node/rebuild_lock.py](node/rebuild_lock.py)) refuses concurrent multi-node wipe. **Pre-wipe gates** ([node/wipe_preflight.py](node/wipe_preflight.py)): live path **fail closed** unless alternate residual and target peer health both pass. After rebuild, **mandatory package reinstall** via selfhost. Clients auto hop to a healthy alternate while a peer drains, then rejoin preferred when ready ([client/multihop.py](client/multihop.py)). Public homepage preferred-entry clear timer: [status_page/node_wipe_countdown.py](status_page/node_wipe_countdown.py). Results log: [docs/FLEET_WIPE_RESULTS_2026-07-25.md](docs/FLEET_WIPE_RESULTS_2026-07-25.md). Live requires `RPT_EPHEMERAL_CONFIRM=yes`. Does not erase provider backups/netflow; re-ship **public** node pins if keys rotate.

**Private capacity probes (near-capacity residual migration):** [docs/CAPACITY_PROBES.md](docs/CAPACITY_PROBES.md). Residual nodes: `sudo bash scripts/install_capacity_token_env.sh` (sets durable `RPT_CAPACITY_TOKEN` for token-gated `/api/private/capacity`). Operator clients: `export RPT_CAPACITY_TOKEN='…'` (same secret). Optional: `RPT_CAPACITY_PROBE_URLS`, `RPT_CAPACITY_PROBE_TIMEOUT`, `RPT_NODE_MAX_SESSIONS`. Template: [scripts/hop_env.example](scripts/hop_env.example). **RO Mac SSH finalize** (unlimited-class / extendable-at-cost bandwidth when Windows keys cannot reach RO): [docs/RO_CAPACITY_MAC_FINALIZE.md](docs/RO_CAPACITY_MAC_FINALIZE.md). **No public client counts** — public status remains title-only; missing token leaves probes off.

**Release scripts:** `scripts/build_release_0.5.7.py`. **Windows multihop PE** (x64 only): `scripts/build_windows_multihop.py` / `scripts\build_windows_multihop.bat` — handoff [`client/windows/WINDOWS_HANDOFF_0.5.7.md`](client/windows/WINDOWS_HANDOFF_0.5.7.md). Release notes: [`scripts/RELEASE_NOTES_0.5.7.md`](scripts/RELEASE_NOTES_0.5.7.md). Catalog **0.5.7** Apple/Android/Linux hosted; Windows PE from Windows host; multihop residual-via-exit remains opt-in (`RPT_MULTIHOP_ENABLED=1` / Settings multi-hop).

```bash
# Windows GUI (requires system Python)
python -m client.windows

# Windows multihop residual installer (run on Windows x64)
python scripts/build_windows_multihop.py

# Ubuntu / Mint GUI from source (needs system cryptography)
sudo PYTHONPATH=. python3 -m client.linux

# Linux installer package with baked-in crypto wheels (re-run each release)
python scripts/package_linux.py  # manylinux wheels for CPython 3.8—3.12; re-run each release

# Release packages (current tag)
python scripts/build_release_0.5.7.py
```

**Node wipe reinstall (sequential fleet):** [docs/NODE_WIPE_REINSTALL.md](docs/NODE_WIPE_REINSTALL.md) — weekly wipe is **one peer at a time** (IS → DE → US) with mandatory full selfhost reinstall; never concurrent multi-node wipe.
