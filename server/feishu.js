// 飞书客户端（零依赖，node 内置模块）
// 只被 server/api.js 调用；凭据只在这里读，绝不外发。
'use strict';
const fs = require('fs');
const path = require('path');
const https = require('https');

const HOME = path.resolve(__dirname, '..');
const ENV_PATH = path.join(HOME, '..', '.env');

function loadEnv() {
  const out = {};
  try {
    const txt = fs.readFileSync(ENV_PATH, 'utf8');
    for (const line of txt.split(/\r?\n/)) {
      const m = /^([A-Z0-9_]+)\s*=\s*(.*)$/.exec(line.trim());
      if (m) out[m[1]] = m[2].replace(/^["']|["']$/g, '');
    }
  } catch (e) { /* 忽略 */ }
  return out;
}

const ENV = loadEnv();
const APP_ID = ENV.FEISHU_APP_ID || '';
const APP_SECRET = ENV.FEISHU_APP_SECRET || '';
const BASE = 'https://open.feishu.cn/open-apis';

let token = { value: '', exp: 0 };

function request(method, url, body, headers = {}, timeout = 8000) {
  return new Promise((resolve, reject) => {
    const u = new URL(url);
    const payload = body == null ? null : JSON.stringify(body);
    const req = https.request({
      hostname: u.hostname, path: u.pathname + u.search, method,
      headers: {
        'Content-Type': 'application/json; charset=utf-8',
        ...(payload ? { 'Content-Length': Buffer.byteLength(payload) } : {}),
        ...headers,
      },
      timeout,
    }, (res) => {
      let buf = '';
      res.on('data', (c) => { buf += c; });
      res.on('end', () => {
        try { resolve({ status: res.statusCode, json: JSON.parse(buf) }); }
        catch (e) { resolve({ status: res.statusCode, json: null, raw: buf }); }
      });
    });
    req.on('timeout', () => { req.destroy(new Error('timeout')); });
    req.on('error', reject);
    if (payload) req.write(payload);
    req.end();
  });
}

async function getToken(force = false) {
  if (!force && token.value && Date.now() < token.exp) return token.value;
  const r = await request('POST', `${BASE}/auth/v3/tenant_access_token/internal`, { app_id: APP_ID, app_secret: APP_SECRET });
  if (!r.json || r.json.code !== 0) throw new Error('飞书 token 失败: ' + JSON.stringify(r.json || r.status));
  token = { value: r.json.tenant_access_token, exp: Date.now() + Math.max(60, (r.json.expire || 7200) - 300) * 1000 };
  return token.value;
}

async function api(method, p, body) {
  const t = await getToken();
  const r = await request(method, BASE + p, body, { Authorization: 'Bearer ' + t });
  if (r.json && r.json.code === 99991663) { // token 失效重试一次
    const t2 = await getToken(true);
    return request(method, BASE + p, body, { Authorization: 'Bearer ' + t2 }).then((x) => x.json);
  }
  return r.json;
}

// ── 多维表格 ──
async function listFields(app, table) {
  const j = await api('GET', `/bitable/v1/apps/${app}/tables/${table}/fields?page_size=100`);
  return (j && j.data && j.data.items) || [];
}

async function listRecords(app, table, { pageSize = 200, maxPages = 5 } = {}) {
  const items = [];
  let pageToken = '';
  for (let i = 0; i < maxPages; i++) {
    const q = `?page_size=${pageSize}${pageToken ? '&page_token=' + encodeURIComponent(pageToken) : ''}`;
    const j = await api('GET', `/bitable/v1/apps/${app}/tables/${table}/records${q}`);
    if (!j || j.code !== 0) throw new Error('读记录失败: ' + JSON.stringify(j && j.msg));
    items.push(...(j.data.items || []));
    if (!j.data.has_more) break;
    pageToken = j.data.page_token || '';
  }
  return items;
}

async function createRecord(app, table, fields) {
  const j = await api('POST', `/bitable/v1/apps/${app}/tables/${table}/records`, { fields });
  if (!j || j.code !== 0) throw new Error('写记录失败: ' + JSON.stringify(j && j.msg));
  return j.data.record;
}

async function updateRecord(app, table, recordId, fields) {
  const j = await api('PUT', `/bitable/v1/apps/${app}/tables/${table}/records/${recordId}`, { fields });
  if (!j || j.code !== 0) throw new Error('更新记录失败: ' + JSON.stringify(j && j.msg));
  return j.data.record;
}

async function listTables(app) {
  const j = await api('GET', `/bitable/v1/apps/${app}/tables?page_size=50`);
  return (j && j.data && j.data.items) || [];
}

// 富文本主字段 → 纯字符串
function textOf(v) {
  if (v == null) return '';
  if (typeof v === 'string') return v;
  if (Array.isArray(v)) return v.map((x) => (typeof x === 'string' ? x : x && (x.text || x.name || ''))).join('');
  if (typeof v === 'object') return v.text || v.name || '';
  return String(v);
}
const dateOf = (ms) => (ms ? new Date(Number(ms)).toLocaleDateString('sv-SE', { timeZone: 'Asia/Shanghai' }) : null);

module.exports = { api, listFields, listRecords, createRecord, updateRecord, listTables, textOf, dateOf, BASE };
