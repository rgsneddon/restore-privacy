/* GOD page: learn-from-input + dashboard refresh. */
(function () {
  const input = document.getElementById("god-learn-input");
  const submit = document.getElementById("god-learn-submit");
  const answer = document.getElementById("god-learn-answer");
  if (!submit || !input) return;
  submit.addEventListener("click", async function () {
    const body = { input: input.value || "" };
    try {
      const res = await fetch("/api/learn", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (answer) {
        answer.hidden = false;
        answer.textContent = data.answer || JSON.stringify(data);
      }
    } catch (err) {
      if (answer) {
        answer.hidden = false;
        answer.textContent = "learn failed";
      }
    }
  });
})();
