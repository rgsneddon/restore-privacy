import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import {
  PED_MINUTE,
  SEAL_MINUTES,
  TARGET_BLOCKS_PER_HOUR,
  grokSessionStatus,
  mintIterationScenario,
  pedObserveX,
  pickEvolveWallet,
  sealIdempotencyKey,
  sealWho,
  shouldSealNow,
} from './rpai_ped.js';
import { resetSharedNedState, explorerNedPayload, getSharedNedState } from './ned_learn.js';

describe('PEDRO rpAI iteration', () => {
  it('seals at :14 FRED, :34 PEDRO, :54 GOD for three blocks per hour', () => {
    assert.equal(PED_MINUTE, 34);
    assert.deepEqual([...SEAL_MINUTES], [14, 34, 54]);
    assert.equal(TARGET_BLOCKS_PER_HOUR, 3);
    assert.equal(SEAL_MINUTES.length, 3);
    const ped = Date.UTC(2026, 7, 14, 12, 34, 10);
    const fred = Date.UTC(2026, 7, 14, 12, 14, 10);
    const god = Date.UTC(2026, 7, 14, 12, 54, 10);
    const other = Date.UTC(2026, 7, 14, 12, 20, 10);
    assert.equal(sealWho(ped), 'PEDRO');
    assert.equal(sealWho(fred), 'FRED');
    assert.equal(sealWho(god), 'GOD');
    assert.equal(sealWho(other), null);
    const first = shouldSealNow(ped, '');
    assert.equal(first.due, true);
    assert.equal(first.who, 'PEDRO');
    const again = shouldSealNow(ped, first.key);
    assert.equal(again.due, false);
    assert.ok(sealIdempotencyKey(ped).endsWith('1234'));
  });

  it('construes via rgsneddon wallet when present, else another evolve account', () => {
    assert.equal(
      pickEvolveWallet({ accounts: { rgsneddon: {}, evolve_treasury: {} } }),
      'rgsneddon',
    );
    assert.equal(
      pickEvolveWallet({ accounts: { wEVXd: {}, evolve_treasury: {} } }),
      'wEVXd',
    );
    assert.equal(pickEvolveWallet({ accounts: {} }), 'rgsneddon');
  });

  it('Grok observe falls back without key and mints a PEDRO scenario block', async () => {
    const prev = process.env.XAI_API_KEY;
    delete process.env.XAI_API_KEY;
    const obs = await pedObserveX('rgsneddon');
    assert.equal(obs.ok, true);
    assert.equal(obs.grok, false);
    assert.match(obs.line, /PEDRO/);
    const session = grokSessionStatus();
    assert.equal(session.perpetual, false);
    assert.equal(session.observe, 'https://x.com');
    const ledger = { blocks: [], accounts: { rgsneddon: { username: 'rgsneddon' } } };
    const minted = mintIterationScenario(ledger, {
      who: 'PEDRO',
      label: 'PEDRO · X.com',
      memo: obs.line,
      wallet: 'rgsneddon',
    });
    assert.equal(minted.ok, true);
    assert.equal(ledger.blocks.length, 1);
    assert.equal(ledger.blocks[0].triggerUsername, 'rgsneddon');
    assert.equal(ledger.blocks[0].adminActionKind, 'pedro_scenario');
    if (prev == null) delete process.env.XAI_API_KEY;
    else process.env.XAI_API_KEY = prev;
  });

  it('explorer iterations include PEDRO under NED under GOD', () => {
    resetSharedNedState();
    const payload = explorerNedPayload(getSharedNedState());
    assert.equal(payload.identity, 'GOD · rpAI');
    const ids = payload.iterations.map((r) => r.id);
    assert.ok(ids.includes('PEDRO'));
    assert.ok(!ids.includes('PED'));
    assert.ok(ids.includes('NED'));
    assert.ok(ids.includes('FRED'));
    assert.ok(ids.includes('GOD'));
    assert.equal(payload.iterations.find((r) => r.id === 'NED').reportsTo, 'GOD');
    assert.equal(payload.iterations.find((r) => r.id === 'PEDRO').reportsTo, 'NED');
  });
});
