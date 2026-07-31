#!/usr/bin/env node
/**
 * Boot two internet_node processes on distinct ports/data dirs and verify peer coexistence.
 * Usage: node scripts/multi_seed_launch.mjs [scratchDir]
 */
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const scratch = path.resolve(process.argv[2] ?? process.env.SCRATCH ?? '.');
const percChainRoot = path.join(__dirname, '..');
const CHAIN_ID = 'evolve-chronoflux-principia-chain-1';

const PORT_A = Number(process.env.SEED_A_PORT ?? 9478);
const PORT_B = Number(process.env.SEED_B_PORT ?? 9479);
const BASE_A = `http://127.0.0.1:${PORT_A}`;
const BASE_B = `http://127.0.0.1:${PORT_B}`;
const dataA = path.join(scratch, `seed_a_${Date.now()}`);
const dataB = path.join(scratch, `seed_b_${Date.now()}`);

fs.mkdirSync(scratch, { recursive: true });
fs.mkdirSync(dataA, { recursive: true });
fs.mkdirSync(dataB, { recursive: true });

const logLines = [];
function log(msg) {
  const line = `[${new Date().toISOString()}] ${msg}`;
  logLines.push(line);
  console.log(line);
}

function spawnSeed({ port, dataDir, username, publicEndpoint, upstream }) {
  const env = {
    ...process.env,
    PORT: String(port),
    PERC_BIND_HOST: '127.0.0.1',
    PERC_PUBLIC_ENDPOINT: publicEndpoint,
    PERC_DATA_DIR: dataDir,
    PERC_SEED_USERNAME: username,
    PERC_CHAIN_GENESIS_REVISION: '2',
    PERC_SYNC_INTERVAL_MS: '2000',
  };
  if (upstream) env.PERC_UPSTREAM_RENDEZVOUS_URL = upstream;
  const child = spawn('node', ['src/internet_node.js'], {
    cwd: percChainRoot,
    env,
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  child.stdout.on('data', (d) => log(`[${username}] ${d}`.trimEnd()));
  child.stderr.on('data', (d) => log(`[${username}:err] ${d}`.trimEnd()));
  return child;
}

async function fetchJson(url) {
  const res = await fetch(url, { signal: AbortSignal.timeout(12_000) });
  if (!res.ok) throw new Error(`${url} -> HTTP ${res.status}`);
  return res.json();
}

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

async function waitHealth(base, label) {
  for (let i = 0; i < 60; i++) {
    try {
      const h = await fetchJson(`${base}/health`);
      if (h?.ok && h?.ledgerReady) {
        log(`${label} health ready (height=${h.blockHeight})`);
        return h;
      }
    } catch {
      // retry
    }
    await sleep(500);
  }
  throw new Error(`${label} health never ready at ${base}/health`);
}

async function runOnce(runLabel) {
  log(`=== ${runLabel} ===`);
  const childA = spawnSeed({
    port: PORT_A,
    dataDir: dataA,
    username: 'seed_alpha',
    publicEndpoint: BASE_A,
  });
  await sleep(1500);
  const childB = spawnSeed({
    port: PORT_B,
    dataDir: dataB,
    username: 'seed_beta',
    publicEndpoint: BASE_B,
    upstream: BASE_A,
  });

  try {
    const healthA = await waitHealth(BASE_A, 'seed_alpha');
    const healthB = await waitHealth(BASE_B, 'seed_beta');
    await sleep(2500);

    const peersA = await fetchJson(
      `${BASE_A}/perc/rendezvous/peers?chainId=${encodeURIComponent(CHAIN_ID)}`,
    );
    let peersB = [];
    for (let i = 0; i < 15; i++) {
      peersB = await fetchJson(
        `${BASE_B}/perc/rendezvous/peers?chainId=${encodeURIComponent(CHAIN_ID)}`,
      );
      const endpoints = new Set(
        (Array.isArray(peersB) ? peersB : []).map((p) => p.endpoint).filter(Boolean),
      );
      if (endpoints.size >= 2) break;
      await sleep(1000);
    }

    const endpointsB = [...new Set(peersB.map((p) => p.endpoint).filter(Boolean))];
    const aliasesB = [
      ...new Set(peersB.map((p) => p.publicAlias).filter(Boolean)),
    ];
    const chainOk = peersB.every(
      (p) => (p.evolutionaryChainId ?? CHAIN_ID) === CHAIN_ID,
    );
    const aliasA = healthA.publicAlias;
    const aliasB = healthB.publicAlias;
    const hasUpstreamAlias = aliasesB.includes(aliasA);
    const hasSelfAlias = aliasesB.includes(aliasB);

    const result = {
      run: runLabel,
      healthA,
      healthB,
      peersA,
      peersB,
      peerCountB: peersB.length,
      distinctEndpointsB: endpointsB,
      distinctEndpointCountB: endpointsB.length,
      expectedAliases: { upstream: aliasA, self: aliasB },
      peerAliasesB: aliasesB,
      hasUpstreamAlias,
      hasSelfAlias,
      chainIdMatch: chainOk,
      pass:
        healthA.ledgerReady &&
        healthB.ledgerReady &&
        peersB.length >= 2 &&
        hasUpstreamAlias &&
        hasSelfAlias &&
        chainOk,
    };
    log(
      `${runLabel}: peersB=${peersB.length} aliases=${aliasesB.join(',')} upstream=${hasUpstreamAlias} self=${hasSelfAlias} pass=${result.pass}`,
    );
    return result;
  } finally {
    childA.kill('SIGTERM');
    childB.kill('SIGTERM');
    await sleep(800);
  }
}

let exitCode = 1;
try {
  const run1 = await runOnce('launch_run_1');
  await sleep(2000);
  const run2 = await runOnce('launch_run_2');

  const peersOut = {
    chainId: CHAIN_ID,
    seedA: { port: PORT_A, base: BASE_A, username: 'seed_alpha' },
    seedB: { port: PORT_B, base: BASE_B, username: 'seed_beta', upstream: BASE_A },
    run1: {
      peerCount: run1.peerCountB,
      distinctEndpoints: run1.distinctEndpointsB,
      expectedAliases: run1.expectedAliases,
      peerAliases: run1.peerAliasesB,
      hasUpstreamAlias: run1.hasUpstreamAlias,
      hasSelfAlias: run1.hasSelfAlias,
      peers: run1.peersB,
    },
    run2: {
      peerCount: run2.peerCountB,
      distinctEndpoints: run2.distinctEndpointsB,
      expectedAliases: run2.expectedAliases,
      peerAliases: run2.peerAliasesB,
      hasUpstreamAlias: run2.hasUpstreamAlias,
      hasSelfAlias: run2.hasSelfAlias,
      peers: run2.peersB,
    },
    pass: run1.pass && run2.pass,
  };

  fs.writeFileSync(
    path.join(scratch, 'multi_seed_peers.json'),
    `${JSON.stringify(peersOut, null, 2)}\n`,
    'utf8',
  );
  fs.writeFileSync(
    path.join(scratch, 'multi_seed_launch.log'),
    `${logLines.join('\n')}\n`,
    'utf8',
  );

  if (peersOut.pass) {
    log('multi_seed_launch PASS (both runs, upstream + self aliases on seed B)');
    exitCode = 0;
  } else {
    log('multi_seed_launch FAIL — see multi_seed_peers.json');
    exitCode = 1;
  }
} catch (err) {
  log(`FATAL: ${err?.message ?? err}`);
  fs.writeFileSync(
    path.join(scratch, 'multi_seed_launch.log'),
    `${logLines.join('\n')}\n`,
    'utf8',
  );
  exitCode = 1;
} finally {
  try {
    fs.rmSync(dataA, { recursive: true, force: true });
    fs.rmSync(dataB, { recursive: true, force: true });
  } catch {
    // ignore
  }
}

process.exit(exitCode);