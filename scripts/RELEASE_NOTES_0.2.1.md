# Restore Privacy 0.2.1 — release notes

**Status:** Public package release (docs/audit refresh + privacy feature surface).

## Highlights

- Production node remains **`82.221.101.241:44044`**.
- **Session PFS:** ephemeral X25519 mixed into session AEAD key derivation (Python path).
- **Optional traffic shaping** (defaults off): packet padding, send jitter, cover frames (`node/traffic_shape.py`).
- **Multi-hop:** hop *list* config only — **not residual multi-hop**; status is entry-only / not routed.
- **Self-host:** `scripts/selfhost_node.sh` one-shot install recipe.
- **Product node pub pin:** `product/node_elgamal.pub` must match the live node (Android always refreshes assets → filesDir).
- Catalog, README, privacy policy, and **audit.md** updated for **0.2.1**.

## Upgrade

Install **0.2.1** packages from this GitHub Release or the status page. Prefer upgrading from 0.2.0 so node pub and handshake paths stay current.

## Operators

- Self-host: `sudo bash scripts/selfhost_node.sh`
- Build: `python scripts/build_release_0.2.1.py`
- Audit: [audit.md](../audit.md)
