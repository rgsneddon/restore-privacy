"""Co-joined residual roles + admin rpS readiness + client single contact."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "status_page"))
sys.path.insert(0, str(ROOT / "client"))
sys.path.insert(0, str(ROOT / "node"))


class TestCojoinedRoles(unittest.TestCase):
    def test_registry_starts_three_roles(self) -> None:
        from node.cojoined_roles import (
            COJOINED_ROLES,
            ROLE_PERC,
            ROLE_RPAI,
            ROLE_VPN,
            CojoinedRoleRegistry,
        )

        self.assertEqual(set(COJOINED_ROLES), {ROLE_VPN, ROLE_RPAI, ROLE_PERC})
        reg = CojoinedRoleRegistry()
        reg.configure_contact(host="10.0.0.1", port=44044, ui_port=8080)
        reg.start_background_roles()
        # VPN marked immediately; background threads mark AI/chain
        reg.mark_role(ROLE_RPAI, ready=True, running=True)
        reg.mark_role(ROLE_PERC, ready=True, running=True)
        snap = reg.snapshot()
        self.assertTrue(snap["cojoined"])
        self.assertTrue(snap["all_ready"])
        self.assertEqual(snap["contact"]["contact"], "10.0.0.1:44044")
        self.assertEqual(snap["contact"]["roles"], list(COJOINED_ROLES))
        reg.stop_background_roles()

    def test_deploy_script_lists_cojoined_modules(self) -> None:
        text = (ROOT / "scripts" / "deploy_rpt_node.py").read_text(encoding="utf-8")
        self.assertIn("cojoined_roles.py", text)
        self.assertIn("oracle_master.py", text)


class TestClientSingleContact(unittest.TestCase):
    def test_cojoined_single_contact(self) -> None:
        import importlib.util

        path = ROOT / "client" / "cojoined_contact.py"
        spec = importlib.util.spec_from_file_location("cojoined_contact", path)
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        # Load endpoint dependency first under package-less names
        ep_path = ROOT / "client" / "endpoint.py"
        ep_spec = importlib.util.spec_from_file_location("endpoint", ep_path)
        assert ep_spec and ep_spec.loader
        ep_mod = importlib.util.module_from_spec(ep_spec)
        sys.modules["endpoint"] = ep_mod
        ep_spec.loader.exec_module(ep_mod)
        sys.modules["cojoined_contact"] = mod
        spec.loader.exec_module(mod)
        c = mod.cojoined_single_contact()
        self.assertTrue(c["cojoined"])
        self.assertEqual(len(c["roles"]), 3)
        self.assertIn("vpn", c["hooks"])
        self.assertIn("rpai", c["hooks"])
        self.assertIn("perccent", c["hooks"])
        host, port = mod.primary_residual_endpoint()
        self.assertEqual(c["host"], host)
        self.assertEqual(c["port"], port)
        self.assertEqual(c["contact"], f"{host}:{port}")


class TestAdminRpsReady(unittest.TestCase):
    def test_readiness_all_true_after_lab_oracle(self) -> None:
        from admin_rps import (
            ensure_admin_rps_ready_surface,
            readiness_parameters,
            render_admin_rps_page_html,
            render_admin_rps_stats_html,
        )

        td = tempfile.TemporaryDirectory()
        try:
            path = Path(td.name) / "rps.json"
            stats = ensure_admin_rps_ready_surface(stats_path=path)
            ready = readiness_parameters(stats)
            for k, v in ready.items():
                self.assertTrue(v, msg=f"{k} should be true, got {v}")
            html = render_admin_rps_stats_html(stats)
            self.assertIn("data-all-ready=\"true\"", html)
            self.assertIn("ready_vpn", html)
            self.assertIn("ready_rpai", html)
            self.assertIn("ready_perccent", html)
            page = render_admin_rps_page_html().decode("utf-8")
            self.assertIn("admin-rps-page", page)
            self.assertIn("co-joined", page.lower() or "cojoined")
        finally:
            td.cleanup()

    def test_oracle_collate_two_satellites(self) -> None:
        from node.oracle_master import collate_satellite_heartbeats, ned_learn_oracle

        cj = {
            "all_ready": True,
            "readiness": {"vpn": True, "rpai": True, "perccent": True},
            "roles": {
                "rpai": {"ready": True, "stats": {"learning_epochs_local": 2}},
                "perccent": {"ready": True, "stats": {"seed_ticks": 3}},
            },
        }
        o = collate_satellite_heartbeats(
            [
                {"host": "a", "cojoined": cj, "capacity": {"live": 1, "capacity": 100}},
                {"host": "b", "cojoined": cj, "capacity": {"live": 2, "capacity": 200}},
            ]
        )
        self.assertEqual(o["satellites_seen"], 2)
        self.assertTrue(o["all_satellites_ready"])
        self.assertTrue(o["roles_ready"]["vpn"])
        learned = ned_learn_oracle({}, o)
        self.assertTrue(learned["ready_cojoined"])
        self.assertGreaterEqual(learned["compute_score"], 0)


class TestNodeOperatorDoc(unittest.TestCase):
    def test_node_operator_mentions_three_parts(self) -> None:
        text = (ROOT / "status_page" / "public" / "NODE_OPERATOR.md").read_text(
            encoding="utf-8"
        ).lower()
        self.assertIn("co-joined", text)
        self.assertIn("vpn", text)
        self.assertIn("rpai", text)
        self.assertIn("perccent", text)
        self.assertIn("single residual contact", text)


if __name__ == "__main__":
    unittest.main()
