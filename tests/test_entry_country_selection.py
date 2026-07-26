"""Entry country (IS/RO) selection + multihop exit complement/random (shipped helpers)."""

from __future__ import annotations

import random
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from client.multihop import (  # noqa: E402
    COUNTRY_IS,
    COUNTRY_RO,
    COUNTRY_US,
    PRODUCT_COUNTRY_CATALOG,
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

    def test_single_hop_romania(self):
        entry, exit_n = resolve_entry_exit(COUNTRY_RO, multihop_enabled=False)
        self.assertEqual(entry.code, COUNTRY_RO)
        self.assertEqual(entry.host, PRODUCT_EXIT_HOST)
        self.assertIsNone(exit_n)
        cfg = multihop_config_for_entry_country(COUNTRY_RO, multihop_enabled=False)
        self.assertFalse(is_multihop_active(cfg))
        self.assertEqual(residual_endpoint(cfg).host, PRODUCT_EXIT_HOST)
        self.assertEqual(
            node_pub_name_for_endpoint(residual_endpoint(cfg)),
            "exit_node_elgamal.pub",
        )

    def test_multihop_iceland_entry_non_entry_exit(self):
        # Three-peer catalog: exit is RNG among non-entry peers (RO or US).
        entry, exit_n = resolve_entry_exit(
            COUNTRY_IS, multihop_enabled=True, rng=random.Random(0)
        )
        self.assertEqual(entry.code, COUNTRY_IS)
        self.assertIsNotNone(exit_n)
        assert exit_n is not None
        self.assertIn(exit_n.code, (COUNTRY_RO, COUNTRY_US))
        self.assertNotEqual(entry.host, exit_n.host)
        cfg = multihop_config_for_entry_country(
            COUNTRY_IS, multihop_enabled=True, rng=random.Random(0)
        )
        self.assertTrue(is_multihop_active(cfg))
        self.assertEqual(entry_endpoint(cfg).host, PRODUCT_NODE_HOST)
        self.assertNotEqual(exit_endpoint(cfg).host, PRODUCT_NODE_HOST)
        # Residual-via-exit when multihop active
        self.assertEqual(residual_endpoint(cfg).host, exit_endpoint(cfg).host)

    def test_single_hop_united_states(self):
        entry, exit_n = resolve_entry_exit(COUNTRY_US, multihop_enabled=False)
        self.assertEqual(entry.code, COUNTRY_US)
        self.assertEqual(entry.host, PRODUCT_US_HOST)
        self.assertIsNone(exit_n)
        cfg = multihop_config_for_entry_country(COUNTRY_US, multihop_enabled=False)
        self.assertFalse(is_multihop_active(cfg))
        self.assertEqual(residual_endpoint(cfg).host, PRODUCT_US_HOST)
        self.assertEqual(
            node_pub_name_for_endpoint(residual_endpoint(cfg)),
            "us_node_elgamal.pub",
        )

    def test_multihop_is_can_pick_us_exit(self):
        """With ≥3 peers, multihop exit among non-entry can include US."""
        seen: set[str] = set()
        for seed in range(40):
            _e, x = resolve_entry_exit(
                COUNTRY_IS, multihop_enabled=True, rng=random.Random(seed)
            )
            assert x is not None
            seen.add(x.code)
        self.assertIn(COUNTRY_RO, seen)
        self.assertIn(COUNTRY_US, seen)
        self.assertNotIn(COUNTRY_IS, seen)

    def test_multihop_romania_entry_non_entry_exit(self):
        entry, exit_n = resolve_entry_exit(
            COUNTRY_RO, multihop_enabled=True, rng=random.Random(1)
        )
        self.assertEqual(entry.code, COUNTRY_RO)
        self.assertIsNotNone(exit_n)
        assert exit_n is not None
        self.assertEqual(exit_n.code, COUNTRY_IS)
        cfg = multihop_config_for_entry_country(
            COUNTRY_RO, multihop_enabled=True, rng=random.Random(1)
        )
        self.assertTrue(is_multihop_active(cfg))
        self.assertEqual(entry_endpoint(cfg).host, PRODUCT_EXIT_HOST)
        self.assertNotEqual(exit_endpoint(cfg).host, PRODUCT_EXIT_HOST)
        self.assertEqual(residual_endpoint(cfg).host, exit_endpoint(cfg).host)

    def test_exit_never_equals_entry(self):
        for code in (COUNTRY_IS, COUNTRY_RO):
            for mh in (False, True):
                e, x = resolve_entry_exit(code, multihop_enabled=mh, rng=random.Random(2))
                if x is not None:
                    self.assertNotEqual(e.host, x.host)

    def test_single_hop_romania_failover_is_iceland_not_ro(self):
        """Preferred entry=RO must not failover to PRODUCT_EXIT_HOST (also RO)."""
        from client.multihop import (
            alternate_peer_endpoint,
            exit_endpoint,
            select_residual_endpoint,
        )

        cfg = multihop_config_for_entry_country(COUNTRY_RO, multihop_enabled=False)
        self.assertEqual(entry_endpoint(cfg).host, PRODUCT_EXIT_HOST)
        alt = alternate_peer_endpoint(cfg)
        self.assertEqual(alt.host, PRODUCT_NODE_HOST)
        self.assertNotEqual(alt.host, entry_endpoint(cfg).host)
        self.assertEqual(exit_endpoint(cfg).host, PRODUCT_NODE_HOST)
        sel = select_residual_endpoint(
            cfg, entry_healthy=True, exit_healthy=True, entry_draining=True
        )
        self.assertEqual(sel.reason, "exit_failover")
        self.assertEqual(sel.endpoint.host, PRODUCT_NODE_HOST)
        self.assertTrue(sel.failover_active)

    def test_random_among_non_entry_when_catalog_expanded(self):
        """With ≥3 countries, exit is RNG-picked among non-entry peers."""
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
        # Should see both RO and XX across draws
        self.assertIn(COUNTRY_RO, picks)
        self.assertIn("XX", picks)
        self.assertNotIn(COUNTRY_IS, picks)

    def test_normalize_aliases(self):
        self.assertEqual(normalize_entry_country("iceland"), COUNTRY_IS)
        self.assertEqual(normalize_entry_country("Romania"), COUNTRY_RO)
        self.assertEqual(normalize_entry_country("USA"), COUNTRY_US)
        self.assertEqual(normalize_entry_country("United States"), COUNTRY_US)
        self.assertEqual(normalize_entry_country("weird"), COUNTRY_US)


class TestSettingsEntryCountryPersist(unittest.TestCase):
    def test_default_is_united_states(self):
        from client.windows.settings_store import default_settings

        self.assertEqual(default_settings().entry_country, COUNTRY_US)

    def test_save_load_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "settings.json"
            s = ProductSettings(entry_country=COUNTRY_RO, privacy_multihop=True)
            save_settings(s, path=path)
            loaded = load_settings(path=path)
            self.assertEqual(loaded.entry_country, COUNTRY_RO)
            self.assertTrue(loaded.privacy_multihop)

    def test_settings_ui_has_entry_country_control(self):
        src = (ROOT / "client" / "windows" / "app.py").read_text(encoding="utf-8")
        self.assertIn("entry_country_var", src)
        self.assertIn("Entry country (node)", src)
        self.assertIn("OptionMenu", src)
        self.assertIn("entry_country=", src)
        # Main shell + Settings list all three catalog countries with flags
        self.assertIn("catalog_country_options", src)
        self.assertIn("country_frame", src)
        self.assertIn("Iceland", src)
        self.assertIn("Romania", src)


class TestConnectWiring(unittest.TestCase):
    def test_multihop_from_env_honours_entry_country(self):
        cfg = multihop_config_from_env(
            {
                "RPT_MULTIHOP_ENABLED": "0",
                "RPT_ENTRY_COUNTRY": "RO",
            }
        )
        self.assertEqual(residual_endpoint(cfg).host, PRODUCT_EXIT_HOST)

        cfg2 = multihop_config_from_env(
            {
                "RPT_MULTIHOP_ENABLED": "1",
                "RPT_ENTRY_COUNTRY": "RO",
            }
        )
        self.assertTrue(is_multihop_active(cfg2))
        self.assertEqual(entry_endpoint(cfg2).host, PRODUCT_EXIT_HOST)
        # Multi-hop exit is a non-entry catalog peer (IS or DE when three peers).
        self.assertNotEqual(exit_endpoint(cfg2).host, PRODUCT_EXIT_HOST)
        self.assertNotEqual(exit_endpoint(cfg2).host, entry_endpoint(cfg2).host)

    def test_connect_module_uses_select_residual_and_multihop_from_env(self):
        src = (ROOT / "client" / "connect.py").read_text(encoding="utf-8")
        self.assertIn("select_residual_endpoint", src)
        self.assertIn("multihop_config_from_env", src)
        # Windows re-establish refreshes multihop from env/settings
        app = (ROOT / "client" / "windows" / "app.py").read_text(encoding="utf-8")
        self.assertIn("multihop_config_from_env", app)
        self.assertIn("entry_country", app)

    def test_start_connect_refreshes_multihop_from_settings(self):
        """Windows Connect must reload Settings path before residual dial.

        Without this, saving entry_country while disconnected leaves
        RptClient.multihop at app-init defaults (always Iceland).
        """
        app = (ROOT / "client" / "windows" / "app.py").read_text(encoding="utf-8")
        self.assertIn("def _refresh_multihop_from_settings", app)
        self.assertIn("def _start_connect", app)
        # Slice only _start_connect → next top-level method
        start = app.index("    def _start_connect")
        # Next method after _start_connect at class indent
        rest = app[start + 1 :]
        # Find next "    def " at method level after body starts
        end_rel = rest.find("\n    def ")
        self.assertGreater(end_rel, 0)
        connect_src = app[start : start + 1 + end_rel]
        self.assertIn("_refresh_multihop_from_settings()", connect_src)
        # Refresh is the first substantive call (before residual dial work)
        self.assertLess(
            connect_src.index("_refresh_multihop_from_settings()"),
            connect_src.index("has_accepted_licence"),
        )
        # Helper assigns multihop_config_from_env onto the client
        refresh_start = app.index("    def _refresh_multihop_from_settings")
        refresh_end = app.index("    def _on_toggle_connect", refresh_start)
        refresh_src = app[refresh_start:refresh_end]
        self.assertIn("multihop_config_from_env()", refresh_src)
        self.assertIn("self.client.multihop", refresh_src)
        # Settings save also refreshes while disconnected
        self.assertIn(
            "self._refresh_multihop_from_settings()",
            app[app.index("def _save_privacy") : app.index("def _save_privacy") + 2500],
        )


if __name__ == "__main__":
    unittest.main()
