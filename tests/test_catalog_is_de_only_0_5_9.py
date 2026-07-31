"""Live residual catalog is IS + DE only; US/RO normalize to DE; monopin 0.5.9."""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class TestLiveCatalogIsDeOnly(unittest.TestCase):
    def test_product_country_catalog_codes(self):
        from client.multihop import PRODUCT_US_HOST, product_country_catalog

        codes = {n.code for n in product_country_catalog()}
        hosts = {n.host for n in product_country_catalog()}
        self.assertEqual(codes, {"IS", "DE"})
        self.assertNotIn("US", codes)
        self.assertNotIn("RO", codes)
        self.assertNotIn(PRODUCT_US_HOST, hosts)
        self.assertNotIn("5.161.242.85", hosts)

    def test_normalize_stale_us_and_ro_to_de(self):
        from client.multihop import DEFAULT_ENTRY_COUNTRY, normalize_entry_country

        self.assertEqual(DEFAULT_ENTRY_COUNTRY, "DE")
        for raw in ("US", "USA", "United States", "AMERICA", "RO", "Romania", ""):
            self.assertEqual(normalize_entry_country(raw), "DE", msg=repr(raw))
        self.assertEqual(normalize_entry_country("IS"), "IS")
        self.assertEqual(normalize_entry_country("DE"), "DE")

    def test_us_host_pub_heals_to_de(self):
        from client.endpoint import Endpoint
        from client.multihop import PRODUCT_US_HOST, node_pub_name_for_endpoint
        from client.residual_pub_ensure import residual_node_pub_name_for_host

        self.assertEqual(
            residual_node_pub_name_for_host(PRODUCT_US_HOST), "de_node_elgamal.pub"
        )
        self.assertEqual(
            node_pub_name_for_endpoint(Endpoint(host=PRODUCT_US_HOST, port=44044)),
            "de_node_elgamal.pub",
        )

    def test_fleet_order_is_de(self):
        from node.fleet_wipe import PREFERRED_FLEET_ORDER, fleet_country_codes

        self.assertEqual(PREFERRED_FLEET_ORDER, ("IS", "DE"))
        self.assertEqual(fleet_country_codes(), ["IS", "DE"])

    def test_monopin_version_0_5_9(self):
        ver = (ROOT / "client" / "VERSION").read_text(encoding="utf-8").strip()
        self.assertEqual(ver, "0.5.9")
        dl = (ROOT / "status_page" / "downloads.py").read_text(encoding="utf-8")
        self.assertIn('RELEASE_VERSION = "0.5.9"', dl)
        pub = (ROOT / "client_app" / "pubspec.yaml").read_text(encoding="utf-8")
        self.assertTrue(re.search(r"^version:\s*0\.5\.9\+", pub, flags=re.M))
        dart = (ROOT / "client_app" / "lib" / "rpt_config.dart").read_text(
            encoding="utf-8"
        )
        self.assertIn("productVersion = '0.5.9'", dart)
        dart_cat = (ROOT / "client_app" / "lib" / "country_select.dart").read_text(
            encoding="utf-8"
        )
        block = dart_cat.split("kProductCountryCatalog")[1].split("];")[0]
        self.assertNotIn("5.161.242.85", block)
        self.assertIn("82.221.101.241", block)
        self.assertIn("178.105.187.178", block)

    def test_keygen_unlock_is_version_agnostic(self):
        from client.payment_entitlement import keygen_unlock_is_version_agnostic

        # Monopin bump alone must not force re-unlock
        self.assertTrue(keygen_unlock_is_version_agnostic())

    def test_macos_vpn_protocol_reuse_in_source(self):
        """Structural gate: seamless upgrade reuses existing NETunnelProviderProtocol."""
        swift = (
            ROOT
            / "client_app"
            / "macos"
            / "NativePrep"
            / "RptVpnChannel.swift"
        ).read_text(encoding="utf-8")
        self.assertIn("applyProductPacketTunnelProtocol", swift)
        self.assertIn("Seamless upgrade", swift)
        self.assertIn(
            "manager.protocolConfiguration as? NETunnelProviderProtocol",
            swift,
        )
        # Must not always allocate a brand-new protocol without reuse path
        self.assertIn("proto = existing", swift)


if __name__ == "__main__":
    unittest.main()
