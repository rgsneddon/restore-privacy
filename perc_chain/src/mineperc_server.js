/**
 * Perccent PERC pool front (BeamHash III). HTTP landing + /health + /api.
 * Stratum TCP is published on POOL_STRATUM_PORT (default 3334).
 */
import http from 'http';
import net from 'net';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { buildJob, checkShare, defaultPreWork } from './beamhash_iii.js';
import { applyCredit, creditAcceptedShare } from './perc_pool_credit.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
export const DEFAULT_HTTP_PORT = 8011;
export const DEFAULT_STRATUM_PORT = 3334;
export const DEFAULT_HOST = 'mineperc.restoreprivacy.online';

let jobSeq = 1;
let credits = {};
let height = 0;

export function poolFacing({
  host = DEFAULT_HOST,
  stratumPort = DEFAULT_STRATUM_PORT,
  httpPort = DEFAULT_HTTP_PORT,
} = {}) {
  return {
    product: 'Perccent PERC pool',
    coin: 'PERC',
    asset: 'PERC',
    algorithm: 'BeamHash III',
    algorithmId: 'beamhashIII',
    host,
    stratum: `stratum+tcp://${host}:${stratumPort}`,
    stratumTls: `stratum+ssl://${host}:${stratumPort}`,
    httpPort,
    username: 'PERC_USERNAME.WORKER',
    note: 'Mine Perccent (PERC) with BeamHash III. Do not use --coin BEAM.',
    connect: [
      `lolMiner --algo BEAM-III --pool ${host}:${stratumPort} --user PERC_USERNAME.WORKER`,
      `miniZ --url ${host}:${stratumPort} --user PERC_USERNAME.WORKER --algo beamhashiii`,
      `gminer --algo beamhashIII --server ${host}:${stratumPort} --user PERC_USERNAME.WORKER`,
    ],
  };
}

export function nextJob(ledgerHeight) {
  height = Number(ledgerHeight ?? height) || 0;
  return buildJob({
    preWork: defaultPreWork(height),
    height,
    jobId: `perc-${height}-${jobSeq++}`,
  });
}

export function submitShare({ username, nonce, solution, jobId }) {
  const job = buildJob({ preWork: defaultPreWork(height), height, jobId });
  const checked = checkShare({
    preWork: job.preWork,
    nonce,
    solution,
  });
  if (!checked.ok) {
    return { accepted: false, reason: checked.reason, asset: 'PERC' };
  }
  const credit = creditAcceptedShare({ username, jobId: job.jobId });
  credits = applyCredit(credits, credit);
  return { accepted: true, credit, balances: credits };
}

export function handleApi(url, method, body) {
  if (url === '/health' || url === '/api/health') {
    return {
      status: 200,
      json: {
        ok: true,
        coin: 'PERC',
        algorithm: 'BeamHash III',
        product: 'perc_pool',
        ...poolFacing(),
      },
    };
  }
  if (url === '/api/pool' || url === '/api/connect') {
    return { status: 200, json: poolFacing() };
  }
  if (url === '/api/job') {
    return { status: 200, json: nextJob() };
  }
  if (url === '/api/submit' && method === 'POST') {
    try {
      const got = submitShare(typeof body === 'string' ? JSON.parse(body || '{}') : body || {});
      return { status: got.accepted ? 200 : 400, json: got };
    } catch (err) {
      return { status: 400, json: { accepted: false, reason: err.message, asset: 'PERC' } };
    }
  }
  return null;
}

function publicDir() {
  return path.join(__dirname, '..', 'mineperc', 'public');
}

export function createStratumServer({ port = DEFAULT_STRATUM_PORT } = {}) {
  const server = net.createServer((sock) => {
    let buf = '';
    const send = (obj) => sock.write(`${JSON.stringify(obj)}\n`);
    send({ jsonrpc: '2.0', method: 'job', params: nextJob() });
    sock.on('data', (chunk) => {
      buf += chunk.toString('utf8');
      let idx;
      while ((idx = buf.indexOf('\n')) >= 0) {
        const line = buf.slice(0, idx).trim();
        buf = buf.slice(idx + 1);
        if (!line) continue;
        let msg;
        try {
          msg = JSON.parse(line);
        } catch {
          send({ id: null, error: 'bad_json', coin: 'PERC' });
          continue;
        }
        const method = msg.method || msg.jsonrpc;
        if (method === 'login' || method === 'mining.subscribe') {
          const user = msg.params?.login || msg.params?.user || msg.login || 'anon';
          send({ id: msg.id ?? 1, result: { status: 'ok', coin: 'PERC', algorithm: 'beamhashIII' } });
          send({ jsonrpc: '2.0', method: 'job', params: nextJob() });
          void user;
        } else if (method === 'submit' || method === 'mining.submit') {
          const p = msg.params || {};
          const got = submitShare({
            username: p.login || p.user || 'anon',
            nonce: p.nonce,
            solution: p.solution || p.sol,
            jobId: p.jobId || p.id,
          });
          send({ id: msg.id ?? 1, result: got.accepted, error: got.accepted ? null : got.reason, credit: got.credit });
        } else {
          send({ id: msg.id ?? null, result: { coin: 'PERC', algorithm: 'BeamHash III' } });
        }
      }
    });
  });
  return {
    listen: (cb) => server.listen(port, '0.0.0.0', cb),
    close: () => new Promise((resolve) => server.close(resolve)),
    address: () => server.address(),
    server,
  };
}

export function createServer({ port = DEFAULT_HTTP_PORT } = {}) {
  const server = http.createServer((req, res) => {
    const url = (req.url || '/').split('?')[0];
    if (url === '/' || url === '/index.html') {
      const file = path.join(publicDir(), 'index.html');
      res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-cache' });
      res.end(fs.readFileSync(file));
      return;
    }
    if (req.method === 'POST') {
      const chunks = [];
      req.on('data', (c) => chunks.push(c));
      req.on('end', () => {
        const raw = Buffer.concat(chunks).toString('utf8');
        const hit = handleApi(url, 'POST', raw);
        if (!hit) {
          res.writeHead(404);
          res.end('not found');
          return;
        }
        res.writeHead(hit.status, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify(hit.json));
      });
      return;
    }
    const hit = handleApi(url, req.method || 'GET');
    if (hit) {
      res.writeHead(hit.status, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify(hit.json));
      return;
    }
    res.writeHead(404);
    res.end('not found');
  });
  return {
    listen: (cb) => server.listen(port, '127.0.0.1', cb),
    close: () => new Promise((resolve) => server.close(resolve)),
    address: () => server.address(),
    server,
  };
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const port = Number(process.env.MINEPERC_HTTP_PORT || DEFAULT_HTTP_PORT);
  const sPort = Number(process.env.MINEPERC_STRATUM_PORT || DEFAULT_STRATUM_PORT);
  const srv = createServer({ port });
  const stratum = createStratumServer({ port: sPort });
  srv.listen(() => {
    console.log(`mineperc perc pool http://127.0.0.1:${port}/  coin=PERC algo=BeamHash III`);
  });
  stratum.listen(() => {
    console.log(`mineperc stratum 0.0.0.0:${sPort} BeamHash III PERC`);
  });
}
