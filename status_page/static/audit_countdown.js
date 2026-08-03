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
  var pollEveryTicksWhenRolled = 15; // faster poll after deadline until last-run advances
  var tickCount = 0;
  var awaitingNewRun = false;
  var lastSeenIso = lastRunEl ? (lastRunEl.getAttribute("datetime") || "") : "";

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
        // When timer expiry produced a newer stamp, realign countdown deadline.
        if (iso !== lastSeenIso) {
          lastSeenIso = iso;
          awaitingNewRun = false;
          var parsed = Date.parse(iso);
          if (!isNaN(parsed)) {
            deadlineMs = parsed + period * 1000;
            while (deadlineMs <= Date.now()) {
              deadlineMs += period * 1000;
            }
            if (root) {
              root.setAttribute("data-next-audit", new Date(deadlineMs).toISOString());
            }
          }
        }
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
      awaitingNewRun = true;
    }
    var rem = Math.max(0, Math.floor((deadlineMs - now) / 1000));
    el.textContent = fmt(rem);
    tickCount += 1;
    // Refresh last-run when the period rolls (timer expiry) and periodically so
    // a scheduled publish mid-period updates without full page reload.
    var interval = awaitingNewRun ? pollEveryTicksWhenRolled : pollEveryTicks;
    if (rolled || tickCount === 1 || tickCount % interval === 0) {
      refreshLastRun();
    }
  }
  tick();
  setInterval(tick, 1000);
})();
