"""Traffic-shape helpers: padding, timing jitter, optional cover frames.

Used on the RPT DATA seal/open path to resist coarse traffic analysis / DPI
size and timing fingerprints. These are mitigations, not undetectability guarantees.

Defaults keep features off for connectivity and bandwidth; enable via policy.
"""

from __future__ import annotations

import os
import random
import struct
import time
from dataclasses import dataclass
from typing import Callable

# Prefixed payload formats (inside AEAD plaintext):
#   Real padded:  RPTP || u16_be(len) || plain || random_pad
#   Cover dummy:  RPTC || random_bytes
PAD_MAGIC = b"RPTP"
COVER_MAGIC = b"RPTC"
_MIN_PAD_BUCKET = 16
_MAX_PAD_BUCKET = 2048
_MAX_JITTER_MS = 500


@dataclass(frozen=True)
class TrafficShapePolicy:
    """Feature flags for DATA path hardening (privacy-safe defaults: all off)."""

    padding: bool = False
    # Pad plaintext to the next multiple of this size (after header).
    pad_bucket: int = 128
    # Max milliseconds of send-side delay before outbound UDP send (0 = off).
    jitter_ms_max: int = 0
    # Inject sealed dummy frames that peers discard after open.
    cover_traffic: bool = False
    # Target interval between cover frames when cover_traffic is on (0 = no auto).
    cover_interval_s: float = 0.0

    def __post_init__(self) -> None:
        # frozen dataclass: use object.__setattr__ for validation normalize
        bucket = int(self.pad_bucket)
        if bucket < _MIN_PAD_BUCKET:
            bucket = _MIN_PAD_BUCKET
        if bucket > _MAX_PAD_BUCKET:
            bucket = _MAX_PAD_BUCKET
        object.__setattr__(self, "pad_bucket", bucket)
        j = int(self.jitter_ms_max)
        if j < 0:
            j = 0
        if j > _MAX_JITTER_MS:
            j = _MAX_JITTER_MS
        object.__setattr__(self, "jitter_ms_max", j)


DEFAULT_TRAFFIC_SHAPE = TrafficShapePolicy()


def pad_payload(
    plain: bytes,
    *,
    bucket: int = 128,
    rng: Callable[[int], bytes] | None = None,
) -> bytes:
    """Wrap *plain* with length prefix and pad to a multiple of *bucket*.

    Layout: RPTP || u16_be(len(plain)) || plain || random_pad
    """
    if rng is None:
        rng = os.urandom
    if not (0 <= len(plain) <= 65535):
        raise ValueError("plain too large for u16 length prefix")
    b = max(_MIN_PAD_BUCKET, min(_MAX_PAD_BUCKET, int(bucket)))
    body = struct.pack("!H", len(plain)) + plain
    # total after magic should be multiple of bucket
    total_body = len(body)
    pad_len = (b - (total_body % b)) % b
    # Always add at least some entropy pad when plain is non-empty? Prefer
    # exact multiple only; empty plain still gets header alignment.
    return PAD_MAGIC + body + rng(pad_len)


def make_cover_payload(
    size: int = 128,
    *,
    rng: Callable[[int], bytes] | None = None,
) -> bytes:
    """Build a cover (dummy) plaintext discarded after open."""
    if rng is None:
        rng = os.urandom
    n = max(16, min(2048, int(size)))
    # Cover body is pure noise after magic (no real IP).
    return COVER_MAGIC + rng(n - len(COVER_MAGIC))


def unpad_payload(blob: bytes) -> tuple[bytes, bool]:
    """Strip pad/cover framing.

    Returns ``(payload, is_cover)``. Cover payloads return empty payload and
    ``is_cover=True``. Unmarked blobs are treated as raw IP (compat / padding off).
    """
    if blob.startswith(COVER_MAGIC):
        return b"", True
    if not blob.startswith(PAD_MAGIC):
        return blob, False
    rest = blob[len(PAD_MAGIC) :]
    if len(rest) < 2:
        raise ValueError("truncated padded payload")
    (n,) = struct.unpack("!H", rest[:2])
    if len(rest) < 2 + n:
        raise ValueError("padded payload length exceeds buffer")
    return rest[2 : 2 + n], False


def jitter_delay_seconds(
    max_ms: int,
    *,
    rng: random.Random | None = None,
) -> float:
    """Bounded uniform send-side delay in seconds. 0 when max_ms <= 0."""
    m = int(max_ms)
    if m <= 0:
        return 0.0
    m = min(m, _MAX_JITTER_MS)
    r = rng if rng is not None else random.Random()
    # Inclusive 0..max_ms
    return r.randint(0, m) / 1000.0


def apply_send_jitter(
    max_ms: int,
    *,
    sleep: Callable[[float], None] = time.sleep,
    rng: random.Random | None = None,
) -> float:
    """Sleep a bounded random time; return the delay applied (seconds)."""
    delay = jitter_delay_seconds(max_ms, rng=rng)
    if delay > 0:
        sleep(delay)
    return delay


def prepare_outbound_plaintext(
    ip_packet: bytes,
    policy: TrafficShapePolicy,
    *,
    rng: Callable[[int], bytes] | None = None,
) -> bytes:
    """Apply padding policy to a real IP packet before AEAD seal."""
    if policy.padding:
        return pad_payload(ip_packet, bucket=policy.pad_bucket, rng=rng)
    return ip_packet


def interpret_inbound_plaintext(blob: bytes) -> tuple[bytes | None, bool]:
    """After AEAD open: return (ip_packet_or_None, is_cover).

    Cover → (None, True). Real (possibly unpadded) → (packet, False).
    """
    plain, is_cover = unpad_payload(blob)
    if is_cover:
        return None, True
    return plain, False
