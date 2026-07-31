import http from 'http';
import { PercChain, microToDisplay } from './chain.js';

const PORT = Number(process.env.PERC_CHAIN_PORT ?? 9477);
const chain = PercChain.load();

setInterval(() => {
  const emitted = chain.tickTreasury();
  if (emitted > 0) chain.save();
}, 1000);

function json(res, code, body) {
  res.writeHead(code, { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' });
  res.end(JSON.stringify(body));
}

const server = http.createServer((req, res) => {
  if (req.method === 'OPTIONS') {
    res.writeHead(204, {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET,POST,OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type',
    });
    res.end();
    return;
  }

  const url = new URL(req.url, `http://127.0.0.1:${PORT}`);

  if (req.method === 'GET' && url.pathname === '/status') {
    return json(res, 200, chain.status());
  }

  if (req.method === 'GET' && url.pathname.startsWith('/wallet/')) {
    const address = decodeURIComponent(url.pathname.slice('/wallet/'.length));
    chain.ensureAddress(address);
    return json(res, 200, {
      address,
      balance: chain.balances[address] ?? 0,
      balanceDisplay: microToDisplay(chain.balances[address] ?? 0),
      transactions: chain.transactions.filter((t) => true).slice(0, 50),
    });
  }

  if (req.method === 'POST' && url.pathname === '/faucet/scenario') {
    let body = '';
    req.on('data', (chunk) => (body += chunk));
    req.on('end', () => {
      try {
        const data = JSON.parse(body || '{}');
        if (!data.address) return json(res, 400, { error: 'address required' });
        const reward = chain.creditScenario({
          address: data.address,
          percentChance: data.percentChance ?? 0,
          memo: data.memo ?? 'Scenario',
        });
        chain.save();
        json(res, 200, { ok: true, reward });
      } catch (e) {
        json(res, 500, { error: e.message });
      }
    });
    return;
  }

  json(res, 404, { error: 'not found' });
});

server.listen(PORT, () => {
  console.log(`Perccent chain node listening on http://127.0.0.1:${PORT}`);
});