import {
  cloneTransferBlockForCanonicalTip,
  peerLedgerHeight,
} from './transfer_relay_ack.js';

const TREASURY_USERNAME = process.env.PERC_TREASURY_USERNAME ?? 'evolve_treasury';

export const TREASURY_PAYOUT_KINDS = new Set(['scenarioReward', 'stakingReward']);

function cloneBlock(block) {
  return typeof structuredClone === 'function'
    ? structuredClone(block)
    : JSON.parse(JSON.stringify(block));
}

function microUnits(amount) {
  return amount?.microUnits ?? 0;
}

function addMicro(balance, delta) {
  return { microUnits: microUnits(balance) + delta };
}

function blockHasTreasuryPayout(block) {
  return (block?.transactions ?? []).some((tx) => TREASURY_PAYOUT_KINDS.has(tx?.kind));
}

export function collectTreasuryPayoutTxIds(ledger) {
  const ids = new Set();
  for (const block of ledger?.blocks ?? []) {
    for (const tx of block?.transactions ?? []) {
      if (TREASURY_PAYOUT_KINDS.has(tx?.kind) && tx.id) ids.add(tx.id);
    }
  }
  return ids;
}

function findPayoutTx(remote, payoutId) {
  for (const block of remote?.blocks ?? []) {
    for (const tx of block?.transactions ?? []) {
      if (tx?.id === payoutId && TREASURY_PAYOUT_KINDS.has(tx?.kind)) return tx;
    }
  }
  return null;
}

function ensureTreasuryAccount(canonical, remote, treasuryUsername = TREASURY_USERNAME) {
  canonical.accounts = canonical.accounts ?? {};
  if (canonical.accounts[treasuryUsername]) return;

  const remoteTreasury = remote?.accounts?.[treasuryUsername];
  canonical.accounts[treasuryUsername] = remoteTreasury
    ? {
        ...remoteTreasury,
        balance: cloneBlock(remoteTreasury.balance ?? { microUnits: 0 }),
        cumulativeStakingEarned: cloneBlock(
          remoteTreasury.cumulativeStakingEarned ?? { microUnits: 0 },
        ),
      }
    : {
        username: treasuryUsername,
        balance: { microUnits: 0 },
        cumulativeStakingEarned: { microUnits: 0 },
        transactions: [],
      };
}

function stubRecipientFromRemote(remoteAcc, username) {
  if (remoteAcc) {
    return {
      username,
      passwordHash: remoteAcc.passwordHash ?? '',
      salt: remoteAcc.salt ?? '',
      address: remoteAcc.address ?? '',
      passwordSet: remoteAcc.passwordSet ?? false,
      balance: { microUnits: 0 },
      cumulativeStakingEarned: { microUnits: 0 },
      transactions: [],
    };
  }
  return {
    username,
    passwordHash: '',
    salt: '',
    address: '',
    passwordSet: false,
    balance: { microUnits: 0 },
    cumulativeStakingEarned: { microUnits: 0 },
    transactions: [],
  };
}

/**
 * Promote scenario/staking payout blocks from a peer onto the canonical seed ledger.
 */
export function mergeTreasuryPayoutBlocksFromPeer(canonical, remote) {
  if (!canonical || !remote || !Array.isArray(canonical.blocks)) {
    return { merged: 0, payoutIds: [] };
  }

  const known = collectTreasuryPayoutTxIds(canonical);
  const payoutIds = [];
  let merged = 0;

  for (const block of remote.blocks ?? []) {
    if (!blockHasTreasuryPayout(block)) continue;
    const ids = (block.transactions ?? [])
      .filter((tx) => TREASURY_PAYOUT_KINDS.has(tx?.kind))
      .map((tx) => tx.id)
      .filter(Boolean);
    if (ids.length === 0 || ids.every((id) => known.has(id))) continue;

    const canonicalIndex = peerLedgerHeight(canonical);
    canonical.blocks.push(cloneTransferBlockForCanonicalTip(block, canonicalIndex));
    for (const id of ids) known.add(id);
    payoutIds.push(...ids);
    merged += 1;
  }

  return { merged, payoutIds };
}

/**
 * Apply treasury debits and recipient credits from newly merged payout txs only.
 * Preserves canonical pre-merge balances — never wholesale-replaces peer totals.
 */
export function applyTreasuryPayoutDeltasFromPeer(
  canonical,
  remote,
  payoutIds,
  treasuryUsername = TREASURY_USERNAME,
) {
  if (!canonical || !remote || !payoutIds?.length) {
    return { treasuryDebited: 0, recipientsCredited: 0, totalDebitedMicro: 0 };
  }

  ensureTreasuryAccount(canonical, remote, treasuryUsername);
  canonical.accounts = canonical.accounts ?? {};

  let treasuryDebited = 0;
  let recipientsCredited = 0;
  let totalDebitedMicro = 0;

  for (const payoutId of payoutIds) {
    const tx = findPayoutTx(remote, payoutId);
    if (!tx) continue;

    const amountMicro = microUnits(tx.amount);
    if (amountMicro <= 0) continue;

    const to = tx.toUsername ?? tx.to;
    if (!to || to === treasuryUsername) continue;

    const treasury = canonical.accounts[treasuryUsername];
    treasury.balance = addMicro(treasury.balance, -amountMicro);
    treasuryDebited += 1;
    totalDebitedMicro += amountMicro;

    const remoteAcc = remote.accounts?.[to];
    const local =
      canonical.accounts[to] ?? stubRecipientFromRemote(remoteAcc, to);
    local.balance = addMicro(local.balance, amountMicro);
    if (tx.kind === 'stakingReward') {
      local.cumulativeStakingEarned = addMicro(
        local.cumulativeStakingEarned,
        amountMicro,
      );
    }
    if (remoteAcc?.address && !local.address) local.address = remoteAcc.address;
    if (remoteAcc?.passwordSet && !local.passwordSet) {
      local.passwordSet = remoteAcc.passwordSet;
    }
    canonical.accounts[to] = local;
    recipientsCredited += 1;
  }

  return { treasuryDebited, recipientsCredited, totalDebitedMicro };
}

/** Sum tracked wallet balances on a ledger (treasury + all other accounts). */
export function sumAccountBalancesMicro(ledger, treasuryUsername = TREASURY_USERNAME) {
  let total = 0;
  for (const [name, acc] of Object.entries(ledger?.accounts ?? {})) {
    if (!acc) continue;
    total += microUnits(acc.balance);
  }
  return total;
}

/**
 * Merge treasury payout blocks and apply conserved deltas on canonical accounts.
 */
export function mergeTreasuryStateFromPeer(canonical, remote) {
  const payout = mergeTreasuryPayoutBlocksFromPeer(canonical, remote);
  const deltas =
    payout.payoutIds.length > 0
      ? applyTreasuryPayoutDeltasFromPeer(canonical, remote, payout.payoutIds)
      : { treasuryDebited: 0, recipientsCredited: 0, totalDebitedMicro: 0 };

  if (payout.merged > 0 && remote?.lastScenarioAt) {
    canonical.lastScenarioAt = remote.lastScenarioAt;
  }

  return {
    payoutBlocksMerged: payout.merged,
    payoutIds: payout.payoutIds,
    recipientsCredited: deltas.recipientsCredited,
    treasuryDebitedMicro: deltas.totalDebitedMicro,
    accountSynced: deltas.treasuryDebited > 0,
    merged: payout.merged > 0,
  };
}