/**
 * Node unit tests for shipped browser_extension/lib/vpn_core.js
 * Run: node browser_extension/test/vpn_core.test.js
 */
"use strict";

var path = require("path");
var assert = require("assert");
var core = require(path.join(__dirname, "..", "lib", "vpn_core.js"));

/** Product-shaped fixture (12 hex) — not a live mint. */
var FIXTURE_KEYGEN = "RPT-KEY-ABCD-EF01-2345";
/** Host entitlement confirm used by pure unit tests (no network). */
var HOST_OK = { connect_allowed: true, status: "active" };

function test(name, fn) {
  try {
    fn();
    console.log("ok -", name);
  } catch (e) {
    console.error("FAIL -", name);
    console.error(e);
    process.exitCode = 1;
  }
}

test("default state is disconnected without proxy", function () {
  var s = core.defaultState();
  assert.strictEqual(s.status, "disconnected");
  assert.strictEqual(s.proxyConfig, null);
  assert.strictEqual(s.browserScopeOnly, true);
  assert.strictEqual(core.isConnected(s), false);
});

test("Connect blocked without KEYGEN unlock", function () {
  var s = core.enableVpn(core.defaultState(), {
    host: "127.0.0.1",
    port: 1080,
  });
  assert.strictEqual(s.status, "error");
  assert.strictEqual(s.proxyConfig, null);
  assert.ok(String(s.error).toLowerCase().indexOf("keygen") >= 0);
  assert.strictEqual(core.isKeygenUnlocked(core.defaultState()), false);
});

test("looksLikeProductKeygen requires RPT-KEY-XXXX-XXXX-XXXX hex shape", function () {
  assert.strictEqual(core.looksLikeProductKeygen(FIXTURE_KEYGEN), true);
  assert.strictEqual(
    core.looksLikeProductKeygen("rpt-key-abcd-ef01-2345"),
    true
  );
  assert.strictEqual(core.looksLikeProductKeygen("RPT-KEY-TEST-TEST-TEST"), false);
  assert.strictEqual(core.looksLikeProductKeygen("RPT-KEY-"), false);
  assert.strictEqual(core.looksLikeProductKeygen("deadbeefcafe"), false);
  assert.strictEqual(
    core.normalizeKeygen("RPTKEYabcdef012345"),
    "RPT-KEY-ABCD-EF01-2345"
  );
});

test("unlockWithKeygen requires host connect_allowed (not shape theater)", function () {
  var noHost = core.unlockWithKeygen(null, FIXTURE_KEYGEN);
  assert.strictEqual(core.isKeygenUnlocked(noHost), false);
  assert.ok(String(noHost.error).toLowerCase().indexOf("status host") >= 0);

  var inactive = core.unlockWithKeygen(null, FIXTURE_KEYGEN, {
    connect_allowed: false,
    status: "unknown",
    reason: "no_entitlement",
  });
  assert.strictEqual(core.isKeygenUnlocked(inactive), false);
  assert.ok(String(inactive.error).toLowerCase().indexOf("not active") >= 0);

  var weak = core.unlockWithKeygen(null, "RPT-KEY-TEST-TEST-TEST", HOST_OK);
  assert.strictEqual(core.isKeygenUnlocked(weak), false);
});

test("unlockWithKeygen then enableVpn connects once unlocked", function () {
  var unlocked = core.unlockWithKeygen(
    core.defaultState(),
    FIXTURE_KEYGEN,
    HOST_OK
  );
  assert.strictEqual(core.isKeygenUnlocked(unlocked), true);
  var s = core.enableVpn(unlocked, {
    host: "127.0.0.1",
    port: 1080,
    scheme: "socks5",
  });
  assert.strictEqual(s.status, "connected");
  assert.ok(s.proxyConfig);
  assert.strictEqual(s.proxyConfig.mode, "fixed_servers");
  assert.strictEqual(s.proxyConfig.rules.singleProxy.host, "127.0.0.1");
  assert.strictEqual(s.proxyConfig.rules.singleProxy.port, 1080);
  assert.strictEqual(s.proxyConfig.rules.singleProxy.scheme, "socks5");
  assert.strictEqual(core.isConnected(s), true);
  assert.strictEqual(core.getStatus(s), "connected");
  // KEYGEN remains after connect
  assert.strictEqual(core.isKeygenUnlocked(s), true);
});

test("disableVpn clears proxy but keeps KEYGEN unlock", function () {
  var unlocked = core.unlockWithKeygen(null, FIXTURE_KEYGEN, HOST_OK);
  var on = core.enableVpn(unlocked, { host: "10.0.0.1", port: 9050 });
  assert.strictEqual(core.isConnected(on), true);
  var off = core.disableVpn(on);
  assert.strictEqual(off.status, "disconnected");
  assert.strictEqual(off.proxyConfig, null);
  assert.strictEqual(core.isConnected(off), false);
  assert.strictEqual(core.isKeygenUnlocked(off), true);
});

test("invalid KEYGEN rejected; invalid port after unlock still errors", function () {
  var bad = core.unlockWithKeygen(null, "x", HOST_OK);
  assert.strictEqual(core.isKeygenUnlocked(bad), false);
  var unlocked = core.unlockWithKeygen(null, FIXTURE_KEYGEN, HOST_OK);
  var s = core.enableVpn(unlocked, { host: "127.0.0.1", port: 0 });
  assert.strictEqual(s.status, "error");
  assert.strictEqual(s.proxyConfig, null);
  assert.ok(s.error);
  // enableVpn error path preserves KEYGEN fields
  assert.strictEqual(core.isKeygenUnlocked(s), true);
});

test("disclaimer is browser-scope honest (not OS residual TUN)", function () {
  var d = core.browserScopeDisclaimer().toLowerCase();
  assert.ok(d.indexOf("browser") >= 0);
  assert.ok(d.indexOf("residual") >= 0 || d.indexOf("tun") >= 0);
  assert.ok(d.indexOf("does not create") >= 0 || d.indexOf("not") >= 0);
});

test("proxy adapter apply + clear with mock chrome", function () {
  var adapterFactory = require(path.join(
    __dirname,
    "..",
    "lib",
    "proxy_adapter.js"
  ));
  var applied = null;
  var cleared = false;
  var mock = {
    runtime: { lastError: null },
    proxy: {
      settings: {
        set: function (details, cb) {
          applied = details.value;
          cb();
        },
        clear: function (_details, cb) {
          cleared = true;
          applied = null;
          cb();
        },
      },
    },
  };
  var ad = adapterFactory.createProxyAdapter(mock);
  var unlocked = core.unlockWithKeygen(null, FIXTURE_KEYGEN, HOST_OK);
  var state = core.enableVpn(unlocked, { host: "127.0.0.1", port: 1080 });
  return ad.applyProxyConfig(state.proxyConfig).then(function () {
    assert.ok(applied);
    assert.strictEqual(applied.mode, "fixed_servers");
    return ad.clearProxyConfig().then(function () {
      assert.strictEqual(cleared, true);
      assert.strictEqual(applied, null);
    });
  });
});

// Run async adapter test last
test("proxy adapter async path", function () {
  // sync-style harness already scheduled promises; wait via process tick below
});

Promise.resolve()
  .then(function () {
    var adapterFactory = require(path.join(
      __dirname,
      "..",
      "lib",
      "proxy_adapter.js"
    ));
    var applied = null;
    var mock = {
      runtime: { lastError: null },
      proxy: {
        settings: {
          set: function (details, cb) {
            applied = details.value;
            cb();
          },
          clear: function (_d, cb) {
            applied = null;
            cb();
          },
        },
      },
    };
    var ad = adapterFactory.createProxyAdapter(mock);
    var unlocked = core.unlockWithKeygen(null, FIXTURE_KEYGEN, HOST_OK);
    var state = core.enableVpn(unlocked, { host: "127.0.0.1", port: 1080 });
    return ad.applyProxyConfig(state.proxyConfig).then(function () {
      assert.strictEqual(applied.mode, "fixed_servers");
      return ad.clearProxyConfig().then(function () {
        assert.strictEqual(applied, null);
        console.log("ok - proxy adapter apply/clear with mock chrome");
      });
    });
  })
  .catch(function (e) {
    console.error("FAIL - proxy adapter", e);
    process.exitCode = 1;
  })
  .then(function () {
    if (process.exitCode) {
      process.exit(process.exitCode);
    }
    console.log("ALL PASS");
  });
