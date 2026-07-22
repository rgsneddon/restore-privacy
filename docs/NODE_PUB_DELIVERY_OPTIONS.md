# Node public-key delivery options (HELLO pin)

## Current product path

Paid catalog packages (Windows `.exe`, Android `.apk`, Linux `.tar.gz`, macOS `.zip`,
iOS `.zip`) **may include the public node key** (`node_elgamal.pub`, and when
multi-hop residual-via-exit is enabled, `exit_node_elgamal.pub`) so clients can
open a HELLO without a network round-trip first.

- Load path: `client/secrets_loader.py` (entry pin default; exit pin selected by
  residual endpoint when multi-hop is active).
- **Never** ship `node_elgamal.priv` (or exit private keys) in packages.

Observed packaging honesty (privacy policy): packages may include the **public**
pin for HELLO; each install generates its own device Ed25519 private key.

## Critical honesty: “obfuscate” ≠ secret

`node_elgamal.pub` is a **public** encryption pin for the residual node. Anyone
who obtains it can *encrypt HELLO material to the node*; they cannot decrypt
node-held secrets or impersonate the node without the **private** key.

So “more private methods” below can only:

1. Raise **casual extraction** friction from installer trees, and/or  
2. Improve **authenticity**, **rotation**, or **when** the pin is delivered  

They **cannot** turn the public pin into a confidential secret. A determined
reverse engineer who can run HELLO can always recover whatever bytes the client
uses as the node public key.

---

## Recommended alternatives / complements

### 1. Authenticated pin fetch after payment (recommended primary complement)

**How:** After successful Stripe/checkout entitlement (session id / grant), client
or a small post-pay step downloads **only** the current entry (and exit) **public**
pin(s) over HTTPS from the status host (or a pin endpoint), with TLS + optional
response signature (operator Ed25519 over pin bytes + version).

**Improves:** Pin **rotation without rebuilding** every catalog package; removes
need for the installer tree to be the *only* pin source; casual unzip of a free
leak of an old package does not guarantee the **current** pin.

**Does not:** Hide the pin from anyone who paid or who intercepts the TLS
session as the device; still requires clients to trust the pin server /
signature root.

**Product fit:** Aligns with existing payment entitlement and private repo /
paid delivery. Keep a **bootstrap fallback** pin in-package only if offline
first Connect is required.

### 2. Entitlement-gated extract (pay wall before plain secrets dir)

**How:** Installer ships pin bytes only inside an encrypted blob (symmetric key
delivered after entitlement verify, or unwrapped using material from
`payment_entitlement.json` + server challenge). Until verify succeeds, no
`node_elgamal.pub` file sits plain under `secrets/`.

**Improves:** Casual filesystem browsing of an unpaid/abandoned install tree.

**Does not:** Protect against a user who has paid (they must obtain usable pin
bytes); runtime memory still holds the pin for HELLO.

### 3. Non-obvious resource packing (obfuscation only)

**How:** Embed pin as non-filename-obvious resources (e.g. split chunks, XOR with
build-time constant, store under opaque asset names, or compile into a small
native blob)—still **public** material after decode.

**Improves:** Slightly harder **casual** APK/zip grepping for `node_elgamal.pub`
or PEM-looking blobs.

**Does not:** Cryptographic confidentiality; RE tools recover the pin once the
client constructs `ElGamalPublicKey`. Prefer this only as a **light** hardening
layer on top of (1) or (2), not as a security boundary.

### 4. Pin directory / CDN with pinning + short TTL

**How:** Host current pins at a well-known HTTPS path (status origin) with
`Cache-Control` short TTL and optional **transparency log** or signed pin list
(versioned `pins.json` + sig). Clients refresh periodically or on HELLO
failure.

**Improves:** Fast **rotation** after entry rebuild/key rotate; multi-hop
**entry vs exit** pins published together; one operator surface for Node A/B.

**Does not:** Stop adversaries from downloading the same public pins.

### 5. OS keystore / secure enclave for *device* keys only (not for node pub)

**How:** Continue storing **client Ed25519 private** keys in platform keystore
(where available). Optionally cache **fetched** node **public** pins in app
private storage (not world-readable).

**Improves:** Device private-key hygiene (already product direction).

**Does not:** Make the **node public** pin secret; do not confuse with sealing
`node_elgamal.priv` on the **server** (`RPT_KEY_BACKEND=sealed|tpm`).

---

## Entry vs exit pins

| Role | Public file (product monopin) | When needed |
|------|-------------------------------|-------------|
| **Entry (Node A)** | `node_elgamal.pub` | Default residual HELLO |
| **Exit (Node B)** | `exit_node_elgamal.pub` | Multi-hop residual-via-exit **and** entry-drain failover residual |

Any delivery design should provision **both** public pins for catalog clients that
support multi-hop / failover, still **never** shipping private keys.

---

## Practical recommendation for Restore Privacy

1. **Keep** a minimal in-package public pin for offline/first-boot HELLO if you
   need zero network before Connect (current model).  
2. **Add** (recommended) **post-payment authenticated pin fetch** + signed pin
   version so rebuild/rotation does not depend only on re-shipping all five
   catalog binaries.  
3. Optionally **gate** plain `secrets/node_elgamal.pub` extract until entitlement
   is active.  
4. Treat **resource obfuscation** as optional cosmetic friction only.  
5. **Never** ship `node_elgamal.priv`; node-side sealed/TPM backends remain the
   correct place for long-term private material.

---

## Non-goals of this note

- Implementing the above pipelines  
- Claiming public-key obfuscation equals resistance to a determined reverse engineer  
- Changing HELLO/ElGamal crypto
