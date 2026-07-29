"""Sequential fleet wipe (IS → DE → US) + peer preflight (shipped helpers)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from client.multihop import (  # noqa: E402
    COUNTRY_DE,
    COUNTRY_IS,
    COUNTRY_US,
    CountryNode,
    PRODUCT_COUNTRY_CATALOG,
    PRODUCT_DE_HOST,
    PRODUCT_NODE_HOST,
    PRODUCT_US_HOST,
    multihop_config_for_entry_country,
    residual_endpoint,
    resolve_entry_exit,
)
from node.fleet_wipe import (  # noqa: E402
    PREFERRED_FLEET_ORDER,
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
    def test_monopin_order_is_de_us(self):
        self.assertEqual(PREFERRED_FLEET_ORDER, ("IS", "DE", "US"))
        codes = fleet_country_codes(PRODUCT_COUNTRY_CATALOG)
        self.assertEqual(codes, ["IS", "DE", "US"])
        nodes = fleet_wipe_order(PRODUCT_COUNTRY_CATALOG)
        self.assertEqual([n.code for n in nodes], ["IS", "DE", "US"])
        self.assertEqual(nodes[0].host, PRODUCT_NODE_HOST)
        self.assertEqual(nodes[1].host, PRODUCT_DE_HOST)
        self.assertEqual(nodes[2].host, PRODUCT_US_HOST)
        self.assertNotIn("RO", codes)

    def test_third_country_appends_after_preferred(self):
        extra = CountryNode(
            code="XX", name="Extra", host="198.51.100.20", port=44044
        )
        cat = list(PRODUCT_COUNTRY_CATALOG) + [extra]
        self.assertEqual(fleet_country_codes(cat), ["IS", "DE", "US", "XX"])

    def test_next_target_and_refuse_concurrent(self):
        self.assertEqual(
            next_wipe_target(completed=[], in_progress=None), "IS"
        )
        # DE before IS complete refused
        d = assert_sequential_fleet_start("DE", completed=[], in_progress=None)
        self.assertFalse(d.allow)
        self.assertIn("out-of-order", d.reason.lower())
        # IS may start
        d2 = assert_sequential_fleet_start("IS", completed=[], in_progress=None)
        self.assertTrue(d2.allow)
        # Concurrent: IS in progress, cannot start DE
        d3 = assert_sequential_fleet_start(
            "DE", completed=[], in_progress="IS"
        )
        self.assertFalse(d3.allow)
        self.assertIn("concurrent", d3.reason.lower())
        # After IS complete, DE is next
        done, nxt = mark_wipe_complete("IS", completed=[])
        self.assertEqual(done, ["IS"])
        self.assertEqual(nxt, "DE")
        d4 = assert_sequential_fleet_start("DE", completed=done, in_progress=None)
        self.assertTrue(d4.allow)
        done2, nxt2 = mark_wipe_complete("DE", completed=done)
        self.assertEqual(nxt2, "US")
        done3, nxt3 = mark_wipe_complete("US", completed=done2)
        self.assertTrue(is_fleet_cycle_complete(done3))
        self.assertIsNone(nxt3)

    def test_appended_country_after_is_de_us(self):
        extra = CountryNode(
            code="XX", name="Extra", host="198.51.100.20", port=44044
        )
        cat = list(PRODUCT_COUNTRY_CATALOG) + [extra]
        done, nxt = mark_wipe_complete("IS", completed=[], catalog=cat)
        done, nxt = mark_wipe_complete("DE", completed=done, catalog=cat)
        done, nxt = mark_wipe_complete("US", completed=done, catalog=cat)
        self.assertEqual(nxt, "XX")
        d = assert_sequential_fleet_start(
            "XX", completed=done, in_progress=None, catalog=cat
        )
        self.assertTrue(d.allow)


class TestPeerPrewipe(unittest.TestCase):
    def test_refuse_without_healthy_peer(self):
        r = evaluate_peer_prewipe_gate(
            "IS", {"IS": True, "DE": False, "US": False}
        )
        self.assertFalse(r.allow_wipe)
        self.assertIn("fail closed", r.reasons[0].lower())

    def test_allow_with_healthy_peer(self):
        r = evaluate_peer_prewipe_gate(
            "IS", {"IS": True, "DE": True, "US": False}
        )
        self.assertTrue(r.allow_wipe)
        self.assertIn("DE", r.healthy_peers)

    def test_catalog_peer_prewipe_bridge(self):
        g = evaluate_catalog_peer_prewipe(
            "DE",
            {"IS": True, "DE": False, "US": True},
            local_ok=True,
        )
        self.assertTrue(g.allow_wipe)
        g2 = evaluate_catalog_peer_prewipe(
            "DE",
            {"IS": False, "DE": True, "US": False},
            local_ok=True,
        )
        self.assertFalse(g2.allow_wipe)


class TestCatalogAlignment(unittest.TestCase):
    def test_client_residual_and_fleet_share_codes(self):
        fleet = set(fleet_country_codes(PRODUCT_COUNTRY_CATALOG))
        self.assertEqual(fleet, {COUNTRY_IS, COUNTRY_DE, COUNTRY_US})
        # DE entry preference (default monopin) resolves
        e, x = resolve_entry_exit(COUNTRY_DE, multihop_enabled=False)
        self.assertEqual(e.host, PRODUCT_DE_HOST)
        cfg = multihop_config_for_entry_country(COUNTRY_DE, multihop_enabled=False)
        self.assertEqual(residual_endpoint(cfg).host, PRODUCT_DE_HOST)
        # Multihop: entry DE exit not DE
        e2, x2 = resolve_entry_exit(COUNTRY_DE, multihop_enabled=True)
        self.assertEqual(e2.code, COUNTRY_DE)
        self.assertIsNotNone(x2)
        self.assertNotEqual(x2.code, COUNTRY_DE)

    def test_fleet_summary_in_ephemeral(self):
        from node.ephemeral_node import build_fleet_sequential_plan_summary

        s = build_fleet_sequential_plan_summary(completed=[], in_progress=None)
        self.assertEqual(s["fleet_order"], ["IS", "DE", "US"])
        self.assertEqual(s["next_target"], "IS")
        self.assertFalse(s["decisions"]["DE"]["allow"])
        self.assertTrue(s["decisions"]["IS"]["allow"])


class TestWeeklyFleetPlannerWiring(unittest.TestCase):
    def test_weekly_plan_targets_is_first_then_de(self):
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
        # After IS complete, DE is next
        p2 = build_weekly_entry_rebuild_plan(
            role="auto",
            completed=["IS"],
            in_progress=None,
            exit_healthy=True,
            entry_healthy=True,
            dry_run=True,
        )
        self.assertIn("acquire_rebuild_lock('de'", p2.format_text())
        # Out of order DE before IS complete raises
        with self.assertRaises(ValueError):
            build_weekly_entry_rebuild_plan(
                role="de",
                completed=[],
                in_progress=None,
                exit_healthy=True,
                entry_healthy=True,
            )
        # Bulk exit never becomes DE even if IS already complete
        d_exit = resolve_weekly_target(completed=["IS"], role_hint="exit")
        self.assertFalse(d_exit.allow)
        self.assertIsNone(d_exit.target_code)
        with self.assertRaises(ValueError):
            build_weekly_entry_rebuild_plan(
                role="exit", completed=["IS"], exit_healthy=True, entry_healthy=True
            )
        # Auto rolls after full cycle
        d_roll = resolve_weekly_target(
            completed=["IS", "DE", "US"], role_hint="auto"
        )
        self.assertTrue(d_roll.allow)
        self.assertEqual(d_roll.target_code, "IS")
        self.assertEqual(d_roll.completed, ())

    def test_plan_after_cycle_roll_embeds_empty_completed_in_mark_steps(self):
        """After [IS,DE,US] auto-roll, mark_wipe_complete must not keep stale completed."""
        from node.ephemeral_node import build_weekly_entry_rebuild_plan

        plan = build_weekly_entry_rebuild_plan(
            role="auto",
            completed=["IS", "DE", "US"],
            in_progress=None,
            exit_healthy=True,
            entry_healthy=True,
            dry_run=True,
        )
        self.assertEqual(plan.mode, "weekly_fleet_rebuild")
        text = plan.format_text()
        self.assertIn("target=IS", text)
        mark_complete = next(
            s for s in plan.steps if s.id == "mark_fleet_peer_complete"
        )
        self.assertIn("mark_wipe_complete('IS'", mark_complete.command)
        self.assertIn("completed=[]", mark_complete.command)
        self.assertNotIn("completed=['IS', 'DE', 'US']", mark_complete.command)


if __name__ == "__main__":
    unittest.main()
