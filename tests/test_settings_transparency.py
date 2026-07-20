"""Settings transparency: connection log UI, DPI disclaimer, shared copy."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from client.transparency_copy import (  # noqa: E402
    CONNECTION_LOG_DISCLAIMER,
    CONNECTION_LOG_TITLE,
    DPI_DISCLAIMER_MARKERS,
    DPI_MITIGATION_DISCLAIMER,
    DPI_MITIGATION_TITLE,
    EXPORT_LOG_BUTTON,
    LEAK_TEST_BUTTON,
    LEAK_TEST_DISCLAIMER,
)


class TestTransparencyCopy(unittest.TestCase):
    def test_dpi_disclaimer_is_honest(self):
        text = DPI_MITIGATION_DISCLAIMER
        for marker in DPI_DISCLAIMER_MARKERS:
            self.assertIn(marker, text)
        self.assertIn("mitigations only", text)
        # Must not over-claim
        low = text.lower()
        self.assertNotIn("guarantees undetectability", low)
        self.assertNotIn("impossible to detect", low)

    def test_connection_log_local_only_copy(self):
        self.assertIn("this device", CONNECTION_LOG_DISCLAIMER.lower())
        self.assertIn("does not upload", CONNECTION_LOG_DISCLAIMER.lower())


class TestSettingsUiTransparencyWiring(unittest.TestCase):
    def test_windows_settings_has_log_export_dpi(self):
        src = (ROOT / "client" / "windows" / "app.py").read_text(encoding="utf-8")
        copy = (ROOT / "client" / "transparency_copy.py").read_text(encoding="utf-8")
        combined = src + copy
        self.assertIn("connection_log", src)
        self.assertIn("EXPORT_LOG_BUTTON", src)
        self.assertIn(EXPORT_LOG_BUTTON, copy)
        self.assertIn("CONNECTION_LOG_TITLE", src)
        self.assertIn(CONNECTION_LOG_TITLE, copy)
        self.assertIn("DPI_MITIGATION_TITLE", src)
        self.assertIn(DPI_MITIGATION_TITLE, copy)
        for marker in DPI_DISCLAIMER_MARKERS:
            self.assertIn(marker, combined)
        self.assertIn("LEAK_TEST_BUTTON", src)
        self.assertIn(LEAK_TEST_BUTTON, copy)
        self.assertIn("append_event", src)
        self.assertIn("format_export", src)
        self.assertIn("export_to_file", src)

    def test_flutter_settings_has_log_export_dpi(self):
        screen = (
            ROOT / "client_app" / "lib" / "settings_screen.dart"
        ).read_text(encoding="utf-8")
        dart_log = (
            ROOT / "client_app" / "lib" / "connection_log.dart"
        ).read_text(encoding="utf-8")
        dart_copy = (
            ROOT / "client_app" / "lib" / "transparency_copy.dart"
        ).read_text(encoding="utf-8")
        combined = screen + dart_copy
        self.assertIn("kConnectionLogTitle", screen)
        self.assertIn("Connection log", dart_copy)
        self.assertIn("kExportLogButton", screen)
        self.assertIn("Export log", dart_copy)
        self.assertIn("DPI-undetectability", combined)
        self.assertIn("mitigations only", combined)
        self.assertIn("appendEvent", dart_log)
        self.assertIn("formatExport", dart_log)
        self.assertIn("not uploaded", (dart_log + dart_copy).lower())

    def test_node_nolog_still_disables_connection_log(self):
        from node.nolog import NO_LOG_POLICY, apply_no_log_policy

        self.assertFalse(NO_LOG_POLICY.get("connection_log"))
        out = apply_no_log_policy({})
        self.assertFalse(out.get("connection_log"))


if __name__ == "__main__":
    unittest.main()
