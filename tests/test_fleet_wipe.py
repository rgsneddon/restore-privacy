"""Sequential fleet wipe (IS → DE) + peer preflight (shipped helpers)."""

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
        self.assertEqual(PREFERRED_FLEET_ORDER, ("DE",))
        codes = fleet_country_codes(PRODUCT_COUNTRY_CATALOG)
        self.assertEqual(codes, ["DE"])
        nodes = fleet_wipe_order(PRODUCT_COUNTRY_CATALOG)
        self.assertEqual([n.code for n in nodes], ["DE"])
        self.assertEqual(nodes[0].host, PRODUCT_DE_HOST)
        self.assertEqual(len(nodes), 1)
        self.assertNotIn("IS", codes)
        self.assertNotIn("RO", codes)
        self.assertNotIn("US", codes)
        self.assertNotEqual(nodes[0].host, PRODUCT_NODE_HOST)

    def test_third_country_appends_after_preferred(self):
        extra = CountryNode(
            code="XX", name="Extra", host="198.51.100.20", port=44044
        )
        cat = list(PRODUCT_COUNTRY_CATALOG) + [extra]
        self.assertEqual(fleet_country_codes(cat), ["DE", "XX"])

    def test_next_target_and_refuse_concurrent(self):
        self.assertEqual(
            next_wipe_target(completed=[], in_progress=None), "DE"
        )
        # Iceland is not a wipe target
        d_is = assert_sequential_fleet_start("IS", completed=[], in_progress=None)
        self.assertFalse(d_is.allow)
        # DE may start as the only offered peer (prewipe gate still fail-closes live)
        d2 = assert_sequential_fleet_start("DE", completed=[], in_progress=None)
        self.assertTrue(d2.allow)
        done, nxt = mark_wipe_complete("DE", completed=[])
        self.assertEqual(done, ["DE"])
        self.assertIsNone(nxt)
        self.assertTrue(is_fleet_cycle_complete(done))

    def test_appended_country_after_is_de(self):
        extra = CountryNode(
            code="XX", name="Extra", host="198.51.100.20", port=44044
        )
        cat = list(PRODUCT_COUNTRY_CATALOG) + [extra]
        done, nxt = mark_wipe_complete("DE", completed=[], catalog=cat)
        self.assertEqual(nxt, "XX")
        d = assert_sequential_fleet_start(
            "XX", completed=done, in_progress=None, catalog=cat
        )
        self.assertTrue(d.allow)


class TestPeerPrewipe(unittest.TestCase):
    def test_refuse_without_healthy_peer(self):
        r = evaluate_peer_prewipe_gate(
            "DE", {"DE": True, "IS": False, "US": False}
        )
        self.assertFalse(r.allow_wipe)
        self.assertIn("fail closed", r.reasons[0].lower())

    def test_allow_with_healthy_peer(self):
        extra = CountryNode(
            code="XX", name="Extra", host="198.51.100.20", port=44044
        )
        cat = list(PRODUCT_COUNTRY_CATALOG) + [extra]
        r = evaluate_peer_prewipe_gate(
            "DE", {"DE": True, "XX": True}, catalog=cat
        )
        self.assertTrue(r.allow_wipe)
        self.assertIn("XX", r.healthy_peers)
        self.assertNotIn("IS", r.healthy_peers)

    def test_catalog_peer_prewipe_bridge(self):
        extra = CountryNode(
            code="XX", name="Extra", host="198.51.100.20", port=44044
        )
        cat = list(PRODUCT_COUNTRY_CATALOG) + [extra]
        r = evaluate_peer_prewipe_gate(
            "DE", {"DE": False, "XX": True}, catalog=cat
        )
        self.assertTrue(r.allow_wipe)
        g2 = evaluate_catalog_peer_prewipe(
            "DE",
            {"DE": True},
            local_ok=True,
        )
        self.assertFalse(g2.allow_wipe)


class TestCatalogAlignment(unittest.TestCase):
    def test_client_residual_and_fleet_share_codes(self):
        fleet = set(fleet_country_codes(PRODUCT_COUNTRY_CATALOG))
        self.assertEqual(fleet, {COUNTRY_DE})
        self.assertNotIn(COUNTRY_IS, fleet)
        # DE entry preference (default monopin) resolves
        e, x = resolve_entry_exit(COUNTRY_DE, multihop_enabled=False)
        self.assertEqual(e.host, PRODUCT_DE_HOST)
        cfg = multihop_config_for_entry_country(COUNTRY_DE, multihop_enabled=False)
        self.assertEqual(residual_endpoint(cfg).host, PRODUCT_DE_HOST)
        # Multihop with sole peer stays single-hop (no Iceland exit)
        e2, x2 = resolve_entry_exit(COUNTRY_DE, multihop_enabled=True)
        self.assertEqual(e2.code, COUNTRY_DE)
        self.assertIsNone(x2)

    def test_fleet_summary_in_ephemeral(self):
        from node.ephemeral_node import build_fleet_sequential_plan_summary

        s = build_fleet_sequential_plan_summary(completed=[], in_progress=None)
        self.assertEqual(s["fleet_order"], ["DE"])
        self.assertEqual(s["next_target"], "DE")
        self.assertNotIn("IS", s["fleet_order"])
        self.assertTrue(s["decisions"]["DE"]["allow"])
        self.assertNotIn("IS", s["decisions"])


class TestWeeklyFleetPlannerWiring(unittest.TestCase):
    def test_weekly_plan_targets_is_first_then_de(self):
        from node.ephemeral_node import build_weekly_entry_rebuild_plan
        from node.fleet_wipe import resolve_weekly_target

        d = resolve_weekly_target(completed=[], role_hint="auto")
        self.assertEqual(d.target_code, "DE")
        self.assertNotEqual(d.target_code, "IS")
        # Sole offered peer: planner must not wipe DE (no failover) and never IS.
        p1 = build_weekly_entry_rebuild_plan(
            role="auto",
            completed=[],
            in_progress=None,
            exit_healthy=True,
            entry_healthy=True,
            dry_run=True,
        )
        ids = [s.id for s in p1.steps]
        text = p1.format_text()
        self.assertIn("fleet_target_resolve", ids)
        self.assertIn("peer_failover_preflight", ids)
        self.assertNotIn("acquire_rebuild_lock('is'", text)
        self.assertEqual(p1.mode, "weekly_fleet_rebuild_aborted")
        self.assertIn("abort_peer_unhealthy", ids)
        # Iceland role heals to DE, still abort (no second peer)
        p2 = build_weekly_entry_rebuild_plan(
            role="is",
            completed=[],
            in_progress=None,
            exit_healthy=True,
            entry_healthy=True,
            dry_run=True,
        )
        self.assertNotIn("acquire_rebuild_lock('is'", p2.format_text())
        self.assertEqual(p2.mode, "weekly_fleet_rebuild_aborted")
        # Bulk exit never becomes a wipe target
        d_exit = resolve_weekly_target(completed=["DE"], role_hint="exit")
        self.assertFalse(d_exit.allow)
        self.assertIsNone(d_exit.target_code)
        with self.assertRaises(ValueError):
            build_weekly_entry_rebuild_plan(
                role="exit", completed=["DE"], exit_healthy=True, entry_healthy=True
            )
        # Auto rolls after full cycle (offered DE only) — still not Iceland
        d_roll = resolve_weekly_target(
            completed=["DE"], role_hint="auto"
        )
        self.assertTrue(d_roll.allow)
        self.assertEqual(d_roll.target_code, "DE")
        self.assertEqual(d_roll.completed, ())

    def test_plan_after_cycle_roll_embeds_empty_completed_in_mark_steps(self):
        """Sole-peer DE cycle: abort wipe; never target Iceland."""
        from node.ephemeral_node import build_weekly_entry_rebuild_plan

        plan = build_weekly_entry_rebuild_plan(
            role="auto",
            completed=["DE"],
            in_progress=None,
            exit_healthy=True,
            entry_healthy=True,
            dry_run=True,
        )
        self.assertEqual(plan.mode, "weekly_fleet_rebuild_aborted")
        text = plan.format_text()
        self.assertNotIn("target=IS", text)
        self.assertNotIn("acquire_rebuild_lock('is'", text)
        ids = [s.id for s in plan.steps]
        self.assertIn("abort_peer_unhealthy", ids)
        self.assertNotIn("mark_fleet_peer_complete", ids)


if __name__ == "__main__":
    unittest.main()
