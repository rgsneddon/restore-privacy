/**
 * Live Perc pool miner book. Login / stats / shares → public /api/stats.
 */
const miners = new Map();
const startedAt = Date.now();
let poolAccepted = 0;
let poolRejected = 0;

export function resetMinerStats() {
  miners.clear();
  poolAccepted = 0;
  poolRejected = 0;
}

export function minerKey(username) {
  const raw = String(username || 'anon').trim() || 'anon';
  return raw;
}

export function splitWorker(username) {
  const raw = minerKey(username);
  const i = raw.indexOf('.');
  if (i <= 0) return { user: raw, worker: raw };
  return { user: raw.slice(0, i), worker: raw.slice(i + 1) || raw };
}

function row(username) {
  const key = minerKey(username);
  if (!miners.has(key)) {
    const { user, worker } = splitWorker(key);
    miners.set(key, {
      id: key,
      username: key,
      user,
      worker,
      connected: false,
      connectedAt: null,
      lastSeen: null,
      lastJobId: null,
      height: null,
      threads: 0,
      hashes: 0,
      hashrate: 0,
      accepted: 0,
      rejected: 0,
      percMicro: 0,
      version: '',
      remote: '',
      port: 1466,
      algo: 'beamhashIII',
      asset: 'PERC',
    });
  }
  return miners.get(key);
}

export function recordMinerLogin({ username, remote, port } = {}) {
  const rec = row(username);
  rec.connected = true;
  rec.connectedAt = rec.connectedAt || Date.now();
  rec.lastSeen = Date.now();
  if (remote) rec.remote = String(remote);
  if (port) rec.port = Number(port);
  return rec;
}

export function recordMinerJob({ username, jobId, height } = {}) {
  const rec = row(username);
  rec.lastSeen = Date.now();
  rec.connected = true;
  if (jobId != null) rec.lastJobId = String(jobId);
  if (height != null) rec.height = Number(height);
  return rec;
}

export function recordMinerStats(body = {}) {
  const username = body.username || body.login || body.user;
  const rec = row(username);
  rec.connected = true;
  rec.lastSeen = Date.now();
  if (body.threads != null) rec.threads = Math.max(0, Number(body.threads) || 0);
  if (body.hashes != null) rec.hashes = Math.max(rec.hashes, Number(body.hashes) || 0);
  if (body.hashrate != null) rec.hashrate = Number(body.hashrate) || 0;
  if (body.version) rec.version = String(body.version);
  if (body.jobId != null) rec.lastJobId = String(body.jobId);
  if (body.height != null) rec.height = Number(body.height);
  if (body.remote) rec.remote = String(body.remote);
  return rec;
}

export function recordMinerShare({ username, accepted, percMicro } = {}) {
  const rec = row(username);
  rec.lastSeen = Date.now();
  rec.connected = true;
  if (accepted) {
    rec.accepted += 1;
    poolAccepted += 1;
    rec.percMicro += Number(percMicro) || 0;
  } else {
    rec.rejected += 1;
    poolRejected += 1;
  }
  return rec;
}

export function recordMinerDisconnect(username) {
  const rec = miners.get(minerKey(username));
  if (rec) {
    rec.connected = false;
    rec.lastSeen = Date.now();
  }
  return rec || null;
}

export function listMiners({ staleMs = 120000 } = {}) {
  const now = Date.now();
  return [...miners.values()]
    .map((m) => {
      const age = m.lastSeen ? now - m.lastSeen : Infinity;
      const connected = Boolean(m.connected && age <= staleMs);
      return {
        ...m,
        connected,
        staleSeconds: m.lastSeen ? Math.round(age / 1000) : null,
        perc: (m.percMicro || 0) / 100_000_000,
      };
    })
    .sort((a, b) => Number(b.connected) - Number(a.connected) || (b.hashrate || 0) - (a.hashrate || 0));
}

export function poolStatsSnapshot() {
  const rows = listMiners();
  const online = rows.filter((m) => m.connected);
  return {
    ok: true,
    coin: 'PERC',
    asset: 'PERC',
    product: 'Perccent PERC pool',
    host: 'mineperc.restoreprivacy.online',
    stratum: 'mineperc.restoreprivacy.online:1466',
    startedAt,
    uptimeSeconds: Math.round((Date.now() - startedAt) / 1000),
    miners: rows.length,
    minersOnline: online.length,
    threads: online.reduce((s, m) => s + (m.threads || 0), 0),
    hashes: rows.reduce((s, m) => s + (m.hashes || 0), 0),
    hashrate: online.reduce((s, m) => s + (m.hashrate || 0), 0),
    accepted: poolAccepted,
    rejected: poolRejected,
    percMicro: rows.reduce((s, m) => s + (m.percMicro || 0), 0),
    perc: rows.reduce((s, m) => s + (m.perc || 0), 0),
    workers: rows,
  };
}
