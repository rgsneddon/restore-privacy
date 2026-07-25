"""Sequential fleet wipe (IS → RO → new peers) + peer preflight (shipped helpers)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from client.multihop import (  # noqa: E402
    COUNTRY_IS,
    COUNTRY_RO,
    CountryNode,
    PRODUCT_COUNTRY_CATALOG,
    multihop_config_for_entry_country,
    residual_endpoint,
    resolve_entry_exit,
)
from client.multihop import PRODUCT_EXIT_HOST, PRODUCT_NODE_HOST  # noqa: E402
from node.fleet_wipe import (  # noqa: E402
    assert_sequential_fleet_start,
    evaluate_peer_prewipe_gate,
    fleet_country_codes,
    fleet_wipe_order,
    is_fleet_cycle_complete,
    mark_wipe_complete,
    next_wipe_target,
)
from node.wipe_preflight import evaluate_catalog_peer_prewipe  # noqa: E402


class TestFleetWipeOrder(unittest.TestCase):
    def test_two_country_order_is_then_ro(self):
        codes = fleet_country_codes(PRODUCT_COUNTRY_CATALOG)
        self.assertEqual(codes, ["IS", "RO"])
        nodes = fleet_wipe_order(PRODUCT_COUNTRY_CATALOG)
        self.assertEqual(nodes[0].code, "IS")
        self.assertEqual(nodes[1].code, "RO")
        self.assertEqual(nodes[0].host, PRODUCT_NODE_HOST)
        self.assertEqual(nodes[1].host, PRODUCT_EXIT_HOST)

    def test_third_country_appends(self):
        extra = CountryNode(
            code="XX", name="Extra", host="198.51.100.20", port=44044
        )
        cat = list(PRODUCT_COUNTRY_CATALOG) + [extra]
        self.assertEqual(fleet_country_codes(cat), ["IS", "RO", "XX"])

    def test_next_target_and_refuse_concurrent(self):
        self.assertEqual(
            next_wipe_target(completed=[], in_progress=None), "IS"
        )
        # RO before IS complete refused
        d = assert_sequential_fleet_start("RO", completed=[], in_progress=None)
        self.assertFalse(d.allow)
        self.assertIn("out-of-order", d.reason.lower())
        # IS may start
        d2 = assert_sequential_fleet_start("IS", completed=[], in_progress=None)
        self.assertTrue(d2.allow)
        # Concurrent: IS in progress, cannot start RO
        d3 = assert_sequential_fleet_start(
            "RO", completed=[], in_progress="IS"
        )
        self.assertFalse(d3.allow)
        self.assertIn("concurrent", d3.reason.lower())
        # After IS complete, RO is next
        done, nxt = mark_wipe_complete("IS", completed=[])
        self.assertEqual(done, ["IS"])
        self.assertEqual(nxt, "RO")
        d4 = assert_sequential_fleet_start("RO", completed=done, in_progress=None)
        self.assertTrue(d4.allow)
        done2, nxt2 = mark_wipe_complete("RO", completed=done)
        self.assertTrue(is_fleet_cycle_complete(done2))
        self.assertIsNone(nxt2)

    def test_third_country_after_is_ro(self):
        extra = CountryNode(
            code="XX", name="Extra", host="198.51.100.20", port=44044
        )
        cat = list(PRODUCT_COUNTRY_CATALOG) + [extra]
        done, nxt = mark_wipe_complete("IS", completed=[], catalog=cat)
        done, nxt = mark_wipe_complete("RO", completed=done, catalog=cat)
        self.assertEqual(nxt, "XX")
        d = assert_sequential_fleet_start(
            "XX", completed=done, in_progress=None, catalog=cat
        )
        self.assertTrue(d.allow)


class TestPeerPrewipe(unittest.TestCase):
    def test_refuse_without_healthy_peer(self):
        r = evaluate_peer_prewipe_gate("IS", {"IS": True, "RO": False})
        self.assertFalse(r.allow_wipe)
        self.assertIn("fail closed", r.reasons[0].lower())

    def test_allow_with_healthy_peer(self):
        r = evaluate_peer_prewipe_gate("IS", {"IS": True, "RO": True})
        self.assertTrue(r.allow_wipe)
        self.assertIn("RO", r.healthy_peers)

    def test_catalog_peer_prewipe_bridge(self):
        g = evaluate_catalog_peer_prewipe(
            "RO",
            {"IS": True, "RO": False},
            local_ok=True,
        )
        self.assertTrue(g.allow_wipe)
        g2 = evaluate_catalog_peer_prewipe(
            "RO",
            {"IS": False, "RO": True},
            local_ok=True,
        )
        self.assertFalse(g2.allow_wipe)


class TestCatalogAlignment(unittest.TestCase):
    def test_client_residual_and_fleet_share_codes(self):
        fleet = set(fleet_country_codes(PRODUCT_COUNTRY_CATALOG))
        self.assertEqual(fleet, {COUNTRY_IS, COUNTRY_RO})
        # RO entry preference still resolves (not Iceland-hardcoded)
        e, x = resolve_entry_exit(COUNTRY_RO, multihop_enabled=False)
        self.assertEqual(e.host, PRODUCT_EXIT_HOST)
        cfg = multihop_config_for_entry_country(COUNTRY_RO, multihop_enabled=False)
        self.assertEqual(residual_endpoint(cfg).host, PRODUCT_EXIT_HOST)
        # Multihop: entry RO exit IS
        e2, x2 = resolve_entry_exit(COUNTRY_RO, multihop_enabled=True)
        self.assertEqual(e2.code, COUNTRY_RO)
        self.assertIsNotNone(x2)
        self.assertEqual(x2.code, COUNTRY_IS)

    def test_fleet_summary_in_ephemeral(self):
        from node.ephemeral_node import build_fleet_sequential_plan_summary

        s = build_fleet_sequential_plan_summary(completed=[], in_progress=None)
        self.assertEqual(s["fleet_order"], ["IS", "RO"])
        self.assertEqual(s["next_target"], "IS")
        self.assertFalse(s["decisions"]["RO"]["allow"])
        self.assertTrue(s["decisions"]["IS"]["allow"])


class TestWeeklyFleetPlannerWiring(unittest.TestCase):
    def test_weekly_plan_targets_is_first_then_ro(self):
        from node.ephemeral_node import build_weekly_entry_rebuild_plan
        from node.fleet_wipe import resolve_weekly_target

        p1 = build_weekly_entry_rebuild_plan(
            role="auto",
            completed=[],
            in_progress=None,
            exit_healthy=True,
            entry_healthy=True,
            dry_run=True,
        )
        ids = [s.id for s in p1.steps]
        self.assertIn("fleet_target_resolve", ids)
        self.assertIn("peer_failover_preflight", ids)
        self.assertIn("mark_fleet_peer_complete", ids)
        self.assertIn("acquire_rebuild_lock('is'", p1.format_text())
        self.assertEqual(p1.mode, "weekly_fleet_rebuild")
        # After IS complete, RO is next
        p2 = build_weekly_entry_rebuild_plan(
            role="auto",
            completed=["IS"],
            in_progress=None,
            exit_healthy=True,
            entry_healthy=True,
            dry_run=True,
        )
        self.assertIn("acquire_rebuild_lock('ro'", p2.format_text())
        # Out of order RO before IS complete raises
        with self.assertRaises(ValueError):
            build_weekly_entry_rebuild_plan(
                role="ro",
                completed=[],
                in_progress=None,
                exit_healthy=True,
                entry_healthy=True,
            )
        # Bulk exit never becomes RO even if IS already complete
        d_exit = resolve_weekly_target(completed=["IS"], role_hint="exit")
        self.assertFalse(d_exit.allow)
        self.assertIsNone(d_exit.target_code)
        with self.assertRaises(ValueError):
            build_weekly_entry_rebuild_plan(
                role="exit", completed=["IS"], exit_healthy=True, entry_healthy=True
            )
        # Auto rolls after full cycle
        d_roll = resolve_weekly_target(completed=["IS", "RO"], role_hint="auto")
        self.assertTrue(d_roll.allow)
        self.assertEqual(d_roll.target_code, "IS")
        self.assertEqual(d_roll.completed, ())

    def test_plan_after_cycle_roll_embeds_empty_completed_in_mark_steps(self):
        """After [IS,RO] auto-roll, mark_wipe_complete must not keep stale completed.

        Otherwise mark_wipe_complete('IS', ['IS','RO']) no-ops and next→None.
        """
        from node.ephemeral_node import build_weekly_entry_rebuild_plan

        plan = build_weekly_entry_rebuild_plan(
            role="auto",
            completed=["IS", "RO"],
            in_progress=None,
            exit_healthy=True,
            entry_healthy=True,
            dry_run=True,
        )
        self.assertEqual(plan.mode, "weekly_fleet_rebuild")
        text = plan.format_text()
        self.assertIn("target=IS", text)
        # mark steps must embed empty completed after roll (not ['IS','RO'])
        mark_complete = next(
            s for s in plan.steps if s.id == "mark_fleet_peer_complete"
        )
        self.assertIn("mark_wipe_complete('IS'", mark_complete.command)
        self.assertIn("completed=[]", mark_complete.command)
        self.assertNotIn("completed=['IS', 'RO']", mark_complete.command)
        self.assertNotIn('completed=["IS", "RO"]', mark_complete.command)
        drain = next(s for s in plan.steps if s.id == "mark_entry_draining")
        self.assertIn("completed=[]", drain.command)
        # fleet_target_resolve detail should show rolled empty completed
        resolve = next(s for s in plan.steps if s.id == "fleet_target_resolve")
        self.assertIn("completed=[]", resolve.detail)

    def test_weekly_script_uses_fleet_and_live_peer_prewipe(self):
        src = (
            ROOT / "scripts" / "weekly_entry_rebuild.py"
        ).read_text(encoding="utf-8")
        self.assertIn("resolve_weekly_target", src)
        self.assertIn("load_fleet_wipe_state", src)
        self.assertIn("run_live_prewipe_gates", src)
        self.assertIn("target_code=", src)
        self.assertIn("assert_weekly_entry_role_only(args.role)", src)
        # Raw role check before resolve
        role_i = src.index("assert_weekly_entry_role_only(args.role)")
        resolve_i = src.index("resolve_weekly_target(")
        self.assertLess(role_i, resolve_i)

    def test_host_identity_helpers_gate_remote_peer(self):
        from node.fleet_wipe import (
            catalog_host_for_code,
            catalog_pub_name_for_code,
            is_target_host_local,
        )

        self.assertEqual(catalog_host_for_code("IS"), PRODUCT_NODE_HOST)
        self.assertEqual(catalog_host_for_code("RO"), PRODUCT_EXIT_HOST)
        self.assertEqual(catalog_pub_name_for_code("IS"), "node_elgamal.pub")
        self.assertEqual(catalog_pub_name_for_code("RO"), "exit_node_elgamal.pub")
        ok_is, msg_is = is_target_host_local("IS", local_country="IS")
        self.assertTrue(ok_is, msg_is)
        ok_ro_on_is, msg_ro = is_target_host_local("RO", local_country="IS")
        self.assertFalse(ok_ro_on_is, msg_ro)
        self.assertIn("refuse", msg_ro.lower())
        ok_ro, msg_ro2 = is_target_host_local("RO", local_country="RO")
        self.assertTrue(ok_ro, msg_ro2)
        # Host set match (RO monopin in local addresses)
        ok_h, _ = is_target_host_local(
            "RO",
            local_hosts=[PRODUCT_EXIT_HOST],
            env={"RPT_FLEET_ORCHESTRATOR_DEFAULT": ""},
        )
        self.assertTrue(ok_h)
        # Orchestrator IS host set must not claim RO is local
        ok_wrong, msg_w = is_target_host_local(
            "RO",
            local_hosts=[PRODUCT_NODE_HOST],
            env={"RPT_FLEET_ORCHESTRATOR_DEFAULT": "IS"},
        )
        self.assertFalse(ok_wrong, msg_w)


if __name__ == "__main__":
    unittest.main()
