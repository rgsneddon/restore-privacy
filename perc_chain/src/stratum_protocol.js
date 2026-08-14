/**
 * BeamHash III miner wire helpers for the Perccent PERC pool.
 * Login / job / solution shape matches lolMiner, gminer, and miniZ.
 * Payouts are PERC — this is not a Beam coin pool.
 */

export function normalizeMinerKey(message) {
  if (!message || typeof message !== 'object') return '';
  const p = message.params && typeof message.params === 'object' ? message.params : {};
  let raw =
    p.login ||
    p.user ||
    p.username ||
    message.login ||
    message.api_key ||
    message.user ||
    '';
  if (typeof raw !== 'string') raw = String(raw || '');
  return raw.trim();
}

export function loginIdentity(message) {
  return normalizeMinerKey(message);
}

export function loginReply(message, identity) {
  const nonceprefix = identity?.nonceprefix || '';
  return {
    code: 0,
    description: 'Login Successful',
    id: message?.id ?? 1,
    jsonrpc: '2.0',
    nonceprefix,
    method: 'result',
  };
}

export function shareAck(id, accepted, description) {
  if (accepted) {
    return {
      code: 1,
      description: 'accepted',
      id,
      jsonrpc: '2.0',
      method: 'result',
      asset: 'PERC',
    };
  }
  return {
    code: -32003,
    description: description || 'rejected',
    id,
    jsonrpc: '2.0',
    method: 'result',
    asset: 'PERC',
  };
}

export function minerTlsFlags() {
  return {
    requestCert: false,
    requireCert: false,
    rejectUnauthorized: false,
  };
}

export function nextNoncePrefix(counter) {
  const n = Number(counter) || 0;
  return (n >>> 0).toString(16).padStart(8, '0');
}

/** Miner-facing job: top-level 32-byte `input` (64 hex), not a nested preWork blob. */
export function minerJob(job = {}) {
  const input = String(job.input || job.preWork || '');
  return {
    jsonrpc: '2.0',
    method: 'job',
    id: job.jobId || job.id || '1',
    height: Number(job.height) || 0,
    difficulty: Number(job.difficulty) || 0,
    input,
    coin: 'PERC',
    algorithm: 'beamhashIII',
  };
}

/** Beam miners submit method=solution with 8-byte nonce + 104-byte output. */
export function extractSolution(message) {
  if (!message || typeof message !== 'object') {
    return { nonce: '', output: '', jobId: undefined };
  }
  const p = message.params && typeof message.params === 'object' ? message.params : {};
  const nonce = message.nonce || p.nonce || '';
  const output = message.output || p.output || message.solution || p.solution || p.sol || '';
  const jobId = message.id || p.id || p.jobId || message.jobId;
  return {
    nonce: String(nonce),
    output: String(output),
    jobId: jobId != null ? String(jobId) : undefined,
  };
}

export function isLoginMethod(method) {
  return method === 'login' || method === 'mining.subscribe';
}

export function isSolutionMethod(method) {
  return method === 'solution' || method === 'submit' || method === 'mining.submit';
}
