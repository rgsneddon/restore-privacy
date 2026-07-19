"""Padding, timing jitter, and cover traffic — shipped traffic_shape + SessionCrypto."""

from __future__ import annotations

import random
import struct
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

from node.crypto_session import CoverFrame, SessionCrypto  # noqa: E402
from node.protocol import pack_data, parse_data  # noqa: E402
from node.traffic_shape import (  # noqa: E402
    COVER_MAGIC,
    PAD_MAGIC,
    TrafficShapePolicy,
    apply_send_jitter,
    interpret_inbound_plaintext,
    jitter_delay_seconds,
    make_cover_payload,
    pad_payload,
    prepare_outbound_plaintext,
    unpad_payload,
)


class TestPadUnpad(unittest.TestCase):
    def test_roundtrip_various_sizes(self):
        for size in (0, 1, 20, 40, 100, 1500):
            plain = bytes((i * 7) % 256 for i in range(size))
            wrapped = pad_payload(plain, bucket=64)
            self.assertTrue(wrapped.startswith(PAD_MAGIC))
            out, is_cover = unpad_payload(wrapped)
            self.assertFalse(is_cover)
            self.assertEqual(out, plain)

    def test_padded_length_is_bucket_aligned(self):
        plain = b"x" * 50
        wrapped = pad_payload(plain, bucket=128)
        # body after magic is multiple of 128
        self.assertEqual((len(wrapped) - len(PAD_MAGIC)) % 128, 0)
        self.assertGreater(len(wrapped), len(plain))

    def test_unmarked_blob_compat(self):
        raw_ip = b"\x45" + b"\x00" * 19
        out, is_cover = unpad_payload(raw_ip)
        self.assertEqual(out, raw_ip)
        self.assertFalse(is_cover)


class TestCoverFrames(unittest.TestCase):
    def test_cover_payload_marked(self):
        c = make_cover_payload(96)
        self.assertTrue(c.startswith(COVER_MAGIC))
        out, is_cover = unpad_payload(c)
        self.assertTrue(is_cover)
        self.assertEqual(out, b"")

    def test_session_crypto_seal_open_with_padding(self):
        key = b"k" * 32
        pol = TrafficShapePolicy(padding=True, pad_bucket=64)
        crypto = SessionCrypto(key=key, traffic_shape=pol)
        ip = b"\x45" + b"\x11" * 40
        aad = b"sid" + struct.pack("!Q", 1)
        nonce, sealed = crypto.seal(ip, aad=aad)
        # ciphertext longer than plain when padded
        self.assertGreater(len(sealed), len(ip))
        opened = crypto.open(nonce, sealed, aad=aad)
        self.assertEqual(opened, ip)

    def test_cover_seal_open_allow(self):
        key = b"c" * 32
        crypto = SessionCrypto(key=key)
        aad = b"s" * 8 + struct.pack("!Q", 2)
        nonce, sealed = crypto.seal_cover(80, aad=aad)
        plain, is_cover = crypto.open_allow_cover(nonce, sealed, aad=aad)
        self.assertTrue(is_cover)
        self.assertIsNone(plain)
        with self.assertRaises(CoverFrame):
            crypto.open(nonce, sealed, aad=aad)

    def test_cover_does_not_corrupt_following_real_data(self):
        key = b"z" * 32
        crypto = SessionCrypto(
            key=key, traffic_shape=TrafficShapePolicy(padding=True, pad_bucket=32)
        )
        aad1 = b"AAAAAAAA" + struct.pack("!Q", 1)
        aad2 = b"AAAAAAAA" + struct.pack("!Q", 2)
        n1, s1 = crypto.seal_cover(48, aad=aad1)
        real = b"\x45REALPACKETDATA!!"
        n2, s2 = crypto.seal(real, aad=aad2)
        p1, c1 = crypto.open_allow_cover(n1, s1, aad=aad1)
        self.assertTrue(c1)
        p2, c2 = crypto.open_allow_cover(n2, s2, aad=aad2)
        self.assertFalse(c2)
        self.assertEqual(p2, real)


class TestTimingJitter(unittest.TestCase):
    def test_zero_when_disabled(self):
        self.assertEqual(jitter_delay_seconds(0), 0.0)
        self.assertEqual(jitter_delay_seconds(-5), 0.0)

    def test_bounds(self):
        rng = random.Random(42)
        for _ in range(50):
            d = jitter_delay_seconds(100, rng=rng)
            self.assertGreaterEqual(d, 0.0)
            self.assertLessEqual(d, 0.1000001)

    def test_nonzero_variance_when_enabled(self):
        rng = random.Random(7)
        samples = [jitter_delay_seconds(50, rng=rng) for _ in range(40)]
        self.assertTrue(any(s > 0 for s in samples))
        self.assertGreater(len(set(round(s, 4) for s in samples)), 1)

    def test_apply_send_jitter_calls_sleep(self):
        slept: list[float] = []
        rng = random.Random(1)
        apply_send_jitter(20, sleep=slept.append, rng=rng)
        self.assertEqual(len(slept), 1)
        self.assertGreaterEqual(slept[0], 0.0)
        self.assertLessEqual(slept[0], 0.02)

    def test_apply_send_jitter_off(self):
        slept: list[float] = []
        d = apply_send_jitter(0, sleep=slept.append)
        self.assertEqual(d, 0.0)
        self.assertEqual(slept, [])


class TestPrepareInterpret(unittest.TestCase):
    def test_policy_off_passthrough(self):
        pol = TrafficShapePolicy(padding=False)
        raw = b"\x45abc"
        self.assertEqual(prepare_outbound_plaintext(raw, pol), raw)
        p, c = interpret_inbound_plaintext(raw)
        self.assertEqual(p, raw)
        self.assertFalse(c)


if __name__ == "__main__":
    unittest.main()
