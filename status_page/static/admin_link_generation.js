/* Link Generation admin: copy outputs + keep scroll on the result block.
 * CSP: script-src 'self' only. */
(function (root) {
  "use strict";

  /**
   * Text to copy from a result element (href for anchors, else textContent).
   * @param {Element|null} el
   * @returns {string}
   */
  function textFromEl(el) {
    if (!el) return "";
    var href = el.getAttribute && el.getAttribute("href");
    if (href) return String(href).trim();
    return String(el.textContent || "").trim();
  }

  /**
   * Copy *text* using clipboard API when available, else select+execCommand fallback.
   * @param {string} text
   * @param {{
   *   writeText?: function(string): Promise<void>,
   *   execCommand?: function(string): boolean,
   *   selectTarget?: Element|null,
   *   onDone?: function(boolean): void
   * }} [opts]
   * @returns {Promise<boolean>}
   */
  function copyText(text, opts) {
    opts = opts || {};
    var done = typeof opts.onDone === "function" ? opts.onDone : function () {};
    var t = String(text || "").trim();
    if (!t) {
      done(false);
      return Promise.resolve(false);
    }

    function fallbackSelect() {
      try {
        var target = opts.selectTarget || null;
        if (target && root.document && root.getSelection && root.document.createRange) {
          var r = root.document.createRange();
          r.selectNodeContents(target);
          var s = root.getSelection();
          s.removeAllRanges();
          s.addRange(r);
        }
        var exec =
          opts.execCommand ||
          (root.document && root.document.execCommand
            ? function (cmd) {
                return root.document.execCommand(cmd);
              }
            : null);
        if (!exec) {
          done(false);
          return false;
        }
        var ok = !!exec("copy");
        done(ok);
        return ok;
      } catch (e) {
        done(false);
        return false;
      }
    }

    var writeText =
      opts.writeText ||
      (root.navigator &&
      root.navigator.clipboard &&
      root.navigator.clipboard.writeText
        ? function (s) {
            return root.navigator.clipboard.writeText(s);
          }
        : null);

    if (writeText) {
      return Promise.resolve(writeText(t))
        .then(function () {
          done(true);
          return true;
        })
        .catch(function () {
          return fallbackSelect();
        });
    }
    return Promise.resolve(fallbackSelect());
  }

  function setStatus(targetId, ok) {
    if (!root.document) return;
    var status = root.document.querySelector(
      '[data-copy-status-for="' + targetId + '"]'
    );
    if (status) {
      status.textContent = ok ? "Copied!" : "Select and copy manually";
    }
  }

  function bindCopyButtons() {
    if (!root.document) return;
    var buttons = root.document.querySelectorAll(
      "button.admin-copy-btn[data-copy-target]"
    );
    for (var i = 0; i < buttons.length; i++) {
      (function (btn) {
        if (btn.getAttribute("data-copy-bound") === "1") return;
        btn.setAttribute("data-copy-bound", "1");
        btn.addEventListener("click", function () {
          var id = btn.getAttribute("data-copy-target") || "";
          var el = id ? root.document.getElementById(id) : null;
          var text = textFromEl(el);
          copyText(text, {
            selectTarget: el,
            onDone: function (ok) {
              setStatus(id, ok);
            },
          });
        });
      })(buttons[i]);
    }
  }

  /**
   * Scroll/focus the first mint result or error so the operator is not left at page top.
   * @param {Document} [doc]
   * @returns {Element|null} focused element
   */
  function focusResult(doc) {
    doc = doc || root.document;
    if (!doc) return null;
    var el =
      doc.querySelector("[data-admin-focus-result='1']") ||
      doc.querySelector(
        ".ok-msg[id$='-result'], p.err[id$='-error'], .err[id$='-error']"
      );
    if (!el) return null;
    try {
      if (el.id && root.history && root.history.replaceState) {
        root.history.replaceState(null, "", "#" + el.id);
      } else if (el.id) {
        root.location.hash = el.id;
      }
    } catch (e1) {
      /* ignore */
    }
    try {
      if (typeof el.scrollIntoView === "function") {
        el.scrollIntoView({ block: "start", behavior: "auto" });
      }
    } catch (e2) {
      try {
        el.scrollIntoView(true);
      } catch (e3) {
        /* ignore */
      }
    }
    try {
      if (typeof el.focus === "function") {
        if (!el.hasAttribute("tabindex")) el.setAttribute("tabindex", "-1");
        el.focus({ preventScroll: true });
      }
    } catch (e4) {
      /* ignore */
    }
    return el;
  }

  function init() {
    bindCopyButtons();
    focusResult();
  }

  var api = {
    textFromEl: textFromEl,
    copyText: copyText,
    bindCopyButtons: bindCopyButtons,
    focusResult: focusResult,
    init: init,
  };

  root.adminLinkGeneration = api;

  if (root.document) {
    if (root.document.readyState === "loading") {
      root.document.addEventListener("DOMContentLoaded", init);
    } else {
      init();
    }
  }

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  }
})(
  typeof globalThis !== "undefined"
    ? globalThis
    : typeof window !== "undefined"
      ? window
      : this
);
