"""Multi-hop path config + residual routing (entry → exit when active)."""

from __future__ import annotations

import unittest

from client.endpoint import PRODUCT_NODE_HOST, PRODUCT_NODE_PORT
from client.multihop import (
    MULTI_HOP_ROUTING_IMPLEMENTED,
    PRODUCT_EXIT_HOST,
    Hop,
    MultiHopConfig,
    build_entry_exit_path,
    build_hop_path,
    default_single_hop,
    entry_hop,
    exit_hop_label,
    first_hop_endpoint,
    hop_path_configured,
    is_multihop_active,
    multihop_config_from_env,
    multihop_status_text,
    node_pub_name_for_endpoint,
    parse_hops_csv,
    residual_endpoint,
    select_residual_endpoint,
)


class TestMultiHopPath(unittest.TestCase):
    def test_default_single_hop(self):
        cfg = default_single_hop()
        self.assertFalse(cfg.enabled)
        self.assertFalse(is_multihop_active(cfg))
        self.assertIn("inactive", multihop_status_text(cfg))
        ep = first_hop_endpoint(cfg)
        self.assertEqual(ep.host, PRODUCT_NODE_HOST)
        self.assertEqual(ep.port, PRODUCT_NODE_PORT)
        self.assertEqual(residual_endpoint(cfg).host, PRODUCT_NODE_HOST)

    def test_build_hop_path_empty_defaults_product(self):
        hops = build_hop_path([])
        self.assertEqual(len(hops), 1)
        self.assertEqual(hops[0].host, PRODUCT_NODE_HOST)

    def test_two_or_more_hops_active_routes_to_exit(self):
        """≥2 hops + enabled + routing implemented → residual dials exit."""
        hops = [
            Hop("10.0.0.1", 44044),
            Hop("10.0.0.2", 44045),
        ]
        cfg = MultiHopConfig(hops=hops, enabled=True)
        self.assertTrue(MULTI_HOP_ROUTING_IMPLEMENTED)
        self.assertTrue(hop_path_configured(cfg))
        self.assertTrue(is_multihop_active(cfg))
        self.assertEqual(first_hop_endpoint(cfg).host, "10.0.0.1")
        self.assertEqual(residual_endpoint(cfg).host, "10.0.0.2")
        self.assertEqual(residual_endpoint(cfg).port, 44045)
        text = multihop_status_text(cfg)
        self.assertIn("multi-hop active", text)
        self.assertIn("residual via", text)
        self.assertNotIn("not routed", text.lower())
        self.assertNotIn("entry-only", text.lower())

    def test_enabled_but_one_hop_honest(self):
        cfg = MultiHopConfig(hops=[Hop("1.2.3.4")], enabled=True)
        self.assertFalse(is_multihop_active(cfg))
        self.assertFalse(hop_path_configured(cfg))
        self.assertIn("≥2", multihop_status_text(cfg))

    def test_parse_hops_csv(self):
        hops = parse_hops_csv("a.example:44044, b.example, c.example:9")
        self.assertEqual(len(hops), 3)
        self.assertEqual(hops[0].port, 44044)
        self.assertEqual(hops[1].host, "b.example")
        self.assertEqual(hops[2].port, 9)

    def test_disabled_uses_configured_entry_only(self):
        """Multi-hop off: residual uses first configured hop (user entry country).

        Extra exit hops are not dialed; entry may be Romania or a custom host.
        """
        cfg = MultiHopConfig(
            hops=[Hop("9.9.9.9"), Hop("8.8.8.8")],
            enabled=False,
        )
        hops = cfg.active_hops()
        self.assertEqual(len(hops), 1)
        self.assertEqual(hops[0].host, "9.9.9.9")
        self.assertEqual(residual_endpoint(cfg).host, "9.9.9.9")

    def test_product_entry_exit_romania(self):
        path = build_entry_exit_path(PRODUCT_EXIT_HOST)
        cfg = MultiHopConfig(hops=path, enabled=True)
        self.assertTrue(is_multihop_active(cfg))
        self.assertEqual(first_hop_endpoint(cfg).host, PRODUCT_NODE_HOST)
        self.assertEqual(residual_endpoint(cfg).host, PRODUCT_EXIT_HOST)
        self.assertEqual(exit_hop_label(cfg), f"{PRODUCT_EXIT_HOST}:{PRODUCT_NODE_PORT}")
        self.assertEqual(
            node_pub_name_for_endpoint(residual_endpoint(cfg)),
            "exit_node_elgamal.pub",
        )
        self.assertEqual(
            node_pub_name_for_endpoint(first_hop_endpoint(cfg)),
            "node_elgamal.pub",
        )

    def test_multihop_config_from_env_exit_host(self):
        env = {
            "RPT_MULTIHOP_ENABLED": "1",
            "RPT_EXIT_HOST": "185.146.232.107",
            "RPT_EXIT_PORT": "44044",
        }
        cfg = multihop_config_from_env(env)
        self.assertTrue(cfg.enabled)
        self.assertTrue(is_multihop_active(cfg))
        self.assertEqual(residual_endpoint(cfg).host, "185.146.232.107")
        bare = multihop_config_from_env({})
        self.assertFalse(bare.enabled)
        self.assertEqual(entry_hop().host, PRODUCT_NODE_HOST)

    def test_entry_exit_requires_exit_host(self):
        with self.assertRaises(ValueError):
            build_entry_exit_path("")

    def test_routing_flag_gates_active(self):
        self.assertIs(MULTI_HOP_ROUTING_IMPLEMENTED, True)
        cfg = MultiHopConfig(
            hops=[Hop("1.1.1.1"), Hop("2.2.2.2")],
            enabled=True,
        )
        self.assertTrue(is_multihop_active(cfg))

    def test_select_residual_entry_primary_and_wipe_drain(self):
        # Entry healthy → entry-primary (single-hop default)
        sel = select_residual_endpoint(
            default_single_hop(),
            entry_healthy=True,
            exit_healthy=True,
            entry_draining=False,
        )
        self.assertEqual(sel.endpoint.host, PRODUCT_NODE_HOST)
        self.assertEqual(sel.reason, "entry_primary")
        # Entry draining → automatic hop to any non-preferred catalog peer
        fo = select_residual_endpoint(
            default_single_hop(),
            entry_healthy=True,
            exit_healthy=True,
            entry_draining=True,
        )
        self.assertNotEqual(fo.endpoint.host, PRODUCT_NODE_HOST)
        self.assertTrue(fo.failover_active)
        # Fleet wipe / entry drain uses exit_failover to an alternate catalog peer
        self.assertEqual(fo.reason, "exit_failover")


if __name__ == "__main__":
    unittest.main()
