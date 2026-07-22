"""Entry-only Node A wipe countdown for public homepage (exit timer removed)."""

from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "status_page"))

from node_wipe_countdown import (  # noqa: E402
    HONESTY_BLURB,
    NODE_A_ENTRY_LABEL,
    NODE_B_EXIT_LABEL,
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
        self.assertIn(NODE_A_ENTRY_LABEL, html)
        self.assertNotIn(NODE_B_EXIT_LABEL, html)
        self.assertIn('id="node-wipe-countdown"', html)
        self.assertIn('id="nw-entry-days"', html)
        self.assertNotIn('id="nw-exit-seconds"', html)
        self.assertIn('id="node-wipe-label-entry"', html)
        self.assertNotIn('id="node-wipe-label-exit"', html)
        self.assertIn("nw-unit", html)
        self.assertIn("setInterval", html)
        self.assertIn("1000", html)
        self.assertIn("data-next-entry", html)
        self.assertIn("data-entry-only", html)
        self.assertIn(str(NODE_WIPE_PERIOD_SECONDS), html)
        # Honesty: entry-only live wipe / exit never wiped / not provider backup erase
        low = html.lower()
        self.assertIn("entry", low)
        self.assertIn("never wiped", low)
        self.assertIn("provider", low)

    def test_homepage_render_includes_dual_wipe_countdown(self):
        """Drive shipped status_page.render_html entry point."""
        page = status_app.render_html({"title": "RESTORE PRIVACY"}).decode("utf-8")
        self.assertIn(NODE_A_ENTRY_LABEL, page)
        self.assertNotIn(NODE_B_EXIT_LABEL, page)
        self.assertIn('id="node-wipe-countdown"', page)
        self.assertIn('id="nw-entry-days"', page)
        self.assertIn("nw-unit", page)
        self.assertIn("setInterval", page)
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


if __name__ == "__main__":
    unittest.main()
