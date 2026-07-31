import { acknowledgeRelayTransfers, collectTransferTxIds } from './transfer_relay_ack.js';
import { mergeTreasuryStateFromPeer } from './treasury_merge.js';

const CONFIRMATIONS_REQUIRED = 1;

export function peerGenesisRevision(ledger) {
  return ledger?.networkGenesisRevision ?? 1;
}

export function listObservedPendingTransfers(ledger) {
  return (ledger?.pendingInboundTransfers ?? []).map((p) => ({
    id: p.id,
    fromUsername: p.fromUsername,
    toUsername: p.toUsername,
    amountMicroUnits: p.amount?.microUnits ?? 0,
    feeMicroUnits: p.fee?.microUnits ?? 1,
    sentAt: p.sentAt,
    confirmations: 0,
    spendable: false,
  }));
}

export function listSettlementWitnessIds(ledger) {
  return (ledger?.settlementWitnesses ?? [])
    .filter((w) => w?.senderCanDebit)
    .map((w) => w.transferId);
}

export function mergeSettlementWitnessesFromPeer(canonical, remote) {
  if (!canonical || !remote) return 0;
  canonical.settlementWitnesses = canonical.settlementWitnesses ?? [];
  const seen = new Set(canonical.settlementWitnesses.map((w) => w.id ?? w.transferId));
  let merged = 0;
  for (const witness of remote.settlementWitnesses ?? []) {
    const id = witness?.transferId;
    if (!id || seen.has(id)) continue;
    canonical.settlementWitnesses.push({ ...witness });
    seen.add(id);
    merged += 1;
  }
  return merged;
}

export function listSettledTransferIds(ledger) {
  const ids = new Set();
  for (const block of ledger?.blocks ?? []) {
    for (const tx of block?.transactions ?? []) {
      if (tx?.kind !== 'transfer') continue;
      const confirmations = tx?.confirmations ?? 0;
      if (confirmations >= CONFIRMATIONS_REQUIRED) {
        ids.add(tx.id);
      }
    }
  }
  return [...ids];
}

/**
 * Merges pending inbound transfers from a relay ledger (initiation gossip).
 * @param {object} canonical
 * @param {object} remote
 */
export function mergePendingInboundFromPeer(canonical, remote) {
  if (!canonical || !remote) return 0;
  const seen = new Set((canonical.pendingInboundTransfers ?? []).map((p) => p.id));
  let merged = 0;
  canonical.pendingInboundTransfers = canonical.pendingInboundTransfers ?? [];

  for (const pending of remote.pendingInboundTransfers ?? []) {
    if (!pending?.id || seen.has(pending.id)) continue;
    canonical.pendingInboundTransfers.push({ ...pending });
    seen.add(pending.id);
    merged += 1;
  }
  return merged;
}

/**
 * Seed/wallet network merge: pending initiation state + relay transfer blocks.
 * @param {object} canonical
 * @param {object} remote
 */
export function mergeNetworkStateFromPeer(canonical, remote) {
  if (!canonical || !remote) {
    return {
      pendingMerged: 0,
      acknowledged: 0,
      ok: false,
      transferIds: [],
      canonicalIndices: [],
    };
  }
  if (peerGenesisRevision(canonical) !== peerGenesisRevision(remote)) {
    return {
      pendingMerged: 0,
      acknowledged: 0,
      ok: false,
      transferIds: [],
      canonicalIndices: [],
    };
  }

  const pendingMerged = mergePendingInboundFromPeer(canonical, remote);
  const witnessesMerged = mergeSettlementWitnessesFromPeer(canonical, remote);
  const treasury = mergeTreasuryStateFromPeer(canonical, remote);
  const ack = acknowledgeRelayTransfers(canonical, remote);
  return {
    pendingMerged,
    witnessesMerged,
    treasuryMerged: treasury.merged,
    treasuryPayoutBlocksMerged: treasury.payoutBlocksMerged,
    treasuryRecipientsCredited: treasury.recipientsCredited,
    treasuryDebitedMicro: treasury.treasuryDebitedMicro,
    treasuryAccountSynced: treasury.accountSynced,
    ...ack,
    ok: ack.ok || treasury.merged || pendingMerged > 0 || witnessesMerged > 0,
  };
}

export function seedObservesTransferInitiation(canonical, relay) {
  const result = mergeNetworkStateFromPeer(canonical, relay);
  const pending = listObservedPendingTransfers(canonical);
  const transferIds = collectTransferTxIds(canonical);
  return {
    ...result,
    pendingCount: pending.length,
    pendingIds: pending.map((p) => p.id),
    transferBlockIds: [...transferIds],
    observedAtInitiation:
      result.pendingMerged > 0 || result.acknowledged > 0,
  };
}

export function seedObservesTransferSettlement(canonical) {
  const pending = listObservedPendingTransfers(canonical);
  const settled = listSettledTransferIds(canonical);
  return {
    pendingCount: pending.length,
    settledIds: settled,
    spendableSettled: settled.length > 0 && pending.length === 0,
  };
}