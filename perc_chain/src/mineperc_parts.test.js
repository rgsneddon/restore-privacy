import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  copyPayloadForPart,
  longestPartLength,
  minWidthChFromParts,
} from '../mineperc/public/mineperc_parts.js';

const __dirname = dirname(fileURLToPath(import.meta.url));
const PAGE = join(__dirname, '..', 'mineperc', 'public', 'index.html');

test('longest-string helper grows min-width with the longest sample', () => {
  const short = ['1466', 'PERC'];
  const longer = [...short, 'mineperc.restoreprivacy.online:1466'];
  const longest = [
    ...longer,
    'perc-mine --pool mineperc.restoreprivacy.online:1466 --user PERC_USERNAME.WORKER',
  ];
  assert.equal(longestPartLength(short), 4);
  const wShort = minWidthChFromParts(short, 1);
  const wMid = minWidthChFromParts(longer, 1);
  const wLong = minWidthChFromParts(longest, 1);
  assert.ok(wMid > wShort);
  assert.ok(wLong > wMid);
  assert.equal(wLong, longest[longest.length - 1].length + 1);
});

test('copy helper returns that part only', () => {
  const cmd = 'perc-mine --pool mineperc.restoreprivacy.online:1466 --user PERC_USERNAME.WORKER';
  assert.equal(copyPayloadForPart(cmd), cmd);
  assert.equal(copyPayloadForPart('PERC_USERNAME.WORKER'), 'PERC_USERNAME.WORKER');
  assert.notEqual(copyPayloadForPart('1466'), cmd);
});

test('shipped page has facts, no clip, copy controls per part', () => {
  const html = readFileSync(PAGE, 'utf8');
  assert.match(html, /mineperc\.restoreprivacy\.online/);
  assert.match(html, /1466/);
  assert.match(html, /PERC_USERNAME\.WORKER/);
  assert.match(html, /perc-mine --pool mineperc\.restoreprivacy\.online:1466/);
  assert.doesNotMatch(html, /beam/i);
  assert.match(html, /data-copy-part="stratum"/);
  assert.match(html, /data-copy-part="worker"/);
  assert.match(html, /data-copy-part="high"/);
  assert.match(html, /data-copy-part="perc-mine"/);
  assert.equal((html.match(/class="copy-icon"/g) || []).length, 4);
  const valueCss = html.slice(html.indexOf('.info-value'), html.indexOf('.copy-icon'));
  assert.doesNotMatch(valueCss, /text-overflow:\s*ellipsis/);
  assert.doesNotMatch(valueCss, /overflow:\s*hidden/);
  assert.match(html, /--mineperc-longest-ch/);
  assert.match(html, /min-width:\s*calc\(var\(--mineperc-longest-ch\)/);
});
