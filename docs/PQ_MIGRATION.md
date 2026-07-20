# Post-quantum migration plan — Restore Privacy Tunnel (RPT)

**Status:** staged readiness (plan + hybrid IKM/KEM hook in tree)  
**Last updated:** 2026-07-20  
**Code hook:** `node/pq_hybrid.py`  
**Wire residual PQ:** **not** claimed until full client/node dual-wire + real ML-KEM ships

---

## 1. Threat

Large-scale cryptographically relevant quantum computers (CRQC) could break:

| Primitive in RPT today | PQ risk |
|------------------------|---------|
| Ephemeral **X25519** (session PFS IKM) | Shor → session key recovery from transcript |
| **Ed25519** device admission signatures | Shor → forge device identity |
| Long-term **ElGamal** (MODP 2048 hybrid wrap) | Shor → decrypt HELLO hybrids offline |
| AEAD **ChaCha20-Poly1305** | Largely considered PQ-safe at current sizes |

Compromise of long-term ElGamal after harvest-now-decrypt-later is the primary
motivation for hybrid KEM on the HELLO/session path.

---

## 2. Hybrid stages

| Stage | What | Product claim |
|-------|------|----------------|
| **S0** (now) | Classical PFS (X25519) + plan + `pq_hybrid` unit hook | No residual PQ claim |
| **S1** | Hybrid IKM: classical PFS IKM ∥ ML-KEM shared (`hybrid_session_ikm`) on Python path under `RPT_PQ_HYBRID=1` | Lab / opt-in only |
| **S2** | Dual-wire CLIENT_HELLO / SERVER_HELLO carry KEM ct + pub; node + Python clients | Staged residual hybrid |
| **S3** | Android/Apple native engines dual-wired | Cross-platform residual hybrid |
| **S4** | PQ signatures for admission (optional, later) | Device auth PQ |

Default product env keeps `RPT_PQ_HYBRID=0` until S2 is complete and audited.

---

## 3. What rotates when

| Material | Rotation driver | Notes |
|----------|-----------------|-------|
| Node **ElGamal** long-term | `node.key_rotation` / HSM-sealed backend | Clients re-provision **public** only |
| Session AEAD keys | Per session (X25519 PFS) | Already ephemeral |
| Hybrid KEM ephemeral | Per session encaps | When S2 enabled |
| Device Ed25519 | Per install (not shared) | Never ship shared client priv |
| Product `node_elgamal.pub` pin | On node rotation | Catalog / assets refresh |

HSM/TPM-class sealed storage (`RPT_KEY_BACKEND=sealed|tpm`) reduces impact of
disk theft of long-term private material between rotations.

---

## 4. Kyber / ML-KEM choice

- Target: **ML-KEM** (FIPS 203), formerly Kyber, at security level matching AES-128 or AES-256 product policy.
- Interim CI: `ToyKyberClassKem` in `node/pq_hybrid.py` exercises encaps/decaps **API only** — **not** a secure PQ KEM.
- Production must replace the toy with a maintained library (e.g. `cryptography` ML-KEM when available, or liboqs binding) before any residual PQ claim.

---

## 5. Compatibility

- Classical-only clients continue to work while hybrid is off.
- Hybrid HELLO must be version-flagged so older clients fail closed with a clear upgrade message.
- Rotation of classical ElGamal remains independent of PQ wire enablement.

---

## 6. Exit criteria for residual PQ claim

1. Real ML-KEM on node + product Python clients.  
2. Mobile/Apple parity or honest “Python primary” residual statement.  
3. Audit refresh: hybrid transcript, KEM sizes, downgrade resistance.  
4. `RPT_PQ_HYBRID` product default **on** only after 1–3.

Until then, document hybrid as **readiness / opt-in lab**, not residual privacy.
