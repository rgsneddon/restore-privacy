"""Linux Mint client: route plan, residual honesty, entry wiring."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from client.full_tunnel import (  # noqa: E402
    FullTunnelPlan,
    assert_full_tunnel_plan,
    build_full_tunnel_plan,
    linux_route_commands,
    linux_route_delete_commands,
)
from client.linux.tunnel_linux import (  # noqa: E402
    LinuxTunnelResult,
    build_linux_route_plan_cmds,
    product_connect_requires_root,
    residual_ip_capture_active,
    start_full_tunnel,
    stop_full_tunnel,
)
from client.linux.tun_linux import system_capture_ready, tun_device_path  # noqa: E402
from client.ui_theme import plain_tunnel_status  # noqa: E402


class TestLinuxRouteBuilders(unittest.TestCase):
    def test_dual_slash1_and_server_pin_order(self):
        plan = build_full_tunnel_plan("10.88.0.2", tunnel_iface="rpt0")
        cmds = linux_route_commands(
            plan,
            "104.156.224.47",
            iface="rpt0",
            physical_dev="eth0",
            physical_gw="192.168.1.1",
        )
        joined = "\n".join(cmds)
        self.assertIn("0.0.0.0/1 dev rpt0", joined)
        self.assertIn("128.0.0.0/1 dev rpt0", joined)
        self.assertIn("104.156.224.47/32", joined)
        pin = joined.find("104.156.224.47/32")
        catch = joined.find("0.0.0.0/1")
        self.assertLess(pin, catch)
        # no catch-all without flag
        no = "\n".join(
            linux_route_commands(plan, "1.2.3.4", include_catchall=False)
        )
        self.assertNotIn("0.0.0.0/1", no)

    def test_delete_covers_dual_and_pin(self):
        plan = build_full_tunnel_plan("10.88.0.2", tunnel_iface="rpt0")
        dels = linux_route_delete_commands(plan, "9.9.9.9", iface="rpt0")
        joined = "\n".join(dels)
        self.assertIn("0.0.0.0/1", joined)
        self.assertIn("128.0.0.0/1", joined)
        self.assertIn("9.9.9.9/32", joined)

    def test_assert_full_tunnel_plan_includes_linux(self):
        plan = build_full_tunnel_plan("10.88.0.2")
        v = assert_full_tunnel_plan(plan)
        self.assertEqual(v, [], v)

    def test_build_linux_route_plan_cmds_normalizes_iface(self):
        plan = FullTunnelPlan(tunnel_iface="RPT", tunnel_client_ip="10.88.0.2")
        cmds = build_linux_route_plan_cmds(
            plan, "1.1.1.1", physical_gw="10.0.0.1", physical_dev="wlan0"
        )
        self.assertTrue(any("rpt0" in c for c in cmds))
        self.assertEqual(plan.tunnel_iface, "rpt0")


class TestLinuxResidualHonesty(unittest.TestCase):
    def test_residual_requires_routes_and_capture(self):
        self.assertFalse(residual_ip_capture_active(None))
        bare = LinuxTunnelResult(True, "ok", system_capture=False, routes_applied=False)
        self.assertFalse(residual_ip_capture_active(bare))
        half = LinuxTunnelResult(
            True, "ok", system_capture=True, routes_applied=False, dataplane=object()
        )
        self.assertFalse(residual_ip_capture_active(half))
        plane = mock.Mock()
        full = LinuxTunnelResult(
            True,
            "ok",
            system_capture=True,
            routes_applied=True,
            dataplane=plane,
        )
        self.assertTrue(residual_ip_capture_active(full))

    def test_product_requires_root(self):
        self.assertTrue(product_connect_requires_root())

    def test_status_plain_language(self):
        ok = plain_tunnel_status(
            "connected", vpn_ip="10.88.0.2", residual_capture=True
        )
        self.assertIn("VPN", ok)
        off = plain_tunnel_status(
            "connected", vpn_ip="10.88.0.2", residual_capture=False
        )
        self.assertIn("ISP", off)

    def test_start_full_tunnel_refuses_non_linux_without_dry_run(self):
        client = mock.Mock()
        client.session = mock.Mock(vpn_ip="10.88.0.2")
        plan = build_full_tunnel_plan("10.88.0.2", tunnel_iface="rpt0")
        if sys.platform == "linux":
            # On Linux without root, require_system_capture fails honestly
            with mock.patch("client.linux.tunnel_linux.is_root", return_value=False):
                res = start_full_tunnel(
                    client, plan, "1.2.3.4", require_system_capture=True
                )
            self.assertFalse(res.ok)
            self.assertFalse(residual_ip_capture_active(res))
            self.assertIn("root", res.message.lower())
        else:
            res = start_full_tunnel(
                client, plan, "1.2.3.4", require_system_capture=True
            )
            self.assertFalse(res.ok)
            self.assertFalse(residual_ip_capture_active(res))
            self.assertIn("Linux", res.message)

    def test_dry_run_emits_dual_slash1(self):
        client = mock.Mock()
        client.session = mock.Mock(vpn_ip="10.88.0.2")
        plan = build_full_tunnel_plan("10.88.0.2", tunnel_iface="rpt0")
        with mock.patch(
            "client.linux.tunnel_linux.resolve_default_route",
            return_value=("192.168.0.1", "eth0"),
        ):
            res = start_full_tunnel(
                client, plan, "8.8.8.8", dry_run=True, require_system_capture=True
            )
        self.assertTrue(res.ok)
        joined = "\n".join(res.applied_commands)
        self.assertIn("0.0.0.0/1", joined)
        self.assertFalse(res.routes_applied)  # dry_run is not residual capture

    def test_stop_clears_residual_flags(self):
        plane = mock.Mock()
        tun = mock.Mock()
        res = LinuxTunnelResult(
            True,
            "up",
            system_capture=True,
            routes_applied=True,
            dataplane=plane,
            tun=tun,
            plan=build_full_tunnel_plan("10.88.0.2"),
            server_host="1.2.3.4",
            iface="rpt0",
        )
        with mock.patch(
            "client.linux.tunnel_linux.rollback_full_tunnel_routes", return_value=[]
        ):
            stop_full_tunnel(res, client=None, disconnect_session=False)
        self.assertFalse(res.ok)
        self.assertFalse(res.routes_applied)
        self.assertIsNone(res.dataplane)
        self.assertFalse(residual_ip_capture_active(res))
        plane.stop.assert_called()
        tun.close.assert_called()


class TestLinuxEntryAndDocs(unittest.TestCase):
    def test_module_entry_exists(self):
        main_py = ROOT / "client" / "linux" / "__main__.py"
        app_py = ROOT / "client" / "linux" / "app.py"
        self.assertTrue(main_py.is_file())
        self.assertTrue(app_py.is_file())
        src = app_py.read_text(encoding="utf-8")
        self.assertIn("def _start_connect", src)
        self.assertIn("def _start_disconnect", src)
        self.assertIn("residual_ip_capture_active", src)
        self.assertIn("require_system_capture=True", src)
        self.assertIn("start_full_tunnel", src)

    def test_install_script_and_package_recipe(self):
        inst = ROOT / "scripts" / "install_linux_mint.sh"
        self.assertTrue(inst.is_file())
        t = inst.read_text(encoding="utf-8")
        self.assertIn("python3 -m client.linux", t)
        self.assertIn("modprobe tun", t)
        pkg = ROOT / "scripts" / "package_linux.py"
        self.assertTrue(pkg.is_file())
        self.assertIn("linux-x64.tar.gz", pkg.read_text(encoding="utf-8"))

    def test_readme_mentions_mint(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("Linux Mint", readme)
        self.assertIn("client.linux", readme)
        self.assertIn("linux-x64.tar.gz", readme)

    def test_catalog_lists_linux(self):
        from status_page.downloads import (
            LINUX_TGZ_FILENAME,
            RELEASE_VERSION,
            available_downloads,
            render_download_section_html,
        )

        plats = {a.platform for a in available_downloads()}
        self.assertIn("linux", plats)
        self.assertIn(RELEASE_VERSION, LINUX_TGZ_FILENAME)
        html = render_download_section_html()
        self.assertIn("linux", html.lower())
        self.assertIn(LINUX_TGZ_FILENAME, html)
        self.assertIn("Linux Mint", html)

    def test_tun_path_helper(self):
        p = tun_device_path()
        self.assertEqual(p.as_posix(), "/dev/net/tun")
        # On Windows agent host, system capture is not ready
        if sys.platform != "linux":
            self.assertFalse(system_capture_ready())


if __name__ == "__main__":
    unittest.main()
