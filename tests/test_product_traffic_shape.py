"""Product dataplane policy enables padding/jitter/cover on the real path."""

from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]

from client.product_policy import (  # noqa: E402
    PRODUCT_ENABLED_TRAFFIC_SHAPE,
    product_dataplane_traffic_shape,
    traffic_shape_enabled_by_env,
)
from client.dataplane import RptDataPlane  # noqa: E402
from node.crypto_session import SessionCrypto  # noqa: E402
from node.traffic_shape import DEFAULT_TRAFFIC_SHAPE  # noqa: E402


class TestProductTrafficShapePolicy(unittest.TestCase):
    def test_default_env_enables_shaping(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("RPT_TRAFFIC_SHAPE", None)
            self.assertTrue(traffic_shape_enabled_by_env())
            pol = product_dataplane_traffic_shape()
            self.assertTrue(pol.padding)
            self.assertGreater(pol.jitter_ms_max, 0)
            self.assertTrue(pol.cover_traffic)
            self.assertGreater(pol.cover_interval_s, 0)

    def test_env_off_disables(self):
        with mock.patch.dict(os.environ, {"RPT_TRAFFIC_SHAPE": "0"}):
            self.assertFalse(traffic_shape_enabled_by_env())
            pol = product_dataplane_traffic_shape()
            self.assertFalse(pol.padding)
            self.assertEqual(pol.jitter_ms_max, 0)
            self.assertFalse(pol.cover_traffic)

    def test_enabled_policy_roundtrip_via_session_crypto(self):
        """Real seal/open with product enabled policy recovers IP payload."""
        pol = PRODUCT_ENABLED_TRAFFIC_SHAPE
        crypto = SessionCrypto(key=b"p" * 32, traffic_shape=pol)
        ip = b"\x45" + b"\xab" * 60
        aad = b"sessid01" + b"\x00" * 0  # 8 bytes sid + use counter in tests
        import struct

        aad = b"S" * 8 + struct.pack("!Q", 1)
        n, sealed = crypto.seal(ip, aad=aad)
        self.assertGreater(len(sealed), len(ip))  # padding expands
        opened = crypto.open(n, sealed, aad=aad)
        self.assertEqual(opened, ip)
        # cover frame discarded
        nc, sc = crypto.seal_cover(pol.pad_bucket, aad=aad)
        plain, is_cover = crypto.open_allow_cover(nc, sc, aad=aad)
        self.assertTrue(is_cover)
        self.assertIsNone(plain)

    def test_windows_tunnel_wires_product_policy(self):
        src = (
            ROOT / "client" / "windows" / "tunnel_win.py"
        ).read_text(encoding="utf-8")
        self.assertIn("product_dataplane_traffic_shape", src)
        self.assertIn("RptDataPlane(client, traffic_shape=", src)

    def test_linux_tunnel_wires_product_policy(self):
        src = (
            ROOT / "client" / "linux" / "tunnel_linux.py"
        ).read_text(encoding="utf-8")
        self.assertIn("product_dataplane_traffic_shape", src)
        self.assertIn("RptDataPlane(client, traffic_shape=", src)


if __name__ == "__main__":
    unittest.main()
