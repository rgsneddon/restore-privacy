/**
 * App-testers triple gate (CSP-safe external script; script-src 'self').
 *
 * 1) Scroll #licence-scroll to bottom → enable both consent checkboxes
 * 2) Both checkboxes checked → enable package radios + mint submit
 */
(function () {
  "use strict";

  var SCROLL_SLACK = 16;

  /**
   * Pure bottom detection (exported for unit tests via window when present).
   * @param {number} scrollTop
   * @param {number} clientHeight
   * @param {number} scrollHeight
   * @param {number} [slack]
   * @returns {boolean}
   */
  function atBottomMetrics(scrollTop, clientHeight, scrollHeight, slack) {
    var s = typeof slack === "number" ? slack : SCROLL_SLACK;
    var st = Number(scrollTop) || 0;
    var ch = Number(clientHeight) || 0;
    var sh = Number(scrollHeight) || 0;
    if (sh <= ch + s) {
      return true; // no overflow / short content
    }
    return st + ch >= sh - s;
  }

  function atBottom(el) {
    if (!el) return false;
    return atBottomMetrics(el.scrollTop, el.clientHeight, el.scrollHeight, SCROLL_SLACK);
  }

  function init() {
    var scrollEl = document.getElementById("licence-scroll");
    var hint = document.getElementById("scroll-hint");
    var box = document.getElementById("accept-box");
    var reports = document.getElementById("reports-box");
    var acceptLabel = document.getElementById("accept-label");
    var reportsLabel = document.getElementById("reports-label");
    var gen = document.getElementById("generator");
    var btn = document.getElementById("mint-btn");
    var radios = document.querySelectorAll(".plat-radio");
    var scrolledToBottom = false;

    function packageEnabled() {
      return !!(
        scrolledToBottom &&
        box &&
        box.checked &&
        reports &&
        reports.checked
      );
    }

    function sync() {
      scrolledToBottom = atBottom(scrollEl);
      if (hint) {
        if (scrolledToBottom) {
          hint.textContent =
            "Agreements scrolled — check both boxes below to select a package.";
          hint.classList.add("done");
        } else {
          hint.textContent =
            "Scroll to the bottom of the agreements to continue.";
          hint.classList.remove("done");
        }
      }
      // Unlock checkboxes only after scroll-to-bottom
      [box, reports].forEach(function (el) {
        if (!el) return;
        el.disabled = !scrolledToBottom;
      });
      [acceptLabel, reportsLabel].forEach(function (el) {
        if (!el) return;
        if (scrolledToBottom) el.classList.remove("disabled-check");
        else el.classList.add("disabled-check");
      });
      // Package select only when both boxes checked
      var on = packageEnabled();
      if (gen) gen.classList.toggle("enabled", on);
      radios.forEach(function (r) {
        r.disabled = !on;
      });
      if (btn) btn.disabled = !on;
    }

    if (scrollEl) {
      scrollEl.addEventListener("scroll", sync, { passive: true });
      // Also respond to keyboard focus + wheel on the pane
      scrollEl.addEventListener("wheel", function () {
        // deferred so scrollTop updates first
        setTimeout(sync, 0);
      }, { passive: true });
    }
    if (box) box.addEventListener("change", sync);
    if (reports) reports.addEventListener("change", sync);
    if (typeof requestAnimationFrame === "function") {
      requestAnimationFrame(function () {
        sync();
      });
    }
    // Second tick after layout (fonts / pre-wrap height)
    setTimeout(sync, 50);
    setTimeout(sync, 250);
    sync();
  }

  // Expose pure helper for tests / console
  if (typeof window !== "undefined") {
    window.rptTesterAtBottomMetrics = atBottomMetrics;
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
