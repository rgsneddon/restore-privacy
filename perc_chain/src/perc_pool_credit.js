/**
 * Perccent pool payouts. Accepted BeamHash III shares credit PERC only.
 * Beam SBBS / BEAM-coin addresses are not a destination of record.
 */

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
