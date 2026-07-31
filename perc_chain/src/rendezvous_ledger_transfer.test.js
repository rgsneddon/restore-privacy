import { describe, it, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'fs';
import os from 'os';
import path from 'path';
import { LedgerStore } from './ledger_store.js';
import { createGenesisLedger } from './genesis.js';
import { genericBlockLabel } from './block_display_label.js';
import { getBlockDetail, listBlocks } from './explorer_api.js';

const CHAIN_ID = 'evolve-chronoflux-principia-chain-1';
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
  };
}

function ledgerWithTransfer(previous) {
  const index = previous.blocks.length;
  return {
    ...previous,
    blocks: [
      ...previous.blocks,
      {
        index,
        timestamp: '2026-07-06T12:00:00.000Z',
        triggerUsername: 'android_user',
        transactions: [
          {
            id: 'tx-transfer-cross',
            kind: 'transfer',
            fromUsername: 'android_user',
            toUsername: 'windows_user',
            amount: { microUnits: 10 },
            memo: 'Cross-device send',
            timestamp: '2026-07-06T12:00:00.000Z',
          },
          {
            id: 'tx-fee-cross',
            kind: 'feeBurn',
            fromUsername: 'android_user',
            amount: { microUnits: 1 },
            memo: 'Burned network fee',
          },
        ],
      },
    ],
    microblocksPerBlock: MICROBLOCKS_PER_BLOCK,
  };
}

describe('rendezvous ledger gossip imports transfer blocks into seed store', () => {
  let tmpDir;

  beforeEach(() => {
    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'perc-rendezvous-transfer-'));
  });

  afterEach(() => {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  });

  it('peer PUT ledger taller than seed exposes Manual tx on /api/blocks shape', () => {
    const store = new LedgerStore(tmpDir);
    const genesis = launchLedger(
      createGenesisLedger({ genesisRevision: 2, chainId: CHAIN_ID }),
    );
    store.forceReplaceLedger(genesis);

    const peerLedger = ledgerWithTransfer(genesis);
    assert.equal(peerLedger.blocks.length, genesis.blocks.length + 1);

    const imported = store.importLedger(peerLedger);
    assert.equal(imported, true, 'seed should import taller peer ledger');

    const transferIndex = peerLedger.blocks.length - 1;
    const block = store.ledger.blocks[transferIndex];
    assert.equal(genericBlockLabel(block), 'Manual tx');

    const detail = getBlockDetail(store.ledger, transferIndex);
    assert.ok(detail);
    assert.equal(detail.displayLabel, 'Manual tx');
    const transfer = detail.transactions.find((tx) => tx.kind === 'transfer');
    assert.ok(transfer);
    assert.equal(transfer.from, 'android_user');
    assert.equal(transfer.to, 'windows_user');
    assert.equal(transfer.amount, '0.0000001');

    const listing = listBlocks(store.ledger, { offset: 0, limit: 50 });
    const listed = listing.blocks.find((b) => b.index === transferIndex);
    assert.ok(listed);
    assert.equal(listed.displayLabel, 'Manual tx');
    assert.equal(store.ledger.microblocksPerBlock ?? MICROBLOCKS_PER_BLOCK, MICROBLOCKS_PER_BLOCK);
  });

  it('shorter peer without new transfers does not change taller seed ledger', () => {
    const store = new LedgerStore(tmpDir);
    const tall = ledgerWithTransfer(
      launchLedger(createGenesisLedger({ genesisRevision: 2, chainId: CHAIN_ID })),
    );
    store.forceReplaceLedger(tall);

    const short = launchLedger(createGenesisLedger({ genesisRevision: 2, chainId: CHAIN_ID }));
    const imported = store.importLedger(short);
    assert.equal(imported, false);
    assert.equal(store.ledger.blocks.length, tall.blocks.length);
  });

  it('shorter peer with new transfer merges onto taller seed without replacing tip', () => {
    const store = new LedgerStore(tmpDir);
    let tall = launchLedger(createGenesisLedger({ genesisRevision: 2, chainId: CHAIN_ID }));
    for (let i = 0; i < 2; i += 1) {
      tall = {
        ...tall,
        blocks: [
          ...tall.blocks,
          {
            index: tall.blocks.length,
            timestamp: `2026-07-06T11:0${i}:00.000Z`,
            scenarioLabel: `Seed scenario ${i + 1}`,
            transactions: [{ id: `tx-seed-${i}`, kind: 'scenarioReward' }],
          },
        ],
      };
    }
    store.forceReplaceLedger(tall);

    const shortBase = launchLedger(createGenesisLedger({ genesisRevision: 2, chainId: CHAIN_ID }));
    const short = ledgerWithTransfer(shortBase);
    assert.ok(short.blocks.length < tall.blocks.length, 'peer relay must be shorter than seed');

    const imported = store.importLedger(short);
    assert.equal(imported, true);
    assert.equal(store.ledger.blocks.length, tall.blocks.length);

    const transferIndex = short.blocks.length - 1;
    const detail = getBlockDetail(store.ledger, transferIndex);
    assert.ok(detail.transactions.some((tx) => tx.kind === 'transfer'));
    assert.equal(detail.transactions.find((tx) => tx.kind === 'transfer').id, 'tx-transfer-cross');
    assert.equal(store.ledger.blocks[transferIndex].index, transferIndex);
    assert.equal(store.ledger.blocks[transferIndex].relaySourceBlockIndex, undefined);
  });
});