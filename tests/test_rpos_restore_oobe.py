"""Tests for rpOS single-click RESTORE gate, dry-run wipe, and Ned OOBE."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from rpos.installer.advisories import (  # noqa: E402
    ADVISORY_LAYERS,
    RESTORE_CONFIRM_PHRASE,
    advisory_text_blob,
    has_required_warning_keywords,
)
from rpos.installer.gate import evaluate_confirmation, require_restore_confirmation  # noqa: E402
from rpos.installer.ned_oobe import NedOobe, run_oobe_scripted  # noqa: E402
from rpos.installer.pipeline import RestorePipeline  # noqa: E402
from rpos.installer.wipe_adapter import DryRunWipeAdapter  # noqa: E402
from rpos.installer import __main__ as installer_main  # noqa: E402


class TestAdvisories(unittest.TestCase):
    def test_multi_layer_keywords(self) -> None:
        text = advisory_text_blob()
        self.assertTrue(has_required_warning_keywords(text))
        self.assertGreaterEqual(len(ADVISORY_LAYERS), 3)
        ids = {a["id"] for a in ADVISORY_LAYERS}
        self.assertIn("careful", ids)
        self.assertIn("irreversible", ids)
        self.assertIn("data_loss", ids)
        self.assertIn(RESTORE_CONFIRM_PHRASE, text)
        low = text.lower()
        self.assertIn("careful", low)
        self.assertIn("irreversible", low)
        self.assertIn("data loss", low)


class TestGate(unittest.TestCase):
    def test_reject_then_accept(self) -> None:
        bad = evaluate_confirmation("yes")
        self.assertFalse(bad.allowed)
        self.assertEqual(bad.reason, "confirmation_rejected")
        with self.assertRaises(PermissionError):
            require_restore_confirmation("wipe")
        good = evaluate_confirmation("RESTORE")
        self.assertTrue(good.allowed)
        no_adv = evaluate_confirmation("RESTORE", advisories_acknowledged=False)
        self.assertFalse(no_adv.allowed)


class TestPipeline(unittest.TestCase):
    def test_wrong_confirm_does_not_wipe_or_install(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            prefix = Path(td) / "p"
            pipe = RestorePipeline(prefix=prefix, wipe=DryRunWipeAdapter())
            r = pipe.run("nope")
            self.assertFalse(r["proceeded"])
            self.assertIsNone(r["wipe"])
            self.assertFalse((prefix / "RPOS_INSTALLED.json").exists())

    def test_restore_dry_run_then_install(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            src = ROOT / "rpos"
            pipe = RestorePipeline(
                prefix=tdp / "root",
                source_rpos=src,
                wipe=DryRunWipeAdapter(),
            )
            r = pipe.run("RESTORE")
            self.assertTrue(r["ok"])
            self.assertTrue(r["proceeded"])
            self.assertIn("wipe_intent", r["stages"])
            self.assertIn("install_foundation", r["stages"])
            self.assertFalse(r["wipe"]["host_disk_touched"])
            self.assertEqual(r["wipe"]["mode"], "dry_run")
            self.assertTrue(r["wipe"]["intent"].startswith("absolute"))
            marker = Path(r["install"]["marker"])
            self.assertTrue(marker.is_file())
            data = json.loads(marker.read_text(encoding="utf-8"))
            self.assertTrue(data["from_scratch"])
            self.assertTrue(data["oobe_pending"])


class TestNedOobe(unittest.TestCase):
    def test_timezone_language_email_rpmail(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "oobe.json"
            out = run_oobe_scripted(
                "Europe/London",
                "en-GB",
                "human@example.com",
                persist_path=path,
            )
            self.assertTrue(out["ok"])
            self.assertEqual(out["timezone"], "Europe/London")
            self.assertEqual(out["language"], "en-GB")
            self.assertEqual(out["email"], "human@example.com")
            self.assertTrue(out["rpmail"]["bound"])
            self.assertEqual(out["rpmail"]["address"], "human@example.com")
            self.assertEqual(out["rpmail"]["product"], "rpMail")
            # Ned spoke at each step
            self.assertGreaterEqual(len(out["ned_log"]), 3)
            self.assertTrue(any("timezone" in s["ned"].lower() for s in out["steps"]))
            self.assertTrue(any("language" in s["ned"].lower() for s in out["steps"]))
            self.assertTrue(any("rpmail" in s["ned"].lower() or "email" in s["ned"].lower() for s in out["steps"]))
            loaded = NedOobe.load(path)
            self.assertTrue(loaded.state.completed)
            self.assertEqual(loaded.state.email, "human@example.com")


class TestEntrySmoke(unittest.TestCase):
    def test_cli_smoke_twice(self) -> None:
        self.assertEqual(installer_main.main(["smoke"]), 0)
        self.assertEqual(installer_main.main(["advisories"]), 0)
        self.assertEqual(installer_main.main(["smoke"]), 0)


class TestPackageHasSingleClick(unittest.TestCase):
    def test_archives_include_restore_rpos_click(self) -> None:
        import tarfile
        import zipfile

        from package_rpos import package_all
        import sys

        sys.path.insert(0, str(ROOT / "scripts"))
        # re-import after path
        import importlib
        import package_rpos as pr

        importlib.reload(pr)
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "out"
            r = pr.package_all(version="0.1.0", out_dir=out)
            self.assertTrue(r["ok"], r)
            by = {p["platform"]: p for p in r["packages"]}
            with zipfile.ZipFile(by["windows"]["archive"]) as zf:
                names = "\n".join(zf.namelist())
                self.assertIn("RESTORE_rpOS.cmd", names)
                self.assertIn("rpos/installer/", names)
            with tarfile.open(by["linux-x86_64"]["archive"], "r:gz") as tf:
                names = "\n".join(tf.getnames())
                self.assertIn("RESTORE_rpOS", names)
                self.assertIn("rpos/installer/pipeline.py", names)
                self.assertIn("rpos/installer/ned_oobe.py", names)


if __name__ == "__main__":
    unittest.main()
