/**
 * Confirm a block by id or index. Never throws. Always returns
 * confirmed | not_found | rejected.
 */

function findInList(blocks, needle) {
  if (!Array.isArray(blocks)) return null;
  const n = String(needle);
  return (
    blocks.find(
      (b) =>
        b &&
        (String(b.id) === n ||
          String(b.hash) === n ||
          String(b.index) === n ||
          String(b.canonicalIndex) === n),
    ) ?? null
  );
}

export function confirmBlock(id, { ledger = null, actionBlocks = [] } = {}) {
  try {
    const needle = String(id ?? '').trim();
    if (!needle) {
      return { id: '', status: 'rejected', reason: 'missing_id', confirmed: false };
    }
    const fromActions = findInList(actionBlocks, needle);
    if (fromActions) {
      return { id: needle, status: 'confirmed', block: fromActions, confirmed: true };
    }
    const fromLedger = findInList(ledger?.blocks, needle);
    if (fromLedger) {
      return { id: needle, status: 'confirmed', block: fromLedger, confirmed: true };
    }
    return { id: needle, status: 'not_found', reason: 'unknown_block', confirmed: false };
  } catch (err) {
    return {
      id: String(id ?? ''),
      status: 'rejected',
      reason: String(err?.message || err || 'confirm_failed'),
      confirmed: false,
    };
  }
}

export function wardsForVotingEpoch(epochId, wardCount = 8) {
  const id = String(epochId || '').trim();
  const n = Math.max(1, Math.min(64, Number(wardCount) || 8));
  if (!id) return [];
  return Array.from({ length: n }, (_, i) => ({
    epochId: id,
    wardIndex: i + 1,
    wardId: `ward-${id}-${i + 1}`,
    label: `Ward ${i + 1} · ${id}`,
  }));
}
