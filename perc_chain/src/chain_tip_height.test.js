import { describe, it, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  bindPoolToLedger,
  currentPoolTipHeight,
  fetchPercChainTipHeight,
  percChainTipFromHealth,
  percChainTipHeight,
  resetPoolTip,
  setPoolTipHeight,
} from './chain_tip.js';
import { jobFromLedger } from './pow.js';
import { nextJob, handleApi } from './mineperc_server.js';
import { hydrateMinepercIndex, poolStatsSnapshot, resetMinerStats } from './miner_stats.js';
import {
  buildNetworkSnapshot,
  hydrateExplorerIndex,
  networkCalculationsFromLedger,
} from './explorer_api.js';
import { buildDynamicEmissionStats } from './dynamic_emission.js';

const __dirname = dirname(fileURLToPath(import.meta.url));
const EXPLORER_HTML = join(__dirname, '..', 'public', 'index.html');
const MINEPERC_HTML = join(__dirname, '..', 'mineperc', 'public', 'index.html');

function fixtureLedger(blockCount) {
  const t0 = Date.parse('2026-03-01T00:00:00.000Z');
  const blocks = [];
  for (let i = 0; i < blockCount; i += 1) {
    blocks.push({
      index: i,
      timestamp: new Date(t0 + i * 90_000).toISOString(),
      transactions: i === 0 ? [] : [{ kind: 'scenarioReward', amount: { microUnits: 1 } }],
    });
  }
  return {
    blockchainLaunched: true,
    treasuryGenesisDone: true,
    treasuryCycle: 1,
    cumulativeTreasuryMinted: { microUnits: 50_000_000 },
    accounts: {
      evolve_treasury: { balance: { microUnits: 88_624_114_766_24 } },
      alice: { username: 'alice', balance: { microUnits: 1 } },
      bob: { username: 'bob', balance: { microUnits: 1 } },
      carol: { username: 'carol', balance: { microUnits: 1 } },
    },
    networkNodes: {
      alice: { username: 'alice', online: true },
      bob: { username: 'bob', online: true },
    },
    blocks,
  };
}

describe('perc_chain tip height binds pool, mineperc, and explorer', () => {
  beforeEach(() => {
    resetPoolTip();
    resetMinerStats();
  });

  it('shipped job/stats/page/explorer functions share ledger tip + calculations', () => {
    const ledger = fixtureLedger(7);
    const H = percChainTipHeight(ledger);
    assert.equal(H, ledger.blocks.length);
    assert.notEqual(H, 0);

    bindPoolToLedger(ledger);
    assert.equal(currentPoolTipHeight(), H);

    const job = jobFromLedger(ledger);
    assert.equal(job.height, H);
    const issued = nextJob();
    assert.equal(issued.height, H);

    const stats = poolStatsSnapshot();
    assert.equal(stats.blockHeight, H);
    assert.equal(stats.networkHeight, H);
    const api = handleApi('/api/stats', 'GET');
    assert.equal(api.status, 200);
    assert.equal(api.json.blockHeight, H);
    const jobApi = handleApi('/api/job', 'GET');
    assert.equal(jobApi.json.height, H);

    const landing = hydrateMinepercIndex(readFileSync(MINEPERC_HTML, 'utf8'));
    assert.match(landing, new RegExp(`id="stat-height">${H}`));
    assert.match(landing, /Block height/);

    const store = {
      ledger,
      revision: 3,
      getGenesisRevision: () => 2,
      hasLedger: () => true,
    };
    const net = buildNetworkSnapshot({
      peers: new Map(),
      ledgers: new Map(),
      store,
      seedUsername: 'evolve_seed_node',
      endpoint: 'https://135.181.152.10.sslip.io/perc',
      chainId: 'evolve-chronoflux-principia-chain-1',
    });
    assert.equal(net.blockHeight, H);
    assert.equal(net.networkHeight, H);
    const calc = networkCalculationsFromLedger(ledger);
    const shippedCalc = buildDynamicEmissionStats(ledger);
    assert.equal(calc.emissionPerMinute, shippedCalc.emissionPerMinute);
    assert.equal(calc.loadFactorPercent, shippedCalc.loadFactorPercent);
    assert.equal(calc.blockTimeFactorPercent, shippedCalc.blockTimeFactorPercent);
    assert.equal(calc.walletLoadCount, shippedCalc.walletLoadCount);
    assert.equal(calc.averageBlockSeconds, shippedCalc.averageBlockSeconds);
    assert.equal(net.networkCalculations.emissionPerMinute, calc.emissionPerMinute);
    assert.equal(net.networkCalculations.loadFactorPercent, calc.loadFactorPercent);
    assert.equal(net.networkCalculations.blockTimeFactorPercent, calc.blockTimeFactorPercent);
    assert.equal(net.networkCalculations.walletLoadCount, calc.walletLoadCount);
    assert.equal(net.networkCalculations.averageBlockSeconds, calc.averageBlockSeconds);
    assert.equal(net.treasuryEmission.emissionPerMinute, calc.emissionPerMinute);
    assert.equal(net.treasuryEmission.loadFactorPercent, calc.loadFactorPercent);
    assert.ok(Number(calc.walletLoadCount) > 0);
    assert.ok(Number(calc.averageBlockSeconds) > 0);

    const explorerPage = hydrateExplorerIndex(readFileSync(EXPLORER_HTML, 'utf8'), net);
    assert.match(explorerPage, new RegExp(`id="stat-seed-height">${H}`));
    assert.match(explorerPage, new RegExp(`id="stat-network-height">${H}`));
    assert.match(explorerPage, new RegExp(`id="calc-emission-rate">${calc.emissionPerMinute} PERC/min`));
    assert.match(explorerPage, new RegExp(`id="calc-load-factor">${calc.loadFactorPercent}%`));
    assert.match(explorerPage, new RegExp(`id="calc-block-time">${calc.blockTimeFactorPercent}%`));
    assert.match(explorerPage, new RegExp(`id="calc-wallet-load">${calc.walletLoadCount}`));
    assert.match(explorerPage, new RegExp(`id="calc-avg-block-seconds">${calc.averageBlockSeconds}`));
    assert.match(explorerPage, /Network calculations/);
  });

  it('health payload and remote poll set the same pool tip', async () => {
    const ledger = fixtureLedger(11);
    const H = percChainTipHeight(ledger);
    const health = { ok: true, blockHeight: H, networkHeight: H };
    assert.equal(percChainTipFromHealth(health), H);
    const got = await fetchPercChainTipHeight({
      url: 'https://135.181.152.10.sslip.io/perc/health',
      fetchImpl: async () => ({ json: async () => health }),
    });
    assert.equal(got, H);
    assert.equal(currentPoolTipHeight(), H);
    assert.equal(nextJob().height, H);
    setPoolTipHeight(H);
    assert.equal(poolStatsSnapshot().blockHeight, H);
  });
});
