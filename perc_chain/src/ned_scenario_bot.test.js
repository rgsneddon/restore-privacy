import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import {
  FRED_USERNAME,
  NED_USERNAME,
  applyNedHourlyPair,
  faucetMicroForOutcome,
  minerBookIsRunning,
  parseXHeadlines,
  scenarioRecipients,
  stakingMicroForHeld,
  uniqueScenarioPair,
} from './ned_scenario_bot.js';

function emptyLedger() {
  return {
    accounts: {
      evolve_treasury: {
        username: 'evolve_treasury',
        balance: { microUnits: 10_000_000_000 },
        transactions: [],
      },
      alice: { username: 'alice', balance: { microUnits: 200_000_000 }, transactions: [] },
      bob: { username: 'bob', balance: { microUnits: 0 }, transactions: [] },
    },
    blocks: [],
  };
}

describe('ned/fred scenario bot', () => {
  it('pays only the agent when no miners are listed', () => {
    const ledger = emptyLedger();
    const got = applyNedHourlyPair(ledger, {
      minerWallets: [],
      now: new Date('2026-08-14T10:14:00Z'),
    });
    assert.equal(got.percent.ok, true);
    assert.deepEqual(got.percent.recipients, ['ned']);
    assert.ok(ledger.accounts.ned.balance.microUnits > 0);
    assert.ok(got.percent.blockGen?.count >= 1);
    assert.ok(
      (ledger.accounts.alice.transactions || []).some(
        (t) => t.kind === 'block_gen_reward',
      ),
    );
    assert.ok(ledger.accounts.alice.balance.microUnits > 200_000_000);
    assert.equal(got.initiator, NED_USERNAME);
    assert.equal(ledger.blocks.length, 2);
    assert.match(got.percent.label, /^Percent chance:/);
    assert.match(got.cohesion.label, /^Social cohesion score:/);
  });

  it('miner running: every user including miners gets the same faucet', () => {
    const ledger = emptyLedger();
    const aliceHeld = ledger.accounts.alice.balance.microUnits;
    const got = applyNedHourlyPair(ledger, {
      minerWallets: ['bob'],
      minerRunning: true,
      now: new Date('2026-08-14T10:14:00Z'),
    });
    assert.equal(got.percent.ok, true);
    const unitP = got.percent.unit;
    const unitC = got.cohesion.unit;
    assert.equal(unitP, faucetMicroForOutcome(got.percent.score));
    assert.ok(got.percent.recipients.includes('ned'));
    assert.ok(got.percent.recipients.includes('bob'));
    assert.ok(got.percent.recipients.includes('alice'));
    const extra =
      (got.percent.blockGen?.unit || 0) + (got.cohesion.blockGen?.unit || 0);
    assert.equal(ledger.accounts.ned.balance.microUnits, unitP + unitC + extra);
    assert.equal(ledger.accounts.bob.balance.microUnits, unitP + unitC + extra);
    assert.equal(ledger.accounts.alice.balance.microUnits, aliceHeld + unitP + unitC + extra);
    assert.equal(got.percent.stakePays.length, 0);
  });

  it('fred at :52 is a distinct initiator and hour salt', () => {
    const now = new Date('2026-08-14T10:52:00Z');
    const ned = uniqueScenarioPair(now, [], NED_USERNAME);
    const fred = uniqueScenarioPair(now, [], FRED_USERNAME);
    assert.notEqual(ned.hourKey, fred.hourKey);
    const ledger = emptyLedger();
    const got = applyNedHourlyPair(ledger, {
      initiator: FRED_USERNAME,
      minerWallets: [],
      now,
    });
    assert.equal(got.initiator, 'fred');
    assert.deepEqual(got.percent.recipients, ['fred']);
    assert.ok(ledger.accounts.fred.balance.microUnits > 0);
  });

  it('hour key changes the pair; miner book reads pool workers', () => {
    const a = uniqueScenarioPair(new Date('2026-08-14T10:14:00Z'));
    const b = uniqueScenarioPair(new Date('2026-08-14T11:14:00Z'));
    assert.notEqual(a.hourKey, b.hourKey);
    assert.equal(minerBookIsRunning({ minersOnline: 1, workers: [] }), true);
    assert.equal(minerBookIsRunning({ minersOnline: 0, workers: [{ connected: true }] }), true);
    assert.equal(minerBookIsRunning({ minersOnline: 0, workers: [] }), false);
    const heads = parseXHeadlines(
      '# Hello world this is a long enough headline about civic trust\nshort\n',
    );
    assert.ok(heads.some((h) => /civic trust/i.test(h)));
    assert.deepEqual(scenarioRecipients(emptyLedger(), { minerWallets: [] }), ['ned']);
  });
});
