"""Post-quantum hybrid IKM hook + plan artifact."""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

from node.pq_hybrid import (  # noqa: E402
    ToyKyberClassKem,
    default_kem,
    hybrid_ikm_from_kem,
    hybrid_session_ikm,
    pq_hybrid_enabled,
)
from node.pfs import derive_pfs_session_shared  # noqa: E402


class TestPqHybridHook(unittest.TestCase):
    def test_toy_kem_roundtrip_and_hybrid_ikm(self):
        kem = default_kem()
        self.assertIsInstance(kem, ToyKyberClassKem)
        pk, sk = kem.generate_keypair()
        ct, ss = kem.encaps_recoverable(pk)
        ss2 = kem.decaps(sk, ct)
        self.assertEqual(ss, ss2)
        classical = derive_pfs_session_shared(
            b"c" * 32, b"s" * 32, b"i" * 8, b"p" * 32, b"e" * 32
        )
        hybrid = hybrid_session_ikm(classical, ss)
        self.assertEqual(len(hybrid), 32)
        self.assertNotEqual(hybrid, classical)
        # Deterministic mix
        self.assertEqual(hybrid, hybrid_session_ikm(classical, ss))

    def test_hybrid_ikm_from_kem_helper(self):
        kem = ToyKyberClassKem()
        pk, sk = kem.generate_keypair()
        classical = b"C" * 32
        hikm, ct, ss = hybrid_ikm_from_kem(
            classical, kem, pk, recoverable_toy=True
        )
        self.assertEqual(hikm, hybrid_session_ikm(classical, ss))
        self.assertEqual(kem.decaps(sk, ct), ss)

    def test_pq_hybrid_default_off(self):
        import os
        from unittest import mock

        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("RPT_PQ_HYBRID", None)
            self.assertFalse(pq_hybrid_enabled())


class TestPqPlanArtifact(unittest.TestCase):
    def test_migration_plan_exists_and_names_kyber(self):
        plan = ROOT / "docs" / "PQ_MIGRATION.md"
        self.assertTrue(plan.is_file(), "missing docs/PQ_MIGRATION.md")
        text = plan.read_text(encoding="utf-8")
        self.assertIn("Kyber", text)
        self.assertIn("ML-KEM", text)
        self.assertIn("hybrid", text.lower())
        self.assertIn("pq_hybrid", text)
        self.assertIn("rotation", text.lower())
        # Honest: not residual PQ until dual-wire
        self.assertTrue(
            "not** claimed" in text or "not claimed" in text.lower() or "S0" in text
        )


if __name__ == "__main__":
    unittest.main()
