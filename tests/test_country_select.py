"""Entry-country selector: Iceland default, flags, Connect gate (shipped helpers)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from client.country_select import (  # noqa: E402
    catalog_country_options,
    country_flag_emoji,
    default_entry_country,
    entry_country_allows_connect,
    label_to_country_code,
    option_label_for_code,
    parse_catalog_country_code,
    resolve_entry_country_selection,
)
from client.multihop import (  # noqa: E402
    COUNTRY_DE,
    COUNTRY_IS,
    COUNTRY_RO,
    PRODUCT_COUNTRY_CATALOG,
    PRODUCT_EXIT_HOST,
    PRODUCT_NODE_HOST,
    multihop_config_for_entry_country,
    residual_endpoint,
)
from client.endpoint import Endpoint  # noqa: E402


class TestCountrySelectPure(unittest.TestCase):
    def test_default_is_iceland(self):
        self.assertEqual(default_entry_country(), COUNTRY_IS)
        ok, code, reason = resolve_entry_country_selection(None)
        self.assertTrue(ok)
        self.assertEqual(code, COUNTRY_IS)
        self.assertEqual(reason, "default_iceland")
        ok2, code2, _ = resolve_entry_country_selection("")
        self.assertTrue(ok2)
        self.assertEqual(code2, COUNTRY_IS)

    def test_valid_catalog_accepted(self):
        for raw, want in (
            ("IS", COUNTRY_IS),
            ("iceland", COUNTRY_IS),
            ("RO", COUNTRY_RO),
            ("Romania", COUNTRY_RO),
            ("DE", COUNTRY_DE),
            ("Germany", COUNTRY_DE),
        ):
            ok, code, reason = resolve_entry_country_selection(raw)
            self.assertTrue(ok, raw)
            self.assertEqual(code, want, raw)
            self.assertEqual(reason, "ok", raw)
            self.assertTrue(entry_country_allows_connect(raw))

    def test_invalid_refuses_connect(self):
        for bad in ("XX", "US", "not-a-country", "??"):
            ok, code, reason = resolve_entry_country_selection(bad)
            self.assertFalse(ok, bad)
            self.assertEqual(code, "")
            self.assertEqual(reason, "invalid_entry_country")
            self.assertFalse(entry_country_allows_connect(bad))
            self.assertIsNone(parse_catalog_country_code(bad))

    def test_missing_without_default_blocks(self):
        ok, code, reason = resolve_entry_country_selection(
            "", allow_default=False
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "missing_entry_country")
        self.assertFalse(
            entry_country_allows_connect("", allow_default=False)
        )

    def test_flags_and_catalog_options(self):
        opts = catalog_country_options(PRODUCT_COUNTRY_CATALOG)
        codes = [o.code for o in opts]
        self.assertEqual(set(codes), {COUNTRY_IS, COUNTRY_RO, COUNTRY_DE})
        self.assertEqual(len(opts), 3)
        for o in opts:
            self.assertTrue(o.flag, o.code)
            self.assertIn(o.code, o.label())
            self.assertIn(o.name, o.label())
            self.assertEqual(country_flag_emoji(o.code), o.flag)
            # Flag appears before name in menu label
            self.assertTrue(o.label().startswith(o.flag))
        # label round-trip
        for o in opts:
            self.assertEqual(label_to_country_code(o.label()), o.code)
        self.assertEqual(
            option_label_for_code(None).count(COUNTRY_IS)
            + (1 if COUNTRY_IS in option_label_for_code(None) else 0),
            option_label_for_code(None).count(COUNTRY_IS)
            + (1 if COUNTRY_IS in option_label_for_code(None) else 0),
        )
        self.assertIn(COUNTRY_IS, option_label_for_code(None))
        self.assertIn(COUNTRY_RO, option_label_for_code("RO"))

    def test_flags_present_for_catalog_countries(self):
        self.assertTrue(country_flag_emoji("IS"))
        self.assertTrue(country_flag_emoji("RO"))
        self.assertTrue(country_flag_emoji("DE"))
        self.assertEqual(country_flag_emoji("IS"), "\U0001f1ee\U0001f1f8")


class TestConnectPathUsesSelection(unittest.TestCase):
    def test_multihop_config_honours_selected_entry(self):
        # Default Iceland residual
        cfg_is = multihop_config_for_entry_country("IS", multihop_enabled=False)
        self.assertEqual(residual_endpoint(cfg_is).host, PRODUCT_NODE_HOST)
        # Romania entry
        cfg_ro = multihop_config_for_entry_country("RO", multihop_enabled=False)
        self.assertEqual(residual_endpoint(cfg_ro).host, PRODUCT_EXIT_HOST)
        # Germany when in catalog
        de_hosts = {
            n.host for n in PRODUCT_COUNTRY_CATALOG if n.code == COUNTRY_DE
        }
        self.assertTrue(de_hosts)
        cfg_de = multihop_config_for_entry_country("DE", multihop_enabled=False)
        self.assertIn(residual_endpoint(cfg_de).host, de_hosts)
        # Invalid selection does not get a residual dial via gate
        self.assertFalse(entry_country_allows_connect("US"))

    def test_windows_app_struct_country_above_connect(self):
        src = (ROOT / "client" / "windows" / "app.py").read_text(encoding="utf-8")
        # Country control exists on main shell
        self.assertIn("entry_country", src.lower() or src)
        self.assertIn("country_select", src or "")
        # Pack order: country frame before connect button in bottom
        c_i = src.find("country_frame")
        if c_i < 0:
            c_i = src.find("_country_row")
        if c_i < 0:
            c_i = src.find("country_menu")
        b_i = src.find("connect_btn.pack")
        self.assertGreater(c_i, 0, "main shell must build a country control")
        self.assertGreater(b_i, 0)
        # country construction before connect pack (above in bottom column)
        self.assertLess(c_i, b_i)
        self.assertIn("entry_country_allows_connect", src)
        self.assertIn("catalog_country_options", src)

    def test_flutter_struct_country_above_connect(self):
        main = (ROOT / "client_app" / "lib" / "main.dart").read_text(
            encoding="utf-8"
        )
        self.assertIn("entryCountry", main)
        self.assertIn("DropdownButton", main)
        # Dropdown appears before ElevatedButton Connect in source order
        d_i = main.find("DropdownButton")
        e_i = main.find("ElevatedButton")
        self.assertGreater(d_i, 0)
        self.assertGreater(e_i, 0)
        self.assertLess(d_i, e_i)
        store = (ROOT / "client_app" / "lib" / "settings_store.dart").read_text(
            encoding="utf-8"
        )
        self.assertIn("entryCountry", store)
        self.assertIn("entry_country", store)
        sel = (ROOT / "client_app" / "lib" / "country_select.dart").read_text(
            encoding="utf-8"
        )
        self.assertIn("Iceland", sel)
        self.assertIn("Romania", sel)
        self.assertIn("Germany", sel)
        self.assertIn("defaultEntryCountry", sel)
        self.assertIn("kCountryGermany", sel)
        # Three catalog codes with flag emojis in shared Flutter list
        self.assertIn("kProductCountryCatalog", sel)
        self.assertIn("'IS'", sel)
        self.assertIn("'RO'", sel)
        self.assertIn("'DE'", sel)

    def test_linux_app_struct_country_above_connect(self):
        src = (ROOT / "client" / "linux" / "app.py").read_text(encoding="utf-8")
        self.assertIn("country_select", src)
        self.assertIn("catalog_country_options", src)
        self.assertIn("entry_country_allows_connect", src)
        c_i = src.find("country_frame")
        if c_i < 0:
            c_i = src.find("_country_row")
        if c_i < 0:
            c_i = src.find("country_menu")
        b_i = src.find("connect_btn.pack")
        self.assertGreater(c_i, 0, "Linux main shell must build a country control")
        self.assertGreater(b_i, 0)
        self.assertLess(c_i, b_i)
        store = (ROOT / "client" / "linux" / "settings_store.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("entry_country", store)
        self.assertIn("KEY_ENTRY_COUNTRY", store)

    def test_de_pub_bundled_and_native_host_map(self):
        """DE catalog option must ship de_node_elgamal.pub + host→pub mapping."""
        de_asset = (
            ROOT
            / "client_app"
            / "android"
            / "app"
            / "src"
            / "main"
            / "assets"
            / "secrets"
            / "de_node_elgamal.pub"
        )
        self.assertTrue(de_asset.is_file(), "Android assets missing de_node_elgamal.pub")
        self.assertGreaterEqual(de_asset.stat().st_size, 32)
        product_de = ROOT / "product" / "de_node_elgamal.pub"
        self.assertTrue(product_de.is_file())
        # Android residual HELLO maps DE monopin host → de pub
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
        self.assertIn("de_node_elgamal.pub", vpn)
        self.assertIn("PRODUCT_DE_HOST", vpn)
        self.assertIn("167.233.224.5", vpn)
        self.assertIn("residualNodePubNameForHost", vpn)
        # preBuild inject must re-heal DE pin (not only force-tracked asset)
        gradle = (
            ROOT / "client_app" / "android" / "app" / "build.gradle.kts"
        ).read_text(encoding="utf-8")
        self.assertIn("de_node_elgamal.pub", gradle)
        self.assertIn("copyRptSecretsToAssets", gradle)
        # Apple inject ships DE pub
        inject = (ROOT / "scripts" / "inject_apple_secrets.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("de_node_elgamal.pub", inject)
        self.assertIn("PUBLIC_PUBS", inject)
        self.assertIn("DE_PUB", inject)
        # Flutter derives pub from dial host (not entry-only multi-hop guess)
        sel = (ROOT / "client_app" / "lib" / "country_select.dart").read_text(
            encoding="utf-8"
        )
        self.assertIn("residualNodePubNameForHost", sel)
        self.assertIn("de_node_elgamal.pub", sel)
        cfg = (ROOT / "client_app" / "lib" / "rpt_config.dart").read_text(
            encoding="utf-8"
        )
        self.assertIn("residualNodePubNameForHost(host)", cfg)
        # Apple native maps DE host + fail closed (no IS fallback for DE)
        for rel in (
            "client_app/macos/NativePrep/RptSecrets.swift",
            "client_app/ios/NativePrep/RptSecrets.swift",
            "client_app/apple_shared/Rpt2/Sources/Rpt2/RptSecrets.swift",
        ):
            sw = (ROOT / rel).read_text(encoding="utf-8")
            self.assertIn("de_node_elgamal.pub", sw, rel)
            self.assertIn("167.233.224.5", sw, rel)
        for rel in (
            "client_app/macos/NativePrep/RptSecrets.swift",
            "client_app/ios/NativePrep/RptSecrets.swift",
        ):
            sw = (ROOT / rel).read_text(encoding="utf-8")
            self.assertIn("refuse Iceland entry pub fallback", sw, rel)
            self.assertNotIn("Fall back to entry pub if exit pub missing", sw, rel)

    def test_inject_apple_and_android_include_de_pub(self):
        """Shipped inject paths list de_node so rebuilds re-heal DE pin."""
        inject = (ROOT / "scripts" / "inject_apple_secrets.py").read_text(
            encoding="utf-8"
        )
        # PUBLIC_PUBS must include all three catalog pins
        self.assertIn('DE_PUB = "de_node_elgamal.pub"', inject)
        self.assertIn("PUBLIC_PUBS = (NODE_PUB, EXIT_PUB, DE_PUB)", inject)
        # Runnable: resolve product DE pub
        sys.path.insert(0, str(ROOT / "scripts"))
        import inject_apple_secrets as ias  # noqa: E402

        self.assertIn(ias.DE_PUB, ias.PUBLIC_PUBS)
        p = ias.resolve_pub(ias.DE_PUB, None)
        self.assertIsNotNone(p)
        assert p is not None
        self.assertTrue(p.is_file())
        self.assertGreaterEqual(p.stat().st_size, 32)


if __name__ == "__main__":
    unittest.main()
