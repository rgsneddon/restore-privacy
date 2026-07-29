"""Layer obfuscation: QUIC-mimic wrap/unwrap + product wiring."""

from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from node.obfuscation import (  # noqa: E402
    OBFS_VERSION,
    looks_like_bare_rpt,
    looks_like_obfs,
    maybe_unwrap,
    maybe_wrap,
    product_obfuscation_enabled,
    unwrap_frame,
    wrap_frame,
)
from node.protocol import MAGIC, MsgType, pack_keepalive  # noqa: E402


class TestObfuscationCodec(unittest.TestCase):
    def test_wrap_differs_from_bare_and_roundtrips(self):
        inner = MAGIC + bytes([MsgType.KEEPALIVE]) + b"\xab" * 8
        outer = wrap_frame(inner)
        self.assertNotEqual(outer, inner)
        self.assertFalse(looks_like_bare_rpt(outer))
        self.assertTrue(looks_like_obfs(outer))
        self.assertNotEqual(outer[:4], MAGIC)
        # QUIC-like first nibble
        self.assertEqual(outer[0] & 0xC0, 0xC0)
        (ver,) = struct.unpack("!I", outer[1:5])
        self.assertEqual(ver, OBFS_VERSION)
        back = unwrap_frame(outer)
        self.assertEqual(back, inner)

    def test_unwrap_accepts_bare_rpt_compat(self):
        bare = pack_keepalive(b"\x11" * 8)
        self.assertTrue(looks_like_bare_rpt(bare))
        self.assertEqual(unwrap_frame(bare, allow_bare=True), bare)

    def test_maybe_wrap_respects_env(self):
        inner = MAGIC + bytes([MsgType.DATA]) + b"x" * 20
        with mock.patch.dict("os.environ", {"RPT_OBFS": "0"}):
            self.assertFalse(product_obfuscation_enabled())
            self.assertEqual(maybe_wrap(inner), inner)
        with mock.patch.dict("os.environ", {"RPT_OBFS": "1"}):
            self.assertTrue(product_obfuscation_enabled())
            w = maybe_wrap(inner)
            self.assertNotEqual(w[:4], MAGIC)
            self.assertEqual(maybe_unwrap(w), inner)

    def test_product_default_lean_off(self):
        """Product residual baseline: outer wrap off when RPT_OBFS unset."""
        with mock.patch.dict("os.environ", {}, clear=False):
            import os

            os.environ.pop("RPT_OBFS", None)
            self.assertFalse(product_obfuscation_enabled())


class TestObfuscationWiring(unittest.TestCase):
    def test_client_connect_uses_maybe_wrap(self):
        src = (ROOT / "client" / "connect.py").read_text(encoding="utf-8")
        self.assertIn("maybe_wrap", src)
        self.assertIn("maybe_unwrap", src)
        self.assertIn("from node.obfuscation import", src)

    def test_node_server_uses_obfuscation(self):
        src = (ROOT / "node" / "server.py").read_text(encoding="utf-8")
        self.assertIn("maybe_wrap", src)
        self.assertIn("maybe_unwrap", src)

    def test_seal_packet_returns_wrapped_when_enabled(self):
        """Drive real seal path with a minimal session stub."""
        from client.connect import RptClient
        from node.crypto_session import SessionCrypto
        from types import SimpleNamespace

        client = RptClient()
        crypto = SessionCrypto(key=b"k" * 32)
        client.session = SimpleNamespace(
            session_id=b"S" * 8,
            counter_out=0,
            crypto=crypto,
        )
        with mock.patch.dict("os.environ", {"RPT_OBFS": "1"}):
            wire = client.seal_packet(b"\x45" + b"\x00" * 20)
        self.assertFalse(looks_like_bare_rpt(wire))
        self.assertTrue(looks_like_obfs(wire))
        # Round-trip open
        with mock.patch.dict("os.environ", {"RPT_OBFS": "1"}):
            plain, is_cover = client.open_packet_allow_cover(wire)
        self.assertFalse(is_cover)
        self.assertEqual(plain[:1], b"\x45")


if __name__ == "__main__":
    unittest.main()
