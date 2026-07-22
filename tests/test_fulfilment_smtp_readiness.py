"""Fulfilment SMTP readiness: real assess_fulfilment_smtp_readiness + key list."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "status_page"))


class TestFulfilmentSmtpReadiness(unittest.TestCase):
    def test_env_keys_match_reader(self):
        from payments import fulfilment_smtp_env_keys

        keys = fulfilment_smtp_env_keys()
        self.assertEqual(
            keys,
            [
                "RPT_FULFILMENT_SMTP_HOST",
                "RPT_FULFILMENT_SMTP_PORT",
                "RPT_FULFILMENT_SMTP_USER",
                "RPT_FULFILMENT_SMTP_PASSWORD",
                "RPT_FULFILMENT_FROM_EMAIL",
                "RPT_FULFILMENT_SMTP_TLS",
            ],
        )
        ry = (ROOT / "render.yaml").read_text(encoding="utf-8")
        for k in keys:
            self.assertIn(k, ry)

    def test_disabled_when_host_unset(self):
        from payments import assess_fulfilment_smtp_readiness, fulfilment_smtp_config

        with mock.patch.dict(os.environ, {}, clear=False):
            for k in (
                "RPT_FULFILMENT_SMTP_HOST",
                "RPT_FULFILMENT_SMTP_USER",
                "RPT_FULFILMENT_SMTP_PASSWORD",
            ):
                os.environ.pop(k, None)
            cfg = fulfilment_smtp_config()
            self.assertFalse(cfg["configured"])
            v = assess_fulfilment_smtp_readiness(cfg)
            self.assertEqual(v["status"], "disabled")
            self.assertFalse(v["email_flow_enabled"])
            self.assertIn("RPT_FULFILMENT_SMTP_HOST", v["missing_or_empty"])

    def test_host_only_incomplete(self):
        from payments import assess_fulfilment_smtp_readiness

        v = assess_fulfilment_smtp_readiness(
            {
                "host": "smtp.example.com",
                "port": 587,
                "user": "",
                "password": "",
                "from_addr": "noreply@restoreprivacy.online",
                "use_tls": True,
                "configured": True,
            }
        )
        self.assertEqual(v["status"], "host_only_incomplete_auth")
        self.assertFalse(v["email_flow_enabled"])
        self.assertTrue(v["code_configured_flag"])

    def test_ready_when_auth_complete(self):
        from payments import assess_fulfilment_smtp_readiness

        v = assess_fulfilment_smtp_readiness(
            {
                "host": "smtp.example.com",
                "port": 587,
                "user": "u",
                "password": "p",
                "from_addr": "noreply@restoreprivacy.online",
                "use_tls": True,
                "configured": True,
            }
        )
        self.assertEqual(v["status"], "ready_to_attempt_send")
        self.assertTrue(v["email_flow_enabled"])
        self.assertEqual(v["missing_or_empty"], [])

    def test_send_skips_without_host(self):
        from payments import send_fulfilment_email

        with mock.patch.dict(os.environ, {"RPT_FULFILMENT_SMTP_HOST": ""}, clear=False):
            os.environ.pop("RPT_FULFILMENT_SMTP_HOST", None)
            r = send_fulfilment_email(
                {
                    "to": "a@b.co",
                    "subject": "t",
                    "body": "b",
                }
            )
            self.assertTrue(r.get("ok"))
            self.assertFalse(r.get("sent"))
            self.assertTrue(r.get("skipped"))
            self.assertEqual(r.get("error"), "smtp_not_configured")

    def test_check_script_exists(self):
        script = ROOT / "scripts" / "check_render_fulfilment_smtp.ps1"
        self.assertTrue(script.is_file())
        src = script.read_text(encoding="utf-8")
        self.assertIn("RPT_FULFILMENT_SMTP_HOST", src)
        self.assertIn("RENDER_API_KEY", src)
        self.assertIn("email_flow_enabled", src)


if __name__ == "__main__":
    unittest.main()
