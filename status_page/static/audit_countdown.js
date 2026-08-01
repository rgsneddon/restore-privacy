/* Homepage audit countdown ticker + last-run refresh. CSP: script-src 'self' only. */
(function () {
  var root = document.getElementById("audit-countdown");
  var el = document.getElementById("audit-countdown-value");
  if (!root || !el) return;
  var nextIso = root.getAttribute("data-next-audit") || "";
  var available = root.getAttribute("data-available") === "1";
  var lastRunEl = document.getElementById("audit-last-run-time");
  var helpers = globalThis.RptAuditLastRun || null;
  var pollEveryTicks = 60; // ~60s light poll for new generated_at
  var tickCount = 0;

  function pad(n) {
    return n < 10 ? "0" + n : String(n);
  }
  function fmt(sec) {
    sec = Math.max(0, Math.floor(sec));
    var d = Math.floor(sec / 86400);
    var h = Math.floor((sec % 86400) / 3600);
    var m = Math.floor((sec % 3600) / 60);
    var s = sec % 60;
    return d + "d " + pad(h) + ":" + pad(m) + ":" + pad(s);
  }

  var period = parseInt(root.getAttribute("data-period-seconds") || "86400", 10);
  if (!period || period < 1) period = 86400;
  var deadlineMs = Date.parse(nextIso);

  function refreshLastRun() {
    if (!helpers || !lastRunEl || typeof fetch !== "function") return;
    var url = helpers.lastRunJsonUrl(Date.now());
    fetch(url, {
      credentials: "same-origin",
      cache: "no-store",
      headers: { Accept: "application/json" },
    })
      .then(function (resp) {
        if (!resp.ok) return null;
        return resp.json();
      })
      .then(function (data) {
        var iso = helpers.generatedAtFromPayload(data);
        if (!iso) return;
        helpers.applyLastRunToTimeElement(lastRunEl, iso);
      })
      .catch(function () {
        /* honest: leave last-run unchanged if fetch fails */
      });
  }

  function tick() {
    if (!available || !nextIso || isNaN(deadlineMs)) {
      el.textContent = "—";
      return;
    }
    var now = Date.now();
    var rolled = false;
    while (deadlineMs <= now) {
      deadlineMs += period * 1000;
      rolled = true;
    }
    var rem = Math.max(0, Math.floor((deadlineMs - now) / 1000));
    el.textContent = fmt(rem);
    tickCount += 1;
    // Refresh last-run when the period rolls (may coincide with a new audit write)
    // and on a light periodic poll so an audit mid-period updates without reload.
    if (rolled || tickCount === 1 || tickCount % pollEveryTicks === 0) {
      refreshLastRun();
    }
  }
  tick();
  setInterval(tick, 1000);
})();
