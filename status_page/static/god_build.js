/* GOD page: Grok Build CLI poll. */
(function () {
  const cli = document.getElementById("god-cli");
  const dl = document.getElementById("god-cli-download");
  if (!cli) return;
  window.godStartBuild = async function (device) {
    const res = await fetch("/api/god-build", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ device: device || "", brief: "" }),
    });
    const data = await res.json();
    if (cli) cli.textContent = (data.lines || []).join("\n");
    if (dl && data.download) {
      dl.href = data.download;
      dl.classList.add("is-ready");
    }
  };
})();
