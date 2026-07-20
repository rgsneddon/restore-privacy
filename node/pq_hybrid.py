"""Post-quantum hybrid hooks: classical session IKM + Kyber-class KEM shared.

This module stages hybrid IKM mixing for future wire enablement. It does **not**
claim residual post-quantum confidentiality on the product wire until full
client/node dual-wire ships under a product flag.

- ``hybrid_session_ikm`` mixes classical PFS IKM with a KEM shared secret.
- ``ToyKyberClassKem`` is a **test double** (hash-based) for unit encaps/decaps —
  not a NIST-standardized ML-KEM implementation.
- Production migration steps: see ``docs/PQ_MIGRATION.md``.

Env: ``RPT_PQ_HYBRID=1`` enables hybrid mix when callers opt in (default off).
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from typing import Optional, Protocol, Tuple


def pq_hybrid_enabled(env: Optional[dict] = None) -> bool:
    e = env if env is not None else os.environ
    raw = str(e.get("RPT_PQ_HYBRID", "0")).strip().lower()
    return raw in ("1", "true", "on", "yes")


class Kem(Protocol):
    """Minimal KEM interface (Kyber/ML-KEM-class)."""

    def generate_keypair(self) -> Tuple[bytes, bytes]:
        """Return (public_key, secret_key)."""
        ...

    def encaps(self, public_key: bytes) -> Tuple[bytes, bytes]:
        """Return (ciphertext, shared_secret)."""
        ...

    def decaps(self, secret_key: bytes, ciphertext: bytes) -> bytes:
        """Return shared_secret."""
        ...


@dataclass
class ToyKyberClassKem:
    """Deterministic hash-based KEM stand-in for unit tests / staging.

    **Not** post-quantum secure. Labelled toy so it cannot be mistaken for
    production ML-KEM. Wire hybrid must replace this with real ML-KEM (e.g.
    cryptography/liboqs) before product residual PQ claims.
    """

    name: str = "toy-kyber-class-v1"
    sk_len: int = 32
    pk_len: int = 32
    ct_len: int = 32
    ss_len: int = 32

    def generate_keypair(self) -> Tuple[bytes, bytes]:
        sk = os.urandom(self.sk_len)
        pk = hashlib.sha256(b"toy-kem-pk|" + sk).digest()
        return pk, sk

    def encaps(self, public_key: bytes) -> Tuple[bytes, bytes]:
        if len(public_key) != self.pk_len:
            raise ValueError("bad toy kem public key length")
        eph = os.urandom(32)
        ct = hashlib.sha256(b"toy-kem-ct|" + public_key + eph).digest()
        ss = hashlib.sha256(b"toy-kem-ss|" + public_key + eph).digest()
        return ct, ss

    def decaps(self, secret_key: bytes, ciphertext: bytes) -> bytes:
        """Decaps for the toy KEM is asymmetric with encaps (test double limit).

        For unit tests we store eph recovery material in ciphertext when using
        ``encaps_with_recoverable_ct``; standard encaps is one-way by design of
        this toy. Prefer ``roundtrip_shared`` for tests.
        """
        if len(secret_key) != self.sk_len:
            raise ValueError("bad toy kem secret key length")
        if len(ciphertext) == 64:
            # recoverable: ct || eph
            eph = ciphertext[32:]
            pk = hashlib.sha256(b"toy-kem-pk|" + secret_key).digest()
            return hashlib.sha256(b"toy-kem-ss|" + pk + eph).digest()
        raise ValueError(
            "toy decaps requires recoverable ciphertext (use encaps_recoverable)"
        )

    def encaps_recoverable(self, public_key: bytes) -> Tuple[bytes, bytes]:
        """Encaps that embeds eph for toy decaps round-trip (tests only)."""
        if len(public_key) != self.pk_len:
            raise ValueError("bad toy kem public key length")
        eph = os.urandom(32)
        ct_core = hashlib.sha256(b"toy-kem-ct|" + public_key + eph).digest()
        ss = hashlib.sha256(b"toy-kem-ss|" + public_key + eph).digest()
        return ct_core + eph, ss


def hybrid_session_ikm(
    classical_ikm: bytes,
    kem_shared: bytes,
    *,
    label: bytes = b"rpt-pq-hybrid-v1",
) -> bytes:
    """Mix classical PFS IKM with KEM shared secret into session IKM.

    Both parties must use the same classical_ikm and kem_shared.
    """
    if len(classical_ikm) < 16:
        raise ValueError("classical IKM too short")
    if len(kem_shared) < 16:
        raise ValueError("KEM shared secret too short")
    return hashlib.sha256(
        classical_ikm + b"|" + label + b"|" + kem_shared
    ).digest()


def hybrid_ikm_from_kem(
    classical_ikm: bytes,
    kem: Kem,
    peer_public_key: bytes,
    *,
    recoverable_toy: bool = False,
) -> Tuple[bytes, bytes, bytes]:
    """Encaps to peer and return (hybrid_ikm, kem_ct, kem_ss)."""
    if recoverable_toy and isinstance(kem, ToyKyberClassKem):
        ct, ss = kem.encaps_recoverable(peer_public_key)
    else:
        ct, ss = kem.encaps(peer_public_key)
    return hybrid_session_ikm(classical_ikm, ss), ct, ss


def default_kem() -> ToyKyberClassKem:
    """Default staged KEM (toy). Replace with real ML-KEM for production PQ."""
    return ToyKyberClassKem()
