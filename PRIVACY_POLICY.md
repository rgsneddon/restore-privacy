# Privacy Policy  -  Restore Privacy

**Last updated:** 21 July 2026  
**Product:** Restore Privacy Tunnel (RPT / RPT2) — custom VPN node, client apps, and public status page  
**Current packages (catalog v0.3.3):** paid installers (£2.45 GBP per package) via [status downloads](https://restoreprivacy.online/) (Windows · Android · macOS · iOS · Linux — macOS Developer ID notarized; iOS Team-signed sideload). The product **source repository is private**; free permanent public GitHub installer URLs are **not** offered. After payment the status host delivers a **one-time** download (authenticated proxy).  

**STRONG DISCLAIMER — PAYMENT REQUIRED FOR CONNECT:** Access to **Connect** and residual VPN use requires **successful payment**. If payment **fails at any time** (failed checkout, failed charge, refund, dispute, or revoked entitlement), the ability to **Connect with the Restore Privacy app is cancelled** for that purchase/install until a successful payment is completed. Stripe Checkout session id is used as a **payment entitlement** key (not a username/password account); status host stores entitlement outcome for Connect checks.
**Code & policy audit:** [AUDIT.md](AUDIT.md) (also served on the status host as `/AUDIT.md`)  
**Operator / project:** Russell G Sneddon (`rgsneddon`) / Restore Privacy — public docs and paid downloads: [status host](https://restoreprivacy.online/)

This policy describes how the **Restore Privacy** software is designed to handle data. It is written for end users and operators. It is **not** legal advice and is not a jurisdiction-specific compliance certificate (e.g. full GDPR/CCPA legal opinion).

---

## 1. Summary

Restore Privacy is a **custom-built encrypted tunnel** (not WireGuard, OpenVPN, or other pre-existing VPN products). The product goal is:

| Commitment | Meaning |
|------------|---------|
| **No user-info logs** | The node and status software are configured **not** to write connection, session, access, traffic, accounting, or peer-activity logs to disk. |
| **No client PII collection** | The public status surface exposes **product title and paid-download entry** only — **not** a live connected-client count, identities, IPs, usernames, or per-client lists. |
| **Tunnel as a relay** | After cryptographic admission, the node forwards encrypted-session traffic; it is not designed as an analytics or advertising platform. |

---

## 2. What we do **not** collect or retain (by design)

Unless an operator **deliberately** changes configuration or hosting outside this software's defaults, the shipped node and status page are intended **not** to:

- Store **usernames, passwords, email addresses, or account profiles** for tunnel use (tunnel attach uses **cryptographic product keys**, not user accounts).
- Write **connection logs**, **session logs**, **access logs**, **traffic logs**, or **peer activity logs** for tunnel use.
- Publish **client IP addresses**, **device identifiers**, or **session identifiers** on the public status page.
- Keep a **lifetime / cumulative "total clients ever"** counter or a **live connected-client count** on the public page.
- Bundle the **node ElGamal private key** (`node_elgamal.priv`) in public packages (never shipped).

Process stdout/stderr for the node service is configured for **no journal session streams** in the standard install (`StandardOutput=null` / similar).

---

## 3. What processing happens (high level)

### 3.1 VPN node (server)

- Production product endpoint used by current client packages: **UDP 82.221.101.241:44044** (operator-hosted RPT node).
- **Location / host:** the production node is hosted in **Iceland** on **FlokiNET** (also written Flokinet; https://flokinet.is/). Icelandic privacy and free-expression law (including the broader **Icelandic** press/speech protections that privacy-focused hosts cite, such as IMMI-era policy) governs this placement more strictly than many common VPS jurisdictions.
- **Host connection logging (assurance, not a product forensic audit):** as far as we can be assured from FlokiNET’s **public** statements, the host does **not** retain invasive logs of users connecting to the VPS / node and does **not** share tenant traffic or traffic patterns with third parties; FlokiNET states **“No invasive logs”**, root-only customer access, monitoring limited to **overall resource usage**, and no third-party sharing of traffic/patterns (see https://flokinet.is/privacy/ and https://flokinet.is/vps/). This is **host-published posture**, not a Restore Privacy laboratory audit of FlokiNET’s network. Product **application** no-log defaults (below) remain separate.

- Listens for RPT tunnel handshakes and **encrypted** data frames.
- **Admits** only peers that complete the product handshake with an **authorized client key** (Ed25519 allow-list + ElGamal / Pedersen-based handshake materials).
- Assigns a temporary tunnel IP and **relays** IP traffic (forwarding + NAT) while the session is active.
- Holds **in-memory** session state for active tunnels so traffic can be routed (internal only — **not** published as a public live count).
- When a session ends, that in-memory state is dropped; it is **not** designed to be written as a durable user history file.
- Outer **layer obfuscation** (QUIC-mimic wrapper around RPT frames) is enabled by default on the product Python path so clear ``RPT2`` magic is not on the wire alone (mitigation; not a DPI-undetectability claim).

### 3.2 Client applications (Windows, Android, Linux, iOS, and macOS)

- **Product UI** uses **manual Connect / Disconnect** by default. Optional **Settings** preferences (stored only on the device) let the user enable **run at device startup** and/or **autoconnect on launch** (both **off** until opted in). Settings also exposes links to the **most recent audit** (`AUDIT.md`), **privacy policy** (`PRIVACY_POLICY.md`), and **end user licence** (`LICENSE`). These preferences and links are local/device-side only  -  not synced to the node or status page.
- Closing or minimizing the main UI is designed to **leave the tunnel running** until the user **Disconnects** or **Quits** (Windows tray identity: **Privacy Restored**). Android keep-alive uses a foreground VPN service; Activity destroy does not stop the tunnel.
- Clients use **local** cryptographic material (when provisioned) to complete admission and establish session keys when the user connects. On the Python client/node path, session AEAD keys incorporate **ephemeral X25519** material (perfect forward secrecy) in addition to handshake nonces — long-term keys remain for admission/authentication.
- **Traffic-shape** features (packet padding, send-side timing jitter, cover/dummy frames) are **enabled by default** on the product Windows/Linux Python DATA path (bounded pad bucket, modest send jitter, periodic cover frames). Set environment variable **`RPT_TRAFFIC_SHAPE=0`** to disable. They reduce coarse traffic fingerprints and are **not** a guarantee of undetectability against sophisticated DPI. Native Android/Apple engines may lag this wire surface until dual-wired.
- **Full-tunnel** modes route device traffic into the encrypted tunnel **only when** the OS grants VPN permission (Windows Administrator / UAC + Wintun dual `/1` routes, Android VPN consent, iOS/macOS VPN permission). On **iOS and macOS**, full-system VPN uses a signed **Packet Tunnel Network Extension** (and App Group access to admission secrets). Product "connected for residual public IP" requires the system tunnel / dual `/1` path to be active (residual public IP only changes then).
- **On Disconnect / Quit**, clients are designed to **fully tear down** the tunnel (routes, TUN/Packet Tunnel, session, and product residual route state such as Windows dual `/1`) so traffic **reverts to the device's normal public IP path**. This is ordinary session teardown — **not** the same as **Restore Internet** complete product removal (see §3.5).
- **Windows Defender Firewall product rules:** residual Connect may install **scoped allow** rules (**RPT-FW**) for the product program and the product node UDP endpoint only. These are local OS firewall configuration for connectivity — **not** telemetry, analytics, or outbound reporting. On Disconnect / Quit / Restore Internet they are removed with residual restore. Unscoped “block all” kill-switch rules are **not** applied by default.
- Clients are **not** designed to upload browsing history or identity dossiers to the node as product telemetry.
- **No public-IP geo admission (from 0.1.9 source):** product Connect does **not** look up the device public IP via third-party geo services, and does **not** allow or deny access by country. Admission is cryptographic (device Ed25519 + node keys) only. Older installed packages (e.g. 0.1.8) may still perform a client-side UK geo check until users upgrade.
- **DNS on full tunnel:** product full-tunnel clients default DNS to the **node tunnel gateway** (`10.88.0.1`) only — **no** client-side public DNS fallbacks (Cloudflare/Google/Quad9/etc.). The node Unbound instance listens on the tunnel address and uses **DNS-over-TLS (DoT)** upstream to privacy-oriented resolvers (`node/unbound-rpt.conf`, `node/install_dns.sh`). Until node DNS is installed, name resolution while connected may fail. The VPS provider may still see DoT/encrypted recursive upstream traffic from the node.
- **Kill switch / leak protection:** product residual **does not** apply a kill switch by default (no always-on firewall/iptables block of non-tunnel egress; Android does not use `setBlocking(true)`). Optional opt-in: set environment variable **`RPT_KILL_SWITCH=1`** on Windows/Linux. Tunnel DNS remains gateway-only (`10.88.0.1`). Browser WebRTC may still use local interfaces — disable WebRTC in the browser for maximum assurance.
- Paid catalog packages (Windows `.exe`, Android `.apk`, Linux `.tar.gz` installer, macOS `.zip`, iOS `.zip`) may include the **public** node key (`node_elgamal.pub`) so clients can open a HELLO. Each install **generates a unique Ed25519 device private key on first run** and keeps it only in local device-private storage - packages do **not** ship a shared `client_ed25519.priv` (which would allow universal impersonation). They **never** include the **node private key** (`node_elgamal.priv`). Windows installers ship a **bundled runtime** (no separate system Python install). The Linux installer package ships **manylinux wheels** for the app Python crypto stack (private venv via `install.sh`); OS tools such as TUN/`ip`/root for full tunnel remain host-provided.

### 3.3 Public status page (e.g. Render)

- Displays the product **title**, beta note, and **paid download** entry (Stripe Payment Link per platform) only. The downloads platform line is **platform names only** (Windows | Linux | macOS | iOS | Android) — not a live client metric.
- **Payment entitlement:** after successful paid Checkout the status host records an **active** Connect entitlement for that Stripe session; webhook-observed **payment failures / refunds / disputes** set the entitlement to **failed/revoked** so Connect is blocked for that purchase. Clients may query `/api/connect-entitlement` with the session id (no password account).
- Does **not** expose a live connected-client count or poll a session metric on the public HTML surface.
- Optional `/api/status` JSON is **title-only** (no `clients_connected`).
- **Does not** publish free permanent GitHub `releases/download` installer buttons. Catalog **v0.3.3** packages are fulfilled **after payment** on [status downloads](https://restoreprivacy.online/) via a **one-time** proxy download (private source repository).
- Serves same-origin legal documents (`/PRIVACY_POLICY.md`, `/LICENSE`, `/README.md`, `/CREDITS.md`, `/AUDIT.md`) so clients can open docs without a public GitHub tree. The security audit includes a **per-installer AUDIT STATE** (Green / Amber / Red) for catalog packages.

### 3.4 Operator-held secrets

- **Node ElGamal private key** and **authorized client private keys** are operational secrets.
- The **node ElGamal private key** lives only on the operator node (e.g. `/opt/restore-privacy/secrets/`) and is gitignored - **never** in paid release packages.
- **Client** device Ed25519 keys are created locally on first run (not a shared installer secret). Possession of a device key allows tunnel use for that install - treat local secrets as credentials.

### 3.5 Restore Internet failsafe (complete product removal)

Every catalog installer ships a user-facing **Restore Internet** artifact (Windows/Linux runnable script; macOS `.command`; iOS/Android guidance text).

| Intent | Behaviour |
|--------|-----------|
| **Network restore** | Best-effort residual route / kill-switch / firewall cleanup so ordinary internet works again. |
| **Complete removal** | Deletes the product app tree (including portable Windows extract trees), shortcuts, and local product secrets (e.g. `~/.restore-privacy` / device-local keys). |

This processing is **entirely on the user’s device**. It does **not** phone home, upload identity, or notify the node/status host that a wipe occurred.

**BIG WARNING (user-facing):** Running **Restore Internet** **ERASES ALL** parts of Restore Privacy from the device. Paid catalog downloads use **one-time** fulfilment links. After a full wipe you may **not** be able to automatically re-download your subscription app. Contact **russell.gray.sneddon@gmail.com** to obtain a new download link (or pay again on the [status downloads](https://restoreprivacy.online/) page). Ordinary **Disconnect** does **not** perform this full wipe.

---

## 4. Limits of this privacy promise

Please understand these **operational limits**:

1. **Hosting and networks.** The production RPT node runs on **FlokiNET** in **Iceland** under **strict Icelandic privacy** / free-expression-oriented hosting norms. **As far as we can be assured** from FlokiNET’s public materials, the host does **not** retain invasive connection logs of users connecting to the node and does not share tenant traffic/patterns with third parties (**“No invasive logs”**; resource-usage monitoring only — https://flokinet.is/privacy/, https://flokinet.is/vps/). That assurance is **not** a third-party no-logs audit and does **not** erase risk if the **node OS itself** is compromised (live memory). A separate **CDN**, status host, or DNS operator (or another **VPS provider** if you self-host elsewhere) may still log IP-level connection metadata under **their** policies (**outside this application's no-log** settings).
2. **Destination sites.** Websites and services you visit through the tunnel have their own privacy policies.
3. **Device and OS.** Android VPN consent dialogs, Windows admin elevation, iOS/macOS VPN permission sheets, Apple Network Extension processes, crash reporters, or OS network stacks may process data independently of this app.
4. **Misconfiguration.** If an operator enables verbose logging, reverse proxies with access logs, or third-party monitoring, that can create logs this policy assumes are off.
5. **Security vs. privacy.** Per-device Ed25519 keys identify a **product install**, not a named human account - but a device key can still be treated as an access secret for that install.
6. **Open relay risk is reduced by keys, not by accounts.** Unauthorized clients should fail handshake; authorized keys must be protected.
7. **Traffic analysis mitigations are incomplete.** Product Windows/Linux clients apply packet padding, timing jitter, and cover traffic **by default** (opt out with `RPT_TRAFFIC_SHAPE=0`). They reduce coarse size/timing fingerprints; they do **not** guarantee undetectability against sophisticated DPI. Multi-hop hop *lists* may be configured for future use; product traffic remains **single-hop / entry-only** until a real multi-hop relay path ships (status never claims multi-hop residual from config alone). Session AEAD keys use ephemeral X25519 material (PFS) so long-term key compromise after a session ends should not reconstruct that session’s traffic keys from the public transcript alone.
8. **Self-hosted operators** must still protect long-term node keys (prefer `RPT_KEY_BACKEND=sealed` / TPM-class wrap so plaintext `node_elgamal.priv` is not free on disk), keep product no-log defaults, and remember provider-level IP logs (limit 1 above). Session AEAD uses ephemeral X25519 (PFS) on the product path; long-term key rotation updates public pins only for clients. Post-quantum hybrid (Kyber/ML-KEM class) is staged readiness — not residual PQ on the wire until dual-wire + real ML-KEM ships (`docs/PQ_MIGRATION.md`).

---

## 5. Threat model

This section is for **user education**. It states **what Restore Privacy protects against** and **what it does not**, in plain language. A longer scenario write-up (VPS compromise, ISP traffic analysis, client device seizure) lives in [AUDIT.md §4.6](AUDIT.md). This is **not** a formal certification or pen-test report.

### 5.1 What it protects against

| Goal | Product stance when residual full tunnel is actually up |
|------|--------------------------------------------------------|
| **Casual observation of destination sites on the home ISP path** | Device traffic is intended to exit via the VPN node, so destination sites and the home ISP path see the **node’s residual public IP**, not your home IP (Windows dual `/1` + Wintun, Android VPN service, signed Apple Packet Tunnel). |
| **Product node writing user browsing history** | Shipped no-log defaults: no connection / session / traffic / user-info logs for tunnel use. |
| **Public “who is online” metrics** | Status page and node public API are **title (+ downloads) only** — no live client count, no per-client lists, no identifying session fields. |
| **Shared installer impersonation** | Each install generates its **own** device Ed25519 key; packages do not ship a universal `client_ed25519.priv`. |
| **Coarse wire fingerprints** | Outer obfuscation and traffic shaping (padding / jitter / cover) are **on by default** on the product residual DATA path as **mitigations** (not undetectability). |
| **Casual DNS leaks while residual is up** | Tunnel-only DNS (`10.88.0.1`) is the product residual plan (no public DNS fallbacks). Kill-switch firewall blocks of non-tunnel egress are **not** applied by default (opt-in `RPT_KILL_SWITCH=1` only). Residual routes may still fail open to the ISP path without that opt-in. |
| **Past-session key recovery from long-term keys alone** | Session AEAD incorporates **ephemeral X25519 (PFS)** on the product path so long-term key compromise later should not reconstruct that session’s traffic keys from the public transcript alone. |

### 5.2 What it does **not** protect against

| Non-goal | Why |
|----------|-----|
| **Endpoint correlation** | A service you visit can still recognize *you* via accounts, cookies, browser fingerprint, or the same login across sessions. The tunnel does **not** unlink your identity at the destination. Destinations may also correlate multiple sessions that share the **same VPN egress IP** (many users behind one node). |
| **Behavioral analysis** | Observers (ISP, workplace, or analyst with flow logs) can still study **when** you connect, **how long**, and rough volume patterns. Pad/cover/obfs reduce coarse fingerprints; they do **not** stop behavioral analysis of usage patterns. |
| **VPS / provider metadata** | Product node is on **FlokiNET** in **Iceland**. As far as we can be assured from host public statements, FlokiNET does **not** retain invasive logs of users connecting to the node (see §3.1 / §4 item 1). Other networks (home ISP path before Connect, CDN/status hosts, destination sites) may still log under their policies. Product no-log does not erase **non-FlokiNET** provider logs. |
| **VPS compromise (active sessions)** | If the **node OS / root** is fully compromised while you are connected, **live** memory may still expose session material — distinct from FlokiNET’s published “no invasive logs” / no tenant traffic sharing stance. See [AUDIT.md](AUDIT.md) **VPS compromise** scenario. |
| **Traffic analysis by ISP (undetectability)** | Your ISP can still see that you talk to the VPN node. We do **not** claim DPI-undetectability or full pluggable-transport parity. |
| **Client device seizure** | Seizure of an unlocked (or decryptable) device exposes local keys, apps, browser history, and any local connection log. Disk encryption is an OS control, not an RPT server feature. |
| **Multi-hop residual routing** | Hop *lists* may exist for planning; product traffic remains **single-hop / entry-only** until a real multi-hop path ships. |
| **Malware or compromised endpoints** | A keylogger, malicious browser extension, or rooted device is outside the tunnel’s trust boundary. |

### 5.3 Scenario map (summary)

| Scenario | Protects / mitigates | Does not eliminate |
|----------|----------------------|--------------------|
| **VPS compromise** | No durable user-info logs; PFS for past sessions; no public client metrics | Live memory, provider IP logs, future key abuse until rotation |
| **Traffic analysis by ISP** | Residual egress via node; pad/obfs mitigations | Visibility of VPN use; DPI-class fingerprinting; behavioral timing |
| **Client device seizure** | No server-side history upload by design | Local forensics, device key, other apps |

---

## 6. Cookies and tracking

The status page is a minimal static UI. It does **not** use advertising trackers or analytics SDKs in the shipped code. It does **not** poll a live client count. No account login cookies are required for the tunnel protocol itself.

---

## 7. Children

This software is a network tool for general audiences. It is not directed at children under 13 (or the minimum age in your jurisdiction). Do not provide personal data of children through misconfigured logging or external services.

---

## 8. Changes

We may update this policy as the product evolves. The **Last updated** date at the top will change when material edits are made. Continued use of updated software implies review of the current policy in the repository.

---

## 9. Contact

The product **source repository is private**. For privacy questions about Restore Privacy:

- Read the public policy and audit on the [status host](https://restoreprivacy.online/) (`/PRIVACY_POLICY.md`, `/AUDIT.md`)
- Install / pay path: [How to buy](https://restoreprivacy.online/how-to-buy)
- **Re-download after full wipe (Restore Internet):** **russell.gray.sneddon@gmail.com**
- Or contact the operator via their public project channels (e.g. GitHub profile `rgsneddon`)

---

## 10. Related documents

- Project license and third-party credits: [`LICENSE`](LICENSE), [`CREDITS.md`](CREDITS.md) (also on the status host)
- How to install and run (including **Restore Internet** warning): [`README.md`](README.md)
- Code & policy audit (including per-installer AUDIT STATE): [`AUDIT.md`](AUDIT.md)
