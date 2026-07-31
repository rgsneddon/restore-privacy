import test from 'node:test';
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import net from 'node:net';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { obfuscateUsername } from './account_privacy.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const percChainRoot = path.join(__dirname, '..');
const SEED_USERNAME = 'loopback_seed_test';

function getFreePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.listen(0, '127.0.0.1', () => {
      const port = server.address().port;
      server.close(() => resolve(port));
    });
    server.on('error', reject);
  });
}

test(
  'explicit PERC_PUBLIC_ENDPOINT registers loopback seed (health peers >= 1)',
  { concurrency: false },
  async () => {
    const dataDir = fs.mkdtempSync(path.join(os.tmpdir(), 'perc-reg-loop-'));
    const port = await getFreePort();
    const base = `http://127.0.0.1:${port}`;
    const expectedAlias = obfuscateUsername(SEED_USERNAME);

    const child = spawn('node', ['src/internet_node.js'], {
      cwd: percChainRoot,
      env: {
        ...process.env,
        PORT: String(port),
        PERC_BIND_HOST: '127.0.0.1',
        PERC_PUBLIC_ENDPOINT: base,
        PERC_DATA_DIR: dataDir,
        PERC_SEED_USERNAME: SEED_USERNAME,
        PERC_CHAIN_GENESIS_REVISION: '2',
      },
      stdio: 'ignore',
    });

    try {
      await new Promise((r) => setTimeout(r, 1200));
      let health = null;
      let lastErr = null;
      for (let i = 0; i < 60; i++) {
        try {
          const healthRes = await fetch(`${base}/health`, { signal: AbortSignal.timeout(5000) });
          if (healthRes.ok) {
            health = await healthRes.json();
            if (
              health.ledgerReady &&
              health.publicAlias === expectedAlias &&
              Number(health.peers) >= 1
            ) {
              break;
            }
          }
        } catch (err) {
          lastErr = err;
        }
        await new Promise((r) => setTimeout(r, 500));
      }
      if (!health && lastErr) {
        assert.fail(`server never became reachable: ${lastErr?.message ?? lastErr}`);
      }
      assert.equal(health?.ledgerReady, true);
      assert.equal(health?.publicAlias, expectedAlias);
      assert.ok(Number(health?.peers) >= 1, 'seed should appear in local peer map');
    } finally {
      child.kill('SIGTERM');
      await new Promise((r) => setTimeout(r, 400));
      fs.rmSync(dataDir, { recursive: true, force: true });
    }
  },
);