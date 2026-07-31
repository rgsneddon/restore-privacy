/**
 * Compact ledgers persisted on the seed node — truncate scenario narrative,
 * drop redundant per-account transaction histories, strip wallet-only logs,
 * and optionally retain only the newest main-chain blocks.
 */

const DEFAULT_SCENARIO_MAX = 120;

export function scenarioLabelMaxLength() {
  const raw = Number(process.env.PERC_SEED_SCENARIO_MAX ?? DEFAULT_SCENARIO_MAX);
  if (!Number.isFinite(raw) || raw < 32) return DEFAULT_SCENARIO_MAX;
  return Math.min(Math.floor(raw), 512);
}

/** @returns {number} 0 = unlimited */
export function seedBlocksMax() {
  const raw = Number(process.env.PERC_SEED_BLOCKS_MAX ?? 0);
  if (!Number.isFinite(raw) || raw <= 0) return 0;
  return Math.min(Math.floor(raw), 100_000);
}

export function truncateScenarioText(value, maxLen = scenarioLabelMaxLength()) {
  if (value == null) return value;
  const text = String(value).trim();
  if (!text || text.length <= maxLen) return text || null;
  if (maxLen <= 1) return '…';
  return `${text.slice(0, maxLen - 1)}…`;
}

function compactTx(tx, maxLen) {
  if (!tx || typeof tx !== 'object') return;
  if (tx.scenarioLabel != null) {
    tx.scenarioLabel = truncateScenarioText(tx.scenarioLabel, maxLen);
  }
  if (tx.memo != null && String(tx.memo).length > maxLen) {
    tx.memo = truncateScenarioText(tx.memo, maxLen);
  }
}

function cloneLedger(ledger) {
  if (typeof structuredClone === 'function') return structuredClone(ledger);
  return JSON.parse(JSON.stringify(ledger));
}

/**
 * @param {object|null|undefined} ledger
 * @returns {object|null|undefined}
 */
export function compactLedgerForSeed(ledger) {
  if (!ledger || typeof ledger !== 'object') return ledger;

  const out = cloneLedger(ledger);
  const maxLen = scenarioLabelMaxLength();
  const blockCap = seedBlocksMax();

  for (const block of out.blocks ?? []) {
    if (block.scenarioLabel != null) {
      block.scenarioLabel = truncateScenarioText(block.scenarioLabel, maxLen);
    }
    for (const tx of block.transactions ?? []) {
      compactTx(tx, maxLen);
    }
  }

  if (blockCap > 0 && Array.isArray(out.blocks) && out.blocks.length > blockCap) {
    out.blocks = out.blocks.slice(-blockCap);
  }

  for (const account of Object.values(out.accounts ?? {})) {
    if (!account || typeof account !== 'object') continue;
    account.transactions = [];
  }

  out.microblockLog = [];

  for (const proposal of out.wardProposals ?? []) {
    if (!proposal || typeof proposal !== 'object') continue;
    if (proposal.title != null) {
      proposal.title = truncateScenarioText(proposal.title, maxLen);
    }
    if (proposal.summary != null) {
      proposal.summary = truncateScenarioText(proposal.summary, maxLen);
    }
  }

  for (const ballot of out.wardBallots ?? []) {
    if (!ballot || typeof ballot !== 'object') continue;
    if (ballot.comment != null) {
      ballot.comment = truncateScenarioText(ballot.comment, maxLen);
    }
  }

  return out;
}