/** Blake2b-256 with 16-byte personalization. Port of RFC 7693 / dcposch blakejs. */

function add64AA(v, a, b) {
  const o0 = v[a] + v[b];
  let o1 = v[a + 1] + v[b + 1];
  if (o0 >= 0x100000000) o1++;
  v[a] = o0;
  v[a + 1] = o1;
}

function add64AC(v, a, b0, b1) {
  let o0 = v[a] + b0;
  if (b0 < 0) o0 += 0x100000000;
  let o1 = v[a + 1] + b1;
  if (o0 >= 0x100000000) o1++;
  v[a] = o0;
  v[a + 1] = o1;
}

function get32(arr, i) {
  return arr[i] ^ (arr[i + 1] << 8) ^ (arr[i + 2] << 16) ^ (arr[i + 3] << 24);
}

const IV32 = new Uint32Array([
  0xf3bcc908, 0x6a09e667, 0x84caa73b, 0xbb67ae85, 0xfe94f82b, 0x3c6ef372,
  0x5f1d36f1, 0xa54ff53a, 0xade682d1, 0x510e527f, 0x2b3e6c1f, 0x9b05688c,
  0xfb41bd6b, 0x1f83d9ab, 0x137e2179, 0x5be0cd19,
]);

const SIGMA82 = Uint8Array.from(
  [
    0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 14, 10, 4, 8, 9, 15, 13, 6,
    1, 12, 0, 2, 11, 7, 5, 3, 11, 8, 12, 0, 5, 2, 15, 13, 10, 14, 3, 6, 7, 1, 9, 4, 7,
    9, 3, 1, 13, 12, 11, 14, 2, 6, 5, 10, 4, 0, 15, 8, 9, 0, 5, 7, 2, 4, 10, 15, 14, 1,
    11, 12, 6, 8, 3, 13, 2, 12, 6, 10, 0, 11, 8, 3, 4, 13, 7, 5, 15, 14, 1, 9, 12, 5, 1,
    15, 14, 13, 4, 10, 0, 7, 6, 3, 9, 2, 8, 11, 13, 11, 7, 14, 12, 1, 3, 9, 5, 0, 15, 4,
    8, 6, 2, 10, 6, 15, 14, 9, 11, 3, 0, 8, 12, 2, 13, 7, 1, 4, 10, 5, 10, 2, 8, 4, 7, 6,
    1, 5, 15, 11, 9, 14, 3, 12, 13, 0, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14,
    15, 14, 10, 4, 8, 9, 15, 13, 6, 1, 12, 0, 2, 11, 7, 5, 3,
  ].map((x) => x * 2),
);

function g(v, m, a, b, c, d, ix, iy) {
  const x0 = m[ix];
  const x1 = m[ix + 1];
  const y0 = m[iy];
  const y1 = m[iy + 1];
  add64AA(v, a, b);
  add64AC(v, a, x0, x1);
  let xor0 = v[d] ^ v[a];
  let xor1 = v[d + 1] ^ v[a + 1];
  v[d] = xor1;
  v[d + 1] = xor0;
  add64AA(v, c, d);
  xor0 = v[b] ^ v[c];
  xor1 = v[b + 1] ^ v[c + 1];
  v[b] = (xor0 >>> 24) ^ (xor1 << 8);
  v[b + 1] = (xor1 >>> 24) ^ (xor0 << 8);
  add64AA(v, a, b);
  add64AC(v, a, y0, y1);
  xor0 = v[d] ^ v[a];
  xor1 = v[d + 1] ^ v[a + 1];
  v[d] = (xor0 >>> 16) ^ (xor1 << 16);
  v[d + 1] = (xor1 >>> 16) ^ (xor0 << 16);
  add64AA(v, c, d);
  xor0 = v[b] ^ v[c];
  xor1 = v[b + 1] ^ v[c + 1];
  v[b] = (xor1 >>> 31) ^ (xor0 << 1);
  v[b + 1] = (xor0 >>> 31) ^ (xor1 << 1);
}

function compress(ctx, last) {
  const v = new Uint32Array(32);
  const m = new Uint32Array(32);
  for (let i = 0; i < 16; i++) {
    v[i] = ctx.h[i];
    v[i + 16] = IV32[i];
  }
  v[24] ^= ctx.t;
  v[25] ^= Math.floor(ctx.t / 0x100000000);
  if (last) {
    v[28] = ~v[28];
    v[29] = ~v[29];
  }
  for (let i = 0; i < 32; i++) m[i] = get32(ctx.b, 4 * i);
  for (let i = 0; i < 12; i++) {
    g(v, m, 0, 8, 16, 24, SIGMA82[i * 16 + 0], SIGMA82[i * 16 + 1]);
    g(v, m, 2, 10, 18, 26, SIGMA82[i * 16 + 2], SIGMA82[i * 16 + 3]);
    g(v, m, 4, 12, 20, 28, SIGMA82[i * 16 + 4], SIGMA82[i * 16 + 5]);
    g(v, m, 6, 14, 22, 30, SIGMA82[i * 16 + 6], SIGMA82[i * 16 + 7]);
    g(v, m, 0, 10, 20, 30, SIGMA82[i * 16 + 8], SIGMA82[i * 16 + 9]);
    g(v, m, 2, 12, 22, 24, SIGMA82[i * 16 + 10], SIGMA82[i * 16 + 11]);
    g(v, m, 4, 14, 16, 26, SIGMA82[i * 16 + 12], SIGMA82[i * 16 + 13]);
    g(v, m, 6, 8, 18, 28, SIGMA82[i * 16 + 14], SIGMA82[i * 16 + 15]);
  }
  for (let i = 0; i < 16; i++) ctx.h[i] ^= v[i] ^ v[i + 16];
}

/**
 * @param {Uint8Array} message
 * @param {string|Uint8Array} personal
 * @returns {Uint8Array} 32-byte digest
 */
export function blake2b256Personal(message, personal) {
  const pers = new Uint8Array(16);
  if (typeof personal === 'string') {
    pers.set(new TextEncoder().encode(personal).subarray(0, 16));
  } else if (personal) {
    pers.set(Uint8Array.from(personal).subarray(0, 16));
  }
  const param = new Uint8Array(64);
  param[0] = 32;
  param[2] = 1;
  param[3] = 1;
  param.set(pers, 48);
  const ctx = {
    b: new Uint8Array(128),
    h: new Uint32Array(16),
    t: 0,
    c: 0,
    outlen: 32,
  };
  for (let i = 0; i < 16; i++) ctx.h[i] = IV32[i] ^ get32(param, i * 4);
  const input = message instanceof Uint8Array ? message : Uint8Array.from(message);
  for (let i = 0; i < input.length; i++) {
    if (ctx.c === 128) {
      ctx.t += ctx.c;
      compress(ctx, false);
      ctx.c = 0;
    }
    ctx.b[ctx.c++] = input[i];
  }
  ctx.t += ctx.c;
  while (ctx.c < 128) ctx.b[ctx.c++] = 0;
  compress(ctx, true);
  const out = new Uint8Array(32);
  for (let i = 0; i < 32; i++) out[i] = ctx.h[i >> 2] >> (8 * (i & 3));
  return out;
}
