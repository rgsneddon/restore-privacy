/* Thank-you page: copy keygen to clipboard. CSP: script-src 'self' only. */
(function () {
  var btn = document.getElementById("keygen-copy-btn");
  var code = document.getElementById("product-keygen");
  var status = document.getElementById("keygen-copy-status");
  if (!btn || !code) return;
  function done(ok) {
    if (status) status.textContent = ok ? "Copied!" : "Select and copy manually";
  }
  btn.addEventListener("click", function () {
    var text = (code.textContent || "").trim();
    if (!text) return;
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard
        .writeText(text)
        .then(function () {
          done(true);
        })
        .catch(function () {
          try {
            var r = document.createRange();
            r.selectNodeContents(code);
            var s = window.getSelection();
            s.removeAllRanges();
            s.addRange(r);
            done(document.execCommand("copy"));
          } catch (e) {
            done(false);
          }
        });
    } else {
      try {
        var r2 = document.createRange();
        r2.selectNodeContents(code);
        var s2 = window.getSelection();
        s2.removeAllRanges();
        s2.addRange(r2);
        done(document.execCommand("copy"));
      } catch (e2) {
        done(false);
      }
    }
  });
})();
