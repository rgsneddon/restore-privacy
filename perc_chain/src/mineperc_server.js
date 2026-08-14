/**
 * Perccent PERC pool front (BeamHash III). HTTP landing + /health + /api.
 * Stratum TCP is published on port 1466 (Perc mine). Not Beam 1690/1974/3333.
 */
import http from 'http';
import net from 'net';
import tls from 'tls';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { buildJob, checkShare, defaultPreWork } from './beamhash_iii.js';
import { applyCredit, creditAcceptedShare } from './perc_pool_credit.js';
import {
  extractSolution,
  isLoginMethod,
  isSolutionMethod,
  loginIdentity,
  loginReply,
  minerJob,
  minerTlsFlags,
  nextNoncePrefix,
  shareAck,
} from './stratum_protocol.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
export const DEFAULT_HTTP_PORT = 8011;
export const DEFAULT_STRATUM_PORT = 1466;
export const STRATUM_PORTS = [1466];
export const BEAM_RESERVED_PORTS = [1690, 1974];
export const DEFAULT_HOST = 'mineperc.restoreprivacy.online';

export function percStratumPorts(raw = process.env.MINEPERC_STRATUM_PORTS) {
  if (raw === '' || raw === 'none' || raw === '0') return [];
  const requested = String(raw ?? STRATUM_PORTS.join(','))
    .split(',')
    .map((p) => Number(p.trim()))
    .filter((p) => p > 0);
  const blocked = requested.filter((p) => BEAM_RESERVED_PORTS.includes(p));
  if (blocked.length) {
    throw new Error(`ports ${blocked.join(',')} reserved for Beam; Perc mine uses 1466 only`);
  }
  return requested.length ? requested : [...STRATUM_PORTS];
}

let jobSeq = 1;
let credits = {};
let height = 0;
let nonceCounter = 1;
const issuedJobs = new Map();
let lastJob = null;

export function poolFacing({
  host = DEFAULT_HOST,
  stratumPort = DEFAULT_STRATUM_PORT,
  httpPort = DEFAULT_HTTP_PORT,
} = {}) {
  return {
    product: 'Perccent PERC pool',
    coin: 'PERC',
    asset: 'PERC',
    algorithm: 'PERC',
    host,
    stratum: `stratum+tcp://${host}:${stratumPort}`,
    stratumTls: `stratum+ssl://${host}:${stratumPort}`,
    httpPort,
    username: 'PERC_USERNAME.WORKER',
    note: 'Mine Perccent (PERC). Username is your Perccent identity.',
    connect: [
      `pool ${host}:${stratumPort}`,
      `user PERC_USERNAME.WORKER`,
      `coin PERC`,
    ],
  };
}

export function seedJob(opts = {}) {
  const job = buildJob({
    preWork: opts.preWork ?? defaultPreWork(opts.height ?? height),
    height: opts.height ?? height,
    jobId: opts.jobId ?? `perc-${opts.height ?? height}-${jobSeq++}`,
  });
  issuedJobs.set(String(job.jobId), job);
  lastJob = job;
  return job;
}

export function nextJob(ledgerHeight) {
  height = Number(ledgerHeight ?? height) || 0;
  return seedJob({ height, preWork: defaultPreWork(height) });
}

export function submitShare({ username, nonce, solution, output, jobId, preWork, input }) {
  const job = (jobId && issuedJobs.get(String(jobId))) || lastJob;
  const work = input || preWork || job?.input || job?.preWork;
  const sol = output || solution;
  const checked = checkShare({
    preWork: work,
    nonce,
    solution: sol,
  });
  if (!checked.ok) {
    return { accepted: false, reason: checked.reason, asset: 'PERC' };
  }
  const credit = creditAcceptedShare({
    username,
    jobId: job?.jobId || jobId,
  });
  credits = applyCredit(credits, credit);
  return { accepted: true, credit, balances: credits, asset: 'PERC' };
}

export function handleApi(url, method, body) {
  if (url === '/health' || url === '/api/health') {
    return {
      status: 200,
      json: {
        ok: true,
        coin: 'PERC',
        algorithm: 'PERC',
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

export function attachMiner(sock, { jobFactory } = {}) {
  let buf = '';
  let username = 'anon';
  const send = (obj) => sock.write(`${JSON.stringify(obj)}\n`);
  const issueJob = () => {
    const built = jobFactory ? jobFactory() : lastJob || nextJob();
    if (built && !issuedJobs.has(String(built.jobId || built.id))) {
      issuedJobs.set(String(built.jobId || built.id), built);
      lastJob = built;
    }
    return minerJob(built);
  };
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
      const method = msg.method;
      if (isLoginMethod(method)) {
        username = loginIdentity(msg) || username;
        send(loginReply(msg, { nonceprefix: nextNoncePrefix(nonceCounter++) }));
        send(issueJob());
        continue;
      }
      if (isSolutionMethod(method)) {
        const sol = extractSolution(msg);
        const got = submitShare({
          username,
          nonce: sol.nonce,
          output: sol.output,
          solution: sol.output,
          jobId: sol.jobId,
        });
        send({
          ...shareAck(msg.id ?? sol.jobId, got.accepted, got.reason),
          credit: got.credit || undefined,
        });
        continue;
      }
      send({ id: msg.id ?? null, result: { coin: 'PERC' } });
    }
  });
}

function loadTlsOptions() {
  const keyPath = process.env.PERC_MINE_TLS_KEY || process.env.MINEPERC_TLS_KEY || '';
  const certPath = process.env.PERC_MINE_TLS_CERT || process.env.MINEPERC_TLS_CERT || '';
  if (!keyPath || !certPath || !fs.existsSync(keyPath) || !fs.existsSync(certPath)) {
    return null;
  }
  return {
    key: fs.readFileSync(keyPath),
    cert: fs.readFileSync(certPath),
    ...minerTlsFlags(),
  };
}

export function createStratumServer({
  port = DEFAULT_STRATUM_PORT,
  tls: tlsOptions,
  jobFactory,
} = {}) {
  const handler = (sock) => attachMiner(sock, { jobFactory });
  const useTls = tlsOptions === undefined ? loadTlsOptions() : tlsOptions;
  const server = useTls ? tls.createServer(useTls, handler) : net.createServer(handler);
  return {
    listen: (cb) => server.listen(port, '0.0.0.0', cb),
    close: () => new Promise((resolve) => server.close(resolve)),
    address: () => server.address(),
    server,
    tls: Boolean(useTls),
  };
}

export function startPercMinePool({
  httpPort = Number(process.env.MINEPERC_HTTP_PORT || DEFAULT_HTTP_PORT),
  stratumPorts,
} = {}) {
  const extra = stratumPorts || percStratumPorts();
  const httpSrv = createServer({ port: httpPort });
  httpSrv.listen(() => {
    console.log(`mineperc perc pool http://127.0.0.1:${httpPort}/  coin=PERC algo=BeamHash III`);
  });
  const strata = extra.map((sPort) => {
    const stratum = createStratumServer({ port: sPort });
    stratum.listen(() => {
      console.log(
        `mineperc stratum ${stratum.tls ? 'tls' : 'tcp'} 0.0.0.0:${sPort} BeamHash III PERC`,
      );
    });
    return stratum;
  });
  return { http: httpSrv, strata };
}

export { publicDir };

export function writePublicFile(res, url, dir = publicDir()) {
  const clean = String(url || '/').split('?')[0];
  const files = {
    '/': { name: 'index.html', type: 'text/html; charset=utf-8' },
    '/index.html': { name: 'index.html', type: 'text/html; charset=utf-8' },
    '/mineperc_parts.js': {
      name: 'mineperc_parts.js',
      type: 'text/javascript; charset=utf-8',
    },
  };
  const hit = files[clean];
  if (!hit) return false;
  const file = path.join(dir, hit.name);
  if (!fs.existsSync(file)) return false;
  res.writeHead(200, { 'Content-Type': hit.type, 'Cache-Control': 'no-cache' });
  res.end(fs.readFileSync(file));
  return true;
}

export function createServer({ port = DEFAULT_HTTP_PORT } = {}) {
  const server = http.createServer((req, res) => {
    const url = (req.url || '/').split('?')[0];
    if (writePublicFile(res, url)) return;
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
  startPercMinePool();
}
