/* Homepage node wipe / fleet rebuild countdown. CSP: script-src 'self' only. */
(function () {
  var root = document.getElementById("node-wipe-countdown");
  if (!root) return;
  var nextA = root.getAttribute("data-next-entry") || "";
  var period = parseInt(root.getAttribute("data-period-seconds") || "604800", 10);
  if (!period || period < 1) period = 604800;
  function pad(n) {
    return n < 10 ? "0" + n : String(n);
  }
  function split(sec) {
    sec = Math.max(0, Math.floor(sec));
    var d = Math.floor(sec / 86400);
    var h = Math.floor((sec % 86400) / 3600);
    var m = Math.floor((sec % 3600) / 60);
    var s = sec % 60;
    return { d: d, h: h, m: m, s: s };
  }
  function paint(prefix, sec) {
    var u = split(sec);
    var map = { days: u.d, hours: u.h, minutes: u.m, seconds: u.s };
    Object.keys(map).forEach(function (k) {
      var el = document.getElementById(prefix + "-" + k);
      if (el) el.textContent = pad(map[k]);
    });
  }
  function roll(iso) {
    var d = Date.parse(iso);
    if (isNaN(d)) return null;
    var now = Date.now();
    while (d <= now) {
      d += period * 1000;
    }
    return d;
  }
  var deadlineA = roll(nextA);
  function tick() {
    var now = Date.now();
    if (deadlineA != null) {
      while (deadlineA <= now) {
        deadlineA += period * 1000;
      }
      paint("nw-entry", Math.max(0, Math.floor((deadlineA - now) / 1000)));
    }
  }
  tick();
  setInterval(tick, 1000);
})();
