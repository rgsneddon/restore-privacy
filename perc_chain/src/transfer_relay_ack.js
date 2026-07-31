/**
 * Canonical relay acknowledgment: promote sender transfer blocks by stable tx.id
 * at the sender's block height (not re-indexed to the canonical tip).
 */

export function peerGenesisRevision(ledger) {
  return ledger?.networkGenesisRevision ?? 1;
}

export function peerLedgerHeight(ledger) {
  return ledger?.blocks?.length ?? 0;
}

export function collectTransferTxIds(ledger) {
  const ids = new Set();
  for (const block of ledger?.blocks ?? []) {
    for (const tx of block?.transactions ?? []) {
      if (tx?.kind === 'transfer' && tx.id) ids.add(tx.id);
    }
  }
  return ids;
}

export function blockHasTransfer(block) {
  return (block?.transactions ?? []).some((tx) => tx?.kind === 'transfer');
}

function clonePreservedBlock(block) {
  return typeof structuredClone === 'function'
    ? structuredClone(block)
    : JSON.parse(JSON.stringify(block));
}

function emptyBlockAtIndex(index) {
  return {
    index,
    transactions: [],
    timestamp: new Date().toISOString(),
  };
}

function ensureChainSlots(canonical, minLength) {
  while (canonical.blocks.length < minLength) {
    canonical.blocks.push(emptyBlockAtIndex(canonical.blocks.length));
  }
}

function transferIdsInBlock(block) {
  return (block?.transactions ?? [])
    .filter((tx) => tx?.kind === 'transfer' && tx.id)
    .map((tx) => tx.id);
}

/**
 * Clone relay transfer block preserving sender height and tx.blockIndex.
 * @param {object} block
 */
export function cloneTransferBlockPreservingHeight(block) {
  const cloned = clonePreservedBlock(block);
  const sourceIndex = block.index ?? 0;
  cloned.index = sourceIndex;
  delete cloned.relaySourceBlockIndex;
  for (const tx of cloned.transactions ?? []) {
    if (tx && typeof tx === 'object' && tx.kind === 'transfer') {
      tx.blockIndex = sourceIndex;
    }
  }
  return cloned;
}

/**
 * @deprecated Use cloneTransferBlockPreservingHeight — kept for treasury payout tip promotion.
 */
export function cloneTransferBlockForCanonicalTip(block, canonicalIndex) {
  const cloned = clonePreservedBlock(block);
  cloned.index = canonicalIndex;
  for (const tx of cloned.transactions ?? []) {
    if (tx && typeof tx === 'object') {
      tx.blockIndex = canonicalIndex;
    }
  }
  return cloned;
}

function mergeBlockAtSourceIndex(canonical, block) {
  const sourceIndex = block.index ?? 0;
  ensureChainSlots(canonical, sourceIndex + 1);

  const incomingIds = transferIdsInBlock(block);
  const existing = canonical.blocks[sourceIndex];
  const cloned = cloneTransferBlockPreservingHeight(block);

  if (!existing || (existing.transactions ?? []).length === 0) {
    canonical.blocks[sourceIndex] = cloned;
    return true;
  }

  const existingTransferIds = new Set(transferIdsInBlock(existing));
  if (incomingIds.some((id) => existingTransferIds.has(id))) {
    return false;
  }
  if (existingTransferIds.size > 0) {
    return false;
  }

  existing.index = sourceIndex;
  for (const tx of cloned.transactions ?? []) {
    if (tx?.kind !== 'transfer') continue;
    tx.blockIndex = sourceIndex;
    existing.transactions.push(tx);
  }
  if (!existing.timestamp && cloned.timestamp) {
    existing.timestamp = cloned.timestamp;
  }
  if (!existing.triggerUsername && cloned.triggerUsername) {
    existing.triggerUsername = cloned.triggerUsername;
  }
  if (!existing.chronofluxFingerprint && cloned.chronofluxFingerprint) {
    existing.chronofluxFingerprint = cloned.chronofluxFingerprint;
  }
  return true;
}

/**
 * @param {object} canonical — mutable seed or wallet ledger
 * @param {object} relay — peer relay ledger (often shorter)
 * @returns {{ acknowledged: number, ok: boolean, transferIds: string[], canonicalIndices: number[] }}
 */
export function acknowledgeRelayTransfers(canonical, relay) {
  if (!canonical || !relay || !Array.isArray(canonical.blocks)) {
    return { acknowledged: 0, ok: false, transferIds: [], canonicalIndices: [] };
  }
  if (peerGenesisRevision(canonical) !== peerGenesisRevision(relay)) {
    return { acknowledged: 0, ok: false, transferIds: [], canonicalIndices: [] };
  }

  const known = collectTransferTxIds(canonical);
  const promoted = [];
  const canonicalIndices = [];
  let acknowledged = 0;

  for (const block of relay.blocks ?? []) {
    if (!blockHasTransfer(block)) continue;
    const transferIds = (block.transactions ?? [])
      .filter((tx) => tx?.kind === 'transfer')
      .map((tx) => tx.id)
      .filter(Boolean);
    if (transferIds.length === 0) continue;
    if (transferIds.some((id) => known.has(id))) continue;

    const sourceIndex = block.index ?? 0;
    if (!mergeBlockAtSourceIndex(canonical, block)) continue;

    for (const id of transferIds) {
      known.add(id);
      promoted.push(id);
    }
    canonicalIndices.push(sourceIndex);
    acknowledged += 1;
  }

  return {
    acknowledged,
    ok: acknowledged > 0,
    transferIds: promoted,
    canonicalIndices,
  };
}

/** @deprecated Use acknowledgeRelayTransfers */
export function mergeTransferBlocksFromPeer(local, remote) {
  const result = acknowledgeRelayTransfers(local, remote);
  return { appended: result.acknowledged, merged: result.ok };
}