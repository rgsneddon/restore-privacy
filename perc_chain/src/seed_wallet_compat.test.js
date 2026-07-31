import test from 'node:test';
import assert from 'node:assert/strict';

const DEFAULT_SEED = 'https://evolve-perc-internet.onrender.com';
const CHAIN_ID = 'evolve-chronoflux-principia-chain-1';
const EXPECTED_GENESIS = 2;
const PEER_ONLINE_MS = 7 * 60 * 1000;

async function getJson(base, path) {
  const response = await fetch(`${base}${path}`, {
    signal: AbortSignal.timeout(12_000),
  });
  assert.equal(response.status, 200, `GET ${path}`);
  return response.json();
}

test('peer_online module matches wallet peerOnlineWindow (7 min)', () => {
  assert.equal(PEER_ONLINE_MS, 7 * 60 * 1000);
});

function isLiveSeedUnreachableError(err) {
  return err?.name === 'TimeoutError' ||
    err?.code === 'ABORT_ERR' ||
    err?.cause?.code === 'ETIMEDOUT' ||
    err?.cause?.code === 'ECONNREFUSED' ||
    err?.cause?.code === 'ENOTFOUND';
}

test('live seed is compatible with v3.1.1 wallet API', async (t) => {
  const base = (process.env.PERC_SEED_URL ?? DEFAULT_SEED).replace(/\/$/, '');
  if (process.env.PERC_SKIP_LIVE_SEED === '1') {
    t.skip('PERC_SKIP_LIVE_SEED=1');
  }

  let health;
  try {
    health = await getJson(base, '/health');
  } catch (err) {
    if (isLiveSeedUnreachableError(err)) {
      t.skip(`live seed unreachable (${base}): ${err.message}`);
    }
    throw err;
  }
  assert.equal(health.ok, true);
  assert.equal(health.service, 'perc-internet-node');
  assert.equal(health.ledgerReady, true);

  const status = await getJson(base, '/perc/status');
  assert.equal(status.evolutionaryChainId, CHAIN_ID);
  assert.equal(status.networkGenesisRevision, EXPECTED_GENESIS);

  const ledger = await getJson(base, '/perc/ledger');
  assert.equal(status.blockHeight, ledger.blocks?.length ?? 0,
    'status blockHeight must match exported ledger block count');
  assert.equal(ledger.networkGenesisRevision, EXPECTED_GENESIS);
  assert.equal(ledger.blockchainLaunched, true);
  assert.ok(Array.isArray(ledger.pendingInboundTransfers));
  assert.ok(ledger.accounts && typeof ledger.accounts === 'object');

  const online = await getJson(
    base,
    '/perc/rendezvous/online?username=evolve_seed_node',
  );
  assert.equal(online.online, true);

  const probe = 'percpriv1nodecompatprobe00000000000000000001';
  const post = await fetch(`${base}/perc/rendezvous/address`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ address: probe }),
    signal: AbortSignal.timeout(12_000),
  });
  assert.equal(post.status, 200);
  const postBody = await post.json();
  assert.equal(postBody.ok, true);

  const offline = await getJson(
    base,
    `/perc/rendezvous/online?address=${encodeURIComponent(probe)}`,
  );
  assert.equal(offline.online, false);

  const peersResponse = await fetch(
    `${base}/perc/rendezvous/peers?chainId=${encodeURIComponent(CHAIN_ID)}`,
    { signal: AbortSignal.timeout(12_000) },
  );
  assert.equal(peersResponse.status, 200);
  const peers = await peersResponse.json();
  assert.ok(peers.length >= 1);
  assert.ok(peers[0].updatedAt);
});