/**
 * Canonical block tip payload — MUST match Dart PercChainTip key order exactly.
 *
 * Block keys (lib/perc/services/perc_chain_tip.dart _blockTipJson):
 *   index, timestamp, treasuryEmitted,
 *   [treasuryCycle if != 1],
 *   [isGenesisRenewal if true],
 *   [confirmations if != confirmationsRequired],
 *   [microblockSeal if true],
 *   [chronofluxFingerprint if not null],
 *   [microblocksSealed if not null],
 *   transactions  ← always last
 *
 * Tx keys (_txTipJson):
 *   id, kind, amount, timestamp,
 *   [percentChance], [blockIndex], [confirmations if != 0],
 *   [continuumScs], [vortexScs], [shearScs], [resistanceScs], [flowScs],
 *   [microblockIndex], [chronofluxFingerprint]
 */

const CONFIRMATIONS_REQUIRED = 1;

function amountJson(amount) {
  if (!amount || typeof amount !== 'object') return { microUnits: 0 };
  return { microUnits: amount.microUnits ?? 0 };
}

/** Insert [key, value] pairs in declaration order; skip null/undefined values. */
function orderedPayload(entries) {
  const out = {};
  for (const [key, value] of entries) {
    if (value === undefined || value === null) continue;
    out[key] = value;
  }
  return out;
}

export function txTipPayload(tx) {
  if (!tx || typeof tx !== 'object') return null;
  if (tx.id == null || tx.kind == null || tx.timestamp == null) return null;

  return orderedPayload([
    ['id', tx.id],
    ['kind', tx.kind],
    ['amount', amountJson(tx.amount)],
    ['timestamp', tx.timestamp],
    ['percentChance', tx.percentChance],
    ['blockIndex', tx.blockIndex],
    ['confirmations', tx.confirmations != null && tx.confirmations !== 0 ? tx.confirmations : undefined],
    ['continuumScs', tx.continuumScs],
    ['vortexScs', tx.vortexScs],
    ['shearScs', tx.shearScs],
    ['resistanceScs', tx.resistanceScs],
    ['flowScs', tx.flowScs],
    ['microblockIndex', tx.microblockIndex],
    ['chronofluxFingerprint', tx.chronofluxFingerprint],
  ]);
}

export function blockTipPayload(block) {
  if (!block || typeof block !== 'object') return null;
  if (block.index == null || block.timestamp == null) return null;

  const treasuryCycle = block.treasuryCycle ?? 1;
  const confirmations = block.confirmations ?? CONFIRMATIONS_REQUIRED;
  const transactions = (block.transactions ?? [])
    .map((tx) => txTipPayload(tx))
    .filter(Boolean);

  return orderedPayload([
    ['index', block.index],
    ['timestamp', block.timestamp],
    ['treasuryEmitted', amountJson(block.treasuryEmitted)],
    ['treasuryCycle', treasuryCycle !== 1 ? treasuryCycle : undefined],
    ['isGenesisRenewal', block.isGenesisRenewal ? true : undefined],
    ['confirmations', confirmations !== CONFIRMATIONS_REQUIRED ? confirmations : undefined],
    ['microblockSeal', block.microblockSeal ? true : undefined],
    ['chronofluxFingerprint', block.chronofluxFingerprint],
    ['microblocksSealed', block.microblocksSealed],
    ['transactions', transactions],
  ]);
}