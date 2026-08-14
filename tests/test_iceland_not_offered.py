"""Iceland is not a residual connection option or wipe target (until sales)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class TestIcelandNotOfferedCatalog(unittest.TestCase):
    def test_offered_catalog_is_de_only(self) -> None:
        from client.country_select import catalog_country_options
        from client.multihop import (
            PRODUCT_DE_HOST,
            PRODUCT_NODE_HOST,
            offered_catalog_codes,
            offered_catalog_hosts,
            product_country_catalog,
        )

        codes = offered_catalog_codes()
        hosts = offered_catalog_hosts()
        self.assertEqual(codes, tuple(n.code for n in product_country_catalog()))
        self.assertEqual(codes, ("DE",))
        self.assertNotIn("IS", codes)
        self.assertIn(PRODUCT_DE_HOST, hosts)
        self.assertNotIn(PRODUCT_NODE_HOST, hosts)
        offered = catalog_country_options()
        self.assertEqual([o.code for o in offered], ["DE"])
        self.assertFalse(any("iceland" in o.name.lower() for o in offered))

    def test_stale_is_heals_to_de(self) -> None:
        from client.country_select import parse_catalog_country_code
        from client.multihop import normalize_entry_country

        for raw in ("IS", "Iceland", "iceland", "is"):
            self.assertEqual(normalize_entry_country(raw), "DE", msg=repr(raw))
        self.assertEqual(parse_catalog_country_code("IS"), "DE")
        self.assertEqual(parse_catalog_country_code("Iceland"), "DE")
        self.assertEqual(normalize_entry_country("DE"), "DE")


class TestIcelandNotWipeTarget(unittest.TestCase):
    def test_wipe_codes_follow_offered_catalog(self) -> None:
        from client.multihop import offered_catalog_codes, product_country_catalog
        from node.fleet_wipe import (
            PREFERRED_FLEET_ORDER,
            fleet_country_codes,
            next_wipe_target,
            wipe_catalog_codes,
        )

        self.assertNotIn("IS", PREFERRED_FLEET_ORDER)
        wipe = wipe_catalog_codes()
        self.assertEqual(wipe, fleet_country_codes())
        self.assertEqual(set(wipe), set(offered_catalog_codes()))
        self.assertNotIn("IS", wipe)
        self.assertNotIn("IS", [n.code for n in product_country_catalog()])
        self.assertNotEqual(next_wipe_target(completed=[], in_progress=None), "IS")
        self.assertEqual(next_wipe_target(completed=[], in_progress=None), "DE")


class TestNoIcelandFailoverOrFirewall(unittest.TestCase):
    def test_try_order_and_drain_never_dial_iceland(self) -> None:
        from client.endpoint import PRODUCT_NODE_HOST
        from client.multihop import (
            PRODUCT_DE_HOST,
            ResidualUnavailable,
            default_single_hop,
            residual_try_order,
            select_residual_endpoint,
        )

        cfg = default_single_hop()
        order = residual_try_order(cfg)
        hosts = [e.host for e in order]
        self.assertEqual(hosts, [PRODUCT_DE_HOST])
        self.assertNotIn(PRODUCT_NODE_HOST, hosts)
        sel = select_residual_endpoint(
            cfg, entry_healthy=True, exit_healthy=True, entry_draining=False
        )
        self.assertEqual(sel.endpoint.host, PRODUCT_DE_HOST)
        self.assertNotEqual(sel.endpoint.host, PRODUCT_NODE_HOST)
        self.assertEqual(sel.reason, "entry_primary")
        with self.assertRaises(ResidualUnavailable):
            select_residual_endpoint(
                cfg, entry_healthy=True, exit_healthy=True, entry_draining=True
            )
        with self.assertRaises(ResidualUnavailable):
            select_residual_endpoint(
                cfg, entry_healthy=False, exit_healthy=True, entry_draining=False
            )

    def test_firewall_hosts_follow_offered_catalog(self) -> None:
        from client.endpoint import PRODUCT_NODE_HOST
        from client.multihop import PRODUCT_DE_HOST, offered_catalog_hosts
        from client.windows.firewall_allow import residual_firewall_hosts

        hosts = residual_firewall_hosts()
        self.assertEqual(set(hosts), set(offered_catalog_hosts()))
        self.assertIn(PRODUCT_DE_HOST, hosts)
        self.assertNotIn(PRODUCT_NODE_HOST, hosts)
        de_only = residual_firewall_hosts(server_host=PRODUCT_DE_HOST)
        self.assertNotIn(PRODUCT_NODE_HOST, de_only)
