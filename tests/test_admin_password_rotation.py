"""Admin password: env RPT_ADMIN_PASSWORD wins; verify_credentials gate.

Drives shipped status_page.admin_panel helpers with a temporary env password
(CSPRNG). Does not embed production secrets.
"""

from __future__ import annotations

import os
import secrets
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "status_page"))


class TestAdminPasswordEnvOverride(unittest.TestCase):
    def test_strong_password_verify_accept_reject(self):
        import admin_panel as ap

        pw = secrets.token_urlsafe(32)
        self.assertGreaterEqual(len(pw), 40)
        with mock.patch.dict(
            os.environ,
            {
                "RPT_ADMIN_PASSWORD": pw,
                "RPT_ADMIN_USER": "admin",
            },
            clear=False,
        ):
            self.assertEqual(ap.admin_password(), pw)
            self.assertTrue(ap.verify_admin_password(pw))
            self.assertFalse(ap.verify_admin_password(pw + "nope"))
            self.assertFalse(ap.verify_admin_password(""))
            self.assertTrue(ap.admin_enabled())
            self.assertTrue(ap.verify_credentials("admin", pw))
            self.assertFalse(ap.verify_credentials("admin", "wrong"))
            self.assertFalse(ap.verify_credentials("root", pw))

    def test_env_wins_over_digest(self):
        import admin_panel as ap

        pw = secrets.token_urlsafe(24)
        with mock.patch.dict(
            os.environ,
            {"RPT_ADMIN_PASSWORD": pw},
            clear=False,
        ):
            # Even if bootstrap digest exists, wrong password fails
            self.assertFalse(ap.verify_admin_password("not-the-env-password"))
            self.assertTrue(ap.verify_admin_password(pw))

    def test_render_apply_script_present(self):
        script = ROOT / "scripts" / "set_render_admin_password.ps1"
        self.assertTrue(script.is_file())
        src = script.read_text(encoding="utf-8")
        self.assertIn("RPT_ADMIN_PASSWORD", src)
        self.assertIn("RENDER_API_KEY", src)
        self.assertIn("restore-privacy-status", src)
        # Script must not print the password value
        self.assertIn("value redacted", src.lower())


if __name__ == "__main__":
    unittest.main()
