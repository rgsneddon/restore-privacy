"""Entry-primary residual / exit failover selection and re-entry preference."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from client.endpoint import PRODUCT_NODE_HOST  # noqa: E402
from client.multihop import (  # noqa: E402
    PRODUCT_EXIT_HOST,
    MultiHopConfig,
    ResidualUnavailable,
    build_entry_exit_path,
    residual_try_order,
    select_residual_endpoint,
)


class TestResidualFailoverSelection(unittest.TestCase):
    def test_entry_primary_when_healthy(self):
        sel = select_residual_endpoint(
            MultiHopConfig(),
            entry_healthy=True,
            exit_healthy=True,
            entry_draining=False,
        )
        self.assertEqual(sel.endpoint.host, PRODUCT_NODE_HOST)
        self.assertEqual(sel.reason, "entry_primary")
        self.assertFalse(sel.failover_active)

    def test_exit_failover_when_entry_draining(self):
        sel = select_residual_endpoint(
            MultiHopConfig(),
            entry_healthy=True,
            exit_healthy=True,
            entry_draining=True,
        )
        self.assertEqual(sel.endpoint.host, PRODUCT_EXIT_HOST)
        self.assertEqual(sel.reason, "exit_failover")
        self.assertTrue(sel.failover_active)

    def test_exit_failover_when_entry_unhealthy(self):
        sel = select_residual_endpoint(
            MultiHopConfig(),
            entry_healthy=False,
            exit_healthy=True,
            entry_draining=False,
        )
        self.assertEqual(sel.endpoint.host, PRODUCT_EXIT_HOST)
        self.assertTrue(sel.failover_active)

    def test_reentry_when_entry_healthy_again(self):
        # After rebuild: draining ends, entry healthy → prefer entry again
        down = select_residual_endpoint(
            MultiHopConfig(),
            entry_healthy=False,
            exit_healthy=True,
            entry_draining=True,
        )
        self.assertEqual(down.reason, "exit_failover")
        up = select_residual_endpoint(
            MultiHopConfig(),
            entry_healthy=True,
            exit_healthy=True,
            entry_draining=False,
        )
        self.assertEqual(up.endpoint.host, PRODUCT_NODE_HOST)
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
        path = build_entry_exit_path(PRODUCT_EXIT_HOST)
        cfg = MultiHopConfig(hops=path, enabled=True)
        sel = select_residual_endpoint(
            cfg,
            entry_healthy=True,
            exit_healthy=True,
            entry_draining=False,
        )
        self.assertEqual(sel.endpoint.host, PRODUCT_EXIT_HOST)
        self.assertEqual(sel.reason, "multihop_residual_via_exit")
        self.assertFalse(sel.failover_active)

    def test_multihop_entry_drain_still_exit_failover(self):
        path = build_entry_exit_path(PRODUCT_EXIT_HOST)
        cfg = MultiHopConfig(hops=path, enabled=True)
        sel = select_residual_endpoint(
            cfg,
            entry_healthy=True,
            exit_healthy=True,
            entry_draining=True,
        )
        self.assertEqual(sel.endpoint.host, PRODUCT_EXIT_HOST)
        self.assertEqual(sel.reason, "exit_failover")

    def test_try_order_failover_includes_alternate(self):
        order = residual_try_order(
            MultiHopConfig(),
            entry_healthy=True,
            exit_healthy=True,
            entry_draining=False,
        )
        self.assertGreaterEqual(len(order), 1)
        self.assertEqual(order[0].host, PRODUCT_NODE_HOST)
        # Healthy exit is alternate for HELLO failover
        hosts = [e.host for e in order]
        self.assertIn(PRODUCT_EXIT_HOST, hosts)

        drained = residual_try_order(
            MultiHopConfig(),
            entry_healthy=False,
            exit_healthy=True,
            entry_draining=True,
        )
        self.assertEqual(drained[0].host, PRODUCT_EXIT_HOST)

    def test_selection_to_dict(self):
        d = select_residual_endpoint(
            MultiHopConfig(), entry_draining=True
        ).to_dict()
        self.assertEqual(d["host"], PRODUCT_EXIT_HOST)
        self.assertTrue(d["failover_active"])


if __name__ == "__main__":
    unittest.main()
