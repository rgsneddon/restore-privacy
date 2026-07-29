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
    PRODUCT_US_HOST,
    MultiHopConfig,
    ResidualUnavailable,
    multihop_config_for_entry_country,
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
    signal_applies_to_preferred,
    wipe_hop_advisory,
)
from node.protocol import (  # noqa: E402
    NODE_STATUS_DRAINING,
    NODE_STATUS_READY,
    NODE_STATUS_REBUILDING,
    MsgType,
    pack_node_status,
    parse_node_status,
    peek_type,
)

# Optional: connect path needs cryptography; selection/signal tests do not.
try:
    from client.connect import ConnectState, RptClient  # noqa: E402
except Exception:  # noqa: BLE001
    ConnectState = None  # type: ignore
    RptClient = None  # type: ignore


class TestWipeHopSelection(unittest.TestCase):
    def test_drain_hops_to_non_preferred(self):
        sel = select_wipe_aware_residual(
            MultiHopConfig(),
            preferred_draining=True,
            preferred_healthy=True,
            peer_health={
                PRODUCT_NODE_HOST: True,
                PRODUCT_EXIT_HOST: True,
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
                },
                rng=random.Random(seed),
            )
            self.assertNotEqual(sel.endpoint.host, PRODUCT_NODE_HOST)

    def test_catalog_alternates_include_de_and_us(self):
        """Three-peer catalog: DE and US eligible when preferred is IS."""
        preferred = Endpoint(host=PRODUCT_NODE_HOST, port=44044)
        alts = eligible_wipe_alternates(
            preferred,
            peer_health={
                PRODUCT_NODE_HOST: True,
                PRODUCT_DE_HOST: True,
                PRODUCT_US_HOST: True,
            },
            catalog=PRODUCT_COUNTRY_CATALOG,
        )
        hosts = {a.host for a in alts}
        self.assertEqual(hosts, {PRODUCT_DE_HOST, PRODUCT_US_HOST})
        self.assertNotIn(PRODUCT_NODE_HOST, hosts)
        seen: set[str] = set()
        for seed in range(40):
            ep = pick_random_alternate(
                preferred,
                peer_health={
                    PRODUCT_DE_HOST: True,
                    PRODUCT_US_HOST: True,
                },
                catalog=PRODUCT_COUNTRY_CATALOG,
                rng=random.Random(seed),
            )
            assert ep is not None
            seen.add(ep.host)
        self.assertGreaterEqual(len(seen), 2)
        self.assertIn(PRODUCT_DE_HOST, seen)
        self.assertIn(PRODUCT_US_HOST, seen)

    def test_de_preferred_drain_hops_to_is_or_us(self):
        """Monopin DE preferred draining → alternate is IS or US (not DE)."""
        cfg = multihop_config_for_entry_country("DE", multihop_enabled=False)
        sel = select_wipe_aware_residual(
            cfg,
            preferred_draining=True,
            preferred_healthy=True,
            peer_health={
                PRODUCT_NODE_HOST: True,
                PRODUCT_DE_HOST: True,
                PRODUCT_US_HOST: True,
            },
            rng=random.Random(1),
        )
        self.assertEqual(sel.reason, REASON_WIPE_DRAIN_FAILOVER)
        self.assertIn(sel.endpoint.host, {PRODUCT_NODE_HOST, PRODUCT_US_HOST})
        self.assertNotEqual(sel.endpoint.host, PRODUCT_DE_HOST)
        # rejoin preferred DE when ready
        sel2 = select_wipe_aware_residual(
            cfg,
            preferred_draining=False,
            preferred_healthy=True,
            peer_health={
                PRODUCT_NODE_HOST: True,
                PRODUCT_DE_HOST: True,
                PRODUCT_US_HOST: True,
            },
        )
        self.assertEqual(sel2.reason, REASON_WIPE_REJOIN)
        self.assertEqual(sel2.endpoint.host, PRODUCT_DE_HOST)

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
                    PRODUCT_DE_HOST: False,
                    PRODUCT_US_HOST: False,
                    PRODUCT_EXIT_HOST: False,
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
        # Different catalog monopin ignored
        d3, r3, n3 = apply_wipe_signal_to_flags(
            WipeSignal(state="draining", host=PRODUCT_EXIT_HOST),
            preferred_host=PRODUCT_NODE_HOST,
            current_entry_draining=False,
        )
        self.assertFalse(d3)
        self.assertFalse(r3)
        self.assertEqual(n3, "signal_other_host")

    def test_empty_host_udp_is_current_residual_only(self):
        """Empty host on UDP ≡ residual_host; not preferred-by-default."""
        # No residual context + empty host → do not apply preferred flags
        self.assertFalse(
            signal_applies_to_preferred(
                WipeSignal(state="draining", host=""),
                PRODUCT_NODE_HOST,
                residual_host=None,
                trusted_preferred=False,
            )
        )
        # On preferred residual + empty host → apply (hop-off / ready)
        self.assertTrue(
            signal_applies_to_preferred(
                WipeSignal(state="draining", host=""),
                PRODUCT_NODE_HOST,
                residual_host=PRODUCT_NODE_HOST,
                trusted_preferred=False,
            )
        )
        d, r, n = apply_wipe_signal_to_flags(
            WipeSignal(state="draining", host=""),
            preferred_host=PRODUCT_NODE_HOST,
            current_entry_draining=False,
            residual_host=PRODUCT_NODE_HOST,
            trusted_preferred=False,
        )
        self.assertTrue(d and r)
        self.assertEqual(n, "enter_drain_hop_off")

    def test_alternate_empty_ready_does_not_clear_preferred_drain(self):
        """After hop-off, alternate NODE_STATUS ready (empty host) must not thrash."""
        # Client is on RO alternate; preferred IS still draining
        d, r, n = apply_wipe_signal_to_flags(
            WipeSignal(state="ready", host=""),
            preferred_host=PRODUCT_NODE_HOST,
            current_entry_draining=True,
            residual_host=PRODUCT_EXIT_HOST,
            trusted_preferred=False,
        )
        self.assertTrue(d)  # preferred drain flag unchanged
        self.assertFalse(r)
        self.assertEqual(n, "signal_other_host")
        # Explicit empty drain from non-preferred alternate also ignored
        d2, r2, n2 = apply_wipe_signal_to_flags(
            WipeSignal(state="draining", host=""),
            preferred_host=PRODUCT_NODE_HOST,
            current_entry_draining=True,
            residual_host=PRODUCT_EXIT_HOST,
            trusted_preferred=False,
        )
        self.assertTrue(d2)
        self.assertFalse(r2)
        self.assertEqual(n2, "signal_other_host")

    def test_preferred_poll_empty_host_soft_applies(self):
        """HTTP preferred poll: empty host / hostname soft-apply (trusted)."""
        self.assertTrue(
            signal_applies_to_preferred(
                WipeSignal(state="ready", host=""),
                PRODUCT_NODE_HOST,
                trusted_preferred=True,
            )
        )
        self.assertTrue(
            signal_applies_to_preferred(
                WipeSignal(state="draining", host="rpt-is-01.local"),
                PRODUCT_NODE_HOST,
                trusted_preferred=True,
            )
        )
        self.assertTrue(
            signal_applies_to_preferred(
                WipeSignal(state="ready", host="10.0.0.9"),
                PRODUCT_NODE_HOST,
                trusted_preferred=True,
            )
        )
        # Different catalog residual still ignored even on trusted path
        self.assertFalse(
            signal_applies_to_preferred(
                WipeSignal(state="draining", host=PRODUCT_EXIT_HOST),
                PRODUCT_NODE_HOST,
                trusted_preferred=True,
            )
        )
        d, r, n = apply_wipe_signal_to_flags(
            WipeSignal(state="ready", host=""),
            preferred_host=PRODUCT_NODE_HOST,
            current_entry_draining=True,
            trusted_preferred=True,
        )
        self.assertFalse(d)
        self.assertTrue(r)
        self.assertEqual(n, "ready_rejoin_preferred")

    def test_fail_soft_none_signal(self):
        d, r, n = apply_wipe_signal_to_flags(
            None, preferred_host=PRODUCT_NODE_HOST, current_entry_draining=True
        )
        self.assertTrue(d)
        self.assertFalse(r)
        self.assertEqual(n, "no_signal")


@unittest.skipIf(RptClient is None, "cryptography not installed for RptClient")
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
        # Connected residual is preferred (pre-hop)
        client.endpoint = Endpoint(PRODUCT_NODE_HOST, 44044)
        with mock.patch.object(
            client,
            "connect",
            return_value=mock.Mock(ok=True),
        ) as conn:
            with mock.patch.object(client, "disconnect"):
                note = client.apply_wipe_signal(
                    WipeSignal(state="draining", host=""),
                    reconnect=True,
                    trusted_preferred=False,
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
                # Preferred poll path (empty host OK)
                note = client.apply_wipe_signal(
                    WipeSignal(state="ready", host=""),
                    reconnect=True,
                    trusted_preferred=True,
                )
        self.assertIn("ready_rejoin", note)
        self.assertFalse(client.entry_draining)
        self.assertTrue(conn.called)

    def test_udp_on_alternate_empty_ready_no_thrash_reconnect(self):
        """On alternate residual, empty ready must not rejoin preferred mid-wipe."""
        client = RptClient(
            entry_draining=True,
            exit_healthy=True,
            probe_capacity=False,
        )
        client.endpoint = Endpoint(PRODUCT_EXIT_HOST, 44044)
        with mock.patch.object(
            client,
            "connect",
            return_value=mock.Mock(ok=True),
        ) as conn:
            with mock.patch.object(client, "disconnect"):
                note = client.apply_wipe_signal(
                    WipeSignal(state="ready", host=""),
                    reconnect=True,
                    trusted_preferred=False,
                )
        self.assertEqual(note, "signal_other_host")
        self.assertTrue(client.entry_draining)
        self.assertFalse(conn.called)

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

    def test_send_keepalive_is_send_only_no_recv(self):
        """Keepalive must not recv/settimeout on the shared residual sock."""
        src = (ROOT / "client" / "connect.py").read_text(encoding="utf-8")
        start = src.find("def send_keepalive")
        self.assertGreater(start, 0)
        end = src.find("\n    def ", start + 1)
        body = src[start:end] if end > start else src[start : start + 600]
        self.assertIn("sendto", body)
        # Code calls (not docstring prose): no sock.settimeout / sock.recvfrom
        self.assertNotIn(".settimeout(", body)
        self.assertNotIn(".recvfrom(", body)
        if RptClient is None:
            self.skipTest("cryptography not installed for RptClient")
        client = RptClient(probe_capacity=False)
        mock_sock = mock.Mock()
        client._sock = mock_sock
        client.session = mock.Mock(session_id=b"\x02" * 8)
        client.endpoint = Endpoint(PRODUCT_NODE_HOST, 44044)
        client.send_keepalive()
        mock_sock.sendto.assert_called()
        self.assertFalse(mock_sock.settimeout.called)
        self.assertFalse(mock_sock.recvfrom.called)

    def test_dataplane_routes_node_status_not_as_data(self):
        src = (ROOT / "client" / "dataplane.py").read_text(encoding="utf-8")
        self.assertIn("MsgType.NODE_STATUS", src)
        self.assertIn("process_node_status_frame", src)
        self.assertIn("peek_type", src)

    def test_wipe_status_default_empty_host(self):
        from node.wipe_status import current_wipe_state

        with mock.patch("node.rebuild_lock.read_lock", return_value=None):
            st = current_wipe_state(install_root="/tmp/none-root")
        self.assertEqual(st["state"], "ready")
        self.assertEqual(st.get("host") or "", "")

    def test_server_keepalive_replies_node_status(self):
        src = (ROOT / "node" / "server.py").read_text(encoding="utf-8")
        self.assertIn("pack_current_node_status", src)
        self.assertIn("MsgType.KEEPALIVE", src)


if __name__ == "__main__":
    unittest.main()
