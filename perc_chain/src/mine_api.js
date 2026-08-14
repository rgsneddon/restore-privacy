/**
 * /api/mine/* — BeamHash III jobs + PERC credit. Used by internet_node and the pool.
 */
import { applyPowToLedger, jobFromLedger } from './pow.js';

export function mineStatus(ledger) {
  const job = jobFromLedger(ledger || { blocks: [] });
  return {
    ok: true,
    coin: 'PERC',
    algorithm: 'BeamHash III',
    algorithmId: 'beamhashIII',
    height: job.height,
    blockHeight: job.height,
    inputBytes: 32,
    stratum: 'mineperc.restoreprivacy.online:1466',
  };
}

export function mineJob(ledger) {
  return jobFromLedger(ledger || { blocks: [] });
}

export function mineSubmit(ledger, body = {}) {
  return applyPowToLedger(ledger || { blocks: [] }, {
    nonce: body.nonce,
    output: body.output || body.solution,
    username: body.username || body.login,
    login: body.login,
    job: body.job,
    header: body.header,
    input: body.input || body.preWork,
    preWork: body.preWork,
  });
}
