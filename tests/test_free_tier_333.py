"""Free-tier 3.3.3 policy — locked lean Iceland residual; permanent version pin."""

from __future__ import annotations

import os
import unittest


class TestFreeTierConstants(unittest.TestCase):
    def test_version_is_exactly_3_3_3(self):
        from client.free_tier import FREE_TIER_VERSION

        self.assertEqual(FREE_TIER_VERSION, "3.3.3")
        # Never look like a 0.x catalog pin
        self.assertFalse(FREE_TIER_VERSION.startswith("0."))

    def test_iceland_entry_only(self):
        from client.endpoint import PRODUCT_NODE_HOST
        from client.free_tier import FREE_TIER_ENTRY_HOST, free_tier_policy

        self.assertEqual(FREE_TIER_ENTRY_HOST, PRODUCT_NODE_HOST)
        p = free_tier_policy()
        self.assertEqual(p.residual_host(), PRODUCT_NODE_HOST)
        self.assertFalse(p.multihop)
        self.assertFalse(p.traffic_shape)
        self.assertFalse(p.outer_obfuscation)
        self.assertTrue(p.settings_locked)
        self.assertTrue(p.residual_vpn_core)


class TestFreeTierEnvPolicy(unittest.TestCase):
    def setUp(self):
        self._prev = os.environ.get("RPT_FREE_TIER")
        os.environ["RPT_FREE_TIER"] = "1"
        # Clear operator overrides that would confuse free-tier resolution
        for k in ("RPT_TRAFFIC_SHAPE", "RPT_OBFS", "RPT_MULTIHOP_ENABLED"):
            os.environ.pop(k, None)

    def tearDown(self):
        if self._prev is None:
            os.environ.pop("RPT_FREE_TIER", None)
        else:
            os.environ["RPT_FREE_TIER"] = self._prev

    def test_free_tier_enabled(self):
        from client.free_tier import free_tier_enabled, free_tier_product_version

        self.assertTrue(free_tier_enabled())
        self.assertEqual(free_tier_product_version(), "3.3.3")

    def test_product_policy_forces_lean(self):
        from client.product_policy import (
            product_multihop_enabled,
            product_outer_obfuscation_enabled,
            resolve_privacy_policy,
            traffic_shape_enabled,
        )

        self.assertFalse(traffic_shape_enabled())
        self.assertFalse(product_outer_obfuscation_enabled())
        self.assertFalse(product_multihop_enabled())
        r = resolve_privacy_policy()
        self.assertFalse(r.traffic_shape_enabled)
        self.assertFalse(r.outer_obfuscation_enabled)
        self.assertFalse(r.multihop_enabled)
        self.assertTrue(r.residual_vpn_core)

    def test_settings_locked_helpers(self):
        from client.free_tier import (
            free_tier_privacy_scale_locked_off,
            free_tier_settings_locked,
        )

        self.assertTrue(free_tier_settings_locked())
        self.assertEqual(free_tier_privacy_scale_locked_off(), (False, False, False))


class TestPaidTierUnaffected(unittest.TestCase):
    def setUp(self):
        self._prev = os.environ.get("RPT_FREE_TIER")
        os.environ.pop("RPT_FREE_TIER", None)
        for k in ("RPT_TRAFFIC_SHAPE", "RPT_OBFS", "RPT_MULTIHOP_ENABLED"):
            os.environ.pop(k, None)

    def tearDown(self):
        if self._prev is None:
            os.environ.pop("RPT_FREE_TIER", None)
        else:
            os.environ["RPT_FREE_TIER"] = self._prev

    def test_paid_defaults_privacy_max_shape_obfs(self):
        from client.free_tier import free_tier_enabled
        from client.product_policy import (
            product_outer_obfuscation_enabled,
            traffic_shape_enabled,
        )

        self.assertFalse(free_tier_enabled())
        self.assertTrue(traffic_shape_enabled())
        self.assertTrue(product_outer_obfuscation_enabled())


if __name__ == "__main__":
    unittest.main()
