/**
 * Service worker: Connect/Disconnect browser-scoped proxy via pure vpn_core.
 */
/* global chrome, importScripts, RptBrowserVpnCore, RptProxyAdapter */

importScripts("lib/vpn_core.js", "lib/proxy_adapter.js");

var STORAGE_KEY = "rpt_browser_vpn_state";
var core = RptBrowserVpnCore;
var adapter = null;

try {
  adapter = RptProxyAdapter.createProxyAdapter(chrome);
} catch (e) {
  console.warn("RPT browser extension: proxy adapter init failed", e);
}

function loadState() {
  return new Promise(function (resolve) {
    chrome.storage.local.get([STORAGE_KEY], function (data) {
      resolve(data[STORAGE_KEY] || core.defaultState());
    });
  });
}

function saveState(state) {
  return new Promise(function (resolve) {
    var payload = {};
    payload[STORAGE_KEY] = state;
    chrome.storage.local.set(payload, function () {
      resolve(state);
    });
  });
}

function setBadge(state) {
  var connected = core.isConnected(state);
  chrome.action.setBadgeText({ text: connected ? "ON" : "" });
  chrome.action.setBadgeBackgroundColor({
    color: connected ? "#39ff6a" : "#666666",
  });
}

/**
 * Verify product KEYGEN against status host /api/connect-entitlement.
 * @param {string} keygen normalized product keygen
 * @returns {Promise<object>} entitlement JSON (connect_allowed, status, …)
 */
function verifyKeygenWithStatusHost(keygen) {
  var url =
    core.CONNECT_ENTITLEMENT_URL +
    "?keygen=" +
    encodeURIComponent(keygen);
  return fetch(url, {
    method: "GET",
    credentials: "omit",
    cache: "no-store",
  }).then(function (resp) {
    if (!resp || !resp.ok) {
      return {
        connect_allowed: false,
        status: "unknown",
        error: "status_host_http_" + (resp && resp.status),
      };
    }
    return resp.json().then(
      function (body) {
        return body && typeof body === "object"
          ? body
          : { connect_allowed: false, status: "unknown", error: "bad_json" };
      },
      function () {
        return {
          connect_allowed: false,
          status: "unknown",
          error: "bad_json",
        };
      }
    );
  });
}

async function connect(opts) {
  var prev = await loadState();
  var next = core.enableVpn(prev, opts || {});
  if (next.status === core.STATUS.ERROR) {
    await saveState(next);
    setBadge(next);
    return next;
  }
  if (adapter && next.proxyConfig) {
    try {
      await adapter.applyProxyConfig(next.proxyConfig);
    } catch (err) {
      // Proxy apply failure must not wipe one-time KEYGEN unlock.
      next = {
        status: core.STATUS.ERROR,
        proxyConfig: null,
        error: String(err && err.message ? err.message : err),
        browserScopeOnly: true,
        productTitle: next.productTitle,
        catalogVersion: next.catalogVersion,
        keygenUnlocked: !!next.keygenUnlocked,
        keygenStored: next.keygenStored || "",
      };
      await saveState(next);
      setBadge(next);
      return next;
    }
  }
  await saveState(next);
  setBadge(next);
  return next;
}

async function disconnect() {
  var prev = await loadState();
  if (adapter) {
    try {
      await adapter.clearProxyConfig();
    } catch (err) {
      var failed = core.disableVpn(prev);
      failed.status = core.STATUS.ERROR;
      failed.error = String(err && err.message ? err.message : err);
      await saveState(failed);
      setBadge(failed);
      return failed;
    }
  }
  var next = core.disableVpn(prev);
  await saveState(next);
  setBadge(next);
  return next;
}

chrome.runtime.onInstalled.addListener(function () {
  loadState().then(setBadge);
});

chrome.runtime.onStartup.addListener(function () {
  loadState().then(async function (state) {
    // Re-apply proxy if we were connected (browser restart)
    if (core.isConnected(state) && adapter && state.proxyConfig) {
      try {
        await adapter.applyProxyConfig(state.proxyConfig);
      } catch (e) {
        state = core.disableVpn(state);
        state.error = "re-apply failed: " + e;
        await saveState(state);
      }
    }
    setBadge(state);
  });
});

chrome.runtime.onMessage.addListener(function (msg, _sender, sendResponse) {
  if (!msg || !msg.type) {
    sendResponse({ ok: false, error: "bad message" });
    return false;
  }
  if (msg.type === "get_status") {
    loadState().then(function (state) {
      sendResponse({
        ok: true,
        state: state,
        disclaimer: core.browserScopeDisclaimer(),
      });
    });
    return true;
  }
  if (msg.type === "connect") {
    connect(msg.opts || {}).then(function (state) {
      sendResponse({ ok: state.status !== core.STATUS.ERROR, state: state });
    });
    return true;
  }
  if (msg.type === "disconnect") {
    disconnect().then(function (state) {
      sendResponse({ ok: true, state: state });
    });
    return true;
  }
  if (msg.type === "unlock_keygen") {
    loadState().then(async function (prev) {
      var raw = msg.keygen || "";
      var shapeOnly = core.unlockWithKeygen(prev, raw, null);
      // Fail closed on empty/invalid shape without hitting the host.
      if (!core.looksLikeProductKeygen(raw)) {
        await saveState(shapeOnly);
        setBadge(shapeOnly);
        sendResponse({
          ok: false,
          state: shapeOnly,
          error: shapeOnly.error || null,
        });
        return;
      }
      var kg = core.normalizeKeygen(raw);
      var hostResult;
      try {
        hostResult = await verifyKeygenWithStatusHost(kg);
      } catch (err) {
        hostResult = {
          connect_allowed: false,
          status: "unknown",
          error: String(err && err.message ? err.message : err),
        };
      }
      var next = core.unlockWithKeygen(prev, kg, hostResult);
      await saveState(next);
      setBadge(next);
      sendResponse({
        ok: core.isKeygenUnlocked(next),
        state: next,
        error: next.error || null,
      });
    });
    return true;
  }
  sendResponse({ ok: false, error: "unknown type" });
  return false;
});
