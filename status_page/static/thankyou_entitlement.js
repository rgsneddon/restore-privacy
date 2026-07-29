/* Thank-you: defer entitlement auto-fetch after installer iframe. CSP: self. */
(function () {
  var delayMs = 1800;
  var ent = document.getElementById("auto-entitlement-frame");
  if (!ent) return;
  var src = ent.getAttribute("data-src") || "";
  if (!src) return;
  setTimeout(function () {
    ent.setAttribute("src", src);
  }, delayMs);
})();
