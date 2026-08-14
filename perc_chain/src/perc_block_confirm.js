/**
 * Pool-found PERC blocks: 72 minutes until spendable from the wallet.
 */
export const CONFIRMATION_MS = 72 * 60 * 1000;

const blocks = [];
const heightSeen = new Set();

export function resetPoolBlocks() {
  blocks.length = 0;
  heightSeen.clear();
}

export function recordPoolBlock({ miner, height, jobId, foundAt } = {}) {
  const h = Number(height);
  const key = Number.isFinite(h) ? h : String(jobId || '');
  if (key === '' || heightSeen.has(key)) return null;
  const at = Number(foundAt) || Date.now();
  const rec = {
    height: Number.isFinite(h) ? h : blocks.length,
    jobId: jobId != null ? String(jobId) : '',
    miner: String(miner || '').trim() || 'anon',
    foundAt: at,
  };
  heightSeen.add(key);
  blocks.push(rec);
  return rec;
}

export function blockConfirmation(block, now = Date.now()) {
  const foundAt = Number(block?.foundAt) || 0;
  const age = Number(now) - foundAt;
  const remainingMs = Math.max(0, CONFIRMATION_MS - age);
  const confirmed = age >= CONFIRMATION_MS;
  return {
    ...block,
    ageMs: age,
    remainingMs,
    confirmed,
    spendable: confirmed,
    status: confirmed ? 'confirmed' : 'unconfirmed',
  };
}

export function listPoolBlocks(now = Date.now()) {
  return blocks
    .map((b) => blockConfirmation(b, now))
    .sort((a, b) => (b.height || 0) - (a.height || 0) || (b.foundAt || 0) - (a.foundAt || 0));
}

export function averageBlockIntervalMs(rows = blocks) {
  if (!rows || rows.length < 2) return null;
  const ordered = [...rows].sort((a, b) => a.foundAt - b.foundAt);
  let sum = 0;
  for (let i = 1; i < ordered.length; i++) {
    sum += ordered[i].foundAt - ordered[i - 1].foundAt;
  }
  return sum / (ordered.length - 1);
}

export function nextBlockEta({ now = Date.now(), rows = blocks } = {}) {
  const avg = averageBlockIntervalMs(rows);
  if (avg == null || !rows.length) {
    return { averageMs: avg, etaMs: null, lastFoundAt: rows.at?.(-1)?.foundAt ?? null };
  }
  const last = [...rows].sort((a, b) => a.foundAt - b.foundAt).at(-1);
  const etaMs = Math.max(0, last.foundAt + avg - Number(now));
  return { averageMs: avg, etaMs, lastFoundAt: last.foundAt };
}

export function confirmationSnapshot(now = Date.now()) {
  const listed = listPoolBlocks(now);
  const eta = nextBlockEta({ now, rows: blocks });
  return {
    ok: true,
    coin: 'PERC',
    confirmationMs: CONFIRMATION_MS,
    confirmationMinutes: CONFIRMATION_MS / 60000,
    spendableAfter: '72 minutes',
    averageBlockIntervalMs: eta.averageMs,
    etaNextBlockMs: eta.etaMs,
    lastFoundAt: eta.lastFoundAt,
    blocks: listed,
    confirmed: listed.filter((b) => b.confirmed).length,
    unconfirmed: listed.filter((b) => !b.confirmed).length,
  };
}
