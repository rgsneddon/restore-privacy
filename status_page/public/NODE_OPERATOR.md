# Residual node / operator path

**Not** the Suite client installers. This page is for people who prefer to
**host** a residual node (operator tooling / self-host) rather than only
install Restore Privacy Suite for residual **Connect** on a phone or PC.

| Role | What you get |
|------|----------------|
| **Suite client** | Free installers + KEYGEN on the VPN APP Shop — residual Connect on *your* device |
| **Node / operator** | Run the co-joined residual stack on a **host** you control |

The monthly KEYGEN checkout unlocks **client** Connect. It does **not** replace
node hosting and does **not** turn a client download into a residual node package.

---

## Co-joined node (three parts, one host)

Each residual **node server** runs **three co-located roles** as one deploy unit
— not three unrelated machines:

| Part | What it does |
|------|----------------|
| **VPN residual** | HELLO / sessions / TUN path — residual privacy tunnel (public status stays **title-only**) |
| **rpAI · Ned** | Co-located Ned helper loop — learns oracle/housework counters for admin rpS (not a full LLM fleet claim) |
| **Perccent blockchain** | Co-located chain seed heartbeat — same host as residual, private hooks on the node UI port |

They start together with `python3 -m node` / `rpt-node.service` and
`scripts/deploy_rpt_node.py`. Clients keep a **single residual contact**
(`host:44044` for Connect); Ned and Perccent use private UI hooks on that same
host (default UI port **8080**), not a second peer list.

Optional **Helsinki oracle** (master) collates satellite heartbeats for admin
**rpS** (`/admin/rps`) — readiness, compute score, Ned findings/housework.

---

## Product node stack (operator monorepo)

| Path | Purpose |
|------|---------|
| `node/` | Residual co-joined stack (VPN + `cojoined_roles` + optional oracle collate) |
| `node/cojoined_roles.py` | Role registry: vpn · rpai · perccent |
| `node/oracle_master.py` | Helsinki oracle aggregation helpers |
| `node_operator/` | Node Operator lab GUI |
| `scripts/selfhost_node.sh` | One-shot self-host install |
| `scripts/deploy_rpt_node.py` | Remote deploy (copies co-joined modules) |
| `scripts/deploy_perc_chain_helsinki.py` | Helsinki Perccent public rendezvous (when used) |

**Node Operator** is **admin / lab** tooling. Public node `/status` stays
**title-only** (no live client count).

---

## Self-host (summary)

From a product monorepo checkout on a Linux host with TUN:

```bash
sudo bash scripts/selfhost_node.sh
# Deploy remote: python scripts/deploy_rpt_node.py
```

Ports (typical): **UDP 44044** residual tunnel, **TCP 8080** title-only status UI
+ private co-join/capacity hooks (token-gated). Weekly fleet wipe notes live in
operator README material.

---

## Node Operator package (lab GUI)

When packaged, the Linux operator GUI artifact is named like:

`restore-privacy-node-operator-<version>-linux-x64.tar.gz`

under `releases/node-operator/`. That artifact is **operator tooling**, not a
Suite free-download client.

---

## Related public docs

| Doc | Path |
|-----|------|
| Suite client README | [/README.md](/README.md) |
| Privacy policy | [/PRIVACY_POLICY.md](/PRIVACY_POLICY.md) |
| Security audit | [/AUDIT.md](/AUDIT.md) |
| Public Suite Pages (client) | https://rgsneddon.github.io/restore-privacy-suite/ |
| Admin rpS (operator auth) | `/admin/rps` |

---
