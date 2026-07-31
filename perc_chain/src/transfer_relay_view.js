/**
 * Single read contract for relay-promoted transfer blocks on taller seed/receiver ledgers.
 * Canonical index lives on the tip; relaySourceBlockIndex preserves sender timing.
 */

export function firstTransferTx(block) {
  return (block?.transactions ?? []).find((tx) => tx?.kind === 'transfer') ?? null;
}

/**
 * @param {object} ledger
 * @param {number} queriedIndex — canonical chain index or sender relay-source alias
 * @returns {{
 *   block: object,
 *   queriedIndex: number,
 *   canonicalIndex: number,
 *   relaySourceBlockIndex: number|null,
 *   matchedBy: 'canonical'|'relaySource'|'positional',
 *   transferTx: object|null,
 * }|null}
 */
export function resolveRelayBlockView(ledger, queriedIndex) {
  const blocks = ledger?.blocks ?? [];
  if (!Number.isInteger(queriedIndex) || queriedIndex < 0 || !blocks.length) {
    return null;
  }

  let block = blocks.find((b) => b?.index === queriedIndex);
  let matchedBy = 'canonical';
  if (!block) {
    block = blocks.find((b) => b?.relaySourceBlockIndex === queriedIndex);
    if (block) matchedBy = 'relaySource';
  }
  if (!block) {
    const positional = blocks[queriedIndex];
    if (positional != null && (positional.index == null || positional.index === queriedIndex)) {
      block = positional;
      matchedBy = 'positional';
    }
  }
  if (!block) return null;

  return {
    block,
    queriedIndex,
    /** Chain tip index where the promoted block lives. */
    canonicalIndex: block.index,
    /** Sender-original index when relay-promoted; same as queriedIndex on alias hits. */
    relaySourceBlockIndex: block.relaySourceBlockIndex ?? null,
    matchedBy,
    transferTx: firstTransferTx(block),
    /** Index callers should display for this query (alias vs canonical). */
    displayIndex: matchedBy === 'relaySource' ? queriedIndex : block.index,
  };
}

/** Microblock ring fraction (0–1) using sender relay source when present. */
export function transferMarkerAngle(block, microblocksPerBlock) {
  if (!block || !Number.isFinite(microblocksPerBlock) || microblocksPerBlock <= 0) {
    return 0;
  }
  const timingIndex = block.relaySourceBlockIndex ?? block.index ?? 0;
  return (timingIndex % microblocksPerBlock) / microblocksPerBlock;
}