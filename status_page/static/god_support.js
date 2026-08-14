/* GOD support box — POST /support/god-ask (CSP script-src 'self'). */
(function () {
  var box = document.getElementById("god-support-box");
  if (!box) return;
  var input = document.getElementById("god-question");
  var btn = document.getElementById("god-ask-submit");
  var out = document.getElementById("god-support-answer");
  var learned = document.getElementById("god-learned-count");
  var fred = document.getElementById("fred-scenario-count");
  if (!input || !btn || !out) return;

  function show(text) {
    out.hidden = false;
    out.textContent = text;
  }

  async function ask() {
    var q = String(input.value || "").trim();
    if (!q) {
      show("Ask GOD a question first.");
      return;
    }
    btn.disabled = true;
    show("GOD is thinking…");
    try {
      var res = await fetch(box.getAttribute("data-ask-path") || "/support/god-ask", {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ question: q }),
      });
      var data = {};
      try {
        data = await res.json();
      } catch (e) {
        data = {};
      }
      if (!res.ok || !data.ok) {
        show(data.error || "GOD could not answer just now.");
        return;
      }
      if (learned) learned.textContent = String(data.learned || 0);
      if (fred && data.fred) fred.textContent = String(data.fred.count || 0);
      show(data.answer || "");
    } catch (err) {
      show("Network error talking to GOD.");
    } finally {
      btn.disabled = false;
    }
  }

  btn.addEventListener("click", function (ev) {
    ev.preventDefault();
    ask();
  });
})();
