import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const snapshotPath = path.resolve(__dirname, '../../build/seed_ledger_snapshot.json');

function fmt(n) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(2)} MB`;
}

function rebuildUncompacted(ledger) {
  const est = structuredClone(ledger);
  for (const [name, acc] of Object.entries(est.accounts ?? {})) {
    const txs = [];
    for (const block of est.blocks ?? []) {
      for (const tx of block.transactions ?? []) {
        if (tx.fromUsername === name || tx.toUsername === name) txs.push(tx);
      }
    }
    acc.transactions = txs;
  }
  return est;
}

const raw = fs.readFileSync(snapshotPath, 'utf8');
const ledger = JSON.parse(raw);
const compactBytes = Buffer.byteLength(raw, 'utf8');
const uncompactBytes = Buffer.byteLength(JSON.stringify(rebuildUncompacted(ledger)), 'utf8');

const blocks = ledger.blocks ?? [];
const blockCount = blocks.length;
const times = blocks.map((b) => new Date(b.timestamp).getTime()).filter((t) => !Number.isNaN(t));
times.sort((a, b) => a - b);
const spanDays = times.length > 1 ? (times.at(-1) - times[0]) / 86_400_000 : 0;
const blocksPerDay = spanDays > 0 ? blockCount / spanDays : 20;
const avgBlockBytes = compactBytes / blockCount;

let totalAccountTxs = 0;
let maxAccountTxs = 0;
for (const acc of Object.values(ledger.accounts ?? {})) {
  const n = (acc.transactions ?? []).length;
  totalAccountTxs += n;
  maxAccountTxs = Math.max(maxAccountTxs, n);
}

let maxScenarioLen = 0;
let truncatedCount = 0;
for (const b of blocks) {
  for (const text of [b.scenarioLabel, ...(b.transactions ?? []).map((t) => t.scenarioLabel)]) {
    if (!text) continue;
    maxScenarioLen = Math.max(maxScenarioLen, text.length);
    if (text.endsWith('…')) truncatedCount += 1;
  }
}

const THRESHOLD = 0.8 * 1024 * 1024 * 1024;
const bytesPerDay = avgBlockBytes * blocksPerDay;

const blockSizes = blocks
  .map((b, i) => ({
    index: b.index ?? i,
    bytes: Buffer.byteLength(JSON.stringify({ ...ledger, blocks: [b] }), 'utf8'),
    ts: b.timestamp,
  }))
  .sort((a, b) => b.bytes - a.bytes);

const scenarios = [
  { name: 'Pilot (observed)', bpd: blocksPerDay },
  { name: 'Moderate (35/day)', bpd: 35 },
  { name: 'Heavy (80/day)', bpd: 80 },
];

console.log('=== LIVE SEED DISK ANALYSIS ===');
console.log(`Snapshot: ${snapshotPath}`);
console.log(`Fetched:  ${new Date().toISOString()}`);
console.log('');
console.log('--- Disk provisioned ---');
console.log('Render disk: 1 GB @ /var/data (render.yaml)');
console.log(`Safety threshold (80%): ${fmt(THRESHOLD)}`);
console.log('');
console.log('--- Ledger size (/perc/ledger) ---');
console.log(`Compact JSON:              ${compactBytes.toLocaleString()} B (${fmt(compactBytes)})`);
console.log(
  `Est. pre-compaction:       ${uncompactBytes.toLocaleString()} B (${fmt(uncompactBytes)})`,
);
console.log(`Compaction savings:        ${((1 - compactBytes / uncompactBytes) * 100).toFixed(1)}%`);
console.log(`Blocks:                    ${blockCount}`);
console.log(`Bytes/block (avg):         ${Math.round(avgBlockBytes).toLocaleString()} (${fmt(avgBlockBytes)})`);
console.log('');
console.log('--- Compaction verification ---');
console.log(`Account tx histories:      ${totalAccountTxs} total (max ${maxAccountTxs}/account)`);
console.log(`Max scenario label:        ${maxScenarioLen} chars (cap 120 + ellipsis)`);
console.log(`Truncated labels (…):      ${truncatedCount}`);
console.log('');
console.log('--- Block rate ---');
console.log(`Genesis:                   ${blocks[0]?.timestamp}`);
console.log(`Latest:                    ${blocks.at(-1)?.timestamp}`);
console.log(`Span:                      ${spanDays.toFixed(2)} days`);
console.log(`Observed rate:             ${blocksPerDay.toFixed(2)} blocks/day`);
console.log(`Growth rate:               ${fmt(bytesPerDay)}/day`);
console.log('');
console.log('--- Time to 800 MB ---');
for (const s of scenarios) {
  const days = THRESHOLD / (avgBlockBytes * s.bpd);
  console.log(`${s.name.padEnd(24)} ${Math.round(days).toLocaleString()} days (~${(days / 365).toFixed(1)} years)`);
}
console.log('');
const components = {
  blocks: Buffer.byteLength(JSON.stringify(blocks), 'utf8'),
  accounts: Buffer.byteLength(JSON.stringify(ledger.accounts ?? {}), 'utf8'),
  microblockLog: Buffer.byteLength(JSON.stringify(ledger.microblockLog ?? []), 'utf8'),
  metadata: Buffer.byteLength(
    JSON.stringify({
      ...ledger,
      blocks: undefined,
      accounts: undefined,
      microblockLog: undefined,
      pendingInboundTransfers: undefined,
      wardProposals: undefined,
      wardBallots: undefined,
    }),
    'utf8',
  ),
  pending: Buffer.byteLength(JSON.stringify(ledger.pendingInboundTransfers ?? []), 'utf8'),
};

console.log('--- Size by component ---');
for (const [k, v] of Object.entries(components)) {
  const pct = ((v / compactBytes) * 100).toFixed(1);
  console.log(`  ${k.padEnd(14)} ${fmt(v).padStart(10)}  (${pct}%)`);
}

const incrementalBlockSizes = [];
for (let i = 0; i < blocks.length; i += 1) {
  const slice = blocks.slice(0, i + 1);
  incrementalBlockSizes.push(Buffer.byteLength(JSON.stringify(slice), 'utf8'));
}
const deltas = incrementalBlockSizes.map((n, i) => (i === 0 ? n : n - incrementalBlockSizes[i - 1]));
const avgDelta = deltas.reduce((a, b) => a + b, 0) / deltas.length;

console.log('');
console.log(`Incremental bytes/block (blocks[] only): avg ${Math.round(avgDelta)} (${fmt(avgDelta)})`);
console.log('');
console.log('--- Largest blocks (full-ledger context) ---');
for (const b of blockSizes.slice(0, 5)) {
  console.log(`  #${b.index}: ${fmt(b.bytes)}  ${b.ts}`);
}