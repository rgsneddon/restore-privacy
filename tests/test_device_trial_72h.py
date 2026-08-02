"""KEYGEN-free 72h device trial: pure rules + host registry + paid isolation."""

from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "status_page"))

from device_trial import (  # noqa: E402
    TRIAL_SECONDS,
    claim_device_trial,
    connect_allowed_trial_or_paid,
    decide_trial_claim,
    get_device_trial_row,
    trial_is_active,
)


def _fake_pub(n: int = 1) -> str:
    return (f"{n:02x}" * 32)[:64]


class TestTrialPureRules(unittest.TestCase):
    def test_active_window_and_expiry(self) -> None:
        start = 1_000_000.0
        ends = start + TRIAL_SECONDS
        self.assertTrue(
            trial_is_active(
                started_at=start, ends_at=ends, status="active", now=start + 60
            )
        )
        self.assertFalse(
            trial_is_active(
                started_at=start, ends_at=ends, status="active", now=ends
            )
        )
        self.assertFalse(
            trial_is_active(
                started_at=start, ends_at=ends, status="expired", now=start + 1
            )
        )
        self.assertAlmostEqual(TRIAL_SECONDS, 72 * 3600)

    def test_decide_claim_create_reuse_deny(self) -> None:
        t0 = 2_000_000.0
        c = decide_trial_claim(None, now=t0)
        self.assertEqual(c["action"], "create")
        self.assertTrue(c["connect_allowed"])
        self.assertEqual(c["ends_at"], t0 + TRIAL_SECONDS)

        row = {
            "started_at": c["started_at"],
            "ends_at": c["ends_at"],
            "status": "active",
        }
        r = decide_trial_claim(row, now=t0 + 3600)
        self.assertEqual(r["action"], "reuse")
        self.assertTrue(r["connect_allowed"])
        self.assertEqual(r["ends_at"], c["ends_at"])  # no extension

        d = decide_trial_claim(row, now=c["ends_at"] + 1)
        self.assertEqual(d["action"], "deny")
        self.assertFalse(d["connect_allowed"])
        self.assertEqual(d["error"], "trial_exhausted")

    def test_decide_claim_install_exhausted_blocks_new_pub(self) -> None:
        t0 = 3_000_000.0
        d = decide_trial_claim(None, now=t0, install_exhausted=True)
        self.assertEqual(d["action"], "deny")
        self.assertFalse(d["connect_allowed"])
        self.assertEqual(d["error"], "trial_exhausted")

    def test_paid_or_trial_decision(self) -> None:
        self.assertTrue(
            connect_allowed_trial_or_paid(
                keygen_connect_allowed=False, trial_connect_allowed=True
            )
        )
        self.assertTrue(
            connect_allowed_trial_or_paid(
                keygen_connect_allowed=True, trial_connect_allowed=False
            )
        )
        self.assertFalse(
            connect_allowed_trial_or_paid(
                keygen_connect_allowed=False, trial_connect_allowed=False
            )
        )


class TestTrialHostRegistry(unittest.TestCase):
    def setUp(self) -> None:
        self._td = tempfile.TemporaryDirectory()
        self._prev = os.environ.get("RPT_PAYMENT_DATA_DIR")
        os.environ["RPT_PAYMENT_DATA_DIR"] = self._td.name
        import payments

        payments.init_db()

    def tearDown(self) -> None:
        if self._prev is None:
            os.environ.pop("RPT_PAYMENT_DATA_DIR", None)
        else:
            os.environ["RPT_PAYMENT_DATA_DIR"] = self._prev
        self._td.cleanup()

    def test_claim_reuse_and_anti_reinstall(self) -> None:
        pub = _fake_pub(7)
        t0 = time.time()
        a = claim_device_trial(pub, now=t0)
        self.assertTrue(a["ok"], a)
        self.assertTrue(a["connect_allowed"])
        self.assertEqual(a["action"], "create")
        ends = float(a["ends_at"])

        # Same device_pub re-claim (sim reinstall prefs wipe, same keystore pub)
        b = claim_device_trial(pub, now=t0 + 100)
        self.assertTrue(b["connect_allowed"])
        self.assertEqual(b["action"], "reuse")
        self.assertEqual(float(b["ends_at"]), ends)

        # After expiry — no second full 72h
        c = claim_device_trial(pub, now=ends + 5)
        self.assertFalse(c["connect_allowed"])
        self.assertEqual(c.get("error"), "trial_exhausted")
        self.assertTrue(c.get("requires_keygen"))

        row = get_device_trial_row(pub, now=ends + 5)
        self.assertIsNotNone(row)
        assert row is not None
        self.assertFalse(row["connect_allowed"])

    def test_install_id_blocks_second_trial_after_new_device_pub(self) -> None:
        """Best-effort: same install_id + new device_pub after expiry → deny."""
        pub1 = _fake_pub(21)
        pub2 = _fake_pub(22)
        iid = "a1b2c3d4e5f60718293a4b5c6d7e8f90"
        t0 = time.time()
        a = claim_device_trial(pub1, now=t0, install_id=iid)
        self.assertTrue(a["connect_allowed"], a)
        ends = float(a["ends_at"])
        denied_same = claim_device_trial(pub1, now=ends + 5, install_id=iid)
        self.assertFalse(denied_same["connect_allowed"])
        # Wipe keystore (new pub) but keep install marker
        denied_new = claim_device_trial(pub2, now=ends + 10, install_id=iid)
        self.assertFalse(denied_new["connect_allowed"], denied_new)
        self.assertEqual(denied_new.get("error"), "trial_exhausted")
        # Different install gets a fresh trial
        ok = claim_device_trial(pub2, now=ends + 15, install_id="f0e1d2c3b4a5968778695a4b3c2d1e0f")
        self.assertTrue(ok["connect_allowed"], ok)

    def test_get_device_entitlement_trial_and_paid_isolation(self) -> None:
        import payments

        pub = _fake_pub(9)
        t0 = time.time()
        claim_device_trial(pub, now=t0)
        ent = payments.get_device_entitlement(pub, now=t0 + 10)
        self.assertTrue(ent.get("connect_allowed"), ent)
        self.assertEqual(ent.get("kind"), "device_trial")
        self.assertEqual(ent.get("keygen") or "", "")

        # Paid bind present but not active must not fall through to free trial.
        sid = "cs_test_paid_only"
        conn = payments._connect()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO connect_entitlements"
                "(session_id, status, platform, reason, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?)",
                (sid, "failed", "macos", "test_fail", t0, t0),
            )
            conn.execute(
                "INSERT OR REPLACE INTO device_entitlements"
                "(device_pub_hex, session_id, created_at, updated_at) VALUES (?,?,?,?)",
                (pub, sid, t0, t0),
            )
        finally:
            conn.close()
        ent2 = payments.get_device_entitlement(pub, now=t0 + 20)
        self.assertFalse(ent2.get("connect_allowed"), ent2)
        self.assertEqual(ent2.get("kind"), "paid")


class TestTrialPrivacySurface(unittest.TestCase):
    def test_claim_api_fields_have_no_email_card(self) -> None:
        src = (ROOT / "status_page" / "device_trial.py").read_text(encoding="utf-8")
        self.assertNotIn("customer_email", src)
        self.assertIn("device_pub_hex", src)
        self.assertIn("TRIAL_SECONDS", src)
        self.assertIn("no email", src.lower())
        app = (ROOT / "status_page" / "app.py").read_text(encoding="utf-8")
        self.assertIn("/api/device-trial/claim", app)
        self.assertIn("device-trial", app)
        # Claim must live on do_POST (Flutter POSTs); status on do_GET.
        post_idx = app.find("def do_POST")
        get_idx = app.find("def do_GET")
        claim_in_post = app.find("/api/device-trial/claim", post_idx)
        self.assertGreater(post_idx, 0)
        self.assertGreater(claim_in_post, post_idx)
        # Status path remains on GET before do_POST
        status_in_get = app.find("/api/device-trial/status", get_idx)
        self.assertGreater(status_in_get, get_idx)
        self.assertLess(status_in_get, post_idx)


class TestTrialHttpHandler(unittest.TestCase):
    """Drive real status_page.Handler POST claim + GET status (Flutter path)."""

    def setUp(self) -> None:
        import json
        import threading
        import urllib.error
        import urllib.request
        from http.server import ThreadingHTTPServer

        self.json = json
        self.urllib_request = urllib.request
        self.urllib_error = urllib.error
        self._td = tempfile.TemporaryDirectory()
        self._prev = os.environ.get("RPT_PAYMENT_DATA_DIR")
        os.environ["RPT_PAYMENT_DATA_DIR"] = self._td.name
        import payments

        payments.init_db()
        import app as status_app

        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), status_app.Handler)
        self._port = self._httpd.server_address[1]
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()
        self._base = f"http://127.0.0.1:{self._port}"

    def tearDown(self) -> None:
        try:
            self._httpd.shutdown()
            self._httpd.server_close()
        except Exception:
            pass
        if self._prev is None:
            os.environ.pop("RPT_PAYMENT_DATA_DIR", None)
        else:
            os.environ["RPT_PAYMENT_DATA_DIR"] = self._prev
        self._td.cleanup()

    def _post_json(self, path: str, payload: dict) -> tuple[int, dict]:
        data = self.json.dumps(payload).encode("utf-8")
        req = self.urllib_request.Request(
            f"{self._base}{path}",
            data=data,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        try:
            with self.urllib_request.urlopen(req, timeout=5) as resp:
                body = resp.read().decode("utf-8")
                return resp.status, self.json.loads(body)
        except self.urllib_error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            try:
                parsed = self.json.loads(body) if body else {}
            except self.json.JSONDecodeError:
                parsed = {"raw": body}
            return int(exc.code), parsed

    def _get_json(self, path: str) -> tuple[int, dict]:
        req = self.urllib_request.Request(
            f"{self._base}{path}",
            method="GET",
            headers={"Accept": "application/json"},
        )
        try:
            with self.urllib_request.urlopen(req, timeout=5) as resp:
                body = resp.read().decode("utf-8")
                return resp.status, self.json.loads(body)
        except self.urllib_error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            try:
                parsed = self.json.loads(body) if body else {}
            except self.json.JSONDecodeError:
                parsed = {"raw": body}
            return int(exc.code), parsed

    def test_post_claim_then_get_status_and_device_entitlement(self) -> None:
        pub = _fake_pub(11)
        code, claim = self._post_json(
            "/api/device-trial/claim", {"device_pub": pub}
        )
        self.assertEqual(code, 200, claim)
        self.assertTrue(claim.get("connect_allowed"), claim)
        self.assertTrue(claim.get("ok"), claim)
        self.assertEqual(claim.get("kind"), "device_trial")
        self.assertEqual(claim.get("keygen") or "", "")
        self.assertNotIn("customer_email", claim)

        # Same pub GET status
        code2, st = self._get_json(f"/api/device-trial/status?device_pub={pub}")
        self.assertEqual(code2, 200, st)
        self.assertTrue(st.get("connect_allowed"), st)

        # Node residual path uses device-entitlement
        code3, ent = self._get_json(f"/api/device-entitlement?device_pub={pub}")
        self.assertEqual(code3, 200, ent)
        self.assertTrue(ent.get("connect_allowed"), ent)
        self.assertEqual(ent.get("kind"), "device_trial")

        # Anti-reinstall after forced expiry: reuse host clock via claim with now
        from device_trial import claim_device_trial

        ends = float(claim["ends_at"])
        denied = claim_device_trial(pub, now=ends + 10)
        self.assertFalse(denied.get("connect_allowed"), denied)
        self.assertEqual(denied.get("error"), "trial_exhausted")

        # POST claim again after expiry still exhausted (HTTP path)
        code4, claim2 = self._post_json(
            "/api/device-trial/claim", {"device_pub": pub}
        )
        self.assertEqual(code4, 200, claim2)
        self.assertFalse(claim2.get("connect_allowed"), claim2)
        self.assertEqual(claim2.get("error"), "trial_exhausted")

        # After expiry, residual HELLO must deny without KEYGEN
        code5, ent2 = self._get_json(f"/api/device-entitlement?device_pub={pub}")
        self.assertEqual(code5, 200, ent2)
        self.assertFalse(ent2.get("connect_allowed"), ent2)

    def test_get_claim_returns_405(self) -> None:
        code, body = self._get_json("/api/device-trial/claim")
        self.assertEqual(code, 405, body)
        self.assertEqual(body.get("error"), "method_not_allowed")

    def test_post_claim_bad_pub_400(self) -> None:
        code, body = self._post_json(
            "/api/device-trial/claim", {"device_pub": "not-a-key"}
        )
        self.assertEqual(code, 400, body)
        self.assertEqual(body.get("error"), "bad_device_pub")


if __name__ == "__main__":
    unittest.main()
