import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { createServer, handleApi, poolFacing } from './mineperc_server.js';
import { checkShare } from './beamhash_iii.js';
import { creditAcceptedShare } from './perc_pool_credit.js';

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
    assert.match(f.stratum, /mineperc\.restoreprivacy\.online:3334/);
    assert.match(f.note, /Do not use --coin BEAM/);
    const blob = JSON.stringify(f);
    assert.doesNotMatch(blob, /Beam mining pool/);
    assert.doesNotMatch(blob, /--coin BEAM --/);
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
    assert.match(c.json.stratum, /3334/);
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

describe('createServer launch', () => {
  it('serves the landing page twice with PERC + BeamHash III + stratum', async () => {
    const bodies = [];
    for (let i = 0; i < 2; i++) {
      const srv = createServer({ port: 0 });
      await new Promise((r) => srv.listen(r));
      const { port } = srv.address();
      const res = await fetch(`http://127.0.0.1:${port}/`);
      const text = await res.text();
      const health = await fetch(`http://127.0.0.1:${port}/health`).then((r) => r.json());
      await srv.close();
      bodies.push({ text, health });
    }
    for (const { text, health } of bodies) {
      assert.match(text, /Perccent PERC pool/);
      assert.match(text, /BeamHash III/);
      assert.match(text, /mineperc\.restoreprivacy\.online:3334/);
      assert.doesNotMatch(text, /Beam mining pool/);
      assert.equal(health.coin, 'PERC');
      assert.equal(health.algorithm, 'BeamHash III');
    }
  });
});
