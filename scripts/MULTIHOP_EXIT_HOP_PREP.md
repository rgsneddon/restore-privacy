# Multi-hop exit hop prep (second FlokiNET VPS)

**Status:** prepare only — **paused awaiting VPS readiness**.  
**Role of second host (for now):** **exit hop / exit server** on a **different FlokiNET country** than the product entry node.  
**Entry (unchanged product default):** `82.221.101.241:44044` (Iceland / FlokiNET).

Product honesty: multi-hop hop **lists** may be configured for planning.  
`MULTI_HOP_ROUTING_IMPLEMENTED` remains **false** until a real intermediate relay/data path ships.  
Connect still dials the **entry** hop only. Status text will say *path configured (not routed; entry-only)* — not residual multi-hop.

---


## Live exit hop (Romania) — recorded

| Field | Value |
|-------|--------|
| **Role** | Exit hop (for now) |
| **Country** | **Romania** (FlokiNET) |
| **Public IPv4** | `185.146.232.107` |
| **SSH** | `raskul@185.146.232.107` / alias `restore-privacy-hop` |
| **SSH key** | `~/.ssh/id_ed25519_restore_privacy_hop` (BatchMode confirmed) |
| **OS** | Ubuntu 26.04 LTS |
| **ElGamal** | **A — new exit-only keypair** (not product entry pin) |
| **Entry (unchanged)** | `82.221.101.241:44044` (Iceland) |
| **RPT port** | UDP **44044** |
| **Host firewall** | `ufw` present; status **inactive** (not blocking). Rule `allow 44044/udp` applied for when ufw is enabled. INPUT policy ACCEPT. |
| **FlokiNET panel** | **Operator must** open **UDP 44044** inbound for this VPS in the FlokiNET control panel (cannot automate panel login). |

## Install status (Romania exit)

| Check | Result |
|-------|--------|
| **rpt-node.service** | **active** + **enabled** |
| **UDP 44044** | listening on `0.0.0.0:44044` |
| **ElGamal A** | new exit key on host (`node_elgamal.priv` present; pub SHA-256 ≠ entry product pin) |
| **External UDP** | send to `185.146.232.107:44044` succeeded (`nc -u -z` exit 0) |
| **Status UI** | local `http://127.0.0.1:8080/api/status` → title-only |
| **Multi-hop residual** | still **not** routed (`MULTI_HOP_ROUTING_IMPLEMENTED=false`); entry default remains Iceland |


## What we need when the exit VPS is ready

Provide these before we can **build/install the multi-hop exit node** on the new box:

| # | Input | Why |
|---|--------|-----|
| 1 | **Public IPv4** of the new VPS | DNS name optional; IP is required for deploy + hop config |
| 2 | **SSH reachability** as deploy user | Prefer user **`raskul`** (FlokiNET image) with **sudo**; password only for one-time key install |
| 3 | **SSH public-key auth working** | Preferred key: `~/.ssh/id_ed25519_restore_privacy_hop` (already generated). Confirm: `ssh -i … -o BatchMode=yes raskul@<IP> 'whoami'` |
| 4 | **FlokiNET region / country label** | e.g. Romania / Netherlands / Finland — for honest docs only |
| 5 | **UDP port for RPT** | Default product port **`44044/udp`** open in FlokiNET firewall + host |
| 6 | **TCP optional** | Status UI **`8080/tcp`** only if you want node status on the exit (not required for exit role) |
| 7 | **Node ElGamal decision** | **A)** new exit-only keypair (recommended for isolation), or **B)** same product pin as entry (`product/node_elgamal.pub`) — product clients today pin the **entry** pub; exit key policy must match how multi-hop is later wired |
| 8 | **OS baseline** | Ubuntu/Debian-class image with `python3`, `systemd`, and ability to run `node/install.sh` |
| 9 | **Hostname label** (optional) | e.g. `restore-privacy-hop` in DNS or `/etc/hosts` / SSH `Host` alias |

**Do not** put the SSH password or private keys in git.

---

## Files prepared in monorepo (this prep)

| Path | Purpose |
|------|---------|
| `client/multihop.py` | Hop list config; `build_entry_exit_path`, `multihop_config_from_env`; honesty flags |
| `scripts/hop_env.example` | Env template for entry + exit deploy targets |
| `scripts/deploy_rpt_node.py` | Supports hop key path + any `RPT_SSH_HOST` (second host) |
| `scripts/MULTIHOP_EXIT_HOP_PREP.md` | This checklist |
| `~/.ssh/id_ed25519_restore_privacy_hop[.pub]` | Operator hop SSH key (local; gitignored) |

---

## Deploy sketch (after IP + SSH work)

```bash
# Point deploy at the NEW exit VPS (not the entry node IP)
export RPT_SSH_HOST='<EXIT_PUBLIC_IPV4>'
export RPT_SSH_USER=raskul
export RPT_SSH_SUDO=1
export RPT_SSH_KEY="$HOME/.ssh/id_ed25519_restore_privacy_hop"

# Optional path planning on operators/clients (config only until routing ships)
export RPT_MULTIHOP_ENABLED=1
export RPT_EXIT_HOST='<EXIT_PUBLIC_IPV4>'
export RPT_EXIT_PORT=44044
# Or: export RPT_MULTIHOP_HOPS='82.221.101.241:44044,<EXIT_PUBLIC_IPV4>:44044'

python3 scripts/deploy_rpt_node.py
# Then on host: install.sh / host privacy as for entry node
```

---

## Pause

When you have spun up the second FlokiNET VPS, send at least:

1. Public IPv4  
2. Confirmation SSH as `raskul` works with the hop key (or temporary password for key install only)  
3. Country/region label  
4. ElGamal choice A or B  

Then we can install the exit node and wire hop config. No multi-hop residual claims until routing is implemented.
