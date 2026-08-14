/**
 * Mineperc miner-box helpers: longest-string sizing + per-part copy payload.
 * Used by the public pool page and unit tests.
 */

export function longestPartLength(parts) {
  const list = Array.isArray(parts) ? parts : [];
  if (!list.length) return 0;
  return Math.max(0, ...list.map((p) => String(p ?? '').length));
}

/** CSS min-width in `ch` so a box is at least as wide as the longest miner string. */
export function minWidthChFromParts(parts, pad = 1) {
  const extra = Number.isFinite(pad) ? Math.max(0, pad) : 1;
  return longestPartLength(parts) + extra;
}

/** Exact clipboard payload for one miner part (never the whole page). */
export function copyPayloadForPart(text) {
  return String(text ?? '');
}

export function collectPartTexts(nodes) {
  const list = Array.from(nodes || []);
  return list.map((n) => copyPayloadForPart(n && n.textContent));
}
