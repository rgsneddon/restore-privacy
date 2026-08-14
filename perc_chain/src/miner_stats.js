/**
 * Live Perc pool miner book.
 * A connected miner is listed immediately. After disconnect, a recent
 * submitted hash (or hashrate report) keeps them listed for 72s.
 */
import { currentPoolTipHeight } from './chain_tip.js';
const miners = new Map();
const startedAt = Date.now();
let poolAccepted = 0;
let poolRejected = 0;

/** Visible after disconnect while last hash / hashrate report is this fresh. */
export const HASH_PRESENCE_MS = 72_000;

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

/** Perccent wallet / identity: the login part before `.worker`. */
export function percWalletAddress(username) {
  return splitWorker(username).user;
}

/** Public miner row: wallet + location worker; never IP / remote. */
export function publicMinerRow(m, now = Date.now()) {
  const wallet = percWalletAddress(m?.username || m?.user || m?.id);
  const worker = splitWorker(m?.username || m?.user || m?.id).worker;
  const at = Number(now) || Date.now();
  return {
    wallet,
    worker,
    connected: Boolean(m?.connected),
    threads: m?.threads || 0,
    hashes: m?.hashes || 0,
    hashrate: m?.hashrate || 0,
    accepted: m?.accepted || 0,
    rejected: m?.rejected || 0,
    percMicro: m?.percMicro || 0,
    perc: (m?.percMicro || 0) / 100_000_000,
    staleSeconds: m?.lastHashAt ? Math.round((at - m.lastHashAt) / 1000) : null,
    asset: 'PERC',
  };
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
      lastHashAt: null,
      lastJobId: null,
      height: null,
      threads: 0,
      hashes: 0,
      hashrate: 0,
      accepted: 0,
      rejected: 0,
      sessionShares: 0,
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
  const at = Number(body.now) || Date.now();
  rec.connected = true;
  rec.lastSeen = at;
  if (body.threads != null) rec.threads = Math.max(0, Number(body.threads) || 0);
  if (body.hashes != null) rec.hashes = Math.max(rec.hashes, Number(body.hashes) || 0);
  if (body.hashrate != null) rec.hashrate = Number(body.hashrate) || 0;
  if (body.version) rec.version = String(body.version);
  if (body.jobId != null) rec.lastJobId = String(body.jobId);
  if (body.height != null) rec.height = Number(body.height);
  if (body.remote) rec.remote = String(body.remote);
  if ((rec.hashes || 0) > 0 || (rec.hashrate || 0) > 0) {
    rec.lastHashAt = at;
  }
  return rec;
}

export function recordMinerShare({ username, accepted, percMicro, now } = {}) {
  const rec = row(username);
  const at = Number(now) || Date.now();
  rec.lastSeen = at;
  rec.lastHashAt = at;
  rec.connected = true;
  rec.sessionShares += 1;
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
  const key = minerKey(username);
  const rec = miners.get(key) || null;
  if (rec) rec.connected = false;
  return rec;
}

/** Public list: connected now, or last hash within HASH_PRESENCE_MS. */
export function minerIsListed(m, now = Date.now()) {
  if (m?.connected) return true;
  const at = Number(m?.lastHashAt);
  if (!Number.isFinite(at)) return false;
  return Number(now) - at <= HASH_PRESENCE_MS;
}

/** True when any worker is connected or listed (hashing window). */
export function poolHasRunningMiner(now = Date.now()) {
  const at = Number(now) || Date.now();
  for (const m of miners.values()) {
    if (m?.connected) return true;
    if (minerIsListed(m, at)) return true;
  }
  return false;
}

export function listMiners(now = Date.now()) {
  const at = Number(now) || Date.now();
  return [...miners.values()]
    .filter((m) => minerIsListed(m, at))
    .map((m) => publicMinerRow(m, at))
    .sort((a, b) => (b.hashrate || 0) - (a.hashrate || 0) || (b.accepted || 0) - (a.accepted || 0));
}

export function poolStatsSnapshot(now = Date.now()) {
  const rows = listMiners(now);
  const online = rows;
  const tip = currentPoolTipHeight();
  return {
    ok: true,
    coin: 'PERC',
    asset: 'PERC',
    product: 'Perccent PERC pool',
    host: 'mineperc.restoreprivacy.online',
    stratum: 'mineperc.restoreprivacy.online:1466',
    startedAt,
    uptimeSeconds: Math.round((Date.now() - startedAt) / 1000),
    blockHeight: tip,
    networkHeight: tip,
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

export function fmtHashrate(n) {
  const v = Number(n) || 0;
  if (v >= 1e6) return `${(v / 1e6).toFixed(2)} MH/s`;
  if (v >= 1e3) return `${(v / 1e3).toFixed(2)} kH/s`;
  return `${v.toFixed(1)} H/s`;
}

const EMPTY_MINER_ROW =
  '<tr><td colspan="6" class="off">No miners connected.</td></tr>';

export function minerTableBodyHtml(now = Date.now()) {
  const rows = listMiners(now);
  if (!rows.length) return EMPTY_MINER_ROW;
  return rows
    .map(
      (m) => `<tr>
          <td>${m.wallet || ''}</td>
          <td>${m.worker || ''}</td>
          <td>${fmtHashrate(m.hashrate)}</td>
          <td>${m.accepted || 0}</td>
          <td>${m.rejected || 0}</td>
          <td>${Number(m.perc || 0).toFixed(8)}</td>
        </tr>`,
    )
    .join('');
}

/** Fill the static landing table so the miner is visible without JS. */
export function hydrateMinepercIndex(html, now = Date.now()) {
  const snap = poolStatsSnapshot(now);
  const body = minerTableBodyHtml(now);
  return String(html || '')
    .replace(/(id="stat-online">)[^<]*/g, `$1${snap.minersOnline}`)
    .replace(/(id="stat-threads">)[^<]*/g, `$1${snap.threads}`)
    .replace(/(id="stat-height">)[^<]*/g, `$1${snap.blockHeight}`)
    .replace(/(id="stat-hashrate">)[^<]*/g, `$1${fmtHashrate(snap.hashrate)}`)
    .replace(/(id="stat-hashes">)[^<]*/g, `$1${snap.hashes}`)
    .replace(/(id="stat-accepted">)[^<]*/g, `$1${snap.accepted}`)
    .replace(/(id="stat-rejected">)[^<]*/g, `$1${snap.rejected}`)
    .replace(/(id="stat-perc">)[^<]*/g, `$1${Number(snap.perc || 0).toFixed(8)}`)
    .replace(
      /<tbody id="miner-body">[\s\S]*?<\/tbody>/,
      `<tbody id="miner-body">\n        ${body}\n      </tbody>`,
    );
}
