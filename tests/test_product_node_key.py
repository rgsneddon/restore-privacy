"""Production node ElGamal public key must match packages and live node.

Root cause of Android (and any client) handshake timeout when the APK/installer
ships a node_elgamal.pub that does not match the node's private key: hybrid
decrypt fails server-side and HELLO is silently dropped.
"""

from __future__ import annotations

import hashlib
import socket
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

from client.endpoint import (  # noqa: E402
    DEFAULT_ENDPOINT,
    PRODUCT_NODE_ELGAMAL_PUB_SHA256,
    PRODUCT_NODE_HOST,
    product_node_elgamal_pub_path,
)
from client.connect import (  # noqa: E402
    build_authorized_client_hello,
    complete_server_hello,
)
from client.secrets_loader import (  # noqa: E402
    ensure_device_admission_key,
    load_client_private_key,
    load_node_elgamal_public,
)
from node.obfuscation import maybe_unwrap, maybe_wrap  # noqa: E402
from node.protocol import MsgType, peek_type  # noqa: E402


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().lower()


class TestProductNodeElgamalPubPinned(unittest.TestCase):
    def test_tracked_product_pub_matches_pin(self):
        path = product_node_elgamal_pub_path()
        self.assertTrue(path.is_file(), f"missing tracked {path}")
        raw = path.read_bytes()
        self.assertEqual(len(raw), 256)
        self.assertEqual(_sha256_file(path), PRODUCT_NODE_ELGAMAL_PUB_SHA256)

        pin_file = ROOT / "product" / "NODE_ELGAMAL_PUB.sha256"
        self.assertTrue(pin_file.is_file())
        pin_text = pin_file.read_text(encoding="utf-8")
        self.assertIn(PRODUCT_NODE_ELGAMAL_PUB_SHA256, pin_text)

    def test_android_assets_or_product_source_aligned(self):
        """Assets may be gitignored; product/ is the build source of truth."""
        product = product_node_elgamal_pub_path()
        self.assertEqual(_sha256_file(product), PRODUCT_NODE_ELGAMAL_PUB_SHA256)
        assets = (
            ROOT
            / "client_app"
            / "android"
            / "app"
            / "src"
            / "main"
            / "assets"
            / "secrets"
            / "node_elgamal.pub"
        )
        if assets.is_file():
            self.assertEqual(
                _sha256_file(assets),
                PRODUCT_NODE_ELGAMAL_PUB_SHA256,
                "Android assets node_elgamal.pub does not match production pin — "
                "rebuild APK after syncing product/node_elgamal.pub",
            )

    def test_gradle_prefers_product_pub(self):
        gradle = (
            ROOT / "client_app" / "android" / "app" / "build.gradle.kts"
        ).read_text(encoding="utf-8")
        self.assertIn("product/$name", gradle)
        self.assertIn("copyRptSecretsToAssets", gradle)
        # Candidates list: product monopin before secrets/ fallback
        prod = gradle.index('rootProject.file("../../product/$name")')
        sec = gradle.index('rootProject.file("../../secrets/$name")')
        self.assertLess(prod, sec)

    def test_secrets_loader_finds_product_pub_bytes(self):
        """_find_node_pub prefers tracked product/node_elgamal.pub."""
        from client.secrets_loader import _find_node_pub

        raw = _find_node_pub([])
        self.assertIsNotNone(raw)
        assert raw is not None
        self.assertEqual(len(raw), 256)
        self.assertEqual(
            hashlib.sha256(raw).hexdigest().lower(),
            PRODUCT_NODE_ELGAMAL_PUB_SHA256,
        )


class TestLiveHelloWithProductKey(unittest.TestCase):
    """Drive real CLIENT_HELLO with product pub against production host."""

    def test_live_handshake_with_product_node_pub(self):
        product = product_node_elgamal_pub_path()
        if not product.is_file():
            self.skipTest("product/node_elgamal.pub missing")
        if _sha256_file(product) != PRODUCT_NODE_ELGAMAL_PUB_SHA256:
            self.fail("product pub hash drift vs PRODUCT_NODE_ELGAMAL_PUB_SHA256")

        with tempfile.TemporaryDirectory() as td:
            sdir = Path(td)
            (sdir / "node_elgamal.pub").write_bytes(product.read_bytes())
            sdir = ensure_device_admission_key(sdir)
            priv = load_client_private_key(sdir)
            # Force pub bytes from product file (not ambient secrets)
            from node.elgamal import ElGamalPublicKey

            node_pub = ElGamalPublicKey.import_bytes(product.read_bytes())
            frame, nonce, cpub, _eph = build_authorized_client_hello(priv, node_pub)
            self.assertEqual(frame[:5], b"RPT2\x01")
            # Product wire (Rust node + device releases) uses outer QUIC-mimic obfs.
            wire = maybe_wrap(frame)
            self.assertNotEqual(wire[:4], b"RPT2", "product HELLO must be obfuscated")
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(12.0)
            try:
                sock.sendto(wire, (PRODUCT_NODE_HOST, DEFAULT_ENDPOINT.port))
                raw_reply, _addr = sock.recvfrom(65535)
            except (TimeoutError, socket.timeout) as exc:
                self.fail(
                    f"No SERVER_HELLO from {PRODUCT_NODE_HOST}:{DEFAULT_ENDPOINT.port} "
                    f"with product node pub — {exc}. "
                    "If network is fine, node key still mismatches or UDP blocked."
                )
            finally:
                sock.close()

            reply = maybe_unwrap(raw_reply)
            self.assertEqual(peek_type(reply), MsgType.SERVER_HELLO)
            sess = complete_server_hello(reply, nonce, cpub, _eph)
            self.assertTrue(sess.vpn_ip.startswith("10.88.0."))
            self.assertEqual(len(sess.session_id), 8)


class TestAndroidHandshakeSurfacesTimeoutHint(unittest.TestCase):
    def test_vpn_service_mentions_node_pub_on_timeout(self):
        svc = (
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
        self.assertIn("engine.handshake", svc)
        self.assertIn("node_elgamal.pub", svc)
        self.assertIn("SocketTimeoutException", svc)
        self.assertIn("matches the production node", svc)


class TestAndroidNodePubRefreshOnUpgrade(unittest.TestCase):
    """APK upgrade must overwrite filesDir node_elgamal.pub (not only if missing)."""

    def _vpn_service_src(self) -> str:
        return (
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

    def test_shipped_refresh_helper_always_writebytes(self):
        """refreshNodeElgamalPub must overwrite; no skip-if-exists for node pub."""
        svc = self._vpn_service_src()
        self.assertIn("fun refreshNodeElgamalPub", svc)
        # Extract helper body between fun and next fun/const
        start = svc.index("fun refreshNodeElgamalPub")
        body = svc[start : start + 500]
        self.assertIn("writeBytes", body)
        self.assertIn("assetBytes", body)
        # Must not early-return solely because dest already exists
        self.assertNotIn("if (!pubFile.isFile())", body)
        self.assertNotIn("if (!pubFile.exists())", body)

    def test_load_secrets_always_refreshes_from_assets(self):
        """loadSecrets must call refresh from assets every Connect (upgrade heal)."""
        svc = self._vpn_service_src()
        load = svc[svc.index("private fun loadSecrets") : svc.index("private fun loadSecrets") + 1600]
        # Multi-country residual: host → pubName (IS/RO/US), always refresh from assets
        self.assertTrue(
            'assets.open("secrets/node_elgamal.pub")' in load
            or 'assets.open("secrets/$pubName")' in load,
            "loadSecrets must open package secrets pub assets",
        )
        self.assertIn("refreshNodeElgamalPub", load)
        # Old bug: only copy when !pubF.isFile — must be gone for node pub path
        self.assertNotIn("if (!pubF.isFile())", load)
        self.assertIn("Always copy package pub", load)
        self.assertIn("residualNodePubNameForHost", load)
        # Catalog residual pubs must still exist on the service (name map + assets)
        self.assertIn("exit_node_elgamal.pub", svc)
        # US residual pub name is us_node_elgamal.pub (not usa_*)
        self.assertIn("us_node_elgamal.pub", svc)

    def test_refresh_node_elgamal_pub_file_overwrites_stale(self):
        """Shipped Python mirror of Android helper: stale filesDir bytes replaced."""
        from client.secrets_loader import refresh_node_elgamal_pub_file

        stale = b"\x11" * 256  # wrong key material
        good = product_node_elgamal_pub_path().read_bytes()
        self.assertEqual(hashlib.sha256(good).hexdigest().lower(), PRODUCT_NODE_ELGAMAL_PUB_SHA256)
        with tempfile.TemporaryDirectory() as td:
            pub_path = Path(td) / "secrets" / "node_elgamal.pub"
            pub_path.parent.mkdir(parents=True)
            pub_path.write_bytes(stale)
            self.assertEqual(pub_path.read_bytes(), stale)
            ok = refresh_node_elgamal_pub_file(pub_path, good)
            self.assertTrue(ok)
            self.assertEqual(pub_path.read_bytes(), good)
            self.assertEqual(
                hashlib.sha256(pub_path.read_bytes()).hexdigest().lower(),
                PRODUCT_NODE_ELGAMAL_PUB_SHA256,
            )

    def test_ensure_device_admission_overwrites_stale_node_pub(self):
        """Connect bootstrap heals secrets_dir with product pin (Windows same policy)."""
        good = product_node_elgamal_pub_path().read_bytes()
        stale = b"\x22" * 256
        with tempfile.TemporaryDirectory() as td:
            sdir = Path(td)
            (sdir / "node_elgamal.pub").write_bytes(stale)
            # device key present so bootstrap keeps identity
            from client.secrets_loader import generate_and_persist_device_key

            generate_and_persist_device_key(sdir)
            out = ensure_device_admission_key(sdir)
            self.assertEqual(out, sdir)
            self.assertEqual((sdir / "node_elgamal.pub").read_bytes(), good)


if __name__ == "__main__":
    unittest.main()
