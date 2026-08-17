import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { describe, it } from 'node:test';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const LANDING = join(__dirname, '..', 'site', 'evolve', 'index.html');
const NGINX = join(__dirname, '..', 'deploy', 'nginx-evolve.restoreprivacy.online.conf');

describe('evolve.restoreprivacy.online is the Evolve app', () => {
  it('ships a landing page with v4.2.1 installers and no GNFP pool chrome', () => {
    assert.equal(existsSync(LANDING), true);
    const html = readFileSync(LANDING, 'utf8');
    assert.match(html, /<title>Evolve Chronoflux — the app<\/title>/);
    assert.match(html, /evolve-v4\.2\.1-windows-x64-setup\.exe/);
    assert.match(html, /evolve-v4\.2\.1-macos-x64\.zip/);
    assert.match(html, /evolve-v4\.2\.1-linux-x64\.tar\.gz/);
    assert.match(html, /evolve-v4\.2\.1-archlinux-x86_64\.pkg\.tar\.zst/);
    assert.match(html, /evolve-v4\.2\.1-android-setup\.apk/);
    assert.match(html, /evolve-v4\.2\.1-ios-setup\.ipa/);
    assert.match(html, /rgsneddon\.github\.io\/evolve/);
    assert.doesNotMatch(html, /<title>\$GNFP pool/);
    assert.doesNotMatch(html, /gnfp-mine --pool/);
    assert.doesNotMatch(html, /id="gnfp-pool-main"/);
    assert.doesNotMatch(html, /GET YOUR MINER COMMAND LINE/);
  });

  it('nginx serves the static app at / and keeps perc_chain APIs', () => {
    const conf = readFileSync(NGINX, 'utf8');
    assert.match(conf, /root \/var\/www\/evolve\.restoreprivacy\.online;/);
    assert.match(conf, /proxy_pass http:\/\/127\.0\.0\.1:9478\/api\//);
    assert.match(conf, /proxy_pass http:\/\/127\.0\.0\.1:9478\/perc\//);
    assert.match(conf, /proxy_pass http:\/\/127\.0\.0\.1:9478\/explorer/);
    assert.doesNotMatch(conf, /proxy_pass http:\/\/127\.0\.0\.1:8014/);
    assert.doesNotMatch(conf, /location \/ \{\s*proxy_pass http:\/\/127\.0\.0\.1:9478\//);
  });
});
