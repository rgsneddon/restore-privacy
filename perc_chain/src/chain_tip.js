/**
 * Single perc_chain tip-height source.
 * Pool jobs, mineperc stats/HTML, and explorer network snapshots all read this.
 */
import { blockHeight } from './ledger_store.js';

export const DEFAULT_PERC_NODE_URL =
  process.env.PERC_NODE_URL || 'https://135.181.152.10.sslip.io/perc';

let boundLedger = null;
let remoteTipHeight = 0;

/** Ledger tip height — the only number jobs / stats / explorer should share. */
export function percChainTipHeight(ledger) {
  return blockHeight(ledger);
}

export function percChainTipFromHealth(payload) {
  if (!payload || typeof payload !== 'object') return 0;
  return Number(payload.blockHeight ?? payload.networkHeight ?? 0) || 0;
}

export function bindPoolToLedger(ledger) {
  boundLedger = ledger && typeof ledger === 'object' ? ledger : null;
}

export function setPoolTipHeight(height) {
  remoteTipHeight = Math.max(0, Number(height) || 0);
}

export function resetPoolTip() {
  boundLedger = null;
  remoteTipHeight = 0;
}

export function currentPoolTipHeight() {
  if (boundLedger) return percChainTipHeight(boundLedger);
  return remoteTipHeight;
}

export function percChainTipHealthUrl(nodeUrl = DEFAULT_PERC_NODE_URL) {
  const base = String(nodeUrl || DEFAULT_PERC_NODE_URL).replace(/\/+$/, '');
  return `${base}/health`;
}

export async function fetchPercChainTipHeight({
  url,
  nodeUrl = DEFAULT_PERC_NODE_URL,
  fetchImpl = globalThis.fetch,
} = {}) {
  const target = url || percChainTipHealthUrl(nodeUrl);
  const res = await fetchImpl(target);
  const json = typeof res.json === 'function' ? await res.json() : res;
  const height = percChainTipFromHealth(json);
  setPoolTipHeight(height);
  return height;
}
