/**
 * Perccent mine job helpers. `input` is a 32-byte BeamHash III pre-work hex.
 * Share check is BeamHash III; accepted work credits PERC, not BEAM.
 */
import { buildJob, checkShare, defaultPreWork } from './beamhash_iii.js';
import { creditAcceptedShare, rewardAllOnBlockGen } from './perc_pool_credit.js';
import { percChainTipHeight } from './chain_tip.js';
import {
  MINER_UNLOCK_DIFFICULTY_BITS,
  TARGET_BLOCK_INTERVAL_MS,
} from './chain_timing.js';

export const DEFAULT_DIFFICULTY_BITS = MINER_UNLOCK_DIFFICULTY_BITS;
export { TARGET_BLOCK_INTERVAL_MS, MINER_UNLOCK_DIFFICULTY_BITS };

export function jobFromLedger(ledger, difficultyBits = DEFAULT_DIFFICULTY_BITS) {
  const height = percChainTipHeight(ledger);
  const prev =
    height > 0
      ? String(
          ledger.blocks[height - 1].powHash ||
            ledger.blocks[height - 1].hash ||
            ledger.blocks[height - 1].chronofluxFingerprint ||
            height - 1,
        )
      : '0'.repeat(64);
  const job = buildJob({
    preWork: defaultPreWork(height),
    height,
    jobId: String(height),
  });
  return {
    id: job.jobId,
    jobId: job.jobId,
    height,
    difficulty: Number(difficultyBits) || 0,
    input: job.input,
    preWork: job.preWork,
    prev,
    jsonrpc: '2.0',
    method: 'job',
    coin: 'PERC',
    algorithm: 'beamhashIII',
  };
}

export function headerFromJob(job) {
  return {
    height: Number(job?.height) || 0,
    prev: job?.prev || '0'.repeat(64),
    input: job?.input || job?.preWork || '',
  };
}

/**
 * Verify a miner solution against the job's 32-byte input.
 * Forwards output + username; accepted shares are PERC credits.
 */
export function applyPowToLedger(ledger, submission) {
  const state = ledger && typeof ledger === 'object' ? ledger : { blocks: [] };
  if (!Array.isArray(state.blocks)) state.blocks = [];
  const heightBefore = state.blocks.length;
  const header = submission?.header || headerFromJob(submission?.job || {});
  const input = submission?.input || header.input || submission?.job?.input || submission?.preWork;
  const output = submission?.output || submission?.solution;
  const nonce = submission?.nonce;
  const checked = checkShare({ preWork: input, nonce, solution: output });
  if (!checked.ok) {
    return {
      accepted: false,
      height: heightBefore,
      error: checked.reason || 'rejected',
      asset: 'PERC',
    };
  }
  let credit;
  try {
    credit = creditAcceptedShare({
      username: submission?.username || submission?.login || 'anon',
      jobId: submission?.job?.id || submission?.job?.jobId || header.height,
    });
  } catch (err) {
    return {
      accepted: false,
      height: heightBefore,
      error: err.message || 'credit_failed',
      asset: 'PERC',
    };
  }
  if (!state.mineCredits || typeof state.mineCredits !== 'object') state.mineCredits = {};
  const prev = state.mineCredits[credit.username] ?? { asset: 'PERC', microUnits: 0 };
  state.mineCredits[credit.username] = {
    asset: 'PERC',
    username: credit.username,
    microUnits: (prev.microUnits ?? 0) + credit.microUnits,
  };
  const unlockHash = String(output || nonce || `unlock-${heightBefore}`);
  const memo = `Unlocking hash found by ${credit.username}`;
  state.blocks.push({
    index: heightBefore,
    timestamp: new Date().toISOString(),
    scenarioLabel: `Miner unlock · ${credit.username}`,
    memo,
    powHash: unlockHash,
    triggerUsername: credit.username,
    minerUnlock: true,
    targetIntervalMs: TARGET_BLOCK_INTERVAL_MS,
    transactions: [
      {
        id: `mine-unlock-${heightBefore}-${credit.username}`,
        kind: 'minerUnlock',
        memo,
        scenarioLabel: `Miner unlock · ${credit.username}`,
        from: credit.username,
        timestamp: new Date().toISOString(),
        blockIndex: heightBefore,
      },
    ],
  });
  const rewards = rewardAllOnBlockGen(state, {
    finder: credit.username,
    height: heightBefore,
  });
  return {
    accepted: true,
    height: heightBefore,
    unlocked: true,
    unlockingHash: unlockHash,
    error: null,
    credit,
    rewards,
    asset: 'PERC',
    algorithm: 'beamhashIII',
    targetIntervalMs: TARGET_BLOCK_INTERVAL_MS,
  };
}
