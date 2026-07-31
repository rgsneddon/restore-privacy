import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import crypto from 'crypto';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { blockTipPayload } from './chain_tip_payload.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const FIXTURE_PATH = path.join(__dirname, '..', 'fixtures', 'tip_payload_canonical.json');
const fixtures = JSON.parse(fs.readFileSync(FIXTURE_PATH, 'utf8'));

function tipHashFromBlock(block) {
  const payload = blockTipPayload(block);
  assert.ok(payload, 'blockTipPayload returned null');
  return crypto.createHash('sha256').update(JSON.stringify(payload)).digest('hex');
}

describe('blockTipPayload Dart parity fixtures', () => {
  for (const [name, row] of Object.entries(fixtures)) {
    it(`${name}: JSON.stringify matches Dart canonicalJson`, () => {
      const payload = blockTipPayload(row.block);
      assert.equal(JSON.stringify(payload), row.canonicalJson);
    });

    it(`${name}: SHA-256 tip hash matches Dart tipHash`, () => {
      assert.equal(tipHashFromBlock(row.block), row.tipHash);
    });
  }

  it('treasury_cycle_two places treasuryCycle before transactions in JSON', () => {
    const row = fixtures.treasury_cycle_two;
    const idxCycle = row.canonicalJson.indexOf('"treasuryCycle"');
    const idxTx = row.canonicalJson.indexOf('"transactions"');
    assert.ok(idxCycle >= 0 && idxTx > idxCycle);
    assert.equal(JSON.stringify(blockTipPayload(row.block)), row.canonicalJson);
  });
});