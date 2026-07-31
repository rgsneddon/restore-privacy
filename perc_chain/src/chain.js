import crypto from 'crypto';
import fs from 'fs';
import path from 'path';

const UNITS_PER_PERC = 100_000_000;
const MAX_SUPPLY = 283_000_000 * UNITS_PER_PERC;
/** 0.00000001 PERC per minute — matches PercChainConstants.treasuryEmissionPerMinute */
const EMISSION_MICRO_PER_MINUTE = 1;
const SCENARIO_BASE = 50; // 50 cent (0.00000050 PERC)

const DATA_FILE = path.join(process.cwd(), 'data', 'chain.json');

export function microToDisplay(micro) {
  const whole = Math.floor(micro / UNITS_PER_PERC);
  const frac = String(micro % UNITS_PER_PERC).padStart(8, '0').replace(/0+$/, '');
  return frac.length ? `${whole}.${frac}` : `${whole}`;
}

function hashBlock(payload) {
  return crypto.createHash('sha256').update(JSON.stringify(payload)).digest('hex');
}

export class PercChain {
  constructor(state) {
    this.chainId = 'perc-main-evolve-1';
    this.treasuryMinted = state?.treasuryMinted ?? 0;
    this.lastTick = state?.lastTick ?? Date.now();
    this.blocks = state?.blocks ?? [];
    this.balances = state?.balances ?? {};
    this.transactions = state?.transactions ?? [];
    if (this.blocks.length === 0) this.ensureGenesis();
  }

  ensureGenesis() {
    const genesis = {
      height: 0,
      timestamp: new Date().toISOString(),
      previousHash: '0'.repeat(64),
      treasuryEmission: 0,
      treasuryTotalAfter: 0,
      faucetPayouts: [],
    };
    genesis.hash = hashBlock(genesis);
    this.blocks.push(genesis);
  }

  tickTreasury(now = Date.now()) {
    if (this.treasuryMinted >= MAX_SUPPLY) return 0;
    const elapsed = Math.floor((now - this.lastTick) / 1000);
    if (elapsed <= 0) return 0;
    let emission = Math.floor((elapsed * EMISSION_MICRO_PER_MINUTE) / 60);
    const remaining = MAX_SUPPLY - this.treasuryMinted;
    if (emission > remaining) emission = remaining;
    this.treasuryMinted += emission;
    this.lastTick += elapsed * 1000;
    const block = {
      height: this.blocks.length,
      timestamp: new Date(now).toISOString(),
      previousHash: this.blocks[this.blocks.length - 1].hash,
      treasuryEmission: emission,
      treasuryTotalAfter: this.treasuryMinted,
      faucetPayouts: [],
    };
    block.hash = hashBlock(block);
    this.blocks.push(block);
    return emission;
  }

  ensureAddress(address) {
    if (!this.balances[address]) this.balances[address] = 0;
  }

  creditScenario({ address, percentChance = 0, memo = 'Scenario' }) {
    this.tickTreasury();
    this.ensureAddress(address);
    const pct = Math.max(0, Math.min(100, Math.round(percentChance)));
    const bonus = pct;
    const total = SCENARIO_BASE + bonus;
    if (this.treasuryMinted < total) throw new Error('Treasury cap reached');
    this.treasuryMinted -= total;
    this.balances[address] += total;
    const tx = {
      id: crypto.randomBytes(8).toString('hex'),
      timestamp: new Date().toISOString(),
      kind: 'scenarioFaucet',
      amount: total,
      balanceAfter: this.balances[address],
      memo,
      percentChance: pct,
    };
    this.transactions.unshift(tx);
    const block = {
      height: this.blocks.length,
      timestamp: new Date().toISOString(),
      previousHash: this.blocks[this.blocks.length - 1].hash,
      treasuryEmission: 0,
      treasuryTotalAfter: this.treasuryMinted,
      faucetPayouts: [{ address, base: SCENARIO_BASE, bonus, percent: pct }],
    };
    block.hash = hashBlock(block);
    this.blocks.push(block);
    return { base: SCENARIO_BASE, bonus, total, display: microToDisplay(total) };
  }

  status() {
    return {
      chainId: this.chainId,
      blockHeight: this.blocks.length - 1,
      treasuryMinted: this.treasuryMinted,
      treasuryMintedDisplay: microToDisplay(this.treasuryMinted),
      maxSupply: MAX_SUPPLY,
      maxSupplyDisplay: microToDisplay(MAX_SUPPLY),
      emissionPerMinute: '0.00000001',
      emissionMicroPerMinute: EMISSION_MICRO_PER_MINUTE,
    };
  }

  save() {
    fs.mkdirSync(path.dirname(DATA_FILE), { recursive: true });
    fs.writeFileSync(
      DATA_FILE,
      JSON.stringify(
        {
          treasuryMinted: this.treasuryMinted,
          lastTick: this.lastTick,
          blocks: this.blocks,
          balances: this.balances,
          transactions: this.transactions,
        },
        null,
        2,
      ),
    );
  }

  static load() {
    if (!fs.existsSync(DATA_FILE)) return new PercChain();
    const raw = JSON.parse(fs.readFileSync(DATA_FILE, 'utf8'));
    return new PercChain(raw);
  }
}