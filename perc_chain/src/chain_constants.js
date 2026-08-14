/** Matches PercChainConstants — treasury emission aligned with faucet scale. */
export const UNITS_PER_PERC = 100_000_000;
export const FAUCET_COOLDOWN_SECONDS = 7 * 60;
export const MAX_FAUCET_PAYOUT_MICRO = UNITS_PER_PERC;

/** One max faucet draw (1 PERC) accrues per cooldown window. */
export const EMISSION_MICRO_PER_MINUTE = Math.floor(
  (MAX_FAUCET_PAYOUT_MICRO * 60) / FAUCET_COOLDOWN_SECONDS,
);

/** Prior cooldown mint (3/3). Current mint keeps 1/3 of that. */
export const TREASURY_MINT_PRIOR_MICRO_PER_COOLDOWN = 99_999_999;
export const TREASURY_MINT_KEEP_NUMERATOR = 1;
export const TREASURY_MINT_KEEP_DENOMINATOR = 3;
export const TREASURY_MINT_MICRO_PER_COOLDOWN = Math.floor(
  TREASURY_MINT_PRIOR_MICRO_PER_COOLDOWN / TREASURY_MINT_KEEP_DENOMINATOR,
);

export function emissionPerMinuteDisplay() {
  const whole = Math.floor(EMISSION_MICRO_PER_MINUTE / UNITS_PER_PERC);
  const frac = String(EMISSION_MICRO_PER_MINUTE % UNITS_PER_PERC)
    .padStart(8, '0')
    .replace(/0+$/, '');
  return frac.length ? `${whole}.${frac}` : String(whole);
}