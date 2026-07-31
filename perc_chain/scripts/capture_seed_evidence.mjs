#!/usr/bin/env node
/**
 * Capture standalone seed evidence from a local internet_node process.
 * Usage: node scripts/capture_seed_evidence.mjs <scratchDir>
 */
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const scratch = path.resolve(process.argv[2] ?? process.env.SCRATCH ?? '.');
const percChainRoot = path.join(__dirname, '..');
const port = Number(process.env.CAPTURE_PORT ?? 9479);
const base = `http://127.0.0.1:${port}`;
const upstream =
  process.env.PERC_UPSTREAM_RENDEZVOUS_URL ??
  'https://evolve-perc-internet.onrender.com';
const dataDir = path.join(scratch, `seed_data_${Date.now()}`);

fs.mkdirSync(scratch, { recursive: true });
fs.mkdirSync(dataDir, { recursive: true });

async function fetchJson(url) {
  const res = await fetch(url, { signal: AbortSignal.timeout(12_000) });
  if (!res.ok) throw new Error(`${url} -> HTTP ${res.status}`);
  return res.json();
}

function write(name, data) {
  const file = path.join(scratch, name);
  fs.writeFileSync(file, `${JSON.stringify(data, null, 2)}\n`, 'utf8');
  console.log(`wrote ${file}`);
}

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

const child = spawn('node', ['src/internet_node.js'], {
  cwd: percChainRoot,
  env: {
    ...process.env,
    PORT: String(port),
    PERC_BIND_HOST: '127.0.0.1',
    PERC_PUBLIC_ENDPOINT: base,
    PERC_UPSTREAM_RENDEZVOUS_URL: upstream,
    PERC_DATA_DIR: dataDir,
    PERC_CHAIN_GENESIS_REVISION: '2',
    PERC_SYNC_INTERVAL_MS: '3000',
  },
  stdio: ['ignore', 'pipe', 'pipe'],
});

let log = '';
child.stdout.on('data', (d) => (log += d));
child.stderr.on('data', (d) => (log += d));

async function waitForHealth() {
  for (let i = 0; i < 40; i++) {
    try {
      const h = await fetchJson(`${base}/health`);
      if (h?.ok && h?.ledgerReady) return h;
    } catch {
      // retry
    }
    await sleep(500);
  }
  throw new Error('health never became ready');
}

let exitCode = 1;
try {
  const health1 = await waitForHealth();
  write('standalone_seed_health_1.json', health1);
  await sleep(1500);
  const health2 = await fetchJson(`${base}/health`);
  write('standalone_seed_health_2.json', health2);

  let peers = [];
  for (let i = 0; i < 20; i++) {
    try {
      peers = await fetchJson(
        `${base}/perc/rendezvous/peers?chainId=evolve-chronoflux-principia-chain-1`,
      );
      if (Array.isArray(peers) && peers.length > 0) break;
    } catch (err) {
      log += `\npeers poll ${i}: ${err.message}`;
    }
    await sleep(1000);
  }

  const status = await fetchJson(`${base}/perc/status`);
  write('standalone_seed_status.json', status);

  if (!Array.isArray(peers) || peers.length === 0) {
    write('standalone_seed_peers.json', {
      localUrl: `${base}/perc/rendezvous/peers?chainId=evolve-chronoflux-principia-chain-1`,
      peers,
      upstream,
      note: 'upstream unreachable or empty — see fallbackTests',
      logTail: log.slice(-2000),
    });
    exitCode = 2;
  } else {
    write('standalone_seed_peers.json', peers);
    exitCode = 0;
  }
} catch (err) {
  write('standalone_seed_peers.json', {
    error: String(err?.message ?? err),
    upstream,
    logTail: log.slice(-4000),
    fallback: 'run merge_network_state.test.js and seed_wallet_compat.test.js',
  });
  exitCode = 2;
} finally {
  child.kill('SIGTERM');
  await sleep(500);
  try {
    fs.rmSync(dataDir, { recursive: true, force: true });
  } catch {
    // ignore
  }
}

process.exit(exitCode);