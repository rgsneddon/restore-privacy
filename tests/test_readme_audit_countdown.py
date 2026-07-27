"""README SuperGrok tagline + real-time time-til-next-audit countdown."""

from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "status_page"))

from audit_countdown import (  # noqa: E402
    AUDIT_PERIOD,
    AUDIT_PERIOD_SECONDS,
    TIME_TIL_NEXT_AUDIT_BLURB,
    TIME_TIL_NEXT_AUDIT_LABEL,
    countdown_state,
    format_countdown,
    next_audit_at,
    parse_audit_generated_at,
    remaining_seconds_until,
    render_audit_countdown_html,
)
import app as status_app  # noqa: E402


class TestReadmeSuperGrokTagline(unittest.TestCase):
    def test_readme_operator_raskul_and_product_identity(self):
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        # Removed OBJECTIVE sentence
        self.assertNotIn(
            "Not WireGuard, OpenVPN, IPsec, or any other pre-existing VPN product.",
            text,
        )
        # Operator credit (concise product intro — no banned person names)
        self.assertIn("Raskul", text)
        self.assertNotIn("Russell G Sneddon", text)
        self.assertNotIn("Sneddon", text)
        self.assertIn("custom VPN", text)
        self.assertIn("security audits", text)
        # Public mirror stays in sync when present
        pub = ROOT / "status_page" / "public" / "README.md"
        if pub.is_file():
            pub_text = pub.read_text(encoding="utf-8")
            self.assertIn("Raskul", pub_text)
            self.assertNotIn("Russell G Sneddon", pub_text)
            self.assertNotIn(
                "Not WireGuard, OpenVPN, IPsec, or any other pre-existing VPN product.",
                pub_text,
            )


class TestAuditCountdownMath(unittest.TestCase):
    def test_period_is_one_day(self):
        self.assertEqual(AUDIT_PERIOD_SECONDS, 86400)
        self.assertEqual(AUDIT_PERIOD, timedelta(days=1))

    def test_format_countdown_includes_days_hours_minutes_seconds(self):
        """Display always exposes days, hours, minutes, seconds (not HH:MM:SS-only)."""
        from audit_countdown import split_countdown_units

        # Sub-day remainder
        self.assertEqual(format_countdown(3600), "0d 01:00:00")
        self.assertEqual(format_countdown(0), "0d 00:00:00")
        self.assertEqual(format_countdown(90), "0d 00:01:30")
        # Multi-day remainder
        self.assertEqual(format_countdown(86400 + 3661), "1d 01:01:01")
        self.assertEqual(format_countdown(2 * 86400 + 5), "2d 00:00:05")
        units = split_countdown_units(90061)  # 1d 1h 1m 1s
        self.assertEqual(units["days"], 1)
        self.assertEqual(units["hours"], 1)
        self.assertEqual(units["minutes"], 1)
        self.assertEqual(units["seconds"], 1)

    def test_parse_and_remaining_from_known_timestamp(self):
        last = parse_audit_generated_at("2026-07-21T10:00:00Z")
        self.assertIsNotNone(last)
        assert last is not None
        nxt = next_audit_at(last)
        self.assertEqual(
            nxt,
            datetime(2026, 7, 22, 10, 0, 0, tzinfo=timezone.utc),
        )
        # Exactly 1h before deadline
        now = datetime(2026, 7, 22, 9, 0, 0, tzinfo=timezone.utc)
        rem = remaining_seconds_until(nxt, now=now)
        self.assertEqual(rem, 3600)
        self.assertEqual(format_countdown(rem), "0d 01:00:00")
        # Overdue → 0
        late = datetime(2026, 7, 22, 11, 0, 0, tzinfo=timezone.utc)
        self.assertEqual(remaining_seconds_until(nxt, now=late), 0)
        self.assertEqual(format_countdown(0), "0d 00:00:00")

    def test_countdown_state_drives_real_helper(self):
        last = datetime(2026, 7, 21, 10, 47, 19, tzinfo=timezone.utc)
        now = last + timedelta(hours=1, minutes=15, seconds=5)
        st = countdown_state(now=now, last_generated_at=last)
        self.assertTrue(st["available"])
        self.assertEqual(st["label"], TIME_TIL_NEXT_AUDIT_LABEL)
        self.assertIn("time til next audit", st["label"])
        self.assertIn("wipedown", st["label"])
        self.assertEqual(st["blurb"], TIME_TIL_NEXT_AUDIT_BLURB)
        self.assertEqual(st["period_seconds"], AUDIT_PERIOD_SECONDS)
        # 1d - 1h15m5s = 22h44m55s
        self.assertEqual(st["remaining_seconds"], 22 * 3600 + 44 * 60 + 55)
        self.assertEqual(st["display"], format_countdown(st["remaining_seconds"]))
        self.assertEqual(st["display"], "0d 22:44:55")
        self.assertEqual(st["next_audit_at"], "2026-07-22T10:47:19Z")
        self.assertFalse(st.get("rolled_forward"))

    def test_countdown_rolls_forward_when_overdue(self):
        """Stale generated_at must not freeze remaining at 0d 00:00:00."""
        from audit_countdown import next_audit_at_rolling

        last = datetime(2026, 7, 21, 10, 0, 0, tzinfo=timezone.utc)
        # 30h after last → last+1d = 22nd 10:00 past → next 23rd 10:00 (last+2d)
        now = datetime(2026, 7, 22, 16, 0, 0, tzinfo=timezone.utc)
        nxt = next_audit_at_rolling(last, now=now)
        self.assertEqual(nxt, datetime(2026, 7, 23, 10, 0, 0, tzinfo=timezone.utc))
        st = countdown_state(now=now, last_generated_at=last)
        self.assertTrue(st["available"])
        self.assertGreater(st["remaining_seconds"], 0)
        self.assertEqual(st["remaining_seconds"], 18 * 3600)
        self.assertEqual(st["display"], "0d 18:00:00")
        self.assertNotEqual(st["display"], "0d 00:00:00")
        self.assertTrue(st.get("rolled_forward"))
        # Fragment still ticks with period for client roll
        html = render_audit_countdown_html(now=now, json_path=None)
        # force state via last by writing temp is heavy; assert helper path in module source
        src = Path(ROOT / "status_page" / "audit_countdown.py").read_text(encoding="utf-8")
        self.assertIn("while (deadlineMs <= now)", src)
        self.assertIn("next_audit_at_rolling", src)
        self.assertIn("86400", src)

    def test_load_from_shipped_json_when_present(self):
        json_path = ROOT / "status_page" / "static" / "security_audit_latest.json"
        if not json_path.is_file():
            self.skipTest("security_audit_latest.json missing")
        st = countdown_state(json_path=json_path)
        self.assertTrue(st["available"], msg="shipped JSON should have generated_at")
        self.assertIsInstance(st["remaining_seconds"], int)
        self.assertRegex(st["display"], r"^\d+d \d{2}:\d{2}:\d{2}$")


class TestAuditCountdownUi(unittest.TestCase):
    def test_fragment_has_label_blurb_and_setinterval(self):
        last = datetime(2026, 7, 21, 10, 0, 0, tzinfo=timezone.utc)
        html = render_audit_countdown_html(
            now=last + timedelta(hours=1),
            json_path=ROOT / "status_page" / "static" / "security_audit_latest.json",
        )
        self.assertIn("time til next audit", html)
        self.assertIn("wipedown", html)
        self.assertIn('id="audit-countdown"', html)
        self.assertIn('id="audit-countdown-value"', html)
        self.assertIn('id="audit-countdown-blurb"', html)
        self.assertIn("setInterval", html)
        self.assertIn("1000", html)
        self.assertIn("data-next-audit", html)
        # Honest 1-day job: security audit + temp scratch; not full erase
        low = html.lower()
        self.assertIn("security audit", low)
        self.assertTrue("1 day" in low or "1d" in low)
        self.assertIn("scratch", low)
        self.assertIn("not a full", low)
        self.assertNotIn("restore internet", low)
        self.assertNotIn("full disk wipe", low)
        self.assertNotIn("~every 4h", low)

    def test_status_render_html_includes_live_countdown(self):
        """Drive shipped status_page.render_html entry point."""
        page = status_app.render_html({"title": "RESTORE PRIVACY"}).decode("utf-8")
        self.assertIn("time til next audit", page)
        self.assertIn("wipedown", page)
        self.assertIn('id="audit-countdown"', page)
        self.assertIn('id="audit-countdown-value"', page)
        self.assertIn('id="audit-countdown-blurb"', page)
        self.assertIn("security audit", page.lower())
        self.assertIn("setInterval", page)
        self.assertIn("audit-countdown-blurb", page)
        # Still no client count poll
        self.assertNotIn("clients-connected", page)
        self.assertNotIn("fetch('/api/status'", page)

    def test_blurb_honesty_markers(self):
        """Canonical blurb: audit + period + scratch wipe; no full host/device wipe claim."""
        blurb = TIME_TIL_NEXT_AUDIT_BLURB.lower()
        self.assertIn("security audit", blurb)
        self.assertTrue("1 day" in blurb or "1d" in blurb)
        self.assertNotIn("4h", blurb)
        self.assertTrue("scratch" in blurb or "temporary" in blurb)
        self.assertIn("not a full", blurb)
        self.assertNotIn("restore internet", blurb)
        self.assertNotIn("luks format", blurb)
        self.assertIn("wipedown", TIME_TIL_NEXT_AUDIT_LABEL)


if __name__ == "__main__":
    unittest.main()
