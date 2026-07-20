"""Product session path requires PFS by default."""

from __future__ import annotations

import unittest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from client.connect import complete_server_hello
from node.elgamal import generate_keypair
from node.handshake import NodeHandshake, build_client_hello, node_complete_hello


class TestProductRequirePfs(unittest.TestCase):
    def test_product_hello_uses_pfs(self):
        node = generate_keypair()
        hs = NodeHandshake(node, admit_unknown_devices=True, require_pfs=True)
        client = Ed25519PrivateKey.generate()
        frame, cnonce, cpub, eph = build_client_hello(
            client, node.public, with_pfs=True
        )
        self.assertIsNotNone(eph)
        reply, result = node_complete_hello(hs, frame, "10.88.0.2")
        self.assertTrue(result.pfs)
        sess = complete_server_hello(reply, cnonce, cpub, eph)  # require_pfs default True
        self.assertTrue(sess.pfs)

    def test_product_rejects_legacy_without_eph(self):
        node = generate_keypair()
        hs = NodeHandshake(node, admit_unknown_devices=True, require_pfs=True)
        client = Ed25519PrivateKey.generate()
        frame, cnonce, cpub, eph = build_client_hello(
            client, node.public, with_pfs=False
        )
        self.assertIsNone(eph)
        from node.handshake import AdmissionError

        with self.assertRaises(AdmissionError):
            node_complete_hello(hs, frame, "10.88.0.3")

    def test_client_require_pfs_rejects_legacy_session(self):
        node = generate_keypair()
        hs = NodeHandshake(node, admit_unknown_devices=True, require_pfs=False)
        client = Ed25519PrivateKey.generate()
        frame, cnonce, cpub, eph = build_client_hello(
            client, node.public, with_pfs=False
        )
        reply, result = node_complete_hello(hs, frame, "10.88.0.5")
        self.assertFalse(result.pfs)
        with self.assertRaises(ValueError):
            complete_server_hello(reply, cnonce, cpub, None, require_pfs=True)


if __name__ == "__main__":
    unittest.main()
