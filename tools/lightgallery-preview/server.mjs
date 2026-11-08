import { createServer } from 'node:http';
import { createHash, randomBytes } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { networkInterfaces } from 'node:os';
import { extname } from 'node:path';
import { createInterface } from 'node:readline/promises';

const packageRoot = new URL('./', import.meta.url);
const manifest = JSON.parse(readFileSync(new URL('manifest.json', packageRoot), 'utf8'));
const files = new Map();
for (const [name, expected] of Object.entries(manifest.files)) {
  if (!/^(?:before|after|host)\/[a-z0-9_./-]+$/i.test(name) || name.split('/').some(part => part === '.' || part === '..')) {
    throw new Error('Invalid package path');
  }
  const bytes = readFileSync(new URL(name, packageRoot));
  if (createHash('sha256').update(bytes).digest('hex') !== expected) {
    throw new Error('Package hash mismatch: ' + name);
  }
  files.set(name, bytes);
}

const hostPort = 8142;
const childPort = 8143;
const lifetimeMinutes = 120;
const ticket = randomBytes(12).toString('base64url');
const loopback = '127.0.0.1';
const privateIPv4 = /^(?:10\.|192\.168\.|172\.(?:1[6-9]|2\d|3[01])\.)/;
const modes = [
  ['normal.html', '通常埋め込み'],
  ['body.html', '独立BODYスクロール'],
  ['best-shots-2025.html', '直アクセス'],
];
const mime = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.webp': 'image/webp',
  '.gif': 'image/gif',
  '.woff': 'font/woff',
  '.woff2': 'font/woff2',
  '.ttf': 'font/ttf',
};
const versions = { after: '修正後', before: '修正前' };
const escapeHtml = text => String(text).replace(/[&<>"']/g, character =>
  ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[character],
);

function scope(address, isLan) {
  return {
    prefix: isLan ? '/' + ticket : '',
    parent: 'http://' + address + ':' + hostPort,
    child: 'http://' + address + ':' + childPort,
  };
}

function landing(routes) {
  const groups = Object.entries(versions).map(([version, label]) => {
    const links = modes.map(([file, name], index) => {
      const origin = index === 2 ? routes.child : routes.parent;
      return '<a href="' + origin + routes.prefix + '/' + version + '/' + file + '">' + name + '</a>';
    }).join('');
    const sha = version === 'after' ? manifest.candidate : manifest.published_baseline;
    return '<section><h2>' + label + '</h2><p class="sha">' + escapeHtml(sha) + '</p><nav>' + links + '</nav></section>';
  }).join('');
  return files.get('host/index.html').toString('utf8').replace('<!-- MODES -->', groups);
}

function headers(routes, isHost) {
  const rules = [
    "default-src 'none'", "script-src 'self' 'unsafe-inline'", "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data:", "font-src 'self'", "connect-src 'none'", "object-src 'none'",
    "base-uri 'none'", "form-action 'none'",
    isHost ? 'frame-src ' + routes.child : "frame-src 'none'",
    isHost ? "frame-ancestors 'none'" : 'frame-ancestors ' + routes.parent,
  ];
  return {
    'Content-Security-Policy': rules.join('; '),
    'Referrer-Policy': 'origin',
    'X-Content-Type-Options': 'nosniff',
    'X-DNS-Prefetch-Control': 'off',
    'Cache-Control': 'no-store',
  };
}

function ipv4Number(address) {
  return address.split('.').reduce((result, octet) => (result << 8) | Number(octet), 0);
}

function requestHandler(adapter, isHost) {
  const address = adapter?.address ?? loopback;
  const routes = scope(address, !!adapter);
  const expectedHost = address + ':' + (isHost ? hostPort : childPort);
  const security = headers(routes, isHost);
  return (request, response) => {
    const send = (status, body, type = 'text/plain; charset=utf-8') => {
      const bytes = Buffer.isBuffer(body) ? body : Buffer.from(body);
      response.writeHead(status, { ...security, 'Content-Type': type, 'Content-Length': bytes.length });
      response.end(request.method === 'HEAD' ? undefined : bytes);
    };
    const peer = request.socket.remoteAddress;
    const validPeer = adapter
      ? peer && privateIPv4.test(peer) &&
        (ipv4Number(peer) & ipv4Number(adapter.netmask)) === (ipv4Number(address) & ipv4Number(adapter.netmask))
      : peer === loopback;
    if (request.headers.host !== expectedHost || !validPeer) return send(403, 'Forbidden');
    if (!['GET', 'HEAD'].includes(request.method)) return send(405, 'GET and HEAD only');
    if (!request.url.startsWith(routes.prefix + '/')) return send(404, 'Preview link not found');
    const relative = request.url.slice(routes.prefix.length + 1);
    if (isHost && (relative === '' || relative === 'index.html')) return send(200, landing(routes), mime['.html']);
    const match = /^(before|after)\/(normal|body)\.html$/.exec(relative);
    if (isHost && match) {
      const [, version] = match;
      const page = files.get('host/' + relative).toString('utf8')
        .replaceAll('__PREVIEW_CHILD__', routes.child + routes.prefix + '/' + version)
        .replaceAll('__PREVIEW_HOME__', routes.parent + routes.prefix + '/');
      return send(200, page, mime['.html']);
    }
    if (isHost || !/^(?:after|before)\/[a-z0-9_./-]+$/i.test(relative) || !files.has(relative)) {
      return send(404, 'Preview link not found');
    }
    let data = files.get(relative);
    if (relative.endsWith('/assets/gallery.js')) {
      // Substitute only the exact trusted host. Parent WindowProxy checks stay intact.
      data = data.toString('utf8').replace("'https://exsudoporus-ruber.hatenablog.jp'", JSON.stringify(routes.parent));
    }
    return send(200, data, mime[extname(relative)] ?? 'application/octet-stream');
  };
}

async function selectAdapter() {
  if (process.argv.includes('--local')) return null;
  let interfaces;
  try {
    interfaces = networkInterfaces();
  } catch {
    console.log('ネットワークアダプターを取得できなかったため、PCのみで起動します。');
    return null;
  }
  const adapters = Object.entries(interfaces).flatMap(([name, addresses]) =>
    addresses.filter(item => item.family === 'IPv4' && !item.internal && privateIPv4.test(item.address) && item.netmask)
      .map(item => ({ name, ...item })),
  );
  const lanArgument = process.argv.indexOf('--lan');
  if (lanArgument !== -1) {
    const adapter = adapters.find(item => item.address === process.argv[lanArgument + 1]);
    if (!adapter) throw new Error('The requested private IPv4 adapter is unavailable');
    return adapter;
  }
  if (!adapters.length) return null;
  const input = createInterface({ input: process.stdin, output: process.stdout });
  try {
    console.log('同じWi-FiのAndroidでも使う場合は、PCのWi-Fiアダプターを選んでください。');
    console.log('  0  PCのみ');
    adapters.forEach((item, index) => console.log('  ' + (index + 1) + '  ' + item.name + ' (' + item.address + ')'));
    const choice = (await input.question('番号 [Enter = PCのみ]: ')).trim();
    if (choice === '' || choice === '0') return null;
    const adapter = adapters[Number(choice) - 1];
    if (!adapter) throw new Error('番号が一覧にありません。起動し直してください。');
    return adapter;
  } finally {
    input.close();
  }
}

const servers = [];
function stop() {
  for (const server of servers) {
    server.close();
    server.closeAllConnections();
  }
  console.log('プレビューを終了しました。');
  process.exit(0);
}
async function listen(adapter, isHost) {
  const server = createServer(requestHandler(adapter, isHost));
  server.requestTimeout = 10000;
  servers.push(server);
  await new Promise((resolve, reject) => {
    server.once('error', reject);
    server.listen(isHost ? hostPort : childPort, adapter?.address ?? loopback, resolve);
  });
}

try {
  const adapter = await selectAdapter();
  for (const device of adapter ? [null, adapter] : [null]) {
    await listen(device, true);
    await listen(device, false);
  }
  console.log('\nLightGallery PR #142 / ' + manifest.candidate + ' / SHA-256 OK');
  console.log('Windows Chrome: http://127.0.0.1:' + hostPort + '/');
  if (adapter) {
    const routes = scope(adapter.address, true);
    console.log('Android Chrome: ' + routes.parent + routes.prefix + '/');
  } else {
    console.log('PCのみ。Androidで確認する場合はWi-Fiアダプターを選んで再起動してください。');
  }
  console.log(lifetimeMinutes + '分で自動停止します。終了は Ctrl+C。\n');
  process.on('SIGINT', stop);
  process.on('SIGTERM', stop);
  setTimeout(stop, lifetimeMinutes * 60 * 1000).unref();
} catch (error) {
  console.error('起動失敗: ' + error.message);
  console.error('8142 / 8143を使用中の場合は、先に以前のプレビューを閉じてください。');
  for (const server of servers) server.close();
  process.exitCode = 1;
}
