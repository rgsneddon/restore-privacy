/**
 * Popup UI: Connect / Disconnect + status for browser-scoped VPN.
 */
(function () {
  "use strict";

  var statusText = document.getElementById("status-text");
  var errorText = document.getElementById("error-text");
  var disclaimer = document.getElementById("disclaimer");
  var btnConnect = document.getElementById("btn-connect");
  var btnDisconnect = document.getElementById("btn-disconnect");
  var panel = document.getElementById("panel");
  var keygenGate = document.getElementById("keygen-gate");
  var keygenInput = document.getElementById("keygen-input");
  var btnUnlock = document.getElementById("btn-unlock");

  function render(state, disc) {
    var status = (state && state.status) || "disconnected";
    var unlocked = !!(state && state.keygenUnlocked && state.keygenStored);
    statusText.textContent = status;
    panel.classList.toggle("is-connected", status === "connected");
    if (keygenGate) {
      keygenGate.hidden = unlocked;
    }
    if (state && state.error) {
      errorText.hidden = false;
      errorText.textContent = state.error;
    } else {
      errorText.hidden = true;
      errorText.textContent = "";
    }
    if (disc) {
      disclaimer.textContent = disc;
    }
    btnConnect.disabled = !unlocked || status === "connected";
    btnDisconnect.disabled = status === "disconnected";
  }

  function send(type, opts) {
    return new Promise(function (resolve) {
      var payload = { type: type, opts: opts || {} };
      if (opts && opts.keygen != null) {
        payload.keygen = opts.keygen;
      }
      chrome.runtime.sendMessage(payload, function (resp) {
        resolve(resp || { ok: false, error: "no response" });
      });
    });
  }

  async function refresh() {
    var resp = await send("get_status");
    if (resp && resp.state) {
      render(resp.state, resp.disclaimer);
    } else {
      statusText.textContent = "error";
      errorText.hidden = false;
      errorText.textContent = (resp && resp.error) || "status unavailable";
    }
  }

  btnConnect.addEventListener("click", async function () {
    btnConnect.disabled = true;
    var resp = await send("connect", {});
    if (resp && resp.state) {
      render(resp.state, disclaimer.textContent);
    }
    await refresh();
  });

  btnDisconnect.addEventListener("click", async function () {
    btnDisconnect.disabled = true;
    var resp = await send("disconnect");
    if (resp && resp.state) {
      render(resp.state, disclaimer.textContent);
    }
    await refresh();
  });

  if (btnUnlock) {
    btnUnlock.addEventListener("click", async function () {
      btnUnlock.disabled = true;
      var kg = keygenInput ? keygenInput.value : "";
      var resp = await send("unlock_keygen", { keygen: kg });
      if (resp && resp.state) {
        render(resp.state, disclaimer.textContent);
      }
      if (resp && !resp.ok && resp.error) {
        errorText.hidden = false;
        errorText.textContent = resp.error;
      }
      btnUnlock.disabled = false;
      await refresh();
    });
  }

  refresh();
})();
