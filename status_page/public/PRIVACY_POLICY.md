# Privacy Policy — Restore Privacy

**Last updated:** 14 August 2026  
**Product:** Restore Privacy — a dedicated residual virtual private network and the public shop  
**Current packages:** free installers on [restoreprivacy.online](https://restoreprivacy.online/). The public **Downloads Map** (`/downloads-map` and `/downloads-map.json`) is the source of truth for which installer version each platform gets. Residual Connect needs a free device trial or a **KEYGEN** from `/pay` (monthly residual licence from **£3.00 GBP**; yearly residual plan **£30.00** remains available). **macOS** is **Developer ID** + notarized when sealed (Team **SFCBP95595**). **iOS** ships as an IPA-compatible Team-signed zip (`Payload/Runner.app` + embedded provisions; rename to `.ipa` for sideload; same Team **SFCBP95595**). Public GitHub Pages ship docs only — not operator admin.

---

## What this product is

Restore Privacy is a **dedicated virtual private network** for residual traffic on your device.

| Surface | Role |
|---------|------|
| **Residual Connect** | Encrypted residual tunnel; free 3-day (72h) device trial (no card), then paid KEYGEN after trial |
| **Settings / licence** | End-user licence acceptance, KEYGEN unlock, residual privacy toggles |

First use: accept the end-user licence → paste KEYGEN **or** continue the free trial → main VPN. There is **no** username/password account gate and **no** seed phrase gate on the product path.

---

## Licence acceptance (your agreement)

Before residual Connect, you **accept the end-user licence** on this device (local flag only). Acceptance is stored **on-device** — we do not auto-upload the licence text or acceptance prose to residual nodes or the CERBERUS/Helsinki oracle. Residual Connect includes a free **3-day (72-hour)** trial (no card). After the trial ends, enter a **KEYGEN** from your fulfilment email (or buy one at [restoreprivacy.online/pay](https://restoreprivacy.online/pay)). **STRONG DISCLAIMER — PAYMENT REQUIRED AFTER TRIAL:** if payment fails at any time after purchase, Connect is cancelled until successful payment is completed.

---

## What we collect and process

### Residual Connect (VPN)

- Cryptographic HELLO/session material between your client and residual nodes.
- Payment entitlement checks (session id + device public key bind) so Connect can confirm an **active** KEYGEN on this device.
- **No user-info connection logs** are uploaded by the client. Export of a local connection log is **user-initiated** only (save/clipboard/email by you).

### Downloads Map and device platform

- The homepage **FREE DOWNLOAD** button and `/downloads-map` read your browser **User-Agent** only to guess OS (Windows, macOS, iOS, Android, Linux). That string is used for the current request so we can highlight and start the matching installer. We do not store User-Agent as an account profile.
- You get the **latest installer for that OS that is listed on the Downloads Map** (fulfilled from the Helsinki package store). Platforms can be on different versions (for example Windows 1.2.7 while Android is still 1.2.6) until that platform is rebuilt and the map is updated.
- **Platform requirements we check against:** Windows 10 or later, 64-bit (x64) for the `.exe` installer; Android 8+ for the APK; macOS 12+ x86_64/arm64 for the notarized zip; iOS 15+ for the Team-signed sideload zip (rename to `.ipa`); Linux x86_64 for the `.tar.gz`. We do not collect hardware inventories. If your device does not match, the installer may refuse to run — we do not silently give you another OS package.
- The same map is published at `/downloads-map.json` (version + filename per platform, no personal data).

### Payment / shop host

- Checkout and KEYGEN fulfilment go through the public shop (`restoreprivacy.online`, including `/pay`). Payment processors process card data under their terms; we receive entitlement status and fulfilment codes needed to unlock Connect.
- **KEYGEN-free device trial:** residual Connect includes a **72-hour (3-day) free trial** in the app without email or card. You do not need payment details before the trial. After the trial expires, residual Connect requires a **paid KEYGEN / active subscription** (subscription checkout bills immediately — no Stripe trial period). The status host records only your device’s Ed25519 **public** admission key, an optional install marker, and trial timestamps (no connection logs).

### What we do **not** do

- No third-party advertising or analytics SDKs in the client monopin.
- No automatic upload of connection logs or licence-acceptance dumps to residual nodes or the oracle.
- No public live “clients connected” count on node status pages (title-only public status).

---

## Settings defaults (lean residual)

Run at startup **off**, autoconnect **off**, residual VPN core available after KEYGEN unlock (or during free trial), residual **IPv4** on, residual **IPv6** toggleable, traffic shaping / outer obfuscation / multi-hop **off** by default (opt-in).

Force-on for operators/tests (not opt-out of defaults): set **`RPT_TRAFFIC_SHAPE=1`** and/or **`RPT_OBFS=1`** (or use in-app Settings) to enable traffic shaping / outer obfuscation when you want them. Defaults stay **off** so residual paths stay lean.

### Operational limits

- Residual Connect is limited to devices with an **active free residual trial** or a valid **KEYGEN** entitlement (monthly or yearly residual licence) after the trial.
- Free installers are fulfilled on the product host; residual unlock remains KEYGEN-bound and **time-limited** to the active subscription / trial period (not an unlimited free residual CDN).
- Public node status stays **title-only** (no live client count).

---

## rpAI (Ned) — honest description

rpAI is **not** a chatbot in the residual Windows/macOS/Linux/Android/iOS VPN app, and it does **not** read your tunnel traffic.

| What people hear | What is actually shipped |
|------------------|--------------------------|
| “An AI that uses my VPN data” | Residual clients are **VPN-only**. There is no Ned/rpAI tab, prompt box, or cloud-model call on the residual Connect path. |
| “Ned learns about me” | On residual **nodes**, a co-located helper thread (`rpAI · Ned`) ticks local counters (learning epochs, ChronoFlux growth, node heartbeats). Those are operator/product stats, not packet contents and not browsing history. |
| “My chats go to OpenAI / Anthropic / xAI” | They do not. Residual Connect does not send prompts or page contents to third-party AI APIs. |
| “Ned is a real assistant” | The historical Suite Flutter surface is a **scripted** helper (install/how-to narrative, like a privacy-first Clippy). It is **retired from residual client chrome**. It does not train a model on you. |
| “What can Ned learn from the shop?” | Ned may absorb the public **Downloads Map** (which installer version each OS is on). That file has no names, emails, IPs, or User-Agents. |

Private node hook `/api/private/rpai` is operator/token gated. Public `/api/ned-growth` exposes only non-personal growth counters plus the Downloads Map when present.

---

## Your rights and contact

You can export local connection logs and stop using residual Connect by not renewing KEYGEN. For privacy questions: **rus@restoreprivacy.online**.

Related: end-user **LICENSE**, product **README**, and the public security **AUDIT**.

This policy describes product behaviour for the current Downloads Map. It is not a substitute for formal legal advice.
