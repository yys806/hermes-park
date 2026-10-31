// 极简静态服务器 + /api/state
// 用法：node server/server.js   → http://127.0.0.1:8788
const http = require('http');
const fs = require('fs');
const path = require('path');
const api = require('./api');

const ROOT = path.resolve(__dirname, '..');
const PORT = process.env.PORT || 8788;

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
  '.svg': 'image/svg+xml', '.webp': 'image/webp', '.ico': 'image/x-icon',
  '.glb': 'model/gltf-binary', '.gltf': 'model/gltf+json',
};

function send(res, code, body, type = 'application/json; charset=utf-8') {
  res.writeHead(code, { 'Content-Type': type, 'Cache-Control': 'no-store', 'Access-Control-Allow-Origin': '*' });
  res.end(body);
}

const server = http.createServer((req, res) => {
  const url = decodeURIComponent(req.url.split('?')[0]);

  // ── 业务 API（待办/影视/cron/镜像/天气），见 server/api.js ──
  if (url.startsWith('/api/')) {
    api.handle(req, res, send).catch((e) => send(res, 500, JSON.stringify({ error: String(e && e.message || e) })));
    return;
  }

  // ── 状态接口：后续接真实 Hermes 状态就在这里改 ──
  if (url === '/api/state') {
    const mockPath = path.join(ROOT, 'src', 'state', 'mock.json');
    fs.readFile(mockPath, (err, buf) => {
      if (err) return send(res, 500, JSON.stringify({ error: 'state unavailable' }));
      const data = JSON.parse(buf.toString('utf8'));
      data.updatedAt = new Date().toISOString();
      send(res, 200, JSON.stringify(data));
    });
    return;
  }

  // ── 静态文件 ──
  let rel = url.endsWith('/') ? url + 'index.html' : url;  // /viewer/ → /viewer/index.html
  const filePath = path.join(ROOT, rel);
  if (!filePath.startsWith(ROOT)) return send(res, 403, 'forbidden', 'text/plain');

  fs.readFile(filePath, (err, buf) => {
    if (err) return send(res, 404, 'not found', 'text/plain');
    send(res, 200, buf, MIME[path.extname(filePath).toLowerCase()] || 'application/octet-stream');
  });
});

server.listen(PORT, () => {
  console.log(`园区中控台 → http://127.0.0.1:${PORT}`);
});
