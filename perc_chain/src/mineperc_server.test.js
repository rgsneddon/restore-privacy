import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import net from 'net';
import {
  createServer,
  createStratumServer,
  handleApi,
  percStratumPorts,
  poolFacing,
  seedJob,
} from './mineperc_server.js';
import { checkShare } from './beamhash_iii.js';
import { creditAcceptedShare } from './perc_pool_credit.js';
import { extractSolution, loginReply, minerJob } from './stratum_protocol.js';
import { applyPowToLedger, jobFromLedger } from './pow.js';
import { mineSubmit } from './mine_api.js';
import { startPercMinePool } from './mine_pool.js';

const BH3 = {
  preWork: '990504d96fba29cfd6d9c2f3f8663e511fca10758f33c1e4dea443bbe6c5aac0',
  nonce: '89c94dfd09620712',
  solution:
    'a4eb00a087831aa944d914c2d500b920b74bb86c9f3a1de38b9a0c5d3c18802ed66c6be4494c0cf7ac4b72e18e6a6ee2e4e842e323f6d8df0367df5b8e36bbd057adf9ec3b1817395ac98b481829fef5c247372eb65acbbed65d64d52e17a0bf9b956bff00000000',
};

describe('poolFacing', () => {
  it('names PERC + BeamHash III and does not brand a Beam coin pool', () => {
    const f = poolFacing();
    assert.match(f.product, /Perccent PERC pool/);
    assert.equal(f.coin, 'PERC');
    assert.equal(f.algorithm, 'BeamHash III');
    assert.match(f.stratum, /mineperc\.restoreprivacy\.online:1466/);
    assert.match(f.note, /Do not use --coin BEAM/);
    const blob = JSON.stringify(f);
    assert.doesNotMatch(blob, /Beam mining pool/);
    assert.doesNotMatch(blob, /--coin BEAM --/);
  });
});

describe('percStratumPorts', () => {
  it('defaults to 1466 and refuses Beam 1690/1974', () => {
    assert.deepEqual(percStratumPorts(), [1466]);
    assert.deepEqual(percStratumPorts(undefined), [1466]);
    assert.deepEqual(percStratumPorts(''), []);
    assert.deepEqual(percStratumPorts('none'), []);
    assert.deepEqual(percStratumPorts('1466'), [1466]);
    assert.throws(() => percStratumPorts('1690'), /reserved for Beam/);
    assert.throws(() => percStratumPorts('1466,1974'), /1974/);
  });
});

describe('handleApi', () => {
  it('health and connect expose PERC + BeamHash III', () => {
    const h = handleApi('/health', 'GET');
    assert.equal(h.status, 200);
    assert.equal(h.json.ok, true);
    assert.equal(h.json.coin, 'PERC');
    assert.equal(h.json.algorithm, 'BeamHash III');
    const c = handleApi('/api/connect', 'GET');
    assert.match(c.json.stratum, /1466/);
  });
});

describe('submitShare credit path', () => {
  it('accepted official share is a PERC credit, not BEAM', () => {
    const checked = checkShare(BH3);
    assert.equal(checked.ok, true);
    const rec = creditAcceptedShare({ username: 'alice.rig' });
    assert.equal(rec.asset, 'PERC');
    assert.notEqual(rec.asset, 'BEAM');
  });
});

function minerSession(port) {
  const sock = net.connect({ host: '127.0.0.1', port });
  let buf = '';
  const q = [];
  sock.setEncoding('utf8');
  sock.on('data', (chunk) => {
    buf += chunk;
    let i;
    while ((i = buf.indexOf('\n')) >= 0) {
      const line = buf.slice(0, i).trim();
      buf = buf.slice(i + 1);
      if (line) q.push(JSON.parse(line));
    }
  });
  return {
    write(obj) {
      sock.write(`${JSON.stringify(obj)}\n`);
    },
    take(n, ms = 4000) {
      return new Promise((resolve, reject) => {
        const start = Date.now();
        const tick = () => {
          if (q.length >= n) return resolve(q.splice(0, n));
          if (Date.now() - start > ms) return reject(new Error(`timeout have=${q.length}`));
          setTimeout(tick, 8);
        };
        tick();
      });
    },
    end() {
      sock.end();
    },
  };
}

describe('BeamHash III miner wire', () => {
  it('login is Login Successful and jobs expose 32-byte input', () => {
    const reply = loginReply({ id: 7, method: 'login' }, { nonceprefix: '00000001' });
    assert.equal(reply.method, 'result');
    assert.equal(reply.description, 'Login Successful');
    const job = minerJob({
      jobId: 'j1',
      height: 3,
      input: BH3.preWork,
    });
    assert.equal(job.method, 'job');
    assert.equal(job.input.length, 64);
    assert.doesNotMatch(JSON.stringify(job), /"params"/);
    const sol = extractSolution({
      method: 'solution',
      nonce: BH3.nonce,
      output: BH3.solution,
      id: 'j1',
    });
    assert.equal(sol.output.length, 208);
    assert.equal(sol.nonce.length, 16);
  });

  it('two launches: TLS-shaped login, 32-byte input, solution accept+reject, PERC credit', async () => {
    assert.equal(typeof startPercMinePool, 'function');
    for (let i = 0; i < 2; i++) {
      seedJob({ preWork: BH3.preWork, jobId: `vec-${i}` });
      const srv = createStratumServer({ port: 0, tls: null });
      await new Promise((r) => srv.listen(r));
      const { port } = srv.address();
      const s = minerSession(port);
      s.write({
        id: 1,
        method: 'login',
        params: { login: 'perc_user.gpu0', pass: 'x' },
      });
      const [login, job] = await s.take(2);
      assert.equal(login.method, 'result');
      assert.equal(login.description, 'Login Successful');
      assert.equal(job.method, 'job');
      assert.equal(job.input.length, 64);
      assert.equal(job.input, BH3.preWork);
      assert.equal(job.coin, 'PERC');
      s.write({
        id: 2,
        method: 'solution',
        nonce: BH3.nonce,
        output: BH3.solution,
      });
      const [ok] = await s.take(1);
      assert.equal(ok.method, 'result');
      assert.equal(ok.description, 'accepted');
      assert.equal(ok.credit.asset, 'PERC');
      assert.notEqual(ok.credit.asset, 'BEAM');
      const flipped = Buffer.from(BH3.solution, 'hex');
      flipped[0] ^= 0x01;
      s.write({
        id: 3,
        method: 'solution',
        nonce: BH3.nonce,
        output: flipped.toString('hex'),
      });
      const [bad] = await s.take(1);
      assert.notEqual(bad.description, 'accepted');
      assert.equal(bad.asset, 'PERC');
      s.end();
      await srv.close();
    }
  });
});

describe('mine submit forwards output + username', () => {
  it('jobFromLedger input is 32 bytes and mineSubmit credits PERC', () => {
    const job = jobFromLedger({ blocks: [] });
    assert.equal(job.method, 'job');
    assert.equal(job.input.length, 64);
    assert.equal(job.coin, 'PERC');
    const accepted = mineSubmit(
      { blocks: [] },
      {
        username: 'perc_user.gpu0',
        nonce: BH3.nonce,
        output: BH3.solution,
        input: BH3.preWork,
      },
    );
    assert.equal(accepted.accepted, true);
    assert.equal(accepted.credit.asset, 'PERC');
    const rejected = applyPowToLedger(
      { blocks: [] },
      {
        username: 'perc_user.gpu0',
        nonce: BH3.nonce,
        output: BH3.solution.replace(/^a4/, 'a5'),
        header: { input: BH3.preWork },
      },
    );
    assert.equal(rejected.accepted, false);
  });
});

describe('createServer launch', () => {
  it('serves the landing page twice with PERC + BeamHash III + stratum', async () => {
    const bodies = [];
    for (let i = 0; i < 2; i++) {
      const srv = createServer({ port: 0 });
      await new Promise((r) => srv.listen(r));
      const { port } = srv.address();
      const res = await fetch(`http://127.0.0.1:${port}/`);
      const text = await res.text();
      const js = await fetch(`http://127.0.0.1:${port}/mineperc_parts.js`);
      const jsText = await js.text();
      const health = await fetch(`http://127.0.0.1:${port}/health`).then((r) => r.json());
      await srv.close();
      bodies.push({ text, health, jsStatus: js.status, jsText });
    }
    for (const { text, health, jsStatus, jsText } of bodies) {
      assert.match(text, /Perccent PERC pool/);
      assert.match(text, /BeamHash III/);
      assert.match(text, /mineperc\.restoreprivacy\.online:1466/);
      assert.match(text, /copy-icon/);
      assert.match(text, /--mineperc-longest-ch/);
      assert.doesNotMatch(text, /Beam mining pool/);
      assert.equal(health.coin, 'PERC');
      assert.equal(health.algorithm, 'BeamHash III');
      assert.equal(jsStatus, 200);
      assert.match(jsText, /export function copyPayloadForPart/);
      assert.match(jsText, /export function minWidthChFromParts/);
    }
  });
});
