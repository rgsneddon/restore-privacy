"""Audit countdown last-run stays fresh: pure helpers + client refresh wiring."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "status_page"))
STATIC = ROOT / "status_page" / "static"
HELPERS_JS = STATIC / "audit_last_run_helpers.js"


class TestAuditLastRunPythonHelpers(unittest.TestCase):
    def test_load_format_and_countdown_period(self) -> None:
        from audit_countdown import (
            AUDIT_PERIOD_SECONDS,
            countdown_state,
            format_last_audit_run_display,
            load_last_audit_generated_at,
            next_audit_at_rolling,
            parse_audit_generated_at,
        )

        self.assertEqual(AUDIT_PERIOD_SECONDS, 86400)
        last = parse_audit_generated_at("2026-07-30T22:38:09Z")
        self.assertIsNotNone(last)
        assert last is not None
        now = last + timedelta(hours=2)
        st = countdown_state(now=now, last_generated_at=last)
        self.assertTrue(st["available"])
        self.assertEqual(st["last_generated_at"], "2026-07-30T22:38:09Z")
        self.assertEqual(
            format_last_audit_run_display(st["last_generated_at"]),
            "2026-07-30 22:38:09 UTC",
        )
        # Rolling past many periods still uses last from source
        now2 = last + timedelta(days=5, hours=1)
        nxt = next_audit_at_rolling(last, now=now2)
        self.assertGreater(nxt, now2)
        self.assertEqual(
            countdown_state(now=now2, last_generated_at=last)["last_generated_at"],
            "2026-07-30T22:38:09Z",
        )

        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "security_audit_latest.json"
            p.write_text(
                json.dumps({"generated_at": "2026-08-01T08:00:00Z"}),
                encoding="utf-8",
            )
            loaded = load_last_audit_generated_at(p)
            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(
                loaded.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "2026-08-01T08:00:00Z",
            )


class TestAuditLastRunJsHelpers(unittest.TestCase):
    def test_pure_js_helpers_via_node(self) -> None:
        self.assertTrue(HELPERS_JS.is_file(), HELPERS_JS)
        script = f"""
const h = require({json.dumps(str(HELPERS_JS))});
function assert(cond, msg) {{ if (!cond) {{ console.error(msg); process.exit(1); }} }}
assert(h.formatLastAuditRunDisplay("2026-07-30T22:38:09Z") === "2026-07-30 22:38:09 UTC", "fmt");
assert(h.formatLastAuditRunDisplay("") === "not available", "empty");
assert(h.generatedAtFromPayload({{ generated_at: "2026-08-01T01:02:03Z" }}) === "2026-08-01T01:02:03Z", "gen");
assert(h.generatedAtFromPayload({{}}) === "", "no gen");
assert(h.shouldUpdateLastRun("2026-07-30T22:38:09Z", "2026-08-01T01:02:03Z") === true, "update");
assert(h.shouldUpdateLastRun("2026-08-01T01:02:03Z", "2026-08-01T01:02:03Z") === false, "same");
assert(h.shouldUpdateLastRun("2026-08-01T01:02:03Z", "") === false, "no invent");
const url = h.lastRunJsonUrl(12345);
assert(url.indexOf("/static/security_audit_latest.json") === 0, "url path");
assert(url.indexOf("t=12345") > 0, "cache bust");
// Mock DOM element for apply
const el = {{
  datetime: "2026-07-30T22:38:09Z",
  text: "old",
  getAttribute(k) {{ return k === "datetime" ? this.datetime : null; }},
  setAttribute(k, v) {{ if (k === "datetime") this.datetime = v; }},
  set textContent(v) {{ this.text = v; }},
  get textContent() {{ return this.text; }},
}};
assert(h.applyLastRunToTimeElement(el, "2026-08-01T01:02:03Z") === true, "applied");
assert(el.datetime === "2026-08-01T01:02:03Z", "dt");
assert(el.text === "2026-08-01 01:02:03 UTC", "text");
assert(h.applyLastRunToTimeElement(el, "2026-08-01T01:02:03Z") === false, "no-op same");
console.log("JS_HELPERS_OK");
"""
        try:
            proc = subprocess.run(
                ["node", "-e", script],
                capture_output=True,
                text=True,
                timeout=15,
                cwd=str(ROOT),
            )
        except FileNotFoundError:
            self.skipTest("node not available")
        self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
        self.assertIn("JS_HELPERS_OK", proc.stdout)

    def test_tickers_wire_refresh_and_helpers_script(self) -> None:
        from audit_countdown import (
            render_audit_countdown_html,
            render_audit_page_ticker_html,
        )

        home = render_audit_countdown_html()
        page = render_audit_page_ticker_html()
        for html in (home, page):
            self.assertIn("/static/audit_last_run_helpers.js", html)
        self.assertIn('id="audit-last-run-time"', home)
        self.assertIn('id="audit-page-last-run-time"', page)
        self.assertIn("data-last-audit", home)

        helpers_js = HELPERS_JS.read_text(encoding="utf-8")
        self.assertIn("security_audit_latest.json", helpers_js)
        self.assertIn("lastRunJsonUrl", helpers_js)
        cd_js = (STATIC / "audit_countdown.js").read_text(encoding="utf-8")
        pg_js = (STATIC / "audit_page_ticker.js").read_text(encoding="utf-8")
        for js in (cd_js, pg_js):
            self.assertIn("refreshLastRun", js)
            self.assertIn("lastRunJsonUrl", js)
            self.assertIn("RptAuditLastRun", js)
            self.assertIn("rolled", js)
            self.assertIn("pollEveryTicks", js)
            # Must not invent last-run from period alone
            self.assertNotIn("new Date().toISOString()", js)

        # Static route registered
        app_src = (ROOT / "status_page" / "app.py").read_text(encoding="utf-8")
        self.assertIn("audit_last_run_helpers.js", app_src)


class TestAuditLastRunRefreshLogic(unittest.TestCase):
    """Simulated roll-over + payload change (no browser)."""

    def test_update_object_adopts_new_generated_at(self) -> None:
        # Mirror pure JS decision path in Python for the roll-over scenario
        from audit_countdown import format_last_audit_run_display

        prev = "2026-07-30T22:38:09Z"
        payload_new = {"generated_at": "2026-08-01T06:00:00Z"}
        payload_same = {"generated_at": prev}
        payload_empty: dict = {}

        def decide(prev_iso: str, data: dict) -> str | None:
            nxt = str(data.get("generated_at") or "").strip()
            if not nxt or nxt == prev_iso:
                return None
            return nxt

        self.assertEqual(
            decide(prev, payload_new),
            "2026-08-01T06:00:00Z",
        )
        self.assertIsNone(decide(prev, payload_same))
        self.assertIsNone(decide(prev, payload_empty))
        self.assertEqual(
            format_last_audit_run_display("2026-08-01T06:00:00Z"),
            "2026-08-01 06:00:00 UTC",
        )


if __name__ == "__main__":
    unittest.main()
