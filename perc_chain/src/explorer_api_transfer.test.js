import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { genericBlockLabel } from './block_display_label.js';
import { getBlockDetail, listBlocks, summarizeBlock, summarizeListedBlock } from './explorer_api.js';
import { resolveRelayBlockView } from './transfer_relay_view.js';

const transferLedger = {
  blocks: [
    {
      index: 0,
      timestamp: '2026-07-06T12:00:00.000Z',
      treasuryEmitted: { microUnits: 0 },
      triggerUsername: 'alice',
      transactions: [
        {
          id: 'tx-transfer-1',
          kind: 'transfer',
          fromUsername: 'alice',
          toUsername: 'bob',
          amount: { microUnits: 10 },
          memo: 'Pilot payment',
          timestamp: '2026-07-06T12:00:00.000Z',
        },
        {
          id: 'tx-fee-1',
          kind: 'feeBurn',
          fromUsername: 'alice',
          amount: { microUnits: 1 },
          memo: 'Burned network fee',
        },
      ],
    },
  ],
};

describe('explorer transfer API', () => {
  it('summarizeBlock labels transfers as Manual tx', () => {
    const summary = summarizeBlock(transferLedger.blocks[0], transferLedger);
    assert.equal(summary.displayLabel, 'Manual tx');
    assert.equal(genericBlockLabel(transferLedger.blocks[0]), 'Manual tx');
  });

  it('getBlockDetail exposes kind transfer with formatted amount and parties', () => {
    const detail = getBlockDetail(transferLedger, 0);
    assert.ok(detail);
    assert.equal(detail.displayLabel, 'Manual tx');
    const transfer = detail.transactions.find((tx) => tx.kind === 'transfer');
    assert.ok(transfer);
    assert.equal(transfer.from, 'alice');
    assert.equal(transfer.to, 'bob');
    assert.equal(transfer.amount, '0.0000001');
    assert.equal(transfer.memo, 'Pilot payment');
  });

  it('resolveRelayBlockView resolves relay-promoted transfer by sender relaySourceBlockIndex', () => {
    const ledger = {
      blocks: [
        { index: 0, transactions: [] },
        { index: 1, transactions: [{ id: 's', kind: 'scenarioReward' }] },
        {
          index: 5,
          relaySourceBlockIndex: 2,
          timestamp: '2026-07-06T12:00:00.000Z',
          transactions: [
            {
              id: 'tx-relay',
              kind: 'transfer',
              fromUsername: 'alice',
              toUsername: 'bob',
              amount: { microUnits: 5 },
              blockIndex: 5,
            },
          ],
        },
      ],
    };
    const byCanonical = resolveRelayBlockView(ledger, 5);
    const byRelaySource = resolveRelayBlockView(ledger, 2);
    assert.equal(byCanonical.canonicalIndex, 5);
    assert.equal(byRelaySource.canonicalIndex, 5);
    assert.equal(byRelaySource.matchedBy, 'relaySource');
    assert.equal(byRelaySource.relaySourceBlockIndex, 2);
    const detail = getBlockDetail(ledger, 2);
    assert.equal(detail.queriedIndex, 2);
    assert.equal(detail.canonicalIndex, 5);
    assert.equal(detail.matchedBy, 'relaySource');
    assert.equal(detail.transactions.find((tx) => tx.kind === 'transfer').id, 'tx-relay');
    assert.equal(detail.relaySourceBlockIndex, 2);
  });

  it('listBlocks uses summarizeListedBlock resolver contract on transfer rows', () => {
    const ledger = {
      blocks: [
        { index: 0, transactions: [] },
        { index: 1, transactions: [{ id: 's', kind: 'scenarioReward' }] },
        {
          index: 3,
          relaySourceBlockIndex: 1,
          timestamp: '2026-07-06T12:00:00.000Z',
          transactions: [
            {
              id: 'tx-relay',
              kind: 'transfer',
              fromUsername: 'alice',
              toUsername: 'bob',
              amount: { microUnits: 5 },
            },
          ],
        },
      ],
    };
    const list = listBlocks(ledger);
    const row = list.blocks.find((b) => b.displayLabel === 'Manual tx');
    assert.ok(row);
    assert.equal(row.canonicalIndex, 3);
    assert.equal(row.relaySourceBlockIndex, 1);
    assert.equal(row.matchedBy, 'canonical');
    assert.equal(summarizeListedBlock(ledger.blocks[2], ledger).matchedBy, 'canonical');
  });

  it('getBlockDetail uses canonical index for relay-promoted canonical tip block', () => {
    const ledger = {
      blocks: [
        { index: 0, transactions: [] },
        { index: 1, transactions: [{ id: 's', kind: 'scenarioReward' }] },
        {
          index: 2,
          timestamp: '2026-07-06T12:00:00.000Z',
          transactions: [
            {
              id: 'tx-relay',
              kind: 'transfer',
              fromUsername: 'alice',
              toUsername: 'bob',
              amount: { microUnits: 5 },
              blockIndex: 2,
            },
          ],
        },
      ],
    };
    const detail = getBlockDetail(ledger, 2);
    assert.equal(detail.transactions.find((tx) => tx.kind === 'transfer').id, 'tx-relay');
    assert.equal(detail.index, 2);
  });
});