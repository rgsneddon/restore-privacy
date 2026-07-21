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
    def test_readme_has_vibe_coding_tagline_not_wireguard_sentence(self):
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        # Removed OBJECTIVE sentence
        self.assertNotIn(
            "Not WireGuard, OpenVPN, IPsec, or any other pre-existing VPN product.",
            text,
        )
        # Verbatim must-haves from OBJECTIVE
        self.assertIn("vibe coding", text)
        self.assertIn("SuperGrok Heavy Grok-Build", text)
        self.assertIn("Russell G Sneddon", text)
        self.assertIn("Regular audits are scripted to run intermittently", text)
        self.assertIn(
            "Restore Privacy is built from the ground up using unashamed vibe coding methods",
            text,
        )
        # Public mirror stays in sync when present
        pub = ROOT / "status_page" / "public" / "README.md"
        if pub.is_file():
            pub_text = pub.read_text(encoding="utf-8")
            self.assertIn("SuperGrok Heavy Grok-Build", pub_text)
            self.assertNotIn(
                "Not WireGuard, OpenVPN, IPsec, or any other pre-existing VPN product.",
                pub_text,
            )


class TestAuditCountdownMath(unittest.TestCase):
    def test_period_is_four_hours(self):
        self.assertEqual(AUDIT_PERIOD_SECONDS, 4 * 3600)
        self.assertEqual(AUDIT_PERIOD, timedelta(hours=4))

    def test_parse_and_remaining_from_known_timestamp(self):
        last = parse_audit_generated_at("2026-07-21T10:00:00Z")
        self.assertIsNotNone(last)
        assert last is not None
        nxt = next_audit_at(last)
        self.assertEqual(
            nxt,
            datetime(2026, 7, 21, 14, 0, 0, tzinfo=timezone.utc),
        )
        # Exactly 1h before deadline
        now = datetime(2026, 7, 21, 13, 0, 0, tzinfo=timezone.utc)
        rem = remaining_seconds_until(nxt, now=now)
        self.assertEqual(rem, 3600)
        self.assertEqual(format_countdown(rem), "01:00:00")
        # Overdue → 0
        late = datetime(2026, 7, 21, 15, 0, 0, tzinfo=timezone.utc)
        self.assertEqual(remaining_seconds_until(nxt, now=late), 0)
        self.assertEqual(format_countdown(0), "00:00:00")

    def test_countdown_state_drives_real_helper(self):
        last = datetime(2026, 7, 21, 10, 47, 19, tzinfo=timezone.utc)
        now = last + timedelta(hours=1, minutes=15, seconds=5)
        st = countdown_state(now=now, last_generated_at=last)
        self.assertTrue(st["available"])
        self.assertEqual(st["label"], TIME_TIL_NEXT_AUDIT_LABEL)
        self.assertEqual(st["label"], "time til next audit")
        self.assertEqual(st["period_seconds"], AUDIT_PERIOD_SECONDS)
        # 4h - 1h15m5s = 2h44m55s = 9895s
        self.assertEqual(st["remaining_seconds"], 2 * 3600 + 44 * 60 + 55)
        self.assertEqual(st["display"], format_countdown(st["remaining_seconds"]))
        self.assertEqual(st["next_audit_at"], "2026-07-21T14:47:19Z")

    def test_load_from_shipped_json_when_present(self):
        json_path = ROOT / "status_page" / "static" / "security_audit_latest.json"
        if not json_path.is_file():
            self.skipTest("security_audit_latest.json missing")
        st = countdown_state(json_path=json_path)
        self.assertTrue(st["available"], msg="shipped JSON should have generated_at")
        self.assertIsInstance(st["remaining_seconds"], int)
        self.assertRegex(st["display"], r"^\d{2,}:\d{2}:\d{2}$")


class TestAuditCountdownUi(unittest.TestCase):
    def test_fragment_has_label_and_setinterval(self):
        last = datetime(2026, 7, 21, 10, 0, 0, tzinfo=timezone.utc)
        # Inject via temporary json is overkill — use render with mocked load
        html = render_audit_countdown_html(
            now=last + timedelta(hours=1),
            json_path=ROOT / "status_page" / "static" / "security_audit_latest.json",
        )
        self.assertIn("time til next audit", html)
        self.assertIn('id="audit-countdown"', html)
        self.assertIn('id="audit-countdown-value"', html)
        self.assertIn("setInterval", html)
        self.assertIn("1000", html)
        self.assertIn("data-next-audit", html)

    def test_status_render_html_includes_live_countdown(self):
        """Drive shipped status_page.render_html entry point."""
        page = status_app.render_html({"title": "RESTORE PRIVACY"}).decode("utf-8")
        self.assertIn("time til next audit", page)
        self.assertIn('id="audit-countdown"', page)
        self.assertIn('id="audit-countdown-value"', page)
        self.assertIn("setInterval", page)
        # Still no client count poll
        self.assertNotIn("clients-connected", page)
        self.assertNotIn("fetch('/api/status'", page)


if __name__ == "__main__":
    unittest.main()
