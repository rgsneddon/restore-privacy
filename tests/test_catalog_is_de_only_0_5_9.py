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
        self.assertEqual(codes, {"DE", "SG"})
        self.assertNotIn("IS", codes)
        self.assertNotIn("US", codes)
        self.assertNotIn("RO", codes)
        self.assertNotIn(PRODUCT_US_HOST, hosts)
        self.assertNotIn("5.161.242.85", hosts)
        self.assertNotIn("82.221.101.241", hosts)

    def test_normalize_stale_us_and_ro_to_de(self):
        from client.multihop import DEFAULT_ENTRY_COUNTRY, normalize_entry_country

        self.assertEqual(DEFAULT_ENTRY_COUNTRY, "DE")
        for raw in ("US", "USA", "United States", "AMERICA", "RO", "Romania", ""):
            self.assertEqual(normalize_entry_country(raw), "DE", msg=repr(raw))
        self.assertEqual(normalize_entry_country("IS"), "DE")
        self.assertEqual(normalize_entry_country("Iceland"), "DE")
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

        self.assertEqual(PREFERRED_FLEET_ORDER, ("DE", "SG"))
        self.assertEqual(fleet_country_codes(), ["DE", "SG"])
        self.assertNotIn("IS", fleet_country_codes())

    def test_live_monopin_and_is_de_catalog(self):
        """Live Suite monopin is 1.0.0; IS+DE product catalog peers remain (no US)."""
        ver = (ROOT / "client" / "VERSION").read_text(encoding="utf-8").strip()
        self.assertEqual(ver, "1.0.0")
        dl = (ROOT / "status_page" / "downloads.py").read_text(encoding="utf-8")
        self.assertIn(f'RELEASE_VERSION = "{ver}"', dl)
        self.assertNotIn('RELEASE_VERSION = "0.5.9"', dl)
        pub = (ROOT / "client_app" / "pubspec.yaml").read_text(encoding="utf-8")
        self.assertTrue(re.search(rf"^version:\s*{re.escape(ver)}\+", pub, flags=re.M))
        dart = (ROOT / "client_app" / "lib" / "rpt_config.dart").read_text(
            encoding="utf-8"
        )
        self.assertIn(f"productVersion = '{ver}'", dart)
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

    def test_rpt_secrets_declare_de_node_pub_name(self):
        """Every Apple RptSecrets enum must declare deNodePubName (US heal returns it)."""
        rels = [
            "client_app/macos/NativePrep/RptSecrets.swift",
            "client_app/macos/NativePrep/Rpt2/RptSecrets.swift",
            "client_app/ios/NativePrep/RptSecrets.swift",
            "client_app/ios/NativePrep/Rpt2/RptSecrets.swift",
            "client_app/apple_shared/Rpt2/Sources/Rpt2/RptSecrets.swift",
        ]
        for rel in rels:
            text = (ROOT / rel).read_text(encoding="utf-8")
            self.assertIn(
                'public static let deNodePubName = "de_node_elgamal.pub"',
                text,
                msg=rel,
            )
            self.assertIn("return deNodePubName", text, msg=rel)
            # US host branch must not still return usNodePubName
            self.assertNotIn("return usNodePubName", text, msg=rel)

    def test_current_docs_do_not_list_us_as_live_catalog_peer(self):
        """Exhaustive scanner: current product surfaces must not present US as live."""
        # Fixed allowlist of *current* surfaces only (not RELEASE_NOTES / old handoffs).
        allowlist = [
            ROOT / "README.md",
            ROOT / "status_page" / "public" / "README.md",
            ROOT / "PRIVACY_POLICY.md",
            ROOT / "status_page" / "public" / "PRIVACY_POLICY.md",
            ROOT / "docs" / "NODE_WIPE_REINSTALL.md",
            ROOT / "CREDITS.md",
            ROOT / "status_page" / "public" / "CREDITS.md",
            ROOT / "status_page" / "node_wipe_countdown.py",
            ROOT / "status_page" / "admin_panel.py",
            ROOT / "scripts" / "run_security_audit.py",
            ROOT / "AUDIT.md",
            ROOT / "status_page" / "AUDIT.md",
            ROOT / "status_page" / "public" / "AUDIT.md",
        ]
        # Live-presentation patterns (not every English “US” or heal-constant host IP).
        forbidden = [
            "is then de then us",
            "is → de → us",
            "is → de → us",
            "IS then DE then US",
            "IS → DE → US",
            "IS/DE/US",
            "IS / DE / US",
            "**IS** / **DE** (default) / **US**",
            "and the **US** residual host",
            "and the US residual host",
            "catalog pubs IS/DE/US",
            "catalog peers include **Iceland**, **Germany** (default entry), and the **US**",
            "then **US**",
            "then US)",
            "then US).",
            "monopin fleet peers IS/DE/US",
        ]
        offenders: list[str] = []
        for path in allowlist:
            self.assertTrue(path.is_file(), f"missing current surface {path}")
            text = path.read_text(encoding="utf-8")
            low = text.lower()
            for pat in forbidden:
                if pat.lower() in low:
                    offenders.append(f"{path.relative_to(ROOT)}: contains {pat!r}")
            # HONESTY_BLURB / fleet sentence must not advertise US without retired
            if path.name == "node_wipe_countdown.py":
                # Import shipped blurb
                sys.path.insert(0, str(ROOT / "status_page"))
                from node_wipe_countdown import HONESTY_BLURB  # noqa: E402

                bl = HONESTY_BLURB.lower()
                self.assertIn("is then de", bl)
                self.assertNotIn("is then de then us", bl)
                self.assertNotIn("then us", bl)

        self.assertEqual(
            offenders,
            [],
            msg="current surfaces still present US as live catalog/fleet peer:\n"
            + "\n".join(offenders),
        )
        # Positive IS+DE catalog wording still present on primary README
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertTrue(
            "Catalog residual peers: **IS** / **DE** (default)" in readme
            or "Catalog peers: **IS** / **DE** (default) only" in readme
            or ("**IS**" in readme and "**DE**" in readme and "default" in readme),
            "README must state IS/DE residual catalog peers",
        )
        self.assertIn("82.221.101.241", readme)
        self.assertIn("178.105.187.178", readme)
        privacy = (ROOT / "PRIVACY_POLICY.md").read_text(encoding="utf-8")
        self.assertIn("retired", privacy.lower())


if __name__ == "__main__":
    unittest.main()
