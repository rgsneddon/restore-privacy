/**
 * Normalize request pathnames for perc internet_node behind nginx /perc/ strip.
 *
 * Helsinki nginx:
 *   location /perc/ { proxy_pass http://127.0.0.1:9478/; }
 * strips the /perc/ prefix before the Node process sees the path.
 *
 * Wallets use rendezvousUrl ending in `/perc` and then append `/perc/status`
 * (etc.), so the public URL is `/perc/perc/status` → Node sees `/perc/status`.
 *
 * Clients that call `/perc/status` once (base host without /perc, or naive join)
 * reach Node as `/status` after the strip — which previously 404'd.
 *
 * This helper maps both shapes onto the canonical `/perc/...` routes used by
 * internet_node handlers, without breaking direct-to-port or double-prefix.
 */

/**
 * @param {string} pathname
 * @returns {string}
 */
export function normalizeInternetPathname(pathname) {
  let p = String(pathname || '/');
  if (!p.startsWith('/')) p = `/${p}`;

  // Collapse accidental double mount: /perc/perc/... → /perc/...
  while (p.startsWith('/perc/perc/') || p === '/perc/perc') {
    p = p === '/perc/perc' ? '/perc' : p.slice('/perc'.length);
  }

  // Nginx-stripped forms (no leading /perc) → canonical /perc/* routes.
  if (p === '/status') return '/perc/status';
  if (p === '/ledger') return '/perc/ledger';
  if (p.startsWith('/rendezvous/')) return `/perc${p}`;

  // health stays root-relative (handler is GET /health) after nginx strip of /perc/health.
  // api/*, explorer UI, public/* already arrive correctly stripped.

  return p;
}
