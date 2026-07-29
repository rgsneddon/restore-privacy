/* Admin left sidebar collapse. CSP: script-src 'self' only. */
(function () {
  var sb = document.getElementById("admin-sidebar");
  var btn = document.getElementById("admin-sidebar-toggle");
  if (!sb || !btn) return;
  var key = "rpt_admin_sidebar_collapsed";
  function apply(c) {
    if (c) {
      sb.classList.add("collapsed");
      btn.setAttribute("aria-expanded", "false");
      btn.textContent = "\u00bb";
    } else {
      sb.classList.remove("collapsed");
      btn.setAttribute("aria-expanded", "true");
      btn.textContent = "Collapse";
    }
  }
  try {
    apply(localStorage.getItem(key) === "1");
  } catch (e) {}
  btn.addEventListener("click", function () {
    var c = !sb.classList.contains("collapsed");
    apply(c);
    try {
      localStorage.setItem(key, c ? "1" : "0");
    } catch (e) {}
  });
})();
