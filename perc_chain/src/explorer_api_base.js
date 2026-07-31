/**
 * Shared pure helper for Perccent explorer API base path.
 * Mirrors the function shipped in public/index.html (keep in sync).
 *
 * When the explorer is reverse-proxied at /perc/, API calls must go to
 * /perc/api/network — not site-root /api/network (404 on the edge host).
 */

/**
 * @param {string} pathname location.pathname
 * @returns {string} prefix with no trailing slash ("/perc" or "")
 */
export function explorerApiBase(pathname) {
  const p = String(pathname || '/');
  if (p === '/perc' || p.startsWith('/perc/')) {
    return '/perc';
  }
  const lastSlash = p.lastIndexOf('/');
  if (lastSlash > 0) {
    const dir = p.slice(0, lastSlash);
    if (dir && dir !== '/') return dir.replace(/\/$/, '') || '';
  }
  return '';
}

/**
 * @param {string} path relative API path (with or without leading slash)
 * @param {string} [pathname] location.pathname
 * @returns {string} absolute path for fetch/href
 */
export function explorerApiUrl(path, pathname = '/') {
  const base = explorerApiBase(pathname);
  const rel = String(path || '').replace(/^\//, '');
  if (!base) return '/' + rel;
  return base + '/' + rel;
}
