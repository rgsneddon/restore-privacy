# Product public materials

## `node_elgamal.pub`

Public ElGamal key for the **Iceland** residual peer / default entry (`82.221.101.241:44044`).

Clients encrypt CLIENT_HELLO hybrid material to this key. If a package ships a
**different** public key than the running node private key, the node silently
drops HELLO (admission hybrid decrypt fails) and the client times out.

| Field | Value |
|-------|--------|
| Size | 256 bytes |
| SHA-256 | see `NODE_ELGAMAL_PUB.sha256` |
| Host | `82.221.101.241:44044` (IS default entry) |

**Never** put `node_elgamal.priv` here. Device Ed25519 keys are generated on the
client at first run (not shipped shared).

## `exit_node_elgamal.pub`

Public ElGamal key for the **Romania** residual peer (`185.146.232.107:44044`).

## `us_node_elgamal.pub`

Public ElGamal key for the **United States** residual peer (`5.161.242.85:44044`).
Copied from the live US node `/opt/restore-privacy/secrets/node_elgamal.pub`
(256 bytes; HELLO must match that on-box private).

## `de_node_elgamal.pub`

Archived public key for the **retired Germany** residual peer (`167.233.224.5`).
No longer a catalog dial peer.

**Never** put `*.priv` keys in this directory. Privates live only on each node
under `/opt/restore-privacy/secrets/`.

Android release builds inject catalog pubs into APK assets via
`copyRptSecretsToAssets` (prefers `product/`, then `secrets/`).
