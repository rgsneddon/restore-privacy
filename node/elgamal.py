"""ElGamal public-key encryption over RFC 3526 2048-bit MODP group."""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass

P = int(
    "FFFFFFFFFFFFFFFFC90FDAA22168C234C4C6628B80DC1CD1"
    "29024E088A67CC74020BBEA63B139B22514A08798E3404DD"
    "EF9519B3CD3A431B302B0A6DF25F14374FE1356D6D51C245"
    "E485B576625E7EC6F44C42E9A637ED6B0BFF5CB6F406B7ED"
    "EE386BFB5A899FA5AE9F24117C4B1FE649286651ECE45B3D"
    "C2007CB8A163BF0598DA48361C55D39A69163FA8FD24CF5F"
    "83655D23DCA3AD961C62F356208552BB9ED529077096966D"
    "670C354E4ABC9804F1746C08CA18217C32905E462E36CE3B"
    "E39E772C180E86039B2783A2EC07A28FB5C55DF06F4C52C9"
    "DE2BCBF6955817183995497CEA956AE515D2261898FA0510"
    "15728E5A8AACAA68FFFFFFFFFFFFFFFF",
    16,
)
G = 2
Q = (P - 1) // 2


def _mod_pow(base: int, exp: int, mod: int = P) -> int:
    return pow(base, exp, mod)


def _rand_exponent() -> int:
    while True:
        raw = int.from_bytes(os.urandom(256), "big") % Q
        if 1 <= raw < Q:
            return raw


def int_to_bytes(value: int, length: int = 256) -> bytes:
    return value.to_bytes(length, "big")


def bytes_to_int(data: bytes) -> int:
    return int.from_bytes(data, "big")


def encode_message(plaintext: bytes) -> int:
    if len(plaintext) > 240:
        raise ValueError("plaintext too long for ElGamal message encoding")
    blob = bytes([len(plaintext)]) + plaintext + os.urandom(16)
    m = bytes_to_int(blob)
    if m >= P:
        raise ValueError("encoded message out of range")
    return m


def decode_message(m: int) -> bytes:
    compact = m.to_bytes((m.bit_length() + 7) // 8 or 1, "big")
    if not compact:
        raise ValueError("empty message")
    L = compact[0]
    if L > 240 or len(compact) < 1 + L:
        compact = int_to_bytes(m, 256).lstrip(b"\x00")
        if not compact:
            raise ValueError("empty message")
        L = compact[0]
        if len(compact) < 1 + L:
            raise ValueError("truncated message")
    return compact[1 : 1 + L]


@dataclass(frozen=True)
class ElGamalPublicKey:
    y: int

    def export(self) -> bytes:
        return int_to_bytes(self.y, 256)

    @staticmethod
    def import_bytes(data: bytes) -> "ElGamalPublicKey":
        if len(data) != 256:
            raise ValueError("ElGamal public key must be 256 bytes")
        y = bytes_to_int(data)
        if not (1 < y < P):
            raise ValueError("invalid public key")
        return ElGamalPublicKey(y=y)


@dataclass(frozen=True)
class ElGamalPrivateKey:
    x: int
    public: ElGamalPublicKey

    def export(self) -> bytes:
        return int_to_bytes(self.x, 256)

    @staticmethod
    def import_bytes(data: bytes) -> "ElGamalPrivateKey":
        if len(data) != 256:
            raise ValueError("ElGamal private key must be 256 bytes")
        x = bytes_to_int(data)
        if not (1 <= x < Q):
            raise ValueError("invalid private exponent")
        y = _mod_pow(G, x)
        return ElGamalPrivateKey(x=x, public=ElGamalPublicKey(y=y))


def generate_keypair() -> ElGamalPrivateKey:
    x = _rand_exponent()
    y = _mod_pow(G, x)
    return ElGamalPrivateKey(x=x, public=ElGamalPublicKey(y=y))


@dataclass(frozen=True)
class ElGamalCiphertext:
    c1: int
    c2: int

    def export(self) -> bytes:
        return int_to_bytes(self.c1, 256) + int_to_bytes(self.c2, 256)

    @staticmethod
    def import_bytes(data: bytes) -> "ElGamalCiphertext":
        if len(data) != 512:
            raise ValueError("ciphertext must be 512 bytes")
        return ElGamalCiphertext(c1=bytes_to_int(data[:256]), c2=bytes_to_int(data[256:]))


def encrypt(public: ElGamalPublicKey, plaintext: bytes) -> ElGamalCiphertext:
    m = encode_message(plaintext)
    k = _rand_exponent()
    c1 = _mod_pow(G, k)
    c2 = (m * _mod_pow(public.y, k)) % P
    return ElGamalCiphertext(c1=c1, c2=c2)


def decrypt(private: ElGamalPrivateKey, ct: ElGamalCiphertext) -> bytes:
    s = _mod_pow(ct.c1, private.x)
    s_inv = pow(s, -1, P)
    m = (ct.c2 * s_inv) % P
    return decode_message(m)


def fingerprint_public(public: ElGamalPublicKey) -> str:
    return hashlib.sha256(public.export()).hexdigest()[:16]
