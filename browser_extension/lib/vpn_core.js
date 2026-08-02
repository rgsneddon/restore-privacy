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
      catalogVersion: "1.0.7",
      /** One-time KEYGEN unlock for this extension product on this device. */
      keygenUnlocked: false,
      keygenStored: "",
    };
  }

  /** Product mint format: RPT-KEY-XXXX-XXXX-XXXX (12 hex after prefix). */
  var KEYGEN_PREFIX = "RPT-KEY-";
  var PRODUCT_KEYGEN_RE = /^RPT-KEY-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}$/;
  /** Status host used to confirm subscription before unlock (same as Suite). */
  var CONNECT_ENTITLEMENT_URL =
    "https://restoreprivacy.online/api/connect-entitlement";

  /**
   * Normalize customer-entered KEYGEN (uppercase, strip spaces; accept compacted forms).
   * Mirrors status_page payments.normalize_keygen product shape.
   * @param {string} [keygen]
   * @returns {string}
   */
  function normalizeKeygen(keygen) {
    var s = String(keygen || "")
      .trim()
      .toUpperCase()
      .replace(/ /g, "");
    if (!s) return "";
    // RPTKEY + 12 hex (no separators) → RPT-KEY-XXXX-XXXX-XXXX
    if (s.indexOf("RPTKEY") === 0 && s.indexOf("-") < 0 && s.length === 18) {
      var body0 = s.slice(6);
      s =
        KEYGEN_PREFIX +
        body0.slice(0, 4) +
        "-" +
        body0.slice(4, 8) +
        "-" +
        body0.slice(8, 12);
    } else if (
      s.indexOf("RPT-KEY") === 0 &&
      s.split("-").length === 2 &&
      s.length === 19
    ) {
      // RPT-KEY + 12 hex, no inner dashes
      var body1 = s.replace("RPT-KEY", "").replace(/-/g, "");
      if (body1.length === 12) {
        s =
          KEYGEN_PREFIX +
          body1.slice(0, 4) +
          "-" +
          body1.slice(4, 8) +
          "-" +
          body1.slice(8, 12);
      }
    }
    return s;
  }

  /**
   * True when raw matches product KEYGEN shape RPT-KEY-XXXX-XXXX-XXXX (12 hex).
   * Shape only — host entitlement verify is separate (background unlock path).
   * @param {string} raw
   * @returns {boolean}
   */
  function looksLikeProductKeygen(raw) {
    var kg = normalizeKeygen(raw);
    return PRODUCT_KEYGEN_RE.test(kg);
  }

  /**
   * True when a valid KEYGEN has been entered once for this app product.
   * @param {object} state
   * @returns {boolean}
   */
  function isKeygenUnlocked(state) {
    if (!state || typeof state !== "object") return false;
    return (
      state.keygenUnlocked === true &&
      looksLikeProductKeygen(state.keygenStored || "")
    );
  }

  /**
   * Accept a fulfilment KEYGEN once for this extension.
   *
   * Requires product shape RPT-KEY-XXXX-XXXX-XXXX. Production unlock path
   * (background.js) must pass hostResult from /api/connect-entitlement with
   * connect_allowed true — shape alone is not enough for a real unlock.
   *
   * Unit tests may pass { connect_allowed: true } to exercise the state machine
   * without a network hop.
   *
   * @param {object} [prev]
   * @param {string} keygen
   * @param {object} [hostResult] entitlement payload ({ connect_allowed, status, … })
   * @returns {object} next state
   */
  function unlockWithKeygen(prev, keygen, hostResult) {
    var base = prev && typeof prev === "object" ? prev : defaultState();
    var k = normalizeKeygen(keygen);
    if (!k) {
      return Object.assign({}, base, {
        error: "Enter the KEYGEN from your fulfilment email to unlock this app.",
        keygenUnlocked: false,
        keygenStored: "",
      });
    }
    if (!looksLikeProductKeygen(k)) {
      return Object.assign({}, base, {
        error:
          "Invalid KEYGEN — use format RPT-KEY-XXXX-XXXX-XXXX from your fulfilment email.",
        keygenUnlocked: !!base.keygenUnlocked,
        keygenStored: base.keygenStored || "",
      });
    }
    // Require host entitlement confirmation (connect_allowed) before unlock.
    var host = hostResult && typeof hostResult === "object" ? hostResult : null;
    if (!host) {
      return Object.assign({}, base, {
        error:
          "KEYGEN must be verified against the status host before unlock.",
        keygenUnlocked: !!base.keygenUnlocked,
        keygenStored: base.keygenStored || "",
      });
    }
    if (host.connect_allowed !== true) {
      var reason =
        host.reason ||
        host.error ||
        host.status ||
        "entitlement not active";
      return Object.assign({}, base, {
        error:
          "KEYGEN not active on status host (" +
          String(reason) +
          "). Renew or re-check fulfilment email.",
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
        catalogVersion: base.catalogVersion || "1.0.7",
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
        catalogVersion: base.catalogVersion || "1.0.7",
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
        catalogVersion: base.catalogVersion || "1.0.7",
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
      catalogVersion: base.catalogVersion || "1.0.7",
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
    KEYGEN_PREFIX: KEYGEN_PREFIX,
    CONNECT_ENTITLEMENT_URL: CONNECT_ENTITLEMENT_URL,
    defaultState: defaultState,
    buildProxyConfig: buildProxyConfig,
    enableVpn: enableVpn,
    disableVpn: disableVpn,
    getStatus: getStatus,
    isConnected: isConnected,
    isKeygenUnlocked: isKeygenUnlocked,
    normalizeKeygen: normalizeKeygen,
    looksLikeProductKeygen: looksLikeProductKeygen,
    unlockWithKeygen: unlockWithKeygen,
    browserScopeDisclaimer: browserScopeDisclaimer,
  };
});
