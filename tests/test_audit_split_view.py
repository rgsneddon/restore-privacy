"""In-client AUDIT split view: pane policy, device-only visit log, wipe gate."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from client.audit_split_view import (  # noqa: E402
    AUDIT_VISIT_MESSAGE,
    DEVICE_ONLY_RETENTION_SENTENCE,
    DEVICE_ONLY_RETENTION_TYPEWRITER,
    KIND_AUDIT_VISIT,
    LEFT_PANE_ID,
    LEFT_PANE_LABEL,
    RIGHT_PANE_ID,
    RIGHT_PANE_LABEL,
    AuditSplitState,
    append_audit_visit_to_device_log,
    apply_pane_refresh,
    build_project_files_snapshot,
    build_user_browsing_stats,
    catalog_overall_for_installed,
    evaluate_weekly_wipe_prerequisite,
    is_audit_url,
    last_wipe_at_from_state,
    pane_may_auto_update,
    render_split_markup,
    show_audit_split_window,
)
from client.connection_log import format_export, read_events  # noqa: E402


class TestAuditUrl(unittest.TestCase):
    def test_status_host_audit_md(self) -> None:
        self.assertTrue(is_audit_url("https://restoreprivacy.online/AUDIT.md"))
        self.assertTrue(is_audit_url("https://restoreprivacy.online/audit.md"))
        self.assertFalse(is_audit_url("https://restoreprivacy.online/PRIVACY_POLICY.md"))
        self.assertFalse(is_audit_url(""))


class TestPaneRefreshPolicy(unittest.TestCase):
    def test_left_dynamic_right_manual(self) -> None:
        self.assertTrue(pane_may_auto_update(LEFT_PANE_ID))
        self.assertFalse(pane_may_auto_update(RIGHT_PANE_ID))

    def test_left_updates_without_right_refresh(self) -> None:
        state = AuditSplitState()
        state = apply_pane_refresh(
            state,
            RIGHT_PANE_ID,
            {"files": ["AUDIT.md"], "stamp": "a"},
            explicit=True,
        )
        state = apply_pane_refresh(
            state,
            LEFT_PANE_ID,
            {"ping_ms": 12, "stamp": "left-1"},
            explicit=False,
        )
        self.assertEqual(state.left_generation, 1)
        self.assertEqual(state.right_generation, 1)
        self.assertEqual(state.right_snapshot["stamp"], "a")
        state = apply_pane_refresh(
            state,
            LEFT_PANE_ID,
            {"ping_ms": 18, "stamp": "left-2"},
            explicit=False,
        )
        self.assertEqual(state.left_sample["stamp"], "left-2")
        self.assertEqual(state.left_sample["ping_ms"], 18)
        self.assertEqual(state.right_snapshot["stamp"], "a")
        self.assertEqual(state.right_generation, 1)
        # Implicit right refresh must not change the snapshot
        state = apply_pane_refresh(
            state,
            RIGHT_PANE_ID,
            {"files": ["AUDIT.md"], "stamp": "b"},
            explicit=False,
        )
        self.assertEqual(state.right_snapshot["stamp"], "a")
        self.assertEqual(state.right_generation, 1)
        state = apply_pane_refresh(
            state,
            RIGHT_PANE_ID,
            {"files": ["AUDIT.md", "README.md"], "stamp": "b"},
            explicit=True,
        )
        self.assertEqual(state.right_snapshot["stamp"], "b")
        self.assertEqual(state.right_generation, 2)


class TestDeviceVisitLog(unittest.TestCase):
    def test_visit_appends_to_device_log_only(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / ".rpt_support_log.jsonl"
            ev = append_audit_visit_to_device_log(
                path=path, platform="macos", ping_ms=42.5, ts=1_800_000_000.0
            )
            self.assertEqual(ev.kind, KIND_AUDIT_VISIT)
            self.assertEqual(ev.message, AUDIT_VISIT_MESSAGE)
            self.assertTrue(ev.detail.get("device_only"))
            self.assertFalse(ev.detail.get("uploaded"))
            events = read_events(path=path)
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0].kind, KIND_AUDIT_VISIT)
            export = format_export(path=path)
            self.assertIn("AUDIT.md visit", export)
            self.assertIn("local only", export.lower())
            src = (ROOT / "client" / "audit_split_view.py").read_text(encoding="utf-8")
            self.assertNotIn("urllib.request.urlopen", src)
            self.assertIn("never uploads", src.lower())

    def test_opening_split_window_writes_visit_to_device_log(self) -> None:
        """Imperative: visiting AUDIT in-client leaves a device log row."""
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / ".rpt_support_log.jsonl"
            state = show_audit_split_window(
                None,
                connection_log_path=path,
                platform="macos",
                audit_text="# Restore Privacy — Code & Policy Audit\n",
                ping={"ok": True, "rtt_ms": 19, "host": "de"},
            )
            events = read_events(path=path)
            self.assertGreaterEqual(len(events), 1)
            self.assertEqual(events[0].kind, KIND_AUDIT_VISIT)
            self.assertEqual(state.left_sample.get("audit_visit_count"), 1)
            self.assertTrue(state.left_sample.get("device_only"))
            export = format_export(path=path)
            self.assertIn("AUDIT.md visit", export)


class TestInstalledPlatformOverall(unittest.TestCase):
    def test_single_platform_ignores_missing_others(self) -> None:
        packages = [
            {"platform": "windows", "state": "Red"},
            {"platform": "android", "state": "Green"},
            {"platform": "macos", "state": "Green"},
            {"platform": "ios", "state": "Red"},
            {"platform": "linux", "state": "Red"},
        ]
        self.assertEqual(
            catalog_overall_for_installed(packages, ["macos"]),
            "Green",
        )
        self.assertEqual(
            catalog_overall_for_installed(packages, ["windows"]),
            "Red",
        )
        self.assertEqual(catalog_overall_for_installed(packages, []), "Green")


class TestWeeklyWipePrerequisite(unittest.TestCase):
    def test_absent_fails(self) -> None:
        out = evaluate_weekly_wipe_prerequisite(last_wipe_at=None, now=1_000.0)
        self.assertFalse(out["ok"])
        self.assertIn("no weekly", out["reason"])

    def test_current_passes_stale_fails(self) -> None:
        now = 10_000.0
        ok = evaluate_weekly_wipe_prerequisite(
            last_wipe_at=now - 3600, now=now
        )
        self.assertTrue(ok["ok"])
        stale = evaluate_weekly_wipe_prerequisite(
            last_wipe_at=now - (8 * 24 * 3600), now=now
        )
        self.assertFalse(stale["ok"])
        self.assertIn("stale", stale["reason"])

    def test_state_reader(self) -> None:
        self.assertEqual(
            last_wipe_at_from_state({"last_wipe_at": 12.5}),
            12.5,
        )
        self.assertIsNone(last_wipe_at_from_state({}))


class TestSplitMarkupAndStats(unittest.TestCase):
    def test_markup_has_two_labelled_halves(self) -> None:
        left = build_user_browsing_stats(
            [{"kind": KIND_AUDIT_VISIT, "message": AUDIT_VISIT_MESSAGE}],
            {"ok": True, "rtt_ms": 33, "host": "178.105.187.178"},
            now=1.0,
            platform="macos",
        )
        right = build_project_files_snapshot(
            audit_text="# Restore Privacy — Code & Policy Audit\n",
            file_names=["AUDIT.md", "README.md"],
            catalog_overall="Green",
            catalog_version="1.2.7",
        )
        state = apply_pane_refresh(None, LEFT_PANE_ID, left, explicit=True)
        state = apply_pane_refresh(state, RIGHT_PANE_ID, right, explicit=True)
        html = render_split_markup(state)
        self.assertIn(LEFT_PANE_LABEL, html)
        self.assertIn(RIGHT_PANE_LABEL, html)
        self.assertIn('data-pane="user_browsing_stats"', html)
        self.assertIn('data-pane="project_files"', html)
        self.assertIn('data-dynamic="1"', html)
        self.assertIn("data-manual-refresh", html)
        self.assertIn(DEVICE_ONLY_RETENTION_TYPEWRITER, html)
        self.assertIn("data-typewriter-role=\"welcome\"", html)
        self.assertIn("AUDIT.md", html)
        self.assertNotIn("client_ip", html)

    def test_retention_sentence(self) -> None:
        self.assertIn("own device", DEVICE_ONLY_RETENTION_SENTENCE)
        self.assertTrue(
            DEVICE_ONLY_RETENTION_SENTENCE.endswith(
                DEVICE_ONLY_RETENTION_TYPEWRITER
            )
        )


if __name__ == "__main__":
    unittest.main()
