"""Admin UPLOADS page: Suite-only inventory, Helsinki + client push, path browse."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "status_page"))


class TestAdminUploadsPage(unittest.TestCase):
    def test_uploads_page_and_nav(self) -> None:
        from admin_panel import (
            ADMIN_UPLOADS_PATH,
            render_admin_processors_page_html,
            render_admin_uploads_page_html,
        )

        self.assertEqual(ADMIN_UPLOADS_PATH, "/admin/uploads")
        page = render_admin_uploads_page_html().decode("utf-8")
        self.assertIn('id="admin-uploads"', page)
        self.assertIn("UPLOADS", page)
        self.assertIn('id="admin-suite-push-upload"', page)
        self.assertIn('id="admin-suite-push-form"', page)
        self.assertIn("/admin/uploads/push-suite", page)
        self.assertIn('data-brand-wide="0"', page)
        self.assertIn('data-suite-only="1"', page)
        self.assertIn('id="admin-nav-uploads"', page)
        self.assertIn('href="/admin/uploads"', page)
        self.assertIn('class="sb-btn active" id="admin-nav-uploads"', page)
        # Dual push actions
        self.assertIn("Push selected packages to Helsinki", page)
        self.assertIn('id="admin-client-push-form"', page)
        self.assertIn("/admin/uploads/push-clients", page)
        self.assertIn("Push selected updates to clients", page)
        self.assertIn("CHECK BREADCRUMBS", page)
        self.assertIn('id="admin-client-push-section"', page)
        self.assertIn("client-push-pkg-checkbox", page)
        self.assertIn("Build host:", page)
        self.assertIn("Helsinki:", page)
        self.assertIn("Linux / Arch Linux", page)
        # Path browse retained
        self.assertIn('data-path-upload="1"', page)
        self.assertIn("/admin/uploads/upload-path", page)
        self.assertIn("Browse files and Upload", page)
        # Not full-brand inventory copy (sidebar may still link Node Operator)
        self.assertNotIn("full brand", page.lower())
        self.assertNotIn("Pens · Tables · Slides", page)
        self.assertIn("not listed here", page)

        proc = render_admin_processors_page_html().decode("utf-8")
        self.assertNotIn('id="admin-suite-push-upload"', proc)
        self.assertIn("admin-processors-uploads-link", proc)
        self.assertIn("/admin/uploads", proc)

    def test_uploads_inventory_is_suite_only_latest_monopin(self) -> None:
        from node.operator_admin import NodeOperatorController

        ctrl = NodeOperatorController(repo_root=ROOT)
        ver = ctrl.catalog_version_default()
        # Same path the UPLOADS card uses (brand_wide=False).
        inv = ctrl.list_local_packages(version=ver, brand_wide=False)
        self.assertTrue(inv.get("ok"), inv)
        self.assertEqual(inv.get("version"), ver)
        self.assertEqual(int(inv.get("total") or 0), 5)
        kinds = set(inv.get("kinds") or [])
        self.assertEqual(kinds, {"suite_client"})
        platforms = {p["platform"] for p in inv.get("packages") or []}
        self.assertEqual(
            platforms, {"windows", "android", "macos", "ios", "linux"}
        )
        for p in inv.get("packages") or []:
            self.assertEqual(p.get("kind"), "suite_client")
            self.assertNotIn(p.get("kind"), ("rpos", "rpos_app", "browser", "node_installer"))
            fname = str(p.get("filename") or "")
            self.assertTrue(
                fname.startswith(f"restore-privacy-client-{ver}-"),
                fname,
            )

        # Brand-wide still exists elsewhere (node operator) — not UPLOADS.
        brand = ctrl.list_local_packages(version=ver, brand_wide=True)
        self.assertTrue(brand.get("ok"), brand)
        brand_kinds = set(brand.get("kinds") or [])
        self.assertIn("suite_client", brand_kinds)

        html = __import__("admin_panel", fromlist=["render_admin_uploads_page_html"]).render_admin_uploads_page_html().decode("utf-8")
        # Suite basenames appear; brand-only kinds do not as primary rows
        for p in inv.get("packages") or []:
            if p.get("present"):
                self.assertIn(str(p.get("filename")), html)
                break
        self.assertIn(ver, html)
        self.assertIn("Restore Privacy Suite", html)
        # Brand-wide kinds should not dominate the inventory kinds line
        self.assertIn("suite_client", html)
        self.assertNotIn('data-kind="rpos"', html)
        self.assertNotIn('data-kind="browser"', html)
        self.assertNotIn('data-kind="node_installer"', html)

    def test_helsinki_selective_push_suite_only(self) -> None:
        from node.operator_admin import NodeOperatorController
        from suite_push_progress import start_push_job

        ctrl = NodeOperatorController(repo_root=ROOT)
        ver = ctrl.catalog_version_default()
        inv = ctrl.list_local_packages(version=ver, brand_wide=False)
        present = [
            str(p["filename"])
            for p in (inv.get("packages") or [])
            if p.get("present") and p.get("filename")
        ]
        if not present:
            self.skipTest("no local Suite packages present for dry-run push")
        selected = present[:2] if len(present) >= 2 else present
        unselected = [
            str(p["filename"])
            for p in (inv.get("packages") or [])
            if p.get("filename") and p["filename"] not in selected
        ]

        # Dry-run selective via controller (real path, no SSH write)
        r = ctrl.push_suite_packages(
            version=ver,
            stage=False,
            upload=True,
            dry_run=True,
            force=True,
            allow_missing=True,
            brand_wide=False,
            only_filenames=selected,
        )
        self.assertTrue(r.get("dry_run"))
        self.assertFalse(r.get("brand_wide"))
        self.assertEqual(r.get("version"), ver)
        self.assertEqual(list(r.get("only_filenames") or []), selected)
        # Inventory remains suite-only
        self.assertEqual(int((r.get("inventory") or {}).get("total") or 0), 5)
        self.assertEqual((r.get("inventory") or {}).get("kinds"), ["suite_client"])

        # Async job uses suite-only inventory
        started = start_push_job(
            ctrl,
            version=ver,
            stage=False,
            upload=True,
            dry_run=True,
            force=True,
            allow_missing=True,
            only_filenames=selected,
            brand_wide=False,
        )
        self.assertTrue(started.get("ok"), started)
        job = started.get("job") or {}
        pkgs = job.get("packages") or []
        self.assertEqual(len(pkgs), 5, "job table is suite five platforms")
        for p in pkgs:
            self.assertEqual(p.get("kind"), "suite_client")
        opts = job.get("options") or {}
        self.assertEqual(opts.get("only_filenames"), selected)
        self.assertFalse(opts.get("brand_wide"))
        # Unselected names are not in only_filenames
        for u in unselected:
            self.assertNotIn(u, opts.get("only_filenames") or [])

    def test_client_push_opt_in_only(self) -> None:
        from node.operator_admin import NodeOperatorController
        from node.update_push import (
            UpdatePushQueue,
            apply_client_update_directive,
            reset_global_update_queue_for_tests,
        )
        from suite_client_push import summarize_helsinki_suite_inventory

        reset_global_update_queue_for_tests()
        ctrl = NodeOperatorController(repo_root=ROOT)
        ctrl.updates = UpdatePushQueue()
        ver = ctrl.catalog_version_default()
        host = ctrl.suite_host_inventory(version=ver)
        present = list(host.get("present_filenames") or [])
        if not present:
            self.skipTest("no local Suite packages")
        selected = present[:2]
        # Matching Helsinki sizes so gate allows push
        hel = summarize_helsinki_suite_inventory(
            ver,
            [
                {
                    "filename": fn,
                    "bytes": host["present_sizes"][fn],
                    "present": True,
                }
                for fn in selected
            ],
        )
        r = ctrl.push_selected_suite_updates_to_clients(
            version=ver,
            only_filenames=selected,
            url="https://restoreprivacy.online/#downloads",
            message="",
            require_host_helsinki_match=True,
            host=host,
            helsinki=hel,
        )
        self.assertTrue(r.get("ok"), r)
        self.assertTrue(r.get("opt_in_only"))
        self.assertFalse(r.get("force_install"))
        self.assertEqual(r.get("client_gate"), "CHECK BREADCRUMBS")
        self.assertEqual(r.get("version"), ver)
        self.assertEqual(r.get("only_filenames"), selected)
        directive = r.get("directive") or {}
        self.assertEqual(directive.get("version"), ver)
        self.assertIn("CHECK BREADCRUMBS", r.get("message") or "")
        self.assertNotIn("force-install", (r.get("message") or "").lower())

        pulled = ctrl.client_pull_updates("test-client-1")
        self.assertGreaterEqual(len(pulled), 1)
        applied = apply_client_update_directive(pulled[0])
        self.assertTrue(applied.get("ok"))
        store = applied.get("store") or {}
        self.assertEqual(store.get("pending_update_version"), ver)
        self.assertIn("restoreprivacy.online", store.get("pending_update_url") or "")

        from client.breadcrumbs_check import (
            KEY_CHECK_BREADCRUMBS,
            apply_breadcrumbs_update,
        )

        man = {
            "schema": "rpt.breadcrumbs.v1",
            "monopin": ver,
            "update": directive,
        }
        skipped = apply_breadcrumbs_update(
            settings={KEY_CHECK_BREADCRUMBS: False},
            product_version="0.0.1",
            manifest=man,
        )
        self.assertTrue(skipped.get("skipped") or skipped.get("ok"))
        if skipped.get("skipped"):
            self.assertIn("off", (skipped.get("reason") or "").lower())

    def test_path_browse_form_and_dry_run_handler(self) -> None:
        from admin_panel import render_admin_uploads_page_html
        from node.operator_admin import NodeOperatorController

        page = render_admin_uploads_page_html().decode("utf-8")
        self.assertIn('id="admin-path-upload-form"', page)
        self.assertIn('data-path-upload="1"', page)
        self.assertIn('action="/admin/uploads/upload-path"', page)
        self.assertIn('id="admin-path-upload-input"', page)
        self.assertIn('name="path"', page)

        ctrl = NodeOperatorController(repo_root=ROOT)
        ver = ctrl.catalog_version_default()
        # Dry-run path upload with a known present suite file if any
        inv = ctrl.list_local_packages(version=ver, brand_wide=False)
        present = next(
            (p for p in inv.get("packages") or [] if p.get("present") and p.get("path")),
            None,
        )
        if not present:
            self.skipTest("no present suite package for path dry-run")
        r = ctrl.upload_package_by_path(
            present["path"],
            stage=True,
            upload=True,
            dry_run=True,
            force=False,
        )
        self.assertTrue(r.get("ok") or r.get("dry_run") is not None, r)
        # dry-run should not require live SSH success as hard fail when dry
        self.assertTrue(r.get("dry_run") or r.get("ok"), r)

    def test_app_registers_uploads_routes(self) -> None:
        app_src = (ROOT / "status_page" / "app.py").read_text(encoding="utf-8")
        self.assertIn('"/admin/uploads"', app_src)
        self.assertIn("/admin/uploads/push-suite", app_src)
        self.assertIn("/admin/uploads/push-suite/status", app_src)
        self.assertIn("/admin/uploads/upload-path", app_src)
        self.assertIn("/admin/uploads/push-clients", app_src)
        self.assertIn("render_admin_uploads_page_html", app_src)
        self.assertIn("push_selected_suite_updates_to_clients", app_src)
        self.assertIn("brand_wide=False", app_src)


if __name__ == "__main__":
    unittest.main()
