import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'url';
import { acknowledgeRelayTransfers } from './transfer_relay_ack.js';
import {
  resolveRelayBlockView,
  transferMarkerAngle,
} from './transfer_relay_view.js';
import { getBlockDetail } from './explorer_api.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(__dirname, '..', '..');
const FIXTURE_PATH = path.join(REPO_ROOT, 'perc_chain', 'fixtures', 'relay_after_send.json');
const MICROBLOCKS_PER_BLOCK = 100_000_000;

function loadFixture() {
  assert.ok(fs.existsSync(FIXTURE_PATH));
  return JSON.parse(fs.readFileSync(FIXTURE_PATH, 'utf8'));
}

describe('resolveRelayBlockView contract', () => {
  it('canonical query returns transfer with relaySourceBlockIndex from fixture ack', () => {
    const fixture = loadFixture();
    const canonical = {
      networkGenesisRevision: 2,
      blocks: [
        { index: 0, transactions: [] },
        { index: 1, transactions: [{ id: 's', kind: 'scenarioReward' }] },
        { index: 2, transactions: [{ id: 't', kind: 'scenarioReward' }] },
      ],
    };
    acknowledgeRelayTransfers(canonical, fixture.ledger);

    const preservedIndex = fixture.transferBlockIndex;
    const view = resolveRelayBlockView(canonical, preservedIndex);
    assert.ok(view);
    assert.equal(view.matchedBy, 'canonical');
    assert.equal(view.canonicalIndex, preservedIndex);
    assert.equal(view.relaySourceBlockIndex, null);
    assert.equal(view.transferTx.id, fixture.transferTxId);

    const detail = getBlockDetail(canonical, preservedIndex);
    assert.equal(detail.matchedBy, 'canonical');
    assert.equal(detail.queriedIndex, preservedIndex);
    assert.equal(detail.canonicalIndex, preservedIndex);
    assert.equal(detail.relaySourceBlockIndex, null);
    assert.equal(detail.transactions.find((tx) => tx.kind === 'transfer').id, fixture.transferTxId);
  });

  it('relaySource alias returns transfer when no native block occupies sender index', () => {
    const ledger = {
      networkGenesisRevision: 2,
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

    const byRelaySource = resolveRelayBlockView(ledger, 2);
    assert.ok(byRelaySource);
    assert.equal(byRelaySource.matchedBy, 'relaySource');
    assert.equal(byRelaySource.canonicalIndex, 5);
    assert.equal(byRelaySource.relaySourceBlockIndex, 2);
    assert.equal(byRelaySource.transferTx.id, 'tx-relay');

    const detail = getBlockDetail(ledger, 2);
    assert.equal(detail.matchedBy, 'relaySource');
    assert.equal(detail.queriedIndex, 2);
    assert.equal(detail.canonicalIndex, 5);
    assert.equal(detail.displayIndex, 2);
    assert.equal(detail.relaySourceBlockIndex, 2);
  });

  it('transferMarkerAngle uses relaySourceBlockIndex for timing', () => {
    const promoted = {
      index: 5,
      relaySourceBlockIndex: 2,
      transactions: [{ id: 'tx', kind: 'transfer' }],
    };
    const angleFromSource = transferMarkerAngle(promoted, MICROBLOCKS_PER_BLOCK);
    const angleFromCanonical = transferMarkerAngle(
      { index: 5, transactions: promoted.transactions },
      MICROBLOCKS_PER_BLOCK,
    );
    assert.notEqual(angleFromSource, angleFromCanonical);
    assert.equal(
      angleFromSource,
      (2 % MICROBLOCKS_PER_BLOCK) / MICROBLOCKS_PER_BLOCK,
    );
  });
});