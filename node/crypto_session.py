"""Session AEAD keys derived after ElGamal+Pedersen handshake."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from .traffic_shape import (
    DEFAULT_TRAFFIC_SHAPE,
    TrafficShapePolicy,
    interpret_inbound_plaintext,
    prepare_outbound_plaintext,
)


def derive_session_key(shared_secret: bytes, salt: bytes, info: bytes = b"rpt-v2-session") -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=salt, info=info).derive(shared_secret)


@dataclass
class SessionCrypto:
    key: bytes
    # Optional traffic shaping applied around AEAD (defaults: off).
    traffic_shape: TrafficShapePolicy = field(default_factory=lambda: DEFAULT_TRAFFIC_SHAPE)

    def seal(self, plaintext: bytes, aad: bytes = b"") -> tuple[bytes, bytes]:
        """Seal plaintext (optionally padded) with ChaCha20-Poly1305."""
        body = prepare_outbound_plaintext(plaintext, self.traffic_shape)
        nonce = os.urandom(12)
        ct = ChaCha20Poly1305(self.key).encrypt(nonce, body, aad)
        return nonce, ct

    def seal_cover(self, size: int = 128, aad: bytes = b"") -> tuple[bytes, bytes]:
        """Seal a cover (dummy) payload — open returns is_cover."""
        from .traffic_shape import make_cover_payload

        body = make_cover_payload(size)
        nonce = os.urandom(12)
        ct = ChaCha20Poly1305(self.key).encrypt(nonce, body, aad)
        return nonce, ct

    def open(self, nonce: bytes, ciphertext: bytes, aad: bytes = b"") -> bytes:
        """Decrypt; strip padding. Raises ValueError if cover frame (caller should drop)."""
        raw = ChaCha20Poly1305(self.key).decrypt(nonce, ciphertext, aad)
        plain, is_cover = interpret_inbound_plaintext(raw)
        if is_cover:
            raise CoverFrame("cover traffic frame")
        assert plain is not None
        return plain

    def open_allow_cover(
        self, nonce: bytes, ciphertext: bytes, aad: bytes = b""
    ) -> tuple[bytes | None, bool]:
        """Decrypt; return (ip_or_None, is_cover) without raising on cover."""
        raw = ChaCha20Poly1305(self.key).decrypt(nonce, ciphertext, aad)
        return interpret_inbound_plaintext(raw)


class CoverFrame(Exception):
    """Opened AEAD plaintext is cover traffic — discard, do not write to TUN."""
