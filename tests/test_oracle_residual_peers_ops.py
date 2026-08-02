"""Oracle residual peer catalog (IS+DE) + ops entitlement counters + Ned growth.

Drives shipped node.oracle_master collate / ned_learn — no live fleet.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SP = ROOT / "status_page"
if str(SP) not in sys.path:
    sys.path.insert(0, str(SP))


def _full_cojoin() -> dict:
    return {
        "all_ready": True,
        "readiness": {"vpn": True, "rpai": True, "perccent": True},
        "roles": {
            "vpn": {"ready": True},
            "rpai": {"ready": True, "stats": {"learning_epochs_local": 2}},
            "perccent": {"ready": True, "stats": {"seed_ticks": 3}},
        },
    }


class TestOracleResidualPeersAndOps(unittest.TestCase):
    def test_live_peer_codes_match_product_catalog(self) -> None:
        from node.oracle_master import (
            LIVE_RESIDUAL_PEER_CODES,
            RETIRED_RESIDUAL_PEER_CODES,
        )

        self.assertEqual(tuple(LIVE_RESIDUAL_PEER_CODES), ("IS", "DE"))
        self.assertIn("US", RETIRED_RESIDUAL_PEER_CODES)
        self.assertIn("RO", RETIRED_RESIDUAL_PEER_CODES)
        for bad in RETIRED_RESIDUAL_PEER_CODES:
            self.assertNotIn(bad, LIVE_RESIDUAL_PEER_CODES)

    def test_collate_is_de_peers_full_catalog(self) -> None:
        from node.oracle_master import (
            LIVE_RESIDUAL_PEER_CODES,
            collate_satellite_heartbeats,
            ned_learn_oracle,
        )

        o = collate_satellite_heartbeats(
            [
                {
                    "host": "82.221.101.241",
                    "peer_code": "IS",
                    "cojoined": _full_cojoin(),
                    "capacity": {"live": 1, "capacity": 100},
                    "residual_peers": ["IS", "DE"],
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
        )
        peers = o["residual_peers"]
        self.assertTrue(peers["all_live_peers_observed"])
        self.assertEqual(peers["peers_observed"], len(LIVE_RESIDUAL_PEER_CODES))
        self.assertGreaterEqual(peers["peers"]["IS"]["observed"], 1)
        self.assertGreaterEqual(peers["peers"]["DE"]["observed"], 1)
        self.assertEqual(peers["retired_observed"], [])
        self.assertEqual(
            o["capabilities"]["residual_peers_observed"], len(LIVE_RESIDUAL_PEER_CODES)
        )
        self.assertTrue(o["capabilities"]["all_live_peers_observed"])
        # Co-join + suite still complete
        self.assertTrue(o["all_satellites_ready"])
        self.assertTrue(o["suite_architecture"]["all_suite_surfaces_observed"])

        learned = ned_learn_oracle({}, o, points=2)
        self.assertTrue(learned["ready_residual_catalog"])
        self.assertEqual(
            set(learned["residual_peers_learned"]), set(LIVE_RESIDUAL_PEER_CODES)
        )
        self.assertIn("IS", learned["residual_new_peers_learned"])
        self.assertIn("DE", learned["residual_new_peers_learned"])
        hw = " ".join(learned.get("ned_housework_done") or [])
        self.assertIn("learned_residual_peer:IS", hw)
        self.assertIn("learned_residual_peer:DE", hw)

    def test_partial_peers_no_invented_catalog_readiness(self) -> None:
        from node.oracle_master import collate_satellite_heartbeats, ned_learn_oracle

        o = collate_satellite_heartbeats(
            [
                {
                    "host": "is-only",
                    "cojoined": {
                        "all_ready": True,
                        "readiness": {
                            "vpn": True,
                            "rpai": True,
                            "perccent": True,
                        },
                    },
                    "capacity": {"live": 0, "capacity": 10},
                    "residual_peers": ["IS"],  # DE missing
                    "suite_surfaces": ["vpn"],
                }
            ]
        )
        peers = o["residual_peers"]
        self.assertFalse(peers["all_live_peers_observed"])
        self.assertEqual(peers["peers_observed"], 1)
        self.assertGreaterEqual(peers["peers"]["IS"]["observed"], 1)
        self.assertEqual(peers["peers"]["DE"]["observed"], 0)
        hw = " ".join(o.get("housework") or [])
        self.assertIn("learn_residual_peers", hw)
        self.assertIn("DE", hw)

        learned = ned_learn_oracle({}, o)
        self.assertFalse(learned["ready_residual_catalog"])
        self.assertIn("IS", learned["residual_peers_learned"])
        self.assertNotIn("DE", learned["residual_peers_learned"])

    def test_retired_us_does_not_complete_live_catalog(self) -> None:
        from node.oracle_master import collate_satellite_heartbeats, ned_learn_oracle

        o = collate_satellite_heartbeats(
            [
                {
                    "host": "stale-us",
                    "cojoined": {
                        "all_ready": False,
                        "readiness": {
                            "vpn": True,
                            "rpai": False,
                            "perccent": False,
                        },
                    },
                    "capacity": {"live": 0, "capacity": 1},
                    # Only retired peers — must not invent IS+DE readiness
                    "residual_peers": ["US", "RO", "united_states"],
                    "suite_surfaces": ["vpn"],
                }
            ]
        )
        peers = o["residual_peers"]
        self.assertFalse(peers["all_live_peers_observed"])
        self.assertEqual(peers["peers_observed"], 0)
        self.assertIn("US", peers["retired_observed"])
        self.assertIn("RO", peers["retired_observed"])
        hw = " ".join(o.get("housework") or [])
        self.assertIn("drop_retired_residual_peers", hw)
        self.assertIn("report_residual_peers", hw)

        learned = ned_learn_oracle({}, o)
        self.assertFalse(learned["ready_residual_catalog"])
        self.assertEqual(learned["residual_peers_learned"], [])
        self.assertEqual(learned["residual_new_peers_learned"], [])

    def test_ops_entitlement_counters_only(self) -> None:
        from node.oracle_master import collate_satellite_heartbeats, ned_learn_oracle

        o = collate_satellite_heartbeats(
            [
                {
                    "host": "ops-sat",
                    "cojoined": _full_cojoin(),
                    "capacity": {"live": 2, "capacity": 50},
                    "residual_peers": ["IS", "DE"],
                    "suite_surfaces": ["vpn", "rpai"],
                    "ops": {
                        "trial_claims": 4,
                        "trial_denied": 1,
                        "keygen_entitled": 2,
                        "entitled_sessions": 7,
                    },
                    "trial_ops": {"device_trial_claims": 3},
                }
            ]
        )
        ops = o["ops_entitlement"]
        self.assertEqual(ops["trial_claims"], 4)
        self.assertEqual(ops["trial_denied"], 1)
        self.assertEqual(ops["keygen_entitled"], 2)
        self.assertEqual(ops["entitled_sessions"], 7)
        self.assertEqual(ops["device_trial_claims"], 3)
        # No KEYGEN string material in snapshot
        blob = json.dumps(o).lower()
        self.assertNotIn("keygen_string", blob)
        self.assertNotIn("card_number", blob)

        learned = ned_learn_oracle({}, o)
        self.assertEqual(learned["ops_entitlement"]["trial_claims"], 4)
        self.assertEqual(learned["ops_entitlement"]["keygen_entitled"], 2)

    def test_ned_peer_growth_idempotent(self) -> None:
        from node.oracle_master import collate_satellite_heartbeats, ned_learn_oracle

        o = collate_satellite_heartbeats(
            [
                {
                    "host": "h1",
                    "cojoined": _full_cojoin(),
                    "capacity": {"live": 0, "capacity": 1},
                    "residual_peers": ["iceland", "germany"],
                    "suite_surfaces": ["vpn"],
                }
            ]
        )
        first = ned_learn_oracle({}, o, points=2)
        # base 2 + 1 suite (vpn) + 2 peers (IS, DE)
        self.assertEqual(first["growth_points_applied"], 5)
        self.assertEqual(len(first["residual_new_peers_learned"]), 2)

        second = ned_learn_oracle(first, o, points=2)
        # No new surfaces or peers — base only
        self.assertEqual(second["growth_points_applied"], 2)
        self.assertEqual(second["residual_new_peers_learned"], [])
        self.assertEqual(second["suite_new_surfaces_learned"], [])
        self.assertEqual(second["learning_epochs"], 2)

    def test_strip_keygen_card_reinstall_prose(self) -> None:
        from node.oracle_master import (
            assert_no_user_data,
            collate_satellite_heartbeats,
            ned_learn_oracle,
        )

        tainted = {
            "host": "taint-ops",
            "cojoined": _full_cojoin(),
            "capacity": {"live": 1, "capacity": 10},
            "residual_peers": ["IS", "DE"],
            "suite_surfaces": ["vpn", "wallet"],
            "ops": {"trial_claims": 1},
            "keygen_string": "KG-SECRET-XYZ",
            "keygen_token": "tok_abc",
            "card_number": "4111111111111111",
            "stripe_session_id": "cs_test_xxx",
            "reinstall_for_trial": "wipe and reinstall to get second trial",
            "trial_attack_surface": "public caveat prose",
            "install_id": "device-install-uuid",
            "device_pub": "ed25519-device-pub-hex",
            "seed_phrase": "abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about",
        }
        o = collate_satellite_heartbeats([tainted])
        self.assertEqual(assert_no_user_data(o), [])
        blob = json.dumps(o)
        for bad in (
            "KG-SECRET",
            "tok_abc",
            "4111111111111111",
            "cs_test_xxx",
            "wipe and reinstall",
            "second trial",
            "device-install-uuid",
            "ed25519-device-pub",
            "abandon abandon",
            "keygen_string",
            "card_number",
            "reinstall_for_trial",
            "install_id",
            "device_pub",
            "seed_phrase",
        ):
            self.assertNotIn(bad, blob)
        # Ops counters still absorbed
        self.assertEqual(o["ops_entitlement"]["trial_claims"], 1)
        self.assertTrue(o["residual_peers"]["all_live_peers_observed"])

        learned = ned_learn_oracle(
            {
                "keygen_string": "should-go",
                "card_number": "4242",
                "reinstall_for_trial": "nope",
            },
            o,
        )
        self.assertEqual(assert_no_user_data(learned), [])
        self.assertNotIn("keygen_string", learned)
        self.assertNotIn("card_number", learned)
        self.assertNotIn("reinstall_for_trial", learned)
        self.assertEqual(learned["ops_entitlement"]["trial_claims"], 1)

    def test_peer_aliases_and_host_role(self) -> None:
        from node.oracle_master import collate_satellite_heartbeats

        o = collate_satellite_heartbeats(
            [
                {
                    "host": "de-exit",
                    "role": "DE",
                    "cojoined": {
                        "all_ready": True,
                        "readiness": {
                            "vpn": True,
                            "rpai": True,
                            "perccent": True,
                        },
                        "residual_peers": [{"code": "iceland"}, {"country": "Germany"}],
                    },
                    "capacity": {"live": 0, "capacity": 1},
                    "suite_surfaces": ["vpn"],
                }
            ]
        )
        peers = o["residual_peers"]
        self.assertGreaterEqual(peers["peers"]["IS"]["observed"], 1)
        self.assertGreaterEqual(peers["peers"]["DE"]["observed"], 1)
        self.assertTrue(peers["all_live_peers_observed"])


if __name__ == "__main__":
    unittest.main()
