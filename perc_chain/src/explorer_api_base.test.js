/**
 * Explorer base-path resolution for /perc/ path mount.
 */
import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { explorerApiBase, explorerApiUrl } from './explorer_api_base.js';

const __dirname = dirname(fileURLToPath(import.meta.url));
const PUBLIC_HTML = join(__dirname, '..', 'public', 'index.html');

describe('explorerApiBase', () => {
  it('uses /perc prefix when mounted under /perc/', () => {
    assert.equal(explorerApiBase('/perc/'), '/perc');
    assert.equal(explorerApiBase('/perc'), '/perc');
    assert.equal(explorerApiBase('/perc/index.html'), '/perc');
  });

  it('uses root when at site root', () => {
    assert.equal(explorerApiBase('/'), '');
    assert.equal(explorerApiBase('/index.html'), '');
  });

  it('builds network and blocks URLs under /perc/', () => {
    assert.equal(explorerApiUrl('api/network', '/perc/'), '/perc/api/network');
    assert.equal(explorerApiUrl('/api/blocks?limit=40', '/perc/'), '/perc/api/blocks?limit=40');
    assert.equal(explorerApiUrl('api/blocks/3', '/perc/'), '/perc/api/blocks/3');
    assert.equal(explorerApiUrl('health', '/perc/'), '/perc/health');
  });

  it('builds root URLs when not path-mounted', () => {
    assert.equal(explorerApiUrl('api/network', '/'), '/api/network');
    assert.equal(explorerApiUrl('api/blocks', '/'), '/api/blocks');
    assert.equal(explorerApiUrl('health', '/'), '/health');
  });

  it('shipped public/index.html uses explorerApiUrl for fetches (not bare /api/network alone)', () => {
    const html = readFileSync(PUBLIC_HTML, 'utf8');
    assert.match(html, /function explorerApiBase\s*\(/);
    assert.match(html, /function explorerApiUrl\s*\(/);
    assert.match(html, /fetch\s*\(\s*explorerApiUrl\s*\(\s*['"]api\/network['"]/);
    assert.match(html, /fetch\s*\(\s*explorerApiUrl\s*\(\s*['"]api\/blocks/);
    assert.match(html, /fetch\s*\(\s*explorerApiUrl\s*\(\s*`api\/blocks\/\$\{/);
    // Must not be the only production fetch target as bare absolute /api/network
    assert.doesNotMatch(html, /fetch\s*\(\s*['"]\/api\/network['"]\s*\)/);
    assert.doesNotMatch(html, /fetch\s*\(\s*['"]\/api\/blocks/);
    // Footer links wired dynamically (no hard-coded site-root-only hrefs as sole source)
    assert.match(html, /id="link-api-network"/);
    assert.match(html, /wireFooterApiLinks/);
  });
});
