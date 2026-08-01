"""Full-brand Helsinki push inventory, plan, and progress UI."""

from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "status_page"))
sys.path.insert(0, str(ROOT / "scripts"))


class TestBrandWideDefault(unittest.TestCase):
    """Default list/push APIs must be brand_wide=true when flag is omitted."""

    def test_list_local_packages_default_is_brand_wide(self) -> None:
        import inspect

        from node.operator_admin import NodeOperatorController

        ctrl = NodeOperatorController(repo_root=ROOT)
        sig = inspect.signature(ctrl.list_local_packages)
        self.assertIs(sig.parameters["brand_wide"].default, True)

        # No brand_wide kwarg → full brand inventory (not suite-only five).
        inv = ctrl.list_local_packages(version=ctrl.catalog_version_default())
        self.assertTrue(inv.get("ok"), inv)
        self.assertGreaterEqual(int(inv.get("total") or 0), 5)
        kinds = set(inv.get("kinds") or [])
        self.assertIn("suite_client", kinds)
        non_suite = kinds - {"suite_client"}
        self.assertTrue(
            non_suite & {"rpos", "rpos_app", "browser", "node_installer", "node_operator"},
            kinds,
        )
        pkgs = inv.get("packages") or []
        self.assertTrue(any(p.get("kind") == "suite_client" for p in pkgs))
        self.assertTrue(
            any(p.get("kind") in ("rpos", "rpos_app") for p in pkgs),
            "default inventory must include rpOS and/or free apps",
        )

        suite_only = ctrl.list_local_packages(
            version=ctrl.catalog_version_default(), brand_wide=False
        )
        self.assertEqual(int(suite_only.get("total") or 0), 5)
        suite_kinds = set(suite_only.get("kinds") or [])
        self.assertEqual(suite_kinds, {"suite_client"})

    def test_push_suite_packages_default_is_brand_wide(self) -> None:
        import inspect

        from node.operator_admin import NodeOperatorController

        ctrl = NodeOperatorController(repo_root=ROOT)
        for name in ("push_suite_packages", "upload_catalog_packages"):
            sig = inspect.signature(getattr(ctrl, name))
            self.assertIs(
                sig.parameters["brand_wide"].default,
                True,
                f"{name} brand_wide default",
            )

        # Omit brand_wide entirely — must still be full brand push.
        r = ctrl.push_suite_packages(
            stage=True,
            upload=True,
            dry_run=True,
            allow_missing=True,
        )
        self.assertTrue(r.get("brand_wide"), r)
        self.assertGreaterEqual(int(r.get("total") or 0), 5)
        kinds = set(r.get("kinds") or [])
        if not kinds:
            kinds = {p.get("kind") for p in (r.get("packages") or [])}
        self.assertIn("suite_client", kinds)
        self.assertTrue(
            kinds & {"rpos", "rpos_app", "browser", "node_installer", "node_operator"},
            kinds,
        )
        if int(r.get("present_count") or 0) > 0:
            self.assertTrue(r.get("ok"), r.get("error"))
            self.assertEqual(r.get("upload_code"), 0)

    def test_primary_admin_paths_do_not_force_suite_only(self) -> None:
        """Helsinki push entry points must not pass brand_wide=False."""
        files = [
            ROOT / "status_page" / "admin_panel.py",
            ROOT / "status_page" / "suite_push_progress.py",
            ROOT / "status_page" / "admin_node_operator.py",
            ROOT / "status_page" / "app.py",
            ROOT / "node_operator" / "gui_html.py",
            ROOT / "node_operator" / "app.py",
        ]
        for path in files:
            src = path.read_text(encoding="utf-8")
            # No silent suite-only on shared list/push call sites.
            self.assertNotIn(
                "brand_wide=False",
                src,
                f"{path.name} must not force suite-only for primary paths",
            )
            self.assertNotIn("brand_wide=false", src.lower().replace(" ", ""))


class TestBrandPackageInventory(unittest.TestCase):
    def test_inventory_includes_suite_rpos_and_apps(self) -> None:
        from brand_package_inventory import inventory_with_presence, list_brand_installer_packages

        pure = list_brand_installer_packages()
        self.assertGreaterEqual(len(pure), 5)
        kinds = {r["kind"] for r in pure}
        self.assertIn("suite_client", kinds)
        self.assertIn("rpos", kinds)
        self.assertIn("rpos_app", kinds)
        filenames = [r["filename"] for r in pure]
        self.assertTrue(any("restore-privacy-client-" in f for f in filenames))
        self.assertTrue(any(f.startswith("rpos-") for f in filenames))
        self.assertTrue(any(f.startswith("pens-") for f in filenames))
        self.assertTrue(any(f.startswith("tables-") for f in filenames))
        self.assertTrue(any(f.startswith("slides-") for f in filenames))
        for r in pure:
            self.assertTrue(r.get("filename"))
            self.assertTrue(r.get("relative_path"))

        inv = inventory_with_presence(repo_root=ROOT)
        self.assertTrue(inv.get("ok"))
        self.assertGreaterEqual(int(inv["total"]), 5)
        self.assertGreaterEqual(int(inv["present_count"]), 1)
        # Default path (no brand_wide kwarg) matches brand inventory.
        from node.operator_admin import NodeOperatorController

        ctrl = NodeOperatorController(repo_root=ROOT)
        op = ctrl.list_local_packages()
        self.assertGreaterEqual(int(op.get("total") or 0), int(inv["total"]))
        op_kinds = set(op.get("kinds") or [])
        self.assertIn("suite_client", op_kinds)
        self.assertIn("rpos", op_kinds)
        self.assertIn("rpos_app", op_kinds)


class TestBrandPushPlan(unittest.TestCase):
    def test_push_dry_run_plan_brand_wide(self) -> None:
        from node.operator_admin import NodeOperatorController

        ctrl = NodeOperatorController(repo_root=ROOT)
        # Default brand_wide — do not pass the flag.
        r = ctrl.push_suite_packages(
            stage=True,
            upload=True,
            dry_run=True,
            allow_missing=True,
        )
        self.assertTrue(r.get("brand_wide"), r)
        inv = r.get("inventory") or {}
        pkgs = inv.get("packages") or r.get("packages") or []
        self.assertGreaterEqual(len(pkgs), 5)
        kinds = {p.get("kind") for p in pkgs}
        self.assertIn("suite_client", kinds)
        self.assertIn("rpos", kinds)
        self.assertIn("rpos_app", kinds)
        names = [p.get("filename") or "" for p in pkgs]
        self.assertTrue(any("restore-privacy-client-" in n for n in names))
        self.assertTrue(any(n.startswith("rpos-") for n in names))
        self.assertTrue(
            any(n.startswith("pens-") or n.startswith("tables-") or n.startswith("slides-") for n in names)
        )
        # Dry-run should not fail when packages present + allow_missing
        if int(r.get("present_count") or 0) > 0:
            self.assertTrue(r.get("ok"), r.get("error"))
            self.assertEqual(r.get("upload_code"), 0)


class TestSuitePushProgress(unittest.TestCase):
    def test_progress_transition_pending_uploading_done(self) -> None:
        from suite_push_progress import (
            STATUS_DONE,
            STATUS_PENDING,
            STATUS_UPLOADING,
            create_job_from_inventory,
            job_snapshot,
            progress_transition,
        )

        row = {"filename": "pens-0.1.0-installer.zip", "kind": "rpos_app"}
        a = progress_transition(row, status=STATUS_PENDING)
        self.assertEqual(a["status"], "pending")
        self.assertEqual(a["progress"], 0)
        self.assertFalse(a.get("green_done"))
        b = progress_transition(a, status=STATUS_UPLOADING, progress=40)
        self.assertEqual(b["status"], "uploading")
        self.assertEqual(b["progress"], 40)
        c = progress_transition(b, status=STATUS_DONE)
        self.assertEqual(c["status"], "done")
        self.assertEqual(c["progress"], 100)
        self.assertTrue(c.get("green_done"))
        self.assertTrue(c.get("done"))

        inv = {
            "packages": [
                {"filename": "a.zip", "kind": "suite_client", "present": True},
                {"filename": "b.zip", "kind": "rpos", "present": True},
            ]
        }
        jid = create_job_from_inventory(inv)
        snap = job_snapshot(jid)
        self.assertIsNotNone(snap)
        assert snap is not None
        self.assertEqual(snap["total"], 2)
        self.assertEqual(snap["packages"][0]["status"], "pending")

    def test_start_push_job_dry_run_completes(self) -> None:
        from node.operator_admin import NodeOperatorController
        from suite_push_progress import job_snapshot, start_push_job

        ctrl = NodeOperatorController(repo_root=ROOT)
        started = start_push_job(
            ctrl,
            stage=True,
            upload=True,
            dry_run=True,
            allow_missing=True,
        )
        self.assertTrue(started.get("ok"), started)
        jid = started["job_id"]
        # Wait for background dry-run to finish
        deadline = time.time() + 60
        snap = None
        while time.time() < deadline:
            snap = job_snapshot(jid)
            if snap and snap.get("state") in ("complete", "failed"):
                break
            time.sleep(0.05)
        self.assertIsNotNone(snap)
        assert snap is not None
        self.assertIn(snap.get("state"), ("complete", "failed"), snap)
        if snap.get("state") == "complete":
            pkgs = snap.get("packages") or []
            # At least one row should leave pending (done or skipped)
            self.assertTrue(
                any(p.get("status") in ("done", "skipped", "uploading") for p in pkgs),
                pkgs[:3],
            )


class TestAdminSuitePushMarkup(unittest.TestCase):
    def test_render_includes_brand_columns_and_js(self) -> None:
        from admin_panel import render_admin_suite_push_upload_html
        from downloads import RELEASE_VERSION

        frag = render_admin_suite_push_upload_html()
        self.assertIn('id="admin-suite-push-upload"', frag)
        self.assertIn("Push Suite packages to Helsinki", frag)
        self.assertIn('data-brand-wide="1"', frag)
        self.assertIn("admin-suite-packages-table", frag)
        self.assertIn("suite-pkg-progress-bar", frag)
        self.assertIn("suite-pkg-done", frag)
        self.assertIn("/static/admin_suite_push.js", frag)
        self.assertIn("/admin/processors/push-suite/status", frag)
        self.assertIn("<th>Kind</th>", frag)
        self.assertIn("<th>Status</th>", frag)
        self.assertIn("<th>Progress</th>", frag)
        # Brand inventory rows in markup
        self.assertIn("rpos", frag)
        self.assertTrue(
            "pens-" in frag or "tables-" in frag or "slides-" in frag,
            "expected free apps in table",
        )
        self.assertIn(f"restore-privacy-client-{RELEASE_VERSION}", frag)

    def test_js_and_routes_shipped(self) -> None:
        js = (ROOT / "status_page" / "static" / "admin_suite_push.js").read_text(
            encoding="utf-8"
        )
        self.assertIn("suite-pkg-progress-bar", js)
        self.assertIn("suite-pkg-done", js)
        self.assertIn("push-suite", js)
        self.assertIn("job_id", js)
        self.assertIn("data-status", js)
        self.assertIn("setInterval", js)  # continual refresh
        app_src = (ROOT / "status_page" / "app.py").read_text(encoding="utf-8")
        self.assertIn("/admin/processors/push-suite/status", app_src)
        self.assertIn("start_push_job", app_src)
        self.assertIn("admin_suite_push.js", app_src)
        # CSS green-done for finished rows
        from admin_panel import render_admin_suite_push_upload_html

        frag = render_admin_suite_push_upload_html()
        self.assertIn("#16a34a", frag)
        self.assertIn("suite-pkg-done", frag)
        self.assertIn('[data-status="uploading"]', frag)


if __name__ == "__main__":
    unittest.main()
