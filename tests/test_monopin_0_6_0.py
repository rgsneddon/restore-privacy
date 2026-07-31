"""Historical monopin 0.6.0 handoff notes + update-push mechanics.

Current Suite catalog monopin is **1.0.0** (see ``tests/test_suite_monopin_1_0_0.py``
and ``client/VERSION``). This module only covers archival 0.6.0 packaging notes
and that residual UPDATE_PUSH still delivers an arbitrary target version string
(including historical 0.6.0) — it must **not** re-pin the live catalog to 0.6.0.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "status_page"))

PLATFORMS = ("windows", "android", "macos", "ios", "linux")


class TestMonopin060Pins(unittest.TestCase):
    def test_live_catalog_is_not_0_6_0_anymore(self) -> None:
        """Archive 0.6.0 packaging must not redefine the live Suite catalog pin."""
        ver = (ROOT / "client" / "VERSION").read_text(encoding="utf-8").strip()
        self.assertNotEqual(ver, "0.6.0")
        self.assertEqual(ver, "1.0.0")
        from downloads import RELEASE_VERSION

        self.assertEqual(RELEASE_VERSION, "1.0.0")
        self.assertNotEqual(RELEASE_VERSION, "0.6.0")

    def test_release_notes_and_build_script_list_all_platforms(self) -> None:
        notes = (ROOT / "scripts" / "RELEASE_NOTES_0.6.0.md").read_text(
            encoding="utf-8"
        )
        script = (ROOT / "scripts" / "build_release_0.6.0.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("0.6.0", notes)
        self.assertIn('VERSION = "0.6.0"', script)
        for plat in PLATFORMS:
            self.assertIn(plat, notes.lower())
            # basename pattern
            self.assertIn(f"restore-privacy-client-0.6.0-", notes)
        self.assertIn("windows-x64-setup.exe", notes)
        self.assertIn("android.apk", notes)
        self.assertIn("macos.zip", notes)
        self.assertIn("ios.zip", notes)
        self.assertIn("linux-x64.tar.gz", notes)
        self.assertTrue((ROOT / "client_app" / "APPLE_HANDOFF_0.6.0.md").is_file())
        self.assertTrue(
            (ROOT / "client" / "windows" / "WINDOWS_HANDOFF_0.6.0.md").is_file()
        )
        # Build script names all five package constants
        for name in (
            "WINDOWS_EXE_NAME",
            "ANDROID_APK_NAME",
            "MACOS_ZIP_NAME",
            "IOS_ZIP_NAME",
            "LINUX_TGZ_NAME",
        ):
            self.assertIn(name, script)


class TestUpdatePush060(unittest.TestCase):
    def test_operator_push_0_6_0_client_receive_apply(self) -> None:
        from client.update_receive import (
            apply_client_update_directive,
            handle_residual_update_frame,
        )
        from node.protocol import MsgType, pack_update_push, peek_type
        from node.update_push import (
            client_receive_update_directives,
            operator_push_update,
            pack_update_push_json,
            reset_global_update_queue_for_tests,
        )

        q = reset_global_update_queue_for_tests()
        url = "https://restoreprivacy.online/"
        r = operator_push_update(
            version="0.6.0",
            url=url,
            message="Upgrade to monopin 0.6.0",
            connected_client_ids=["client-a", "client-b"],
            queue=q,
        )
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["directive"]["version"], "0.6.0")
        self.assertEqual(set(r["delivered_to"]), {"client-a", "client-b"})

        pending = client_receive_update_directives("client-a", queue=q)
        self.assertTrue(any(p.get("version") == "0.6.0" for p in pending))
        applied = apply_client_update_directive(
            next(p for p in pending if p.get("version") == "0.6.0")
        )
        self.assertTrue(applied["ok"], applied)
        self.assertEqual(applied["store"]["pending_update_version"], "0.6.0")
        self.assertEqual(applied["store"]["pending_update_url"], url)

        frame = pack_update_push(
            b"\x06" * 8,
            pack_update_push_json(
                {
                    "version": "0.6.0",
                    "url": url,
                    "message": "Upgrade to monopin 0.6.0",
                }
            ),
        )
        self.assertEqual(peek_type(frame), MsgType.UPDATE_PUSH)
        got = handle_residual_update_frame(frame)
        self.assertTrue(got["ok"], got)
        self.assertEqual(got["store"]["pending_update_version"], "0.6.0")


if __name__ == "__main__":
    unittest.main()
