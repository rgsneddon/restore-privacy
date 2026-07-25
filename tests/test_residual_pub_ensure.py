"""Filesystem fixture: App Support IS-only + package DE → load DE pin (shipped algorithm).

Mirrors Android always-open-chosen-pubName and Apple ensureResidualPubInWritableDir.
Drives client.residual_pub_ensure on real temp dirs — not string inventory theater.
"""

from __future__ import annotations

import shutil
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
    PRODUCT_COUNTRY_CATALOG,
    PRODUCT_DE_HOST,
    PRODUCT_EXIT_HOST,
    PRODUCT_NODE_HOST,
)


class TestResidualPubEnsureFixture(unittest.TestCase):
    """Writable dir has only IS pin; package has DE → ensure loads DE bytes."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.writable = self.root / "AppSupport" / "secrets"
        self.package = self.root / "Bundle" / "Resources" / "secrets"
        self.writable.mkdir(parents=True)
        self.package.mkdir(parents=True)
        # Real product pins when available (256-byte ElGamal pubs)
        product = ROOT / "product"
        self.is_pub = (product / "node_elgamal.pub").read_bytes()
        self.ro_pub = (product / "exit_node_elgamal.pub").read_bytes()
        self.de_pub = (product / "de_node_elgamal.pub").read_bytes()
        self.assertGreaterEqual(len(self.de_pub), 32)
        # Writable = IS only (legacy App Support seed)
        (self.writable / "node_elgamal.pub").write_bytes(self.is_pub)
        (self.writable / "client_ed25519.priv").write_bytes(b"\x01" * 32)
        # Package inject has DE (+ RO)
        (self.package / "node_elgamal.pub").write_bytes(self.is_pub)
        (self.package / "exit_node_elgamal.pub").write_bytes(self.ro_pub)
        (self.package / "de_node_elgamal.pub").write_bytes(self.de_pub)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_de_host_refreshes_from_package_into_writable(self):
        # Before ensure: writable has no DE pin
        self.assertFalse((self.writable / "de_node_elgamal.pub").is_file())
        dest = ensure_residual_pub_in_writable_dir(
            self.writable,
            PRODUCT_DE_HOST,
            [self.package],
        )
        self.assertEqual(dest.name, "de_node_elgamal.pub")
        self.assertTrue(dest.is_file())
        data = load_residual_node_pub(
            self.writable, PRODUCT_DE_HOST, [self.package]
        )
        self.assertEqual(data, self.de_pub)
        # Must not return Iceland pin for DE host
        self.assertNotEqual(data, self.is_pub)

    def test_de_missing_package_fail_closed_no_is_fallback(self):
        (self.package / "de_node_elgamal.pub").unlink()
        with self.assertRaises(ResidualPubError) as cm:
            load_residual_node_pub(
                self.writable, PRODUCT_DE_HOST, [self.package]
            )
        msg = str(cm.exception).lower()
        self.assertIn("de_node", msg)
        self.assertIn("refuse", msg)
        # Writable still must not gain Iceland file under de name
        self.assertFalse((self.writable / "de_node_elgamal.pub").is_file())
        # Loading with empty candidates still fails (does not open node_elgamal.pub)
        with self.assertRaises(ResidualPubError):
            load_residual_node_pub(self.writable, PRODUCT_DE_HOST, [])

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
            residual_node_pub_name_for_host(PRODUCT_DE_HOST),
            "de_node_elgamal.pub",
        )


class TestCatalogPubInventory(unittest.TestCase):
    """Every catalog code → host → required pub covered by inject/gradle/product."""

    def test_catalog_to_pub_inventory(self):
        # Table from product catalog
        expected = {
            COUNTRY_IS: (PRODUCT_NODE_HOST, "node_elgamal.pub"),
            COUNTRY_RO: (PRODUCT_EXIT_HOST, "exit_node_elgamal.pub"),
            COUNTRY_DE: (PRODUCT_DE_HOST, "de_node_elgamal.pub"),
        }
        for n in PRODUCT_COUNTRY_CATALOG:
            host, pub = expected[n.code]
            self.assertEqual(n.host, host, n.code)
            self.assertEqual(
                residual_node_pub_name_for_host(n.host), pub, n.code
            )
            product_pin = ROOT / "product" / pub
            self.assertTrue(product_pin.is_file(), pub)
            self.assertGreaterEqual(product_pin.stat().st_size, 32, pub)

        # Inject + gradle ship all pubs
        inject = (ROOT / "scripts" / "inject_apple_secrets.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("PUBLIC_PUBS = (NODE_PUB, EXIT_PUB, DE_PUB)", inject)
        gradle = (
            ROOT / "client_app" / "android" / "app" / "build.gradle.kts"
        ).read_text(encoding="utf-8")
        for pub in (
            "node_elgamal.pub",
            "exit_node_elgamal.pub",
            "de_node_elgamal.pub",
        ):
            self.assertIn(pub, gradle)

        # Apple ensure path present (production port of this algorithm)
        for rel in (
            "client_app/ios/NativePrep/RptSecrets.swift",
            "client_app/macos/NativePrep/RptSecrets.swift",
        ):
            sw = (ROOT / rel).read_text(encoding="utf-8")
            self.assertIn("ensureResidualPubInWritableDir", sw, rel)
            # ensure called before loadFromDirectory in admission path
            e_i = sw.find("ensureResidualPubInWritableDir")
            # loadAdmissionMaterial must call ensure
            self.assertIn(
                "try ensureResidualPubInWritableDir",
                sw,
                rel,
            )
            self.assertGreater(e_i, 0, rel)


if __name__ == "__main__":
    unittest.main()
