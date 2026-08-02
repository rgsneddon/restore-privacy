# Privacy Policy — Restore Privacy Suite

**Last updated:** 2 August 2026  
**Product:** Restore Privacy Suite **v1.0.8** — residual Connect, Perccent wallet (%), Evolve analyser, rpAI (Ned), Backup recovery, and the public VPN APP Shop  
**Current packages (catalog v1.0.8):** free Suite installers on [restoreprivacy.online](https://restoreprivacy.online/) (VPN APP Shop). Residual Connect needs a **KEYGEN** from `/pay` (monthly residual licence from **£3.00 GBP**; yearly residual plan **£30.00** remains available). **Linux**, **Android**, **macOS**, **iOS**, and **Windows** monopin **1.0.8** packages are fulfilled from the product host. **macOS** is **Developer ID** + notarized (Team **SFCBP95595**). **iOS** ships as an **Apple Distribution** Team-signed **Runner.app** zip for sideload (same Team); a full App Store–style IPA export still needs `ExportOptions.plist` and is a separate path. Public GitHub Pages ship docs only — not operator admin.

---

## What this product is

Restore Privacy Suite is one app shell with several surfaces:

| Surface | Role |
|---------|------|
| **VPN (residual Connect)** | Encrypted residual tunnel to product nodes; unlock requires KEYGEN after licence acceptance |
| **Wallet (%)** | Perccent private wallet (local ledger; optional encrypted backup / seed) |
| **Evolve** | Chronoflux analysis + parish voting when entitled |
| **Backup** | Encrypted export/import and optional 12-word seed recovery for wallet/analyser identity |
| **rpAI (Ned)** | Local helper / growth surface; fleet oracle learns **operational** Suite map parameters only |
| **Settings / licence** | End-user licence acceptance, KEYGEN unlock, residual toggles |

---

## First-run account and seed (on-device)

Before residual VPN permissions, you create a **Suite account** (username/password) and a **12-word recovery seed** kept only on your device, then accept the licence. Account credentials auto-enable % and Evolve. Seed phrases are not uploaded to residual nodes.

## Licence acceptance (your agreement)

Before residual Connect unlocks, you **accept the end-user licence** on this device (local flag only). Acceptance is stored **on-device** — we do not auto-upload the licence text or acceptance prose to residual nodes or the CERBERUS/Helsinki oracle. After acceptance, enter the **KEYGEN** from your fulfilment email (or buy one at [restoreprivacy.online/pay](https://restoreprivacy.online/pay)). Download alone does not unlock residual VPN.

---

## What we collect and process

### Residual Connect (VPN)

- Cryptographic HELLO/session material between your client and residual nodes.
- Payment entitlement checks (session id + device public key bind) so Connect can confirm an **active** KEYGEN on this device.
- **No user-info connection logs** are uploaded by the client. Export of a local connection log is **user-initiated** only (save/clipboard/email by you).

### Free Suite surfaces (wallet, Evolve, Backup, Ned)

- Wallet and Evolve ledgers live **locally** (and on optional user-chosen backup files / seed envelopes you control).
- Encrypted backup files and seed recovery envelopes are **not** sent as plaintext secrets to the residual oracle. Optional seed rendezvous (when configured) carries **encrypted** envelope material only — never the raw 12-word phrase as a plaintext field.
- Ned/oracle collates fleet **operational** signals (capacity, co-join readiness, Suite surface counters without PII). Forbidden user-secret keys are stripped and **not durably stored** by the oracle path.

### Payment / shop host

- Checkout and KEYGEN fulfilment go through the public shop (`restoreprivacy.online`, including `/pay`). Payment processors process card data under their terms; we receive entitlement status and fulfilment codes needed to unlock Connect.
- **KEYGEN-free device trial (optional):** on first use you may start a **72-hour residual trial** without email or card. The status host records only your device’s existing Ed25519 **public** admission key and trial timestamps (no connection logs). After expiry, residual Connect requires a paid KEYGEN. Reinstall that keeps the same device key does **not** grant a second full trial window.

### What we do **not** do

- No third-party advertising or analytics SDKs in the Suite client monopin.
- No automatic upload of connection logs, seed phrases, backup passphrases, or licence-acceptance dumps to residual nodes or the oracle.
- No public live “clients connected” count on node status pages (title-only public status).

---

## Settings defaults (lean residual)

Run at startup **off**, autoconnect **off**, residual VPN core available after KEYGEN unlock, residual **IPv4** on, residual **IPv6** toggleable, traffic shaping / outer obfuscation / multi-hop **off** by default (opt-in). Optional browser extension is browser-scoped only.

Force-on for operators/tests (not opt-out of defaults): set **`RPT_TRAFFIC_SHAPE=1`** and/or **`RPT_OBFS=1`** (or use in-app Settings) to enable traffic shaping / outer obfuscation when you want them. Defaults stay **off** so residual paths stay lean.

### Operational limits

- Residual Connect is limited to devices with a valid **KEYGEN** entitlement (monthly or yearly residual licence).
- Free Suite installers are fulfilled on the product host; residual unlock remains KEYGEN-bound and **time-limited** to the active subscription / trial period (not an unlimited free residual CDN).
- Public node status stays **title-only** (no live client count).

---

## Your rights and contact

You can export local connection logs, delete local wallet data, and stop using residual Connect by not renewing KEYGEN. For privacy questions: **rus@restoreprivacy.online**.

Related: end-user **LICENSE**, product **README**, and the public security **AUDIT**.

This policy describes product behaviour for catalog **v1.0.8**. It is not a substitute for formal legal advice.
