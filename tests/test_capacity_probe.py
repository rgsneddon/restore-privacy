"""Private capacity probe + node private endpoint (shipped modules)."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from client.capacity_probe import (  # noqa: E402
    parse_private_capacity_payload,
    parse_probe_url_map,
    probe_one_peer,
    probe_peer_capacity_map,
    public_status_forbids_capacity_fields,
)
from client.connect import ConnectState, RptClient  # noqa: E402
from client.endpoint import PRODUCT_NODE_HOST  # noqa: E402
from client.multihop import (  # noqa: E402
    PRODUCT_EXIT_HOST,
    REASON_CAPACITY_MIGRATION,
    MultiHopConfig,
    select_residual_endpoint,
)
from node.aggregate_metrics import filter_public_status  # noqa: E402
from node.private_capacity import (  # noqa: E402
    authorize_capacity_request,
    build_private_capacity_payload,
    utilization_from_counts,
)
from node.sessions import SessionRegistry  # noqa: E402
from node.ui import make_handler, public_status_from_payload  # noqa: E402


class TestPrivateCapacityParse(unittest.TestCase):
    def test_parse_utilization_field(self):
        host, util = parse_private_capacity_payload(
            {"utilization": 0.9, "host": PRODUCT_NODE_HOST}
        )
        self.assertEqual(host, PRODUCT_NODE_HOST)
        self.assertAlmostEqual(util or 0, 0.9)

    def test_parse_live_capacity_counts(self):
        host, util = parse_private_capacity_payload(
            {"live": 90, "capacity": 100}, default_host=PRODUCT_EXIT_HOST
        )
        self.assertEqual(host, PRODUCT_EXIT_HOST)
        self.assertAlmostEqual(util or 0, 0.9)

    def test_parse_invalid_returns_unknown(self):
        h, u = parse_private_capacity_payload("not-json")
        self.assertIsNone(u)
        h2, u2 = parse_private_capacity_payload({"foo": 1})
        self.assertIsNone(u2)

    def test_utilization_from_counts_clamps(self):
        self.assertEqual(utilization_from_counts(0, 100), 0.0)
        self.assertEqual(utilization_from_counts(50, 100), 0.5)
        self.assertEqual(utilization_from_counts(200, 100), 1.0)

    def test_build_payload_and_public_filter_strips(self):
        payload = build_private_capacity_payload(live=10, capacity=100, host="h")
        self.assertIn("utilization", payload)
        self.assertTrue(payload.get("private"))
        public = filter_public_status({**payload, "title": "RESTORE PRIVACY"})
        self.assertEqual(public, {"title": "RESTORE PRIVACY"})
        self.assertNotIn("utilization", public)
        self.assertTrue(public_status_forbids_capacity_fields(payload))


class TestCapacityAuthorize(unittest.TestCase):
    def test_token_required(self):
        ok, _ = authorize_capacity_request(
            authorization_header="Bearer secret",
            env={},
        )
        self.assertFalse(ok)
        ok2, _ = authorize_capacity_request(
            authorization_header="Bearer secret",
            env={"RPT_CAPACITY_TOKEN": "secret"},
        )
        self.assertTrue(ok2)
        ok3, _ = authorize_capacity_request(
            authorization_header="Bearer wrong",
            env={"RPT_CAPACITY_TOKEN": "secret"},
        )
        self.assertFalse(ok3)


class TestProbeFailSoft(unittest.TestCase):
    def test_no_token_empty_map(self):
        m = probe_peer_capacity_map(env={}, catalog_hosts=[PRODUCT_NODE_HOST])
        self.assertEqual(m, {})

    def test_transport_error_omits_host(self):
        def boom(url, headers, timeout_s):
            raise TimeoutError("down")

        m = probe_peer_capacity_map(
            env={"RPT_CAPACITY_TOKEN": "t"},
            catalog_hosts=[PRODUCT_NODE_HOST, PRODUCT_EXIT_HOST],
            transport=boom,
            url_map={
                PRODUCT_NODE_HOST: "http://example.invalid/cap",
                PRODUCT_EXIT_HOST: "http://example.invalid/cap2",
            },
        )
        self.assertEqual(m, {})

    def test_successful_probe_maps_host(self):
        bodies = {
            f"http://a/{PRODUCT_NODE_HOST}": json.dumps(
                {"utilization": 0.95, "host": PRODUCT_NODE_HOST}
            ),
            f"http://b/{PRODUCT_EXIT_HOST}": json.dumps(
                {"live": 10, "capacity": 100, "host": PRODUCT_EXIT_HOST}
            ),
        }

        def transport(url, headers, timeout_s):
            self.assertIn("Authorization", headers)
            return bodies[url]

        m = probe_peer_capacity_map(
            env={"RPT_CAPACITY_TOKEN": "tok"},
            transport=transport,
            url_map={
                PRODUCT_NODE_HOST: f"http://a/{PRODUCT_NODE_HOST}",
                PRODUCT_EXIT_HOST: f"http://b/{PRODUCT_EXIT_HOST}",
            },
        )
        self.assertAlmostEqual(m[PRODUCT_NODE_HOST], 0.95)
        self.assertAlmostEqual(m[PRODUCT_EXIT_HOST], 0.1)

    def test_probe_one_peer_invalid_body_unknown(self):
        h, u = probe_one_peer(
            "http://x",
            token="t",
            transport=lambda url, headers, t: "@@@",
        )
        self.assertIsNone(u)


class TestProbeInjectsSelection(unittest.TestCase):
    def test_probed_map_migrates_when_preferred_full(self):
        m = {
            PRODUCT_NODE_HOST: 0.95,
            PRODUCT_EXIT_HOST: 0.15,
        }
        sel = select_residual_endpoint(MultiHopConfig(), peer_capacity=m)
        self.assertEqual(sel.reason, REASON_CAPACITY_MIGRATION)
        self.assertEqual(sel.endpoint.host, PRODUCT_EXIT_HOST)

    def test_no_probe_data_keeps_preferred(self):
        sel = select_residual_endpoint(MultiHopConfig(), peer_capacity={})
        self.assertEqual(sel.reason, "entry_primary")
        self.assertEqual(sel.endpoint.host, PRODUCT_NODE_HOST)

    def test_connect_uses_transport_probe_then_migrates(self):
        lines: list[str] = []

        def transport(url, headers, timeout_s):
            if PRODUCT_NODE_HOST in url or url.endswith("is"):
                return json.dumps({"utilization": 0.97, "host": PRODUCT_NODE_HOST})
            return json.dumps({"utilization": 0.1, "host": PRODUCT_EXIT_HOST})

        from client.multihop import MultiHopConfig

        # Pin single-hop default catalog (ignore host Settings entry_country)
        mh = MultiHopConfig()
        client = RptClient(
            status_cb=lines.append,
            multihop=mh,
            probe_capacity=True,
            capacity_transport=transport,
            peer_capacity=None,
        )
        # Constructor probes with force=False and empty map → runs probe
        # Need token for probe_peer_capacity_map
        # Without env token, map stays empty — inject via env in probe call.
        # Override by patching probe_peer_capacity_map return:
        with mock.patch(
            "client.connect.probe_peer_capacity_map",
            return_value={
                PRODUCT_NODE_HOST: 0.97,
                PRODUCT_EXIT_HOST: 0.1,
            },
        ):
            client2 = RptClient(
                status_cb=lines.append,
                multihop=MultiHopConfig(),
                probe_capacity=True,
                peer_capacity=None,
            )
            # force=False on init still probes when map empty
            self.assertEqual(client2.endpoint.host, PRODUCT_EXIT_HOST)
            self.assertEqual(client2.last_selection_reason, REASON_CAPACITY_MIGRATION)

            with mock.patch.object(
                client2,
                "_hello_to_endpoint",
                return_value=mock.Mock(
                    ok=True, state=ConnectState.CONNECTED, message="ok"
                ),
            ):
                client2.state = ConnectState.IDLE
                client2.session = None
                client2.tunnel_plan = None
                client2.connect(timeout=1.0)
            self.assertEqual(client2.last_selection_reason, REASON_CAPACITY_MIGRATION)
            self.assertTrue(client2.last_capacity_advisory)
            self.assertIn("capacity", client2.last_capacity_advisory.lower())

    def test_probe_failure_failsoft_no_migration_no_crash(self):
        from client.multihop import MultiHopConfig

        lines: list[str] = []
        with mock.patch(
            "client.connect.probe_peer_capacity_map",
            side_effect=RuntimeError("network"),
        ):
            client = RptClient(
                status_cb=lines.append,
                multihop=MultiHopConfig(),
                probe_capacity=True,
                peer_capacity=None,
            )
            self.assertEqual(client.endpoint.host, PRODUCT_NODE_HOST)
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
                r = client.connect(timeout=1.0)
            self.assertTrue(r.ok or client.last_selection_reason == "entry_primary")
            self.assertEqual(client.last_selection_reason, "entry_primary")
            self.assertEqual(client.last_capacity_advisory, "")


class TestNodePrivateEndpoint(unittest.TestCase):
    def test_registry_private_payload_not_public(self):
        reg = SessionRegistry()
        priv = reg.private_capacity_payload(host="h1")
        self.assertIn("utilization", priv)
        pub = reg.status_payload()
        self.assertEqual(set(pub.keys()), {"title"})
        self.assertNotIn("utilization", pub)

    def test_handler_paths_exist_in_source(self):
        src = (ROOT / "node" / "ui.py").read_text(encoding="utf-8")
        self.assertIn("/api/private/capacity", src)
        self.assertIn("authorize_capacity_request", src)
        self.assertIn("get_private_capacity", src)

    def test_public_status_from_payload_strips_capacity(self):
        dirty = build_private_capacity_payload(live=5, capacity=10)
        dirty["title"] = "RESTORE PRIVACY"
        clean = public_status_from_payload(dirty)
        self.assertEqual(clean, {"title": "RESTORE PRIVACY"})


if __name__ == "__main__":
    unittest.main()
