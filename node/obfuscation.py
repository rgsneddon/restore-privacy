"""Layer obfuscation: QUIC-mimic outer wrapper around RPT frames.

Product wire is no longer bare ``RPT2`` UDP alone. Outer packets use a long-header
shape similar to QUIC Initial (first-nibble high bits, version field, DCID/SCID
lengths, variable payload) so passive classifiers see generic UDP crypto traffic
rather than the clear ``RPT2`` magic.

This is a **mitigation**, not a claim of DPI-undetectability or full pluggable
transport parity with obfs4/meek/V2Ray.

Wire (outer):
  [1] flags_byte     — 0xC0 | (rand & 0x0F)  (QUIC long-header style)
  [4] version        — little product constant (looks like QUIC version)
  [1] dcid_len       — 8
  [8] dcid           — random
  [1] scid_len       — 0
  [2] payload_len    — u16 BE of sealed body
  [12] nonce         — random
  [N] body           — XOR stream of inner RPT frame (ChaCha20-Poly not required;
                       stream XOR with product key + nonce is enough for outer
                       opacity; AEAD remains on RPT DATA)

Bare ``RPT2`` still accepted on unwrap for one release of compatibility when
``allow_bare`` is True (node default True, product client wraps by default).
"""

from __future__ import annotations

import os
import struct
from typing import Optional

from node.protocol import MAGIC as RPT_MAGIC

# QUIC-mimic "version" constant (not a real IETF QUIC version).
OBFS_VERSION = 0x52505431  # 'RPT1' as u32
# Product outer key material (public obfuscation key — not authentication).
# Authentication remains RPT handshake + AEAD. This only hides clear RPT2 magic.
_PRODUCT_OBFS_KEY = (
    b"RPT-OBFS-LAYER-v1\x00\x00\x00\x00\x00\x00\x00\x00"
    b"\x9a\x3c\x7e\x11\xd4\x55\x88\x02"
)  # 33 bytes: 17 prefix + 8 NUL + 8 tail


class ObfuscationError(ValueError):
    pass


def product_obfuscation_enabled(env: Optional[dict] = None) -> bool:
    """True when product clients/nodes should wrap UDP frames (default on)."""
    e = env if env is not None else os.environ
    raw = str(e.get("RPT_OBFS", "1")).strip().lower()
    if raw in ("0", "false", "off", "no", "disabled"):
        return False
    return True


def _stream_mask(nonce: bytes, length: int, key: bytes = _PRODUCT_OBFS_KEY) -> bytes:
    """Deterministic mask from key+nonce (expand with repeated SHA-like mix).

    Uses only stdlib: hashlib for expansion (no extra deps).
    """
    import hashlib

    out = bytearray()
    counter = 0
    while len(out) < length:
        h = hashlib.sha256(key + nonce + struct.pack("!I", counter)).digest()
        out.extend(h)
        counter += 1
    return bytes(out[:length])


def xor_bytes(data: bytes, mask: bytes) -> bytes:
    if len(mask) < len(data):
        raise ObfuscationError("mask too short")
    return bytes(a ^ b for a, b in zip(data, mask))


def wrap_frame(
    inner: bytes,
    *,
    rng: Optional[callable] = None,
    key: bytes = _PRODUCT_OBFS_KEY,
) -> bytes:
    """Wrap an RPT (or any) frame in the QUIC-mimic outer layer."""
    if not inner:
        raise ObfuscationError("empty inner frame")
    rand = rng or os.urandom
    flags = 0xC0 | (rand(1)[0] & 0x0F)
    dcid = rand(8)
    nonce = rand(12)
    mask = _stream_mask(nonce, len(inner), key=key)
    body = xor_bytes(inner, mask)
    if len(body) > 0xFFFF:
        raise ObfuscationError("inner frame too large for u16 length")
    return (
        bytes([flags])
        + struct.pack("!I", OBFS_VERSION)
        + bytes([8])
        + dcid
        + bytes([0])  # scid_len
        + struct.pack("!H", len(body))
        + nonce
        + body
    )


def looks_like_obfs(data: bytes) -> bool:
    if len(data) < 1 + 4 + 1 + 8 + 1 + 2 + 12:
        return False
    # High bits of first byte set like QUIC long header; version matches product
    if (data[0] & 0xC0) != 0xC0:
        return False
    (ver,) = struct.unpack("!I", data[1:5])
    return ver == OBFS_VERSION


def looks_like_bare_rpt(data: bytes) -> bool:
    return len(data) >= 5 and data[:4] == RPT_MAGIC


def unwrap_frame(
    outer: bytes,
    *,
    allow_bare: bool = True,
    key: bytes = _PRODUCT_OBFS_KEY,
) -> bytes:
    """Unwrap outer layer to inner RPT frame.

    If ``allow_bare`` and packet is clear ``RPT2``, return as-is (compat).
    """
    if allow_bare and looks_like_bare_rpt(outer):
        return outer
    if not looks_like_obfs(outer):
        raise ObfuscationError("not an RPT obfuscated frame")
    # Parse header
    # flags(1) version(4) dcid_len(1) dcid(8) scid_len(1) len(2) nonce(12) body
    o = 0
    o += 1  # flags
    o += 4  # version already checked
    dcid_len = outer[o]
    o += 1
    if dcid_len != 8:
        raise ObfuscationError("unexpected dcid_len")
    o += dcid_len
    scid_len = outer[o]
    o += 1
    if scid_len != 0:
        # tolerate small scid but skip
        o += scid_len
    if o + 2 + 12 > len(outer):
        raise ObfuscationError("truncated outer")
    (plen,) = struct.unpack("!H", outer[o : o + 2])
    o += 2
    nonce = outer[o : o + 12]
    o += 12
    body = outer[o : o + plen]
    if len(body) != plen:
        raise ObfuscationError("truncated body")
    mask = _stream_mask(nonce, plen, key=key)
    return xor_bytes(body, mask)


def maybe_wrap(inner: bytes, *, enabled: bool | None = None) -> bytes:
    """Wrap when product obfuscation is enabled; otherwise return bare."""
    if enabled is None:
        enabled = product_obfuscation_enabled()
    if not enabled:
        return inner
    return wrap_frame(inner)


def maybe_unwrap(outer: bytes, *, enabled: bool | None = None) -> bytes:
    """Unwrap when enabled; always accept bare RPT2 for compatibility."""
    if enabled is None:
        enabled = product_obfuscation_enabled()
    # When disabled, still accept either form if peer still wraps
    try:
        return unwrap_frame(outer, allow_bare=True)
    except ObfuscationError:
        if not enabled and looks_like_bare_rpt(outer):
            return outer
        raise
