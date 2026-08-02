"""CERBERUS / Helsinki oracle never collates or persists forbidden user data."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SP = ROOT / "status_page"
if str(SP) not in sys.path:
    sys.path.insert(0, str(SP))


def _tainted_satellite() -> dict:
    return {
        "host": "sat-taint",
        "cojoined": {
            "all_ready": True,
            "readiness": {"vpn": True, "rpai": True, "perccent": True},
            "roles": {
                "rpai": {"ready": True, "stats": {"learning_epochs_local": 1}},
                "perccent": {"ready": True, "stats": {"seed_ticks": 2}},
            },
            # Nested secrets must be stripped
            "connection_log": "Connect failed secret line",
            "mnemonic": "abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about",
        },
        "capacity": {"live": 1, "capacity": 64},
        "suite_surfaces": ["vpn", "wallet", "backup", "rpai"],
        "connection_log": ["line1", "line2"],
        "seed_phrase": "word1 word2 word3 word4 word5 word6 word7 word8 word9 word10 word11 word12",
        "passphrase": "super-secret-backup-pass",
        "backup_bytes": b"\x00\x01\x02percbackup",
        "backup_passphrase": "another-secret",
        "licence_text": "I accept the licence forever…",
        "private_key": "deadbeef",
    }


class TestOracleNoUserData(unittest.TestCase):
    def test_collate_strips_forbidden_fields(self) -> None:
        from node.oracle_master import (
            assert_no_user_data,
            collate_satellite_heartbeats,
            ned_learn_oracle,
        )

        o = collate_satellite_heartbeats([_tainted_satellite()])
        hits = assert_no_user_data(o)
        self.assertEqual(hits, [], hits)
        blob = json.dumps(o)
        for bad in (
            "connection_log",
            "mnemonic",
            "seed_phrase",
            "passphrase",
            "backup_bytes",
            "licence_text",
            "private_key",
            "super-secret",
            "abandon abandon",
        ):
            self.assertNotIn(bad, blob.lower() if bad.islower() else blob)

        # Operational signals still present
        self.assertEqual(o["satellites_seen"], 1)
        self.assertTrue(o["all_satellites_ready"])
        self.assertGreaterEqual(o["capabilities"]["suite_vpn_observed"], 1)

        learned = ned_learn_oracle(
            {
                "connection_log": "should vanish",
                "mnemonic": "also gone",
                "growth_score": 0,
            },
            o,
        )
        hits2 = assert_no_user_data(learned)
        self.assertEqual(hits2, [], hits2)
        self.assertNotIn("connection_log", learned)
        self.assertNotIn("mnemonic", learned)
        self.assertGreaterEqual(learned["learning_epochs"], 1)

    def test_save_rps_stats_never_persists_user_secrets(self) -> None:
        from admin_rps import load_rps_stats, save_rps_stats
        from node.oracle_master import assert_no_user_data, collate_satellite_heartbeats, ned_learn_oracle

        path = Path(tempfile.mkdtemp()) / "ned_stats.json"
        o = collate_satellite_heartbeats([_tainted_satellite()])
        learned = ned_learn_oracle(
            {
                "connection_log": "persist-me-not",
                "seed_phrase": "twelve words would be here",
                "passphrase": "nope",
                "backup_bytes": "AAAA",
                "licence_text": "accept forever",
            },
            o,
        )
        saved = save_rps_stats(learned, stats_path=path)
        self.assertEqual(assert_no_user_data(saved), [])
        raw = path.read_text(encoding="utf-8")
        for bad in (
            "connection_log",
            "seed_phrase",
            "passphrase",
            "backup_bytes",
            "licence_text",
            "persist-me-not",
        ):
            self.assertNotIn(bad, raw)
        reloaded = load_rps_stats(stats_path=path)
        self.assertEqual(assert_no_user_data(reloaded), [])
        self.assertGreaterEqual(int(reloaded.get("learning_epochs") or 0), 1)

    def test_strip_user_data_helper(self) -> None:
        from node.oracle_master import strip_user_data

        cleaned = strip_user_data(
            {
                "host": "x",
                "mnemonic": "secret",
                "nested": {"passphrase": "p", "ok": 1},
                "capacity": {"live": 2},
            }
        )
        self.assertEqual(cleaned["host"], "x")
        self.assertNotIn("mnemonic", cleaned)
        self.assertNotIn("passphrase", cleaned["nested"])
        self.assertEqual(cleaned["nested"]["ok"], 1)


if __name__ == "__main__":
    unittest.main()
