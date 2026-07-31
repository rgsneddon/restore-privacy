import { describe, it, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'fs';
import http from 'http';
import os from 'os';
import path from 'path';
import { fileURLToPath } from 'url';
import { LedgerStore } from './ledger_store.js';
import { createGenesisLedger } from './genesis.js';
import { applyRelayLedgerPut } from './rendezvous_ledger_put.js';
import { getBlockDetail } from './explorer_api.js';
import { collectTreasuryPayoutTxIds } from './treasury_merge.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(__dirname, '..', '..');
const FIXTURE_PATH = path.join(REPO_ROOT, 'perc_chain', 'fixtures', 'relay_after_send.json');
const CHAIN_ID = 'evolve-chronoflux-principia-chain-1';
const SEED_USERNAME = 'evolve_seed_node';
const MICROBLOCKS_PER_BLOCK = 100_000_000;

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

function createPutHandler(ctx) {
  return async (req, res) => {
    if (req.method === 'PUT' && req.url === '/perc/rendezvous/ledger') {
      let body = '';
      req.on('data', (chunk) => {
        body += chunk;
      });
      req.on('end', () => {
        const data = body ? JSON.parse(body) : {};
        const result = applyRelayLedgerPut({
          store: ctx.store,
          ledgers: ctx.ledgers,
          addresses: ctx.addresses,
          username: data.username,
          ledger: data.ledger,
          seedUsername: SEED_USERNAME,
        });
        res.writeHead(result.ok ? 200 : 400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify(result.ok ? { ok: true, imported: result.imported } : result));
      });
      return;
    }
    res.writeHead(404);
    res.end();
  };
}

describe('rendezvous PUT relay path promotes transfer blocks into seed store', () => {
  let tmpDir;

  beforeEach(() => {
    assert.ok(fs.existsSync(FIXTURE_PATH), 'run flutter test test/write_send_relay_fixture_test.dart first');
    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'perc-rendezvous-put-'));
  });

  afterEach(() => {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  });

  it('golden path: PercLedger.send fixture preserves tx.id on seed after PUT', () => {
    const fixture = loadSendRelayFixture();
    const senderRelay = fixture.ledger;
    const expectedTxId = fixture.transferTxId;
    const store = new LedgerStore(tmpDir);
    let tall = launchLedger(createGenesisLedger({ genesisRevision: 2, chainId: CHAIN_ID }));
    tall = scenarioBlock(tall, tall.blocks.length, 'Seed scenario A');
    tall = scenarioBlock(tall, tall.blocks.length, 'Seed scenario B');
    store.forceReplaceLedger(tall);
    const seedHeightBefore = tall.blocks.length;

    assert.ok(senderRelay.blocks.length < seedHeightBefore);

    const ledgers = new Map();
    const addresses = new Map();
    const result = applyRelayLedgerPut({
      store,
      ledgers,
      addresses,
      username: 'android_user',
      ledger: senderRelay,
      seedUsername: SEED_USERNAME,
    });

    assert.equal(result.ok, true);
    assert.equal(result.imported, true);

    const promoted = store.ledger.blocks.find((b) =>
      (b.transactions ?? []).some((tx) => tx.id === expectedTxId),
    );
    assert.ok(promoted);
    const knownPayouts = collectTreasuryPayoutTxIds(tall);
    const treasuryPromotions = (senderRelay.blocks ?? []).filter((block) =>
      (block.transactions ?? []).some(
        (tx) =>
          (tx.kind === 'scenarioReward' || tx.kind === 'stakingReward') &&
          tx.id &&
          !knownPayouts.has(tx.id),
      ),
    ).length;
    assert.equal(store.ledger.blocks.length, seedHeightBefore + treasuryPromotions);
    assert.equal(promoted.index, fixture.transferBlockIndex);
    assert.equal(promoted.relaySourceBlockIndex, undefined);
    assert.equal(
      promoted.transactions.find((tx) => tx.kind === 'transfer').blockIndex,
      fixture.transferBlockIndex,
    );

    const detail = getBlockDetail(store.ledger, fixture.transferBlockIndex);
    assert.ok(detail);
    assert.equal(detail.displayLabel, 'Manual tx');
    const transfer = detail.transactions.find((tx) => tx.kind === 'transfer');
    assert.ok(transfer);
    assert.equal(transfer.id, expectedTxId);
    assert.equal(transfer.kind, 'transfer');
  });

  it('HTTP PUT /perc/rendezvous/ledger imports send fixture with same tx.id', async () => {
    const fixture = loadSendRelayFixture();
    const senderRelay = fixture.ledger;
    const expectedTxId = fixture.transferTxId;

    const store = new LedgerStore(tmpDir);
    let tall = launchLedger(createGenesisLedger({ genesisRevision: 2, chainId: CHAIN_ID }));
    tall = scenarioBlock(tall, tall.blocks.length, 'Seed activity');
    store.forceReplaceLedger(tall);

    const ctx = { store, ledgers: new Map(), addresses: new Map() };
    const server = http.createServer(createPutHandler(ctx));

    await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
    const { port } = server.address();

    try {
      const response = await fetch(`http://127.0.0.1:${port}/perc/rendezvous/ledger`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: 'android_user', ledger: senderRelay }),
      });
      assert.equal(response.status, 200);
      const payload = await response.json();
      assert.equal(payload.ok, true);
      assert.equal(payload.imported, true);

      const detail = getBlockDetail(store.ledger, fixture.transferBlockIndex);
      assert.equal(detail.displayLabel, 'Manual tx');
      const transfer = detail.transactions.find((tx) => tx.kind === 'transfer');
      assert.equal(transfer.id, expectedTxId);
      assert.equal(transfer.kind, 'transfer');
    } finally {
      await new Promise((resolve) => server.close(resolve));
    }
  });
});