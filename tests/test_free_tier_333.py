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


class TestPackageLinuxFreeResolve(unittest.TestCase):
    def test_resolve_free_pins_3_3_3_and_out_dir(self):
        import scripts.package_linux as pl

        prev = os.environ.get("RPT_FREE_TIER")
        try:
            os.environ["RPT_FREE_TIER"] = "1"
            ver, free, out, name = pl._resolve_package_version()
            self.assertEqual(ver, "3.3.3")
            self.assertTrue(free)
            self.assertEqual(out.name, "3.3.3")
            self.assertIn("free", out.parts)
            self.assertEqual(name, "restore-privacy-client-free-3.3.3-linux-x64.tar.gz")
        finally:
            if prev is None:
                os.environ.pop("RPT_FREE_TIER", None)
            else:
                os.environ["RPT_FREE_TIER"] = prev

    def test_resolve_paid_uses_client_version(self):
        import scripts.package_linux as pl
        from pathlib import Path

        prev = os.environ.pop("RPT_FREE_TIER", None)
        prev_pv = os.environ.pop("RPT_PRODUCT_VERSION", None)
        try:
            pin = (Path(__file__).resolve().parents[1] / "client" / "VERSION").read_text(
                encoding="utf-8"
            ).strip()
            ver, free, out, name = pl._resolve_package_version()
            self.assertFalse(free)
            self.assertEqual(ver, pin)
            self.assertEqual(name, f"restore-privacy-client-{pin}-linux-x64.tar.gz")
            self.assertEqual(out.name, pin)
        finally:
            if prev is not None:
                os.environ["RPT_FREE_TIER"] = prev
            if prev_pv is not None:
                os.environ["RPT_PRODUCT_VERSION"] = prev_pv


class TestFreeLinuxPackageArtifact(unittest.TestCase):
    """Drive the *shipped* free linux tarball path when present (real package)."""

    def test_free_linux_tarball_pins_3_3_3_and_enables_free_tier(self):
        import tarfile
        from pathlib import Path

        root = Path(__file__).resolve().parents[1]
        dest = (
            root
            / "releases"
            / "free"
            / "3.3.3"
            / "restore-privacy-client-free-3.3.3-linux-x64.tar.gz"
        )
        if not dest.is_file():
            self.skipTest("free linux package not built yet")
        with tarfile.open(dest, "r:gz") as tf:
            names = tf.getnames()
            # Must not look like paid 0.x catalog root
            self.assertTrue(
                any("restore-privacy-3.3.3-linux" in n for n in names),
                msg=f"unexpected archive roots: {names[:5]}",
            )
            ver_members = [n for n in names if n.endswith("client/VERSION")]
            self.assertTrue(ver_members, msg="client/VERSION missing from free package")
            ver = tf.extractfile(ver_members[0]).read().decode("utf-8").strip()
            self.assertEqual(ver, "3.3.3")
            launch_m = [n for n in names if n.endswith("bin/privacy-restored")]
            self.assertTrue(launch_m)
            launch = tf.extractfile(launch_m[0]).read().decode("utf-8")
            self.assertIn("RPT_FREE_TIER=1", launch)
            self.assertIn("RPT_TRAFFIC_SHAPE=0", launch)
            self.assertIn("RPT_OBFS=0", launch)
            self.assertIn("RPT_MULTIHOP_ENABLED=0", launch)
            # free_tier module must be present so runtime helpers work
            self.assertTrue(
                any(n.endswith("client/free_tier.py") for n in names),
                msg="client/free_tier.py missing from free package",
            )


class TestWindowsSettingsFreeLockSource(unittest.TestCase):
    def test_windows_settings_gates_privacy_scale_on_free_tier(self):
        from pathlib import Path

        src = (
            Path(__file__).resolve().parents[1]
            / "client"
            / "windows"
            / "app.py"
        ).read_text(encoding="utf-8")
        self.assertIn("free_tier_settings_locked", src)
        self.assertIn("Free edition (3.3.3)", src)
        # Privacy-scale toggles only when not free-locked
        self.assertIn("if _free_locked:", src)
        self.assertIn("Traffic shaping (pad / jitter / cover)", src)


if __name__ == "__main__":
    unittest.main()
