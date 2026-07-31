import { describe, it, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'url';
import { getBlockDetail, listBlocks } from './explorer_api.js';
import { applyRelayLedgerPut } from './rendezvous_ledger_put.js';
import { LedgerStore } from './ledger_store.js';
import { createGenesisLedger } from './genesis.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(__dirname, '..', '..');
const FIXTURE_PATH = path.join(REPO_ROOT, 'perc_chain', 'fixtures', 'relay_after_send.json');
const CHAIN_ID = 'evolve-chronoflux-principia-chain-1';
const SEED_USERNAME = 'evolve_seed_node';
const MICROBLOCKS_PER_BLOCK = 100_000_000;
const SCRATCH =
  process.env.PERC_SCRATCH_DIR ??
  path.join(os.tmpdir(), 'grok-goal-a6627874349a', 'implementer');

function launchLedger(base) {
  return {
    ...base,
    blockchainLaunched: true,
    blocks: [
      ...(base.blocks ?? []),
      {
        index: base.blocks?.length ?? 0,
        timestamp: '2026-07-06T10:00:00.000Z',
        scenarioLabel: 'Blockchain launch',
        transactions: [],
      },
    ],
    microblocksPerBlock: MICROBLOCKS_PER_BLOCK,
  };
}

function scenarioBlock(previous, index, label) {
  return {
    ...previous,
    blocks: [
      ...previous.blocks,
      {
        index,
        timestamp: `2026-07-06T11:${String(index).padStart(2, '0')}:00.000Z`,
        scenarioLabel: label,
        triggerUsername: 'GLAL7',
        transactions: [
          {
            id: `tx-scenario-${index}`,
            kind: 'scenarioReward',
            toUsername: 'GLAL7',
            amount: { microUnits: 100 },
          },
        ],
      },
    ],
  };
}

function loadSendRelayFixture() {
  const raw = fs.readFileSync(FIXTURE_PATH, 'utf8');
  return JSON.parse(raw);
}

describe('relay API probe capture', () => {
  let tmpDir;

  beforeEach(() => {
    assert.ok(
      fs.existsSync(FIXTURE_PATH),
      'run flutter test test/write_send_relay_fixture_test.dart first',
    );
    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'perc-probe-'));
  });

  afterEach(() => {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  });

  it('writes list + detail JSON after golden-path relay import', () => {
    const fixture = loadSendRelayFixture();
    const senderRelay = fixture.ledger;
    const expectedTxId = fixture.transferTxId;

    const store = new LedgerStore(tmpDir);
    let tall = launchLedger(createGenesisLedger({ genesisRevision: 2, chainId: CHAIN_ID }));
    tall = scenarioBlock(tall, tall.blocks.length, 'Seed scenario A');
    tall = scenarioBlock(tall, tall.blocks.length, 'Seed scenario B');
    store.forceReplaceLedger(tall);
    assert.ok(senderRelay.blocks.length < tall.blocks.length);

    const result = applyRelayLedgerPut({
      store,
      ledgers: new Map(),
      addresses: new Map(),
      username: 'android_user',
      ledger: senderRelay,
      seedUsername: SEED_USERNAME,
    });
    assert.equal(result.ok, true);
    assert.equal(result.imported, true);

    const preservedIndex = fixture.transferBlockIndex;
    const list = listBlocks(store.ledger, { offset: 0, limit: 50 });
    const detail = getBlockDetail(store.ledger, preservedIndex);
    assert.equal(detail.displayLabel, 'Manual tx');
    assert.equal(detail.relaySourceBlockIndex, null);
    assert.equal(detail.queriedIndex, preservedIndex);
    assert.equal(detail.canonicalIndex, preservedIndex);
    assert.equal(detail.matchedBy, 'canonical');
    const transfer = detail.transactions.find((tx) => tx.kind === 'transfer');
    assert.equal(transfer.id, expectedTxId);
    assert.equal(transfer.kind, 'transfer');
    assert.equal(transfer.blockIndex, preservedIndex);

    const transferSummary = list.blocks.find((b) => b.displayLabel === 'Manual tx');
    assert.ok(transferSummary);
    assert.equal(transferSummary.relaySourceBlockIndex, null);
    assert.equal(transferSummary.canonicalIndex, preservedIndex);
    assert.equal(transferSummary.matchedBy, 'canonical');

    const promoted = store.ledger.blocks.find((b) =>
      (b.transactions ?? []).some((tx) => tx.id === expectedTxId),
    );
    assert.ok(promoted);

    fs.mkdirSync(SCRATCH, { recursive: true });
    fs.writeFileSync(
      path.join(SCRATCH, 'local_relay_api_probe.json'),
      `${JSON.stringify({ list, detail }, null, 2)}\n`,
      'utf8',
    );
  });
});