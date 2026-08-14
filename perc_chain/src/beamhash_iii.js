/**
 * BeamHash III (Trei, 2020) job + share check for the Perccent PERC pool.
 * Algorithm reuse only — payout asset is PERC, not BEAM.
 */
import { blake2b256Personal } from './blake2b_personal.js';

export const ALGORITHM = 'beamhashIII';
export const COIN = 'PERC';
export const BLAKE2B_PERSONAL = 'Beam-PoW';
export const WORK_BIT_SIZE = 448;
export const COLLISION_BITS = 24;
export const NUM_ROUNDS = 5;
export const PREWORK_LEN = 32;
export const NONCE_LEN = 8;
export const SOLUTION_LEN = 104;
export const EXTRA_NONCE_LEN = 4;
export const INDEX_BYTES = 100;
export const INDEX_BITS = 25;
export const LEAF_COUNT = 32;
export const WIRE_SHARE_LEN = NONCE_LEN + SOLUTION_LEN;

const MASK64 = 0xffffffffffffffffn;
const INDEX_MASK = (1 << INDEX_BITS) - 1;

function rotl64(x, n) {
  const s = BigInt(n % 64);
  return ((x << s) | (x >> (64n - s))) & MASK64;
}

function asBytes(x, len) {
  if (x instanceof Uint8Array) {
    if (x.length !== len) {
      throw new Error(`expected ${len} bytes, got ${x.length}`);
    }
    return x;
  }
  if (typeof x === 'string') {
    const hex = x.startsWith('0x') ? x.slice(2) : x;
    if (hex.length !== len * 2) {
      throw new Error(`expected ${len} bytes hex`);
    }
    const out = new Uint8Array(len);
    for (let i = 0; i < len; i++) out[i] = parseInt(hex.slice(i * 2, i * 2 + 2), 16);
    return out;
  }
  throw new Error('expected Uint8Array or hex string');
}

/** 16-byte Blake2b personal: "Beam-PoW" || u32le(448) || u32le(5). */
export function beamPowPersonal() {
  const p = new Uint8Array(16);
  p.set(new TextEncoder().encode('Beam-PoW'));
  p[8] = WORK_BIT_SIZE & 0xff;
  p[9] = (WORK_BIT_SIZE >> 8) & 0xff;
  p[12] = NUM_ROUNDS & 0xff;
  return p;
}

function load64le(buf, off) {
  let v = 0n;
  for (let i = 7; i >= 0; i--) v = (v << 8n) | BigInt(buf[off + i]);
  return v;
}

function rotl64sip(x, b) {
  return ((x << BigInt(b)) | (x >> BigInt(64 - b))) & MASK64;
}

function sipRound(v) {
  v[0] = (v[0] + v[1]) & MASK64;
  v[2] = (v[2] + v[3]) & MASK64;
  v[1] = rotl64sip(v[1], 13);
  v[3] = rotl64sip(v[3], 16);
  v[1] ^= v[0];
  v[3] ^= v[2];
  v[0] = rotl64sip(v[0], 32);
  v[2] = (v[2] + v[1]) & MASK64;
  v[0] = (v[0] + v[3]) & MASK64;
  v[1] = rotl64sip(v[1], 17);
  v[3] = rotl64sip(v[3], 21);
  v[1] ^= v[2];
  v[3] ^= v[0];
  v[2] = rotl64sip(v[2], 32);
}

/** Beam's siphash24 on the 32-byte prePow as v0..v3 (not a keyed 16-byte SipHash). */
export function beamSiphash24(prePow4, nonceWord) {
  const v = prePow4.slice();
  const n = nonceWord & MASK64;
  v[3] ^= n;
  sipRound(v);
  sipRound(v);
  v[0] ^= n;
  v[2] ^= 0xffn;
  sipRound(v);
  sipRound(v);
  sipRound(v);
  sipRound(v);
  return (v[0] ^ v[1] ^ v[2] ^ v[3]) & MASK64;
}

/** 32-byte IndividualWork = Blake2B-256_personal(Beam-PoW||448||5)(header || nonce8 || extra4). */
export function individualWork(preWork, nonce8, extra4) {
  const pre = asBytes(preWork, PREWORK_LEN);
  const nonce = asBytes(nonce8, NONCE_LEN);
  const extra = asBytes(extra4, EXTRA_NONCE_LEN);
  const msg = new Uint8Array(PREWORK_LEN + NONCE_LEN + EXTRA_NONCE_LEN);
  msg.set(pre, 0);
  msg.set(nonce, PREWORK_LEN);
  msg.set(extra, PREWORK_LEN + NONCE_LEN);
  return blake2b256Personal(msg, beamPowPersonal());
}

export function prePowWords(work32) {
  return [
    load64le(work32, 0),
    load64le(work32, 8),
    load64le(work32, 16),
    load64le(work32, 24),
  ];
}

/**
 * 448-bit work bits for one leaf. Official impl fills from i=6..0
 * (high word is siphash((index<<3)+6)).
 */
export function seedWorkBits(work32, index) {
  const st = prePowWords(work32);
  const bits = new BigUint64Array(7);
  for (let i = 6; i >= 0; i--) {
    bits[i] = beamSiphash24(st, (BigInt(index) << 3n) + BigInt(i));
  }
  return bits;
}

function workBitsValue(work) {
  let v = 0n;
  for (let i = 6; i >= 0; i--) {
    v = (v << 64n) | (work[i] & MASK64);
  }
  return v;
}

function workFromValue(v) {
  const work = new BigUint64Array(7);
  for (let i = 0; i < 7; i++) {
    work[i] = v & MASK64;
    v >>= 64n;
  }
  return work;
}

/**
 * Official applyMix: line up remaining work bits + index-tree pads, then
 * WorkBits[0..63] = rotl64(sum_i rotl64(s_i, 29*(i+1)), 24).
 */
export function applyMix(row, remLen) {
  let temp = workBitsValue(row.work);
  const padNum = Math.min(
    Math.floor(((512 - remLen) + COLLISION_BITS) / (COLLISION_BITS + 1)),
    row.indices.length,
  );
  for (let i = 0; i < padNum; i++) {
    temp |= BigInt(row.indices[i] & INDEX_MASK) << BigInt(remLen + i * (COLLISION_BITS + 1));
  }
  let result = 0n;
  for (let i = 0; i < 8; i++) {
    const tmp = temp & MASK64;
    temp >>= 64n;
    result = (result + rotl64(tmp, (29 * (i + 1)) & 0x3f)) & MASK64;
  }
  result = rotl64(result, 24);
  let bits = workBitsValue(row.work);
  bits = (bits >> 64n) << 64n;
  bits |= result;
  row.work = workFromValue(bits);
  return row;
}

export function collisionBits(row) {
  return Number(row.work[0] & ((1n << BigInt(COLLISION_BITS)) - 1n));
}

export function combineRows(a, b, remLen) {
  if (collisionBits(a) !== collisionBits(b)) return null;
  if (a.indices[0] >= b.indices[0]) return null;
  let bits = workBitsValue(a.work) ^ workBitsValue(b.work);
  bits >>= BigInt(COLLISION_BITS);
  if (remLen < 448) {
    bits &= (1n << BigInt(remLen)) - 1n;
  }
  return {
    indices: a.indices.concat(b.indices),
    work: workFromValue(bits),
    workBits: remLen,
  };
}

/** Official GetIndicesFromMinimal: 25-bit indices, soln[0] is the low byte. */
export function unpackIndices(packed100) {
  const buf = asBytes(packed100, INDEX_BYTES);
  let stream = 0n;
  for (let i = 99; i >= 0; i--) {
    stream = (stream << 8n) | BigInt(buf[i]);
  }
  const mask = (1n << BigInt(INDEX_BITS)) - 1n;
  const indices = [];
  for (let i = 0; i < LEAF_COUNT; i++) {
    indices.push(Number(stream & mask));
    stream >>= BigInt(INDEX_BITS);
  }
  return indices;
}

export function packIndices(indices) {
  if (indices.length !== LEAF_COUNT) throw new Error('need 32 indices');
  let stream = 0n;
  for (let i = indices.length - 1; i >= 0; i--) {
    stream <<= BigInt(INDEX_BITS);
    stream |= BigInt(indices[i] & INDEX_MASK);
  }
  const buf = new Uint8Array(INDEX_BYTES);
  for (let i = 0; i < 100; i++) {
    buf[i] = Number(stream & 0xffn);
    stream >>= 8n;
  }
  return buf;
}

export function uniqueIndices(indices) {
  const seen = new Set();
  for (const i of indices) {
    if (i < 0 || i > INDEX_MASK) return false;
    if (seen.has(i)) return false;
    seen.add(i);
  }
  return seen.size === indices.length;
}

/**
 * Verify a BeamHash III solution (header 32 + nonce 8 + solution 104).
 * Matches BeamHash_III::IsValidSolution (beamhashverify).
 */
export function checkShare({ preWork, nonce, solution }) {
  try {
    const pre = asBytes(preWork, PREWORK_LEN);
    const nonce8 = asBytes(nonce, NONCE_LEN);
    const sol = asBytes(solution, SOLUTION_LEN);
    const extra = sol.subarray(100, 104);
    const packed = sol.subarray(0, 100);
    const indices = unpackIndices(packed);
    if (!uniqueIndices(indices)) {
      return { ok: false, reason: 'index_tree' };
    }
    const work32 = individualWork(pre, nonce8, extra);
    let rows = indices.map((idx) => ({
      indices: [idx],
      work: seedWorkBits(work32, idx),
    }));
    let round = 1;
    while (rows.length > 1) {
      const next = [];
      for (let i = 0; i < rows.length; i += 2) {
        let remLen = WORK_BIT_SIZE - (round - 1) * COLLISION_BITS;
        if (round === 5) remLen -= 64;
        applyMix(rows[i], remLen);
        applyMix(rows[i + 1], remLen);
        if (collisionBits(rows[i]) !== collisionBits(rows[i + 1])) {
          return { ok: false, reason: `no_collision_r${round}` };
        }
        const seen = new Set(rows[i].indices);
        for (const ix of rows[i + 1].indices) {
          if (seen.has(ix)) return { ok: false, reason: 'non_distinct' };
        }
        if (rows[i].indices[0] >= rows[i + 1].indices[0]) {
          return { ok: false, reason: 'index_order' };
        }
        remLen = WORK_BIT_SIZE - round * COLLISION_BITS;
        if (round === 4) remLen -= 64;
        if (round === 5) remLen = COLLISION_BITS;
        const combined = combineRows(rows[i], rows[i + 1], remLen);
        if (!combined) return { ok: false, reason: `combine_r${round}` };
        next.push(combined);
      }
      rows = next;
      round += 1;
    }
    const leftover = workBitsValue(rows[0].work);
    if (leftover !== 0n) return { ok: false, reason: 'nonzero_final' };
    return { ok: true, algorithm: ALGORITHM, coin: COIN, indices: rows[0].indices };
  } catch (err) {
    return { ok: false, reason: err.message || 'invalid' };
  }
}

/**
 * Issue a pool job. preWork is 32-byte Perccent header hash (synthetic until PoW lands).
 */
export function buildJob({ preWork, height = 0, jobId = '1', extraNonce = '00000000' } = {}) {
  const pre = asBytes(preWork ?? defaultPreWork(height), PREWORK_LEN);
  const input = Buffer.from(pre).toString('hex');
  return {
    algorithm: ALGORITHM,
    coin: COIN,
    asset: 'PERC',
    jobId: String(jobId),
    id: String(jobId),
    height: Number(height) || 0,
    input,
    preWork: input,
    extraNonceHint: extraNonce,
    nonceBytes: NONCE_LEN,
    solutionBytes: SOLUTION_LEN,
    wire: '8-byte nonce + 104-byte solution (800-bit index tree || 4-byte extra nonce)',
    personal: 'Beam-PoW',
  };
}

export function defaultPreWork(height = 0) {
  const seed = new TextEncoder().encode(`perccent-pow-pending:${height}`);
  return blake2b256Personal(seed, BLAKE2B_PERSONAL);
}

/**
 * Build a wire share (8+104) from parts.
 */
export function packShare(nonce8, extra4, indices) {
  const nonce = asBytes(nonce8, NONCE_LEN);
  const extra = asBytes(extra4, EXTRA_NONCE_LEN);
  const packed = packIndices(indices);
  const sol = new Uint8Array(SOLUTION_LEN);
  sol.set(packed, 0);
  sol.set(extra, 100);
  const wire = new Uint8Array(WIRE_SHARE_LEN);
  wire.set(nonce, 0);
  wire.set(sol, NONCE_LEN);
  return { nonce, solution: sol, wire };
}


