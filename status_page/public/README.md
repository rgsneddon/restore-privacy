# Restore Privacy Suite

**Restore Privacy Suite v1.0.7** is the full app: residual protection, a private
wallet, and Evolve analysis together. Maintained under **Raskul**’s direction,
with regular automated security audits.

| | |
|--|--|
| **Download** | Free installers on [restoreprivacy.online](https://restoreprivacy.online/) — catalog **v1.0.7** |
| **Use residual Connect** | KEYGEN licence from **£3.00/month** (Stripe); yearly residual plan **£30.00** still on **`/pay`** |
| **Privacy** | [PRIVACY_POLICY.md](PRIVACY_POLICY.md) |
| **Licence** | [LICENSE](LICENSE) (proprietary full copyright) |
| **Credits** | [CREDITS.md](CREDITS.md) |
| **Security audit** | [AUDIT.md](AUDIT.md) |
| **Public pages** | https://rgsneddon.github.io/restore-privacy-suite/ · open source: [rgsneddon/restore-privacy-suite](https://github.com/rgsneddon/restore-privacy-suite) · monorepo export [`public_site/`](public_site/) |

---

## What you get

Install the Suite for free. When you want residual Connect, take a monthly
licence, paste the KEYGEN from your fulfilment email, and connect. Download
alone does not unlock residual traffic.

Inside the app: **VPN**, **%** (wallet), **EVOLVE**, and **rpAI** (Ned helper).
One KEYGEN story unlocks residual Connect. Wallet and Evolve share an **optional**
unified Suite account (deferrable). Browser and Vault landings stay on the same
public chrome for what comes next.

---

## How to start

1. Download your platform build for free from the Suite storefront.
2. Install and accept the end-user licence.
3. Buy a KEYGEN (from **£3.00/month**) on the site — or open **`/pay`** for
   **Monthly VPN plan** / **Yearly VPN plan** (£30.00) residual client options —
   then enter the KEYGEN in the app.
4. Connect while the licence is **OK**. Residual Connect is unlocked by KEYGEN
   only — **not** by wallet or Evolve registration.
5. **Optional** after KEYGEN: **Register for % wallet & Evolve?** — one Suite
   account for Perccent (**%**) and Evolve (**EVOLVE**). Choose **Not now — use
   VPN only** to defer; Connect keeps working. Resume the same setup later from
   the **rpAI** (Ned) tab via **Continue wallet & analyser setup**.

Card payment uses Stripe’s hosted checkout. Email delivers **KEYGEN** (`RPT-KEY-…`)
and fulfilment details (**USE THIS KEYGEN TO UNLOCK RESTORE PRIVACY**). Failed
payment, refund, or period end → status **EXPIRED** until you renew and re-enter
a valid KEYGEN.

The app re-checks the status host (`/api/connect-entitlement`) on each Connect.
Settings → Payment entitlement is a fallback unlock path.

> **Payment for Connect, not for the installer:** residual Connect needs an active
> KEYGEN while the subscription is valid. The free download is only the package.
> Suite wallet/Evolve sign-up is optional and never gates Connect.

Operator / implementer detail:
[docs/SUITE_ACCOUNT_AND_RPAI.md](docs/SUITE_ACCOUNT_AND_RPAI.md) ·
[client_app/SUITE.md](client_app/SUITE.md).

---

## At a glance

- **VPN**, **%**, **EVOLVE**, and **rpAI** (Ned) tabs in one Suite shell
  (catalog monopin matches `client/VERSION` — currently **1.0.7** on storefront).
- **Optional Suite account** after KEYGEN: one sign-up/sign-in for **%** and
  **EVOLVE**; **Not now — use VPN only** defers without blocking Connect.
- **rpAI / Ned:** resume deferred wallet & analyser setup; registered users get
  **Offer how-to** with stepped **Continue…** explainers, then optional VPN tour.
- Residual peers: Iceland `82.221.101.241:44044`, Germany `178.105.187.178:44044`
  (**default residual entry**). Multi-hop exit is Germany. United States (US) and
  Romania (RO) residual peers are **retired**.
- **Connect / Disconnect** by hand. Optional Settings: run at startup, autoconnect
  on launch (both **off** by default). Settings also links to audit, privacy, and
  licence — and a quiet local loft link when the app is open.
- System tray identity **Privacy Restored** (Windows) with product logo icons.
- Full-device residual IP only when the OS grants VPN permission. Status is honest
  when residual is not fully up.
- Close or minimize keeps the tunnel until **Disconnect** or **Quit**.
- Windows product firewall rules are **scoped allows** only. Kill-switch is **off**
  unless you set `RPT_KILL_SWITCH=1`.
- **Restore Internet** failsafe in every installer completely removes the product.
- Admission is cryptographic (device Ed25519 + node keys) — no third-party geo on Connect.
- Connect uses the standard **HELLO** residual path.
- Session **PFS** (ephemeral X25519) on residual HELLO for product clients.
- **Outer obfuscation** and **traffic shaping** are **off** by default (lean residual).
  Turn them on in Settings (`RPT_OBFS=1` / `RPT_TRAFFIC_SHAPE=1` also force on for Python).
- Tunnel DNS only (`10.88.0.1`) while residual capture is active.
- Multi-hop residual is **opt-in** (`RPT_MULTIHOP_ENABLED=1`): exit is **Germany (DE)**.
  Default is single-hop **Germany** entry. **residual-via-exit** routing is implemented
  (not hop-list-only).
- Public site shows a **live preferred-entry clear timer** (~7 days). Fleet wipe is
  **sequential** (IS → DE, one peer at a time) — never concurrent multi-node wipe.
- **Weekly** sequential fleet wipe/rebuild (~7d): exclusive lock; clients **best-effort**
  hop (**failover**) to a healthy alternate while a peer drains, then rejoin preferred
  when ready (not zero packet-loss). **Failsafe:** if hop does not succeed, the client
  may disconnect or restart and will require **manual reconnection** whilst
  privacy-preserving weekly node wipedown occurs.
- Wipe UI is **entry-only**: preferred-entry **clear timer** only — **no exit wipe
  countdown**, and no dual **Node A**/B wipe countdown.
- **Near-capacity residual migration (opt-in):** when `RPT_CAPACITY_TOKEN` is set,
  Connect can probe a private capacity signal. Public status stays **title-only** —
  **no live client count**. See [docs/CAPACITY_PROBES.md](docs/CAPACITY_PROBES.md).
- Security audit documents **per-installer AUDIT STATE** — [AUDIT.md](AUDIT.md).
- End-user licence is **proprietary full copyright** ([LICENSE](LICENSE)).

---

## Packages

| Platform | Package |
|----------|---------|
| Windows | `restore-privacy-client-1.0.7-windows-x64-setup.exe` |
| Android | `restore-privacy-client-1.0.7-android.apk` |
| macOS | `restore-privacy-client-1.0.7-macos.zip` |
| iOS | `restore-privacy-client-1.0.7-ios.zip` |
| Linux x64 | `restore-privacy-client-1.0.7-linux-x64.tar.gz` |
| Browser (Chromium MV3) | browser proxy only, not OS residual TUN |

### Windows

1. On the [VPN APP Shop](https://restoreprivacy.online/), download **Windows** free
   from the Suite storefront (`/suite/download?platform=windows`).
2. Run the installer. Default install is **Program Files\\Restore Privacy**.
3. Accept the licence, enter the **KEYGEN** from your fulfilment email.
4. Press **Connect** and approve **UAC** when prompted.
5. **Disconnect** / **Quit** tears down residual routes. For complete removal, use
   **Restore Internet**.

### Android

1. Download **Android** free from the Suite storefront.
2. Install the APK (allow unknown sources if asked).
3. Accept the licence, enter the KEYGEN, press **Connect**, grant **VPN** permission.

### Linux (Ubuntu and derivatives)

Supported floor: **Ubuntu 20.04 LTS** and later.

1. Download **Linux** free from the Suite storefront.
2. Unpack and run:

   ```bash
   tar xzf restore-privacy-client-1.0.7-linux-x64.tar.gz
   cd restore-privacy-*-linux
   bash install.sh
   ```

3. Accept the licence and enter KEYGEN before Connect. Residual public IP needs
   **`sudo ./bin/privacy-restored`** (TUN + dual `/1` routes).
4. Failsafe: **`sudo bash "./Restore Internet"`**.

### macOS

1. Download **macOS** free from the Suite storefront.
2. Unzip and open **`restore_privacy_client.app`**.
3. Accept the licence, enter KEYGEN, press **Connect**, approve **VPN configuration**.
4. Failsafe: **`Restore Internet.command`** in the package.

### iOS

1. Download **iOS** free from the Suite storefront.
2. Install **`Runner.app`** with device tooling; accept licence, enter KEYGEN,
   grant **VPN** permission.
3. Complete removal: follow **`Restore Internet.txt`**.

### Browser extension (Chromium MV3)

Browser-scoped proxy only — it does not replace native residual Connect.
See [`browser_extension/README.md`](browser_extension/README.md).

### VPN APP Shop

https://restoreprivacy.online/

- **Suite free installers** first, then **KEYGEN** from **£3.00/month**
- **Monthly VPN plan** and **Yearly VPN plan** (£30.00) residual options on **`/pay`**
- Catalog **v1.0.7** — Connect needs KEYGEN on an **active** subscription (**OK**)
- **No** public live session / connected-client counter
- Public GitHub Pages tree (`public_site/`) has **no** `/admin` and no operator console

### Restore Internet (failsafe)

Every catalog installer includes a **Restore Internet** failsafe. Use it only when
you need residual internet restored **and** complete product removal.

> **Warning:** Restore Internet **erases all** Restore Privacy material on the
> device. Ordinary **Disconnect** is not a full wipe. Contact
> **rus@restoreprivacy.online** if you need a fresh fulfilment path.

### Support logs (on your device only)

Connect diagnostics stay **only on your device** in a **hidden** file. The app
does **not** upload them. Export from Settings if support asks.

| Platform | Hidden on-device path |
|----------|----------------------|
| **Windows** | `%LOCALAPPDATA%\RestorePrivacy\.rpt_support_log.jsonl` |
| **Linux** | `~/.local/share/restore-privacy/.rpt_support_log.jsonl` |

---

## Privacy in one page

| Document | Link |
|----------|------|
| **Privacy policy** | [PRIVACY_POLICY.md](PRIVACY_POLICY.md) |
| **Licence** | [LICENSE](LICENSE) (proprietary full copyright) |
| **Credits** | [CREDITS.md](CREDITS.md) |
| **Code & policy audit** | [AUDIT.md](AUDIT.md) |

Core promises: **no user-info logs** by design, **minimal public status** (title +
downloads + **preferred-entry clear timer** — **no live client count**), **device keys**,
**honest residual** only when full tunnel is up. Multi-hop residual is **opt-in**
(`RPT_MULTIHOP_ENABLED=1`). **Weekly sequential fleet wipe** (~7d, IS → DE) with
**best-effort** hop; if hop does not succeed, manual reconnection may be required.
Licence is **proprietary full copyright**.

---

## Threat model

Short user-education summary. Full language: **[PRIVACY_POLICY.md — Threat model](PRIVACY_POLICY.md)**.
Auditor detail: **[AUDIT.md §4.6](AUDIT.md)**.

### What it protects against

- Residual public IP uses the VPN node when full tunnel is actually up.
- No user-info logs on the product node path; no public live client count.
- Per-device keys (not a shared installer private key).
- Mitigations for coarse traffic fingerprints (**off by default**).
- Tunnel-only DNS while residual capture is active. Kill-switch is **not** default.
- **PFS** so long-term key compromise later should not reconstruct past session keys
  from the public transcript alone.

### What it does not protect against

- Endpoint correlation, behavioral analysis, VPS provider metadata.
- Traffic analysis beyond mitigations — you still appear to use a VPN.
- Client device seizure, malware, compromised OS, destination-site tracking.

---

## Operators / developers

Node deploy, ports, secrets, from-source builds, and tests: **[sundries.txt](sundries.txt)**.

**Device keys:** packages do **not** ship a shared client private key; each install
generates its own Ed25519 device key on first run.

**Secrets discipline:** Never commit or force-add `secrets/` (gitignored). Paid
release packages must never include `node_elgamal.priv` or a shared
`client_ed25519.priv`.

**Node key protection:** `RPT_KEY_BACKEND=file|mock|sealed|tpm` — see
`node/key_backend.py`.

**Key rotation:** `python scripts/rotate_node_keys.py --secrets-dir …` updates node
long-term material + `product/node_elgamal.pub` pin.

**Post-quantum readiness:** staged hybrid hook in `node/pq_hybrid.py` +
[`docs/PQ_MIGRATION.md`](docs/PQ_MIGRATION.md).

**Product ship (catalog monopin):** Free Suite installers on the VPN APP Shop; KEYGEN from
£3.00/month. Catalog residual peers: **IS** / **DE** (default) — US and Romania
**retired**.

**Self-host (one shot):** `sudo bash scripts/selfhost_node.sh` — node install +
tunnel DNS + host privacy. Deploy remote: `python scripts/deploy_rpt_node.py`.

**Weekly sequential fleet wipe/rebuild:** [node/fleet_wipe.py](node/fleet_wipe.py) +
[scripts/weekly_entry_rebuild.py](scripts/weekly_entry_rebuild.py) — **~7d** timed
wipe, **one peer at a time** (**IS → DE**). Exclusive lock
([node/rebuild_lock.py](node/rebuild_lock.py)) refuses concurrent multi-node wipe.
**Pre-wipe gates** ([node/wipe_preflight.py](node/wipe_preflight.py)): live path
**fail closed** unless alternate residual and target peer health both pass. After
rebuild, **mandatory package reinstall** via selfhost. Clients **best-effort**
failover hop to a healthy alternate while a peer drains. Public homepage
preferred-entry **clear timer** is **entry-only** (**no exit wipe countdown**).
Live requires `RPT_EPHEMERAL_CONFIRM=yes`.

**Private capacity probes:** [docs/CAPACITY_PROBES.md](docs/CAPACITY_PROBES.md).
**No public client counts**.

**Public Pages export (no admin):**

```bash
python3 scripts/build_public_pages.py
# push public_site/ to github.com/rgsneddon/restore-privacy-suite (public open Pages)
# live: https://rgsneddon.github.io/restore-privacy-suite/
```

**Release scripts:**

```bash
python3 scripts/build_suite_1.0.0.py
python3 scripts/package_restore_privacy_suite.py
```

**Node wipe reinstall (sequential fleet):** [docs/NODE_WIPE_REINSTALL.md](docs/NODE_WIPE_REINSTALL.md)
— weekly wipe is **one peer at a time** (IS → DE) with mandatory full selfhost
reinstall; never concurrent multi-node wipe.
