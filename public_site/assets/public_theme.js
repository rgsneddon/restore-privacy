/* Public site theme (light / dark / device). CSP: script-src 'self' only. */
(function () {
  var el = document.currentScript;
  var KEY =
    (el && el.getAttribute("data-storage-key")) || "rpt_public_theme";
  function resolve(mode) {
    if (mode === "light" || mode === "dark") return mode;
    try {
      return window.matchMedia("(prefers-color-scheme: light)").matches
        ? "light"
        : "dark";
    } catch (e) {
      return "dark";
    }
  }
  function apply(mode) {
    var root = document.documentElement;
    var m = mode || "system";
    if (m === "system" || m === "device") {
      root.removeAttribute("data-theme");
      root.setAttribute("data-theme-pref", "device");
    } else {
      root.setAttribute("data-theme", m);
      root.setAttribute("data-theme-pref", m);
    }
  }
  function load() {
    try {
      return localStorage.getItem(KEY) || "device";
    } catch (e) {
      return "device";
    }
  }
  function save(mode) {
    try {
      localStorage.setItem(KEY, mode);
    } catch (e) {}
  }
  var initial = load();
  if (initial === "system") initial = "device";
  apply(initial);
  function wire() {
    var radios = document.querySelectorAll('input[name="public-theme"]');
    if (!radios.length) return;
    radios.forEach(function (r) {
      r.checked =
        r.value === initial || (initial === "device" && r.value === "device");
      r.addEventListener("change", function () {
        if (!r.checked) return;
        save(r.value);
        apply(r.value);
        initial = r.value;
      });
    });
    try {
      window
        .matchMedia("(prefers-color-scheme: light)")
        .addEventListener("change", function () {
          if ((load() || "device") === "device") apply("device");
        });
    } catch (e) {}
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", wire);
  } else {
    wire();
  }
})();
