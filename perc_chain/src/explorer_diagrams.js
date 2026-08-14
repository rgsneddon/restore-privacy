import { TREASURY_MINT_MICRO_PER_COOLDOWN } from './chain_constants.js';
import { wardsForVotingEpoch } from './block_confirm.js';

/**
 * Graphs / diagrams for every explorer piece: blocks, wards, mint, rpAI + NED.
 * Always returns non-empty series.
 */
export function buildExplorerDiagrams({
  ledger = null,
  actionBlocks = [],
  rpaiStats = null,
  epochId = 'current',
} = {}) {
  const ledgerBlocks = Array.isArray(ledger?.blocks) ? ledger.blocks : [];
  const actions = Array.isArray(actionBlocks) ? actionBlocks : [];
  const blockSeries =
    ledgerBlocks.length + actions.length > 0
      ? [...ledgerBlocks.map((b, i) => Number(b.index ?? i + 1)), ...actions.map((b) => Number(b.index || 0))]
      : [0];
  const wards = wardsForVotingEpoch(epochId);
  const wardSeries = wards.length ? wards.map((w) => w.wardIndex) : [1];
  const mintTick = Number(TREASURY_MINT_MICRO_PER_COOLDOWN || 1);
  const mintSeries = blockSeries.map((_, i) => (i + 1) * Math.max(1, Math.floor(mintTick / 1_000_000)));
  const stats = rpaiStats || { learned: 0, byKind: {}, identity: 'NED' };
  const kindValues = Object.values(stats.byKind || {});
  const rpaiSeries = kindValues.length ? kindValues.map((n) => Number(n) || 0) : [Number(stats.learned) || 0];

  return {
    graphs: {
      blocks: blockSeries,
      wards: wardSeries,
      mint: mintSeries,
      rpai: rpaiSeries,
    },
    wards,
    ned: stats,
    mintKeepFraction: '1/3',
    pieces: ['blocks', 'wards', 'mint', 'rpai', 'ned'],
  };
}
