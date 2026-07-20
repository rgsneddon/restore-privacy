"""Leak test decision logic + Settings wiring (honest residual/DNS checks)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from client.leak_test import (  # noqa: E402
    LeakTestInputs,
    VERDICT_FAIL,
    VERDICT_INCONCLUSIVE,
    VERDICT_PARTIAL,
    VERDICT_PASS,
    collect_leak_test_inputs,
    evaluate_leak_test,
    run_product_leak_test,
)


class TestEvaluateLeakTest(unittest.TestCase):
    def test_pass_when_residual_dns_ipv6_and_probe_ok(self):
        r = evaluate_leak_test(
            LeakTestInputs(
                residual_capture_active=True,
                ipv6_protected=True,
                dns_tunnel_gateway_only=True,
                public_ip_probe_ran=True,
                public_ip_matches_expected_node=True,
            )
        )
        self.assertEqual(r.verdict, VERDICT_PASS)
        self.assertFalse(r.claims_multihop_residual)
        self.assertIn("Residual", r.format_user_message())
        self.assertIn("Multi-hop", r.format_user_message())

    def test_inconclusive_when_not_connected(self):
        r = evaluate_leak_test(
            LeakTestInputs(
                residual_capture_active=False,
                dns_tunnel_gateway_only=True,
            )
        )
        self.assertEqual(r.verdict, VERDICT_INCONCLUSIVE)
        self.assertFalse(r.claims_multihop_residual)

    def test_fail_when_public_dns_violations(self):
        r = evaluate_leak_test(
            LeakTestInputs(
                residual_capture_active=True,
                ipv6_protected=True,
                dns_tunnel_gateway_only=False,
                public_dns_violations=("public DNS fallback not allowed: 1.1.1.1",),
                public_ip_probe_ran=True,
                public_ip_matches_expected_node=True,
            )
        )
        self.assertEqual(r.verdict, VERDICT_FAIL)

    def test_fail_when_egress_probe_misses_node(self):
        r = evaluate_leak_test(
            LeakTestInputs(
                residual_capture_active=True,
                ipv6_protected=True,
                dns_tunnel_gateway_only=True,
                public_ip_probe_ran=True,
                public_ip_matches_expected_node=False,
            )
        )
        self.assertEqual(r.verdict, VERDICT_FAIL)
        self.assertIn("leak", r.summary.lower() + " ".join(r.details).lower())

    def test_partial_without_live_probe(self):
        r = evaluate_leak_test(
            LeakTestInputs(
                residual_capture_active=True,
                ipv6_protected=True,
                dns_tunnel_gateway_only=True,
                public_ip_probe_ran=False,
            )
        )
        self.assertEqual(r.verdict, VERDICT_PARTIAL)

    def test_partial_without_ipv6(self):
        r = evaluate_leak_test(
            LeakTestInputs(
                residual_capture_active=True,
                ipv6_protected=False,
                dns_tunnel_gateway_only=True,
                public_ip_probe_ran=True,
                public_ip_matches_expected_node=True,
            )
        )
        self.assertEqual(r.verdict, VERDICT_PARTIAL)

    def test_never_claims_multihop(self):
        for active in (True, False):
            r = evaluate_leak_test(
                LeakTestInputs(
                    residual_capture_active=active,
                    multihop_residual_routed=True,
                )
            )
            self.assertFalse(r.claims_multihop_residual)
            msg = r.format_user_message().lower()
            self.assertIn("multi-hop", msg)
            self.assertNotIn("multi-hop residual is active", msg)


class TestCollectAndRunProductLeakTest(unittest.TestCase):
    def test_collect_uses_shipped_dns_plan(self):
        inputs = collect_leak_test_inputs(
            residual_capture_active=True,
            ipv6_protected=False,
            run_public_ip_probe=False,
        )
        self.assertTrue(inputs.dns_tunnel_gateway_only)
        self.assertEqual(inputs.public_dns_violations, ())
        self.assertFalse(inputs.public_ip_probe_ran)
        self.assertFalse(inputs.multihop_residual_routed)

    def test_run_product_entry_with_probe_fixture(self):
        r = run_product_leak_test(
            residual_capture_active=True,
            ipv6_protected=True,
            run_public_ip_probe=True,
            public_ip_probe=lambda: True,
        )
        self.assertEqual(r.verdict, VERDICT_PASS)
        self.assertFalse(r.claims_multihop_residual)

    def test_run_product_probe_false(self):
        r = run_product_leak_test(
            residual_capture_active=True,
            ipv6_protected=True,
            run_public_ip_probe=True,
            public_ip_probe=lambda: False,
        )
        self.assertEqual(r.verdict, VERDICT_FAIL)


class TestLeakTestUiWiring(unittest.TestCase):
    def test_windows_settings_wires_leak_test(self):
        src = (ROOT / "client" / "windows" / "app.py").read_text(encoding="utf-8")
        copy = (ROOT / "client" / "transparency_copy.py").read_text(encoding="utf-8")
        self.assertIn("run_product_leak_test", src)
        self.assertIn("LEAK_TEST_BUTTON", src)
        self.assertIn("_run_leak_test", src)
        self.assertIn("Run leak test", copy)
        self.assertTrue(
            "leak test" in (src + copy).lower(),
            "Settings must expose Leak test control",
        )

    def test_flutter_settings_wires_leak_test(self):
        screen = (
            ROOT / "client_app" / "lib" / "settings_screen.dart"
        ).read_text(encoding="utf-8")
        leak = (ROOT / "client_app" / "lib" / "leak_test.dart").read_text(
            encoding="utf-8"
        )
        self.assertIn("Leak test", screen + (ROOT / "client_app" / "lib" / "transparency_copy.dart").read_text(encoding="utf-8"))
        self.assertIn("runLeakTest", screen)
        self.assertIn("runProductLeakTest", screen)
        self.assertIn("evaluateLeakTest", leak)


if __name__ == "__main__":
    unittest.main()
