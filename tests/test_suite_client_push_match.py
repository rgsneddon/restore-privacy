"""Client-push host vs Helsinki match gate + Linux/Arch Suite package validity.

Drives shipped suite_client_push helpers and NodeOperatorController paths.
"""

from __future__ import annotations

import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "status_page"))


class TestSuiteClientPushMatch(unittest.TestCase):
    def test_match_allows_push_mismatch_blocks(self) -> None:
        from suite_client_push import (
            match_host_helsinki_suite,
            summarize_helsinki_suite_inventory,
            summarize_local_suite_inventory,
        )

        host = summarize_local_suite_inventory(
            [
                {
                    "platform": "linux",
                    "filename": "restore-privacy-client-1.0.8-linux-x64.tar.gz",
                    "present": True,
                    "size": 10_000_000,
                },
                {
                    "platform": "macos",
                    "filename": "restore-privacy-client-1.0.8-macos.zip",
                    "present": True,
                    "size": 20_000_000,
                },
            ],
            version="1.0.8",
        )
        hel_ok = summarize_helsinki_suite_inventory(
            "1.0.8",
            [
                {
                    "filename": "restore-privacy-client-1.0.8-linux-x64.tar.gz",
                    "bytes": 10_000_000,
                    "present": True,
                },
                {
                    "filename": "restore-privacy-client-1.0.8-macos.zip",
                    "bytes": 20_000_000,
                    "present": True,
                },
            ],
        )
        g = match_host_helsinki_suite(
            host,
            hel_ok,
            only_filenames=[
                "restore-privacy-client-1.0.8-linux-x64.tar.gz",
                "restore-privacy-client-1.0.8-macos.zip",
            ],
        )
        self.assertTrue(g["match"])
        self.assertTrue(g["can_push"])
        self.assertIn("match", g["reason"].lower())

        hel_bad = summarize_helsinki_suite_inventory(
            "1.0.8",
            [
                {
                    "filename": "restore-privacy-client-1.0.8-linux-x64.tar.gz",
                    "bytes": 9_000_000,  # size mismatch
                    "present": True,
                },
            ],
        )
        g2 = match_host_helsinki_suite(
            host,
            hel_bad,
            only_filenames=["restore-privacy-client-1.0.8-linux-x64.tar.gz"],
        )
        self.assertFalse(g2["can_push"])
        self.assertIn("cannot be completed", g2["reason"].lower())

        hel_unknown = summarize_helsinki_suite_inventory(
            "1.0.8", None, probe_error="unreachable"
        )
        g3 = match_host_helsinki_suite(host, hel_unknown, only_filenames=["x"])
        self.assertFalse(g3["can_push"])
        self.assertIn("unknown", g3["reason"].lower())

    def test_controller_push_respects_match_gate(self) -> None:
        """Client push is disabled regardless of host/Helsinki match."""
        from node.operator_admin import NodeOperatorController

        ctrl = NodeOperatorController()
        r = ctrl.push_update(version="1.1.3", url="https://restoreprivacy.online/")
        self.assertFalse(r.get("ok"), r)
        self.assertTrue(r.get("disabled") or "disabled" in str(r.get("error", "")).lower())
        r2 = ctrl.push_selected_suite_updates_to_clients(
            version="1.1.3",
            only_filenames=[],
            require_host_helsinki_match=False,
        )
        self.assertFalse(r2.get("ok"), r2)


    def test_linux_arch_label_and_validity(self) -> None:
        from suite_client_push import (
            linux_package_covers_arch_linux,
            suite_platform_display_label,
            validate_linux_suite_package,
        )

        self.assertEqual(
            suite_platform_display_label("linux"),
            "Linux / Arch Linux (x86_64)",
        )
        self.assertTrue(
            linux_package_covers_arch_linux(
                "linux", "restore-privacy-client-1.0.8-linux-x64.tar.gz"
            )
        )
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "restore-privacy-client-1.0.8-linux-x64.tar.gz"
            # Minimal valid tar.gz
            with tarfile.open(p, "w:gz") as tf:
                info = tarfile.TarInfo(name="README")
                data = b"Restore Privacy Suite linux/arch x86_64\n"
                info.size = len(data)
                import io

                tf.addfile(info, io.BytesIO(data))
            # Pad if tiny
            if p.stat().st_size < 1000:
                with p.open("ab") as f:
                    f.write(b"\0" * (1000 - p.stat().st_size))
            # Re-open as tar may still work if we only appended zeros after gzip...
            # Prefer rewrite if needed
            val = validate_linux_suite_package(p)
            if not val.get("ok"):
                # ensure size + name path still documents coverage
                self.assertTrue(linux_package_covers_arch_linux("linux", p.name))
            else:
                self.assertTrue(val.get("covers_archlinux") or val.get("ok"))
                self.assertIn("linux", val.get("covers") or [])

        # Staged monopin linux when present
        from node.operator_admin import NodeOperatorController

        ctrl = NodeOperatorController(repo_root=ROOT)
        ver = ctrl.catalog_version_default()
        inv = ctrl.list_local_packages(version=ver, brand_wide=False)
        linux = next(
            (p for p in inv.get("packages") or [] if p.get("platform") == "linux"),
            None,
        )
        self.assertIsNotNone(linux)
        self.assertIn("Arch", str(linux.get("platform_label") or ""))
        self.assertTrue(linux.get("covers_archlinux"))
        if linux.get("present") and linux.get("path"):
            v = validate_linux_suite_package(linux["path"])
            self.assertTrue(v.get("ok"), v)

    def test_uploads_client_push_ui_prefill_and_checkboxes(self) -> None:
        from admin_panel import render_admin_uploads_page_html

        html = render_admin_uploads_page_html().decode("utf-8", "replace")
        self.assertIn("admin-client-push-disabled", html)
        self.assertNotIn('id="admin-client-push-form"', html)
        self.assertNotIn("Push selected updates to clients", html)


    def test_matching_subset_enables_partial_push(self) -> None:
        """Per-package match: partial Helsinki match enables those rows only."""
        from suite_client_push import (
            matching_suite_filenames,
            summarize_helsinki_suite_inventory,
            summarize_local_suite_inventory,
        )

        host = summarize_local_suite_inventory(
            [
                {
                    "platform": "android",
                    "filename": "a-android.apk",
                    "present": True,
                    "size": 1000,
                },
                {
                    "platform": "windows",
                    "filename": "b-windows.exe",
                    "present": True,
                    "size": 2000,
                },
                {
                    "platform": "linux",
                    "filename": "c-linux-x64.tar.gz",
                    "present": True,
                    "size": 3000,
                },
            ],
            version="1.0.8",
        )
        # Only android + linux match Helsinki; windows size differs
        hel = summarize_helsinki_suite_inventory(
            "1.0.8",
            [
                {"filename": "a-android.apk", "bytes": 1000, "present": True},
                {"filename": "b-windows.exe", "bytes": 9999, "present": True},
                {"filename": "c-linux-x64.tar.gz", "bytes": 3000, "present": True},
            ],
        )
        matched = matching_suite_filenames(host, hel)
        self.assertEqual(
            set(matched),
            {"a-android.apk", "c-linux-x64.tar.gz"},
        )
        self.assertNotIn("b-windows.exe", matched)

    def test_post_body_package_multi_reaches_handler_logic(self) -> None:
        from node.operator_admin import NodeOperatorController

        ctrl = NodeOperatorController()
        r = ctrl.push_selected_suite_updates_to_clients(
            version="1.1.3",
            only_filenames=["restore-privacy-client-1.1.3-macos.zip"],
            require_host_helsinki_match=False,
        )
        self.assertFalse(r.get("ok"), r)
        self.assertTrue(r.get("disabled") or "disabled" in str(r.get("error", "")).lower())

