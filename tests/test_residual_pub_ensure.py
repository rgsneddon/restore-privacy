"""Filesystem fixture: App Support IS-only + package RO → load RO pin (shipped algorithm).

Mirrors Android always-open-chosen-pubName and Apple ensureResidualPubInWritableDir.
Drives client.residual_pub_ensure on real temp dirs — not string inventory theater.
Germany residual peer is retired (no de_node dial path).
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from client.residual_pub_ensure import (  # noqa: E402
    ResidualPubError,
    ensure_residual_pub_in_writable_dir,
    load_residual_node_pub,
    residual_node_pub_name_for_host,
)
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
)


class TestResidualPubEnsureFixture(unittest.TestCase):
    """Writable dir has only IS pin; package has RO → ensure loads RO bytes."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.writable = self.root / "AppSupport" / "secrets"
        self.package = self.root / "Bundle" / "Resources" / "secrets"
        self.writable.mkdir(parents=True)
        self.package.mkdir(parents=True)
        product = ROOT / "product"
        self.is_pub = (product / "node_elgamal.pub").read_bytes()
        self.ro_pub = (product / "exit_node_elgamal.pub").read_bytes()
        self.us_pub = (product / "us_node_elgamal.pub").read_bytes()
        # Writable = IS only (legacy App Support seed)
        (self.writable / "node_elgamal.pub").write_bytes(self.is_pub)
        (self.writable / "client_ed25519.priv").write_bytes(b"\x01" * 32)
        # Package inject has IS + RO + US (catalog)
        (self.package / "node_elgamal.pub").write_bytes(self.is_pub)
        (self.package / "exit_node_elgamal.pub").write_bytes(self.ro_pub)
        (self.package / "us_node_elgamal.pub").write_bytes(self.us_pub)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_ro_host_refreshes_from_package_into_writable(self):
        self.assertFalse((self.writable / "exit_node_elgamal.pub").is_file())
        dest = ensure_residual_pub_in_writable_dir(
            self.writable,
            PRODUCT_EXIT_HOST,
            [self.package],
        )
        self.assertEqual(dest.name, "exit_node_elgamal.pub")
        self.assertTrue(dest.is_file())
        data = load_residual_node_pub(
            self.writable, PRODUCT_EXIT_HOST, [self.package]
        )
        self.assertEqual(data, self.ro_pub)
        self.assertNotEqual(data, self.is_pub)

    def test_ro_missing_package_fail_closed_no_is_fallback(self):
        (self.package / "exit_node_elgamal.pub").unlink()
        with self.assertRaises(ResidualPubError) as cm:
            load_residual_node_pub(
                self.writable, PRODUCT_EXIT_HOST, [self.package]
            )
        msg = str(cm.exception).lower()
        self.assertIn("exit_node", msg)
        self.assertIn("refuse", msg)
        self.assertFalse((self.writable / "exit_node_elgamal.pub").is_file())
        with self.assertRaises(ResidualPubError):
            load_residual_node_pub(self.writable, PRODUCT_EXIT_HOST, [])

    def test_ro_host_from_package(self):
        data = load_residual_node_pub(
            self.writable, PRODUCT_EXIT_HOST, [self.package]
        )
        self.assertEqual(data, self.ro_pub)

    def test_is_host_uses_writable_or_package(self):
        data = load_residual_node_pub(
            self.writable, PRODUCT_NODE_HOST, [self.package]
        )
        self.assertEqual(data, self.is_pub)

    def test_us_host_refreshes_from_package(self):
        data = load_residual_node_pub(
            self.writable, PRODUCT_US_HOST, [self.package]
        )
        self.assertEqual(data, self.us_pub)
        self.assertNotEqual(data, self.is_pub)

    def test_us_missing_package_fail_closed_no_is_fallback(self):
        (self.package / "us_node_elgamal.pub").unlink()
        with self.assertRaises(ResidualPubError) as cm:
            load_residual_node_pub(
                self.writable, PRODUCT_US_HOST, [self.package]
            )
        msg = str(cm.exception).lower()
        self.assertIn("us_node", msg)
        self.assertIn("refuse", msg)

    def test_pub_name_for_host_table(self):
        self.assertEqual(
            residual_node_pub_name_for_host(PRODUCT_NODE_HOST),
            "node_elgamal.pub",
        )
        self.assertEqual(
            residual_node_pub_name_for_host(PRODUCT_EXIT_HOST),
            "exit_node_elgamal.pub",
        )
        self.assertEqual(
            residual_node_pub_name_for_host(PRODUCT_US_HOST),
            "us_node_elgamal.pub",
        )
        # Retired DE monopin must not map to de_node pin
        self.assertEqual(
            residual_node_pub_name_for_host("167.233.224.5"),
            "node_elgamal.pub",
        )
        self.assertNotEqual(
            residual_node_pub_name_for_host("167.233.224.5"),
            "de_node_elgamal.pub",
        )


class TestPacketTunnelLayoutFixture(unittest.TestCase):
    """Host inject + IS-only App Group + empty tunnel bundle → RO HELLO after preseed."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.host_pkg = self.root / "Runner.app" / "Contents" / "Resources" / "secrets"
        self.tunnel_pkg = (
            self.root
            / "Runner.app"
            / "Contents"
            / "PlugIns"
            / "PacketTunnel.appex"
            / "Contents"
            / "Resources"
            / "secrets"
        )
        self.app_group = self.root / "AppGroup" / "group.com.restoreprivacy.shared" / "secrets"
        self.host_pkg.mkdir(parents=True)
        self.tunnel_pkg.mkdir(parents=True)
        self.app_group.mkdir(parents=True)
        product = ROOT / "product"
        self.is_pub = (product / "node_elgamal.pub").read_bytes()
        self.ro_pub = (product / "exit_node_elgamal.pub").read_bytes()
        for name, data in (
            ("node_elgamal.pub", self.is_pub),
            ("exit_node_elgamal.pub", self.ro_pub),
        ):
            (self.host_pkg / name).write_bytes(data)
        (self.tunnel_pkg / "node_elgamal.pub").write_bytes(self.is_pub)
        (self.app_group / "node_elgamal.pub").write_bytes(self.is_pub)
        (self.app_group / "client_ed25519.priv").write_bytes(b"\x02" * 32)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_tunnel_cannot_load_ro_without_host_preseed(self):
        with self.assertRaises(ResidualPubError):
            load_residual_node_pub(
                self.app_group,
                PRODUCT_EXIT_HOST,
                [self.tunnel_pkg, self.app_group],
            )

    def test_host_preseed_then_tunnel_loads_ro_from_app_group(self):
        from client.residual_pub_ensure import preseed_shared_writable_for_residual_host

        data = preseed_shared_writable_for_residual_host(
            PRODUCT_EXIT_HOST,
            host_package_secrets=self.host_pkg,
            shared_writable_dirs=[self.app_group],
            tunnel_bundle_secrets=self.tunnel_pkg,
        )
        self.assertEqual(data, self.ro_pub)
        self.assertTrue((self.app_group / "exit_node_elgamal.pub").is_file())
        again = load_residual_node_pub(
            self.app_group,
            PRODUCT_EXIT_HOST,
            [self.tunnel_pkg, self.app_group],
        )
        self.assertEqual(again, self.ro_pub)

    def test_inject_script_targets_appex(self):
        inject = (ROOT / "scripts" / "inject_apple_secrets.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("*.appex", inject)
        self.assertIn("PlugIns", inject)
        self.assertIn("_inject_into_secrets_dir", inject)

    def test_swift_host_preseed_and_seed_catalog(self):
        for rel in (
            "client_app/macos/NativePrep/RptSecrets.swift",
            "client_app/ios/NativePrep/RptSecrets.swift",
        ):
            sw = (ROOT / rel).read_text(encoding="utf-8")
            self.assertIn("preseedSharedWritableSecretsForResidualHost", sw, rel)
            self.assertIn("seedCatalogPublicKeys", sw, rel)
            self.assertIn("usNodePubName", sw, rel)
            self.assertIn("productUsHost", sw, rel)
            self.assertNotIn("deNodePubName", sw, rel)
            self.assertNotIn("productDeHost", sw, rel)
            self.assertNotIn("167.233.224.5", sw, rel)
        for rel in (
            "client_app/macos/NativePrep/RptVpnChannel.swift",
            "client_app/ios/NativePrep/RptVpnChannel.swift",
        ):
            ch = (ROOT / rel).read_text(encoding="utf-8")
            self.assertIn(
                "preseedSharedWritableSecretsForResidualHost", ch, rel
            )


class TestCatalogPubInventory(unittest.TestCase):
    """Every live catalog code → host → required pub covered by inject/gradle/product."""

    def test_catalog_to_pub_inventory(self):
        # Live residual catalog is IS + DE only (US/RO retired).
        expected = {
            COUNTRY_DE: (PRODUCT_DE_HOST, "de_node_elgamal.pub"),
            "SG": ("5.223.48.8", "sg_node_elgamal.pub"),
        }
        codes = {n.code for n in PRODUCT_COUNTRY_CATALOG}
        self.assertEqual(codes, {"DE", "SG"})
        self.assertNotIn("IS", codes)
        self.assertNotIn("US", codes)
        self.assertNotIn("RO", codes)
        for n in PRODUCT_COUNTRY_CATALOG:
            host, pub = expected[n.code]
            self.assertEqual(n.host, host, n.code)
            self.assertEqual(
                residual_node_pub_name_for_host(n.host), pub, n.code
            )
            product_pin = ROOT / "product" / pub
            self.assertTrue(product_pin.is_file(), pub)
            self.assertGreaterEqual(product_pin.stat().st_size, 32, pub)

        inject = (ROOT / "scripts" / "inject_apple_secrets.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("SG_PUB", inject)
        self.assertIn("sg_node_elgamal.pub", inject)
        self.assertIn("de_node_elgamal.pub", inject)
        self.assertIn("exit_node_elgamal.pub", inject)
        # Retired US must not be in the default inject tuple
        self.assertNotIn("US_PUB)", inject)
        self.assertNotIn(", US_PUB)", inject)
        self.assertNotIn("US_PUB,", inject)
        gradle = (
            ROOT / "client_app" / "android" / "app" / "build.gradle.kts"
        ).read_text(encoding="utf-8")
        self.assertIn("node_elgamal.pub", gradle)
        self.assertIn("exit_node_elgamal.pub", gradle)
        self.assertIn('"de_node_elgamal.pub"', gradle)
        # Retired US must not be in APK assets inject list
        self.assertNotIn('"us_node_elgamal.pub"', gradle)

        for rel in (
            "client_app/ios/NativePrep/RptSecrets.swift",
            "client_app/macos/NativePrep/RptSecrets.swift",
        ):
            sw = (ROOT / rel).read_text(encoding="utf-8")
            self.assertIn("ensureResidualPubInWritableDir", sw, rel)
            # Stale US host may still map → DE pin for heal; catalog list is live-only
            self.assertIn("catalogPublicPubNames", sw, rel)
            self.assertIn("deNodePubName", sw, rel)
            e_i = sw.find("ensureResidualPubInWritableDir")
            self.assertIn(
                "try ensureResidualPubInWritableDir",
                sw,
                rel,
            )
            self.assertGreater(e_i, 0, rel)


if __name__ == "__main__":
    unittest.main()
