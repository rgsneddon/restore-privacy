/**
 * Pure browser-VPN state machine (no Chrome APIs).
 *
 * Connect applies a browser-scoped proxy routing config; Disconnect clears it.
 * This is NOT OS residual TUN / Packet Tunnel / Wintun — only browser traffic
 * subject to chrome.proxy (or equivalent) is affected.
 *
 * Loadable by: service worker (importScripts), Node unit tests (require/vm).
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else {
    root.RptBrowserVpnCore = factory();
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  /** Product browser-path defaults (honest SOCKS-class proxy config for browser scope). */
  var PRODUCT_BROWSER_PROXY = {
    scheme: "socks5",
    // Local companion / future browser bridge — not a claim the remote residual
    // UDP node is a public SOCKS server. Operators may override via storage.
    host: "127.0.0.1",
    port: 1080,
    bypassList: ["localhost", "127.0.0.1", "<local>"],
  };

  var STATUS = {
    DISCONNECTED: "disconnected",
    CONNECTED: "connected",
    ERROR: "error",
  };

  function defaultState() {
    return {
      status: STATUS.DISCONNECTED,
      proxyConfig: null,
      error: null,
      browserScopeOnly: true,
      productTitle: "RESTORE PRIVACY SUITE",
      catalogVersion: "1.0.2",
      /** One-time KEYGEN unlock for this extension product on this device. */
      keygenUnlocked: false,
      keygenStored: "",
    };
  }

  /**
   * True when a valid KEYGEN has been entered once for this app product.
   * @param {object} state
   * @returns {boolean}
   */
  function isKeygenUnlocked(state) {
    if (!state || typeof state !== "object") return false;
    return state.keygenUnlocked === true && String(state.keygenStored || "").trim().length > 0;
  }

  /**
   * Accept a fulfilment KEYGEN once for this extension (does not re-verify host).
   * Minimal shape: non-empty RPT-KEY-… or long token (same family as Suite KEYGEN).
   * @param {object} [prev]
   * @param {string} keygen
   * @returns {object} next state
   */
  function unlockWithKeygen(prev, keygen) {
    var base = prev && typeof prev === "object" ? prev : defaultState();
    var k = String(keygen || "").trim();
    if (!k) {
      return Object.assign({}, base, {
        error: "Enter the KEYGEN from your fulfilment email to unlock this app.",
        keygenUnlocked: false,
        keygenStored: "",
      });
    }
    var ok =
      /^RPT-KEY-/i.test(k) ||
      (k.length >= 12 && /[A-Za-z0-9-]{12,}/.test(k));
    if (!ok) {
      return Object.assign({}, base, {
        error: "Invalid KEYGEN — paste the keygen from your fulfilment email.",
        keygenUnlocked: !!base.keygenUnlocked,
        keygenStored: base.keygenStored || "",
      });
    }
    return Object.assign({}, base, {
      keygenUnlocked: true,
      keygenStored: k,
      error: null,
    });
  }

  /**
   * Build chrome.proxy-compatible fixed_servers value (plain object).
   * @param {object} opts
   * @returns {{mode: string, rules: object}}
   */
  function buildProxyConfig(opts) {
    var o = opts || {};
    var scheme = o.scheme || PRODUCT_BROWSER_PROXY.scheme;
    var host = o.host || PRODUCT_BROWSER_PROXY.host;
    var port = Number(o.port != null ? o.port : PRODUCT_BROWSER_PROXY.port);
    var bypass = o.bypassList || PRODUCT_BROWSER_PROXY.bypassList.slice();
    if (!host || !port || port < 1 || port > 65535) {
      throw new Error("invalid proxy host/port");
    }
    return {
      mode: "fixed_servers",
      rules: {
        singleProxy: {
          scheme: String(scheme),
          host: String(host),
          port: port,
        },
        bypassList: bypass.map(String),
      },
    };
  }

  /**
   * Enable browser-scoped VPN routing (Connect).
   * @param {object} [prev]
   * @param {object} [opts] host/port/scheme/bypassList
   * @returns {object} next state
   */
  function enableVpn(prev, opts) {
    var base = prev && typeof prev === "object" ? prev : defaultState();
    if (!isKeygenUnlocked(base)) {
      return {
        status: STATUS.ERROR,
        proxyConfig: null,
        error:
          "KEYGEN required: unlock this app once with the keygen from your " +
          "fulfilment email before Connect.",
        browserScopeOnly: true,
        productTitle: base.productTitle || "RESTORE PRIVACY SUITE",
        catalogVersion: base.catalogVersion || "1.0.2",
        keygenUnlocked: false,
        keygenStored: "",
      };
    }
    try {
      var cfg = buildProxyConfig(opts);
      return {
        status: STATUS.CONNECTED,
        proxyConfig: cfg,
        error: null,
        browserScopeOnly: true,
        productTitle: base.productTitle || "RESTORE PRIVACY SUITE",
        catalogVersion: base.catalogVersion || "1.0.2",
        keygenUnlocked: true,
        keygenStored: base.keygenStored || "",
        enabledAt: Date.now(),
      };
    } catch (err) {
      return {
        status: STATUS.ERROR,
        proxyConfig: null,
        error: String(err && err.message ? err.message : err),
        browserScopeOnly: true,
        productTitle: base.productTitle || "RESTORE PRIVACY SUITE",
        catalogVersion: base.catalogVersion || "1.0.2",
        keygenUnlocked: !!base.keygenUnlocked,
        keygenStored: base.keygenStored || "",
      };
    }
  }

  /**
   * Disable browser-scoped VPN routing (Disconnect).
   * @param {object} [prev]
   * @returns {object} next state with proxyConfig cleared
   */
  function disableVpn(prev) {
    var base = prev && typeof prev === "object" ? prev : defaultState();
    return {
      status: STATUS.DISCONNECTED,
      proxyConfig: null,
      error: null,
      browserScopeOnly: true,
      productTitle: base.productTitle || "RESTORE PRIVACY SUITE",
      catalogVersion: base.catalogVersion || "1.0.2",
      keygenUnlocked: !!base.keygenUnlocked,
      keygenStored: base.keygenStored || "",
      disabledAt: Date.now(),
    };
  }

  /** @param {object} state */
  function getStatus(state) {
    if (!state || typeof state !== "object") {
      return STATUS.DISCONNECTED;
    }
    return state.status || STATUS.DISCONNECTED;
  }

  /** True when status is connected and a non-null proxy config is present. */
  function isConnected(state) {
    return (
      getStatus(state) === STATUS.CONNECTED &&
      state.proxyConfig != null &&
      state.proxyConfig.mode === "fixed_servers"
    );
  }

  /** Honest browser-limit copy for UI. */
  function browserScopeDisclaimer() {
    return (
      "Browser-scoped only: Connect routes this browser’s traffic via the " +
      "configured local proxy path. This extension does not create OS residual " +
      "TUN / Packet Tunnel / Wintun. Use the paid native clients for system " +
      "residual VPN. See restoreprivacy.online."
    );
  }

  return {
    STATUS: STATUS,
    PRODUCT_BROWSER_PROXY: PRODUCT_BROWSER_PROXY,
    defaultState: defaultState,
    buildProxyConfig: buildProxyConfig,
    enableVpn: enableVpn,
    disableVpn: disableVpn,
    getStatus: getStatus,
    isConnected: isConnected,
    isKeygenUnlocked: isKeygenUnlocked,
    unlockWithKeygen: unlockWithKeygen,
    browserScopeDisclaimer: browserScopeDisclaimer,
  };
});
