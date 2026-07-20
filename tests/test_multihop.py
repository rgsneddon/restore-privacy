"""Optional multi-hop path *config* — default single-hop, honest status."""

from __future__ import annotations

import unittest

from client.endpoint import PRODUCT_NODE_HOST, PRODUCT_NODE_PORT
from client.multihop import (
    MULTI_HOP_ROUTING_IMPLEMENTED,
    Hop,
    MultiHopConfig,
    build_hop_path,
    default_single_hop,
    first_hop_endpoint,
    hop_path_configured,
    is_multihop_active,
    multihop_status_text,
    parse_hops_csv,
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

    def test_build_hop_path_empty_defaults_product(self):
        hops = build_hop_path([])
        self.assertEqual(len(hops), 1)
        self.assertEqual(hops[0].host, PRODUCT_NODE_HOST)

    def test_two_or_more_hops_configured_not_claimed_active(self):
        """≥2 hops + enabled is config only — not multi-hop residual until relay exists."""
        hops = [
            Hop("10.0.0.1", 44044),
            Hop("10.0.0.2", 44045),
            Hop("10.0.0.3", 44044),
        ]
        path = build_hop_path(hops)
        self.assertEqual(len(path), 3)
        cfg = MultiHopConfig(hops=hops, enabled=True)
        self.assertTrue(hop_path_configured(cfg))
        # Product has no multi-hop data path yet
        self.assertFalse(MULTI_HOP_ROUTING_IMPLEMENTED)
        self.assertFalse(is_multihop_active(cfg))
        text = multihop_status_text(cfg)
        self.assertNotIn("multi-hop active", text)
        self.assertIn("not routed", text.lower())
        self.assertIn("entry-only", text.lower())
        self.assertIn("10.0.0.1", text)
        self.assertIn("10.0.0.2", text)
        # Entry hop is first (what Connect would dial if wired)
        self.assertEqual(first_hop_endpoint(cfg).host, "10.0.0.1")

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

    def test_disabled_ignores_extra_hops(self):
        cfg = MultiHopConfig(
            hops=[Hop("9.9.9.9"), Hop("8.8.8.8")],
            enabled=False,
        )
        hops = cfg.active_hops()
        self.assertEqual(len(hops), 1)
        self.assertEqual(hops[0].host, PRODUCT_NODE_HOST)
        self.assertFalse(hop_path_configured(cfg))
        self.assertFalse(is_multihop_active(cfg))

    def test_routing_flag_gates_active(self):
        """is_multihop_active requires MULTI_HOP_ROUTING_IMPLEMENTED (shipped constant)."""
        self.assertIs(MULTI_HOP_ROUTING_IMPLEMENTED, False)
        cfg = MultiHopConfig(
            hops=[Hop("1.1.1.1"), Hop("2.2.2.2")],
            enabled=True,
        )
        self.assertTrue(hop_path_configured(cfg))
        self.assertFalse(is_multihop_active(cfg))


if __name__ == "__main__":
    unittest.main()
