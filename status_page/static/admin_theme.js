/* Admin appearance theme. CSP: script-src 'self' only. */
(function () {
  var el = document.currentScript;
  var KEY =
    (el && el.getAttribute("data-storage-key")) || "rpt_admin_theme";
  var root = document.documentElement;
  function normalize(m) {
    m = (m || "").toLowerCase();
    if (m === "light" || m === "dark" || m === "system") return m;
    return "system";
  }
  function apply(mode) {
    mode = normalize(mode);
    if (mode === "system") {
      root.removeAttribute("data-theme");
    } else {
      root.setAttribute("data-theme", mode);
    }
    try {
      localStorage.setItem(KEY, mode);
    } catch (e) {}
    var radios = document.querySelectorAll('input[name="admin-theme"]');
    for (var i = 0; i < radios.length; i++) {
      radios[i].checked = radios[i].value === mode;
    }
  }
  var saved = "system";
  try {
    saved = normalize(localStorage.getItem(KEY));
  } catch (e) {}
  apply(saved);
  document.addEventListener("DOMContentLoaded", function () {
    apply(saved);
    var radios = document.querySelectorAll('input[name="admin-theme"]');
    for (var i = 0; i < radios.length; i++) {
      radios[i].addEventListener("change", function (ev) {
        if (ev.target && ev.target.checked) apply(ev.target.value);
      });
    }
  });
})();
