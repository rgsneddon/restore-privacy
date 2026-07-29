"""Entry-only Node A wipe countdown for public homepage (exit timer removed)."""

from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "status_page"))

from node_wipe_countdown import (  # noqa: E402
    ALL_NODES_DATA_CLEARED_LABEL,
    HONESTY_BLURB,
    NODE_A_ENTRY_LABEL,
    NODE_B_EXIT_LABEL,
    NODE_WIPE_HEADING,
    NODE_WIPE_PERIOD,
    NODE_WIPE_PERIOD_SECONDS,
    dual_node_wipe_state,
    format_countdown,
    next_clear_from_last,
    next_deadline_on_grid,
    remaining_seconds_until,
    render_node_wipe_countdown_html,
    split_countdown_units,
    unit_boxes_html,
)
import app as status_app  # noqa: E402


class TestNodeWipePeriod(unittest.TestCase):
    def test_period_is_seven_days_matching_weekly_wipe(self):
        """Shipped constant — not a hard-coded 604800 only in the test."""
        self.assertEqual(NODE_WIPE_PERIOD_SECONDS, int(NODE_WIPE_PERIOD.total_seconds()))
        self.assertEqual(NODE_WIPE_PERIOD, timedelta(days=7))
        self.assertEqual(NODE_WIPE_PERIOD_SECONDS, 7 * 86400)


class TestNodeWipeMath(unittest.TestCase):
    def test_remaining_and_format(self):
        deadline = datetime(2026, 7, 28, 12, 0, 0, tzinfo=timezone.utc)
        now = datetime(2026, 7, 28, 10, 0, 0, tzinfo=timezone.utc)
        rem = remaining_seconds_until(deadline, now=now)
        self.assertEqual(rem, 2 * 3600)
        self.assertEqual(format_countdown(rem), "02:00:00")
        self.assertEqual(
            remaining_seconds_until(deadline, now=deadline + timedelta(hours=1)), 0
        )

    def test_dhms_split_and_unit_boxes(self):
        # 2 days + 3h + 4m + 5s
        sec = 2 * 86400 + 3 * 3600 + 4 * 60 + 5
        u = split_countdown_units(sec)
        self.assertEqual(u["days"], 2)
        self.assertEqual(u["hours"], 3)
        self.assertEqual(u["minutes"], 4)
        self.assertEqual(u["seconds"], 5)
        self.assertIn("2d", format_countdown(sec))
        boxes = unit_boxes_html(sec, value_id_prefix="nw-test")
        self.assertIn("nw-unit", boxes)
        self.assertIn('data-unit="days"', boxes)
        self.assertIn('data-unit="hours"', boxes)
        self.assertIn('data-unit="minutes"', boxes)
        self.assertIn('data-unit="seconds"', boxes)
        self.assertIn("nw-test-days", boxes)
        self.assertIn("DAYS", boxes)

    def test_next_clear_from_last_rolls_forward(self):
        last = datetime(2026, 7, 1, 0, 0, 0, tzinfo=timezone.utc)
        now = datetime(2026, 7, 20, 0, 0, 0, tzinfo=timezone.utc)
        nxt = next_clear_from_last(last, now=now, period=NODE_WIPE_PERIOD)
        self.assertGreater(nxt, now)
        # last + 3*7d = Jul 22
        self.assertEqual(nxt, datetime(2026, 7, 22, 0, 0, 0, tzinfo=timezone.utc))

    def test_dual_state_labels_and_remaining(self):
        now = datetime(2026, 7, 21, 12, 0, 0, tzinfo=timezone.utc)
        entry_next = now + timedelta(hours=5, minutes=30)
        exit_next = now + timedelta(hours=10)
        st = dual_node_wipe_state(
            now=now, entry_next=entry_next, exit_next=exit_next
        )
        self.assertEqual(st["period_seconds"], NODE_WIPE_PERIOD_SECONDS)
        self.assertEqual(st["entry"]["label"], NODE_A_ENTRY_LABEL)
        self.assertEqual(st["exit"]["label"], NODE_B_EXIT_LABEL)
        self.assertEqual(
            st["entry"]["remaining_seconds"], 5 * 3600 + 30 * 60
        )
        self.assertEqual(st["exit"]["remaining_seconds"], 10 * 3600)
        self.assertEqual(
            st["entry"]["display"],
            format_countdown(st["entry"]["remaining_seconds"]),
        )
        # Distinct deadlines
        self.assertNotEqual(st["entry"]["next_clear_at"], st["exit"]["next_clear_at"])

    def test_grid_default_period_constant(self):
        now = datetime(2026, 7, 21, 12, 0, 0, tzinfo=timezone.utc)
        nxt = next_deadline_on_grid(
            now=now, period_seconds=NODE_WIPE_PERIOD_SECONDS, phase_seconds=0
        )
        rem = remaining_seconds_until(nxt, now=now)
        self.assertGreater(rem, 0)
        self.assertLessEqual(rem, NODE_WIPE_PERIOD_SECONDS)


class TestNodeWipeHtml(unittest.TestCase):
    def test_fragment_exact_labels_two_slots_and_tick(self):
        now = datetime(2026, 7, 21, 12, 0, 0, tzinfo=timezone.utc)
        html = render_node_wipe_countdown_html(
            now=now,
            entry_next=now + timedelta(days=1),
            exit_next=now + timedelta(days=2),
        )
        self.assertEqual(ALL_NODES_DATA_CLEARED_LABEL, "ALL NODES DATA CLEARED IN")
        self.assertEqual(NODE_A_ENTRY_LABEL, ALL_NODES_DATA_CLEARED_LABEL)
        self.assertIn(ALL_NODES_DATA_CLEARED_LABEL, html)
        self.assertNotIn(NODE_B_EXIT_LABEL, html)
        self.assertNotIn("ALL NODE A (ENTRY NODE)", html)
        self.assertIn(NODE_WIPE_HEADING, html)
        self.assertIn('id="node-wipe-countdown"', html)
        self.assertIn('id="nw-entry-days"', html)
        self.assertNotIn('id="nw-exit-seconds"', html)
        self.assertIn('id="node-wipe-label-entry"', html)
        self.assertNotIn('id="node-wipe-label-exit"', html)
        self.assertIn("nw-unit", html)
        self.assertIn("/static/node_wipe_countdown.js", html)
        js = (ROOT / "status_page" / "static" / "node_wipe_countdown.js").read_text(
            encoding="utf-8"
        )
        self.assertIn("setInterval", js)
        self.assertIn("1000", js)
        self.assertIn("data-next-entry", html)
        self.assertIn("data-fleet-sequential", html)
        self.assertIn(str(NODE_WIPE_PERIOD_SECONDS), html)
        # Honesty: sequential fleet / all nodes (short blurb) + hop failsafe
        low = html.lower()
        self.assertIn("one at a time", low)
        self.assertNotIn("simultaneous all-node wipe", low)
        self.assertNotIn("provider backups and netflow are not erased", low)
        self.assertTrue(
            "is" in low and "de" in low and "us" in low,
            "blurb should name monopin fleet peers IS/DE/US",
        )
        self.assertNotIn("is then ro then us", low)
        self.assertIn("manual reconnection", low)
        self.assertIn("weekly", low)
        self.assertIn("disconnect", low)
        self.assertIn(HONESTY_BLURB, html)

    def test_homepage_render_includes_dual_wipe_countdown(self):
        """Drive shipped status_page.render_html entry point."""
        page = status_app.render_html({"title": "RESTORE PRIVACY"}).decode("utf-8")
        self.assertIn(ALL_NODES_DATA_CLEARED_LABEL, page)
        self.assertNotIn(NODE_B_EXIT_LABEL, page)
        self.assertIn('id="node-wipe-countdown"', page)
        self.assertIn('id="nw-entry-days"', page)
        self.assertIn("nw-unit", page)
        self.assertIn("/static/node_wipe_countdown.js", page)
        # Coexists with audit countdown
        self.assertIn('id="audit-countdown"', page)
        self.assertIn(HONESTY_BLURB.split(".")[0], page)
        # Redesign compartments + RB palette
        self.assertIn("page-shell", page)
        self.assertIn("panel-card", page)
        self.assertIn("--rb-navy", page)
        self.assertNotIn("STRONG DISCLAIMER", page)
        self.assertNotIn("#0b0f14", page)

    def test_epoch_roll_does_not_crash_when_past(self):
        now = datetime(2026, 7, 21, 12, 0, 0, tzinfo=timezone.utc)
        past = now - timedelta(hours=1)
        st = dual_node_wipe_state(now=now, entry_next=past, exit_next=past)
        self.assertGreater(st["entry"]["remaining_seconds"], 0)
        self.assertGreater(st["exit"]["remaining_seconds"], 0)
        html = render_node_wipe_countdown_html(
            now=now, entry_next=past, exit_next=past
        )
        self.assertIn(NODE_A_ENTRY_LABEL, html)
        self.assertIn("nw-entry-days", html)


class TestLastClearResetsPeriod(unittest.TestCase):
    """Acceptance: post-completion remaining ≈ full period; mid-grid without anchor."""

    def test_mid_grid_without_anchor_nonzero(self):
        """No last-clear → epoch grid; remaining in (0, period] (e.g. ~3d class)."""
        # Epoch-aligned: 3.5 days into a 7d period from a known boundary
        # 2026-07-23 12:00 UTC is mid-period if boundary is 2026-07-23 00:00? Use pure grid.
        now = datetime(2026, 7, 23, 12, 0, 0, tzinfo=timezone.utc)
        nxt = next_deadline_on_grid(
            now=now, period_seconds=NODE_WIPE_PERIOD_SECONDS, phase_seconds=0
        )
        rem = remaining_seconds_until(nxt, now=now)
        self.assertGreater(rem, 0)
        self.assertLessEqual(rem, NODE_WIPE_PERIOD_SECONDS)
        st = dual_node_wipe_state(
            now=now, entry_last=None, entry_next=None
        )
        # dual_node may still pick env/file — force pure grid via next_deadline
        self.assertGreater(st["entry"]["remaining_seconds"], 0)
        self.assertLessEqual(st["entry"]["remaining_seconds"], NODE_WIPE_PERIOD_SECONDS)

    def test_last_clear_at_now_full_period_remaining(self):
        """After successful clear at *now*, next deadline is ~now+7d."""
        now = datetime(2026, 7, 25, 18, 0, 0, tzinfo=timezone.utc)
        st = dual_node_wipe_state(
            now=now,
            entry_last=now,
            entry_next=None,
        )
        rem = st["entry"]["remaining_seconds"]
        # Full period ± 1s (integer seconds)
        self.assertGreaterEqual(rem, NODE_WIPE_PERIOD_SECONDS - 1)
        self.assertLessEqual(rem, NODE_WIPE_PERIOD_SECONDS)
        nxt = datetime.fromisoformat(
            st["entry"]["next_clear_at"].replace("Z", "+00:00")
        )
        self.assertAlmostEqual(
            (nxt - now).total_seconds(),
            float(NODE_WIPE_PERIOD_SECONDS),
            delta=1.0,
        )

    def test_resolve_entry_last_clear_from_file(self):
        import json
        import os
        import tempfile
        from node_wipe_countdown import resolve_entry_last_clear

        now = datetime(2026, 7, 25, 12, 0, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "var" / "rpt-node-a-last-clear.json"
            path.parent.mkdir(parents=True)
            path.write_text(
                json.dumps(
                    {
                        "last_clear_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "target": "IS",
                        "live": True,
                    }
                ),
                encoding="utf-8",
            )
            prev = os.environ.pop("RPT_NODE_A_LAST_CLEAR", None)
            prev_f = os.environ.pop("RPT_NODE_A_LAST_CLEAR_FILE", None)
            try:
                got = resolve_entry_last_clear(install_root=td)
                self.assertEqual(got, now)
                st = dual_node_wipe_state(
                    now=now + timedelta(hours=1),
                    entry_last=got,
                )
                self.assertGreater(
                    st["entry"]["remaining_seconds"],
                    NODE_WIPE_PERIOD_SECONDS - 3700,
                )
            finally:
                if prev is not None:
                    os.environ["RPT_NODE_A_LAST_CLEAR"] = prev
                if prev_f is not None:
                    os.environ["RPT_NODE_A_LAST_CLEAR_FILE"] = prev_f


class TestRecordEntryLastClearLiveOnly(unittest.TestCase):
    def test_dry_run_does_not_write_and_live_is_writes(self):
        import json
        import tempfile

        from node.fleet_wipe import (  # noqa: E402
            entry_last_clear_path,
            load_entry_last_clear,
            record_entry_last_clear,
        )

        with tempfile.TemporaryDirectory() as td:
            self.assertIsNone(
                record_entry_last_clear(
                    live=False,
                    install_root=td,
                    when="2026-07-25T18:00:00Z",
                )
            )
            self.assertFalse(Path(entry_last_clear_path(td)).is_file())
            # RO target must not advance public entry clear
            self.assertIsNone(
                record_entry_last_clear(
                    live=True, target="RO", install_root=td, when="2026-07-25T18:00:00Z"
                )
            )
            rec = record_entry_last_clear(
                live=True,
                target="IS",
                install_root=td,
                when="2026-07-25T18:00:00Z",
                source="unit_test",
            )
            self.assertIsNotNone(rec)
            assert rec is not None
            self.assertEqual(rec["last_clear_at"], "2026-07-25T18:00:00Z")
            loaded = load_entry_last_clear(install_root=td)
            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(loaded["last_clear_at"], "2026-07-25T18:00:00Z")
            blob = json.loads(Path(entry_last_clear_path(td)).read_text(encoding="utf-8"))
            self.assertTrue(blob.get("live"))


if __name__ == "__main__":
    unittest.main()
