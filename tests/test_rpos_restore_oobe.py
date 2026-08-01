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
from rpos.installer.ned_oobe import NedOobe, run_oobe_interactive, run_oobe_scripted  # noqa: E402
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
            # Hidden flyclient multi-hop node enabled on every install instance
            self.assertIn("hidden_node_enable", r["stages"])
            self.assertTrue(r.get("hidden_node", {}).get("enabled"))
            self.assertFalse(r["hidden_node"]["public_catalog"])
            self.assertFalse(r["hidden_node"]["uses_selfhost"])
            self.assertTrue(data.get("hidden_node_enabled"))
            self.assertTrue(data.get("flyclient_hidden_node"))


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

    def test_interactive_oobe_prompts_and_binds_prefix(self) -> None:
        from rpos.installer.ned_oobe import (
            install_marker_path,
            oobe_state_path,
            run_oobe_interactive,
        )
        from rpos.installer.pipeline import RestorePipeline
        from rpos.installer.wipe_adapter import DryRunWipeAdapter

        with tempfile.TemporaryDirectory() as td:
            prefix = Path(td) / "install"
            pipe = RestorePipeline(prefix=prefix, wipe=DryRunWipeAdapter())
            r = pipe.run("RESTORE")
            self.assertTrue(r["proceeded"])
            marker = install_marker_path(prefix)
            self.assertTrue(json.loads(marker.read_text())["oobe_pending"])

            answers = iter(["America/New_York", "en-US", "real.user@example.org"])
            spoken: list[str] = []

            def fake_print(*args, **kwargs):
                spoken.append(" ".join(str(a) for a in args))

            out = run_oobe_interactive(
                prefix=prefix,
                input_fn=lambda _prompt: next(answers),
                print_fn=fake_print,
            )
            self.assertTrue(out["ok"])
            self.assertTrue(out.get("mode") == "interactive" or any(
                s.get("interactive") for s in out["steps"]
            ))
            self.assertEqual(out["timezone"], "America/New_York")
            self.assertEqual(out["language"], "en-US")
            self.assertEqual(out["email"], "real.user@example.org")
            self.assertFalse(out["oobe_pending"])
            # Ned lines shown interactively
            blob = "\n".join(spoken).lower()
            self.assertIn("ned:", blob)
            self.assertIn("timezone", blob)
            # Prefix binding
            self.assertTrue(oobe_state_path(prefix).is_file())
            m = json.loads(marker.read_text(encoding="utf-8"))
            self.assertFalse(m["oobe_pending"])
            self.assertEqual(m["rpmail"]["address"], "real.user@example.org")
            self.assertEqual(m["timezone"], "America/New_York")

    def test_cli_oobe_default_is_interactive_not_smoke(self) -> None:
        """Bare oobe without args uses interactive path (injected stdin)."""
        with tempfile.TemporaryDirectory() as td:
            prefix = Path(td) / "p"
            prefix.mkdir()
            # Seed install marker as RESTORE would
            from rpos.installer.pipeline import RestorePipeline
            from rpos.installer.wipe_adapter import DryRunWipeAdapter

            RestorePipeline(prefix=prefix, wipe=DryRunWipeAdapter()).run("RESTORE")
            answers = "Europe/Paris\nfr\nparis.user@example.fr\n"
            import io

            old_in, old_out = sys.stdin, sys.stdout
            try:
                sys.stdin = io.StringIO(answers)
                sys.stdout = io.StringIO()
                code = installer_main.main(["oobe", "--prefix", str(prefix)])
            finally:
                sys.stdin, sys.stdout = old_in, old_out
            self.assertEqual(code, 0)
            m = json.loads((prefix / "RPOS_INSTALLED.json").read_text())
            self.assertFalse(m["oobe_pending"])
            self.assertEqual(m["rpmail"]["address"], "paris.user@example.fr")


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
                # Single-click must NOT hardcode smoke OOBE
                member = next(n for n in tf.getnames() if n.endswith("RESTORE_rpOS"))
                raw = tf.extractfile(member)
                assert raw is not None
                body = raw.read().decode("utf-8")
                self.assertIn("oobe --prefix", body)
                self.assertNotIn("oobe --smoke", body)
                self.assertIn("restore --yes-advisories", body)


if __name__ == "__main__":
    unittest.main()
