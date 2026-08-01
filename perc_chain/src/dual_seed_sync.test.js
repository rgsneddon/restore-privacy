import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import {
  isRemoteLedgerCandidate,
  normalizeEndpoint,
  pickBestLedger,
  resolveNetworkSyncBase,
  selectTallerLedger,
} from './dual_seed_sync.js';
import { blockHeight, shouldImportLedger } from './ledger_store.js';

describe('dual_seed_sync', () => {
  it('resolveNetworkSyncBase prefers upstream over public endpoint', () => {
    assert.equal(
      resolveNetworkSyncBase(
        'https://evolve-perc-internet.onrender.com',
        'https://135.181.152.10.sslip.io/perc',
      ),
      'https://evolve-perc-internet.onrender.com',
    );
    assert.equal(
      resolveNetworkSyncBase('', 'https://135.181.152.10.sslip.io/perc'),
      'https://135.181.152.10.sslip.io/perc',
    );
    assert.equal(
      resolveNetworkSyncBase(
        'https://evolve-perc-internet.onrender.com/',
        'https://135.181.152.10.sslip.io/perc/',
      ),
      'https://evolve-perc-internet.onrender.com',
    );
  });

  it('isRemoteLedgerCandidate allows same seed username on different endpoint', () => {
    const ctx = {
      seedUsername: 'evolve_seed_node',
      localEndpoint: 'https://135.181.152.10.sslip.io/perc',
    };
    // Dual remote seed (Render) — same name, different URL
    assert.equal(
      isRemoteLedgerCandidate(
        {
          sessionUsername: 'evolve_seed_node',
          endpoint: 'https://evolve-perc-internet.onrender.com',
          blockHeight: 97,
        },
        ctx,
      ),
      true,
    );
    // Local self registration
    assert.equal(
      isRemoteLedgerCandidate(
        {
          sessionUsername: 'evolve_seed_node',
          endpoint: 'https://135.181.152.10.sslip.io/perc',
          blockHeight: 0,
        },
        ctx,
      ),
      false,
    );
    // Privacy-masked self
    assert.equal(
      isRemoteLedgerCandidate(
        {
          sessionUsername: 'evolve_seed_node',
          endpoint: 'Private node',
          blockHeight: 10,
        },
        ctx,
      ),
      false,
    );
    // Other peer
    assert.equal(
      isRemoteLedgerCandidate(
        {
          sessionUsername: 'wallet_alice',
          endpoint: 'https://example.test',
          blockHeight: 5,
        },
        ctx,
      ),
      true,
    );
  });

  it('selectTallerLedger adopts Render-height ledger over empty local', () => {
    const local = {
      networkGenesisRevision: 2,
      evolutionaryChainId: 'evolve-chronoflux-principia-chain-1',
      blocks: [],
    };
    const remote = {
      networkGenesisRevision: 2,
      evolutionaryChainId: 'evolve-chronoflux-principia-chain-1',
      blocks: Array.from({ length: 97 }, (_, i) => ({
        index: i,
        transactions: [],
      })),
    };
    assert.equal(blockHeight(local), 0);
    assert.equal(blockHeight(remote), 97);
    assert.equal(shouldImportLedger(local, remote), true);
    const picked = selectTallerLedger(local, remote);
    assert.equal(picked, remote);
    assert.equal(selectTallerLedger(remote, local), null);
  });

  it('pickBestLedger chooses tallest among candidates', () => {
    const short = { blocks: [{ index: 0 }] };
    const tall = { blocks: [{}, {}, {}, {}] };
    assert.equal(pickBestLedger([null, short, tall, undefined]), tall);
    assert.equal(pickBestLedger([]), null);
  });

  it('normalizeEndpoint strips private masks', () => {
    assert.equal(normalizeEndpoint('Private node'), '');
    assert.equal(
      normalizeEndpoint('https://evolve-perc-internet.onrender.com/'),
      'https://evolve-perc-internet.onrender.com',
    );
  });
});
