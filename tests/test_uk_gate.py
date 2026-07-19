"""Product connect has no UK public-IP geo admission (privacy: no third-party geo).

Drives shipped ``RptClient.connect`` and asserts product sources no longer call
geo providers or fail closed on non-UK country before handshake.
"""

from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from client.connect import ConnectState, RptClient  # noqa: E402


class TestProductConnectNoUkGeoGate(unittest.TestCase):
    def test_uk_gate_module_removed(self):
        self.assertFalse(
            (ROOT / "client" / "uk_gate.py").is_file(),
            "client.uk_gate must not ship as product geo admission",
        )

    def test_connect_source_has_no_uk_gate_call(self):
        src = (ROOT / "client" / "connect.py").read_text(encoding="utf-8")
        self.assertNotIn("check_uk_public_ip", src)
        self.assertNotIn("run_uk_gate", src)
        self.assertNotIn("uk_gate_fetcher", src)
        self.assertNotIn("skip_uk_gate", src)
        self.assertNotIn("from .uk_gate", src)
        # Docstring / comment must state no geo admission
        lowered = src.lower().replace("—", "-").replace("–", "-")
        self.assertIn("no public-ip geo", lowered)
        self.assertIn("no third-party geo", lowered)
        tree = ast.parse(src)
        names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
        self.assertNotIn("check_uk_public_ip", names)
        self.assertNotIn("UkGateResult", names)

    def test_connect_does_not_block_for_non_uk_geo(self):
        """Former behaviour blocked non-UK before secrets; product must reach secrets path."""
        client = RptClient(secrets_dir=Path("/nonexistent/secrets/path-for-uk-strip-test"))
        # If UK gate still ran, non-UK would never touch secrets. We only require that
        # connect is not a UK denial — secrets/network failure is fine.
        result = client.connect(timeout=0.5)
        self.assertFalse(result.ok)
        self.assertEqual(result.state, ConnectState.ERROR)
        msg = result.message.lower()
        self.assertNotIn("united kingdom", msg)
        self.assertNotIn("not uk", msg)
        self.assertNotIn("geolocat", msg)
        # Must have attempted admission material, not geo-only fail
        self.assertTrue(
            "secret" in msg
            or "node_elgamal" in msg
            or "client_ed25519" in msg
            or "node" in msg
            or "key" in msg
            or "not found" in msg
            or "missing" in msg
            or "no such" in msg
            or "permission" in msg
            or "directory" in msg
            or "file" in msg,
            f"expected secrets/network failure, got: {result.message!r}",
        )

    def test_connect_does_not_call_geo_https(self):
        """urllib geo fetch must not run during product connect."""
        client = RptClient(secrets_dir=Path("/nonexistent/uk-strip-geo"))
        with mock.patch("urllib.request.urlopen") as urlopen:
            result = client.connect(timeout=0.3)
            urlopen.assert_not_called()
        self.assertFalse(result.ok)
        self.assertNotIn("United Kingdom", result.message)

    def test_android_vpn_service_has_no_uk_gate_call(self):
        path = (
            ROOT
            / "client_app"
            / "android"
            / "app"
            / "src"
            / "main"
            / "kotlin"
            / "com"
            / "restoreprivacy"
            / "restore_privacy_client"
            / "RptVpnService.kt"
        )
        text = path.read_text(encoding="utf-8")
        self.assertNotIn("UkIpGate.checkUkPublicIp", text)
        self.assertNotIn("UK public-IP gate", text)

    def test_apple_product_paths_have_no_uk_gate_call(self):
        orch = (
            ROOT
            / "client_app"
            / "apple_shared"
            / "Rpt2"
            / "Sources"
            / "Rpt2"
            / "RptConnectOrchestrator.swift"
        ).read_text(encoding="utf-8")
        self.assertNotIn("RptUkIpGate.checkUkPublicIp", orch)
        self.assertNotIn("skipUkGate", orch)
        for rel in (
            "client_app/ios/NativePrep/PacketTunnelProvider.swift",
            "client_app/macos/NativePrep/PacketTunnelProvider.swift",
        ):
            text = (ROOT / rel).read_text(encoding="utf-8")
            self.assertNotIn("RptUkIpGate.checkUkPublicIp", text)
            self.assertNotIn("UK public IP gate", text)


if __name__ == "__main__":
    unittest.main()
