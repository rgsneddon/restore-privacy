import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import {
  GOD_IDENTITY,
  NED_ITERATION,
  FRED_ITERATION,
  SCENARIO_INTERVAL_SEC,
  applyObservation,
  emptyNedState,
  emptyFredState,
  explorerNedPayload,
  resetSharedNedState,
  seedPercPoolCores,
  scenarioDue,
  tickFredCalculation,
  getSharedNedState,
} from './ned_learn.js';

describe('GOD iterations NED + FRED', () => {
  it('explorer payload identity is GOD · rpAI never NED · rpAI', () => {
    resetSharedNedState();
    const st = getSharedNedState();
    const payload = explorerNedPayload(st);
    assert.equal(payload.identity, GOD_IDENTITY);
    assert.notEqual(payload.identity, 'NED · rpAI');
    assert.ok(payload.learned >= 4);
    const ids = payload.iterations.map((r) => r.id);
    assert.deepEqual(ids, ['GOD', NED_ITERATION, FRED_ITERATION, 'PEDRO']);
    const ned = payload.iterations.find((r) => r.id === 'NED');
    assert.equal(ned.role, 'hierarchical leader under GOD');
    assert.equal(ned.reportsTo, 'GOD');
    assert.equal(ned.mayLearn, true);
    assert.equal(ned.learned, payload.learned);
    const pedro = payload.iterations.find((r) => r.id === 'PEDRO');
    assert.equal(pedro.reportsTo, 'NED');
    assert.equal(pedro.mayLearn, true);
    const fred = payload.iterations.find((r) => r.id === 'FRED');
    assert.equal(fred.intervalSec, SCENARIO_INTERVAL_SEC);
    assert.equal(fred.role, 'Helsinki scenario bot');
  });

  it('FRED two-hour cadence records a scenario then waits', () => {
    const t0 = 1_700_000_000_000;
    let fred = emptyFredState();
    const first = tickFredCalculation(fred, t0, {
      source: 'self',
      question: 'Helsinki scenario check',
    });
    assert.equal(first.grew, true);
    assert.equal(first.state.scenarios, 1);
    assert.equal(first.state.nextAt, t0 + SCENARIO_INTERVAL_SEC * 1000);
    const tooSoon = tickFredCalculation(first.state, t0 + 60_000);
    assert.equal(tooSoon.grew, false);
    const later = tickFredCalculation(
      first.state,
      t0 + SCENARIO_INTERVAL_SEC * 1000,
      { source: 'web', question: 'Public Downloads Map pin?' },
    );
    assert.equal(later.grew, true);
    assert.equal(later.state.scenarios, 2);
    assert.equal(later.state.lastSource, 'web');
    assert.equal(scenarioDue(t0, t0 + 1000), false);
    assert.equal(scenarioDue(0, t0), true);
  });

  it('NED observations stay non-personal and count as absorbed stats', () => {
    const st = emptyNedState();
    seedPercPoolCores(st);
    const blocked = applyObservation(st, {
      surface: 'vpn_architecture',
      snapshot: { keygen: 'RPT-KEY-secret' },
    });
    assert.equal(blocked.ok, false);
    const payload = explorerNedPayload(st, emptyFredState());
    assert.equal(payload.iterations.find((r) => r.id === 'NED').learned, st.parts.length);
    assert.ok(payload.recentLearned.length >= 1);
  });
});
