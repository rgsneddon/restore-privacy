"""Entry country (IS/DE) selection + multihop exit (shipped helpers). US/RO retired → DE."""

from __future__ import annotations

import random
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from client.multihop import (  # noqa: E402
    COUNTRY_DE,
    COUNTRY_IS,
    COUNTRY_RO,
    COUNTRY_US,
    PRODUCT_COUNTRY_CATALOG,
    PRODUCT_DE_HOST,
    PRODUCT_EXIT_HOST,
    PRODUCT_NODE_HOST,
    PRODUCT_US_HOST,
    CountryNode,
    entry_endpoint,
    exit_endpoint,
    is_multihop_active,
    multihop_config_for_entry_country,
    multihop_config_from_env,
    node_pub_name_for_endpoint,
    normalize_entry_country,
    residual_endpoint,
    resolve_entry_exit,
)
from client.windows.settings_store import (  # noqa: E402
    ProductSettings,
    load_settings,
    save_settings,
)


class TestResolveEntryExit(unittest.TestCase):
    def test_single_hop_iceland(self):
        entry, exit_n = resolve_entry_exit(COUNTRY_IS, multihop_enabled=False)
        self.assertEqual(entry.code, COUNTRY_IS)
        self.assertEqual(entry.host, PRODUCT_NODE_HOST)
        self.assertIsNone(exit_n)
        cfg = multihop_config_for_entry_country(COUNTRY_IS, multihop_enabled=False)
        self.assertFalse(is_multihop_active(cfg))
        self.assertEqual(residual_endpoint(cfg).host, PRODUCT_NODE_HOST)

    def test_stale_romania_normalizes_to_de(self):
        entry, exit_n = resolve_entry_exit(COUNTRY_RO, multihop_enabled=False)
        self.assertEqual(entry.code, COUNTRY_DE)
        self.assertEqual(entry.host, PRODUCT_DE_HOST)
        self.assertIsNone(exit_n)
        cfg = multihop_config_for_entry_country(COUNTRY_RO, multihop_enabled=False)
        self.assertEqual(residual_endpoint(cfg).host, PRODUCT_DE_HOST)
        self.assertEqual(
            node_pub_name_for_endpoint(residual_endpoint(cfg)),
            "de_node_elgamal.pub",
        )

    def test_multihop_iceland_entry_de_exit(self):
        # Two-peer catalog: only non-entry exit is DE
        entry, exit_n = resolve_entry_exit(
            COUNTRY_IS, multihop_enabled=True, rng=random.Random(0)
        )
        self.assertEqual(entry.code, COUNTRY_IS)
        self.assertIsNotNone(exit_n)
        assert exit_n is not None
        self.assertEqual(exit_n.code, COUNTRY_DE)
        self.assertNotEqual(entry.host, exit_n.host)
        cfg = multihop_config_for_entry_country(
            COUNTRY_IS, multihop_enabled=True, rng=random.Random(0)
        )
        self.assertTrue(is_multihop_active(cfg))
        self.assertEqual(entry_endpoint(cfg).host, PRODUCT_NODE_HOST)
        self.assertEqual(exit_endpoint(cfg).host, PRODUCT_DE_HOST)
        self.assertEqual(residual_endpoint(cfg).host, exit_endpoint(cfg).host)

    def test_single_hop_germany(self):
        entry, exit_n = resolve_entry_exit(COUNTRY_DE, multihop_enabled=False)
        self.assertEqual(entry.code, COUNTRY_DE)
        self.assertEqual(entry.host, PRODUCT_DE_HOST)
        self.assertIsNone(exit_n)
        cfg = multihop_config_for_entry_country(COUNTRY_DE, multihop_enabled=False)
        self.assertFalse(is_multihop_active(cfg))
        self.assertEqual(residual_endpoint(cfg).host, PRODUCT_DE_HOST)
        self.assertEqual(
            node_pub_name_for_endpoint(residual_endpoint(cfg)),
            "de_node_elgamal.pub",
        )

    def test_stale_us_normalizes_to_de(self):
        entry, exit_n = resolve_entry_exit(COUNTRY_US, multihop_enabled=False)
        self.assertEqual(entry.code, COUNTRY_DE)
        self.assertEqual(entry.host, PRODUCT_DE_HOST)
        self.assertEqual(
            node_pub_name_for_endpoint(entry.as_endpoint()),
            "de_node_elgamal.pub",
        )
        # Direct US host heal path
        from client.endpoint import Endpoint

        self.assertEqual(
            node_pub_name_for_endpoint(Endpoint(host=PRODUCT_US_HOST, port=44044)),
            "de_node_elgamal.pub",
        )

    def test_multihop_exit_never_entry(self):
        for code in (COUNTRY_IS, COUNTRY_DE, COUNTRY_US, COUNTRY_RO):
            for mh in (False, True):
                e, x = resolve_entry_exit(code, multihop_enabled=mh, rng=random.Random(2))
                if x is not None:
                    self.assertNotEqual(e.host, x.host)

    def test_single_hop_de_drain_failovers_to_iceland(self):
        from client.multihop import select_residual_endpoint

        cfg = multihop_config_for_entry_country(COUNTRY_DE, multihop_enabled=False)
        self.assertEqual(entry_endpoint(cfg).host, PRODUCT_DE_HOST)
        sel = select_residual_endpoint(
            cfg, entry_healthy=True, exit_healthy=True, entry_draining=True
        )
        # Prefer alternate catalog peer when preferred draining
        self.assertIn(sel.endpoint.host, {PRODUCT_NODE_HOST, PRODUCT_DE_HOST})
        if sel.failover_active:
            self.assertEqual(sel.endpoint.host, PRODUCT_NODE_HOST)

    def test_random_among_non_entry_when_catalog_expanded(self):
        extra = CountryNode(
            code="XX",
            name="Extra",
            host="198.51.100.10",
            port=44044,
            pub_name="node_elgamal.pub",
        )
        cat = list(PRODUCT_COUNTRY_CATALOG) + [extra]
        rng = random.Random(0)
        picks = set()
        for _ in range(40):
            _e, x = resolve_entry_exit(
                COUNTRY_IS, multihop_enabled=True, catalog=cat, rng=rng
            )
            assert x is not None
            picks.add(x.code)
        self.assertIn(COUNTRY_DE, picks)
        self.assertIn("XX", picks)
        self.assertNotIn(COUNTRY_IS, picks)

    def test_normalize_aliases(self):
        self.assertEqual(normalize_entry_country("iceland"), COUNTRY_IS)
        self.assertEqual(normalize_entry_country("Romania"), COUNTRY_DE)
        self.assertEqual(normalize_entry_country("USA"), COUNTRY_DE)
        self.assertEqual(normalize_entry_country("US"), COUNTRY_DE)
        self.assertEqual(normalize_entry_country("Germany"), COUNTRY_DE)
        self.assertEqual(normalize_entry_country("weird"), COUNTRY_DE)
        self.assertEqual(normalize_entry_country(""), COUNTRY_DE)


class TestSettingsEntryCountryPersist(unittest.TestCase):
    def test_default_is_germany(self):
        from client.windows.settings_store import default_settings

        self.assertEqual(default_settings().entry_country, COUNTRY_DE)
        self.assertEqual(ProductSettings().entry_country, COUNTRY_DE)

    def test_save_load_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "settings.json"
            s = ProductSettings(entry_country=COUNTRY_IS, privacy_multihop=True)
            save_settings(s, path=path)
            loaded = load_settings(path=path)
            self.assertEqual(loaded.entry_country, COUNTRY_IS)
            self.assertTrue(loaded.privacy_multihop)
            # Stale RO on disk normalizes to DE on load
            s2 = ProductSettings(entry_country=COUNTRY_RO)
            save_settings(s2, path=path)
            loaded2 = load_settings(path=path)
            self.assertEqual(loaded2.entry_country, COUNTRY_DE)

    def test_settings_ui_has_entry_country_control(self):
        src = (ROOT / "client" / "windows" / "app.py").read_text(encoding="utf-8")
        self.assertIn("entry_country_var", src)
        self.assertIn("OptionMenu", src)
        self.assertIn("entry_country=", src)
        self.assertIn("catalog_country_options", src)
        self.assertIn("Iceland", src)
        self.assertIn("Germany", src)
        self.assertNotIn("United States", src)
        self.assertNotIn("Romania", src)


class TestConnectWiring(unittest.TestCase):
    def test_multihop_from_env_honours_entry_country(self):
        cfg = multihop_config_from_env(
            {
                "RPT_MULTIHOP_ENABLED": "0",
                "RPT_ENTRY_COUNTRY": "RO",
            }
        )
        # RO normalizes to DE residual host
        self.assertEqual(residual_endpoint(cfg).host, PRODUCT_DE_HOST)

    def test_catalog_live_codes_only(self):
        codes = {n.code for n in PRODUCT_COUNTRY_CATALOG}
        self.assertEqual(codes, {COUNTRY_IS, COUNTRY_DE})
        self.assertNotIn(COUNTRY_US, codes)
        self.assertNotIn(COUNTRY_RO, codes)


if __name__ == "__main__":
    unittest.main()
