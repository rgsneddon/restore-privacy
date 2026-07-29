/* Homepage audit countdown ticker. CSP: script-src 'self' only. */
(function () {
  var root = document.getElementById("audit-countdown");
  var el = document.getElementById("audit-countdown-value");
  if (!root || !el) return;
  var nextIso = root.getAttribute("data-next-audit") || "";
  var available = root.getAttribute("data-available") === "1";
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
  function tick() {
    if (!available || !nextIso || isNaN(deadlineMs)) {
      el.textContent = "—";
      return;
    }
    var now = Date.now();
    while (deadlineMs <= now) {
      deadlineMs += period * 1000;
    }
    var rem = Math.max(0, Math.floor((deadlineMs - now) / 1000));
    el.textContent = fmt(rem);
  }
  tick();
  setInterval(tick, 1000);
})();
