import test from 'node:test';
import assert from 'node:assert/strict';
import { mergeUpstreamPeers } from './upstream_rendezvous.js';

const CHAIN = 'evolve-chronoflux-principia-chain-1';

test('mergeUpstreamPeers adds remote seeds to empty local map', () => {
  const peers = new Map();
  const merged = mergeUpstreamPeers(peers, [
    {
      sessionUsername: 'evolve_seed_node',
      endpoint: 'https://evolve-perc-internet.onrender.com',
      evolutionaryChainId: CHAIN,
      blockHeight: 32,
      tipHash: 'abc',
      revision: 40,
    },
  ], CHAIN);
  assert.equal(merged, 1);
  assert.equal(peers.size, 1);
  assert.equal(peers.get('evolve_seed_node').endpoint, 'https://evolve-perc-internet.onrender.com');
});

test('mergeUpstreamPeers ignores wrong chain id', () => {
  const peers = new Map();
  const merged = mergeUpstreamPeers(peers, [
    { sessionUsername: 'other', endpoint: 'https://x', evolutionaryChainId: 'other-chain' },
  ], CHAIN);
  assert.equal(merged, 0);
  assert.equal(peers.size, 0);
});

test('mergeUpstreamPeers accepts publicAlias-only upstream records', () => {
  const peers = new Map();
  const merged = mergeUpstreamPeers(peers, [
    {
      publicAlias: 'd4q4e',
      endpoint: 'https://evolve-perc-internet.onrender.com',
      evolutionaryChainId: CHAIN,
      blockHeight: 32,
      revision: 40,
    },
  ], CHAIN);
  assert.equal(merged, 1);
  const stored = peers.get('d4q4e');
  assert.equal(stored.endpoint, 'https://evolve-perc-internet.onrender.com');
  assert.equal(stored.publicAlias, 'd4q4e');
  assert.equal(stored.sessionUsername, undefined);
});

test('mergeUpstreamPeers does not re-obfuscate sanitized publicAlias on export', async () => {
  const { sanitizePeerForPublic } = await import('./account_privacy.js');
  const peers = new Map();
  mergeUpstreamPeers(peers, [
    {
      publicAlias: 'nvz9p',
      endpoint: 'Private node',
      evolutionaryChainId: CHAIN,
      blockHeight: 0,
      revision: 1,
    },
  ], CHAIN);
  const stored = peers.get('nvz9p');
  const exported = sanitizePeerForPublic(stored);
  assert.equal(exported.publicAlias, 'nvz9p');
});

test('publicAlias-only merged peers are not hidden from rendezvous export', async () => {
  const { isHiddenPeer } = await import('./explorer_api.js');
  const { sanitizePeersForPublic } = await import('./account_privacy.js');
  const peers = new Map([
    [
      'seed_beta',
      {
        sessionUsername: 'seed_beta',
        endpoint: 'http://127.0.0.1:9479',
        evolutionaryChainId: CHAIN,
        blockHeight: 0,
        revision: 1,
        updatedAt: Date.now(),
      },
    ],
  ]);
  mergeUpstreamPeers(peers, [
    {
      publicAlias: 'nvz9p',
      endpoint: 'Private node',
      evolutionaryChainId: CHAIN,
      blockHeight: 0,
      revision: 1,
    },
  ], CHAIN);
  const visible = [...peers.values()].filter((p) => !isHiddenPeer(p.sessionUsername));
  assert.equal(visible.length, 2);
  const aliases = sanitizePeersForPublic(visible)
    .map((p) => p.publicAlias)
    .sort();
  assert.deepEqual(aliases, ['WGG9A', 'nvz9p']);
});

test('mergeUpstreamPeers keeps newer local revision', () => {
  const peers = new Map([
    ['local_seed', { sessionUsername: 'local_seed', endpoint: 'http://127.0.0.1:9', revision: 50, blockHeight: 10 }],
  ]);
  mergeUpstreamPeers(peers, [
    { sessionUsername: 'local_seed', endpoint: 'https://stale', revision: 10, blockHeight: 99 },
  ], CHAIN);
  assert.equal(peers.get('local_seed').endpoint, 'http://127.0.0.1:9');
});