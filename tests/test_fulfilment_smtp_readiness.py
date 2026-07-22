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
                "RPT_FULFILMENT_FROM_EMAIL",
            ):
                os.environ.pop(k, None)
            with mock.patch(
                "payments.load_stored_processor_env",
                return_value={},
                create=True,
            ):
                with mock.patch(
                    "processor_plugins.load_stored_processor_env",
                    return_value={},
                ):
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

    def test_config_reads_admin_processor_store(self):
        """SMTP host from processor_env.json must enable configured=True."""
        from payments import assess_fulfilment_smtp_readiness, fulfilment_smtp_config

        store = {
            "RPT_FULFILMENT_SMTP_HOST": "smtp.store.test",
            "RPT_FULFILMENT_SMTP_USER": "store-user",
            "RPT_FULFILMENT_SMTP_PASSWORD": "store-pass",
            "RPT_FULFILMENT_FROM_EMAIL": "noreply@restoreprivacy.online",
        }
        with mock.patch.dict(os.environ, {}, clear=False):
            for k in store:
                os.environ.pop(k, None)
            with mock.patch(
                "processor_plugins.load_stored_processor_env",
                return_value=store,
            ):
                cfg = fulfilment_smtp_config()
        self.assertEqual(cfg["host"], "smtp.store.test")
        self.assertTrue(cfg["configured"])
        self.assertEqual(cfg["user"], "store-user")
        v = assess_fulfilment_smtp_readiness(cfg)
        self.assertTrue(v["email_flow_enabled"])
        self.assertEqual(v["status"], "ready_to_attempt_send")

    def test_send_skips_without_host(self):
        from payments import send_fulfilment_email

        with mock.patch.dict(os.environ, {"RPT_FULFILMENT_SMTP_HOST": ""}, clear=False):
            os.environ.pop("RPT_FULFILMENT_SMTP_HOST", None)
            with mock.patch(
                "processor_plugins.load_stored_processor_env",
                return_value={},
            ):
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

    def test_check_fulfilment_ready_includes_smtp_status(self):
        from payments import check_fulfilment_ready

        with mock.patch("payments.open_release_asset", return_value=None):
            with mock.patch(
                "payments.assess_fulfilment_smtp_readiness",
                return_value={
                    "status": "disabled",
                    "email_flow_enabled": False,
                    "detail": "SMTP host unset",
                    "missing_or_empty": ["RPT_FULFILMENT_SMTP_HOST"],
                },
            ):
                out = check_fulfilment_ready()
        self.assertIn("smtp_status", out)
        self.assertEqual(out["smtp_status"], "disabled")
        self.assertFalse(out["email_flow_enabled"])

    def test_check_script_exists(self):
        script = ROOT / "scripts" / "check_render_fulfilment_smtp.ps1"
        self.assertTrue(script.is_file())
        src = script.read_text(encoding="utf-8")
        self.assertIn("RPT_FULFILMENT_SMTP_HOST", src)
        self.assertIn("RENDER_API_KEY", src)
        self.assertIn("email_flow_enabled", src)

    def test_customer_email_fetches_customer_id(self):
        from payments import customer_email_from_checkout_object

        def fake_get(url: str, headers: dict) -> tuple[int, bytes]:
            self.assertIn("customers/cus_abc", url)
            return 200, b'{"email":"buyer@example.com"}'

        em = customer_email_from_checkout_object(
            {"customer": "cus_abc", "customer_details": {}},
            http_get=fake_get,
            secret_key="sk_test_x",
        )
        self.assertEqual(em, "buyer@example.com")

    def test_admin_resend_uses_real_send_path(self):
        from payments import admin_resend_fulfilment_email

        payloads: list[dict] = []

        def transport(p: dict) -> dict:
            payloads.append(p)
            return {"ok": True, "sent": True, "skipped": False}

        r = admin_resend_fulfilment_email(
            to_email="buyer@example.com",
            platform="windows",
            transport=transport,
        )
        self.assertTrue(r.get("sent"), r)
        self.assertTrue(r.get("admin_resend"))
        self.assertEqual(len(payloads), 1)
        body = payloads[0].get("body") or ""
        self.assertIn("Keygen", body)
        self.assertIn("buyer@example.com", payloads[0].get("to", ""))

    def test_smtp_probe_reports_not_configured(self):
        from payments import probe_fulfilment_smtp_login

        r = probe_fulfilment_smtp_login(
            {
                "host": "",
                "port": 587,
                "user": "",
                "password": "",
                "use_tls": True,
                "configured": False,
            }
        )
        self.assertFalse(r.get("ok"))
        self.assertEqual(r.get("error"), "smtp_not_configured")


if __name__ == "__main__":
    unittest.main()

