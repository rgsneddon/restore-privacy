"""Product Connect must not phone home to third parties (geo/telemetry HTTPS)."""

from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from client.connect import ConnectState, RptClient  # noqa: E402

# Former / forbidden third-party geo & telemetry hosts on product Connect
FORBIDDEN_HOST_FRAGMENTS = (
    "ipapi.co",
    "ipinfo.io",
    "country.is",
    "ip-api.com",
    "google-analytics",
    "sentry.io",
    "segment.io",
    "mixpanel.com",
    "amplitude.com",
)

PRODUCT_CONNECT_SOURCES = (
    ROOT / "client" / "connect.py",
    ROOT / "client" / "windows" / "app.py",
    ROOT / "client" / "linux" / "app.py",
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
    / "RptVpnService.kt",
    ROOT
    / "client_app"
    / "apple_shared"
    / "Rpt2"
    / "Sources"
    / "Rpt2"
    / "RptConnectOrchestrator.swift",
    ROOT / "client_app" / "ios" / "NativePrep" / "PacketTunnelProvider.swift",
    ROOT / "client_app" / "macos" / "NativePrep" / "PacketTunnelProvider.swift",
)


class TestConnectSourceNoThirdParty(unittest.TestCase):
    def test_product_connect_sources_exist(self):
        for p in PRODUCT_CONNECT_SOURCES:
            self.assertTrue(p.is_file(), f"missing product path: {p}")

    def test_product_sources_have_no_forbidden_geo_hosts(self):
        for path in PRODUCT_CONNECT_SOURCES:
            text = path.read_text(encoding="utf-8")
            lower = text.lower()
            for frag in FORBIDDEN_HOST_FRAGMENTS:
                self.assertNotIn(
                    frag,
                    lower,
                    f"product Connect source must not reference {frag}: {path}",
                )

    def test_python_connect_module_has_no_http_client_imports(self):
        src = (ROOT / "client" / "connect.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        # Top-level imports only (nested urllib for first-party node-state poll is OK)
        top_imported: set[str] = set()
        for node in tree.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top_imported.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom) and node.module:
                top_imported.add(node.module.split(".")[0])
        for bad in ("urllib", "requests", "httpx", "aiohttp", "http"):
            self.assertNotIn(
                bad, top_imported, f"connect.py must not top-level import {bad}"
            )
        # Nested urllib is only for private preferred node-state poll (first-party)
        if "urllib" in src:
            self.assertIn("poll_preferred_node_state", src)
            self.assertIn("/api/private/node-state", src)
        self.assertNotIn("uk_gate", src)
        self.assertNotIn("check_uk_public_ip", src)

    def test_android_vpn_service_no_httpurlconnection_on_connect(self):
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
        self.assertNotIn("HttpURLConnection", text)
        self.assertNotIn("UkIpGate.checkUkPublicIp", text)
        self.assertNotIn("ipapi.co", text.lower())

    def test_legacy_uk_gate_stubs_do_not_open_network(self):
        """If leftover gate helpers remain, they must not perform live HTTPS."""
        android = (
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
            / "UkIpGate.kt"
        )
        if android.is_file():
            t = android.read_text(encoding="utf-8")
            self.assertNotIn("HttpURLConnection", t)
            self.assertNotIn("ipapi.co", t.lower())
            self.assertIn("no third-party", t.lower())
        for rel in (
            "client_app/apple_shared/Rpt2/Sources/Rpt2/RptUkIpGate.swift",
            "client_app/ios/NativePrep/Rpt2/RptUkIpGate.swift",
            "client_app/macos/NativePrep/Rpt2/RptUkIpGate.swift",
        ):
            p = ROOT / rel
            if not p.is_file():
                continue
            t = p.read_text(encoding="utf-8")
            self.assertNotIn("ipapi.co", t.lower())
            self.assertNotIn("URLRequest", t)
            self.assertIn("no third-party", t.lower())


class TestRptClientConnectNoUrlopen(unittest.TestCase):
    def test_connect_does_not_call_urllib_urlopen(self):
        """Drive real RptClient.connect; urllib.request.urlopen must not run."""
        client = RptClient(secrets_dir=Path("/nonexistent/no-phones-home-secrets"))
        with mock.patch("urllib.request.urlopen") as urlopen:
            result = client.connect(timeout=0.3)
            urlopen.assert_not_called()
        self.assertFalse(result.ok)
        self.assertEqual(result.state, ConnectState.ERROR)
        msg = result.message.lower()
        for frag in ("ipapi", "ipinfo", "united kingdom", "geo"):
            self.assertNotIn(frag, msg)


class TestNodePrivacyPrepOffline(unittest.TestCase):
    def test_install_dns_tunnel_only(self):
        script = (ROOT / "node" / "install_dns.sh").read_text(encoding="utf-8")
        conf = (ROOT / "node" / "unbound-rpt.conf").read_text(encoding="utf-8")
        self.assertIn("10.88.0.1", script)
        self.assertIn("unbound", script.lower())
        self.assertIn("10.88.0.0/24", conf)
        self.assertIn("0.0.0.0/0 refuse", conf)
        self.assertIn("interface: 10.88.0.1", conf)

    def test_install_host_privacy_and_nolog(self):
        host = ROOT / "node" / "install_host_privacy.sh"
        self.assertTrue(host.is_file())
        text = host.read_text(encoding="utf-8")
        self.assertIn("journald", text.lower())
        self.assertIn("volatile", text.lower())
        install = (ROOT / "node" / "install.sh").read_text(encoding="utf-8")
        self.assertIn("StandardOutput=null", install)
        self.assertIn("install_dns.sh", install)
        self.assertIn("install_host_privacy.sh", install)
        nolog = (ROOT / "node" / "nolog.py").read_text(encoding="utf-8")
        self.assertIn("connection_log", nolog)
        self.assertIn("False", nolog)

    def test_deploy_followup_note_in_sundries(self):
        text = (ROOT / "sundries.txt").read_text(encoding="utf-8")
        lower = text.lower()
        self.assertIn("install_dns", lower)
        self.assertIn("install_host_privacy", lower)
        self.assertTrue(
            "deploy" in lower or "when the box" in lower or "flokinet" in lower or "vps" in lower
        )


if __name__ == "__main__":
    unittest.main()
