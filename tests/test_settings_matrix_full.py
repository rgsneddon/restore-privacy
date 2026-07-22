"""Full privacy-scale settings matrix + keygen gate (shipped helpers only)."""

from __future__ import annotations

import itertools
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class TestPrivacyScaleFullMatrix(unittest.TestCase):
    def tearDown(self) -> None:
        for k in ("RPT_TRAFFIC_SHAPE", "RPT_OBFS", "RPT_MULTIHOP_ENABLED"):
            os.environ.pop(k, None)

    def test_all_eight_combinations_resolve_and_core_stays_on(self) -> None:
        from client.product_policy import (
            PrivacyScalePrefs,
            product_dataplane_traffic_shape,
            product_outer_obfuscation_enabled,
            resolve_privacy_policy,
        )
        from client.uk_ping_estimates import all_privacy_scale_prefs
        from node.obfuscation import maybe_wrap
        from node.protocol import MAGIC

        for k in ("RPT_TRAFFIC_SHAPE", "RPT_OBFS", "RPT_MULTIHOP_ENABLED"):
            os.environ.pop(k, None)

        combos = all_privacy_scale_prefs()
        self.assertEqual(len(combos), 8)
        for prefs in combos:
            pol = resolve_privacy_policy(prefs=prefs)
            self.assertEqual(pol.traffic_shape_enabled, prefs.traffic_shape)
            self.assertEqual(pol.outer_obfuscation_enabled, prefs.outer_obfuscation)
            self.assertEqual(pol.multihop_enabled, prefs.multihop)
            self.assertTrue(pol.residual_vpn_core)
            self.assertTrue(pol.admission_and_crypto)
            shape = product_dataplane_traffic_shape(prefs=prefs)
            if prefs.traffic_shape:
                self.assertTrue(shape.padding)
            else:
                self.assertFalse(shape.padding)
            # Outer wrap path accepts both modes (node bare/obfs)
            inner = MAGIC + b"\x00" * 8 + b"payload-test"
            wire = maybe_wrap(
                inner,
                enabled=product_outer_obfuscation_enabled(prefs=prefs),
            )
            if prefs.outer_obfuscation:
                self.assertNotEqual(wire[:4], MAGIC)
            else:
                self.assertEqual(wire[:4], MAGIC)

    def test_persist_all_combos_roundtrip(self) -> None:
        from client.windows.settings_store import (
            ProductSettings,
            load_settings,
            save_settings,
        )
        from client.uk_ping_estimates import all_privacy_scale_prefs

        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "settings.json"
            for prefs in all_privacy_scale_prefs():
                s = ProductSettings(
                    privacy_traffic_shape=prefs.traffic_shape,
                    privacy_outer_obfuscation=prefs.outer_obfuscation,
                    privacy_multihop=prefs.multihop,
                )
                save_settings(s, path=path)
                loaded = load_settings(path=path)
                self.assertEqual(loaded.privacy_traffic_shape, prefs.traffic_shape)
                self.assertEqual(
                    loaded.privacy_outer_obfuscation, prefs.outer_obfuscation
                )
                self.assertEqual(loaded.privacy_multihop, prefs.multihop)

    def test_hot_apply_all_shape_combos_on_plane(self) -> None:
        try:
            from client.dataplane import RptDataPlane
            from node.crypto_session import SessionCrypto
        except ImportError:
            self.skipTest("cryptography not installed")
        from client.privacy_live import hot_apply_privacy_scale
        from client.product_policy import PRODUCT_ENABLED_TRAFFIC_SHAPE, PrivacyScalePrefs

        for k in ("RPT_TRAFFIC_SHAPE", "RPT_OBFS", "RPT_MULTIHOP_ENABLED"):
            os.environ.pop(k, None)

        class _Sess:
            def __init__(self) -> None:
                self.crypto = SessionCrypto(
                    key=b"m" * 32, traffic_shape=PRODUCT_ENABLED_TRAFFIC_SHAPE
                )

        class _Client:
            def __init__(self) -> None:
                self.session = _Sess()
                self._sock = object()

        client = _Client()
        plane = RptDataPlane(
            client, traffic_shape=PRODUCT_ENABLED_TRAFFIC_SHAPE  # type: ignore[arg-type]
        )
        for shape, obfs in itertools.product((True, False), repeat=2):
            prefs = PrivacyScalePrefs(
                traffic_shape=shape, outer_obfuscation=obfs, multihop=False
            )
            r = hot_apply_privacy_scale(
                dataplane=plane,
                client=client,
                prefs=prefs,
                previous_multihop=False,
                connected=True,
            )
            self.assertTrue(r.shaping_hot_applied)
            self.assertEqual(plane.traffic_shape.padding, shape)
            self.assertTrue(r.policy.residual_vpn_core)

    def test_keygen_still_required_across_privacy_defaults(self) -> None:
        from client.licence_gate import accept_licence, assert_may_connect, needs_keygen_unlock
        from client.payment_entitlement import PaymentEntitlement, save_payment_entitlement

        os.environ["RPT_REQUIRE_PAYMENT_ENTITLEMENT"] = "1"
        try:
            with tempfile.TemporaryDirectory() as td:
                lic = Path(td) / "licence_acceptance.json"
                pay = Path(td) / "payment_entitlement.json"
                accept_licence(lic)
                save_payment_entitlement(PaymentEntitlement(), path=pay)
                with mock.patch(
                    "client.payment_entitlement.default_entitlement_path",
                    return_value=pay,
                ):
                    self.assertTrue(needs_keygen_unlock(lic))
                    with mock.patch(
                        "client.payment_entitlement.ensure_entitlement_for_connect",
                        side_effect=lambda **k: PaymentEntitlement(),
                    ):
                        ok, msg = assert_may_connect(lic)
                    self.assertFalse(ok)
                    self.assertIn("keygen", msg.lower())
        finally:
            os.environ.pop("RPT_REQUIRE_PAYMENT_ENTITLEMENT", None)


if __name__ == "__main__":
    unittest.main()
