"""Pedersen commitments over the same MODP group as ElGamal."""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass

from .elgamal import G, P, Q, bytes_to_int, int_to_bytes, _mod_pow


def _derive_h() -> int:
    digest = hashlib.sha256(b"rpt-pedersen-h-v1" + int_to_bytes(G, 256)).digest()
    acc = digest
    while len(acc) < 256:
        acc += hashlib.sha256(acc).digest()
    x = bytes_to_int(acc[:256]) % P
    if x <= 1:
        x = 3
    h = _mod_pow(x, 2)
    if h <= 1:
        h = _mod_pow(x + 2, 2)
    return h


H = _derive_h()


def _rand_blinding() -> int:
    while True:
        r = int.from_bytes(os.urandom(256), "big") % Q
        if 1 <= r < Q:
            return r


@dataclass(frozen=True)
class PedersenCommitment:
    c: int

    def export(self) -> bytes:
        return int_to_bytes(self.c, 256)

    @staticmethod
    def import_bytes(data: bytes) -> "PedersenCommitment":
        if len(data) != 256:
            raise ValueError("commitment must be 256 bytes")
        c = bytes_to_int(data)
        if not (0 < c < P):
            raise ValueError("invalid commitment")
        return PedersenCommitment(c=c)


@dataclass(frozen=True)
class PedersenOpening:
    message: int
    blinding: int

    def export(self) -> bytes:
        return int_to_bytes(self.message % Q, 32) + int_to_bytes(self.blinding, 256)

    @staticmethod
    def import_bytes(data: bytes) -> "PedersenOpening":
        if len(data) != 32 + 256:
            raise ValueError("opening must be 288 bytes")
        return PedersenOpening(message=bytes_to_int(data[:32]) % Q, blinding=bytes_to_int(data[32:]))


def commit(message: int, blinding: int | None = None) -> tuple[PedersenCommitment, PedersenOpening]:
    m = message % Q
    r = blinding if blinding is not None else _rand_blinding()
    if not (0 <= r < Q):
        raise ValueError("blinding out of range")
    c = (_mod_pow(G, m) * _mod_pow(H, r)) % P
    return PedersenCommitment(c=c), PedersenOpening(message=m, blinding=r)


def commit_bytes(payload: bytes, blinding: int | None = None) -> tuple[PedersenCommitment, PedersenOpening]:
    m = bytes_to_int(hashlib.sha256(payload).digest()) % Q
    return commit(m, blinding=blinding)


def verify(commitment: PedersenCommitment, opening: PedersenOpening) -> bool:
    expected = (_mod_pow(G, opening.message % Q) * _mod_pow(H, opening.blinding % Q)) % P
    return expected == commitment.c


def open_verified(commitment: PedersenCommitment, opening: PedersenOpening) -> int:
    if not verify(commitment, opening):
        raise ValueError("Pedersen opening does not match commitment")
    return opening.message
