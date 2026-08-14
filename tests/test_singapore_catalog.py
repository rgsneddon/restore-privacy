"""Singapore is a live residual catalog peer; Germany stays default."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class TestSingaporeCatalog(unittest.TestCase):
    def test_catalog_pin_is_1_2_7(self) -> None:
        pin = (ROOT / "client" / "VERSION").read_text(encoding="utf-8").strip()
        self.assertEqual(pin, "1.2.7")
        from client.connection_log import product_client_version

        self.assertEqual(product_client_version(), "1.2.7")
        downloads = (ROOT / "status_page" / "downloads.py").read_text(encoding="utf-8")
        self.assertIn('RELEASE_VERSION = "1.2.7"', downloads)

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

    def test_seed_catalog_public_keys_copies_sg_pin(self) -> None:
        import tempfile

        from client.residual_pub_ensure import (
            CATALOG_PUBLIC_PUBS,
            seed_catalog_public_keys,
        )

        self.assertIn("sg_node_elgamal.pub", CATALOG_PUBLIC_PUBS)
        with tempfile.TemporaryDirectory() as td:
            dest = Path(td)
            installed = seed_catalog_public_keys(dest, [ROOT / "product"])
            self.assertIn("sg_node_elgamal.pub", installed)
            copied = dest / "sg_node_elgamal.pub"
            self.assertTrue(copied.is_file())
            self.assertEqual(
                copied.read_bytes(),
                (ROOT / "product" / "sg_node_elgamal.pub").read_bytes(),
            )

    def test_ios_and_android_hello_pin_maps_singapore(self) -> None:
        ios = (
            ROOT
            / "client_app"
            / "ios"
            / "NativePrep"
            / "RptSecrets.swift"
        ).read_text(encoding="utf-8")
        fn = ios.index("func residualNodePubName(forHost")
        body = ios[fn : fn + 1200]
        self.assertIn("productSgHost", body)
        self.assertIn("sgNodePubName", body)
        self.assertIn("sg_node_elgamal.pub", ios)
        self.assertIn("sgNodePubName", ios.split("catalogPublicPubNames")[1][:400])

        from tests.test_android_de_residual_pin import (
            residual_node_pub_name_for_host_from_source,
        )

        vpn = (
            ROOT
            / "client_app"
            / "android"
            / "app"
            / "src"
            / "main"
            / "kotlin"
            / "com"
            / "restoreprivacy"
            / "restore_privacy_client"
            / "RptVpnService.kt"
        ).read_text(encoding="utf-8")
        self.assertEqual(
            residual_node_pub_name_for_host_from_source(vpn, "5.223.48.8"),
            "sg_node_elgamal.pub",
        )
        gradle = (
            ROOT / "client_app" / "android" / "app" / "build.gradle.kts"
        ).read_text(encoding="utf-8")
        names = gradle.split("val names = listOf(")[1].split(")")[0]
        self.assertIn("sg_node_elgamal.pub", names)

    def test_python_secrets_loader_loads_sg_pin_not_iceland(self) -> None:
        import tempfile

        from client.endpoint import Endpoint, product_sg_node_elgamal_pub_path
        from client.secrets_loader import (
            CATALOG_NODE_PUB_NAMES,
            load_node_elgamal_public,
            load_node_elgamal_public_for_endpoint,
            sync_catalog_public_pubs_into,
        )

        self.assertIn("sg_node_elgamal.pub", CATALOG_NODE_PUB_NAMES)
        sg_path = product_sg_node_elgamal_pub_path()
        self.assertTrue(sg_path.is_file())
        loaded = load_node_elgamal_public(pub_name="sg_node_elgamal.pub")
        self.assertEqual(loaded.export(), sg_path.read_bytes())
        via_ep = load_node_elgamal_public_for_endpoint(
            Endpoint(host="5.223.48.8", port=44044)
        )
        self.assertEqual(via_ep.export(), sg_path.read_bytes())
        with tempfile.TemporaryDirectory() as td:
            dest = Path(td)
            installed = sync_catalog_public_pubs_into(dest)
            self.assertIn("sg_node_elgamal.pub", installed)
            self.assertEqual(
                (dest / "sg_node_elgamal.pub").read_bytes(),
                sg_path.read_bytes(),
            )
