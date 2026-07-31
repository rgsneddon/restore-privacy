import { blockHeight, tipHash } from './ledger_store.js';
import { buildPublicTreasuryEmission, formatPercAmount } from './explorer_api.js';

const TREASURY_USERNAME = process.env.PERC_TREASURY_USERNAME ?? 'evolve_treasury';

function treasuryTxMatches(tx, treasuryUsername) {
  const from = tx.fromUsername ?? tx.from ?? null;
  const to = tx.toUsername ?? tx.to ?? null;
  return from === treasuryUsername || to === treasuryUsername;
}

export function recentTreasuryTransactions(ledger, treasuryUsername = TREASURY_USERNAME, limit = 20) {
  const found = [];
  const blocks = ledger?.blocks ?? [];
  for (let i = blocks.length - 1; i >= 0 && found.length < limit; i -= 1) {
    for (const tx of blocks[i].transactions ?? []) {
      if (!treasuryTxMatches(tx, treasuryUsername)) continue;
      found.push(tx);
      if (found.length >= limit) break;
    }
  }
  return found;
}

export function countTreasuryTransactions(ledger, treasuryUsername = TREASURY_USERNAME) {
  let count = 0;
  for (const block of ledger?.blocks ?? []) {
    for (const tx of block.transactions ?? []) {
      if (treasuryTxMatches(tx, treasuryUsername)) count += 1;
    }
  }
  return count;
}

export function buildTreasuryWalletView(store) {
  const ledger = store.ledger;
  const treasury = store.treasuryAccount(TREASURY_USERNAME);
  if (!ledger || !treasury) {
    return { ready: false, error: 'Treasury wallet not initialized' };
  }

  return {
    ready: true,
    username: TREASURY_USERNAME,
    address: treasury.address,
    addressShielded: shieldAddress(treasury.address),
    balance: formatPercAmount(treasury.balance),
    balanceMicroUnits: treasury.balance?.microUnits ?? 0,
    passwordSet: treasury.passwordSet ?? false,
    blockchainLaunched: ledger.blockchainLaunched ?? false,
    blockHeight: blockHeight(ledger),
    tipHash: tipHash(ledger),
    treasuryCycle: ledger.treasuryCycle ?? 1,
    cumulativeTreasuryMinted: formatPercAmount(ledger.cumulativeTreasuryMinted),
    cumulativeBurnedPerc: formatPercAmount(ledger.cumulativeBurnedPerc),
    networkGenesisRevision: store.getGenesisRevision(),
    revision: store.revision,
    transactionCount: countTreasuryTransactions(ledger, TREASURY_USERNAME),
    treasuryEmission: buildPublicTreasuryEmission(ledger, TREASURY_USERNAME),
    recentTransactions: recentTreasuryTransactions(ledger, TREASURY_USERNAME, 20).map((tx) => ({
      id: tx.id,
      kind: tx.kind,
      amount: formatPercAmount(tx.amount),
      from: tx.fromUsername ?? tx.from ?? null,
      to: tx.toUsername ?? tx.to ?? null,
      memo: tx.memo ?? null,
      timestamp: tx.timestamp ?? null,
    })),
  };
}

function shieldAddress(address) {
  if (!address || address.length <= 16) return address ?? '';
  return `${address.substring(0, 10)}···${address.substring(address.length - 6)}`;
}