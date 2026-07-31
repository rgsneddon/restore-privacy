# Residual node / operator path

**Not** the Suite client installers. This page is for people who prefer to
**host** a residual VPN **node** (operator tooling / self-host) rather than only
install Restore Privacy Suite for residual **Connect** on a phone or PC.

| Role | What you get |
|------|----------------|
| **Suite client** | Free installers + KEYGEN on the VPN APP Shop — residual Connect on *your* device |
| **Node / operator** | Run residual node software and operator tooling on a **host** you control |

The monthly KEYGEN checkout unlocks **client** Connect. It does **not** replace
node hosting and does **not** turn a client download into a residual node package.

---

## Product node stack (operator monorepo)

In the product tree, residual node work lives under:

| Path | Purpose |
|------|---------|
| `node/` | Residual VPN node (HELLO, sessions, TUN on Linux, nolog, multi-hop structure) |
| `node_operator/` | **Node Operator** desktop/lab GUI — sessions, priority, package upload, UPDATE_PUSH |
| `scripts/selfhost_node.sh` | One-shot self-host install (node + tunnel DNS + host privacy) |
| `scripts/deploy_rpt_node.py` | Remote deploy helper |

**Node Operator** (`python3 -m node_operator`) is **admin / lab** tooling for
running this host as a residual node lab: start/stop lab stack, connected
clients (admin only), prioritise clients, upload monopin packages to the paid
store host, push residual update directives. Public node `/status` stays
**title-only** (no live client count).

This is **not**:

- a Suite client platform button (Windows / Android / macOS / iOS / Linux)
- unlocked by KEYGEN subscription checkout alone
- the public status shop admin console (that is operator-auth on the status host)

---

## Self-host (summary)

From a product monorepo checkout on a Linux host with TUN:

```bash
sudo bash scripts/selfhost_node.sh
# Deploy remote: python scripts/deploy_rpt_node.py
```

See the product README **Operators / developers** section for ports (UDP 44044
tunnel, TCP 8080 title-only status UI), secrets discipline, and weekly fleet
wipe notes. Source monorepo for full node code is **private**; public shop docs
and this page orient the preference without publishing private operator secrets.

---

## Node Operator package (lab GUI)

When packaged, the Linux operator GUI artifact is named like:

`restore-privacy-node-operator-<version>-linux-x64.tar.gz`

under `releases/node-operator/`. That artifact is **operator tooling**, not a
Suite free-download client. Prefer building from the monorepo (`python3 -m
node_operator`) when you already have a checkout.

---

## Related public docs

| Doc | Path |
|-----|------|
| Suite client README | [/README.md](/README.md) |
| Privacy policy | [/PRIVACY_POLICY.md](/PRIVACY_POLICY.md) |
| Security audit | [/AUDIT.md](/AUDIT.md) |
| Public Suite Pages (client) | https://rgsneddon.github.io/restore-privacy-suite/ |

---

*Restore Privacy — residual node / operator orientation (public). Suite KEYGEN
installers remain on the homepage download boxes.*
