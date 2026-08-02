/**
 * Suite homepage intro — one-shot neon typewriter (welcome + closing).
 * Types each [data-typewriter="1"] node once per page load, then leaves text.
 */
(function () {
  "use strict";

  // Baseline closing/default cadence; welcome is slower so it draws attention.
  var DEFAULT_MS = 55;
  var WELCOME_MS = 120;
  var DONE_CLASS = "is-done";
  var TYPING_CLASS = "is-typing";

  function fullText(el) {
    return (el.getAttribute("data-typewriter-text") || el.getAttribute("aria-label") || "").trim();
  }

  /**
   * Per-role typing delay (ms). Welcome is intentionally slower than DEFAULT_MS.
   * @param {Element} el
   * @returns {number}
   */
  function delayMsFor(el) {
    var role = (el && el.getAttribute("data-typewriter-role")) || "";
    if (role === "welcome") return WELCOME_MS;
    var attr = el && el.getAttribute("data-typewriter-ms");
    if (attr != null && attr !== "") {
      var n = parseInt(attr, 10);
      if (!isNaN(n) && n > 0) return n;
    }
    return DEFAULT_MS;
  }

  /**
   * Pure step helper (mirrors Python typewriter_prefix for tests / consistency).
   * @param {string} full
   * @param {number} step
   * @returns {string}
   */
  function typewriterPrefix(full, step) {
    var text = full || "";
    var n = Math.max(0, Math.min(step | 0, text.length));
    return text.slice(0, n);
  }

  function typewriterDone(full, step) {
    return (step | 0) >= (full || "").length;
  }

  function typeElement(el, opts) {
    opts = opts || {};
    var full = fullText(el);
    var ms = opts.ms != null ? opts.ms : delayMsFor(el);
    var step = 0;
    var finished = false;

    if (!full) {
      el.classList.add(DONE_CLASS);
      if (typeof opts.onDone === "function") opts.onDone();
      return;
    }
    // Already completed once on this node — leave as-is
    if (el.getAttribute("data-typewriter-complete") === "1") {
      el.textContent = full;
      el.classList.remove(TYPING_CLASS);
      el.classList.add(DONE_CLASS);
      if (typeof opts.onDone === "function") opts.onDone();
      return;
    }

    el.textContent = "";
    el.classList.add(TYPING_CLASS);
    el.classList.remove(DONE_CLASS);

    function tick() {
      if (finished) return;
      step += 1;
      el.textContent = typewriterPrefix(full, step);
      if (typewriterDone(full, step)) {
        finished = true;
        el.setAttribute("data-typewriter-complete", "1");
        el.classList.remove(TYPING_CLASS);
        el.classList.add(DONE_CLASS);
        el.textContent = full;
        if (typeof opts.onDone === "function") opts.onDone();
        return;
      }
      window.setTimeout(tick, ms);
    }
    window.setTimeout(tick, ms);
  }

  function runChain(nodes) {
    if (!nodes.length) return;
    var i = 0;
    function next() {
      if (i >= nodes.length) return;
      var el = nodes[i++];
      typeElement(el, {
        ms: delayMsFor(el),
        onDone: function () {
          // brief pause before next typewriter line
          window.setTimeout(next, 280);
        },
      });
    }
    next();
  }

  function boot() {
    var root = document.getElementById("suite-home-intro");
    if (!root) return;
    var nodes = Array.prototype.slice.call(
      root.querySelectorAll('[data-typewriter="1"][data-typewriter-once="1"]')
    );
    // Prefer welcome then closing order
    nodes.sort(function (a, b) {
      var ra = a.getAttribute("data-typewriter-role") || "";
      var rb = b.getAttribute("data-typewriter-role") || "";
      if (ra === "welcome") return -1;
      if (rb === "welcome") return 1;
      if (ra === "closing") return 1;
      if (rb === "closing") return -1;
      return 0;
    });
    runChain(nodes);
  }

  // Expose pure helpers / timing constants for optional unit hooks
  window.SuiteHomeTypewriter = {
    typewriterPrefix: typewriterPrefix,
    typewriterDone: typewriterDone,
    typeElement: typeElement,
    delayMsFor: delayMsFor,
    DEFAULT_MS: DEFAULT_MS,
    WELCOME_MS: WELCOME_MS,
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
