"""RPT wire protocol frames (custom; not WireGuard/OpenVPN)."""

from __future__ import annotations

import struct
from enum import IntEnum
from typing import Optional

MAGIC = b"RPT2"
HEADER_LEN = 5


class MsgType(IntEnum):
    CLIENT_HELLO = 0x01
    SERVER_HELLO = 0x02
    DATA = 0x03
    KEEPALIVE = 0x04


class ProtocolError(ValueError):
    pass


def pack_client_hello(
    client_ed25519_pub: bytes,
    pedersen_commit: bytes,
    hybrid_blob: bytes,
    signature: bytes,
) -> bytes:
    if len(client_ed25519_pub) != 32:
        raise ProtocolError("client pub must be 32 bytes")
    if len(pedersen_commit) != 256:
        raise ProtocolError("commitment must be 256 bytes")
    if len(hybrid_blob) < 512 + 12 + 16:
        raise ProtocolError("hybrid blob too short")
    if len(signature) != 64:
        raise ProtocolError("signature must be 64 bytes")
    # u32 length-prefixed hybrid blob
    return (
        MAGIC
        + bytes([MsgType.CLIENT_HELLO])
        + client_ed25519_pub
        + pedersen_commit
        + struct.pack("!I", len(hybrid_blob))
        + hybrid_blob
        + signature
    )


def parse_client_hello(data: bytes) -> tuple[bytes, bytes, bytes, bytes]:
    if len(data) < HEADER_LEN + 32 + 256 + 4 + 64 or data[:4] != MAGIC or data[4] != MsgType.CLIENT_HELLO:
        raise ProtocolError("bad CLIENT_HELLO")
    body = data[HEADER_LEN:]
    client_pub = body[:32]
    commit = body[32:288]
    (hlen,) = struct.unpack("!I", body[288:292])
    if hlen < 512 + 12 + 16 or len(body) < 292 + hlen + 64:
        raise ProtocolError("bad hybrid length")
    hybrid = body[292 : 292 + hlen]
    sig = body[292 + hlen : 292 + hlen + 64]
    return client_pub, commit, hybrid, sig


def pack_server_hello(
    pedersen_commit: bytes,
    session_id: bytes,
    nonce: bytes,
    sealed: bytes,
) -> bytes:
    if len(pedersen_commit) != 256 or len(session_id) != 8 or len(nonce) != 12:
        raise ProtocolError("bad SERVER_HELLO field lengths")
    return MAGIC + bytes([MsgType.SERVER_HELLO]) + pedersen_commit + session_id + nonce + sealed


def parse_server_hello(data: bytes) -> tuple[bytes, bytes, bytes, bytes]:
    if len(data) < HEADER_LEN + 256 + 8 + 12 + 16 or data[:4] != MAGIC or data[4] != MsgType.SERVER_HELLO:
        raise ProtocolError("bad SERVER_HELLO")
    body = data[HEADER_LEN:]
    return body[:256], body[256:264], body[264:276], body[276:]


def pack_data(session_id: bytes, counter: int, nonce: bytes, sealed: bytes) -> bytes:
    return MAGIC + bytes([MsgType.DATA]) + session_id + struct.pack("!Q", counter) + nonce + sealed


def parse_data(data: bytes) -> tuple[bytes, int, bytes, bytes]:
    if len(data) < HEADER_LEN + 8 + 8 + 12 + 16 or data[:4] != MAGIC or data[4] != MsgType.DATA:
        raise ProtocolError("bad DATA")
    body = data[HEADER_LEN:]
    return body[:8], struct.unpack("!Q", body[8:16])[0], body[16:28], body[28:]


def pack_keepalive(session_id: bytes) -> bytes:
    return MAGIC + bytes([MsgType.KEEPALIVE]) + session_id


def parse_keepalive(data: bytes) -> bytes:
    if len(data) < HEADER_LEN + 8 or data[:4] != MAGIC or data[4] != MsgType.KEEPALIVE:
        raise ProtocolError("bad KEEPALIVE")
    return data[HEADER_LEN : HEADER_LEN + 8]


def peek_type(data: bytes) -> Optional[MsgType]:
    if len(data) < HEADER_LEN or data[:4] != MAGIC:
        return None
    try:
        return MsgType(data[4])
    except ValueError:
        return None
