#!/usr/bin/env python3
"""Admin Push Suite packages must not leave present rows as 'skipped'.

Covers:
  - _finish_job never auto-marks pending as skipped on success
  - start_push_job with force=True, allow_missing=False ends present rows as done
  - admin form defaults force on / allow_missing off
  - progress_cb is invoked one file at a time for each inventory filename
"""

from __future__ import annotations

import sys
import tempfile
import time
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "status_page"
for p in (str(STATUS), str(ROOT / "node"), str(ROOT / "scripts")):
    if p not in sys.path:
        sys.path.insert(0, p)


class TestFinishJobNoAutoSkip(unittest.TestCase):
    def test_finish_job_success_marks_pending_as_error_not_skipped(self) -> None:
        from suite_push_progress import (
            STATUS_DONE,
            STATUS_ERROR,
            STATUS_PENDING,
            STATUS_SKIPPED,
            _finish_job,
            create_job_from_inventory,
            job_snapshot,
            progress_transition,
        )

        inv = {
            "packages": [
                {"filename": "a.zip", "kind": "suite_client", "present": True},
                {"filename": "b.zip", "kind": "rpos", "present": True},
            ]
        }
        jid = create_job_from_inventory(inv)
        # Simulate only first file processed
        from suite_push_progress import _update_file

        _update_file(jid, "a.zip", STATUS_DONE, 100)
        _finish_job(jid, ok=True, message="partial")
        snap = job_snapshot(jid)
        assert snap is not None
        by_name = {p["filename"]: p for p in snap["packages"]}
        self.assertEqual(by_name["a.zip"]["status"], STATUS_DONE)
        self.assertNotEqual(by_name["b.zip"]["status"], STATUS_SKIPPED)
        self.assertEqual(by_name["b.zip"]["status"], STATUS_ERROR)
        self.assertFalse(
            any(p.get("status") == STATUS_SKIPPED for p in snap["packages"]),
            snap["packages"],
        )

    def test_finish_job_failure_marks_pending_as_error_not_skipped(self) -> None:
        from suite_push_progress import (
            STATUS_ERROR,
            STATUS_PENDING,
            STATUS_SKIPPED,
            _finish_job,
            create_job_from_inventory,
            job_snapshot,
        )

        inv = {
            "packages": [
                {"filename": "x.zip", "kind": "suite_client", "present": True},
            ]
        }
        jid = create_job_from_inventory(inv)
        _finish_job(jid, ok=False, error="boom")
        snap = job_snapshot(jid)
        assert snap is not None
        self.assertEqual(snap["packages"][0]["status"], STATUS_ERROR)
        self.assertNotEqual(snap["packages"][0]["status"], STATUS_SKIPPED)


class TestAdminPushDefaults(unittest.TestCase):
    def test_form_force_checked_allow_missing_unchecked(self) -> None:
        from admin_panel import render_admin_suite_push_upload_html

        frag = render_admin_suite_push_upload_html()
        # Force re-upload default ON
        self.assertIn('id="admin-suite-push-force"', frag)
        self.assertRegex(
            frag,
            r'name="force"[^>]*checked|checked[^>]*name="force"|'
            r'name="force" value="1" checked',
        )
        # Allow missing default OFF (no checked on that input)
        self.assertIn('id="admin-suite-push-allow-missing"', frag)
        # Extract the allow_missing checkbox line
        for line in frag.splitlines():
            if "admin-suite-push-allow-missing" in line or (
                'name="allow_missing"' in line and "suite-push" in frag
            ):
                if 'name="allow_missing"' in line:
                    self.assertNotIn("checked", line)
                    break
        else:
            # Fallback: the allow_missing input must not have checked attribute
            import re

            m = re.search(
                r'<input[^>]*name="allow_missing"[^>]*>',
                frag,
            )
            self.assertIsNotNone(m, "allow_missing input missing")
            assert m is not None
            self.assertNotIn("checked", m.group(0))

        # Force input must have checked
        import re

        m = re.search(r'<input[^>]*name="force"[^>]*>', frag)
        self.assertIsNotNone(m)
        assert m is not None
        self.assertIn("checked", m.group(0))

    def test_start_push_job_defaults_force_true_allow_missing_false(self) -> None:
        import inspect

        from suite_push_progress import start_push_job

        sig = inspect.signature(start_push_job)
        self.assertIs(sig.parameters["force"].default, True)
        self.assertIs(sig.parameters["allow_missing"].default, False)


class _FakeController:
    """Mock NodeOperatorController for admin push job tests (no real SSH)."""

    def __init__(self, packages: list[dict[str, Any]]) -> None:
        self._packages = packages
        self.last_kwargs: dict[str, Any] = {}
        self.cb_events: list[tuple[str, str, int]] = []

    def catalog_version_default(self) -> str:
        return "9.9.9"

    def list_local_packages(
        self, *, version: str | None = None, brand_wide: bool = True
    ) -> dict[str, Any]:
        return {
            "ok": True,
            "version": version or "9.9.9",
            "packages": list(self._packages),
            "present_count": sum(1 for p in self._packages if p.get("present")),
            "total": len(self._packages),
            "kinds": sorted({p.get("kind") for p in self._packages}),
        }

    def ssh_upload_access_preflight(self, *, upload: bool = True) -> dict[str, Any]:
        return {"ok": True, "missing_ssh_keys": False, "key_path": "/tmp/fake-key"}

    def push_suite_packages(self, **kwargs: Any) -> dict[str, Any]:
        self.last_kwargs = dict(kwargs)
        cb = kwargs.get("progress_cb")
        # Simulate one-at-a-time upload for every inventory filename
        for p in self._packages:
            fname = p["filename"]
            if cb:
                cb(fname, "uploading", 10)
                self.cb_events.append((fname, "uploading", 10))
                cb(fname, "done", 100)
                self.cb_events.append((fname, "done", 100))
        return {
            "ok": True,
            "suite": "Restore Privacy Suite v9.9.9",
            "error": "",
            "force": kwargs.get("force"),
            "allow_missing": kwargs.get("allow_missing"),
        }


class TestStartPushJobNoSkipped(unittest.TestCase):
    def test_all_present_packages_end_done_not_skipped(self) -> None:
        from suite_push_progress import job_snapshot, start_push_job

        pkgs = [
            {
                "filename": "restore-privacy-client-9.9.9-linux-x64.tar.gz",
                "kind": "suite_client",
                "platform": "linux",
                "product": "Suite",
                "present": True,
                "staged": True,
                "size": 2_000_000,
            },
            {
                "filename": "rpos-0.1.0-macos.zip",
                "kind": "rpos",
                "platform": "macos",
                "product": "rpOS",
                "present": True,
                "staged": True,
                "size": 40_000,
            },
            {
                "filename": "pens-0.1.0-installer.zip",
                "kind": "rpos_app",
                "platform": "pens",
                "product": "Pens",
                "present": True,
                "staged": True,
                "size": 12_000,
            },
        ]
        ctrl = _FakeController(pkgs)
        started = start_push_job(
            ctrl,
            version="9.9.9",
            stage=True,
            upload=True,
            dry_run=False,
            force=True,
            allow_missing=False,
        )
        self.assertTrue(started.get("ok"), started)
        jid = started["job_id"]
        deadline = time.time() + 10
        snap = None
        while time.time() < deadline:
            snap = job_snapshot(jid)
            if snap and snap.get("state") in ("complete", "failed"):
                break
            time.sleep(0.02)
        self.assertIsNotNone(snap)
        assert snap is not None
        self.assertEqual(snap.get("state"), "complete", snap)
        self.assertTrue(snap.get("ok"), snap)
        statuses = [p.get("status") for p in snap.get("packages") or []]
        self.assertEqual(statuses, ["done", "done", "done"], snap.get("packages"))
        self.assertFalse(
            any(s == "skipped" for s in statuses),
            f"present packages must not be skipped: {statuses}",
        )
        # force / allow_missing defaults applied to controller
        self.assertIs(ctrl.last_kwargs.get("force"), True)
        self.assertIs(ctrl.last_kwargs.get("allow_missing"), False)
        # One-at-a-time: uploading then done for each file in order
        events = ctrl.cb_events
        self.assertEqual(len(events), 6)  # 3 files × (uploading, done)
        self.assertEqual(events[0][0], pkgs[0]["filename"])
        self.assertEqual(events[0][1], "uploading")
        self.assertEqual(events[1][1], "done")
        self.assertEqual(events[2][0], pkgs[1]["filename"])

    def test_progress_cb_order_is_sequential_per_file(self) -> None:
        from suite_push_progress import job_snapshot, start_push_job

        pkgs = [
            {"filename": f"pkg-{i}.zip", "kind": "rpos", "present": True}
            for i in range(5)
        ]
        ctrl = _FakeController(pkgs)
        started = start_push_job(
            ctrl,
            force=True,
            allow_missing=False,
            stage=True,
            upload=True,
            dry_run=False,
        )
        self.assertTrue(started.get("ok"))
        jid = started["job_id"]
        deadline = time.time() + 10
        while time.time() < deadline:
            snap = job_snapshot(jid)
            if snap and snap.get("state") in ("complete", "failed"):
                break
            time.sleep(0.02)
        # Never interleave: each file fully done before next starts
        seq = [(e[0], e[1]) for e in ctrl.cb_events]
        expected: list[tuple[str, str]] = []
        for p in pkgs:
            expected.append((p["filename"], "uploading"))
            expected.append((p["filename"], "done"))
        self.assertEqual(seq, expected)


class TestUploadBrandProgressOneAtATime(unittest.TestCase):
    def test_dry_run_progress_cb_covers_all_ready_files(self) -> None:
        import host_paid_assets_vps as hp

        events: list[tuple[str, str, int]] = []

        def cb(filename: str, status: str, progress: int) -> None:
            events.append((filename, status, progress))

        with tempfile.TemporaryDirectory() as td:
            assets = Path(td) / "assets" / "1.0.2"
            assets.mkdir(parents=True)
            names = [
                "restore-privacy-client-1.0.2-linux-x64.tar.gz",
                "rpos-0.1.0-macos.zip",
                "pens-0.1.0-installer.zip",
            ]
            for n in names:
                size = 1_000_001 if "client" in n else 2_000
                (assets / n).write_bytes(b"x" * size)

            fake_inv = {
                "suite_version": "1.0.2",
                "total": len(names),
                "packages": [
                    {
                        "filename": n,
                        "kind": "suite_client" if "client" in n else "rpos",
                        "platform": "linux",
                        "min_bytes": 1_000 if "client" not in n else 1_000_000,
                    }
                    for n in names
                ],
            }

            def _fake_inv(**_kwargs: Any) -> dict[str, Any]:
                return fake_inv

            # Function imports inventory_with_presence from brand_package_inventory
            with mock.patch.object(hp, "STATUS", Path(td)), mock.patch(
                "brand_package_inventory.inventory_with_presence",
                side_effect=_fake_inv,
            ):
                code = hp.upload_brand_packages(
                    version="1.0.2",
                    dry_run=True,
                    force=True,
                    allow_missing=False,
                    progress_cb=cb,
                )
        self.assertEqual(code, 0, events)
        statuses = [e[1] for e in events]
        self.assertNotIn("skipped", statuses, events)
        done_names = [e[0] for e in events if e[1] == "done"]
        self.assertEqual(done_names, names, events)
        for i, n in enumerate(names):
            self.assertEqual(events[i * 2], (n, "uploading", 50))
            self.assertEqual(events[i * 2 + 1], (n, "done", 100))


if __name__ == "__main__":
    unittest.main()
