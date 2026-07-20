# Privacy Policy  -  Restore Privacy

**Last updated:** 20 July 2026  
**Product:** Restore Privacy Tunnel (RPT) — custom VPN node, client apps, and public status page  
**Current public packages:** [v0.2.2](https://github.com/rgsneddon/restore-privacy/releases/tag/0.2.2) (Windows | Android | Linux; macOS | iOS prep packages)  
**Code & policy audit:** [audit.md](audit.md)  
**Operator / project:** Russell G Sneddon (`rgsneddon`) / public repository [restore-privacy](https://github.com/rgsneddon/restore-privacy)

This policy describes how the **Restore Privacy** software is designed to handle data. It is written for end users and operators. It is **not** legal advice and is not a jurisdiction-specific compliance certificate (e.g. full GDPR/CCPA legal opinion).

---

## 1. Summary

Restore Privacy is a **custom-built encrypted tunnel** (not WireGuard, OpenVPN, or other pre-existing VPN products). The product goal is:

| Commitment | Meaning |
|------------|---------|
| **No user-info logs** | The node and status software are configured **not** to write connection, session, access, traffic, accounting, or peer-activity logs to disk. |
| **No client PII collection** | The public status surface exposes **product title and download links** only — **not** a live connected-client count, identities, IPs, usernames, or per-client lists. |
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

- Listens for RPT tunnel handshakes and **encrypted** data frames.
- **Admits** only peers that complete the product handshake with an **authorized client key** (Ed25519 allow-list + ElGamal / Pedersen-based handshake materials).
- Assigns a temporary tunnel IP and **relays** IP traffic (forwarding + NAT) while the session is active.
- Holds **in-memory** session state for active tunnels so traffic can be routed (internal only — **not** published as a public live count).
- When a session ends, that in-memory state is dropped; it is **not** designed to be written as a durable user history file.
- Outer **layer obfuscation** (QUIC-mimic wrapper around RPT frames) is enabled by default on the product Python path so clear ``RPT2`` magic is not on the wire alone (mitigation; not a DPI-undetectability claim).

### 3.2 Client applications (Windows, Android, Linux, iOS, and macOS)

- **Product UI** uses **manual Connect / Disconnect** by default. Optional **Settings** preferences (stored only on the device) let the user enable **run at device startup** and/or **autoconnect on launch** (both **off** until opted in). Settings also exposes links to the **most recent audit** (`audit.md`), **privacy policy** (`PRIVACY_POLICY.md`), and **end user licence** (`LICENSE`). These preferences and links are local/device-side only  -  not synced to the node or status page.
- Closing or minimizing the main UI is designed to **leave the tunnel running** until the user **Disconnects** or **Quits** (Windows tray identity: **Privacy Restored**). Android keep-alive uses a foreground VPN service; Activity destroy does not stop the tunnel.
- Clients use **local** cryptographic material (when provisioned) to complete admission and establish session keys when the user connects. On the Python client/node path, session AEAD keys incorporate **ephemeral X25519** material (perfect forward secrecy) in addition to handshake nonces — long-term keys remain for admission/authentication.
- **Traffic-shape** features (packet padding, send-side timing jitter, cover/dummy frames) are **enabled by default** on the product Windows/Linux Python DATA path (bounded pad bucket, modest send jitter, periodic cover frames). Set environment variable **`RPT_TRAFFIC_SHAPE=0`** to disable. They reduce coarse traffic fingerprints and are **not** a guarantee of undetectability against sophisticated DPI. Native Android/Apple engines may lag this wire surface until dual-wired.
- **Full-tunnel** modes route device traffic into the encrypted tunnel **only when** the OS grants VPN permission (Windows Administrator / UAC + Wintun dual `/1` routes, Android VPN consent, iOS/macOS VPN permission). On **iOS and macOS**, full-system VPN uses a signed **Packet Tunnel Network Extension** (and App Group access to admission secrets). Product "connected for residual public IP" requires the system tunnel / dual `/1` path to be active (residual public IP only changes then).
- **On Disconnect / Quit**, clients are designed to **fully tear down** the tunnel (routes, TUN/Packet Tunnel, session) so traffic **reverts to the device's normal public IP path**.
- Clients are **not** designed to upload browsing history or identity dossiers to the node as product telemetry.
- **No public-IP geo admission (from 0.1.9 source):** product Connect does **not** look up the device public IP via third-party geo services, and does **not** allow or deny access by country. Admission is cryptographic (device Ed25519 + node keys) only. Older installed packages (e.g. 0.1.8) may still perform a client-side UK geo check until users upgrade.
- **DNS on full tunnel:** product full-tunnel clients default DNS to the **node tunnel gateway** (`10.88.0.1`) only — **no** client-side public DNS fallbacks (Cloudflare/Google/Quad9/etc.). The node Unbound instance listens on the tunnel address and uses **DNS-over-TLS (DoT)** upstream to privacy-oriented resolvers (`node/unbound-rpt.conf`, `node/install_dns.sh`). Until node DNS is installed, name resolution while connected may fail. The VPS provider may still see DoT/encrypted recursive upstream traffic from the node.
- **Kill switch / leak protection:** when residual full tunnel is up, product Windows/Linux clients apply an **always-on kill switch** (block non-tunnel outbound) plus **IPv6 ISP path blocking**. STUN/mDNS ports used by common WebRTC discovery are blocked under the kill-switch rules. Android builder config uses `blocking=true` / `allowBypass=false`. Disconnect rolls back kill-switch and IPv6 mitigations.
- Public download packages (Windows `.exe`, Android `.apk`, Linux `.tar.gz` installer, macOS `.zip`, iOS `.zip`) may include the **public** node key (`node_elgamal.pub`) so clients can open a HELLO. Each install **generates a unique Ed25519 device private key on first run** and keeps it only in local device-private storage - packages do **not** ship a shared `client_ed25519.priv` (which would allow universal impersonation). They **never** include the **node private key** (`node_elgamal.priv`). Windows installers ship a **bundled runtime** (no separate system Python install). The Linux installer package ships **manylinux wheels** for the app Python crypto stack (private venv via `install.sh`); OS tools such as TUN/`ip`/root for full tunnel remain host-provided.

### 3.3 Public status page (e.g. Render)

- Displays the product **title**, beta note, and **download links** only.
- Does **not** expose a live connected-client count or poll a session metric on the public HTML surface.
- Optional `/api/status` JSON is **title-only** (no `clients_connected`).
- May offer **download links** to public GitHub release packages (current catalog: **v0.2.2**).

### 3.4 Operator-held secrets

- **Node ElGamal private key** and **authorized client private keys** are operational secrets.
- The **node ElGamal private key** lives only on the operator node (e.g. `/opt/restore-privacy/secrets/`) and is gitignored - **never** in public release zips.
- **Client** device Ed25519 keys are created locally on first run (not a shared installer secret). Possession of a device key allows tunnel use for that install - treat local secrets as credentials.

---

## 4. Limits of this privacy promise

Please understand these **operational limits**:

1. **Hosting and networks.** The VPS provider, CDN, or DNS operator may log IP-level connection metadata under **their** policies (outside this application's no-log settings).
2. **Destination sites.** Websites and services you visit through the tunnel have their own privacy policies.
3. **Device and OS.** Android VPN consent dialogs, Windows admin elevation, iOS/macOS VPN permission sheets, Apple Network Extension processes, crash reporters, or OS network stacks may process data independently of this app.
4. **Misconfiguration.** If an operator enables verbose logging, reverse proxies with access logs, or third-party monitoring, that can create logs this policy assumes are off.
5. **Security vs. privacy.** Per-device Ed25519 keys identify a **product install**, not a named human account - but a device key can still be treated as an access secret for that install.
6. **Open relay risk is reduced by keys, not by accounts.** Unauthorized clients should fail handshake; authorized keys must be protected.
7. **Traffic analysis mitigations are incomplete.** Product Windows/Linux clients apply packet padding, timing jitter, and cover traffic **by default** (opt out with `RPT_TRAFFIC_SHAPE=0`). They reduce coarse size/timing fingerprints; they do **not** guarantee undetectability against sophisticated DPI. Multi-hop hop *lists* may be configured for future use; product traffic remains **single-hop / entry-only** until a real multi-hop relay path ships (status never claims multi-hop residual from config alone). Session AEAD keys use ephemeral X25519 material (PFS) so long-term key compromise after a session ends should not reconstruct that session’s traffic keys from the public transcript alone.
8. **Self-hosted operators** must still protect `node_elgamal.priv`, keep product no-log defaults, and remember provider-level IP logs (limit 1 above).

---

## 5. Cookies and tracking

The status page is a minimal static UI. It does **not** use advertising trackers or analytics SDKs in the shipped code. It does **not** poll a live client count. No account login cookies are required for the tunnel protocol itself.

---

## 6. Children

This software is a network tool for general audiences. It is not directed at children under 13 (or the minimum age in your jurisdiction). Do not provide personal data of children through misconfigured logging or external services.

---

## 7. Changes

We may update this policy as the product evolves. The **Last updated** date at the top will change when material edits are made. Continued use of updated software implies review of the current policy in the repository.

---

## 8. Contact

For privacy questions about this open-source project, open an issue on:

https://github.com/rgsneddon/restore-privacy

Or contact the repository owner via their GitHub profile.

---

## 9. Related documents

- Project license and third-party credits: [`LICENSE`](LICENSE), [`CREDITS.md`](CREDITS.md)
- How to install and run: [`README.md`](README.md)
