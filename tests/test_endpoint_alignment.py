"""Shipped product endpoint must match Flutter + VPN APP Shop + Apple RptEndpoint."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Active Vultr RPT node (VPN APP Shop + live clients)
PRODUCT_HOST = "82.221.101.241"
PRODUCT_PORT = "44044"


def _read(rel: str) -> str:
    p = ROOT / rel
    assert p.is_file(), rel
    return p.read_text(encoding="utf-8")


class TestEndpointAlignment(unittest.TestCase):
    def test_flutter_rpt_config(self):
        text = _read("client_app/lib/rpt_config.dart")
        # Entry default + residual host getter (multi-hop may select exit)
        self.assertIn(f"entryHost = '{PRODUCT_HOST}'", text)
        self.assertIn("exitHost = '185.146.232.107'", text)
        self.assertIn(f"port = {PRODUCT_PORT}", text)
        self.assertIn("static String get host", text)
        self.assertIn("multiHopEnabled", text)

    def test_python_client_endpoint(self):
        text = _read("client/endpoint.py")
        self.assertIn(f'host: str = "{PRODUCT_HOST}"', text)
        self.assertIn(f"port: int = {PRODUCT_PORT}", text)

    def test_status_page_upstream(self):
        app = _read("status_page/app.py")
        yaml = _read("render.yaml")
        self.assertIn(f"http://{PRODUCT_HOST}:8080/api/status", app)
        self.assertIn(f"http://{PRODUCT_HOST}:8080/api/status", yaml)

    def test_apple_shared_rpt_endpoint(self):
        text = _read("client_app/apple_shared/Rpt2/Sources/Rpt2/RptEndpoint.swift")
        self.assertIn(f'host: String = "{PRODUCT_HOST}"', text)
        self.assertIn(f"port: UInt16 = {PRODUCT_PORT}", text)
        # iOS/macOS copies must match
        for rel in (
            "client_app/ios/NativePrep/Rpt2/RptEndpoint.swift",
            "client_app/macos/NativePrep/Rpt2/RptEndpoint.swift",
        ):
            t = _read(rel)
            self.assertIn(PRODUCT_HOST, t)
            self.assertIn(PRODUCT_PORT, t)

    def test_apple_native_paths_use_rpt_endpoint_not_divergent_literals(self):
        """Channel/tunnel defaults should reference RptEndpoint, not a different IP literal."""
        paths = [
            "client_app/ios/NativePrep/RptVpnChannel.swift",
            "client_app/macos/NativePrep/RptVpnChannel.swift",
            "client_app/ios/NativePrep/PacketTunnelProvider.swift",
            "client_app/macos/NativePrep/PacketTunnelProvider.swift",
            "client_app/apple_shared/Rpt2/Sources/Rpt2/RptConnectOrchestrator.swift",
        ]
        for rel in paths:
            text = _read(rel)
            # No hard-coded alternate product host
            self.assertNotRegex(
                text,
                r'host\s*=\s*"[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+"',
                msg=f"{rel} has raw IP host default",
            )
            self.assertTrue(
                "RptEndpoint" in text or PRODUCT_HOST in text,
                msg=f"{rel} should use RptEndpoint or product host",
            )


if __name__ == "__main__":
    unittest.main()
