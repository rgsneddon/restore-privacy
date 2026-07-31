/* Admin support tickets: one-way open→closed toggle.
 * CSP: script-src 'self' only — no inline handlers.
 * Primary close path is native <button type="submit"> (works without JS).
 * This script only guards double-submit after the first close POST starts.
 */
(function (root) {
  "use strict";

  function onReady(fn) {
    if (root.document.readyState === "loading") {
      root.document.addEventListener("DOMContentLoaded", fn);
    } else {
      fn();
    }
  }

  function wireSupportCloseForms() {
    var table = root.document.getElementById("admin-support-table");
    if (!table) return;

    table.addEventListener(
      "submit",
      function (ev) {
        var form = ev.target;
        if (!form || !form.classList || !form.classList.contains("admin-support-close-form")) {
          return;
        }
        if (form.getAttribute("data-submitting") === "1") {
          ev.preventDefault();
          return;
        }
        form.setAttribute("data-submitting", "1");
        var btn = form.querySelector("button.ticket-toggle-submit");
        if (btn) {
          // After submit is committed — do not disable before browser queues POST.
          root.setTimeout(function () {
            try {
              btn.disabled = true;
            } catch (e) {
              /* ignore */
            }
          }, 0);
        }
      },
      false
    );
  }

  onReady(wireSupportCloseForms);
})(typeof window !== "undefined" ? window : this);
