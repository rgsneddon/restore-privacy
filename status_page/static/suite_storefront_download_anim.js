/**
 * Refine suite storefront foot download animation href from navigator.userAgent.
 * CSP: script-src 'self' only (no inline). Same free_direct path as FREE DOWNLOAD CTA.
 */
(function () {
  var a = document.getElementById("suite-storefront-download-anim-link");
  if (!a) return;
  var ua = (navigator.userAgent || "").toLowerCase();
  var plat = "";
  if (/android/.test(ua)) plat = "android";
  else if (/iphone|ipad|ipod/.test(ua)) plat = "ios";
  else if (/mac os x|macintosh/.test(ua) && !/iphone|ipad|ipod/.test(ua))
    plat = "macos";
  else if (/windows/.test(ua)) plat = "windows";
  else if (/cros|linux/.test(ua)) plat = "linux";
  if (!plat) return;
  var href = "/suite/download?platform=" + plat + "&free_direct=1";
  a.setAttribute("href", href);
  a.setAttribute("data-platform", plat);
  a.setAttribute("data-detected-platform", plat);
  a.setAttribute("data-href-kind", "suite_free_direct");
  a.setAttribute("data-free-direct", "1");
  a.setAttribute("data-pay", "0");
  a.removeAttribute("data-fallback-map");
})();
