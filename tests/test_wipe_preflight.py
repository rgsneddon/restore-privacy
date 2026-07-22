"""Pre-wipe health gates — fail closed before live entry wipedown."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from node.ephemeral_node import build_weekly_entry_rebuild_plan  # noqa: E402
from node.wipe_preflight import (  # noqa: E402
    HealthProbeResult,
    check_entry_node_health,
    check_exit_health,
    evaluate_prewipe_gates,
    plan_has_required_live_steps,
    probe_exit_residual,
    probe_icmp_reachable,
    probe_udp_reachable,
    run_live_prewipe_gates,
)

# RFC 5737 TEST-NET-3 — must not be a live residual node
DEAD_EXIT_HOST = "203.0.113.50"
DEAD_EXIT_PORT = 44044


class TestRealExitProbeFailClosed(unittest.TestCase):
    """Drive shipped default probes — no injected HealthProbeResult theater."""

    def test_probe_udp_reachable_fails_without_response(self):
        # Send-only used to return ok=True for blackholes; must fail closed now.
        r = probe_udp_reachable(DEAD_EXIT_HOST, DEAD_EXIT_PORT, timeout_s=1.5)
        self.assertFalse(
            r.ok,
            f"UDP send-only must not pass for dead host: {r.detail}",
        )
        self.assertIn("fail closed", r.detail.lower())

    def test_probe_icmp_fails_for_testnet_dead(self):
        r = probe_icmp_reachable(DEAD_EXIT_HOST, timeout_s=2.0)
        self.assertFalse(r.ok, f"ICMP must fail for {DEAD_EXIT_HOST}: {r.detail}")

    def test_probe_exit_residual_fails_for_dead_host(self):
        r = probe_exit_residual(DEAD_EXIT_HOST, DEAD_EXIT_PORT, timeout_s=1.5)
        self.assertFalse(r.ok, r.detail)
        self.assertEqual(r.name, "exit_residual")

    def test_check_exit_health_default_path_dead_host(self):
        """Default probe path (no inject) fails closed on deliberately-dead exit."""
        r = check_exit_health(host=DEAD_EXIT_HOST, port=DEAD_EXIT_PORT)
        self.assertFalse(r.ok, r.detail)
        self.assertEqual(r.host, DEAD_EXIT_HOST)
        entry = HealthProbeResult("entry_node", True, "sim entry ok", "127.0.0.1", 44044)
        g = evaluate_prewipe_gates(exit_probe=r, entry_probe=entry)
        self.assertFalse(
            g.allow_wipe,
            "live wipe must not proceed when exit residual is dead",
        )


class TestPrewipeGates(unittest.TestCase):
    def test_both_healthy_allows_wipe(self):
        exit_r = HealthProbeResult("exit_residual", True, "ok", "185.146.232.107", 44044)
        entry_r = HealthProbeResult("entry_node", True, "ok", "127.0.0.1", 44044)
        g = evaluate_prewipe_gates(exit_probe=exit_r, entry_probe=entry_r)
        self.assertTrue(g.allow_wipe)
        self.assertTrue(g.package_reinstall_required)
        blob = " ".join(g.reasons).lower()
        self.assertIn("failover", blob)
        self.assertNotIn("zero packet", blob.replace("not zero", "XXX"))
        # Honesty: must not claim absolute zero packet loss as guaranteed
        d = g.to_dict()
        self.assertIn("not absolute zero", d["continuity_honesty"])

    def test_exit_unhealthy_fail_closed(self):
        exit_r = HealthProbeResult("exit_residual", False, "down", "x", 44044)
        entry_r = HealthProbeResult("entry_node", True, "ok", "127.0.0.1", 44044)
        g = evaluate_prewipe_gates(exit_probe=exit_r, entry_probe=entry_r)
        self.assertFalse(g.allow_wipe)
        self.assertTrue(any("exit" in r.lower() for r in g.reasons))

    def test_entry_unhealthy_fail_closed(self):
        exit_r = HealthProbeResult("exit_residual", True, "ok", "x", 44044)
        entry_r = HealthProbeResult("entry_node", False, "no listen", "127.0.0.1", 44044)
        g = evaluate_prewipe_gates(exit_probe=exit_r, entry_probe=entry_r)
        self.assertFalse(g.allow_wipe)
        self.assertTrue(any("entry" in r.lower() for r in g.reasons))

    def test_injected_probes_on_run_live(self):
        def bad_exit(h, p):
            return HealthProbeResult("udp", False, "sim fail", h, p)

        def good_entry():
            return HealthProbeResult("local", True, "sim ok", "127.0.0.1", 44044)

        g = run_live_prewipe_gates(
            exit_probe_fn=bad_exit, entry_probe_fn=good_entry
        )
        self.assertFalse(g.allow_wipe)

        def good_exit(h, p):
            return HealthProbeResult("udp", True, "sim ok", h, p)

        g2 = run_live_prewipe_gates(
            exit_probe_fn=good_exit, entry_probe_fn=good_entry
        )
        self.assertTrue(g2.allow_wipe)

    def test_check_exit_uses_probe(self):
        r = check_exit_health(
            host="10.0.0.1",
            port=9,
            probe=lambda h, p: HealthProbeResult("udp", True, "x", h, p),
        )
        self.assertTrue(r.ok)
        self.assertEqual(r.name, "exit_residual")
        self.assertEqual(r.host, "10.0.0.1")

    def test_check_entry_uses_probe(self):
        r = check_entry_node_health(
            probe=lambda: HealthProbeResult("local", False, "nope", "127.0.0.1", 44044)
        )
        self.assertFalse(r.ok)
        self.assertEqual(r.name, "entry_node")

    def test_plan_requires_selfhost_and_order(self):
        from node.wipe_preflight import (
            package_reinstall_required_for_live_wipe,
            plan_has_required_live_steps,
        )

        self.assertTrue(package_reinstall_required_for_live_wipe())
        good = [
            "exclusive_lock_acquire",
            "exit_failover_preflight",
            "entry_node_preflight",
            "rebuild_host",
            "selfhost_reapply",
            "health_check",
            "exclusive_lock_release",
        ]
        ok, missing = plan_has_required_live_steps(good)
        self.assertTrue(ok, missing)
        no_sh = [x for x in good if x != "selfhost_reapply"]
        ok2, miss2 = plan_has_required_live_steps(no_sh)
        self.assertFalse(ok2)
        self.assertIn("selfhost_reapply", miss2)
        # selfhost before rebuild is invalid
        bad_order = [
            "exit_failover_preflight",
            "entry_node_preflight",
            "exclusive_lock_acquire",
            "selfhost_reapply",
            "rebuild_host",
            "health_check",
            "exclusive_lock_release",
        ]
        ok3, miss3 = plan_has_required_live_steps(bad_order)
        self.assertFalse(ok3)
        self.assertTrue(any("selfhost" in m for m in miss3))


class TestPlanStructuralGates(unittest.TestCase):
    def test_healthy_weekly_plan_has_preflight_and_reinstall(self):
        plan = build_weekly_entry_rebuild_plan(
            period="7d", dry_run=True, exit_healthy=True, entry_healthy=True
        )
        ids = [s.id for s in plan.steps]
        ok, missing = plan_has_required_live_steps(ids)
        self.assertTrue(ok, missing)
        self.assertIn("exit_failover_preflight", ids)
        self.assertIn("entry_node_preflight", ids)
        self.assertIn("selfhost_reapply", ids)
        self.assertLess(ids.index("exit_failover_preflight"), ids.index("rebuild_host"))
        self.assertLess(ids.index("entry_node_preflight"), ids.index("rebuild_host"))
        self.assertGreater(ids.index("selfhost_reapply"), ids.index("rebuild_host"))
        # Package reinstall wording
        sh = next(s for s in plan.steps if s.id == "selfhost_reapply")
        self.assertIn("package", sh.action.lower() + sh.detail.lower())

    def test_abort_when_entry_unhealthy_no_rebuild(self):
        plan = build_weekly_entry_rebuild_plan(
            period="7d", exit_healthy=True, entry_healthy=False
        )
        self.assertEqual(plan.mode, "weekly_entry_rebuild_aborted")
        ids = [s.id for s in plan.steps]
        self.assertIn("abort_entry_unhealthy", ids)
        self.assertNotIn("rebuild_host", ids)

    def test_abort_when_exit_unhealthy_no_rebuild(self):
        plan = build_weekly_entry_rebuild_plan(
            period="7d", exit_healthy=False, entry_healthy=True
        )
        ids = [s.id for s in plan.steps]
        self.assertIn("abort_exit_unhealthy", ids)
        self.assertNotIn("rebuild_host", ids)

    def test_plan_has_required_detects_missing(self):
        ok, missing = plan_has_required_live_steps(["rebuild_host"])
        self.assertFalse(ok)
        self.assertIn("exit_failover_preflight", missing)
        self.assertIn("selfhost_reapply", missing)


if __name__ == "__main__":
    unittest.main()
