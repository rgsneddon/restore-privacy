import { blockHeight } from './ledger_store.js';

/** 100M PERC treasury emission per milestone tier. */
export const PERC_PER_SEED_BLOCK = 100_000_000;
export const MICRO_UNITS_PER_PERC = 100_000_000;

export function treasuryMintedMicroUnits(ledger) {
  const minted = ledger?.cumulativeTreasuryMinted;
  if (!minted) return 0;
  if (minted.microUnits != null) return Number(minted.microUnits);
  const whole = minted.whole ?? 0;
  const fraction = minted.fraction ?? 0;
  return whole * MICRO_UNITS_PER_PERC + fraction;
}

/** Treasury emission milestone (block 1 at 0–99M, block 2 at 100M, …) — display only. */
export function treasuryEmissionMilestoneFromLedger(ledger) {
  const micro = treasuryMintedMicroUnits(ledger);
  const thresholdMicro = PERC_PER_SEED_BLOCK * MICRO_UNITS_PER_PERC;
  if (thresholdMicro <= 0) return 0;
  return Math.floor(micro / thresholdMicro) + 1;
}

/** Real main-chain tip height — `blocks.length` (0 at fresh genesis). */
export function chainBlockHeightFromLedger(ledger) {
  return blockHeight(ledger);
}

/** @deprecated Prefer chainBlockHeightFromLedger for chain height. */
export function seedBlockHeightFromLedger(ledger) {
  return chainBlockHeightFromLedger(ledger);
}