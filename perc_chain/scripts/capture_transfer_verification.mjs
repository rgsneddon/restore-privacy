#!/usr/bin/env node
/**
 * Single capture entrypoint for transfer verification artifacts (plan steps 4–6).
 * Usage: node perc_chain/scripts/capture_transfer_verification.mjs
 * Env: PERC_SCRATCH_DIR (defaults to grok goal implementer scratch)
 */
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(__dirname, '..', '..');
const SCRATCH =
  process.env.PERC_SCRATCH_DIR ??
  path.join(os.tmpdir(), 'grok-goal-a6627874349a', 'implementer');
const GOAL_DIR = process.env.PERC_GOAL_DIR ?? null;

function runShell(command, env = {}) {
  const win = process.platform === 'win32';
  const result = spawnSync(
    win ? 'powershell.exe' : 'sh',
    win ? ['-NoProfile', '-Command', command] : ['-lc', command],
    {
      cwd: REPO_ROOT,
      env: { ...process.env, PERC_SCRATCH_DIR: SCRATCH, ...env },
      encoding: 'utf8',
      maxBuffer: 20 * 1024 * 1024,
    },
  );
  if (result.stdout) process.stdout.write(result.stdout);
  if (result.stderr) process.stderr.write(result.stderr);
  if (result.error) throw result.error;
  if (result.status !== 0) {
    throw new Error(`${command} failed with status ${result.status}`);
  }
}

function copyProbeArtifacts() {
  const localPath = path.join(SCRATCH, 'local_relay_api_probe.json');
  if (!fs.existsSync(localPath)) {
    throw new Error(`missing ${localPath} — relay_api_probe.test.js must run first`);
  }
  const payload = JSON.parse(fs.readFileSync(localPath, 'utf8'));
  fs.mkdirSync(SCRATCH, { recursive: true });
  fs.writeFileSync(
    path.join(SCRATCH, 'live_seed_transfer_probe.json'),
    `${JSON.stringify(payload.list, null, 2)}\n`,
    'utf8',
  );
  const detail = payload.relayAliasDetail ?? payload.detail;
  if (!detail?.matchedBy || detail.matchedBy !== 'relaySource') {
    throw new Error('relayAliasDetail with matchedBy=relaySource required for detail probe');
  }
  fs.writeFileSync(
    path.join(SCRATCH, 'live_seed_transfer_detail_probe.json'),
    `${JSON.stringify(detail, null, 2)}\n`,
    'utf8',
  );
}

function writeDeliverablePatch() {
  if (!GOAL_DIR) return;
  const patch = spawnSync('git', ['diff', 'e235697..HEAD'], {
    cwd: REPO_ROOT,
    encoding: 'utf8',
  });
  if (patch.status !== 0) return;
  fs.mkdirSync(GOAL_DIR, { recursive: true });
  fs.writeFileSync(path.join(GOAL_DIR, 'transfer_deliverable.patch'), patch.stdout, 'utf8');
}

fs.mkdirSync(SCRATCH, { recursive: true });

console.log(`CAPTURE: scratch=${SCRATCH}`);

runShell('flutter test test/write_send_relay_fixture_test.dart');

runShell(
  'node --test perc_chain/src/transfer_relay_view.test.js perc_chain/src/explorer_api_transfer.test.js perc_chain/src/transfer_relay_ack.test.js perc_chain/src/rendezvous_ledger_put.test.js perc_chain/src/rendezvous_ledger_transfer.test.js perc_chain/src/relay_api_probe.test.js',
);

copyProbeArtifacts();

const frameLog = path.join(SCRATCH, 'frame_flow_transfer.log');
const win = process.platform === 'win32';
const frame = spawnSync(
  win ? 'powershell.exe' : 'sh',
  win
    ? ['-NoProfile', '-Command', 'flutter test test/lawful_frame_flow_transfer_test.dart']
    : ['-lc', 'flutter test test/lawful_frame_flow_transfer_test.dart'],
  { cwd: REPO_ROOT, encoding: 'utf8', maxBuffer: 20 * 1024 * 1024 },
);
const frameOut = `${frame.stdout ?? ''}${frame.stderr ?? ''}`;
fs.writeFileSync(frameLog, frameOut, 'utf8');
process.stdout.write(frameOut);
if (frame.status !== 0) {
  throw new Error(`frame flow test failed with status ${frame.status}`);
}
if (!/GRAPHIC:/.test(frameOut)) {
  throw new Error('frame_flow_transfer.log missing GRAPHIC line');
}
if (!/lastPainted=/.test(frameOut)) {
  throw new Error('frame_flow_transfer.log missing lastPainted trace');
}

writeDeliverablePatch();

console.log('CAPTURE: complete');
console.log(`  ${path.join(SCRATCH, 'local_relay_api_probe.json')}`);
console.log(`  ${path.join(SCRATCH, 'live_seed_transfer_probe.json')}`);
console.log(`  ${path.join(SCRATCH, 'live_seed_transfer_detail_probe.json')}`);
console.log(`  ${frameLog}`);