import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { blake2b256Personal } from './blake2b_personal.js';
import { siphash24, siphash24Word } from './siphash24.js';
import {
  ALGORITHM,
  COIN,
  buildJob,
  checkShare,
  defaultPreWork,
  individualWork,
} from './beamhash_iii.js';

describe('blake2b256Personal', () => {
  it('matches the unpersonalized Blake2b-256 empty-message digest', () => {
    const d = blake2b256Personal(new Uint8Array(0), new Uint8Array(16));
    assert.equal(
      Buffer.from(d).toString('hex'),
      '0e5751c026e543b2e8ab2eb06099daa1d1e5df47778f7787faab45cdf12fe3a8',
    );
  });
});

describe('siphash24Word', () => {
  it('matches the SipHash-2-4 8-byte official vector', () => {
    const key = Uint8Array.from([
      0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15,
    ]);
    const msg = Uint8Array.from([0, 1, 2, 3, 4, 5, 6, 7]);
    const out = siphash24(key, msg);
    // uint64 hex (same as reference C %016llx / siphash.c).
    assert.equal(out.toString(16).padStart(16, '0'), '93f5f5799a932462');
    assert.equal(
      siphash24(key, new Uint8Array(0)).toString(16).padStart(16, '0'),
      '726fdb47dd0e0e31',
    );
    const word = siphash24Word(key, 0x0706050403020100n);
    assert.equal(word, out);
  });
});

describe('buildJob', () => {
  it('issues Perccent BeamHash III pre-work, not a Beam coin job', () => {
    const job = buildJob({ height: 12, jobId: 'j12' });
    assert.equal(job.algorithm, ALGORITHM);
    assert.equal(job.algorithm, 'beamhashIII');
    assert.equal(job.coin, COIN);
    assert.equal(job.asset, 'PERC');
    assert.equal(job.personal, 'Beam-PoW');
    assert.equal(job.preWork.length, 64);
    assert.equal(job.height, 12);
    assert.doesNotMatch(JSON.stringify(job), /"BEAM"/);
  });

  it('hashes caller-supplied 32-byte Perccent header as pre-work', () => {
    const pre = defaultPreWork(99);
    const job = buildJob({ preWork: pre, height: 99 });
    assert.equal(job.preWork, Buffer.from(pre).toString('hex'));
  });
});

const BH3_HEADER = '990504d96fba29cfd6d9c2f3f8663e511fca10758f33c1e4dea443bbe6c5aac0';
const BH3_NONCE = '89c94dfd09620712';
const BH3_SOLN =
  'a4eb00a087831aa944d914c2d500b920b74bb86c9f3a1de38b9a0c5d3c18802ed66c6be4494c0cf7ac4b72e18e6a6ee2e4e842e323f6d8df0367df5b8e36bbd057adf9ec3b1817395ac98b481829fef5c247372eb65acbbed65d64d52e17a0bf9b956bff00000000';

describe('checkShare', () => {
  it('accepts the published BeamHash III 32+8+104 vector', () => {
    const ok = checkShare({
      preWork: BH3_HEADER,
      nonce: BH3_NONCE,
      solution: BH3_SOLN,
    });
    assert.equal(ok.ok, true, ok.reason);
    assert.equal(ok.coin, 'PERC');
    assert.equal(ok.algorithm, 'beamhashIII');
  });

  it('rejects a mutated solution on the same pre-work + nonce', () => {
    const flipped = Buffer.from(BH3_SOLN, 'hex');
    flipped[0] ^= 0x01;
    const got = checkShare({
      preWork: BH3_HEADER,
      nonce: BH3_NONCE,
      solution: flipped,
    });
    assert.equal(got.ok, false);
  });

  it('rejects wrong wire sizes', () => {
    const pre = defaultPreWork(0);
    const nonce = new Uint8Array(8);
    assert.equal(checkShare({ preWork: pre, nonce, solution: new Uint8Array(10) }).ok, false);
  });
});

describe('individualWork', () => {
  it('feeds 32+8+4 bytes into Blake2B personal BeamHash', () => {
    const pre = new Uint8Array(32).fill(9);
    const nonce = new Uint8Array(8).fill(1);
    const extra = new Uint8Array(4).fill(2);
    const w = individualWork(pre, nonce, extra);
    assert.equal(w.length, 32);
    const again = individualWork(pre, nonce, extra);
    assert.deepEqual(w, again);
    extra[0] = 3;
    const other = individualWork(pre, nonce, extra);
    assert.notDeepEqual(w, other);
  });
});
