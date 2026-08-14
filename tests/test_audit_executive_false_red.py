"""Executive summary must not paint false security Red from suite-only FAIL.

When catalog package RAG is Green/Amber and live probes are healthy, a host
unit-suite FAIL (monopin doc lag, missing crypto, etc.) must not:
  - force overall_ok False, or
  - render Executive summary as bare **FAIL** that looks like installer Red.
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_security_audit.py"


def _load_rsa():
    spec = importlib.util.spec_from_file_location("run_security_audit", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["run_security_audit"] = mod
    spec.loader.exec_module(mod)
    return mod


class TestExecutiveSuiteLineFalseRed(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.mod = _load_rsa()

    def test_suite_pass_is_pass(self) -> None:
        line = self.mod.format_executive_suite_line(
            {"ran": True, "ok": True, "modules": ["a", "b"]},
            package_rag={"overall": "Green"},
        )
        self.assertIn("**PASS**", line)
        self.assertNotIn("FAIL", line)

    def test_suite_fail_with_green_rag_not_bare_fail(self) -> None:
        """False Red path: suite fail + Green packages → clarify not installer Red."""
        line = self.mod.format_executive_suite_line(
            {"ran": True, "ok": False, "modules": ["tests.test_legal_docs"]},
            package_rag={"overall": "Green"},
        )
        self.assertIn("**FAIL**", line)
        self.assertIn("catalog package RAG remains **Green**", line)
        self.assertIn("not installer Red", line)
        # Must not be the old bare cell that looked like total security Red
        self.assertNotEqual(line.strip(), "**FAIL**")

    def test_suite_fail_with_amber_rag_clarified(self) -> None:
        line = self.mod.format_executive_suite_line(
            {"ran": True, "ok": False, "modules": []},
            package_rag={"overall": "Amber"},
        )
        self.assertIn("**Amber**", line)
        self.assertIn("not installer Red", line)

    def test_suite_fail_with_red_rag_stays_fail(self) -> None:
        line = self.mod.format_executive_suite_line(
            {"ran": True, "ok": False, "modules": []},
            package_rag={"overall": "Red"},
        )
        self.assertEqual(line.strip(), "**FAIL**")

    def test_suite_skip_when_not_ran_and_not_ok(self) -> None:
        line = self.mod.format_executive_suite_line(
            {"ran": False, "ok": False, "modules": []},
            package_rag={"overall": "Green"},
        )
        self.assertIn("**SKIP**", line)

    def test_suite_not_ran_ok_is_pass(self) -> None:
        """Node install / --node-only: suite not run but ok=True remains PASS."""
        line = self.mod.format_executive_suite_line(
            {"ran": False, "ok": True, "modules": [], "reason": "skipped"},
            package_rag={"overall": "Green"},
        )
        self.assertIn("**PASS**", line)


class TestComputeOverallOkFalseRed(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.mod = _load_rsa()

    def _healthy_base(self, **over) -> dict:
        base = {
            "unit_suite": {"ran": True, "ok": True, "modules": ["x"]},
            "tcp_status": {"ok": True},
            "http_status": {"ok": True},
            "no_priv": {"ok": True},
            "section_b": {"ok": True},
            "multihop_structure": {"ok": True},
            "package_rag": {"overall": "Green"},
        }
        base.update(over)
        return base

    def test_all_healthy_is_ok(self) -> None:
        self.assertTrue(self.mod.compute_overall_ok(self._healthy_base()))

    def test_suite_fail_green_rag_live_ok_is_overall_ok(self) -> None:
        """False Red mitigation: suite FAIL alone must not flip overall_ok."""
        r = self._healthy_base(
            unit_suite={"ran": True, "ok": False, "modules": ["tests.test_legal_docs"]},
            package_rag={"overall": "Green"},
        )
        self.assertTrue(self.mod.compute_overall_ok(r))

    def test_suite_fail_amber_rag_live_ok_is_overall_ok(self) -> None:
        r = self._healthy_base(
            unit_suite={"ran": True, "ok": False},
            package_rag={"overall": "Amber"},
        )
        self.assertTrue(self.mod.compute_overall_ok(r))

    def test_tcp_fail_is_not_ok(self) -> None:
        r = self._healthy_base(tcp_status={"ok": False})
        self.assertFalse(self.mod.compute_overall_ok(r))

    def test_suite_fail_and_red_rag_with_probe_fail_is_not_ok(self) -> None:
        r = self._healthy_base(
            unit_suite={"ran": True, "ok": False},
            package_rag={"overall": "Red"},
            http_status={"ok": False},
        )
        self.assertFalse(self.mod.compute_overall_ok(r))

    def test_build_markdown_executive_suite_cell_clarifies_green_rag(self) -> None:
        """Drive real build_markdown — Executive summary must not bare-FAIL."""
        results = {
            "generated_at": "2026-08-14T12:00:00Z",
            "node_host": "Germany (DE)",
            "catalog_version": "1.2.3",
            "unit_suite": {
                "ran": True,
                "ok": False,
                "returncode": 1,
                "modules": ["tests.test_legal_docs"],
            },
            "tcp_status": {"ok": True, "port": 8080},
            "http_status": {
                "ok": True,
                "body": {"title": "RESTORE PRIVACY"},
            },
            "udp": {"sent": True},
            "no_priv": {"ok": True, "hits": []},
            "package_rag": {
                "catalog_version": "1.2.3",
                "overall": "Green",
                "packages": [
                    {
                        "platform": "android",
                        "label": "Android",
                        "filename": "x.apk",
                        "state": "Green",
                        "reasons": ["ok"],
                    }
                ],
                "legend": {
                    "Green": "OK",
                    "Amber": "Partial",
                    "Red": "Fail",
                },
            },
            "section_b": {"ok": True, "probes": {}},
            "multihop_structure": {"ok": True, "probes": {}},
            "live_node_probes": [],
        }
        md = self.mod.build_markdown(results)
        self.assertIn("## 1. Executive summary", md)
        self.assertIn("Security unit suite", md)
        self.assertIn("catalog package RAG remains **Green**", md)
        self.assertIn("not installer Red", md)
        # Bare row that looked like total Red is gone
        self.assertNotIn("| Security unit suite | **FAIL** |", md)


if __name__ == "__main__":
    unittest.main()
