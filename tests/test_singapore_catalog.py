"""Singapore is a live residual catalog peer; Germany stays default."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class TestSingaporeCatalog(unittest.TestCase):
    def test_offered_menu_includes_singapore_and_germany(self) -> None:
        from client.country_select import catalog_country_options, parse_catalog_country_code
        from client.multihop import (
            DEFAULT_ENTRY_COUNTRY,
            PRODUCT_DE_HOST,
            PRODUCT_SG_HOST,
            normalize_entry_country,
            offered_catalog_codes,
            offered_catalog_hosts,
        )

        self.assertEqual(DEFAULT_ENTRY_COUNTRY, "DE")
        self.assertEqual(offered_catalog_codes(), ("DE", "SG"))
        hosts = offered_catalog_hosts()
        self.assertIn(PRODUCT_DE_HOST, hosts)
        self.assertIn(PRODUCT_SG_HOST, hosts)
        opts = catalog_country_options()
        self.assertEqual([o.code for o in opts], ["DE", "SG"])
        self.assertTrue(any(o.name == "Singapore" for o in opts))
        self.assertEqual(normalize_entry_country("SG"), "SG")
        self.assertEqual(normalize_entry_country("Singapore"), "SG")
        self.assertEqual(parse_catalog_country_code("SG"), "SG")
        self.assertEqual(normalize_entry_country(""), "DE")
        self.assertEqual(normalize_entry_country("IS"), "DE")

    def test_singapore_dials_sg_host_not_germany(self) -> None:
        from client.multihop import (
            PRODUCT_DE_HOST,
            PRODUCT_SG_HOST,
            country_node_for_code,
            resolve_entry_exit,
        )

        sg = country_node_for_code("SG")
        de = country_node_for_code("DE")
        self.assertEqual(sg.host, PRODUCT_SG_HOST)
        self.assertNotEqual(sg.host, PRODUCT_DE_HOST)
        self.assertEqual(de.host, PRODUCT_DE_HOST)
        entry_sg, _ = resolve_entry_exit("SG", multihop_enabled=False)
        entry_de, _ = resolve_entry_exit("DE", multihop_enabled=False)
        self.assertEqual(entry_sg.host, PRODUCT_SG_HOST)
        self.assertEqual(entry_de.host, PRODUCT_DE_HOST)


class TestSingaporePin(unittest.TestCase):
    def test_sg_and_de_pins_are_distinct_elgamal_pubs(self) -> None:
        from client.endpoint import Endpoint
        from client.multihop import (
            PRODUCT_DE_HOST,
            PRODUCT_SG_HOST,
            node_pub_name_for_endpoint,
        )
        from client.residual_pub_ensure import residual_node_pub_name_for_host
        from node.elgamal import ElGamalPublicKey

        self.assertEqual(
            residual_node_pub_name_for_host(PRODUCT_SG_HOST), "sg_node_elgamal.pub"
        )
        self.assertEqual(
            node_pub_name_for_endpoint(Endpoint(host=PRODUCT_SG_HOST, port=44044)),
            "sg_node_elgamal.pub",
        )
        self.assertEqual(
            residual_node_pub_name_for_host(PRODUCT_DE_HOST), "de_node_elgamal.pub"
        )
        sg = ROOT / "product" / "sg_node_elgamal.pub"
        de = ROOT / "product" / "de_node_elgamal.pub"
        self.assertTrue(sg.is_file())
        self.assertTrue(de.is_file())
        self.assertEqual(sg.stat().st_size, 256)
        self.assertEqual(de.stat().st_size, 256)
        self.assertNotEqual(sg.read_bytes(), de.read_bytes())
        ElGamalPublicKey.import_bytes(sg.read_bytes())
        ElGamalPublicKey.import_bytes(de.read_bytes())
