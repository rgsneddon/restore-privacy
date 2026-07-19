"""Perfect forward secrecy helpers: ephemeral X25519 for session AEAD keys.

Long-term ElGamal + Ed25519 remain for **admission/authentication** only.
Session traffic keys are derived from an ephemeral X25519 shared secret mixed
into the handshake transcript so compromise of long-term keys after the session
ends cannot reconstruct that session's AEAD key from the transcript alone.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from cryptography.hazmat.primitives.asymmetric.x25519 import (
    X25519PrivateKey,
    X25519PublicKey,
)

from .crypto_session import SessionCrypto, derive_session_key

EPH_PUB_LEN = 32
# Marker: SERVER_HELLO plain includes server X25519 pub after vpn IP when PFS active.
PFS_WIRE_VERSION = 1


@dataclass
class EphemeralX25519:
    private: X25519PrivateKey
    public_raw: bytes

    @staticmethod
    def generate() -> "EphemeralX25519":
        priv = X25519PrivateKey.generate()
        pub = priv.public_key().public_bytes_raw()
        return EphemeralX25519(private=priv, public_raw=pub)


def x25519_shared_secret(private: X25519PrivateKey, peer_public_raw: bytes) -> bytes:
    if len(peer_public_raw) != EPH_PUB_LEN:
        raise ValueError("X25519 public key must be 32 bytes")
    peer = X25519PublicKey.from_public_bytes(peer_public_raw)
    return private.exchange(peer)


def derive_pfs_session_shared(
    client_nonce: bytes,
    server_nonce: bytes,
    session_id: bytes,
    client_pub: bytes,
    eph_shared: bytes,
) -> bytes:
    """Session IKM including ephemeral DH (PFS)."""
    if len(eph_shared) < 16:
        raise ValueError("ephemeral shared secret too short")
    return hashlib.sha256(
        client_nonce
        + server_nonce
        + session_id
        + client_pub
        + b"|pfs-x25519|"
        + eph_shared
    ).digest()


def derive_legacy_session_shared(
    client_nonce: bytes,
    server_nonce: bytes,
    session_id: bytes,
    client_pub: bytes,
) -> bytes:
    """Pre-PFS derivation (nonces only) — kept for analysis tests, not preferred."""
    return hashlib.sha256(client_nonce + server_nonce + session_id + client_pub).digest()


def session_crypto_from_shared(
    session_shared: bytes,
    client_nonce: bytes,
) -> SessionCrypto:
    key = derive_session_key(
        session_shared, salt=client_nonce[:16], info=b"rpt-v2-session"
    )
    return SessionCrypto(key=key)


def long_term_only_cannot_recover_pfs_key(
    *,
    client_nonce: bytes,
    server_nonce: bytes,
    session_id: bytes,
    client_pub: bytes,
    real_session_key: bytes,
) -> bool:
    """True when deriving with only long-term-visible transcript material fails.

    Attacker model: sees nonces, session_id, client_pub on the wire / in memory
    dumps of static state, but **not** the ephemeral X25519 private keys.
    """
    legacy = derive_legacy_session_shared(
        client_nonce, server_nonce, session_id, client_pub
    )
    guess = derive_session_key(legacy, salt=client_nonce[:16], info=b"rpt-v2-session")
    return guess != real_session_key
