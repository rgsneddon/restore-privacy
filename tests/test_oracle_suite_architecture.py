"""Oracle Suite architecture parameters + Ned learn absorption (pure unit).

Drives shipped node.oracle_master.collate_satellite_heartbeats and
ned_learn_oracle — no live nodes.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SP = ROOT / "status_page"
if str(SP) not in sys.path:
    sys.path.insert(0, str(SP))


class TestOracleSuiteArchitecture(unittest.TestCase):
    def test_suite_surface_ids_cover_suite_nav_map(self) -> None:
        from node.oracle_master import SUITE_SURFACE_IDS, SUITE_SURFACE_LABELS

        # Match SuiteNavDest product family: VPN, wallet, Backup, analysis,
        # voting, credit, rpAI.
        for sid in (
            "vpn",
            "wallet",
            "backup",
            "analysis",
            "voting",
            "credit",
            "rpai",
        ):
            self.assertIn(sid, SUITE_SURFACE_IDS)
            self.assertIn(sid, SUITE_SURFACE_LABELS)
        self.assertEqual(len(SUITE_SURFACE_IDS), 7)

    def test_collate_with_full_suite_architecture(self) -> None:
        from node.oracle_master import (
            SUITE_SURFACE_IDS,
            collate_satellite_heartbeats,
            ned_learn_oracle,
        )

        cj = {
            "all_ready": True,
            "readiness": {"vpn": True, "rpai": True, "perccent": True},
            "roles": {
                "rpai": {"ready": True, "stats": {"learning_epochs_local": 3}},
                "perccent": {"ready": True, "stats": {"seed_ticks": 5}},
            },
        }
        suite = {
            "surfaces": {
                "vpn": True,
                "wallet": True,
                "backup": True,  # recovery tab
                "analysis": True,
                "voting": True,
                "credit": True,
                "rpai": True,
            }
        }
        o = collate_satellite_heartbeats(
            [
                {
                    "host": "sat-full",
                    "cojoined": cj,
                    "capacity": {"live": 2, "capacity": 256},
                    "suite": suite,
                }
            ]
        )
        self.assertEqual(o["satellites_seen"], 1)
        self.assertTrue(o["all_satellites_ready"])
        arch = o["suite_architecture"]
        self.assertTrue(arch["all_suite_surfaces_observed"])
        self.assertEqual(arch["surfaces_observed"], len(SUITE_SURFACE_IDS))
        caps = o["capabilities"]
        self.assertEqual(caps["suite_surfaces_observed"], len(SUITE_SURFACE_IDS))
        self.assertGreater(caps["suite_learn_points"], 0)
        self.assertIn("suite_backup_observed", caps)
        self.assertGreaterEqual(caps["suite_backup_observed"], 1)
        # VPN + wallet/Backup + Evolve + rpAI signals present
        for key in (
            "suite_vpn_observed",
            "suite_wallet_observed",
            "suite_backup_observed",
            "suite_analysis_observed",
            "suite_voting_observed",
            "suite_credit_observed",
            "suite_rpai_observed",
        ):
            self.assertGreaterEqual(caps[key], 1, key)

        learned = ned_learn_oracle({}, o)
        self.assertEqual(learned["learning_epochs"], 1)
        self.assertGreater(learned["growth_score"], 0)
        self.assertEqual(
            set(learned["suite_surfaces_learned"]), set(SUITE_SURFACE_IDS)
        )
        self.assertTrue(learned["ready_suite_architecture"])
        self.assertTrue(learned["ready_cojoined"])
        self.assertIn("backup", learned["suite_architecture"]["surfaces"])
        self.assertTrue(
            learned["suite_architecture"]["surfaces"]["backup"]["learned"]
        )
        # Housework records suite learn tags
        hw = " ".join(learned.get("ned_housework_done") or [])
        self.assertIn("learned_suite:backup", hw)
        self.assertIn("learned_suite:rpai", hw)

    def test_collate_list_form_suite_surfaces_and_aliases(self) -> None:
        from node.oracle_master import collate_satellite_heartbeats

        o = collate_satellite_heartbeats(
            [
                {
                    "host": "alias-sat",
                    "cojoined": {
                        "all_ready": False,
                        "readiness": {
                            "vpn": True,
                            "rpai": False,
                            "perccent": True,
                        },
                    },
                    "capacity": {"live": 0, "capacity": 10},
                    # security → backup, ned → rpai, percent → wallet
                    "suite_surfaces": [
                        "vpn",
                        "security",
                        "percent",
                        "ned",
                        "credit",
                    ],
                }
            ]
        )
        caps = o["capabilities"]
        self.assertGreaterEqual(caps["suite_backup_observed"], 1)
        self.assertGreaterEqual(caps["suite_wallet_observed"], 1)
        self.assertGreaterEqual(caps["suite_rpai_observed"], 1)
        self.assertEqual(caps["suite_analysis_observed"], 0)
        self.assertFalse(o["suite_architecture"]["all_suite_surfaces_observed"])
        self.assertFalse(o["all_satellites_ready"])

    def test_incomplete_does_not_invent_full_readiness(self) -> None:
        from node.oracle_master import collate_satellite_heartbeats, ned_learn_oracle

        # Incomplete co-join + partial suite surfaces
        o = collate_satellite_heartbeats(
            [
                {
                    "host": "partial",
                    "cojoined": {
                        "all_ready": False,
                        "readiness": {
                            "vpn": True,
                            "rpai": False,
                            "perccent": False,
                        },
                    },
                    "capacity": {"live": 1, "capacity": 50},
                    "suite": {"surfaces": {"vpn": True, "wallet": 1}},
                }
            ]
        )
        self.assertFalse(o["all_satellites_ready"])
        self.assertFalse(o["roles_ready"]["rpai"])
        self.assertFalse(o["roles_ready"]["perccent"])
        self.assertFalse(o["suite_architecture"]["all_suite_surfaces_observed"])
        self.assertEqual(o["suite_architecture"]["surfaces_observed"], 2)
        # Housework honest about missing suite surfaces / roles
        hw = " ".join(o.get("housework") or [])
        self.assertTrue(
            "learn_suite" in hw or "nudge_roles" in hw or "report_suite" in hw,
            hw,
        )
        findings = " ".join(o.get("findings") or [])
        self.assertIn("incomplete", findings.lower())

        learned = ned_learn_oracle({"learning_epochs": 5, "growth_score": 10}, o)
        self.assertEqual(learned["learning_epochs"], 6)
        self.assertFalse(learned["ready_cojoined"])
        self.assertFalse(learned["ready_suite_architecture"])
        self.assertFalse(learned["ready_rpai"])
        # Still advanced epochs and absorbed partial surfaces
        self.assertIn("vpn", learned["suite_surfaces_learned"])
        self.assertIn("wallet", learned["suite_surfaces_learned"])
        self.assertNotIn("voting", learned["suite_surfaces_learned"])
        self.assertGreater(learned["growth_score"], 10)

    def test_empty_satellites_honest(self) -> None:
        from node.oracle_master import collate_satellite_heartbeats, ned_learn_oracle

        o = collate_satellite_heartbeats([])
        self.assertEqual(o["satellites_seen"], 0)
        self.assertFalse(o["all_satellites_ready"])
        self.assertIn("no satellites", " ".join(o["findings"]).lower())
        self.assertEqual(o["suite_architecture"]["surfaces_observed"], 0)
        learned = ned_learn_oracle({}, o)
        self.assertFalse(learned["ready_cojoined"])
        self.assertFalse(learned["ready_suite_architecture"])
        self.assertEqual(learned["suite_surfaces_observed"], 0)
        self.assertEqual(learned["learning_epochs"], 1)

    def test_ned_learn_bonus_only_for_new_surfaces(self) -> None:
        from node.oracle_master import collate_satellite_heartbeats, ned_learn_oracle

        suite = {
            "surfaces": {sid: True for sid in ("vpn", "wallet", "backup", "rpai")}
        }
        o = collate_satellite_heartbeats(
            [
                {
                    "host": "h1",
                    "cojoined": {
                        "all_ready": True,
                        "readiness": {
                            "vpn": True,
                            "rpai": True,
                            "perccent": True,
                        },
                    },
                    "capacity": {"live": 0, "capacity": 1},
                    "suite": suite,
                }
            ]
        )
        first = ned_learn_oracle({}, o, points=2)
        # base 2 + 4 new surfaces
        self.assertEqual(first["growth_points_applied"], 6)
        self.assertEqual(len(first["suite_new_surfaces_learned"]), 4)

        second = ned_learn_oracle(first, o, points=2)
        # No new surfaces — only base points
        self.assertEqual(second["growth_points_applied"], 2)
        self.assertEqual(second["suite_new_surfaces_learned"], [])
        self.assertEqual(second["learning_epochs"], 2)

    def test_zeroed_nested_architecture_does_not_invent_observations(self) -> None:
        from node.oracle_master import (
            empty_suite_architecture,
            collate_satellite_heartbeats,
        )

        # Re-feed empty_suite_architecture() as satellite payload — must stay zero.
        zero = empty_suite_architecture()
        o = collate_satellite_heartbeats(
            [
                {
                    "host": "zero-arch",
                    "cojoined": {
                        "all_ready": False,
                        "readiness": {
                            "vpn": False,
                            "rpai": False,
                            "perccent": False,
                        },
                    },
                    "capacity": {"live": 0, "capacity": 1},
                    "suite_architecture": zero,
                }
            ]
        )
        arch = o["suite_architecture"]
        self.assertEqual(arch["surfaces_observed"], 0)
        self.assertFalse(arch["all_suite_surfaces_observed"])
        self.assertEqual(arch["suite_learn_points"], 0)
        for sid, entry in arch["surfaces"].items():
            self.assertEqual(entry["observed"], 0, sid)
            self.assertFalse(entry["learned"], sid)

    def test_nested_observed_zero_not_counted(self) -> None:
        from node.oracle_master import collate_satellite_heartbeats

        o = collate_satellite_heartbeats(
            [
                {
                    "host": "nested-zero",
                    "cojoined": {
                        "all_ready": True,
                        "readiness": {
                            "vpn": True,
                            "rpai": True,
                            "perccent": True,
                        },
                    },
                    "capacity": {"live": 0, "capacity": 1},
                    "suite": {
                        "surfaces": {
                            "vpn": {"observed": 0, "learned": True},
                            "wallet": {"observed": 0, "learned": False},
                            "backup": {"observed": 2, "learned": False},
                        }
                    },
                }
            ]
        )
        arch = o["suite_architecture"]
        self.assertEqual(arch["surfaces"]["vpn"]["observed"], 0)
        self.assertEqual(arch["surfaces"]["wallet"]["observed"], 0)
        self.assertEqual(arch["surfaces"]["backup"]["observed"], 2)
        self.assertEqual(arch["surfaces_observed"], 1)
        self.assertFalse(arch["all_suite_surfaces_observed"])

    def test_refeed_collate_output_stays_honest(self) -> None:
        from node.oracle_master import collate_satellite_heartbeats

        first = collate_satellite_heartbeats(
            [
                {
                    "host": "a",
                    "cojoined": {
                        "all_ready": True,
                        "readiness": {
                            "vpn": True,
                            "rpai": True,
                            "perccent": True,
                        },
                    },
                    "capacity": {"live": 1, "capacity": 10},
                    "suite_surfaces": ["vpn", "wallet"],
                }
            ]
        )
        # Re-feed full collated architecture as next satellite's suite_architecture
        second = collate_satellite_heartbeats(
            [
                {
                    "host": "b",
                    "cojoined": {
                        "all_ready": False,
                        "readiness": {
                            "vpn": True,
                            "rpai": False,
                            "perccent": False,
                        },
                    },
                    "capacity": {"live": 0, "capacity": 1},
                    "suite_architecture": first["suite_architecture"],
                }
            ]
        )
        # Should preserve observed counts from nested observed fields, not invent all 7
        arch = second["suite_architecture"]
        self.assertEqual(arch["surfaces"]["vpn"]["observed"], 1)
        self.assertEqual(arch["surfaces"]["wallet"]["observed"], 1)
        self.assertEqual(arch["surfaces"]["backup"]["observed"], 0)
        self.assertEqual(arch["surfaces_observed"], 2)
        self.assertFalse(arch["all_suite_surfaces_observed"])

    def test_forged_learned_true_without_observed_no_growth_bonus(self) -> None:
        from node.oracle_master import (
            SUITE_SURFACE_IDS,
            empty_suite_architecture,
            ned_learn_oracle,
        )

        fake = empty_suite_architecture()
        # Forge learned:true on every surface with observed:0
        for sid in SUITE_SURFACE_IDS:
            fake["surfaces"][sid]["learned"] = True
            fake["surfaces"][sid]["observed"] = 0
        fake["all_suite_surfaces_observed"] = True  # also forged top-level

        o = {
            "role": "helsinki_oracle",
            "satellites_seen": 0,
            "satellites_ready": 0,
            "all_satellites_ready": False,
            "roles_ready": {"vpn": False, "rpai": False, "perccent": False},
            "capabilities": {},
            "suite_architecture": fake,
            "housework": [],
            "findings": [],
            "updated_unix": 1,
        }
        learned = ned_learn_oracle({}, o, points=2)
        # Base points only — no +1 per forged surface
        self.assertEqual(learned["growth_points_applied"], 2)
        self.assertEqual(learned["suite_new_surfaces_learned"], [])
        self.assertEqual(learned["suite_surfaces_learned"], [])
        self.assertEqual(learned["suite_surfaces_observed"], 0)
        self.assertFalse(learned["ready_suite_architecture"])
        self.assertFalse(learned["ready_cojoined"])

    def test_admin_rps_absorbs_suite_keys(self) -> None:
        import tempfile
        from pathlib import Path

        from admin_rps import (
            ensure_admin_rps_ready_surface,
            load_rps_stats,
            ned_growth_public_snapshot,
            readiness_parameters,
        )

        cj = {
            "cojoined": True,
            "all_ready": True,
            "readiness": {"vpn": True, "rpai": True, "perccent": True},
            "roles": {
                "vpn": {"ready": True, "stats": {}},
                "rpai": {"ready": True, "stats": {"learning_epochs_local": 1}},
                "perccent": {"ready": True, "stats": {"seed_ticks": 1}},
            },
        }
        sats = [
            {
                "host": "82.221.101.241",
                "cojoined": cj,
                "capacity": {"live": 1, "capacity": 100},
                "suite_surfaces": [
                    "vpn",
                    "wallet",
                    "backup",
                    "analysis",
                    "voting",
                    "credit",
                    "rpai",
                ],
            }
        ]
        path = Path(tempfile.mkdtemp()) / "rps_suite.json"
        stats = ensure_admin_rps_ready_surface(
            stats_path=path, satellites=sats, allow_lab_fallback=False
        )
        ready = readiness_parameters(stats)
        self.assertTrue(ready["ready_cojoined"])
        # Suite completeness is on stats/snapshot, not co-join readiness matrix.
        self.assertNotIn("ready_suite_architecture", ready)
        self.assertTrue(stats.get("ready_suite_architecture"))
        self.assertEqual(stats["suite_surfaces_observed"], 7)
        snap = ned_growth_public_snapshot(stats)
        self.assertTrue(snap.get("ready_suite_architecture"))
        self.assertIn("backup", snap["suite_surfaces_learned"])
        self.assertIn("suite_architecture_surfaces", snap["growth_methods"])
        # Reload durable file
        again = load_rps_stats(stats_path=path)
        self.assertGreaterEqual(again["suite_surfaces_observed"], 1)


if __name__ == "__main__":
    unittest.main()
