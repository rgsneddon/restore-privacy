/* Pure helpers for audit last-run display + refresh decisions.
 * CSP: script-src 'self' only. Loaded before homepage / AUDIT page tickers.
 * Browser: globalThis.RptAuditLastRun
 * Node tests: module.exports
 */
(function (root) {
  "use strict";

  /**
   * Format ISO Z / offset timestamp like Python format_last_audit_run_display.
   * Returns "not available" for empty/invalid.
   */
  function formatLastAuditRunDisplay(iso) {
    if (!iso || typeof iso !== "string") return "not available";
    var s = iso.trim();
    if (!s) return "not available";
    var ms = Date.parse(s);
    if (isNaN(ms)) return s;
    var d = new Date(ms);
    function pad(n) {
      return n < 10 ? "0" + n : String(n);
    }
    // UTC wall clock display (matches server: YYYY-MM-DD HH:MM:SS UTC)
    return (
      d.getUTCFullYear() +
      "-" +
      pad(d.getUTCMonth() + 1) +
      "-" +
      pad(d.getUTCDate()) +
      " " +
      pad(d.getUTCHours()) +
      ":" +
      pad(d.getUTCMinutes()) +
      ":" +
      pad(d.getUTCSeconds()) +
      " UTC"
    );
  }

  /** Extract generated_at from security_audit_latest.json payload. */
  function generatedAtFromPayload(data) {
    if (!data || typeof data !== "object") return "";
    var g = data.generated_at;
    if (g == null) return "";
    return String(g).trim();
  }

  /**
   * Whether the DOM last-run should change.
   * Never invents a newer time when payload is missing/unchanged.
   */
  function shouldUpdateLastRun(prevIso, nextIso) {
    var a = (prevIso || "").trim();
    var b = (nextIso || "").trim();
    if (!b) return false;
    return a !== b;
  }

  /**
   * Apply last-run to a <time> element (id or element).
   * Returns true if text/datetime changed.
   */
  function applyLastRunToTimeElement(elOrId, iso) {
    var el =
      typeof elOrId === "string"
        ? typeof document !== "undefined"
          ? document.getElementById(elOrId)
          : null
        : elOrId;
    if (!el || !iso) return false;
    var next = String(iso).trim();
    if (!next) return false;
    var prev = (el.getAttribute("datetime") || "").trim();
    if (!shouldUpdateLastRun(prev, next)) return false;
    var disp = formatLastAuditRunDisplay(next);
    el.setAttribute("datetime", next);
    el.textContent = disp;
    return true;
  }

  /** Build cache-busted JSON URL for the last-run source. */
  function lastRunJsonUrl(nowMs) {
    var t = nowMs != null ? nowMs : Date.now();
    return "/static/security_audit_latest.json?t=" + t;
  }

  var api = {
    formatLastAuditRunDisplay: formatLastAuditRunDisplay,
    generatedAtFromPayload: generatedAtFromPayload,
    shouldUpdateLastRun: shouldUpdateLastRun,
    applyLastRunToTimeElement: applyLastRunToTimeElement,
    lastRunJsonUrl: lastRunJsonUrl,
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  }
  root.RptAuditLastRun = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
