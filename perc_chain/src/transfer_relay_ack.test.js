import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import {
  acknowledgeRelayTransfers,
  blockHasTransfer,
  cloneTransferBlockPreservingHeight,
  collectTransferTxIds,
} from './transfer_relay_ack.js';

describe('acknowledgeRelayTransfers', () => {
  it('preserves relay transfer at sender block index', () => {
    const canonical = {
      networkGenesisRevision: 2,
      blocks: [
        { index: 0, transactions: [] },
        { index: 1, transactions: [{ id: 'a', kind: 'scenarioReward' }] },
        { index: 2, transactions: [{ id: 'b', kind: 'scenarioReward' }] },
      ],
    };
    const relay = {
      networkGenesisRevision: 2,
      blocks: [
        {
          index: 1,
          timestamp: '2026-07-06T12:00:00.000Z',
          triggerUsername: 'alice',
          chronofluxFingerprint: 'fp-transfer-1',
          transactions: [
            {
              id: 'tx-1',
              kind: 'transfer',
              fromUsername: 'alice',
              toUsername: 'bob',
              amount: { microUnits: 5 },
              blockIndex: 1,
              timestamp: '2026-07-06T12:00:00.000Z',
            },
          ],
        },
      ],
    };

    const result = acknowledgeRelayTransfers(canonical, relay);
    assert.equal(result.ok, true);
    assert.equal(result.acknowledged, 1);
    assert.deepEqual(result.transferIds, ['tx-1']);
    assert.deepEqual(result.canonicalIndices, [1]);
    assert.equal(canonical.blocks.length, 3);

    const promoted = canonical.blocks[1];
    assert.equal(promoted.index, 1);
    assert.equal(promoted.relaySourceBlockIndex, undefined);
    assert.equal(promoted.chronofluxFingerprint, 'fp-transfer-1');
    assert.equal(promoted.transactions.find((tx) => tx.kind === 'transfer').id, 'tx-1');
    assert.equal(promoted.transactions.find((tx) => tx.kind === 'transfer').blockIndex, 1);
    assert.equal(blockHasTransfer(promoted), true);
    assert.deepEqual([...collectTransferTxIds(canonical)], ['tx-1']);
  });

  it('gap-fills empty slots when sender index exceeds canonical tip', () => {
    const canonical = {
      networkGenesisRevision: 2,
      blocks: [{ index: 0, transactions: [] }],
    };
    const relay = {
      networkGenesisRevision: 2,
      blocks: [
        {
          index: 3,
          transactions: [
            { id: 'tx-gap', kind: 'transfer', blockIndex: 3 },
          ],
        },
      ],
    };

    const result = acknowledgeRelayTransfers(canonical, relay);
    assert.equal(result.ok, true);
    assert.deepEqual(result.canonicalIndices, [3]);
    assert.equal(canonical.blocks.length, 4);
    assert.equal(canonical.blocks[3].index, 3);
    assert.equal(canonical.blocks[3].transactions[0].blockIndex, 3);
    assert.equal(canonical.blocks[1].transactions.length, 0);
    assert.equal(canonical.blocks[2].transactions.length, 0);
  });

  it('cloneTransferBlockPreservingHeight keeps sender index on txs', () => {
    const relayBlock = {
      index: 2,
      transactions: [{ id: 'tx-9', kind: 'transfer', blockIndex: 2 }],
    };
    const cloned = cloneTransferBlockPreservingHeight(relayBlock);
    assert.equal(cloned.index, 2);
    assert.equal(cloned.relaySourceBlockIndex, undefined);
    assert.equal(cloned.transactions[0].blockIndex, 2);
    assert.equal(cloned.transactions[0].id, 'tx-9');
  });

  it('skips duplicate transfer ids already on canonical chain', () => {
    const canonical = {
      networkGenesisRevision: 2,
      blocks: [
        {
          index: 0,
          transactions: [{ id: 'tx-dup', kind: 'transfer', blockIndex: 0 }],
        },
      ],
    };
    const relay = {
      networkGenesisRevision: 2,
      blocks: [
        {
          index: 0,
          transactions: [{ id: 'tx-dup', kind: 'transfer', blockIndex: 0 }],
        },
      ],
    };

    const result = acknowledgeRelayTransfers(canonical, relay);
    assert.equal(result.ok, false);
    assert.equal(canonical.blocks.length, 1);
  });

  it('skips relay block when any transfer id already exists on canonical chain', () => {
    const canonical = {
      networkGenesisRevision: 2,
      blocks: [
        {
          index: 0,
          transactions: [{ id: 'tx-old', kind: 'transfer', blockIndex: 0 }],
        },
      ],
    };
    const relay = {
      networkGenesisRevision: 2,
      blocks: [
        {
          index: 1,
          transactions: [
            { id: 'tx-old', kind: 'transfer', blockIndex: 1 },
            { id: 'tx-new', kind: 'transfer', blockIndex: 1 },
          ],
        },
      ],
    };

    const result = acknowledgeRelayTransfers(canonical, relay);
    assert.equal(result.ok, false);
    assert.equal(canonical.blocks.length, 1);
    assert.deepEqual([...collectTransferTxIds(canonical)], ['tx-old']);
  });

  it('rejects genesis revision mismatch', () => {
    const canonical = { networkGenesisRevision: 2, blocks: [] };
    const relay = { networkGenesisRevision: 3, blocks: [] };
    const result = acknowledgeRelayTransfers(canonical, relay);
    assert.equal(result.ok, false);
  });
});