"""Anonymous registration: no admin verification on product device admission."""

from __future__ import annotations

import inspect
import sys
import tempfile
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from client.registration_copy import (  # noqa: E402
    ANON_REGISTRATION_MARKERS,
    ANON_REGISTRATION_SUMMARY,
    NO_ADMIN_VERIFICATION_MARKER,
    OS_PRIVILEGE_HONESTY,
    registration_requires_admin_verification,
    registration_requires_email_or_phone,
)
from client.secrets_loader import (  # noqa: E402
    generate_and_persist_device_key,
    ensure_device_admission_key,
)


class TestAnonRegistrationPolicy(unittest.TestCase):
    def test_registration_not_admin_verified(self):
        self.assertFalse(registration_requires_admin_verification())
        self.assertFalse(registration_requires_email_or_phone())

    def test_device_key_bootstrap_no_admin_args(self):
        """generate_and_persist_device_key / ensure take no operator-approval params."""
        sig = inspect.signature(generate_and_persist_device_key)
        for name in sig.parameters:
            self.assertNotIn(
                name.lower(),
                {
                    "admin",
                    "operator",
                    "approval",
                    "email",
                    "phone",
                    "captcha",
                    "allowlist",
                    "allow_list",
                },
            )
        sig2 = inspect.signature(ensure_device_admission_key)
        for name in sig2.parameters:
            low = name.lower()
            self.assertNotIn(low, {"admin_token", "operator_approval", "email", "phone"})

    def test_generate_device_key_local_only(self):
        with tempfile.TemporaryDirectory() as td:
            dest = Path(td)
            # Node pub not required for raw keygen helper
            priv = generate_and_persist_device_key(dest)
            self.assertTrue((dest / "client_ed25519.priv").is_file())
            self.assertTrue((dest / "client_ed25519.pub").is_file())
            self.assertIsNotNone(priv)

    def test_copy_mentions_no_admin_verification(self):
        blob = ANON_REGISTRATION_SUMMARY + " " + OS_PRIVILEGE_HONESTY
        self.assertIn(NO_ADMIN_VERIFICATION_MARKER, ANON_REGISTRATION_SUMMARY)
        for m in ANON_REGISTRATION_MARKERS:
            self.assertIn(m, blob)
        # OS privilege honesty must not collapse into "no admin needed for residual"
        self.assertIn("Administrator", OS_PRIVILEGE_HONESTY)
        self.assertIn("not operator approval", OS_PRIVILEGE_HONESTY.lower())


class TestAnonRegistrationUiWiring(unittest.TestCase):
    def test_windows_ui_has_anon_copy(self):
        src = (ROOT / "client" / "windows" / "app.py").read_text(encoding="utf-8")
        copy = (ROOT / "client" / "registration_copy.py").read_text(encoding="utf-8")
        combined = src + copy
        self.assertIn("ANON_REGISTRATION", src)
        self.assertIn(NO_ADMIN_VERIFICATION_MARKER, combined)
        self.assertIn("OS_PRIVILEGE_HONESTY", src)
        # Must not claim residual works without elevation as a universal fact
        self.assertNotIn("residual works without Administrator", combined.lower())

    def test_flutter_ui_has_anon_copy(self):
        main = (ROOT / "client_app" / "lib" / "main.dart").read_text(encoding="utf-8")
        reg = (ROOT / "client_app" / "lib" / "registration_copy.dart").read_text(
            encoding="utf-8"
        )
        combined = main + reg
        self.assertIn("no admin/operator verification", combined)
        self.assertIn("Anonymous", combined)
        self.assertIn("Administrator", reg)


if __name__ == "__main__":
    unittest.main()
