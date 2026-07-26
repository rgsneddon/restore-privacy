"""Residual monopin IPs: public labels only; Connect dial path keeps real hosts."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from client.country_select import catalog_country_options  # noqa: E402
from client.multihop import (  # noqa: E402
    COUNTRY_IS,
    COUNTRY_RO,
    COUNTRY_US,
    PRODUCT_DE_HOST,
    PRODUCT_EXIT_HOST,
    PRODUCT_NODE_HOST,
    PRODUCT_US_HOST,
    country_node_for_code,
    residual_endpoint,
    multihop_config_for_entry_country,
)
from client.residual_public import (  # noqa: E402
    is_residual_monopin_host,
    public_catalog_peers,
    public_country_option_dict,
    public_label_for_code,
    public_label_for_host,
    public_security_audit_payload,
    redact_residual_hosts_in_text,
    residual_monopin_hosts,
)


class TestResidualPublicLabels(unittest.TestCase):
    def test_monopin_set_includes_catalog_hosts(self):
        hosts = residual_monopin_hosts()
        self.assertIn(PRODUCT_NODE_HOST, hosts)
        self.assertIn(PRODUCT_EXIT_HOST, hosts)
        self.assertIn(PRODUCT_US_HOST, hosts)
        self.assertIn(PRODUCT_DE_HOST, hosts)  # retired — still redacted

    def test_public_labels_have_no_ipv4(self):
        for code in (COUNTRY_IS, COUNTRY_RO, COUNTRY_US):
            label = public_label_for_code(code)
            self.assertNotRegex(label, r"\d+\.\d+\.\d+\.\d+", label)
            self.assertIn(code, label)
        for host in residual_monopin_hosts():
            lab = public_label_for_host(host)
            self.assertNotRegex(lab, r"\d+\.\d+\.\d+\.\d+", lab)
            self.assertTrue(lab)

    def test_redact_text_strips_monopins(self):
        raw = (
            f"Connect residual {PRODUCT_DE_HOST}:44044 "
            f"and {PRODUCT_NODE_HOST} via {PRODUCT_EXIT_HOST}"
        )
        out = redact_residual_hosts_in_text(raw)
        for h in residual_monopin_hosts():
            self.assertNotIn(h, out)
        self.assertNotRegex(out, r"\d+\.\d+\.\d+\.\d+")

    def test_country_option_to_dict_public_omits_host(self):
        opts = catalog_country_options()
        self.assertTrue(opts)
        for o in opts:
            d = o.to_dict(admin=False)
            self.assertNotIn("host", d)
            self.assertNotRegex(d.get("label", ""), r"\d+\.\d+\.\d+\.\d+")
            # Dial field still available on the object for Connect
            self.assertTrue(o.host)
            self.assertTrue(is_residual_monopin_host(o.host))

    def test_country_option_to_dict_admin_includes_host(self):
        d = public_country_option_dict(
            code="RO", name="Romania", flag="x", host=PRODUCT_EXIT_HOST, admin=True
        )
        self.assertEqual(d.get("host"), PRODUCT_EXIT_HOST)

    def test_public_catalog_peers_split(self):
        pub = public_catalog_peers(admin=False)
        adm = public_catalog_peers(admin=True)
        self.assertEqual(len(pub), 3)
        self.assertEqual(len(adm), 3)
        for row in pub:
            self.assertNotIn("host", row)
            self.assertIn(row["code"], (COUNTRY_IS, COUNTRY_RO, COUNTRY_US))
        for row in adm:
            self.assertIn("host", row)
            self.assertTrue(is_residual_monopin_host(row["host"]))

    def test_connect_dial_path_still_returns_real_hosts(self):
        """Obfuscation is presentation-only — residual endpoint keeps monopin IPv4."""
        for code, want_host in (
            (COUNTRY_IS, PRODUCT_NODE_HOST),
            (COUNTRY_RO, PRODUCT_EXIT_HOST),
            (COUNTRY_US, PRODUCT_US_HOST),
        ):
            n = country_node_for_code(code)
            self.assertEqual(n.host, want_host)
            cfg = multihop_config_for_entry_country(code, multihop_enabled=False)
            ep = residual_endpoint(cfg)
            self.assertEqual(ep.host, want_host)
            self.assertTrue(is_residual_monopin_host(ep.host))

    def test_security_audit_public_payload_redacts_node_host(self):
        sample = {
            "node_host": PRODUCT_NODE_HOST,
            "tcp_status": {"host": PRODUCT_NODE_HOST, "port": 8080, "ok": True},
            "http_status": {
                "url": f"http://{PRODUCT_NODE_HOST}:8080/status",
                "ok": True,
            },
            "udp": {"host": PRODUCT_EXIT_HOST, "port": 44044},
        }
        out = public_security_audit_payload(sample)
        blob = json.dumps(out)
        for h in residual_monopin_hosts():
            self.assertNotIn(h, blob)
        self.assertNotIn(PRODUCT_NODE_HOST, str(out.get("node_host")))

    def test_connection_log_redacts_on_append(self):
        from client.connection_log import append_event, read_events

        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "log.jsonl"
            append_event(
                "connect",
                f"Connected residual {PRODUCT_EXIT_HOST}",
                path=path,
                include_diagnostics=False,
                detail={"residual_host": PRODUCT_EXIT_HOST},
            )
            raw = path.read_text(encoding="utf-8")
            self.assertNotIn(PRODUCT_EXIT_HOST, raw)
            events = read_events(path=path)
            self.assertTrue(events)
            self.assertNotIn(PRODUCT_EXIT_HOST, events[0].message)
            self.assertNotIn(
                PRODUCT_EXIT_HOST, str(events[0].detail.get("residual_host", ""))
            )


class TestAdminStillShowsHosts(unittest.TestCase):
    def test_admin_node_usage_catalog_has_hosts(self):
        from status_page.admin_node_usage import product_catalog_peers

        peers = product_catalog_peers()
        self.assertGreaterEqual(len(peers), 3)
        hosts = {p["host"] for p in peers}
        self.assertIn(PRODUCT_NODE_HOST, hosts)
        self.assertIn(PRODUCT_EXIT_HOST, hosts)
        self.assertIn(PRODUCT_US_HOST, hosts)
        self.assertNotIn(PRODUCT_DE_HOST, hosts)


class TestMultihopConnectStatusNoMonopinIp(unittest.TestCase):
    def test_multihop_status_text_has_no_monopin_ipv4(self):
        from client.multihop import MultiHopConfig, Hop, multihop_status_text

        cfg = MultiHopConfig(
            enabled=True,
            hops=[
                Hop(host=PRODUCT_NODE_HOST, port=44044, role="entry"),
                Hop(host=PRODUCT_EXIT_HOST, port=44044, role="exit"),
            ],
        )
        text = multihop_status_text(cfg)
        for h in residual_monopin_hosts():
            self.assertNotIn(h, text, text)
        self.assertNotRegex(text, r"\d+\.\d+\.\d+\.\d+")

    def test_hop_label_uses_public_name(self):
        from client.multihop import Hop

        lab = Hop(host=PRODUCT_EXIT_HOST, port=44044).label()
        self.assertNotIn(PRODUCT_EXIT_HOST, lab)
        self.assertIn("RO", lab)

    def test_connect_status_cb_redacts_monopin(self):
        from client.connect import RptClient
        from client.endpoint import Endpoint

        seen: list[str] = []

        def cb(msg: str) -> None:
            seen.append(msg)

        client = RptClient(status_cb=cb, endpoint=Endpoint(host=PRODUCT_NODE_HOST))
        client._status(f"trying {PRODUCT_NODE_HOST}:44044")
        self.assertTrue(seen)
        self.assertNotIn(PRODUCT_NODE_HOST, seen[-1])


if __name__ == "__main__":
    unittest.main()
