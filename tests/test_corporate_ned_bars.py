"""CORPORATE CLIENTS bars track NED / rpAI learned % (home + settings)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "status_page"))

PART_IDS = (
    "admin_sdk",
    "databases",
    "branded_vpn",
    "dedicated_server",
    "branded_ai",
)


def _oracle_stats(surfaces: dict[str, object], *, nodes: int = 0, epochs: int = 0) -> dict:
    """Real NED learn path: collate heartbeat → ned_learn_oracle → rps stats."""
    from node.oracle_master import collate_satellite_heartbeats, ned_learn_oracle

    rpai_on = bool(surfaces.get("rpai"))
    vpn_on = bool(surfaces.get("vpn"))
    perc_on = bool(surfaces.get("wallet") or surfaces.get("backup"))
    cj = {
        "all_ready": vpn_on and rpai_on and perc_on,
        "readiness": {"vpn": vpn_on, "rpai": rpai_on, "perccent": perc_on},
        "roles": {
            "rpai": {"ready": rpai_on, "stats": {"learning_epochs_local": epochs}},
            "perccent": {"ready": perc_on, "stats": {"seed_ticks": 1 if perc_on else 0}},
        },
    }
    o = collate_satellite_heartbeats(
        [
            {
                "host": "corp-ned-sat",
                "cojoined": cj,
                "capacity": {"live": nodes, "capacity": 64},
                "suite": {"surfaces": surfaces},
            }
        ]
    )
    learned = ned_learn_oracle({}, o)
    learned["nodes_online"] = int(nodes)
    if epochs:
        learned["learning_epochs"] = max(int(learned.get("learning_epochs") or 0), int(epochs))
    return learned


class TestCorporateNedBarValues(unittest.TestCase):
    def test_two_snapshots_move_and_can_reach_100(self) -> None:
        from admin_rps import ned_growth_public_snapshot
        from settings_explainer import corporate_ned_bar_values

        empty = ned_growth_public_snapshot({})
        empty_bars = empty["corporate_parts"]
        self.assertEqual([b["id"] for b in empty_bars], list(PART_IDS))
        self.assertEqual(empty_bars, corporate_ned_bar_values(empty))
        for bar in empty_bars:
            self.assertIn(bar["percent"], range(0, 101))
        empty_map = {b["id"]: int(b["percent"]) for b in empty_bars}
        self.assertEqual(empty_map["branded_vpn"], 0)
        self.assertEqual(empty_map["branded_ai"], 0)

        partial_stats = _oracle_stats({"vpn": {"observed": 2}})
        partial = ned_growth_public_snapshot(partial_stats)
        partial_map = {b["id"]: int(b["percent"]) for b in partial["corporate_parts"]}
        self.assertEqual(len(partial["corporate_parts"]), 5)
        self.assertGreater(partial_map["branded_vpn"], empty_map["branded_vpn"])
        self.assertLess(partial_map["branded_vpn"], 100)
        self.assertLess(partial_map["branded_ai"], 100)

        full_stats = _oracle_stats(
            {
                "vpn": {"observed": 2},
                "wallet": {"observed": 1},
                "backup": {"observed": 1},
                "analysis": {"observed": 3},
                "voting": {"observed": 1},
                "credit": {"observed": 1},
                "rpai": {"observed": 4},
            },
            nodes=5,
            epochs=8,
        )
        full = ned_growth_public_snapshot(full_stats)
        full_bars = full["corporate_parts"]
        self.assertEqual([b["id"] for b in full_bars], list(PART_IDS))
        self.assertEqual(full_bars, corporate_ned_bar_values(full))
        full_map = {b["id"]: int(b["percent"]) for b in full_bars}
        for bar in full_bars:
            self.assertIn(bar["percent"], range(0, 101), bar)
        self.assertNotEqual(full_map, empty_map)
        self.assertNotEqual(full_map, partial_map)
        self.assertGreater(full_map["admin_sdk"], partial_map["admin_sdk"])
        self.assertGreater(full_map["databases"], empty_map["databases"])
        self.assertEqual(full_map["branded_ai"], 100)
        self.assertEqual(full_map["dedicated_server"], 100)
        self.assertNotIn(full_map["branded_vpn"], (94, 95, 96, 97, 98, 99))


class TestCorporateClientsBoxRender(unittest.TestCase):
    def _assert_box(self, html: str, *, css: str = "") -> None:
        blob = html + css
        self.assertIn('id="corporate-clients"', html)
        self.assertIn("Corporate clients", html)
        self.assertIn("50% AI", html)
        self.assertIn("worked into the contract", html)
        self.assertIn("no limits", html.lower())
        self.assertIn("controlled and administered", html)
        self.assertIn("rpAI (SDK) progressive learned ability (%)", html)
        i_head = html.index("rpAI (SDK) progressive learned ability (%)")
        i_row = html.index('class="corp-meter-row"')
        self.assertLess(i_head, i_row)
        self.assertIn('id="corporate-clients-graphs"', html)
        heading_css = blob[blob.index(".corp-meters-heading") : blob.index(".corp-meter-row")]
        self.assertIn("#39ff14", heading_css)
        self.assertIn("#39ff14", blob)
        self.assertIn("max-width: 100%", blob)
        self.assertIn(".corp-meter-pct.is-100", blob)
        self.assertIn("#3ec6ff", blob)
        for pid in PART_IDS:
            self.assertIn(f'data-corp-part="{pid}"', html)
        self.assertEqual(html.count('class="corp-meter-row"'), 5)
        self.assertEqual(html.count('data-corp-fill="1"'), 5)
        self.assertNotIn("94%", html)
        self.assertNotIn("99%", html)

    def test_shared_box_on_home_and_settings(self) -> None:
        from admin_rps import ned_growth_public_snapshot
        from app import render_html
        from settings_explainer import (
            CORPORATE_CLIENTS_CONTRACT,
            CORPORATE_CLIENTS_LIMITS,
            corporate_clients_css,
            render_corporate_clients_html,
            render_settings_explainer_page_html,
        )

        self.assertIn("50% AI", CORPORATE_CLIENTS_CONTRACT)
        self.assertIn("worked into the contract", CORPORATE_CLIENTS_CONTRACT)
        self.assertIn("no limits", CORPORATE_CLIENTS_LIMITS.lower())
        self.assertIn("controlled and administered", CORPORATE_CLIENTS_LIMITS)

        snap = ned_growth_public_snapshot(
            _oracle_stats({"rpai": {"observed": 4}, "vpn": {"observed": 1}}, nodes=5, epochs=8)
        )
        box = render_corporate_clients_html(snap)
        css = corporate_clients_css()
        self._assert_box(box, css=css)
        self.assertIn('style="width:100%"', box)
        self.assertIn("corp-meter-pct is-100", box)
        self.assertIn("/api/ned-growth", box)

        home = render_html({"title": "RESTORE PRIVACY"}).decode("utf-8")
        settings = render_settings_explainer_page_html().decode("utf-8")
        self._assert_box(home)
        self._assert_box(settings)
        self.assertIn('id="corporate-clients"', home)
        self.assertIn('id="corporate-clients"', settings)
        self.assertIn("£30,000", home)
        self.assertIn("£30,000", settings)


if __name__ == "__main__":
    unittest.main()
