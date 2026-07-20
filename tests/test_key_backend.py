"""Key-protection backends: mock/sealed decrypt without free-disk .priv sole path."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from node.elgamal import encrypt  # noqa: E402
from node.handshake import NodeHandshake, build_client_hello, node_complete_hello  # noqa: E402
from node.key_backend import (  # noqa: E402
    PRIV_NAME,
    SEALED_NAME,
    SealedNodeKeyBackend,
    load_node_key_backend,
)


class TestMockBackend(unittest.TestCase):
    def test_mock_decrypt_and_handshake_without_plaintext_priv(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            with mock.patch.dict(os.environ, {"RPT_KEY_BACKEND": "mock"}):
                backend = load_node_key_backend(d, backend="mock")
            self.assertEqual(backend.backend_id(), "mock")
            self.assertFalse(
                backend.materializes_plaintext_priv_on_disk(),
                "mock must not require free-disk node_elgamal.priv",
            )
            self.assertFalse((d / PRIV_NAME).is_file())
            # Real decrypt op used by handshake
            pt = b"hello-backend"
            ct = encrypt(backend.public_key(), pt)
            self.assertEqual(backend.decrypt_ciphertext(ct), pt)
            # Real product HELLO path with backend as node key
            hs = NodeHandshake(backend, admit_unknown_devices=True, require_pfs=True)
            client = Ed25519PrivateKey.generate()
            frame, cnonce, cpub, eph = build_client_hello(
                client, backend.public_key(), with_pfs=True
            )
            reply, result = node_complete_hello(hs, frame, "10.88.0.4")
            self.assertTrue(result.pfs)
            self.assertEqual(len(result.session_id), 8)


class TestSealedBackend(unittest.TestCase):
    def test_sealed_no_plaintext_priv_after_create(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            backend = SealedNodeKeyBackend.load_or_create(d)
            self.assertEqual(backend.backend_id(), "sealed")
            self.assertTrue((d / SEALED_NAME).is_file())
            self.assertFalse(
                (d / PRIV_NAME).is_file(),
                "sealed create should not leave plaintext .priv as sole secret",
            )
            self.assertFalse(backend.materializes_plaintext_priv_on_disk())
            # Reload from sealed only
            backend2 = SealedNodeKeyBackend.load_or_create(d)
            pt = b"seal-ok"
            ct = encrypt(backend2.public_key(), pt)
            self.assertEqual(backend2.decrypt_ciphertext(ct), pt)
            # Handshake via sealed backend
            hs = NodeHandshake(backend2, admit_unknown_devices=True)
            client = Ed25519PrivateKey.generate()
            frame, _, _, eph = build_client_hello(client, backend2.public_key())
            self.assertIsNotNone(eph)
            reply, result = node_complete_hello(hs, frame, "10.88.0.7")
            self.assertTrue(result.pfs)


class TestFileBackendStillWorks(unittest.TestCase):
    def test_file_backend_default(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            backend = load_node_key_backend(d, backend="file")
            self.assertEqual(backend.backend_id(), "file")
            self.assertTrue((d / PRIV_NAME).is_file())
            self.assertTrue(backend.materializes_plaintext_priv_on_disk())


if __name__ == "__main__":
    unittest.main()

