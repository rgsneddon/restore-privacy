"""Entry-primary residual / wipe-drain hop / re-entry preference."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from client.endpoint import PRODUCT_NODE_HOST  # noqa: E402
from client.multihop import (  # noqa: E402
    PRODUCT_COUNTRY_CATALOG,
    PRODUCT_DE_HOST,
    PRODUCT_EXIT_HOST,
    MultiHopConfig,
    ResidualUnavailable,
    build_entry_exit_path,
    residual_try_order,
    select_residual_endpoint,
)
from client.wipe_hop import REASON_WIPE_DRAIN_FAILOVER  # noqa: E402


def _catalog_hosts_except(preferred: str) -> set[str]:
    pref = (preferred or "").strip()
    return {
        (n.host or "").strip()
        for n in PRODUCT_COUNTRY_CATALOG
        if (n.host or "").strip() and (n.host or "").strip() != pref
    }


class TestResidualFailoverSelection(unittest.TestCase):
    def test_entry_primary_when_healthy(self):
        sel = select_residual_endpoint(
            MultiHopConfig(),
            entry_healthy=True,
            exit_healthy=True,
            entry_draining=False,
        )
        self.assertEqual(sel.endpoint.host, PRODUCT_DE_HOST)
        self.assertNotEqual(sel.endpoint.host, PRODUCT_NODE_HOST)
        self.assertEqual(sel.reason, "entry_primary")
        self.assertFalse(sel.failover_active)

    def test_wipe_drain_hops_to_random_non_preferred(self):
        """Sole offered peer: drain must fail closed — do not invent Iceland."""
        with self.assertRaises(ResidualUnavailable):
            select_residual_endpoint(
                MultiHopConfig(),
                entry_healthy=True,
                exit_healthy=True,
                entry_draining=True,
            )
        self.assertEqual(_catalog_hosts_except(PRODUCT_DE_HOST), set())

    def test_exit_failover_when_entry_unhealthy(self):
        """Sole offered peer: entry down must fail closed — do not dial Iceland."""
        with self.assertRaises(ResidualUnavailable):
            select_residual_endpoint(
                MultiHopConfig(),
                entry_healthy=False,
                exit_healthy=True,
                entry_draining=False,
            )

    def test_reentry_when_entry_healthy_again(self):
        with self.assertRaises(ResidualUnavailable):
            select_residual_endpoint(
                MultiHopConfig(),
                entry_healthy=False,
                exit_healthy=True,
                entry_draining=True,
            )
        up = select_residual_endpoint(
            MultiHopConfig(),
            entry_healthy=True,
            exit_healthy=True,
            entry_draining=False,
        )
        self.assertEqual(up.endpoint.host, PRODUCT_DE_HOST)
        self.assertNotEqual(up.endpoint.host, PRODUCT_NODE_HOST)
        self.assertEqual(up.reason, "entry_primary")
        self.assertFalse(up.failover_active)

    def test_fail_closed_both_unhealthy(self):
        with self.assertRaises(ResidualUnavailable) as cm:
            select_residual_endpoint(
                MultiHopConfig(),
                entry_healthy=False,
                exit_healthy=False,
                entry_draining=True,
            )
        self.assertIn("fail closed", str(cm.exception).lower())

    def test_multihop_active_residual_via_exit_when_entry_up(self):
        from client.multihop import Hop

        path = [
            Hop(PRODUCT_DE_HOST, 44044, role="entry"),
            Hop("198.51.100.9", 44044, role="exit"),
        ]
        cfg = MultiHopConfig(hops=path, enabled=True)
        sel = select_residual_endpoint(
            cfg,
            entry_healthy=True,
            exit_healthy=True,
            entry_draining=False,
        )
        self.assertEqual(sel.endpoint.host, "198.51.100.9")
        self.assertEqual(sel.reason, "multihop_residual_via_exit")
        self.assertFalse(sel.failover_active)
        self.assertNotEqual(sel.endpoint.host, PRODUCT_NODE_HOST)

    def test_multihop_entry_drain_wipe_hop(self):
        path = build_entry_exit_path(PRODUCT_EXIT_HOST)
        cfg = MultiHopConfig(hops=path, enabled=True)
        # Default entry is DE; exit is also DE — no other catalog peer.
        with self.assertRaises(ResidualUnavailable):
            select_residual_endpoint(
                cfg,
                entry_healthy=True,
                exit_healthy=True,
                entry_draining=True,
            )

    def test_try_order_failover_includes_alternate(self):
        order = residual_try_order(
            MultiHopConfig(),
            entry_healthy=True,
            exit_healthy=True,
            entry_draining=False,
        )
        self.assertEqual([e.host for e in order], [PRODUCT_DE_HOST])
        self.assertNotIn(PRODUCT_NODE_HOST, [e.host for e in order])

        drained = residual_try_order(
            MultiHopConfig(),
            entry_healthy=False,
            exit_healthy=True,
            entry_draining=True,
        )
        self.assertEqual(drained, [])
        self.assertNotIn(PRODUCT_NODE_HOST, [e.host for e in drained])

    def test_selection_to_dict(self):
        d = select_residual_endpoint(MultiHopConfig()).to_dict()
        self.assertEqual(d["host"], PRODUCT_DE_HOST)
        self.assertNotEqual(d["host"], PRODUCT_NODE_HOST)
        self.assertEqual(d["reason"], "entry_primary")
        self.assertFalse(d["failover_active"])


if __name__ == "__main__":
    unittest.main()
