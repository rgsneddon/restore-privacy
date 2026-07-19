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
        # product before secrets
        self.assertLess(gradle.index("product/"), gradle.index("secrets/"))

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
            frame, nonce, cpub = build_authorized_client_hello(priv, node_pub)
            self.assertEqual(frame[:5], b"RPT2\x01")
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(12.0)
            try:
                sock.sendto(frame, (PRODUCT_NODE_HOST, DEFAULT_ENDPOINT.port))
                reply, _addr = sock.recvfrom(65535)
            except (TimeoutError, socket.timeout) as exc:
                self.fail(
                    f"No SERVER_HELLO from {PRODUCT_NODE_HOST}:{DEFAULT_ENDPOINT.port} "
                    f"with product node pub — {exc}. "
                    "If network is fine, node key still mismatches or UDP blocked."
                )
            finally:
                sock.close()

            self.assertEqual(peek_type(reply), MsgType.SERVER_HELLO)
            sess = complete_server_hello(reply, nonce, cpub)
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


if __name__ == "__main__":
    unittest.main()
