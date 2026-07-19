"""Perfect forward secrecy: ephemeral X25519 in shipped handshake/session KDF."""

from __future__ import annotations

import unittest
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT = Path(__file__).resolve().parents[1]

from client.connect import complete_server_hello  # noqa: E402
from node.elgamal import generate_keypair  # noqa: E402
from node.handshake import NodeHandshake, build_client_hello, node_complete_hello  # noqa: E402
from node.pfs import (  # noqa: E402
    EphemeralX25519,
    derive_legacy_session_shared,
    derive_pfs_session_shared,
    long_term_only_cannot_recover_pfs_key,
    session_crypto_from_shared,
    x25519_shared_secret,
)


class TestEphemeralX25519(unittest.TestCase):
    def test_two_sessions_distinct_eph_and_keys(self):
        node = generate_keypair()
        hs = NodeHandshake(node, admit_unknown_devices=True)
        keys = []
        eph_pubs = []
        for _ in range(2):
            client = Ed25519PrivateKey.generate()
            frame, cnonce, cpub, eph = build_client_hello(
                client, node.public, with_pfs=True
            )
            self.assertIsNotNone(eph)
            assert eph is not None
            eph_pubs.append(eph.public_raw)
            reply, result = node_complete_hello(hs, frame, "10.88.0.5")
            self.assertTrue(result.pfs)
            sess = complete_server_hello(reply, cnonce, cpub, eph)
            self.assertTrue(sess.pfs)
            self.assertEqual(sess.crypto.key, result.crypto.key)
            keys.append(sess.crypto.key)
        self.assertNotEqual(eph_pubs[0], eph_pubs[1])
        self.assertNotEqual(keys[0], keys[1])

    def test_session_key_uses_ephemeral_material(self):
        a = EphemeralX25519.generate()
        b = EphemeralX25519.generate()
        shared = x25519_shared_secret(a.private, b.public_raw)
        shared2 = x25519_shared_secret(b.private, a.public_raw)
        self.assertEqual(shared, shared2)
        cn, sn, sid, cpub = b"c" * 32, b"s" * 32, b"i" * 8, b"p" * 32
        pfs_ikm = derive_pfs_session_shared(cn, sn, sid, cpub, shared)
        leg_ikm = derive_legacy_session_shared(cn, sn, sid, cpub)
        self.assertNotEqual(pfs_ikm, leg_ikm)
        pfs_key = session_crypto_from_shared(pfs_ikm, cn).key
        leg_key = session_crypto_from_shared(leg_ikm, cn).key
        self.assertNotEqual(pfs_key, leg_key)

    def test_long_term_only_reconstruction_fails(self):
        """Attacker with nonces/session_id/client_pub cannot recover PFS session key."""
        node = generate_keypair()
        hs = NodeHandshake(node, admit_unknown_devices=True)
        client = Ed25519PrivateKey.generate()
        frame, cnonce, cpub, eph = build_client_hello(client, node.public, with_pfs=True)
        reply, result = node_complete_hello(hs, frame, "10.88.0.9")
        sess = complete_server_hello(reply, cnonce, cpub, eph)
        self.assertTrue(sess.pfs)
        # Extract nonces from handshake path via re-derive check
        # Long-term-only guess uses legacy IKM (no eph_shared)
        ok = long_term_only_cannot_recover_pfs_key(
            client_nonce=cnonce,
            server_nonce=b"\x00" * 32,  # wrong without real server nonce…
            session_id=sess.session_id,
            client_pub=cpub,
            real_session_key=sess.crypto.key,
        )
        # Even with correct nonces from transcript:
        from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
        from node.protocol import parse_server_hello
        import hashlib
        from node.crypto_session import derive_session_key

        _sc, sid, nonce, sealed = parse_server_hello(reply)
        hello_shared = hashlib.sha256(cnonce + cpub + b"|hello").digest()
        hello_key = derive_session_key(
            hello_shared, salt=cnonce[:16], info=b"rpt-v2-hello"
        )
        aad = b"RPT2-SERVER-HELLO" + sid
        plain = ChaCha20Poly1305(hello_key).decrypt(nonce, sealed, aad)
        server_nonce = plain[:32]
        self.assertTrue(
            long_term_only_cannot_recover_pfs_key(
                client_nonce=cnonce,
                server_nonce=server_nonce,
                session_id=sid,
                client_pub=cpub,
                real_session_key=sess.crypto.key,
            )
        )

    def test_legacy_path_without_pfs_still_works(self):
        node = generate_keypair()
        hs = NodeHandshake(node, admit_unknown_devices=True)
        client = Ed25519PrivateKey.generate()
        frame, cnonce, cpub, eph = build_client_hello(
            client, node.public, with_pfs=False
        )
        self.assertIsNone(eph)
        reply, result = node_complete_hello(hs, frame, "10.88.0.3")
        self.assertFalse(result.pfs)
        sess = complete_server_hello(reply, cnonce, cpub, None)
        self.assertFalse(sess.pfs)
        self.assertEqual(sess.crypto.key, result.crypto.key)


if __name__ == "__main__":
    unittest.main()
