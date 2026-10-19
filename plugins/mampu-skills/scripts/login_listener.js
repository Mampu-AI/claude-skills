#!/usr/bin/env node
// Local half of "Sign in with Lark": listens once on 127.0.0.1 for the server's callback redirect
// (/?token=swl_…&name=…), stores the token for this computer, and exits. Node is always present
// where Claude Code runs, which python3 is not (Windows).
//
//   node login_listener.js <keychain-service> <fallback-file>
//
// First stdout line: the port. Then "Signed in as <name>." Exit 0 on success, 1 on timeout (5 min).
// Storage order: macOS Keychain, Linux secret-tool, else the fallback file (0600, user profile).
'use strict';
const http = require('http');
const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

const service = process.argv[2] || 'sapot-work-login';
const fallbackFile = process.argv[3] || path.join(process.env.HOME || process.env.USERPROFILE || '.', '.config', 'sapot', 'work-login');
const TIMEOUT_MS = 5 * 60 * 1000;
const PAGE = "<!doctype html><meta charset=utf-8><body style='font-family:system-ui;margin:4rem'>" +
  '<h1>Done</h1><p>You are signed in. Return to the terminal; this tab can be closed.</p></body>';

function has(cmd) {
  const probe = process.platform === 'win32' ? ['where', [cmd]] : ['sh', ['-c', `command -v ${cmd}`]];
  return spawnSync(probe[0], probe[1], { stdio: 'ignore' }).status === 0;
}

function store(token) {
  if (process.platform === 'darwin' && has('security')) {
    const r = spawnSync('security', ['add-generic-password', '-U', '-a', 'sapot', '-s', service, '-w', token], { stdio: 'ignore' });
    if (r.status === 0) return 'keychain';
  }
  if (process.platform === 'linux' && has('secret-tool')) {
    const r = spawnSync('secret-tool', ['store', '--label=Sapot work login', 'service', service], { input: token, stdio: ['pipe', 'ignore', 'ignore'] });
    if (r.status === 0) return 'keyring';
  }
  fs.mkdirSync(path.dirname(fallbackFile), { recursive: true, mode: 0o700 });
  fs.writeFileSync(fallbackFile, token + '\n', { mode: 0o600 });
  try { fs.chmodSync(fallbackFile, 0o600); } catch (_) { /* Windows ignores modes */ }
  return 'file';
}

const server = http.createServer((req, res) => {
  const url = new URL(req.url, 'http://127.0.0.1');
  const token = url.searchParams.get('token') || '';
  if (!token.startsWith('swl_')) { res.statusCode = 404; res.end(); return; }
  res.setHeader('Content-Type', 'text/html; charset=utf-8');
  res.end(PAGE);
  const where = store(token);
  const who = url.searchParams.get('name') || 'you';
  const place = where === 'file' ? 'a private file in your user profile' : `this computer's ${where}`;
  console.log(`Signed in as ${who}. The login is saved in ${place}.`);
  server.close();
  process.exit(0);
});

server.listen(0, '127.0.0.1', () => {
  console.log(server.address().port);
  setTimeout(() => {
    console.log('Timed out waiting for the browser sign-in. Run the login again.');
    process.exit(1);
  }, TIMEOUT_MS).unref();
});
