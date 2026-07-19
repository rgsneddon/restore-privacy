# Product public materials

## `node_elgamal.pub`

Public ElGamal key for the **production** RPT node (`82.221.101.241:44044`).

Clients encrypt CLIENT_HELLO hybrid material to this key. If a package ships a
**different** public key than the running node private key, the node silently
drops HELLO (admission hybrid decrypt fails) and the client times out.

| Field | Value |
|-------|--------|
| Size | 256 bytes |
| SHA-256 | see `NODE_ELGAMAL_PUB.sha256` |
| Host | `82.221.101.241:44044` |

**Never** put `node_elgamal.priv` here. Device Ed25519 keys are generated on the
client at first run (not shipped shared).

Android release builds inject this file into APK assets via
`copyRptSecretsToAssets` (prefers `product/`, then `secrets/`).
