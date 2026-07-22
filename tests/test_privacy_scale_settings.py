"""Privacy-scale Settings: optional residual layers on/off with policy resolution.

Drives shipped settings store + product_policy helpers (not a re-implemented
oracle). Structural checks ensure Windows Settings exposes toggles + explainers.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class TestPrivacyScaleDefaultsAndPersistence(unittest.TestCase):
    def test_defaults_privacy_max_optional_layers(self) -> None:
        from client.windows.settings_store import default_settings

        d = default_settings()
        self.assertTrue(d.privacy_traffic_shape)
        self.assertTrue(d.privacy_outer_obfuscation)
        self.assertFalse(d.privacy_multihop)  # single-hop product baseline
        self.assertFalse(d.run_at_startup)
        self.assertFalse(d.autoconnect_on_launch)

    def test_save_load_privacy_toggles(self) -> None:
        from client.windows.settings_store import (
            ProductSettings,
            load_settings,
            save_settings,
        )

        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "settings.json"
            s = ProductSettings(
                privacy_traffic_shape=False,
                privacy_outer_obfuscation=False,
                privacy_multihop=True,
            )
            save_settings(s, path=path)
            loaded = load_settings(path=path)
            self.assertFalse(loaded.privacy_traffic_shape)
            self.assertFalse(loaded.privacy_outer_obfuscation)
            self.assertTrue(loaded.privacy_multihop)
            # Legacy file without privacy keys → privacy-max defaults
            path.write_text(
                '{"run_at_startup": false, "autoconnect_on_launch": false}\n',
                encoding="utf-8",
            )
            legacy = load_settings(path=path)
            self.assertTrue(legacy.privacy_traffic_shape)
            self.assertTrue(legacy.privacy_outer_obfuscation)
            self.assertFalse(legacy.privacy_multihop)


class TestResolvedPrivacyPolicy(unittest.TestCase):
    def tearDown(self) -> None:
        for k in ("RPT_TRAFFIC_SHAPE", "RPT_OBFS", "RPT_MULTIHOP_ENABLED"):
            os.environ.pop(k, None)

    def test_defaults_resolve_privacy_on(self) -> None:
        from client.product_policy import (
            PrivacyScalePrefs,
            product_dataplane_traffic_shape,
            product_outer_obfuscation_enabled,
            resolve_privacy_policy,
        )
        from node.traffic_shape import DEFAULT_TRAFFIC_SHAPE

        # Force no env keys so settings prefs apply
        for k in ("RPT_TRAFFIC_SHAPE", "RPT_OBFS", "RPT_MULTIHOP_ENABLED"):
            os.environ.pop(k, None)
        prefs = PrivacyScalePrefs()  # product defaults
        pol = resolve_privacy_policy(prefs=prefs)
        self.assertTrue(pol.traffic_shape_enabled)
        self.assertTrue(pol.outer_obfuscation_enabled)
        self.assertFalse(pol.multihop_enabled)
        self.assertTrue(pol.residual_vpn_core)
        self.assertTrue(pol.admission_and_crypto)
        shape = product_dataplane_traffic_shape(prefs=prefs)
        self.assertTrue(shape.padding)
        self.assertGreater(shape.jitter_ms_max, 0)
        self.assertTrue(product_outer_obfuscation_enabled(prefs=prefs))
        # Core never off
        self.assertIsNot(shape, None)
        self.assertNotEqual(pol.residual_vpn_core, False)

    def test_user_disable_layers_observable_in_policy(self) -> None:
        from client.product_policy import (
            PrivacyScalePrefs,
            product_dataplane_traffic_shape,
            product_multihop_enabled,
            product_outer_obfuscation_enabled,
            resolve_privacy_policy,
        )
        from node.traffic_shape import DEFAULT_TRAFFIC_SHAPE

        for k in ("RPT_TRAFFIC_SHAPE", "RPT_OBFS", "RPT_MULTIHOP_ENABLED"):
            os.environ.pop(k, None)
        prefs = PrivacyScalePrefs(
            traffic_shape=False,
            outer_obfuscation=False,
            multihop=False,
        )
        pol = resolve_privacy_policy(prefs=prefs)
        self.assertFalse(pol.traffic_shape_enabled)
        self.assertFalse(pol.outer_obfuscation_enabled)
        self.assertFalse(pol.multihop_enabled)
        # Residual VPN core still represented
        self.assertTrue(pol.residual_vpn_core)
        self.assertTrue(pol.admission_and_crypto)
        shape = product_dataplane_traffic_shape(prefs=prefs)
        self.assertFalse(shape.padding)
        self.assertEqual(shape.jitter_ms_max, 0)
        self.assertFalse(shape.cover_traffic)
        self.assertEqual(shape, DEFAULT_TRAFFIC_SHAPE)
        self.assertFalse(product_outer_obfuscation_enabled(prefs=prefs))
        self.assertFalse(product_multihop_enabled(prefs=prefs))

    def test_env_override_wins_over_settings(self) -> None:
        from client.product_policy import (
            PrivacyScalePrefs,
            traffic_shape_enabled,
            product_outer_obfuscation_enabled,
        )

        prefs = PrivacyScalePrefs(traffic_shape=True, outer_obfuscation=True)
        os.environ["RPT_TRAFFIC_SHAPE"] = "0"
        os.environ["RPT_OBFS"] = "0"
        self.assertFalse(traffic_shape_enabled(prefs=prefs))
        self.assertFalse(product_outer_obfuscation_enabled(prefs=prefs))

    def test_settings_file_drives_policy_via_load(self) -> None:
        from client.product_policy import (
            load_privacy_scale_prefs,
            resolve_privacy_policy,
        )
        from client.windows.settings_store import ProductSettings, save_settings

        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "settings.json"
            save_settings(
                ProductSettings(
                    privacy_traffic_shape=False,
                    privacy_outer_obfuscation=True,
                    privacy_multihop=True,
                ),
                path=path,
            )
            for k in ("RPT_TRAFFIC_SHAPE", "RPT_OBFS", "RPT_MULTIHOP_ENABLED"):
                os.environ.pop(k, None)
            prefs = load_privacy_scale_prefs(settings_path=path)
            self.assertFalse(prefs.traffic_shape)
            self.assertTrue(prefs.outer_obfuscation)
            self.assertTrue(prefs.multihop)
            pol = resolve_privacy_policy(prefs=prefs)
            self.assertFalse(pol.traffic_shape_enabled)
            self.assertTrue(pol.outer_obfuscation_enabled)
            self.assertTrue(pol.multihop_enabled)
            self.assertTrue(pol.residual_vpn_core)

    def test_multihop_config_honors_product_policy_when_env_unset(self) -> None:
        from client.multihop import multihop_config_from_env
        from client.product_policy import PrivacyScalePrefs

        for k in ("RPT_MULTIHOP_ENABLED", "RPT_MULTIHOP_HOPS", "RPT_EXIT_HOST"):
            os.environ.pop(k, None)
        with mock.patch(
            "client.product_policy.product_multihop_enabled",
            return_value=True,
        ):
            cfg = multihop_config_from_env()
        self.assertTrue(cfg.enabled)
        with mock.patch(
            "client.product_policy.product_multihop_enabled",
            return_value=False,
        ):
            cfg2 = multihop_config_from_env()
        self.assertFalse(cfg2.enabled)


class TestWindowsSettingsUiStructure(unittest.TestCase):
    def test_settings_has_privacy_scale_toggles_and_explainers(self) -> None:
        src = (ROOT / "client" / "windows" / "app.py").read_text(encoding="utf-8")
        self.assertIn("Browsing speed / privacy scale", src)
        self.assertIn("privacy_traffic_shape", src)
        self.assertIn("privacy_outer_obfuscation", src)
        self.assertIn("privacy_multihop", src)
        self.assertIn("EXPLAINER_TRAFFIC_SHAPE", src)
        self.assertIn("EXPLAINER_OUTER_OBFUSCATION", src)
        self.assertIn("EXPLAINER_MULTIHOP", src)
        self.assertIn("EXPLAINER_CORE_VPN", src)
        self.assertIn("Traffic shaping (pad / jitter / cover)", src)
        self.assertIn("Outer obfuscation (QUIC-mimic wrap)", src)
        self.assertIn("Multi-hop residual (exit path)", src)
        # Connect still gates licence/keygen
        self.assertIn("needs_keygen_unlock", src)
        self.assertIn("assert_may_connect", src)
        self.assertIn("_start_connect", src)

    def test_explainers_state_honest_tradeoff(self) -> None:
        from client.product_policy import (
            EXPLAINER_CORE_VPN,
            EXPLAINER_MULTIHOP,
            EXPLAINER_OUTER_OBFUSCATION,
            EXPLAINER_TRAFFIC_SHAPE,
        )

        for text in (
            EXPLAINER_TRAFFIC_SHAPE,
            EXPLAINER_OUTER_OBFUSCATION,
            EXPLAINER_MULTIHOP,
        ):
            low = text.lower()
            self.assertTrue("on" in low and "off" in low)
            # Must not claim same privacy when off
            self.assertNotIn("same privacy", low)
        self.assertIn("cannot be turned off", EXPLAINER_CORE_VPN.lower())

    def test_connect_path_uses_product_outer_obfs_helper(self) -> None:
        src = (ROOT / "client" / "connect.py").read_text(encoding="utf-8")
        self.assertIn("_outer_obfs_enabled", src)
        self.assertIn("product_outer_obfuscation_enabled", src)
        self.assertIn("maybe_wrap(frame, enabled=_outer_obfs_enabled())", src)

    def test_tunnels_still_use_product_dataplane_shape(self) -> None:
        win = (ROOT / "client" / "windows" / "tunnel_win.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("product_dataplane_traffic_shape", win)


if __name__ == "__main__":
    unittest.main()
