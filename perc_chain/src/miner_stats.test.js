import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import {
  listMiners,
  poolStatsSnapshot,
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
    recordMinerShare({ username: name, accepted: true, percMicro: 1 });
    const split = splitWorker(name);
    assert.equal(split.user, 'percpriv193bfbb92db68043f010592e879396c724d488b30');
    assert.equal(split.worker, 'raskul');
    const snap = poolStatsSnapshot();
    assert.equal(snap.minersOnline, 1);
    assert.equal(snap.threads, 2);
    assert.equal(snap.accepted, 1);
    assert.equal(snap.workers[0].username, name);
    assert.equal(snap.workers[0].threads, 2);
    assert.equal(snap.workers[0].hashes, 262144);
    assert.equal(snap.workers[0].accepted, 1);
    assert.equal(snap.workers[0].asset, 'PERC');
    const api = handleApi('/api/stats', 'GET');
    assert.equal(api.status, 200);
    assert.equal(api.json.minersOnline, 1);
    assert.equal(api.json.workers[0].worker, 'raskul');
    const posted = handleApi(
      '/api/miner-stats',
      'POST',
      JSON.stringify({ username: name, threads: 4, hashes: 400000, hashrate: 2000 }),
    );
    assert.equal(posted.status, 200);
    assert.equal(posted.json.miner.threads, 4);
    const rows = listMiners();
    assert.equal(rows[0].threads, 4);
  });
});
