"""Near-capacity residual migration + Connect CLI advisory (shipped helpers)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from client.endpoint import PRODUCT_NODE_HOST  # noqa: E402
from client.multihop import (  # noqa: E402
    DEFAULT_NEAR_CAPACITY_THRESHOLD,
    PRODUCT_EXIT_HOST,
    REASON_CAPACITY_MIGRATION,
    MultiHopConfig,
    capacity_migration_advisory,
    is_freer_capacity,
    is_near_capacity,
    residual_try_order,
    select_residual_endpoint,
)
from client.connect import RptClient  # noqa: E402


class TestCapacityPureHelpers(unittest.TestCase):
    def test_near_capacity_threshold(self):
        self.assertFalse(is_near_capacity(None))
        self.assertFalse(is_near_capacity(0.5))
        self.assertTrue(is_near_capacity(DEFAULT_NEAR_CAPACITY_THRESHOLD))
        self.assertTrue(is_near_capacity(0.99))
        self.assertFalse(is_near_capacity(0.84, threshold=0.85))

    def test_freer_requires_margin(self):
        self.assertTrue(is_freer_capacity(0.2, 0.9))
        self.assertFalse(is_freer_capacity(0.88, 0.9, margin=0.05))  # only 0.02 freer
        self.assertFalse(is_freer_capacity(None, 0.9))
        self.assertFalse(is_freer_capacity(0.2, None))


class TestCapacityResidualSelection(unittest.TestCase):
    def test_migrate_when_preferred_near_capacity_and_alternate_freer(self):
        caps = {
            PRODUCT_NODE_HOST: 0.95,
            PRODUCT_EXIT_HOST: 0.20,
        }
        sel = select_residual_endpoint(
            MultiHopConfig(),
            entry_healthy=True,
            exit_healthy=True,
            entry_draining=False,
            peer_capacity=caps,
        )
        self.assertEqual(sel.reason, REASON_CAPACITY_MIGRATION)
        self.assertEqual(sel.endpoint.host, PRODUCT_EXIT_HOST)
        self.assertNotEqual(sel.endpoint.host, PRODUCT_NODE_HOST)
        self.assertTrue(sel.failover_active)
        self.assertEqual(sel.preferred_host, PRODUCT_NODE_HOST)
        self.assertIsNotNone(sel.capacity_util_preferred)
        self.assertGreaterEqual(sel.capacity_util_preferred or 0, 0.85)

    def test_keep_preferred_when_not_near_capacity(self):
        caps = {
            PRODUCT_NODE_HOST: 0.40,
            PRODUCT_EXIT_HOST: 0.10,
        }
        sel = select_residual_endpoint(
            MultiHopConfig(),
            entry_healthy=True,
            exit_healthy=True,
            peer_capacity=caps,
        )
        self.assertEqual(sel.reason, "entry_primary")
        self.assertEqual(sel.endpoint.host, PRODUCT_NODE_HOST)
        self.assertFalse(sel.failover_active)

    def test_keep_preferred_when_no_capacity_signal(self):
        sel = select_residual_endpoint(
            MultiHopConfig(),
            entry_healthy=True,
            exit_healthy=True,
            peer_capacity=None,
        )
        self.assertEqual(sel.reason, "entry_primary")
        self.assertEqual(sel.endpoint.host, PRODUCT_NODE_HOST)

    def test_near_capacity_but_no_freer_peer_keeps_preferred(self):
        # Alternate is equal/worse — do not black-hole; stay on preferred
        caps = {
            PRODUCT_NODE_HOST: 0.92,
            PRODUCT_EXIT_HOST: 0.95,
        }
        sel = select_residual_endpoint(
            MultiHopConfig(),
            entry_healthy=True,
            exit_healthy=True,
            peer_capacity=caps,
        )
        self.assertEqual(sel.reason, "entry_primary")
        self.assertEqual(sel.endpoint.host, PRODUCT_NODE_HOST)

    def test_alternate_never_same_host(self):
        caps = {
            PRODUCT_NODE_HOST: 0.99,
            PRODUCT_EXIT_HOST: 0.10,
        }
        sel = select_residual_endpoint(
            MultiHopConfig(),
            entry_healthy=True,
            exit_healthy=True,
            peer_capacity=caps,
        )
        self.assertEqual(sel.reason, REASON_CAPACITY_MIGRATION)
        self.assertNotEqual(
            (sel.endpoint.host or "").strip(),
            (sel.preferred_host or "").strip(),
        )

    def test_unhealthy_preferred_still_health_failover_not_capacity(self):
        caps = {
            PRODUCT_NODE_HOST: 0.99,
            PRODUCT_EXIT_HOST: 0.10,
        }
        sel = select_residual_endpoint(
            MultiHopConfig(),
            entry_healthy=False,
            exit_healthy=True,
            peer_capacity=caps,
        )
        # Health/wipe hop takes precedence over capacity; alternate is any
        # healthy non-preferred catalog peer (RO or DE), not capacity_migration.
        self.assertEqual(sel.reason, "exit_failover")
        self.assertNotEqual(sel.endpoint.host, PRODUCT_NODE_HOST)
        self.assertNotEqual(sel.reason, REASON_CAPACITY_MIGRATION)

    def test_try_order_capacity_primary_is_freer(self):
        caps = {
            PRODUCT_NODE_HOST: 0.90,
            PRODUCT_EXIT_HOST: 0.15,
        }
        order = residual_try_order(
            MultiHopConfig(),
            entry_healthy=True,
            exit_healthy=True,
            peer_capacity=caps,
        )
        self.assertGreaterEqual(len(order), 1)
        self.assertEqual(order[0].host, PRODUCT_EXIT_HOST)


class TestCapacityAdvisory(unittest.TestCase):
    def test_advisory_only_for_capacity_migration(self):
        primary = select_residual_endpoint(MultiHopConfig())
        self.assertIsNone(capacity_migration_advisory(primary))

        drain = select_residual_endpoint(
            MultiHopConfig(), entry_draining=True, exit_healthy=True
        )
        self.assertIsNone(capacity_migration_advisory(drain))

        caps = {PRODUCT_NODE_HOST: 0.95, PRODUCT_EXIT_HOST: 0.2}
        mig = select_residual_endpoint(MultiHopConfig(), peer_capacity=caps)
        text = capacity_migration_advisory(mig)
        self.assertIsNotNone(text)
        assert text is not None
        low = text.lower()
        self.assertIn("capacity", low)
        self.assertIn(PRODUCT_EXIT_HOST, text)
        self.assertTrue("near" in low or "moved" in low or "freer" in low)


class TestConnectCapacityPath(unittest.TestCase):
    def test_connect_records_capacity_reason_and_advisory(self):
        lines: list[str] = []

        caps = {
            PRODUCT_NODE_HOST: 0.97,
            PRODUCT_EXIT_HOST: 0.12,
        }
        # Explicit single-hop Iceland entry (empty MultiHopConfig) so capacity
        # map keys match preferred residual; do not use env/Settings default US.
        client = RptClient(
            status_cb=lines.append,
            multihop=MultiHopConfig(),
            peer_capacity=caps,
            entry_healthy=True,
            exit_healthy=True,
            entry_draining=False,
            probe_capacity=False,
        )
        # Constructor selection already capacity-aware
        self.assertEqual(client.endpoint.host, PRODUCT_EXIT_HOST)
        self.assertEqual(client.last_selection_reason, REASON_CAPACITY_MIGRATION)

        # Drive connect residual selection without real UDP: mock HELLO
        with mock.patch.object(
            client,
            "_hello_to_endpoint",
            return_value=mock.Mock(ok=True, state=client.state, message="ok"),
        ) as hello:
            # Force reconnect path through select
            client.state = client.state  # idle
            from client.connect import ConnectState

            client.state = ConnectState.IDLE
            client.session = None
            client.tunnel_plan = None
            client.connect(timeout=1.0)
            self.assertEqual(client.last_selection_reason, REASON_CAPACITY_MIGRATION)
            self.assertEqual(client.endpoint.host, PRODUCT_EXIT_HOST)
            self.assertTrue(hello.called)
            # Advisory emitted via status_cb before Connecting
            blob = "\n".join(lines).lower()
            self.assertIn("capacity", blob)
            self.assertTrue(
                any("capacity" in ln.lower() for ln in lines),
                lines,
            )
            self.assertTrue(client.last_capacity_advisory)
            self.assertIn("capacity", client.last_capacity_advisory.lower())

    def test_connect_no_advisory_for_entry_primary(self):
        lines: list[str] = []
        client = RptClient(
            status_cb=lines.append,
            multihop=MultiHopConfig(),
            peer_capacity={PRODUCT_NODE_HOST: 0.3, PRODUCT_EXIT_HOST: 0.1},
            entry_healthy=True,
            exit_healthy=True,
            probe_capacity=False,
        )
        self.assertEqual(client.endpoint.host, PRODUCT_NODE_HOST)
        from client.connect import ConnectState

        with mock.patch.object(
            client,
            "_hello_to_endpoint",
            return_value=mock.Mock(ok=True, state=ConnectState.CONNECTED, message="ok"),
        ):
            client.state = ConnectState.IDLE
            client.session = None
            client.tunnel_plan = None
            client.connect(timeout=1.0)
        self.assertEqual(client.last_selection_reason, "entry_primary")
        self.assertEqual(client.last_capacity_advisory, "")
        for ln in lines:
            self.assertNotIn("near connection capacity", ln.lower())


if __name__ == "__main__":
    unittest.main()
