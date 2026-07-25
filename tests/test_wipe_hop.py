"""Wipe-drain hop-off and preferred rejoin (shipped helpers + signal path)."""

from __future__ import annotations

import random
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from client.endpoint import PRODUCT_NODE_HOST, Endpoint  # noqa: E402
from client.multihop import (  # noqa: E402
    PRODUCT_COUNTRY_CATALOG,
    PRODUCT_DE_HOST,
    PRODUCT_EXIT_HOST,
    MultiHopConfig,
    ResidualUnavailable,
    select_residual_endpoint,
)
from client.wipe_hop import (  # noqa: E402
    REASON_WIPE_DRAIN_FAILOVER,
    REASON_WIPE_REJOIN,
    WipeSignal,
    apply_wipe_signal_to_flags,
    eligible_wipe_alternates,
    parse_node_status_wire,
    parse_wipe_signal_json,
    pick_random_alternate,
    select_wipe_aware_residual,
    wipe_hop_advisory,
)
from client.connect import ConnectState, RptClient  # noqa: E402
from node.protocol import (  # noqa: E402
    NODE_STATUS_DRAINING,
    NODE_STATUS_READY,
    NODE_STATUS_REBUILDING,
    MsgType,
    pack_node_status,
    parse_node_status,
    peek_type,
)


class TestWipeHopSelection(unittest.TestCase):
    def test_drain_hops_to_non_preferred(self):
        sel = select_wipe_aware_residual(
            MultiHopConfig(),
            preferred_draining=True,
            preferred_healthy=True,
            peer_health={
                PRODUCT_NODE_HOST: True,
                PRODUCT_EXIT_HOST: True,
                PRODUCT_DE_HOST: True,
            },
            rng=random.Random(0),
        )
        self.assertEqual(sel.reason, REASON_WIPE_DRAIN_FAILOVER)
        self.assertNotEqual(sel.endpoint.host, PRODUCT_NODE_HOST)
        self.assertTrue(sel.failover_active)
        self.assertEqual(sel.preferred_host, PRODUCT_NODE_HOST)

    def test_ready_rejoins_preferred(self):
        sel = select_wipe_aware_residual(
            MultiHopConfig(),
            preferred_draining=False,
            preferred_healthy=True,
        )
        self.assertEqual(sel.reason, REASON_WIPE_REJOIN)
        self.assertEqual(sel.endpoint.host, PRODUCT_NODE_HOST)
        self.assertFalse(sel.failover_active)

    def test_alternate_never_same_host(self):
        pref = MultiHopConfig()
        for seed in range(20):
            sel = select_wipe_aware_residual(
                pref,
                preferred_draining=True,
                peer_health={
                    PRODUCT_NODE_HOST: False,
                    PRODUCT_EXIT_HOST: True,
                    PRODUCT_DE_HOST: True,
                },
                rng=random.Random(seed),
            )
            self.assertNotEqual(sel.endpoint.host, PRODUCT_NODE_HOST)

    def test_multi_peer_alternates_not_fixed_single(self):
        preferred = Endpoint(host=PRODUCT_NODE_HOST, port=44044)
        alts = eligible_wipe_alternates(
            preferred,
            peer_health={
                PRODUCT_NODE_HOST: True,
                PRODUCT_EXIT_HOST: True,
                PRODUCT_DE_HOST: True,
            },
            catalog=PRODUCT_COUNTRY_CATALOG,
        )
        hosts = {a.host for a in alts}
        self.assertIn(PRODUCT_EXIT_HOST, hosts)
        self.assertIn(PRODUCT_DE_HOST, hosts)
        self.assertNotIn(PRODUCT_NODE_HOST, hosts)
        # Random among both
        seen: set[str] = set()
        for seed in range(40):
            ep = pick_random_alternate(
                preferred,
                peer_health={
                    PRODUCT_EXIT_HOST: True,
                    PRODUCT_DE_HOST: True,
                },
                catalog=PRODUCT_COUNTRY_CATALOG,
                rng=random.Random(seed),
            )
            assert ep is not None
            seen.add(ep.host)
        self.assertGreaterEqual(len(seen), 2)

    def test_select_residual_endpoint_drain_multi_peer(self):
        seen: set[str] = set()
        for seed in range(30):
            sel = select_residual_endpoint(
                MultiHopConfig(),
                entry_healthy=True,
                exit_healthy=True,
                entry_draining=True,
                rng=random.Random(seed),
            )
            self.assertIn(
                sel.reason,
                (REASON_WIPE_DRAIN_FAILOVER, "exit_failover"),
            )
            self.assertNotEqual(sel.endpoint.host, PRODUCT_NODE_HOST)
            seen.add(sel.endpoint.host)
        self.assertGreaterEqual(len(seen), 1)

    def test_no_alternate_fail_closed(self):
        with self.assertRaises(ResidualUnavailable):
            select_wipe_aware_residual(
                MultiHopConfig(),
                preferred_draining=True,
                peer_health={
                    PRODUCT_NODE_HOST: True,
                    PRODUCT_EXIT_HOST: False,
                    PRODUCT_DE_HOST: False,
                },
            )


class TestWipeSignalParse(unittest.TestCase):
    def test_json_drain_and_ready(self):
        d = parse_wipe_signal_json(
            {"state": "draining", "host": PRODUCT_NODE_HOST, "role": "is"}
        )
        self.assertIsNotNone(d)
        assert d is not None
        self.assertTrue(d.is_drain)
        r = parse_wipe_signal_json({"state": "ready", "host": PRODUCT_NODE_HOST})
        self.assertIsNotNone(r)
        assert r is not None
        self.assertTrue(r.is_ready)

    def test_json_fail_soft(self):
        self.assertIsNone(parse_wipe_signal_json("not-json"))
        self.assertIsNone(parse_wipe_signal_json({"foo": 1}))

    def test_wire_node_status_roundtrip(self):
        frame = pack_node_status(
            flags=NODE_STATUS_DRAINING,
            host=PRODUCT_NODE_HOST,
            role="is",
            session_id=b"\x01" * 8,
        )
        self.assertEqual(peek_type(frame), MsgType.NODE_STATUS)
        sid, flags, host, role = parse_node_status(frame)
        self.assertEqual(host, PRODUCT_NODE_HOST)
        self.assertEqual(role, "is")
        self.assertTrue(flags & NODE_STATUS_DRAINING)
        sig = parse_node_status_wire(frame)
        self.assertIsNotNone(sig)
        assert sig is not None
        self.assertTrue(sig.is_drain)
        self.assertEqual(sig.host, PRODUCT_NODE_HOST)

    def test_apply_signal_flags(self):
        drain, reselect, note = apply_wipe_signal_to_flags(
            WipeSignal(state="draining", host=PRODUCT_NODE_HOST),
            preferred_host=PRODUCT_NODE_HOST,
            current_entry_draining=False,
        )
        self.assertTrue(drain)
        self.assertTrue(reselect)
        self.assertEqual(note, "enter_drain_hop_off")
        ready, reselect2, note2 = apply_wipe_signal_to_flags(
            WipeSignal(state="ready", host=PRODUCT_NODE_HOST),
            preferred_host=PRODUCT_NODE_HOST,
            current_entry_draining=True,
        )
        self.assertFalse(ready)
        self.assertTrue(reselect2)
        self.assertEqual(note2, "ready_rejoin_preferred")
        # Other host ignored
        d3, r3, n3 = apply_wipe_signal_to_flags(
            WipeSignal(state="draining", host=PRODUCT_EXIT_HOST),
            preferred_host=PRODUCT_NODE_HOST,
            current_entry_draining=False,
        )
        self.assertFalse(d3)
        self.assertFalse(r3)
        self.assertEqual(n3, "signal_other_host")

    def test_fail_soft_none_signal(self):
        d, r, n = apply_wipe_signal_to_flags(
            None, preferred_host=PRODUCT_NODE_HOST, current_entry_draining=True
        )
        self.assertTrue(d)
        self.assertFalse(r)
        self.assertEqual(n, "no_signal")


class TestConnectWipePath(unittest.TestCase):
    def test_connect_hops_when_entry_draining(self):
        lines: list[str] = []
        client = RptClient(
            status_cb=lines.append,
            entry_draining=True,
            exit_healthy=True,
            entry_healthy=True,
            probe_capacity=False,
        )
        self.assertNotEqual(client.endpoint.host, PRODUCT_NODE_HOST)
        self.assertIn(
            client.last_selection_reason,
            (REASON_WIPE_DRAIN_FAILOVER, "exit_failover"),
        )
        with mock.patch.object(
            client,
            "_hello_to_endpoint",
            return_value=mock.Mock(
                ok=True, state=ConnectState.CONNECTED, message="ok"
            ),
        ):
            client.state = ConnectState.IDLE
            client.session = None
            client.tunnel_plan = None
            client.entry_draining = True
            client.connect(timeout=1.0, force_reconnect=True)
        self.assertNotEqual(client.endpoint.host, PRODUCT_NODE_HOST)
        blob = "\n".join(lines).lower()
        self.assertTrue(
            "wipe" in blob or "drain" in blob or "hop" in blob or "failover" in blob,
            lines,
        )

    def test_apply_wipe_signal_triggers_reconnect(self):
        client = RptClient(
            entry_draining=False,
            exit_healthy=True,
            probe_capacity=False,
        )
        with mock.patch.object(
            client,
            "connect",
            return_value=mock.Mock(ok=True),
        ) as conn:
            with mock.patch.object(client, "disconnect"):
                note = client.apply_wipe_signal(
                    WipeSignal(state="draining", host=PRODUCT_NODE_HOST),
                    reconnect=True,
                )
        self.assertIn("enter_drain", note)
        self.assertTrue(client.entry_draining)
        self.assertTrue(conn.called)

    def test_apply_ready_rejoins(self):
        client = RptClient(
            entry_draining=True,
            exit_healthy=True,
            probe_capacity=False,
        )
        with mock.patch.object(
            client,
            "connect",
            return_value=mock.Mock(ok=True),
        ) as conn:
            with mock.patch.object(client, "disconnect"):
                note = client.apply_wipe_signal(
                    WipeSignal(state="ready", host=PRODUCT_NODE_HOST),
                    reconnect=True,
                )
        self.assertIn("ready_rejoin", note)
        self.assertFalse(client.entry_draining)
        self.assertTrue(conn.called)

    def test_wipe_hop_advisory_only_for_wipe_reasons(self):
        sel = select_wipe_aware_residual(
            MultiHopConfig(), preferred_draining=True, rng=random.Random(1)
        )
        text = wipe_hop_advisory(sel)
        self.assertIsNotNone(text)
        assert text is not None
        self.assertIn("draining", text.lower())
        primary = select_residual_endpoint(MultiHopConfig())
        self.assertIsNone(wipe_hop_advisory(primary))


class TestNodeWipeStatus(unittest.TestCase):
    def test_current_wipe_state_ready_without_lock(self):
        from node.wipe_status import current_wipe_state, pack_current_node_status

        with mock.patch("node.wipe_status.read_lock", return_value=None, create=True):
            # patch rebuild_lock.read_lock used inside
            with mock.patch(
                "node.rebuild_lock.read_lock", return_value=None
            ):
                st = current_wipe_state(install_root="/tmp/none-root")
        self.assertEqual(st["state"], "ready")
        frame = pack_current_node_status(install_root="/tmp/none-root")
        self.assertEqual(peek_type(frame), MsgType.NODE_STATUS)

    def test_ui_exposes_node_state_path(self):
        src = (ROOT / "node" / "ui.py").read_text(encoding="utf-8")
        self.assertIn("/api/private/node-state", src)
        self.assertIn("current_wipe_state", src)

    def test_server_keepalive_replies_node_status(self):
        src = (ROOT / "node" / "server.py").read_text(encoding="utf-8")
        self.assertIn("pack_current_node_status", src)
        self.assertIn("MsgType.KEEPALIVE", src)


if __name__ == "__main__":
    unittest.main()
