"""Catalog flag PNGs + brand window/taskbar icon resolution (shipped path)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class TestFlagImages(unittest.TestCase):
    def test_catalog_flag_pngs_exist_for_is_ro_us(self):
        from client.flag_images import (
            CATALOG_FLAG_CODES,
            assert_catalog_flag_images_present,
            catalog_flag_image_paths,
            flag_image_path,
            flag_images_dir,
        )

        self.assertTrue(flag_images_dir().is_dir())
        missing = assert_catalog_flag_images_present()
        self.assertEqual(missing, [], f"missing flag PNGs: {missing}")
        paths = catalog_flag_image_paths()
        self.assertEqual(set(paths.keys()), set(CATALOG_FLAG_CODES))
        for code in CATALOG_FLAG_CODES:
            p = flag_image_path(code)
            self.assertIsNotNone(p, code)
            assert p is not None
            self.assertTrue(p.is_file(), code)
            self.assertGreater(p.stat().st_size, 50, code)
            # PNG magic
            self.assertEqual(p.read_bytes()[:8], b"\x89PNG\r\n\x1a\n", code)

    def test_country_options_have_non_empty_flags(self):
        from client.country_select import catalog_country_options, country_flag_emoji
        from client.flag_images import flag_image_path

        opts = catalog_country_options()
        from client.multihop import offered_catalog_codes

        self.assertEqual([o.code for o in opts], list(offered_catalog_codes()))
        self.assertNotIn("IS", [o.code for o in opts])
        self.assertGreaterEqual(len(opts), 1)
        for o in opts:
            self.assertTrue(o.flag.strip(), o.code)
            self.assertTrue(o.label().startswith(o.flag) or o.flag in o.label())
            self.assertEqual(country_flag_emoji(o.code), o.flag)
            # Image asset for each catalog option
            self.assertIsNotNone(flag_image_path(o.code), o.code)


class TestWindowIconBrand(unittest.TestCase):
    def test_brand_icon_paths_prefer_app_icon(self):
        from client.windows.window_icon import brand_icon_paths

        ico, png = brand_icon_paths()
        self.assertIsNotNone(ico)
        assert ico is not None
        self.assertTrue(ico.is_file())
        self.assertIn("app_icon.ico", ico.name)
        self.assertGreater(ico.stat().st_size, 1000)
        # Multi-size ICO (taskbar needs 16/32)
        data = ico.read_bytes()
        count = int.from_bytes(data[4:6], "little")
        self.assertGreaterEqual(count, 4, "multi-size ICO expected for taskbar")
        # Must not document feather / IDI_APPLICATION as primary when brand exists
        src = (ROOT / "client" / "windows" / "window_icon.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("IDI_APPLICATION", src)
        self.assertIn("WM_SETICON", src)
        self.assertIn("app_icon.ico", src)

    def test_app_sets_app_user_model_id_and_apply_helper(self):
        app_src = (ROOT / "client" / "windows" / "app.py").read_text(encoding="utf-8")
        self.assertIn("set_process_app_user_model_id", app_src)
        self.assertIn("apply_brand_window_icon", app_src)
        self.assertIn("flag_image_path", app_src)
        self.assertIn("Menubutton", app_src)
        # Menubutton image compound for flags (not OptionMenu-only)
        self.assertIn("compound=tk.LEFT", app_src)

    def test_win32_icon_helper_does_not_reenter_tk_or_set_class_long(self):
        src = (ROOT / "client" / "windows" / "window_icon.py").read_text(
            encoding="utf-8"
        )
        fn = src[src.find("def _win32_set_icons_from_ico") :]
        self.assertNotIn("root.update_idletasks", fn)
        self.assertNotIn("SetClassLongPtrW(", fn)
        self.assertNotIn("SetClassLongW(", fn)
        self.assertIn("SendMessageW", src)
        app_src = (ROOT / "client" / "windows" / "app.py").read_text(encoding="utf-8")
        self.assertNotIn("_reapply_brand_icon", app_src)

    def test_apply_brand_window_icon_on_real_tk(self):
        import tkinter as tk

        from client.windows.window_icon import (
            apply_brand_window_icon,
            set_process_app_user_model_id,
        )

        set_process_app_user_model_id()
        root = tk.Tk()
        root.withdraw()
        try:
            status = apply_brand_window_icon(root)
            self.assertTrue(
                status.get("iconbitmap") or status.get("iconphoto") or status.get("wm_seticon"),
                status,
            )
            self.assertIsNotNone(status.get("ico"))
            self.assertIn("app_icon", str(status.get("ico") or ""))
            # No intentional stock feather path when brand ICO present
            self.assertNotEqual(status.get("ico"), "")
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
