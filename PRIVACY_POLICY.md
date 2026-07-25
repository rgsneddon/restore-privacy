# Privacy Policy — Restore Privacy

**Last updated:** 25 July 2026  
**Product:** Restore Privacy Tunnel (RPT / RPT2) — VPN node, client apps, and public status shop  
**Current packages (catalog v0.4.5):** paid installers on [restoreprivacy.online](https://restoreprivacy.online/) — Monthly **£2.45 GBP** or Yearly **£27.93** (5% off) per platform (Windows, Android, macOS, iOS, Linux — macOS **Developer ID** notarized; iOS **Team-signed** sideload). Source repository is **private**; free permanent GitHub installer URLs are not offered. After payment you get a **one-time** download and email with **keygen** + **PPI**. Pre-adjustment Settings defaults (lean residual): run at startup **off**, autoconnect **off**, residual VPN core **always on**, traffic shaping / outer obfuscation / multi-hop **off**. Optional browser extension (Chromium MV3, `restore-privacy-browser-extension-0.4.5.zip`) is browser-scoped only — not OS residual TUN.

**Payment and Connect:** residual Connect needs a **successful payment** and **keygen unlock** while the subscription is **OK**. If payment fails, is refunded/disputed, or the paid period ends, status is **EXPIRED**: the app **hard-locks** with **renew your licence *here*** and a **platform payment portal** link until you renew and re-enter a valid keygen. Stripe session id / keygen are entitlement keys, not a username/password account. The status host also binds Stripe **`payment_intent`** so refunds without session metadata still revoke Connect.

**Related:** [AUDIT.md](AUDIT.md) · Operator: **Raskul** · Docs and downloads: [status host](https://restoreprivacy.online/)

This policy describes how the software is **designed** to handle data. It is not legal advice and not a jurisdiction-specific compliance certificate.

---

## 1. Summary

Restore Privacy is a **custom encrypted tunnel**. Product goals:

| Commitment | Meaning |
|------------|---------|
| **No user-info logs** | Node and status software are configured **not** to write connection, session, access, traffic, **accounting**, or peer-activity logs to disk. |
| **No client PII on the public shop** | Public status shows **title and paid-download entry** — not a live client count, identities, IPs, or per-client lists. |
| **Tunnel as a relay** | After admission, the node forwards encrypted-session traffic; it is not an analytics or advertising platform. |

---

## 2. What we do not collect or retain (by design)

Unless an operator deliberately changes hosting outside these defaults, the shipped node and shop are intended **not** to:

- Store usernames, passwords, emails, or account profiles for tunnel use (admission uses **product keys**, not user accounts).
- Write connection, session, access, traffic, **accounting**, or peer activity logs for tunnel use.
- Publish client IPs, device ids, or session ids on the public shop.
- Keep a lifetime “total clients ever” counter or a live connected-client count.
- Bundle the **node ElGamal private key** (`node_elgamal.priv`) in public packages.

Node process stdout/stderr is configured for no journal session streams in the standard install.

---

## 3. What processing happens

### 3.1 VPN node

- **Optional at-rest encryption (operator):** LUKS2 data volumes (`node/install_disk_encryption.sh`) and optional zram+LUKS2 RAM volume (`node/install_zram_luks.sh`) are **node-only**. They protect locked volumes. They are **not** live secrecy against root on an unlocked host, **not** residual tunnel crypto, and they do not erase VPS provider snapshots/netflow.
- **Endpoints (catalog peers):** Iceland **82.221.101.241:44044** (default entry, FlokiNET), Romania **185.146.232.107:44044** (FlokiNET), Germany **167.233.224.5:44044** — user-selectable entry; multi-hop exit is another peer.
- **Location / host:** IS/RO on **FlokiNET** (https://flokinet.is/); DE is a separate residual peer. FlokiNET public materials state **no invasive logs**, root-only customer access, monitoring limited to resource usage, and no third-party sharing of tenant traffic patterns (https://flokinet.is/privacy/, https://flokinet.is/vps/). That is **host-published posture**, not a Restore Privacy forensic audit. Product no-log defaults (below) are separate.
- Listens for handshakes and encrypted data frames; **admits** only peers that complete the product handshake with an authorized client key (**Ed25519 allow-list** + **ElGamal / Pedersen** handshake materials).
- Assigns a temporary tunnel IP and relays traffic while the session is active; holds **in-memory** session state only.
- When a session ends, that memory is dropped — not designed as durable user history.
- Outer **layer obfuscation** (**QUIC-mimic** wrapper around RPT frames) is **off** by default; when enabled in Settings (or `RPT_OBFS=1`) it reduces clear `RPT2` magic on the wire (mitigation, not DPI-undetectability).

### 3.2 Client applications

- Default UI is **manual Connect / Disconnect**. Optional local Settings: run at startup, autoconnect (both off until you opt in). Settings links to audit, privacy policy, and licence (device-side only).
- Closing or minimizing the UI leaves the tunnel up until Disconnect or Quit.
- Session AEAD uses **ephemeral X25519** (PFS) in addition to handshake materials.
- Traffic shaping and outer obfuscation (**QUIC-mimic**) are **off** by default. When on: pad bucket 128, jitter ≤40ms, cover ~2s (product residual paths). Force on Python with `RPT_TRAFFIC_SHAPE=1` / `RPT_OBFS=1`.
- Full tunnel only when the OS grants VPN permission. On iOS/macOS that is a signed Packet Tunnel. Residual public IP changes only when that path is active.
- On Disconnect/Quit, residual routes and product firewall state are torn down so normal internet works again. That is **not** the full **Restore Internet** wipe (§3.5).
- Windows may install **scoped allow** firewall rules (RPT-FW) for the program and node UDP — local connectivity only, not telemetry. Unscoped “block all” kill-switch rules are **not** applied by default.
- Clients are not designed to upload browsing history or identity dossiers as product telemetry.
- **Optional on-device support log (user-controlled):** desktop clients may keep a **local** connect/session diagnostic log (app version, platform, connect outcome / error text) in a **hidden** file only on the device — Windows `%LOCALAPPDATA%\RestorePrivacy\.rpt_support_log.jsonl`, Linux `~/.local/share/restore-privacy/.rpt_support_log.jsonl`. The client does **not** upload this file. Support receives it only if **you** export or copy it and **email** it yourself (Settings → Export log).
- Connect does **not** use third-party geo services to allow/deny access by country. Admission is cryptographic (device Ed25519 + node keys) only. Older packages (e.g. 0.1.8) may still perform a client-side UK geo check until upgraded.
- Full tunnel DNS defaults to node gateway **`10.88.0.1` only** — **no** client-side public DNS fallbacks (Cloudflare / Google / Quad9 / etc.). Node Unbound uses DoT upstream when installed (`node/unbound-rpt.conf`, `node/install_dns.sh`). Until node DNS is installed, name resolution while connected may fail.
- Kill-switch is **off** by default: no always-on firewall/iptables block of non-tunnel egress; Android does **not** use `setBlocking(true)`. Opt in on Windows/Linux with `RPT_KILL_SWITCH=1`. Browser WebRTC can still use local interfaces — disable it in the browser if you need that extra care.
- Paid packages may include the **public** node key (`node_elgamal.pub`). Each install **generates its own device Ed25519 key** on first run. Packages never include `node_elgamal.priv` or a shared `client_ed25519.priv`.

### 3.3 Public status shop

- Shows product title and paid download entry. Platform line is names only — not a live metric.
- After paid Checkout: active Connect entitlement (binds Stripe **`payment_intent`** so refunds without session metadata still revoke), **keygen** mint, email with keygen + PPI + download. Licence accept + keygen required for Connect (**OK**). Failures/refunds/disputes/period end → **EXPIRED**: apps hard-lock with **renew your licence *here*** and a platform payment portal link. Clients re-check `/api/connect-entitlement` on Connect.
- Optional `/api/status` JSON is **title-only** (no `clients_connected`).
- Does not publish free permanent GitHub installer buttons. Catalog v0.4.5 is fulfilled after payment via one-time proxy.
- Serves same-origin legal docs (`/PRIVACY_POLICY.md`, `/LICENSE`, `/README.md`, `/CREDITS.md`, `/AUDIT.md`).

### 3.4 Operator secrets

Node ElGamal private key and authorized materials live only on operator infrastructure (gitignored). Device keys are local credentials for that install.

### 3.5 Restore Internet (complete removal)

Every installer ships a **Restore Internet** failsafe (script or guidance).

| Intent | Behaviour |
|--------|-----------|
| Network restore | Best-effort residual route / firewall cleanup |
| Complete removal | Deletes app tree, shortcuts, local product secrets |

Runs **only on the device** — no phone-home wipe notification.

**Warning:** Restore Internet **erases all** Restore Privacy material. One-time download links will not reappear automatically. Contact **rus@restoreprivacy.online** or pay again. Ordinary Disconnect is not this wipe.

---

## 4. Limits of this privacy promise

1. **Hosting and networks.** Catalog peers: FlokiNET (IS/RO) and the DE residual host. Host public “no invasive logs” stance is not a third-party forensic audit. CDN/status/DNS operators and other networks may log under their policies. Node OS compromise can still expose live memory.
2. **Destination sites** have their own policies.
3. **Device and OS** (VPN dialogs, crash reporters, network stacks) process data outside this app.
4. **Misconfiguration** (verbose logs, reverse-proxy access logs) can create logs this policy assumes are off.
5. **Device keys** identify an install, not a named human account — still treat them as secrets.
6. **Traffic analysis mitigations are incomplete.** Pad/cover/obfs (**QUIC-mimic** when on) reduce coarse fingerprints; they do not guarantee undetectability. Multi-hop residual is opt-in (`RPT_MULTIHOP_ENABLED=1`); default is single-hop on the chosen entry (Iceland default).
7. **Self-hosters** must protect long-term keys and remember provider-level IP logs. PQ hybrid is staged readiness only (`docs/PQ_MIGRATION.md`).
8. **LUKS / zram volumes** protect locked disks/RAM only — not live secrecy against root on an unlocked host.

---

## 5. Threat model

For education — not a pen-test report. Scenario detail: [AUDIT.md §4.6](AUDIT.md).

### 5.1 What it protects against (when residual full tunnel is up)

| Goal | Stance |
|------|--------|
| Home ISP path seeing destination residual IP | Traffic exits via the node when full tunnel is active |
| Product node writing browsing history | No-log defaults for tunnel use |
| Public “who is online” | Title (+ downloads) only |
| Shared installer impersonation | Per-device Ed25519 keys |
| Coarse wire fingerprints | Optional obfs/shape (off by default) |
| Casual DNS leaks while residual is up | Tunnel-only DNS (`10.88.0.1`, no Cloudflare/Google/Quad9 fallbacks); kill-switch off by default (`RPT_KILL_SWITCH=1` opt-in) |
| Past-session key recovery from long-term keys alone | Session PFS (ephemeral X25519) |

### 5.2 What it does not protect against

| Non-goal | Why |
|----------|-----|
| Endpoint correlation | Logins, cookies, fingerprints, shared egress IP |
| Behavioral analysis | Connect timing and volume patterns |
| All provider metadata | Non-FlokiNET paths and OS compromise of the guest |
| ISP “VPN undetectable” | You still talk to a VPN node |
| Client device seizure | Local keys and history on disk |
| Malware / compromised OS | Outside the tunnel trust boundary |

### 5.3 Scenario map

| Scenario | Helps | Does not eliminate |
|----------|-------|--------------------|
| VPS compromise | No durable user-info logs; PFS for past sessions | Live memory; future key abuse until rotation |
| ISP traffic analysis | Residual via node; pad/obfs | Visibility of VPN use; DPI-class analysis |
| Device seizure | No server-side history upload by design | Local forensics |

---

## 6. Cookies and tracking

The status shop is a minimal UI. Shipped code does not use advertising trackers or analytics SDKs, and does not poll a live client count. No account login cookies are required for the tunnel protocol.

---

## 7. Children

This is a general-purpose network tool, not directed at children under 13 (or the minimum age where you live). Do not route children’s personal data through misconfigured logging or external services.

---

## 8. Changes

We may update this policy as the product evolves. The **Last updated** date changes when material edits land. Review the current policy on the status host when you update software.

---

## 9. Contact

- Public policy and audit: [status host](https://restoreprivacy.online/) (`/PRIVACY_POLICY.md`, `/AUDIT.md`)
- How to buy: [how-to-buy](https://restoreprivacy.online/how-to-buy)
- Re-download after Restore Internet wipe: **rus@restoreprivacy.online**
- Or the operator’s public project channels (Raskul / restoreprivacy.online)

---

## 10. Related documents

- [LICENSE](LICENSE), [CREDITS.md](CREDITS.md)
- Install and use: [README.md](README.md)
- Security audit: [AUDIT.md](AUDIT.md)
