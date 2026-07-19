# Privacy Policy â€” Restore Privacy

**Last updated:** 19 July 2026  
**Product:** Restore Privacy Tunnel (RPT) â€” custom VPN node, client apps, and public status page  
**Current client packages:** [v0.1.6](https://github.com/rgsneddon/restore-privacy/releases/tag/0.1.6) (Windows Â· Android; macOS Â· iOS prep packages for Mac-side signing)  
**Operator / project:** Russell G Sneddon (`rgsneddon`) / public repository [restore-privacy](https://github.com/rgsneddon/restore-privacy)

This policy describes how the **Restore Privacy** software is designed to handle data. It is written for end users and operators. It is **not** legal advice and is not a jurisdiction-specific compliance certificate (e.g. full GDPR/CCPA legal opinion).

---

## 1. Summary

Restore Privacy is a **custom-built encrypted tunnel** (not WireGuard, OpenVPN, or other pre-existing VPN products). The product goal is:

| Commitment | Meaning |
|------------|---------|
| **No user-info logs** | The node and status software are configured **not** to write connection, session, access, traffic, accounting, or peer-activity logs to disk. |
| **No client PII collection** | The public status surface exposes **only** a live **current connected client count** (and a product title)â€”not identities, IPs, usernames, or per-client lists. |
| **Tunnel as a relay** | After cryptographic admission, the node forwards encrypted-session traffic; it is not designed as an analytics or advertising platform. |

---

## 2. What we do **not** collect or retain (by design)

Unless an operator **deliberately** changes configuration or hosting outside this softwareâ€™s defaults, the shipped node and status page are intended **not** to:

- Store **usernames, passwords, email addresses, or account profiles** for tunnel use (tunnel attach uses **cryptographic product keys**, not user accounts).
- Write **connection logs**, **session logs**, **access logs**, **traffic logs**, or **peer activity logs** for tunnel use.
- Publish **client IP addresses**, **device identifiers**, or **session identifiers** on the public status page.
- Keep a **lifetime / cumulative â€œtotal clients everâ€** counter on the public page (the status metric is **currently connected** sessions only).
- Bundle the **node ElGamal private key** (`node_elgamal.priv`) in public packages (never shipped).

Process stdout/stderr for the node service is configured for **no journal session streams** in the standard install (`StandardOutput=null` / similar).

---

## 3. What processing happens (high level)

### 3.1 VPN node (server)

- Listens for RPT tunnel handshakes and **encrypted** data frames.
- **Admits** only peers that complete the product handshake with an **authorized client key** (Ed25519 allow-list + ElGamal / Pedersen-based handshake materials).
- Assigns a temporary tunnel IP and **relays** IP traffic (forwarding + NAT) while the session is active.
- Holds **in-memory** session state for active tunnels so traffic can be routed and so a **current session count** can be reported.
- When a session ends, that in-memory state is dropped; it is **not** designed to be written as a durable user history file.

### 3.2 Client applications (Windows, Android, iOS, and macOS)

- **Product UI** uses **manual Connect / Disconnect** by default. Optional **Settings** preferences (stored only on the device) let the user enable **run at device startup** and/or **autoconnect on launch** (both **off** until opted in). These preferences are local only â€” not synced to the node or status page.
- Closing or minimizing the main UI is designed to **leave the tunnel running** until the user **Disconnects** or **Quits** (Windows tray identity: **Privacy Restored**). Android keep-alive uses a foreground VPN service; Activity destroy does not stop the tunnel.
- Clients use **local** cryptographic material (when provisioned) to complete admission and establish session keys when the user connects.
- **Full-tunnel** modes route device traffic into the encrypted tunnel **only when** the OS grants VPN permission (Windows Administrator / UAC + Wintun dual `/1` routes, Android VPN consent, iOS/macOS VPN permission). On **iOS and macOS**, full-system VPN uses a signed **Packet Tunnel Network Extension** (and App Group access to admission secrets). Product â€œconnected for residual public IPâ€ requires the system tunnel / dual `/1` path to be active (residual public IP only changes then).
- **On Disconnect / Quit**, clients are designed to **fully tear down** the tunnel (routes, TUN/Packet Tunnel, session) so traffic **reverts to the deviceâ€™s normal public IP path**.
- Clients are **not** designed to upload browsing history or identity dossiers to the node as product telemetry.
- Public download packages (Windows `.exe`, Android `.apk`, macOS `.zip`, iOS `.zip`) may include the **public** node key (`node_elgamal.pub`) so clients can open a HELLO. Each install **generates a unique Ed25519 device private key on first run** and keeps it only in local device-private storage â€” packages do **not** ship a shared `client_ed25519.priv` (which would allow universal impersonation). They **never** include the **node private key** (`node_elgamal.priv`). Windows installers ship a **bundled runtime** (no separate system Python install).

### 3.3 Public status page (e.g. Render)

- Proxies or displays a **live** `clients_connected` value from the node status API.
- Updates the number in the browser via **client-side polling** (no requirement to store user history on the page host).
- May offer **download links** to public GitHub release packages (current catalog: **v0.1.6**).

### 3.4 Operator-held secrets

- **Node ElGamal private key** and **authorized client private keys** are operational secrets.
- The **node ElGamal private key** lives only on the operator node (e.g. `/opt/restore-privacy/secrets/`) and is gitignoredâ€”**never** in public release zips.
- **Client** device Ed25519 keys are created locally on first run (not a shared installer secret). Possession of a device key allows tunnel use for that installâ€”treat local secrets as credentials.

---

## 4. Limits of this privacy promise

Please understand these **operational limits**:

1. **Hosting and networks.** The VPS provider, CDN, or DNS operator may log IP-level connection metadata under **their** policies (outside this applicationâ€™s no-log settings).
2. **Destination sites.** Websites and services you visit through the tunnel have their own privacy policies.
3. **Device and OS.** Android VPN consent dialogs, Windows admin elevation, iOS/macOS VPN permission sheets, Apple Network Extension processes, crash reporters, or OS network stacks may process data independently of this app.
4. **Misconfiguration.** If an operator enables verbose logging, reverse proxies with access logs, or third-party monitoring, that can create logs this policy assumes are off.
5. **Security vs. privacy.** Per-device Ed25519 keys identify a **product install**, not a named human accountâ€”but a device key can still be treated as an access secret for that install.
6. **Open relay risk is reduced by keys, not by accounts.** Unauthorized clients should fail handshake; authorized keys must be protected.

---

## 5. Cookies and tracking

The status page is a minimal static/JS UI. It does **not** use advertising trackers or analytics SDKs in the shipped code. Browser `fetch` of `/api/status` is for the live count only. No account login cookies are required for the tunnel protocol itself.

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
