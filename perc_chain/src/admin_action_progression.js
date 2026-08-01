/**
 * Admin-action ChronoFlux progression (Evolve seed ledger).
 *
 * Mirrors scenario / SCS / % chance seals: a successful admin mutator mints one
 * confirmed block that carries the admin action and promotes any pending
 * relayed transfers waiting at seal time.
 */

import crypto from 'crypto';
import { acknowledgeRelayTransfers } from './transfer_relay_ack.js';
import { blockHeight } from './ledger_store.js';

export const ADMIN_ACTION_KIND = 'adminAction';
export const CHAIN_ID = 'evolve-chronoflux-principia-chain-1';

/**
 * @param {string} actionKind
 * @param {string} [label]
 * @returns {string}
 */
export function adminActionDisplayLabel(actionKind, label = '') {
  const lab = (label || '').trim();
  if (lab) return lab.length > 80 ? `${lab.slice(0, 77)}…` : lab;
  const kind = (actionKind || 'action').trim() || 'action';
  const pretty = kind
    .replace(/[_-]+/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
  return `Admin: ${pretty}`;
}

/**
 * Collect transfer-like entries from ledger.pendingInboundTransfers (if any).
 * @param {object} ledger
 * @returns {object[]}
 */
export function drainPendingInboundTransfers(ledger) {
  if (!ledger || !Array.isArray(ledger.pendingInboundTransfers)) return [];
  const pending = ledger.pendingInboundTransfers
    .filter((t) => t && typeof t === 'object')
    .map((t) => ({
      ...t,
      kind: t.kind || 'transfer',
      confirmedBy: ADMIN_ACTION_KIND,
    }));
  ledger.pendingInboundTransfers = [];
  return pending;
}

/**
 * Promote pending relayed transfers from peer relay ledgers into canonical,
 * then mint one confirmed admin-action block (SCS / % chance seal pattern).
 *
 * @param {object} ledger — mutable seed/canonical ledger
 * @param {{ actionKind: string, label?: string, memo?: string, path?: string, actor?: string }} action
 * @param {{ relayLedgers?: object[] }} [options]
 * @returns {{
 *   ok: boolean,
 *   block: object|null,
 *   height: number,
 *   confirmedRelayTxIds: string[],
 *   pendingIncluded: number,
 *   label: string,
 * }}
 */
export function mintAdminActionBlock(ledger, action, options = {}) {
  if (!ledger || typeof ledger !== 'object') {
    return {
      ok: false,
      block: null,
      height: -1,
      confirmedRelayTxIds: [],
      pendingIncluded: 0,
      label: '',
    };
  }
  if (!Array.isArray(ledger.blocks)) {
    ledger.blocks = [];
  }

  const actionKind = String(action?.actionKind || 'admin_action').trim() || 'admin_action';
  const label = adminActionDisplayLabel(actionKind, action?.label);
  const memo = String(action?.memo || '').trim();
  const path = String(action?.path || '').trim();
  const actor = String(action?.actor || 'admin').trim() || 'admin';

  const confirmedRelayTxIds = [];
  for (const relay of options.relayLedgers || []) {
    if (!relay) continue;
    const result = acknowledgeRelayTransfers(ledger, relay);
    for (const id of result.transferIds || []) {
      confirmedRelayTxIds.push(id);
    }
  }

  const pendingTxs = drainPendingInboundTransfers(ledger);
  const index = ledger.blocks.length;
  const txId = `admin-${actionKind}-${Date.now()}-${crypto.randomBytes(4).toString('hex')}`;
  const adminTx = {
    id: txId,
    kind: ADMIN_ACTION_KIND,
    actionKind,
    scenarioLabel: label,
    memo: memo || label,
    path,
    actor,
    timestamp: new Date().toISOString(),
    blockIndex: index,
  };

  const transactions = [adminTx, ...pendingTxs];
  const block = {
    index,
    scenarioLabel: label,
    transactions,
    timestamp: new Date().toISOString(),
    triggerUsername: actor,
    adminAction: true,
    adminActionKind: actionKind,
    chronofluxFingerprint: crypto
      .createHash('sha256')
      .update(`${CHAIN_ID}:admin:${actionKind}:${index}:${txId}`)
      .digest('hex')
      .slice(0, 32),
  };
  ledger.blocks.push(block);
  ledger.lastScenarioAt = block.timestamp;
  if (typeof ledger.nextTxId === 'number') {
    ledger.nextTxId += 1;
  }

  return {
    ok: true,
    block,
    height: blockHeight(ledger) - 1,
    confirmedRelayTxIds,
    pendingIncluded: pendingTxs.length,
    label,
  };
}

/**
 * Whether a block is an admin-action ChronoFlux seal (explorer helpers).
 * @param {object|null|undefined} block
 */
export function isAdminActionBlock(block) {
  if (!block) return false;
  if (block.adminAction === true) return true;
  const txs = block.transactions ?? [];
  return txs.some((tx) => tx?.kind === ADMIN_ACTION_KIND);
}
