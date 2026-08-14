/** SipHash-2-4. Port of jedisct1/siphash-js (public algorithm). */

function add(a, b) {
  const rl = a.l + b.l;
  const h = a.h + b.h + ((rl / 2) >>> 31) >>> 0;
  a.h = h;
  a.l = rl >>> 0;
}

function xor(a, b) {
  a.h = (a.h ^ b.h) >>> 0;
  a.l = (a.l ^ b.l) >>> 0;
}

function rotl(a, n) {
  const h = (a.h << n) | (a.l >>> (32 - n));
  const l = (a.l << n) | (a.h >>> (32 - n));
  a.h = h;
  a.l = l;
}

function rotl32(a) {
  const al = a.l;
  a.l = a.h;
  a.h = al;
}

function compress(v0, v1, v2, v3) {
  add(v0, v1);
  add(v2, v3);
  rotl(v1, 13);
  rotl(v3, 16);
  xor(v1, v0);
  xor(v3, v2);
  rotl32(v0);
  add(v2, v1);
  add(v0, v3);
  rotl(v1, 17);
  rotl(v3, 21);
  xor(v1, v2);
  xor(v3, v0);
  rotl32(v2);
}

function getInt(a, offset) {
  return (
    a[offset + 3] * 0x1000000 +
    (a[offset + 2] << 16) +
    (a[offset + 1] << 8) +
    a[offset]
  );
}

function keyFrom16(key16) {
  return [
    { h: getInt(key16, 4) >>> 0, l: getInt(key16, 0) >>> 0 },
    { h: getInt(key16, 12) >>> 0, l: getInt(key16, 8) >>> 0 },
  ];
}

export function siphash24(key16, msg) {
  const [k0, k1] = keyFrom16(key16);
  const v0 = { h: k0.h, l: k0.l };
  const v1 = { h: k1.h, l: k1.l };
  const v2 = { h: k0.h, l: k0.l };
  const v3 = { h: k1.h, l: k1.l };
  xor(v0, { h: 0x736f6d65, l: 0x70736575 });
  xor(v1, { h: 0x646f7261, l: 0x6e646f6d });
  xor(v2, { h: 0x6c796765, l: 0x6e657261 });
  xor(v3, { h: 0x74656462, l: 0x79746573 });
  const ml = msg.length;
  let mp = 0;
  while (mp + 8 <= ml) {
    const mi = { h: getInt(msg, mp + 4) >>> 0, l: getInt(msg, mp) >>> 0 };
    xor(v3, mi);
    compress(v0, v1, v2, v3);
    compress(v0, v1, v2, v3);
    xor(v0, mi);
    mp += 8;
  }
  const buf = new Uint8Array(8);
  buf[7] = ml;
  let ic = 0;
  while (mp < ml) buf[ic++] = msg[mp++];
  const mil = {
    h: (buf[7] << 24) | (buf[6] << 16) | (buf[5] << 8) | buf[4],
    l: (buf[3] << 24) | (buf[2] << 16) | (buf[1] << 8) | buf[0],
  };
  mil.h >>>= 0;
  mil.l >>>= 0;
  xor(v3, mil);
  compress(v0, v1, v2, v3);
  compress(v0, v1, v2, v3);
  xor(v0, mil);
  xor(v2, { h: 0, l: 0xff });
  compress(v0, v1, v2, v3);
  compress(v0, v1, v2, v3);
  compress(v0, v1, v2, v3);
  compress(v0, v1, v2, v3);
  xor(v0, v1);
  xor(v0, v2);
  xor(v0, v3);
  return (BigInt(v0.h >>> 0) << 32n) | BigInt(v0.l >>> 0);
}

export function siphash24Word(key16, word) {
  const buf = new Uint8Array(8);
  let w = BigInt(word) & 0xffffffffffffffffn;
  for (let i = 0; i < 8; i++) {
    buf[i] = Number(w & 0xffn);
    w >>= 8n;
  }
  return siphash24(key16, buf);
}

export function siphash24Hex(key16, msg) {
  return siphash24(key16, msg).toString(16).padStart(16, '0');
}
