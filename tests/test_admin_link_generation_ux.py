"""Link Generation admin: copy controls + stay on result after mint."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "status_page"))

JS_PATH = ROOT / "status_page" / "static" / "admin_link_generation.js"


class TestLinkGenCopyStructure(unittest.TestCase):
    def test_result_surfaces_have_copy_and_focus_anchors(self) -> None:
        from admin_panel import (
            ADMIN_LINK_GENERATION_SCRIPT,
            admin_copy_control_html,
            render_admin_link_generation_html,
            render_admin_keygen_failsafe_section_html,
            render_admin_ondemand_mint_section_html,
            render_admin_tester_month_section_html,
            render_purchase_reissue_section_html,
            render_seed_test_purchase_section_html,
        )

        # Shipped helper markup
        ctrl = admin_copy_control_html("sample-id", label="Copy keygen")
        self.assertIn('data-copy-target="sample-id"', ctrl)
        self.assertIn('data-copy-status-for="sample-id"', ctrl)
        self.assertIn("admin-copy-btn", ctrl)

        reissue = render_purchase_reissue_section_html(
            result={
                "download_url": "https://example.test/download?token=abc",
                "download_path": "/download?token=abc",
                "purchase_id": "RPT-AAAA-BBBB-CCCC",
                "platform": "windows",
                "filename": "pkg.exe",
            }
        )
        self.assertIn('id="reissue-result"', reissue)
        self.assertIn('data-admin-focus-result="1"', reissue)
        self.assertIn('data-copy-target="reissue-download-link"', reissue)
        self.assertIn('data-copy-target="reissue-result-purchase-id"', reissue)
        self.assertIn(
            'action="/admin/reissue-download#admin-reissue"', reissue
        )

        ondemand = render_admin_ondemand_mint_section_html(
            result={
                "download_url": "https://example.test/download?token=def",
                "download_path": "/download?token=def",
                "platform": "linux",
                "filename": "pkg.tar.gz",
            }
        )
        self.assertIn('id="ondemand-result"', ondemand)
        self.assertIn('data-admin-focus-result="1"', ondemand)
        self.assertIn('data-copy-target="ondemand-download-link"', ondemand)
        self.assertIn(
            'action="/admin/mint-download#admin-ondemand-mint"', ondemand
        )

        keygen = render_admin_keygen_failsafe_section_html(
            result={
                "keygen": "KG-TEST-1234-5678",
                "session_id": "admin_keygen_x",
                "platform": "windows",
                "unlock_instruction": "USE THIS KEYGEN TO UNLOCK",
            }
        )
        self.assertIn('id="keygen-failsafe-result"', keygen)
        self.assertIn('data-admin-focus-result="1"', keygen)
        self.assertIn('id="admin-minted-keygen"', keygen)
        self.assertIn('data-copy-target="admin-minted-keygen"', keygen)
        self.assertIn(
            'action="/admin/mint-keygen#admin-keygen-failsafe"', keygen
        )

        tester = render_admin_tester_month_section_html(
            result={
                "download_url": "https://example.test/download?token=t",
                "download_path": "/download?token=t",
                "keygen": "KG-TESTER-9999",
                "platform": "android",
                "filename": "app.apk",
                "ppi": "TESTER - one month",
                "valid_until": 1_900_000_000.0,
            }
        )
        self.assertIn('id="tester-month-result"', tester)
        self.assertIn('data-admin-focus-result="1"', tester)
        self.assertIn('data-copy-target="tester-month-keygen"', tester)
        self.assertIn('data-copy-target="tester-month-download-link"', tester)
        self.assertIn(
            'action="/admin/mint-tester-month#admin-tester-month"', tester
        )

        page = render_admin_link_generation_html(
            reissue_result={
                "download_url": "https://example.test/download?token=page",
                "download_path": "/download?token=page",
                "purchase_id": "RPT-PAGE-TEST-0001",
                "platform": "windows",
                "filename": "pkg.exe",
            }
        ).decode("utf-8")
        self.assertIn(ADMIN_LINK_GENERATION_SCRIPT, page)
        self.assertIn('id="admin-link-generation-script"', page)
        self.assertIn('data-admin-focus-result="1"', page)
        self.assertIn("admin-copy-btn", page)
        # Form section anchors still present for hash navigation
        self.assertIn('id="admin-reissue"', page)

        # Error path also focuses
        err_html = render_purchase_reissue_section_html(
            error="Unknown purchase identifier"
        )
        self.assertIn('id="reissue-error"', err_html)
        self.assertIn('data-admin-focus-result="1"', err_html)

    def test_seed_result_has_copy_when_enabled(self) -> None:
        with mock.patch.dict(os.environ, {"RPT_ADMIN_SEED_PURCHASE": "1"}):
            # Re-import path uses payments.seed_test_purchase_enabled
            from admin_panel import render_seed_test_purchase_section_html

            seed = render_seed_test_purchase_section_html(
                result={
                    "purchase_id": "RPT-SEED-TEST-0001",
                    "platform": "windows",
                    "filename": "pkg.exe",
                    "download_url": "https://example.test/download?token=seed",
                    "download_path": "/download?token=seed",
                }
            )
            self.assertIn('id="seed-purchase-result"', seed)
            self.assertIn('data-admin-focus-result="1"', seed)
            self.assertIn('data-copy-target="seed-purchase-id"', seed)
            self.assertIn('data-copy-target="seed-download-link"', seed)
            self.assertIn(
                'action="/admin/seed-test-purchase#admin-seed-purchase"', seed
            )

    def test_static_route_and_script_file(self) -> None:
        app = (ROOT / "status_page" / "app.py").read_text(encoding="utf-8")
        self.assertIn('"/static/admin_link_generation.js"', app)
        self.assertTrue(JS_PATH.is_file())
        js = JS_PATH.read_text(encoding="utf-8")
        self.assertIn("data-copy-target", js)
        self.assertIn("clipboard.writeText", js)
        self.assertIn("execCommand", js)
        self.assertIn("focusResult", js)
        self.assertIn("data-admin-focus-result", js)
        self.assertIn("scrollIntoView", js)


class TestLinkGenCopyLogic(unittest.TestCase):
    def test_shipped_js_copy_and_focus_via_node(self) -> None:
        """Drive the real admin_link_generation.js (clipboard + fallback + focus)."""
        self.assertTrue(JS_PATH.is_file())
        script = r"""
const fs = require("fs");
const path = process.argv[1];
const code = fs.readFileSync(path, "utf8");

const store = { clipboard: null, hash: "", scrolled: null, focused: null, execCopy: 0 };
const selection = { ranges: [] };
const document = {
  readyState: "complete",
  addEventListener: function () {},
  createRange: function () {
    return {
      selectNodeContents: function () {},
    };
  },
  execCommand: function (cmd) {
    if (cmd === "copy") {
      store.execCopy += 1;
      return true;
    }
    return false;
  },
  getElementById: function (id) {
    return document._els[id] || null;
  },
  querySelector: function (sel) {
    if (sel.indexOf("data-admin-focus-result") >= 0) {
      return document._focus || null;
    }
    if (sel.indexOf("data-copy-status-for") >= 0) {
      const m = /data-copy-status-for="([^"]+)"/.exec(sel);
      const id = m && m[1];
      return (document._status && document._status[id]) || null;
    }
    if (sel.indexOf("ok-msg") >= 0) return document._focus || null;
    return null;
  },
  querySelectorAll: function () {
    return document._buttons || [];
  },
  _els: {},
  _status: {},
  _buttons: [],
  _focus: null,
};

function makeEl(id, text, href) {
  return {
    id: id,
    textContent: text || "",
    getAttribute: function (name) {
      if (name === "href") return href || null;
      return null;
    },
    setAttribute: function () {},
    hasAttribute: function () { return false; },
    scrollIntoView: function () { store.scrolled = id; },
    focus: function () { store.focused = id; },
  };
}

const kg = makeEl("admin-minted-keygen", "  KG-ABC-123  ");
const link = makeEl(
  "reissue-download-link",
  "https://example.test/download?token=xyz",
  "https://example.test/download?token=xyz"
);
document._els["admin-minted-keygen"] = kg;
document._els["reissue-download-link"] = link;
document._focus = makeEl("reissue-result", "ok");
document._focus.id = "reissue-result";

const root = {
  document: document,
  getSelection: function () {
    return {
      removeAllRanges: function () { selection.ranges = []; },
      addRange: function (r) { selection.ranges.push(r); },
    };
  },
  navigator: {
    clipboard: {
      writeText: function (t) {
        store.clipboard = t;
        return Promise.resolve();
      },
    },
  },
  history: {
    replaceState: function (_a, _b, url) {
      store.hash = String(url || "");
    },
  },
  location: { hash: "" },
};

// Load shipped script against mock root (IIFE uses globalThis)
const prev = globalThis;
const sandbox = Object.assign(root, { globalThis: root, module: { exports: {} } });
// Evaluate in Function so `this` / globalThis map to sandbox
const fn = new Function(
  "globalThis",
  "window",
  "module",
  "exports",
  "document",
  "navigator",
  "history",
  "location",
  code + "\n; return globalThis.adminLinkGeneration || module.exports;"
);
const api = fn(
  sandbox,
  sandbox,
  sandbox.module,
  sandbox.module.exports,
  document,
  root.navigator,
  root.history,
  root.location
);
if (!api || !api.copyText || !api.textFromEl || !api.focusResult) {
  console.error("FAIL missing api", Object.keys(api || {}));
  process.exit(1);
}

const t1 = api.textFromEl(kg);
const t2 = api.textFromEl(link);
if (t1 !== "KG-ABC-123") {
  console.error("FAIL keygen text", t1);
  process.exit(1);
}
if (t2 !== "https://example.test/download?token=xyz") {
  console.error("FAIL url text", t2);
  process.exit(1);
}

Promise.resolve()
  .then(function () {
    return api.copyText(t1);
  })
  .then(function (ok) {
    if (!ok || store.clipboard !== "KG-ABC-123") {
      console.error("FAIL clipboard path", ok, store.clipboard);
      process.exit(1);
    }
    // Fallback path when writeText rejects
    store.clipboard = null;
    return api.copyText(t2, {
      writeText: function () {
        return Promise.reject(new Error("denied"));
      },
      selectTarget: link,
      execCommand: function (cmd) {
        if (cmd === "copy") {
          store.execCopy += 1;
          store.clipboard = t2;
          return true;
        }
        return false;
      },
    });
  })
  .then(function (ok2) {
    if (!ok2 || store.execCopy < 1) {
      console.error("FAIL fallback path", ok2, store);
      process.exit(1);
    }
    const focused = api.focusResult(document);
    if (!focused || focused.id !== "reissue-result") {
      console.error("FAIL focusResult", focused && focused.id);
      process.exit(1);
    }
    if (store.scrolled !== "reissue-result") {
      console.error("FAIL scroll", store.scrolled);
      process.exit(1);
    }
    if (store.hash !== "#reissue-result") {
      console.error("FAIL hash", store.hash);
      process.exit(1);
    }
    console.log("PASS copy+focus");
    console.log("keygen=", t1);
    console.log("url=", t2);
    console.log("hash=", store.hash);
  })
  .catch(function (e) {
    console.error("FAIL", e);
    process.exit(1);
  });
"""
        r = subprocess.run(
            ["node", "-e", script, str(JS_PATH)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(
            r.returncode,
            0,
            msg=f"stdout={r.stdout!r}\nstderr={r.stderr!r}",
        )
        self.assertIn("PASS copy+focus", r.stdout)


if __name__ == "__main__":
    unittest.main()
