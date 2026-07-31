# Product public materials

## `node_elgamal.pub`

Public ElGamal key for the **Iceland** residual peer (`82.221.101.241:44044`).

Clients encrypt CLIENT_HELLO hybrid material to this key. If a package ships a
**different** public key than the running node private key, the node silently
drops HELLO (admission hybrid decrypt fails) and the client times out.

| Field | Value |
|-------|--------|
| Size | 256 bytes |
| SHA-256 | see `NODE_ELGAMAL_PUB.sha256` |
| Host | `82.221.101.241:44044` (IS entry) |

**Never** put `node_elgamal.priv` here. Device Ed25519 keys are generated on the
client at first run (not shipped shared).

## `de_node_elgamal.pub`

Public ElGamal key for the **Germany** residual peer (`178.105.187.178:44044`) —
**default residual entry** for monopin **1.0.0** (and prior 0.5.8+ clients).

## `exit_node_elgamal.pub`

Public ElGamal key for multi-hop **exit** (same material as DE product pin).
Former Romania peer is **deprecated**; do not dial `185.146.232.107`.

## `us_node_elgamal.pub`

Public ElGamal key for the **United States** residual peer (`5.161.242.85:44044`).

**Never** put `*.priv` keys in this directory. Privates live only on each node
under `/opt/restore-privacy/secrets/`.

Android release builds inject catalog pubs into APK assets via
`copyRptSecretsToAssets` (prefers `product/`, then `secrets/`).
