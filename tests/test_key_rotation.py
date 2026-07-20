"""Long-term key rotation + client public re-provision (no shared client priv)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from node.elgamal import encrypt
from node.handshake import NodeHandshake, build_client_hello, node_complete_hello
from node.key_backend import PRIV_NAME, load_node_key_backend
from node.key_rotation import (
    reprovision_node_public,
    rotate_node_long_term_keys,
    sha256_hex,
)


class TestKeyRotation(unittest.TestCase):
    def test_rotate_mock_updates_pub_and_handshake(self):
        with tempfile.TemporaryDirectory() as td:
            secrets = Path(td) / "secrets"
            product = Path(td) / "product"
            secrets.mkdir()
            # Initial key
            load_node_key_backend(secrets, backend="mock")
            old_pub = (secrets / "node_elgamal.pub").read_bytes()
            old_sha = sha256_hex(old_pub)

            result = rotate_node_long_term_keys(
                secrets, product_dir=product, backend="mock"
            )
            self.assertTrue(result.ok, result.message)
            self.assertEqual(result.old_pub_sha256, old_sha)
            self.assertNotEqual(result.new_pub_sha256, old_sha)
            self.assertFalse(result.introduced_shared_client_priv)
            # Product pin updated
            prod_pub = (product / "node_elgamal.pub").read_bytes()
            self.assertEqual(sha256_hex(prod_pub), result.new_pub_sha256)
            pin = (product / "NODE_ELGAMAL_PUB.sha256").read_text(encoding="utf-8")
            self.assertIn(result.new_pub_sha256, pin)
            # New backend decrypt + handshake
            backend = load_node_key_backend(secrets, backend="mock")
            self.assertEqual(backend.public_export(), prod_pub)
            hs = NodeHandshake(backend, admit_unknown_devices=True, require_pfs=True)
            client = Ed25519PrivateKey.generate()
            frame, _, _, eph = build_client_hello(client, backend.public_key())
            reply, res = node_complete_hello(hs, frame, "10.88.0.11")
            self.assertTrue(res.pfs)
            # No shared client priv created by rotation
            self.assertFalse((secrets / "client_ed25519.priv").is_file())

    def test_reprovision_node_public_only(self):
        with tempfile.TemporaryDirectory() as td:
            client_sec = Path(td) / "client_secrets"
            client_sec.mkdir()
            # Pretend device key already exists
            (client_sec / "client_ed25519.priv").write_bytes(b"\x01" * 32)
            before = (client_sec / "client_ed25519.priv").read_bytes()
            # New node pub from rotation
            node_secrets = Path(td) / "node"
            product = Path(td) / "product"
            load_node_key_backend(node_secrets, backend="mock")
            rotate_node_long_term_keys(
                node_secrets, product_dir=product, backend="mock"
            )
            src = product / "node_elgamal.pub"
            out = reprovision_node_public(client_sec, src)
            self.assertTrue(out.is_file())
            self.assertEqual(out.read_bytes(), src.read_bytes())
            # Device priv untouched
            self.assertEqual((client_sec / "client_ed25519.priv").read_bytes(), before)

    def test_rotate_sealed_removes_need_for_plaintext_priv(self):
        with tempfile.TemporaryDirectory() as td:
            secrets = Path(td) / "sec"
            product = Path(td) / "prod"
            result = rotate_node_long_term_keys(
                secrets, product_dir=product, backend="sealed"
            )
            self.assertTrue(result.ok, result.message)
            self.assertEqual(result.backend, "sealed")
            # Sealed path: no requirement on plaintext .priv for operation
            backend = load_node_key_backend(secrets, backend="sealed")
            pt = b"post-rot"
            self.assertEqual(
                backend.decrypt_ciphertext(encrypt(backend.public_key(), pt)), pt
            )


if __name__ == "__main__":
    unittest.main()
