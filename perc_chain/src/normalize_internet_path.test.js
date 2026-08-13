import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { normalizeInternetPathname } from './normalize_internet_path.js';

describe('normalizeInternetPathname', () => {
  it('maps nginx-stripped status/ledger to canonical /perc paths', () => {
    assert.equal(normalizeInternetPathname('/status'), '/perc/status');
    assert.equal(normalizeInternetPathname('/ledger'), '/perc/ledger');
  });

  it('maps nginx-stripped rendezvous paths under /perc', () => {
    assert.equal(
      normalizeInternetPathname('/rendezvous/peers'),
      '/perc/rendezvous/peers',
    );
    assert.equal(
      normalizeInternetPathname('/rendezvous/seed-recovery'),
      '/perc/rendezvous/seed-recovery',
    );
    assert.equal(
      normalizeInternetPathname('/rendezvous/register'),
      '/perc/rendezvous/register',
    );
  });

  it('keeps wallet double-prefix after strip as single /perc routes', () => {
    // Public /perc/perc/status → nginx strip → /perc/status
    assert.equal(normalizeInternetPathname('/perc/status'), '/perc/status');
    assert.equal(normalizeInternetPathname('/perc/ledger'), '/perc/ledger');
    assert.equal(
      normalizeInternetPathname('/perc/rendezvous/peers'),
      '/perc/rendezvous/peers',
    );
  });

  it('collapses accidental /perc/perc double mount', () => {
    assert.equal(
      normalizeInternetPathname('/perc/perc/status'),
      '/perc/status',
    );
    assert.equal(
      normalizeInternetPathname('/perc/perc/rendezvous/register'),
      '/perc/rendezvous/register',
    );
  });

  it('leaves health, api, explorer, public unchanged', () => {
    assert.equal(normalizeInternetPathname('/health'), '/health');
    assert.equal(normalizeInternetPathname('/api/network'), '/api/network');
    assert.equal(normalizeInternetPathname('/api/blocks'), '/api/blocks');
    assert.equal(normalizeInternetPathname('/'), '/');
    assert.equal(normalizeInternetPathname('/explorer'), '/explorer');
    assert.equal(
      normalizeInternetPathname('/public/index.html'),
      '/public/index.html',
    );
  });
});
