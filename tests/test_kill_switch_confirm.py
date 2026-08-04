"""Windows/shared kill-switch Settings confirm gate + durable opt-in (shipped code)."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from client.kill_switch_confirm import (  # noqa: E402
    KILL_SWITCH_CONFIRM_RISK_BODY,
    KILL_SWITCH_CONFIRM_TITLE,
    KILL_SWITCH_CONFIRM_TOKEN,
    evaluate_kill_switch_confirm,
    kill_switch_confirm_token_matches,
)
from client.kill_switch import (  # noqa: E402
    product_kill_switch_enabled,
    product_kill_switch_parked,
    set_kill_switch_settings_opt_in_reader,
)
from client.windows.settings_store import (  # noqa: E402
    KEY_KILL_SWITCH_OPT_IN,
    ProductSettings,
    default_settings,
    load_settings,
    save_settings,
)


class TestEvaluateKillSwitchConfirm(unittest.TestCase):
    def test_default_token_is_killswitch(self):
        self.assertEqual(KILL_SWITCH_CONFIRM_TOKEN, "KILLSWITCH")
        self.assertEqual(KILL_SWITCH_CONFIRM_TITLE, "ARE YOU SURE?")
        self.assertIn("KILLSWITCH", KILL_SWITCH_CONFIRM_RISK_BODY)
        self.assertIn("block", KILL_SWITCH_CONFIRM_RISK_BODY.lower())

    def test_disable_always_allowed_no_token(self):
        d = evaluate_kill_switch_confirm(desired_on=False)
        self.assertTrue(d.allow_persist)
        self.assertFalse(d.next_opt_in)
        self.assertEqual(d.reason, "disable_no_confirm")
        with_junk = evaluate_kill_switch_confirm(
            desired_on=False, confirm_text="nope"
        )
        self.assertTrue(with_junk.allow_persist)
        self.assertFalse(with_junk.next_opt_in)

    def test_enable_exact_token_allows(self):
        d = evaluate_kill_switch_confirm(
            desired_on=True, confirm_text=KILL_SWITCH_CONFIRM_TOKEN
        )
        self.assertTrue(d.allow_persist)
        self.assertTrue(d.next_opt_in)
        self.assertEqual(d.reason, "enable_token_ok")

    def test_enable_trims_outer_whitespace(self):
        d = evaluate_kill_switch_confirm(
            desired_on=True, confirm_text="  KILLSWITCH  "
        )
        self.assertTrue(d.allow_persist)
        self.assertTrue(d.next_opt_in)

    def test_enable_wrong_empty_cancel_leaves_off(self):
        for text, reason_part in (
            ("", "empty"),
            ("YES", "wrong"),
            ("killswitch", "wrong"),
            ("KILLSWITCH ", None),  # trailing space trims → ok
        ):
            d = evaluate_kill_switch_confirm(desired_on=True, confirm_text=text)
            if (text or "").strip() == KILL_SWITCH_CONFIRM_TOKEN:
                self.assertTrue(d.allow_persist, msg=repr(text))
                self.assertTrue(d.next_opt_in)
            else:
                self.assertFalse(d.allow_persist, msg=repr(text))
                self.assertFalse(d.next_opt_in)
                if reason_part:
                    self.assertIn(reason_part, d.reason)
        cancelled = evaluate_kill_switch_confirm(
            desired_on=True, confirm_text=KILL_SWITCH_CONFIRM_TOKEN, cancelled=True
        )
        self.assertFalse(cancelled.allow_persist)
        self.assertFalse(cancelled.next_opt_in)
        self.assertEqual(cancelled.reason, "enable_cancelled")

    def test_token_match_helper(self):
        self.assertTrue(kill_switch_confirm_token_matches("KILLSWITCH"))
        self.assertTrue(kill_switch_confirm_token_matches(" KILLSWITCH "))
        self.assertFalse(kill_switch_confirm_token_matches("killswitch"))
        self.assertFalse(kill_switch_confirm_token_matches(""))


class TestDurableKillSwitchOptIn(unittest.TestCase):
    def tearDown(self) -> None:
        set_kill_switch_settings_opt_in_reader(None)
        os.environ.pop("RPT_KILL_SWITCH", None)

    def test_default_settings_kill_switch_off(self):
        s = default_settings()
        self.assertFalse(s.kill_switch_opt_in)

    def test_save_load_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "settings.json"
            s = default_settings()
            s.kill_switch_opt_in = True
            save_settings(s, path=path)
            raw = json.loads(path.read_text(encoding="utf-8"))
            self.assertTrue(raw.get(KEY_KILL_SWITCH_OPT_IN))
            loaded = load_settings(path=path)
            self.assertTrue(loaded.kill_switch_opt_in)
            s2 = default_settings()
            s2.kill_switch_opt_in = False
            save_settings(s2, path=path)
            self.assertFalse(load_settings(path=path).kill_switch_opt_in)

    def test_missing_key_defaults_off(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "settings.json"
            path.write_text("{\"run_at_startup\": false}\n", encoding="utf-8")
            loaded = load_settings(path=path)
            self.assertFalse(loaded.kill_switch_opt_in)

    def test_product_gate_default_off_unparked(self):
        self.assertFalse(product_kill_switch_parked())
        set_kill_switch_settings_opt_in_reader(lambda: False)
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("RPT_KILL_SWITCH", None)
            self.assertFalse(product_kill_switch_enabled())

    def test_product_gate_env_opt_in(self):
        set_kill_switch_settings_opt_in_reader(lambda: False)
        with mock.patch.dict(os.environ, {"RPT_KILL_SWITCH": "1"}, clear=False):
            self.assertTrue(product_kill_switch_enabled())
        with mock.patch.dict(os.environ, {"RPT_KILL_SWITCH": "0"}, clear=False):
            # env not truthy → falls through to settings (False)
            self.assertFalse(product_kill_switch_enabled())

    def test_product_gate_settings_opt_in(self):
        set_kill_switch_settings_opt_in_reader(lambda: True)
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("RPT_KILL_SWITCH", None)
            self.assertTrue(product_kill_switch_enabled())

    def test_enable_persist_path_uses_confirm_gate(self):
        """Simulate Settings save path: only exact token persists ON."""
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "settings.json"
            # Wrong token → stay off
            bad = evaluate_kill_switch_confirm(
                desired_on=True, confirm_text="YES"
            )
            self.assertFalse(bad.allow_persist)
            s = default_settings()
            if bad.allow_persist:
                s.kill_switch_opt_in = bad.next_opt_in
            else:
                s.kill_switch_opt_in = False
            save_settings(s, path=path)
            self.assertFalse(load_settings(path=path).kill_switch_opt_in)
            # Exact token → on
            good = evaluate_kill_switch_confirm(
                desired_on=True, confirm_text="KILLSWITCH"
            )
            self.assertTrue(good.allow_persist)
            s.kill_switch_opt_in = good.next_opt_in
            save_settings(s, path=path)
            self.assertTrue(load_settings(path=path).kill_switch_opt_in)
            # Disable without token
            off = evaluate_kill_switch_confirm(desired_on=False)
            s.kill_switch_opt_in = off.next_opt_in
            save_settings(s, path=path)
            self.assertFalse(load_settings(path=path).kill_switch_opt_in)


class TestWindowsSettingsUiWiresKillSwitch(unittest.TestCase):
    def test_app_py_has_kill_switch_settings_surface(self):
        src = (ROOT / "client" / "windows" / "app.py").read_text(encoding="utf-8")
        self.assertIn("kill_switch_opt_in", src)
        self.assertIn("_save_kill_switch", src)
        self.assertIn("evaluate_kill_switch_confirm", src)
        self.assertIn("KILL_SWITCH_CONFIRM_TITLE", src)
        self.assertIn("ARE YOU SURE?", src)
        self.assertIn("KILLSWITCH", src)
        self.assertIn("KILL_SWITCH_SETTINGS_LABEL", src)
        self.assertIn("ks_var", src)


if __name__ == "__main__":
    unittest.main()
