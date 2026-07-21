"""Connect path after flyclient removal: always HELLO unless already connected."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from client.connect import ConnectState, RptClient, _tunnel_plan_for_session  # noqa: E402
from client.full_tunnel import build_full_tunnel_plan  # noqa: E402


class TestNoFlyclientModule(unittest.TestCase):
    def test_flyclient_module_gone(self):
        self.assertFalse((ROOT / "client" / "flyclient_connect.py").is_file())
        import importlib

        with self.assertRaises(ModuleNotFoundError):
            importlib.import_module("client.flyclient_connect")

    def test_product_sources_have_no_flyclient_strings(self):
        needles = (
            "flyclient_connect",
            "flyclient_decide",
            "FlyclientConnectState",
            "flyclient skip",
            "Flyclient tip",
        )
        paths = [
            ROOT / "client" / "connect.py",
            ROOT / "client" / "windows" / "tunnel_win.py",
            ROOT / "client" / "linux" / "tunnel_linux.py",
            ROOT / "client" / "windows" / "app.py",
            ROOT / "client" / "linux" / "app.py",
        ]
        for p in paths:
            text = p.read_text(encoding="utf-8")
            lower = text.lower()
            for n in needles:
                self.assertNotIn(n.lower(), lower, msg=f"{p.name} still mentions {n}")


class TestTunnelPlanReuse(unittest.TestCase):
    def test_reuses_when_ip_matches(self):
        p1 = build_full_tunnel_plan("10.88.0.7")
        p2 = _tunnel_plan_for_session(p1, "10.88.0.7")
        self.assertIs(p2, p1)

    def test_rebuilds_when_ip_changes(self):
        p1 = build_full_tunnel_plan("10.88.0.7")
        p2 = _tunnel_plan_for_session(p1, "10.88.0.8")
        self.assertIsNot(p2, p1)
        self.assertEqual(p2.tunnel_client_ip, "10.88.0.8")


class TestRptClientAlwaysHello(unittest.TestCase):
    def test_force_reconnect_does_not_early_exit_without_hello(self):
        """Warm session + force_reconnect must attempt HELLO (not flyclient skip)."""
        client = RptClient()
        # Pretend already connected
        client.state = ConnectState.CONNECTED
        client.session = mock.Mock(vpn_ip="10.88.0.1")
        client.tunnel_plan = build_full_tunnel_plan("10.88.0.1")

        with mock.patch.object(
            client,
            "_status",
        ):
            # Force path into HELLO by making secrets fail fast after skip-check
            with mock.patch(
                "client.connect.ensure_device_admission_key",
                side_effect=FileNotFoundError("no secrets"),
            ):
                out = client.connect(timeout=2.0, force_reconnect=True)
        self.assertFalse(out.ok)
        self.assertNotIn("flyclient", (out.message or "").lower())
        self.assertNotIn("already connected", (out.message or "").lower())

    def test_already_connected_idempotent_without_force(self):
        client = RptClient()
        client.state = ConnectState.CONNECTED
        client.session = mock.Mock(vpn_ip="10.88.0.9")
        client.tunnel_plan = build_full_tunnel_plan("10.88.0.9")
        out = client.connect(timeout=2.0, force_reconnect=False)
        self.assertTrue(out.ok)
        self.assertIn("already connected", out.message.lower())
        self.assertNotIn("flyclient", out.message.lower())


class TestProductAppsNoFlyclientWiring(unittest.TestCase):
    def test_windows_linux_apps_do_not_log_flyclient_tip(self):
        for rel in (
            "client/windows/app.py",
            "client/linux/app.py",
        ):
            text = (ROOT / rel).read_text(encoding="utf-8")
            self.assertNotIn("Flyclient tip", text)
            self.assertNotIn("flyclient skip", text)
            self.assertIn("client.connect(", text)


if __name__ == "__main__":
    unittest.main()
