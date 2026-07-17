"""Session AEAD keys derived after ElGamal+Pedersen handshake."""

from __future__ import annotations

import os
from dataclasses import dataclass

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives.kdf.hkdf import HKDF


def derive_session_key(shared_secret: bytes, salt: bytes, info: bytes = b"rpt-v2-session") -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=salt, info=info).derive(shared_secret)


@dataclass
class SessionCrypto:
    key: bytes

    def seal(self, plaintext: bytes, aad: bytes = b"") -> tuple[bytes, bytes]:
        nonce = os.urandom(12)
        ct = ChaCha20Poly1305(self.key).encrypt(nonce, plaintext, aad)
        return nonce, ct

    def open(self, nonce: bytes, ciphertext: bytes, aad: bytes = b"") -> bytes:
        return ChaCha20Poly1305(self.key).decrypt(nonce, ciphertext, aad)
