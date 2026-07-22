"""Privacy-scale hot-apply while residual is connected (shipped path)."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class TestDataplaneApplyTrafficShape(unittest.TestCase):
    def test_apply_traffic_shape_updates_plane_and_crypto(self) -> None:
        try:
            from client.dataplane import RptDataPlane
            from node.crypto_session import SessionCrypto
        except ImportError:
            self.skipTest("cryptography not installed")
        from client.product_policy import (
            PRODUCT_ENABLED_TRAFFIC_SHAPE,
            PrivacyScalePrefs,
            product_dataplane_traffic_shape,
        )
        from node.traffic_shape import DEFAULT_TRAFFIC_SHAPE

        class _Sess:
            def __init__(self) -> None:
                self.crypto = SessionCrypto(
                    key=b"k" * 32, traffic_shape=PRODUCT_ENABLED_TRAFFIC_SHAPE
                )

        class _Client:
            def __init__(self) -> None:
                self.session = _Sess()
                self._sock = object()

        client = _Client()
        plane = RptDataPlane(
            client, traffic_shape=PRODUCT_ENABLED_TRAFFIC_SHAPE  # type: ignore[arg-type]
        )
        self.assertTrue(plane.traffic_shape.padding)
        self.assertTrue(client.session.crypto.traffic_shape.padding)

        off = product_dataplane_traffic_shape(
            prefs=PrivacyScalePrefs(traffic_shape=False)
        )
        plane.apply_traffic_shape(off)
        self.assertFalse(plane.traffic_shape.padding)
        self.assertEqual(plane.traffic_shape.jitter_ms_max, 0)
        self.assertFalse(plane.traffic_shape.cover_traffic)
        self.assertFalse(client.session.crypto.traffic_shape.padding)
        self.assertEqual(client.session.crypto.traffic_shape, DEFAULT_TRAFFIC_SHAPE)

        # Re-enable hot
        on = product_dataplane_traffic_shape(
            prefs=PrivacyScalePrefs(traffic_shape=True)
        )
        plane.apply_traffic_shape(on)
        self.assertTrue(plane.traffic_shape.padding)
        self.assertGreater(plane.traffic_shape.jitter_ms_max, 0)
        self.assertTrue(client.session.crypto.traffic_shape.padding)


class TestHotApplyPrivacyScale(unittest.TestCase):
    def tearDown(self) -> None:
        for k in ("RPT_TRAFFIC_SHAPE", "RPT_OBFS", "RPT_MULTIHOP_ENABLED"):
            os.environ.pop(k, None)

    def test_hot_apply_disables_shaping_on_live_plane(self) -> None:
        try:
            from client.dataplane import RptDataPlane
            from node.crypto_session import SessionCrypto
        except ImportError:
            self.skipTest("cryptography not installed")
        from client.privacy_live import hot_apply_privacy_scale
        from client.product_policy import (
            PRODUCT_ENABLED_TRAFFIC_SHAPE,
            PrivacyScalePrefs,
        )

        for k in ("RPT_TRAFFIC_SHAPE", "RPT_OBFS", "RPT_MULTIHOP_ENABLED"):
            os.environ.pop(k, None)

        class _Sess:
            def __init__(self) -> None:
                self.crypto = SessionCrypto(
                    key=b"p" * 32, traffic_shape=PRODUCT_ENABLED_TRAFFIC_SHAPE
                )

        class _Client:
            def __init__(self) -> None:
                self.session = _Sess()
                self._sock = object()

        client = _Client()
        plane = RptDataPlane(
            client, traffic_shape=PRODUCT_ENABLED_TRAFFIC_SHAPE  # type: ignore[arg-type]
        )
        # (a) start privacy-max
        self.assertTrue(plane.traffic_shape.padding)

        # (b) user disables shaping + obfs via same helper Settings uses
        prefs_off = PrivacyScalePrefs(
            traffic_shape=False, outer_obfuscation=False, multihop=False
        )
        result = hot_apply_privacy_scale(
            dataplane=plane,
            client=client,
            prefs=prefs_off,
            previous_multihop=False,
            connected=True,
        )
        # (c) live policy / plane match off without new Connect entry
        self.assertTrue(result.shaping_hot_applied)
        self.assertTrue(result.obfuscation_live)
        self.assertFalse(result.policy.traffic_shape_enabled)
        self.assertFalse(result.policy.outer_obfuscation_enabled)
        self.assertTrue(result.policy.residual_vpn_core)
        self.assertFalse(plane.traffic_shape.padding)
        self.assertEqual(plane.traffic_shape.jitter_ms_max, 0)
        self.assertIn("hot-applied", result.message.lower())
        self.assertNotIn("next connect only", result.message.lower())

        # re-enable restores on
        prefs_on = PrivacyScalePrefs(
            traffic_shape=True, outer_obfuscation=True, multihop=False
        )
        result2 = hot_apply_privacy_scale(
            dataplane=plane,
            client=client,
            prefs=prefs_on,
            previous_multihop=False,
            connected=True,
        )
        self.assertTrue(result2.policy.traffic_shape_enabled)
        self.assertTrue(plane.traffic_shape.padding)
        self.assertGreater(plane.traffic_shape.jitter_ms_max, 0)

    def test_multihop_toggle_while_connected_flags_reconnect(self) -> None:
        from client.privacy_live import hot_apply_privacy_scale
        from client.product_policy import PrivacyScalePrefs

        for k in ("RPT_TRAFFIC_SHAPE", "RPT_OBFS", "RPT_MULTIHOP_ENABLED"):
            os.environ.pop(k, None)
        r = hot_apply_privacy_scale(
            prefs=PrivacyScalePrefs(multihop=True),
            previous_multihop=False,
            connected=True,
        )
        self.assertTrue(r.multihop_reconnect_needed)
        self.assertIn("re-establishing", r.message.lower())
        r2 = hot_apply_privacy_scale(
            prefs=PrivacyScalePrefs(multihop=True),
            previous_multihop=True,
            connected=True,
        )
        self.assertFalse(r2.multihop_reconnect_needed)

    def test_prefs_from_product_settings(self) -> None:
        from client.privacy_live import prefs_from_product_settings
        from client.windows.settings_store import ProductSettings

        s = ProductSettings(
            privacy_traffic_shape=False,
            privacy_outer_obfuscation=True,
            privacy_multihop=True,
        )
        p = prefs_from_product_settings(s)
        self.assertFalse(p.traffic_shape)
        self.assertTrue(p.outer_obfuscation)
        self.assertTrue(p.multihop)


class TestWindowsSettingsHotApplyStructure(unittest.TestCase):
    def test_settings_hot_applies_while_connected(self) -> None:
        src = (ROOT / "client" / "windows" / "app.py").read_text(encoding="utf-8")
        self.assertIn("hot_apply_privacy_scale", src)
        self.assertIn("_reestablish_residual_for_privacy_scale", src)
        self.assertIn("def _save_privacy", src)
        # Must not claim shape/obfs only apply on next Connect as product truth
        save_fn = src.split("def _save_privacy")[1].split("def _row")[0] if "def _row" in src.split("def _save_privacy")[1] else src.split("def _save_privacy")[1][:2500]
        # Prefer checking the _save_privacy body does not use next-Connect-only for live path
        privacy_block = src[src.index("def _save_privacy") : src.index("def _save_privacy") + 1800]
        self.assertIn("hot_apply_privacy_scale", privacy_block)
        self.assertNotIn("applies on next Connect", privacy_block)
        # Multi-hop reconnect while connected
        self.assertIn("multihop_reconnect_needed", privacy_block)
        self.assertIn("_reestablish_residual_for_privacy_scale", privacy_block)
        # Controls are Checkbuttons with command — no state=DISABLED on privacy toggles
        priv_section = src[
            src.index("Browsing speed / privacy scale") : src.index(
                "Browsing speed / privacy scale"
            )
            + 3500
        ]
        self.assertNotIn("state=tk.DISABLED", priv_section)
        self.assertNotIn('state="disabled"', priv_section)
        self.assertIn("hot-apply", priv_section.lower() or src.lower())
        # Live copy for connected users
        self.assertIn("Changes apply live while connected", src)
        self.assertNotIn(
            "Privacy-scale changes apply on the next Connect",
            src,
        )

    def test_privacy_live_module_shipped(self) -> None:
        path = ROOT / "client" / "privacy_live.py"
        self.assertTrue(path.is_file())
        text = path.read_text(encoding="utf-8")
        self.assertIn("def hot_apply_privacy_scale", text)
        self.assertIn("apply_traffic_shape", text)


if __name__ == "__main__":
    unittest.main()
