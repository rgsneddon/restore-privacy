/**
 * Perccent pool payouts. Accepted BeamHash III shares credit PERC only.
 * Beam SBBS / BEAM-coin addresses are not a destination of record.
 */

import crypto from 'crypto';
import { BLOCK_GEN_REWARD_MICRO } from './chain_timing.js';

export const PAYOUT_ASSET = 'PERC';
export const REJECTED_ASSETS = Object.freeze(['BEAM', 'beam', 'Beam']);

const UNITS_PER_PERC = 100_000_000;
/** Default share credit: 0.00000001 PERC (1 micro-unit). */
export const SHARE_CREDIT_MICRO = 1;

export function normalizePercUser(identity) {
  const raw = String(identity ?? '').trim();
  const user = raw.split('.')[0].trim();
  if (!user) throw new Error('perc_user_required');
  if (/^beam:/i.test(user) || user.includes('sBbs') || user.includes('sbbs')) {
    throw new Error('beam_payout_forbidden');
  }
  return user;
}

/**
 * Record an accepted-share credit. Asset is always PERC.
 * @returns {{ asset: 'PERC', username: string, microUnits: number, kind: string, jobId?: string }}
 */
export function creditAcceptedShare({
  username,
  identity,
  microUnits = SHARE_CREDIT_MICRO,
  jobId,
  asset,
} = {}) {
  if (asset != null && String(asset).toUpperCase() !== PAYOUT_ASSET) {
    throw new Error('payout_asset_must_be_PERC');
  }
  const user = normalizePercUser(username ?? identity);
  const units = Number(microUnits);
  if (!Number.isFinite(units) || units <= 0) {
    throw new Error('credit_must_be_positive');
  }
  return {
    asset: PAYOUT_ASSET,
    username: user,
    microUnits: Math.floor(units),
    perc: units / UNITS_PER_PERC,
    kind: 'mined_share',
    algorithm: 'beamhashIII',
    jobId: jobId != null ? String(jobId) : undefined,
  };
}

const TREASURY_USERNAME = 'evolve_treasury';
const SEED_USERNAME = 'evolve_seed_node';

function ensureWalletAccount(state, username) {
  state.accounts = state.accounts || {};
  if (!state.accounts[username]) {
    state.accounts[username] = {
      username,
      address: '',
      balance: { microUnits: 0 },
      cumulativeStakingEarned: { microUnits: 0 },
      transactions: [],
    };
  }
  const acc = state.accounts[username];
  if (!acc.balance || typeof acc.balance !== 'object') acc.balance = { microUnits: 0 };
  if (!Array.isArray(acc.transactions)) acc.transactions = [];
  return acc;
}

/**
 * Credit every user and miner on block generation the same way the NED
 * faucet does: debit evolve_treasury, credit accounts[u].balance, and
 * post a block_gen_reward / scenarioReward tx wallets already sync.
 * mineCredits is a secondary pool book only.
 */
export function rewardAllOnBlockGen(ledger, { finder, height, unit } = {}) {
  const state = ledger && typeof ledger === 'object' ? ledger : {};
  if (!state.mineCredits || typeof state.mineCredits !== 'object') state.mineCredits = {};
  if (!Array.isArray(state.blocks)) state.blocks = [];
  const names = new Set();
  for (const name of Object.keys(state.accounts || {})) {
    if (name && name !== TREASURY_USERNAME && name !== SEED_USERNAME) names.add(name);
  }
  for (const name of Object.keys(state.mineCredits || {})) {
    try {
      names.add(normalizePercUser(name));
    } catch {
      /* skip */
    }
  }
  if (finder) {
    try {
      names.add(normalizePercUser(finder));
    } catch {
      /* skip invalid finder */
    }
  }
  const payout = Number.isFinite(Number(unit)) && Number(unit) > 0
    ? Math.floor(Number(unit))
    : BLOCK_GEN_REWARD_MICRO;
  const rewarded = [];
  const txs = [];
  const ts = new Date().toISOString();
  const idx =
    height != null && Number.isFinite(Number(height))
      ? Number(height)
      : Math.max(0, state.blocks.length - 1);
  const block =
    state.blocks.find((b) => Number(b?.index) === idx) ||
    state.blocks[state.blocks.length - 1] ||
    null;

  const treasury = ensureWalletAccount(state, TREASURY_USERNAME);
  const total = payout * names.size;
  if ((treasury.balance.microUnits || 0) < total) {
    treasury.balance = {
      microUnits: (treasury.balance.microUnits || 0) + total,
    };
  }
  treasury.balance = {
    microUnits: (treasury.balance.microUnits || 0) - total,
  };

  for (const username of names) {
    let rec;
    try {
      rec = creditAcceptedShare({
        username,
        microUnits: payout,
        jobId: String(idx),
      });
    } catch {
      continue;
    }
    rec.kind = 'block_gen_reward';
    state.mineCredits = applyCredit(state.mineCredits, rec);
    const acc = ensureWalletAccount(state, rec.username);
    acc.balance = { microUnits: (acc.balance.microUnits || 0) + payout };
    const tx = {
      id: `block-gen-${idx}-${rec.username}-${crypto.randomBytes(3).toString('hex')}`,
      kind: 'block_gen_reward',
      amount: { microUnits: payout },
      timestamp: ts,
      fromUsername: TREASURY_USERNAME,
      toUsername: rec.username,
      scenarioLabel: 'Block generation reward',
      memo: 'Reward on block generation',
      blockIndex: idx,
    };
    acc.transactions.unshift(tx);
    treasury.transactions.unshift(tx);
    if (block) {
      if (!Array.isArray(block.transactions)) block.transactions = [];
      block.transactions.push(tx);
    }
    txs.push(tx);
    rewarded.push(rec.username);
  }
  return { rewarded, count: rewarded.length, height: idx, txs, unit: payout };
}

export function applyCredit(book, credit) {
  if (!credit || credit.asset !== PAYOUT_ASSET) {
    throw new Error('not_a_perc_credit');
  }
  const next = book && typeof book === 'object' ? { ...book } : {};
  const prev = next[credit.username] ?? { asset: PAYOUT_ASSET, microUnits: 0 };
  next[credit.username] = {
    asset: PAYOUT_ASSET,
    username: credit.username,
    microUnits: (prev.microUnits ?? 0) + credit.microUnits,
  };
  return next;
}
