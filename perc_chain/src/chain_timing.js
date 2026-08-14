/**
 * Hard-set Perccent / Evolve time structure.
 *
 * Scenario seals + miner unlocking hashes share the same average block
 * window. Full confirmation (spendable) is 72 seconds — not 72 minutes.
 * No Evolve client or perc wallet rebuild is required: wallets read
 * confirmation from this server path.
 */

/** Target production rate from scenario slots (:14 / :34 / :54) and miner unlocks. */
export const TARGET_BLOCKS_PER_HOUR = 3;

/** Expected average time between blocks (20 minutes). */
export const TARGET_BLOCK_INTERVAL_MS = Math.floor(3_600_000 / TARGET_BLOCKS_PER_HOUR);

/** Fully confirmed / spendable after this many milliseconds. */
export const CONFIRMATION_MS = 72 * 1000;

export const CONFIRMATION_SECONDS = CONFIRMATION_MS / 1000;

/**
 * Difficulty bits for miner unlocking hashes. 0 is findable inside the
 * expected average window on the shipped BeamHash III check.
 */
export const MINER_UNLOCK_DIFFICULTY_BITS = 0;

/** PERC micro-units credited to every user/miner when a block is generated. */
export const BLOCK_GEN_REWARD_MICRO = 1;

export function expectedBlocksPerHour() {
  return TARGET_BLOCKS_PER_HOUR;
}

export function expectedAverageBlockMs() {
  return TARGET_BLOCK_INTERVAL_MS;
}

export function confirmationDelayMs() {
  return CONFIRMATION_MS;
}
