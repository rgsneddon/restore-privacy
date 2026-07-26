"""Entry-country selector: Germany/DE default, flags, Connect gate (shipped helpers)."""

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
    COUNTRY_IS,
    COUNTRY_RO,
    COUNTRY_US,
    PRODUCT_COUNTRY_CATALOG,
    PRODUCT_EXIT_HOST,
    PRODUCT_NODE_HOST,
    PRODUCT_US_HOST,
    multihop_config_for_entry_country,
    residual_endpoint,
)
from client.endpoint import Endpoint  # noqa: E402


class TestCountrySelectPure(unittest.TestCase):
    def test_default_is_united_states(self):
        """Empty selection resolves to US via shipped default_entry_country()."""
        from client.multihop import (
            DEFAULT_ENTRY_COUNTRY,
            PRODUCT_US_HOST,
            country_node_for_code,
        )

        self.assertEqual(DEFAULT_ENTRY_COUNTRY, COUNTRY_US)
        self.assertEqual(default_entry_country(), COUNTRY_US)
        ok, code, reason = resolve_entry_country_selection(None)
        self.assertTrue(ok)
        self.assertEqual(code, COUNTRY_US)
        self.assertEqual(reason, "default_united_states")
        ok2, code2, _ = resolve_entry_country_selection("")
        self.assertTrue(ok2)
        self.assertEqual(code2, COUNTRY_US)
        # Default dials US residual host + us_node pub
        node = country_node_for_code(None)
        self.assertEqual(node.code, COUNTRY_US)
        self.assertEqual(node.host, PRODUCT_US_HOST)
        self.assertEqual(node.pub_name, "us_node_elgamal.pub")

    def test_stale_de_normalizes_to_default_us(self):
        """Saved DE prefs must not dial retired Germany monopin."""
        from client.multihop import PRODUCT_DE_HOST, normalize_entry_country, country_node_for_code

        self.assertEqual(normalize_entry_country("DE"), COUNTRY_US)
        self.assertEqual(normalize_entry_country("Germany"), COUNTRY_US)
        n = country_node_for_code("DE")
        self.assertEqual(n.code, COUNTRY_US)
        self.assertNotEqual(n.host, PRODUCT_DE_HOST)

    def test_explicit_is_still_respected(self):
        ok, code, reason = resolve_entry_country_selection("IS")
        self.assertTrue(ok)
        self.assertEqual(code, COUNTRY_IS)
        self.assertEqual(reason, "ok")

    def test_valid_catalog_accepted(self):
        for raw, want in (
            ("IS", COUNTRY_IS),
            ("iceland", COUNTRY_IS),
            ("RO", COUNTRY_RO),
            ("Romania", COUNTRY_RO),
            ("US", COUNTRY_US),
            ("USA", COUNTRY_US),
            ("United States", COUNTRY_US),
        ):
            ok, code, reason = resolve_entry_country_selection(raw)
            self.assertTrue(ok, raw)
            self.assertEqual(code, want, raw)
            self.assertEqual(reason, "ok", raw)
            self.assertTrue(entry_country_allows_connect(raw))

    def test_invalid_refuses_connect(self):
        for bad in ("XX", "CA", "not-a-country", "??"):
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
        self.assertEqual(set(codes), {COUNTRY_IS, COUNTRY_RO, COUNTRY_US})
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
        # Empty code → product default US label
        self.assertIn(COUNTRY_US, option_label_for_code(None))
        self.assertIn("United States", option_label_for_code(None))
        self.assertIn(COUNTRY_RO, option_label_for_code("RO"))
        self.assertIn(COUNTRY_IS, option_label_for_code("IS"))
        self.assertIn(COUNTRY_US, option_label_for_code("US"))

    def test_flags_present_for_catalog_countries(self):
        self.assertTrue(country_flag_emoji("IS"))
        self.assertTrue(country_flag_emoji("RO"))
        self.assertTrue(country_flag_emoji("US"))
        self.assertEqual(country_flag_emoji("IS"), "\U0001f1ee\U0001f1f8")
        self.assertEqual(country_flag_emoji("US"), "\U0001f1fa\U0001f1f8")


class TestConnectPathUsesSelection(unittest.TestCase):
    def test_multihop_config_honours_selected_entry(self):
        # Default Iceland residual
        cfg_is = multihop_config_for_entry_country("IS", multihop_enabled=False)
        self.assertEqual(residual_endpoint(cfg_is).host, PRODUCT_NODE_HOST)
        # Romania entry
        cfg_ro = multihop_config_for_entry_country("RO", multihop_enabled=False)
        self.assertEqual(residual_endpoint(cfg_ro).host, PRODUCT_EXIT_HOST)
        # United States entry
        cfg_us = multihop_config_for_entry_country("US", multihop_enabled=False)
        self.assertEqual(residual_endpoint(cfg_us).host, PRODUCT_US_HOST)
        # Stale DE selection normalizes to US monopin (peer removed)
        cfg_de = multihop_config_for_entry_country("DE", multihop_enabled=False)
        self.assertEqual(residual_endpoint(cfg_de).host, PRODUCT_US_HOST)
        # No DE row in product catalog
        self.assertFalse(
            any(n.code == "DE" for n in PRODUCT_COUNTRY_CATALOG)
        )
        # US is a valid catalog entry
        self.assertTrue(entry_country_allows_connect("US"))
        # Invalid selection does not get a residual dial via gate
        self.assertFalse(entry_country_allows_connect("CA"))

    def test_settings_stale_de_normalizes_and_empty_is_us(self):
        """Stale Settings DE must not dial retired monopin; empty → US."""
        import os
        import tempfile
        import unittest.mock as mock

        from client.multihop import (
            PRODUCT_US_HOST,
            multihop_config_from_env,
            select_residual_endpoint,
        )
        from client.windows.settings_store import (
            ProductSettings,
            load_settings,
            save_settings,
        )

        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "settings.json"
            # save_settings normalizes DE → US
            save_settings(ProductSettings(entry_country="DE"), path=p)
            loaded = load_settings(path=p)
            self.assertEqual(loaded.entry_country, COUNTRY_US)

            env_clean = {
                k: v
                for k, v in os.environ.items()
                if k
                not in (
                    "RPT_ENTRY_COUNTRY",
                    "RPT_MULTIHOP_ENABLED",
                    "RPT_MULTIHOP_HOPS",
                    "RPT_EXIT_HOST",
                )
            }
            with mock.patch.dict(os.environ, env_clean, clear=True):
                with mock.patch(
                    "client.windows.settings_store.load_settings",
                    return_value=loaded,
                ):
                    cfg = multihop_config_from_env()
            self.assertEqual(residual_endpoint(cfg).host, PRODUCT_US_HOST)
            sel = select_residual_endpoint(cfg)
            self.assertEqual(sel.endpoint.host, PRODUCT_US_HOST)
            self.assertEqual(sel.reason, "entry_primary")
            # Unset / empty defaults to United States residual host
            empty_settings = ProductSettings(entry_country="")
            with mock.patch.dict(os.environ, env_clean, clear=True):
                with mock.patch(
                    "client.windows.settings_store.load_settings",
                    return_value=empty_settings,
                ):
                    cfg_def = multihop_config_from_env()
            self.assertEqual(residual_endpoint(cfg_def).host, PRODUCT_US_HOST)

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
        # Connect must sync FROM durable settings (not overwrite DE with stale IS)
        self.assertIn("_sync_main_entry_from_settings", src)
        start_i = src.find("def _start_connect")
        self.assertGreater(start_i, 0)
        next_def = src.find("\n    def ", start_i + 10)
        start_body = src[start_i : next_def if next_def > 0 else start_i + 2500]
        self.assertIn("_sync_main_entry_from_settings", start_body)
        # Must not re-save main-shell label over Settings on Connect
        self.assertNotIn("self._on_main_entry_country_changed()", start_body)
        self.assertIn("_ok_bind_and_close", src)
        ok_i = src.find("def _ok_bind_and_close")
        ok_body = src[ok_i : ok_i + 1200]
        self.assertIn("_sync_main_entry_from_settings", ok_body)

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
        self.assertIn("United States", sel)
        self.assertIn("defaultEntryCountry", sel)
        # Catalog IS + RO + US (Germany residual peer removed)
        self.assertIn("kProductCountryCatalog", sel)
        self.assertIn("'IS'", sel)
        self.assertIn("'RO'", sel)
        self.assertIn("'US'", sel)
        self.assertIn("5.161.242.85", sel)
        self.assertIn("us_node_elgamal.pub", sel)
        self.assertNotIn("167.233.224.5", sel)
        self.assertNotIn("de_node_elgamal.pub", sel)

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

    def test_catalog_is_ro_us_no_de_dial_path(self):
        """Product residual catalog is IS+RO+US; no DE monopin dial identity."""
        from client.multihop import PRODUCT_COUNTRY_CATALOG, PRODUCT_DE_HOST

        codes = {n.code for n in PRODUCT_COUNTRY_CATALOG}
        self.assertEqual(codes, {COUNTRY_IS, COUNTRY_RO, COUNTRY_US})
        hosts = {n.host for n in PRODUCT_COUNTRY_CATALOG}
        self.assertIn(PRODUCT_US_HOST, hosts)
        self.assertNotIn(PRODUCT_DE_HOST, hosts)
        # Android residual HELLO includes US (no PRODUCT_DE_HOST dial)
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
        self.assertIn("residualNodePubNameForHost", vpn)
        self.assertIn("PRODUCT_ENTRY_HOST", vpn)
        self.assertIn("PRODUCT_EXIT_HOST", vpn)
        self.assertIn("PRODUCT_US_HOST", vpn)
        self.assertIn("us_node_elgamal.pub", vpn)
        self.assertNotIn("PRODUCT_DE_HOST", vpn)
        self.assertNotIn("167.233.224.5", vpn)
        # Flutter catalog has US monopin, omits DE
        sel = (ROOT / "client_app" / "lib" / "country_select.dart").read_text(
            encoding="utf-8"
        )
        self.assertIn("residualNodePubNameForHost", sel)
        self.assertIn("5.161.242.85", sel)
        self.assertIn("us_node_elgamal.pub", sel)
        self.assertNotIn("167.233.224.5", sel)
        self.assertNotIn("de_node_elgamal.pub", sel)
        cfg = (ROOT / "client_app" / "lib" / "rpt_config.dart").read_text(
            encoding="utf-8"
        )
        self.assertIn("residualNodePubNameForHost(host)", cfg)

    def test_inject_apple_and_android_include_is_ro_us_pubs(self):
        """Shipped inject paths list IS/RO/US public pins for residual HELLO."""
        inject = (ROOT / "scripts" / "inject_apple_secrets.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("node_elgamal.pub", inject)
        self.assertIn("exit_node_elgamal.pub", inject)
        self.assertIn("us_node_elgamal.pub", inject)
        # DE pin may remain as archive in product/ but must not be required dial path
        sys.path.insert(0, str(ROOT / "scripts"))
        import inject_apple_secrets as ias  # noqa: E402

        # At least IS entry pub resolves
        p = ias.resolve_pub("node_elgamal.pub", None)
        self.assertIsNotNone(p)
        assert p is not None
        self.assertTrue(p.is_file())
        self.assertGreaterEqual(p.stat().st_size, 32)


if __name__ == "__main__":
    unittest.main()
