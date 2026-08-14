import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import {
  HASH_PRESENCE_MS,
  hydrateMinepercIndex,
  listMiners,
  minerIsListed,
  poolHasRunningMiner,
  poolStatsSnapshot,
  recordMinerDisconnect,
  recordMinerLogin,
  recordMinerShare,
  recordMinerStats,
  resetMinerStats,
  splitWorker,
} from './miner_stats.js';
import { handleApi } from './mineperc_server.js';

describe('miner stats book', () => {
  it('login + stats + share appear in pool snapshot', () => {
    resetMinerStats();
    const name = 'percpriv193bfbb92db68043f010592e879396c724d488b30.raskul';
    recordMinerLogin({ username: name, remote: '127.0.0.1', port: 1466 });
    recordMinerStats({
      username: name,
      threads: 2,
      hashes: 262144,
      hashrate: 1200,
      version: '1.0.1',
    });
    const beforeShare = poolStatsSnapshot();
    assert.equal(beforeShare.minersOnline, 1);
    assert.equal(beforeShare.workers.length, 1);
    const hashedAt = Date.now();
    recordMinerShare({ username: name, accepted: true, percMicro: 1, now: hashedAt });
    assert.equal(minerIsListed({ lastHashAt: hashedAt }, hashedAt), true);
    assert.equal(minerIsListed({ lastHashAt: hashedAt }, hashedAt + HASH_PRESENCE_MS), true);
    assert.equal(minerIsListed({ lastHashAt: hashedAt }, hashedAt + HASH_PRESENCE_MS + 1), false);
    assert.equal(minerIsListed({ connected: true, sessionShares: 1 }), true);
    const split = splitWorker(name);
    assert.equal(split.user, 'percpriv193bfbb92db68043f010592e879396c724d488b30');
    assert.equal(split.worker, 'raskul');
    const snap = poolStatsSnapshot(hashedAt);
    assert.equal(snap.minersOnline, 1);
    assert.equal(snap.threads, 2);
    assert.equal(snap.accepted, 1);
    assert.equal(snap.workers[0].wallet, split.user);
    assert.equal(snap.workers[0].worker, 'raskul');
    assert.equal(snap.workers[0].threads, 2);
    assert.equal(snap.workers[0].hashes, 262144);
    assert.equal(snap.workers[0].accepted, 1);
    assert.equal(snap.workers[0].asset, 'PERC');
    assert.equal(snap.workers[0].remote, undefined);
    assert.equal(snap.workers[0].username, undefined);
    const api = handleApi('/api/stats', 'GET');
    assert.equal(api.status, 200);
    assert.equal(api.json.workers[0].wallet, split.user);
    const posted = handleApi(
      '/api/miner-stats',
      'POST',
      JSON.stringify({ username: name, threads: 4, hashes: 400000, hashrate: 2000, now: hashedAt }),
    );
    assert.equal(posted.status, 200);
    assert.equal(posted.json.miner.threads, 4);
    const rows = listMiners(hashedAt);
    assert.equal(rows[0].threads, 4);
    recordMinerDisconnect(name);
    const still = poolStatsSnapshot(hashedAt + 1_000);
    assert.equal(still.minersOnline, 1);
    assert.equal(still.workers[0].wallet, split.user);
    assert.equal(listMiners(hashedAt + HASH_PRESENCE_MS + 1).length, 0);
  });

  it('public snapshot is wallet + worker and never includes IP', () => {
    resetMinerStats();
    const ip = '203.0.113.77';
    const login = 'percprivWALLETADDR00000000000000000000001.rig1';
    recordMinerLogin({ username: login, remote: ip, port: 1466 });
    recordMinerShare({ username: login, accepted: false, now: 8_000 });
    const snap = poolStatsSnapshot(8_000);
    const blob = JSON.stringify(snap.workers);
    assert.equal(snap.workers[0].wallet, splitWorker(login).user);
    assert.equal(snap.workers[0].worker, 'rig1');
    assert.ok(!Object.prototype.hasOwnProperty.call(snap.workers[0], 'remote'));
    assert.ok(!Object.prototype.hasOwnProperty.call(snap.workers[0], 'username'));
    assert.equal(blob.includes(ip), false);
    assert.equal(blob.includes('203.0.113'), false);
  });

  it('login lists immediately; hash keeps them after disconnect for 72s', () => {
    resetMinerStats();
    const t0 = 5_000_000;
    recordMinerLogin({ username: 'bob.rig' });
    assert.equal(listMiners(t0).map((m) => m.wallet).includes('bob'), true);
    recordMinerStats({ username: 'bob.rig', threads: 1, hashes: 10, hashrate: 1, now: t0 });
    recordMinerShare({ username: 'bob.rig', accepted: false, now: t0 });
    recordMinerDisconnect('bob.rig');
    assert.equal(listMiners(t0).map((m) => m.wallet).includes('bob'), true);
    assert.equal(listMiners(t0 + HASH_PRESENCE_MS).length, 1);
    assert.equal(listMiners(t0 + HASH_PRESENCE_MS + 1).length, 0);
  });

  it('hydrateMinepercIndex writes the connected wallet into the landing table', () => {
    resetMinerStats();
    recordMinerLogin({ username: 'percpriv1a2e59c690fa6ad8efb206a40743342fad429823a.raskul' });
    recordMinerStats({
      username: 'percpriv1a2e59c690fa6ad8efb206a40743342fad429823a.raskul',
      threads: 1,
      hashes: 1000,
      hashrate: 500,
    });
    const html = hydrateMinepercIndex(`
      <div id="stat-online">0</div>
      <div id="stat-threads">0</div>
      <div id="stat-height">0</div>
      <div id="stat-hashrate">0 H/s</div>
      <div id="stat-hashes">0</div>
      <div id="stat-accepted">0</div>
      <div id="stat-rejected">0</div>
      <div id="stat-perc">0</div>
      <tbody id="miner-body">
        <tr><td colspan="6" class="off">No miners connected.</td></tr>
      </tbody>`);
    assert.ok(html.includes('id="stat-online">1'));
    assert.ok(html.includes('percpriv1a2e59c690fa6ad8efb206a40743342fad429823a'));
    assert.ok(html.includes('raskul'));
  });

  it('poolHasRunningMiner is true while connected even if not listed', () => {
    resetMinerStats();
    assert.equal(poolHasRunningMiner(), false);
    recordMinerLogin({ username: 'rig.a' });
    assert.equal(poolHasRunningMiner(), true);
    recordMinerDisconnect('rig.a');
    assert.equal(poolHasRunningMiner(), false);
  });
});
