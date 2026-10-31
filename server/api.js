// 园区业务看板 · 本地 API（零依赖）
// 只监听本机；凭据只在服务端；写操作全部走这里，前端不直连飞书。
'use strict';
const fs = require('fs');
const path = require('path');
const https = require('https');
const { execFile } = require('child_process');
const feishu = require('./feishu');
const cron = require('./cron');
const agents = require('./agents');

const HOME = path.resolve(__dirname, '..');
const DATA = path.join(HOME, 'cache', 'api');
fs.mkdirSync(DATA, { recursive: true });

const F = {
  todoMine: { app: 'Kvkqbo32RaERuCstSTuckcfInmd', table: 'tblzIlEmdw2k0eJl', owner: 'mine' },
  todoRainbow: { app: 'Kvkqbo32RaERuCstSTuckcfInmd', table: 'tblgJhXwDhqitqyR', owner: 'rainbow' },
  media: { app: 'GNOGby5g2aw8GRsZV9hcpDzNnad' },
  rainbow: { app: 'FCltbRYiHa12Jbsm8fFczyXGnDg' },
  assets: { app: 'Hs2CbbJDaa5QqCsNdVscJoyTnac' },
};

const readJSON = (p, d) => { try { return JSON.parse(fs.readFileSync(p, 'utf8')); } catch (e) { return d; } };
const writeJSON = (p, v) => { fs.mkdirSync(path.dirname(p), { recursive: true }); fs.writeFileSync(p, JSON.stringify(v, null, 1), 'utf8'); };
const file = (n) => path.join(DATA, n);
const nowISO = () => new Date().toISOString();

function appendChange(rec) { fs.appendFileSync(file('changes.jsonl'), JSON.stringify({ at: nowISO(), ...rec }) + '\n', 'utf8'); }

// ── business.json（地块/分区职责）──
let business = null;
function loadBusiness() {
  if (!business) business = readJSON(path.join(HOME, 'viewer2', 'business.json'), { plots: {} });
  return business;
}
const PLOT_NAME = { control: '中央大厅', learn: '学习科研', daily: '日常事务', family: '家人事务', vault: '资产管理', clock: '通知待办', press: '咨询新闻', inventor: '发明工坊', rainbow: '彩虹事务', clawd: 'Claude外协', pi: 'Pi外协', codex: 'Codex外协' };

// ── 绑定 ──
const BIND_PATH = () => file('bindings.json');
function loadBindings() { return readJSON(BIND_PATH(), {}); }
function saveBindings(b) { writeJSON(BIND_PATH(), b); }

// 关键词优先（2026-10-31 v2.0）：产业务归位，体育/体测/影视一律归日常事务；不再有分区
const KW_PLOT = [
  [/体育|体测|跑步|锻炼|刷锻|影视|电影|电视剧|小说|购物|快递|采购|生活用品/, 'daily'],
  [/彩虹|国考|省考|研考|烟草|求职|招聘|面试|考公/, 'rainbow'],
  [/研习室|图书馆|校园|教务|选课|Canvas|课程|上课|实验|论文|文献|组会|毕业设计|毕设|开题|答辩|北大|同济|科研|算力|报销/, 'learn'],
  [/服务器|域名|备份|中转站|续费|到期|MCP|噜小记|生图站|资产|网站|小程序/, 'vault'],
  [/爸爸|妈妈|弟弟|家人|家里|老爸|老妈|老婆|亲属/, 'family'],
];
const TYPE_PLOT = [[/生活/, 'daily'], [/学业|科研/, 'learn'], [/考公|求职/, 'rainbow'], [/升学/, 'learn']];

function guessBind(item, owner) {
  if (owner === 'rainbow') return { plot: 'rainbow', subsection: null, why: 'owner' };
  const title = String(item.title || '');
  for (const [re, id] of KW_PLOT) if (re.test(title)) return { plot: id, subsection: null, why: 'kw' };
  const type = String(item.type || '');
  for (const [re, id] of TYPE_PLOT) if (re.test(type)) return { plot: id, subsection: null, why: 'type' };
  return { plot: 'control', subsection: null, why: 'default' };
}

function bindKey(owner, id) { return owner + ':' + id; }

function applyBindings(items) {
  const b = loadBindings();
  return items.map((it) => {
    const manual = b[bindKey(it.owner, it.id)];
    if (manual && manual.status !== '软删') return { ...it, plot: manual.plot, subsection: manual.subsection || null, auto_bound: manual.mode === 'auto' };
    if (manual && manual.status === '软删') return { ...it, hidden: true };
    const g = guessBind(it, it.owner);
    return { ...it, plot: g.plot, subsection: g.subsection, auto_bound: true };
  }).filter((x) => !x.hidden);
}

// ── 待办 ──
const FIELD_CACHE = {};
async function resolveFields(cfg) {
  const key = cfg.app + cfg.table;
  if (FIELD_CACHE[key]) return FIELD_CACHE[key];
  const items = await feishu.listFields(cfg.app, cfg.table);
  const names = items.map((i) => i.field_name);
  const pick = (re, fallback) => names.find((n) => re.test(n)) || fallback;
  const map = {
    all: names,
    task: pick(/^任务$|标题|名称/, names[0]),
    type: pick(/类型/, '类型'),
    start: pick(/开始/, null),
    due: pick(/截止/, null),
    status: pick(/状态/, null),
    note: pick(/备注/, null),
  };
  FIELD_CACHE[key] = map;
  return map;
}

function normTodo(rec, cfg, map) {
  const f = rec.fields || {};
  const get = (n) => (n ? f[n] : undefined);
  return {
    id: rec.record_id,
    owner: cfg.owner,
    title: feishu.textOf(get(map.task)),
    type: feishu.textOf(get(map.type)),
    start: feishu.dateOf(get(map.start)),
    due: feishu.dateOf(get(map.due)),
    status: feishu.textOf(get(map.status)),
    note: feishu.textOf(get(map.note)),
  };
}

async function getTodos(owner, scope) {
  const cfgs = owner === 'rainbow' ? [F.todoRainbow] : owner === 'mine' ? [F.todoMine] : [F.todoMine, F.todoRainbow];
  const out = [];
  let stale = false, fetchedAt = null;
  for (const cfg of cfgs) {
    const cachePath = file('todo_cache_' + cfg.owner + '.json');
    try {
      const map = await resolveFields(cfg);
      const recs = await feishu.listRecords(cfg.app, cfg.table);
      const items = recs.map((r) => normTodo(r, cfg, map));
      writeJSON(cachePath, { at: nowISO(), items });
      out.push(...items);
      fetchedAt = nowISO();
    } catch (e) {
      const c = readJSON(cachePath, { items: [] });
      out.push(...(c.items || []));
      stale = true;
      fetchedAt = c.at || null;
    }
  }
  let items = applyBindings(out);
  if (scope !== 'all') items = items.filter((x) => !/已完成/.test(x.status || ''));
  return { items, stale, fetched_at: fetchedAt };
}

async function createTodo(body) {
  const cfg = body.owner === 'rainbow' ? F.todoRainbow : F.todoMine;
  const map = await resolveFields(cfg);
  const fields = {};
  fields[map.task] = String(body.title || '').trim() || '未命名';
  if (body.type && map.type) fields[map.type] = body.type;
  if (body.status && map.status) fields[map.status] = body.status;
  if (body.note && map.note) fields[map.note] = body.note;
  if (body.due && map.due) fields[map.due] = Date.parse(body.due + 'T00:00:00+08:00');
  if (body.start && map.start) fields[map.start] = Date.parse(body.start + 'T00:00:00+08:00');
  const rec = await feishu.createRecord(cfg.app, cfg.table, fields);
  if (body.plot) {
    const b = loadBindings();
    b[bindKey(cfg.owner, rec.record_id)] = { plot: body.plot, subsection: body.subsection || null, mode: 'manual', status: '有效', at: nowISO() };
    saveBindings(b);
  }
  appendChange({ op: 'create', owner: cfg.owner, id: rec.record_id, fields });
  return { ok: true, id: rec.record_id };
}

async function patchTodo(body) {
  const cfg = body.owner === 'rainbow' ? F.todoRainbow : F.todoMine;
  const map = await resolveFields(cfg);
  const f = body.fields || {};
  const fields = {};
  if (f.status && map.status) fields[map.status] = f.status;
  if (f.title && map.task) fields[map.task] = f.title;
  if (f.note != null && map.note) fields[map.note] = f.note;
  if (f.due && map.due) fields[map.due] = Date.parse(f.due + 'T00:00:00+08:00');
  if (!Object.keys(fields).length) return { ok: false, error: '没有可写字段' };
  // 记录旧值，便于撤销
  const before = await feishu.listRecords(cfg.app, cfg.table).then((rs) => normTodo(rs.find((r) => r.record_id === body.id) || { fields: {} }, cfg, map));
  await feishu.updateRecord(cfg.app, cfg.table, body.id, fields);
  appendChange({ op: 'update', owner: cfg.owner, id: body.id, fields, before });
  return { ok: true, rev: Date.now() };
}

// G5：过期自动归档（截止日早于今天 → 云表置「已完成」并留痕，可撤销）
async function cleanOverdue() {
  const today = new Date(); today.setHours(0, 0, 0, 0);
  const cleaned = [];
  for (const owner of ['mine', 'rainbow']) {
    const cfg = owner === 'rainbow' ? F.todoRainbow : F.todoMine;
    const map = await resolveFields(cfg);
    const recs = await feishu.listRecords(cfg.app, cfg.table);
    for (const r of recs) {
      const it = normTodo(r, cfg, map);
      if (!it.due || !map.status) continue;
      if (/已完成|已取消|完成|取消/.test(it.status || '')) continue;
      const d = new Date(it.due + 'T00:00:00+08:00');
      if (!(d < today)) continue;
      const fields = { [map.status]: '已完成' };
      await feishu.updateRecord(cfg.app, cfg.table, it.id, fields);
      appendChange({ op: 'update', owner: it.owner, id: it.id, fields, before: it, auto: 'overdue' });
      cleaned.push({ owner: it.owner, title: it.title, due: it.due });
    }
  }
  return { ok: true, count: cleaned.length, cleaned, at: nowISO() };
}

async function undoLast(body) {
  const cfg = body.owner === 'rainbow' ? F.todoRainbow : F.todoMine;
  const map = await resolveFields(cfg);
  const lines = fs.existsSync(file('changes.jsonl')) ? fs.readFileSync(file('changes.jsonl'), 'utf8').trim().split('\n') : [];
  for (let i = lines.length - 1; i >= 0; i--) {
    let r; try { r = JSON.parse(lines[i]); } catch (e) { continue; }
    if (r.op === 'update' && r.owner === cfg.owner && r.id === body.id && r.before) {
      const fields = {};
      if (r.before.status && map.status) fields[map.status] = r.before.status;
      if (r.before.title && map.task) fields[map.task] = r.before.title;
      if (r.before.note != null && map.note) fields[map.note] = r.before.note;
      if (r.before.due && map.due) fields[map.due] = Date.parse(r.before.due + 'T00:00:00+08:00');
      await feishu.updateRecord(cfg.app, cfg.table, body.id, fields);
      appendChange({ op: 'undo', owner: cfg.owner, id: body.id, fields });
      return { ok: true, restored: r.before };
    }
  }
  return { ok: false, error: '没有可撤销的改动' };
}

async function softDelete(body) {
  const b = loadBindings();
  const k = bindKey(body.owner, body.id);
  const prev = b[k] || {};
  b[k] = { ...prev, status: '软删', at: nowISO() };
  saveBindings(b);
  appendChange({ op: 'soft-delete', owner: body.owner, id: body.id });
  return { ok: true };
}

// ── 影视 ──
async function mediaSheets() {
  const tabs = await feishu.listTables(F.media.app);
  return tabs.map((t) => ({ id: t.table_id, name: t.name }));
}
async function getMedia(sheetName, limit) {
  const tabs = await mediaSheets();
  const t = tabs.find((x) => sheetName ? x.name.includes(sheetName) : true) || tabs[0];
  if (!t) return { items: [] };
  const recs = await feishu.listRecords(F.media.app, t.id, { pageSize: 200, maxPages: 2 });
  const items = recs.slice(0, limit || 40).map((r) => {
    const f = r.fields || {};
    const g = (re) => { const k = Object.keys(f).find((n) => re.test(n)); return k ? feishu.textOf(f[k]) : ''; };
    const raw = (re) => { const k = Object.keys(f).find((n) => re.test(n)); return k ? f[k] : null; };
    const doneRaw = raw(/看完/);
    return { id: r.record_id, sheet: t.name,
      name: g(/名称|标题/), status: g(/^状态$/), year: g(/年份/), author: g(/导演|作者/),
      done: typeof doneRaw === 'number' ? feishu.dateOf(doneRaw) : (doneRaw ? feishu.textOf(doneRaw) : ''),
      score: g(/豆瓣/), mine: g(/我的评分/), note: g(/短评|备注/) };
  });
  return { sheet: t.name, items };
}
async function patchMedia(body) {
  const tabs = await mediaSheets();
  const t = tabs.find((x) => x.name === body.sheet) || tabs.find((x) => body.sheet && x.name.includes(body.sheet));
  if (!t) return { ok: false, error: '找不到子表' };
  const fields = await feishu.listFields(F.media.app, t.id);
  const names = fields.map((f) => f.field_name);
  const out = {};
  const st = names.find((n) => /^状态$/.test(n));
  const dn = names.find((n) => /看完/.test(n));
  if (body.fields.status && st) out[st] = body.fields.status;
  if (body.fields.watched_at && dn) out[dn] = Date.parse(body.fields.watched_at + 'T00:00:00+08:00');
  if (!Object.keys(out).length) return { ok: false, error: '只允许改 状态 / 看完日期' };
  await feishu.updateRecord(F.media.app, t.id, body.id, out);
  appendChange({ op: 'media-update', sheet: t.name, id: body.id, fields: out });
  return { ok: true };
}

// ── 真实会话状态（进度环用真数据，不是装饰）──
// 数据源：D:/hermes/state.db（Hermes 自己的会话表 + 消息表），由 scripts/live_state.py 读出
const CHAT2PLOT = {
  oc_91703634e58ed8f3c258e7345f0c5354: 'learn',
  oc_c73e1da1943d50e50b2645b8bb391471: 'daily',
  oc_297f2b68127d9f96411e7d9ceb7bfb1b: 'family',
  oc_99819e11b0dfda58e81193cece50700f: 'rainbow',
  oc_ddea1b31f5c72999e3b9625eb5273226: 'vault',
  oc_adbdc29db37955177a603586f065f819: 'press',
  oc_92aabb918636f083f664e197e82d6279: 'clock',
  oc_58468b4626a37ec8dd47038dc4d56e77: 'inventor',
};
let liveCache = { at: 0, data: null };
function readLive() {
  return new Promise((resolve) => {
    const now = Date.now();
    if (liveCache.data && now - liveCache.at < 5000) return resolve(liveCache.data);
    const { execFile } = require('child_process');
    execFile('python', [path.join(HOME, '..', 'scripts', 'live_state.py')], { timeout: 15000, windowsHide: true },
      (err, so) => {
        if (err) return resolve(liveCache.data || { ok: false, plots: {}, error: String(err.message || err) });
        try {
          const raw = JSON.parse(String(so));
          const plots = {};
          for (const c of raw.chats || []) {
            const pl = CHAT2PLOT[c.chat_id];
            if (!pl) continue;
            const cur = plots[pl];
            const item = { name: c.name, busy: !!c.busy, idleSec: c.idleSec, doing: c.doing, chat_id: c.chat_id };
            if (!cur) plots[pl] = item;
            else {
              cur.busy = cur.busy || item.busy;
              if ((item.idleSec ?? 1e9) < (cur.idleSec ?? 1e9)) { cur.idleSec = item.idleSec; cur.doing = item.doing; }
            }
          }
          // 外协三块已改为纯摆件：不参与进度环判定（用户 2026-10-31 19:45 定）
          liveCache = { at: now, data: { ok: true, at: raw.at, plots } };
          resolve(liveCache.data);
        } catch (e) { resolve({ ok: false, plots: {}, error: 'parse' }); }
      });
  });
}

// ── 只读镜像 ──
async function mirror(name) {
  const cfg = name === 'rainbow' ? F.rainbow : F.assets;
  const tabs = await feishu.listTables(cfg.app);
  const out = [];
  for (const t of tabs) {
    const recs = await feishu.listRecords(cfg.app, t.table_id, { pageSize: 100, maxPages: 2 });
    const rows = recs.slice(0, 60).map((r) => {
      const o = {};
      for (const [k, v] of Object.entries(r.fields || {})) {
        // 敏感列一律打码：镜像页只给人看结构，不把密码/密钥送到浏览器
        o[k] = /密码|凭据|安全码|卡号|token|key|secret/i.test(k)
          ? '••••'
          : ((typeof v === 'number' ? feishu.dateOf(v) : '') || feishu.textOf(v));
      }
      return o;
    });
    out.push({ name: t.name, count: recs.length, rows });
  }
  return { name, tables: out, at: nowISO() };
}

// ── 天气 ──
let wxCache = { at: 0, data: null };
function fetchWeather() {
  return new Promise((resolve) => {
    if (wxCache.data && Date.now() - wxCache.at < 10 * 60 * 1000) return resolve(wxCache.data);
    const url = 'https://api.open-meteo.com/v1/forecast?latitude=31.38&longitude=121.25&current=temperature_2m,weather_code,cloud_cover,wind_speed_10m&daily=sunrise,sunset&timezone=Asia%2FShanghai&forecast_days=1';
    const req = https.get(url, { timeout: 8000 }, (res) => {
      let b = ''; res.on('data', (c) => (b += c));
      res.on('end', () => {
        try { const j = JSON.parse(b); wxCache = { at: Date.now(), data: j }; resolve(j); }
        catch (e) { resolve(wxCache.data); }
      });
    });
    req.on('timeout', () => { req.destroy(); resolve(wxCache.data); });
    req.on('error', () => resolve(wxCache.data));
  });
}

// ── cron 重跑 ──
function runCronJob(id) {
  return new Promise((resolve) => {
    execFile('hermes', ['cron', 'run', id], { timeout: 20000 }, (err, so, se) => {
      if (err) return resolve({ ok: false, error: String(se || err.message).slice(0, 300) });
      resolve({ ok: true, output: String(so).trim() });
    });
  });
}

// ── 路由 ──
function readBody(req) {
  return new Promise((resolve, reject) => {
    let b = ''; let n = 0;
    req.on('data', (c) => { n += c.length; if (n > 1e6) { reject(new Error('body too large')); req.destroy(); } b += c; });
    req.on('end', () => { try { resolve(b ? JSON.parse(b) : {}); } catch (e) { reject(e); } });
  });
}

// GET /api/todo 短缓存：相邻地块预取时不重复打飞书；任何写操作清空
const todoMemo = new Map();

async function handle(req, res, send) {
  const u = new URL(req.url, 'http://127.0.0.1');
  const p = u.pathname;
  const q = u.searchParams;
  const method = req.method;

  if (p === '/api/health') return send(res, 200, JSON.stringify({ ok: true, ts: nowISO(), pending: readJSON(file('pending_writes.json'), []).length }));
  if (p === '/api/business') return send(res, 200, JSON.stringify(loadBusiness()));

  if (p.startsWith('/api/todo') && method !== 'GET') todoMemo.clear();
  if (p === '/api/todo') {
    if (method === 'GET') {
      const owner = q.get('owner') || 'all', scope = q.get('scope') || 'open', key = owner + '|' + scope;
      let m = todoMemo.get(key);
      if (!m || Date.now() - m.at > 15000) { m = { at: Date.now(), r: await getTodos(owner, scope) }; todoMemo.set(key, m); }
      const plot = q.get('plot');
      return send(res, 200, JSON.stringify(plot ? { ...m.r, items: m.r.items.filter((x) => x.plot === plot) } : m.r));
    }
    const body = await readBody(req);
    if (method === 'POST') return send(res, 200, JSON.stringify(await createTodo(body)));
    if (method === 'PATCH') return send(res, 200, JSON.stringify(await patchTodo(body)));
    if (method === 'DELETE') return send(res, 200, JSON.stringify(await softDelete(body)));
  }
  if (p === '/api/todo/clean' && method === 'POST') return send(res, 200, JSON.stringify(await cleanOverdue()));
  if (p === '/api/todo/undo' && method === 'POST') return send(res, 200, JSON.stringify(await undoLast(await readBody(req))));

  if (p === '/api/media') {
    if (method === 'GET') return send(res, 200, JSON.stringify(await getMedia(q.get('sheet'), Number(q.get('limit')) || 40)));
    if (method === 'PATCH') return send(res, 200, JSON.stringify(await patchMedia(await readBody(req))));
  }

  if (p === '/api/mirror') return send(res, 200, JSON.stringify(await mirror(q.get('name') || 'assets')));
  if (p === '/api/weather') return send(res, 200, JSON.stringify(await fetchWeather()));

  if (p === '/api/cron') {
    try {
      const r = cron.summary();
      const plot = q.get('plot');
      return send(res, 200, JSON.stringify(plot ? { ...r, jobs: r.jobs.filter((j) => j.plot === plot) } : r));
    }
    catch (e) { return send(res, 500, JSON.stringify({ error: String(e.message) })); }
  }
  if (p === '/api/cron/report') {
    const r = cron.readReport(q.get('id'), Number(q.get('n')) || 1);
    return send(res, r ? 200 : 404, JSON.stringify(r || { error: '没有报表' }));
  }
  if (p === '/api/cron/history') {
    const id = q.get('id');
    const rows = cron.recentRuns(600).filter((x) => x.job === id).slice(0, Number(q.get('limit')) || 30);
    return send(res, 200, JSON.stringify({ id, rows }));
  }
  if (p === '/api/cron/run' && method === 'POST') {
    const body = await readBody(req);
    return send(res, 200, JSON.stringify(await runCronJob(body.id)));
  }

  // P5：云表入口（只给跳转链接，不取表内容）。园区绑定表读 feishu_bindings.json（home/cache 优先，其次上一级 cache）
  if (p === '/api/live') return send(res, 200, JSON.stringify(await readLive()));
  if (p === '/api/links') {
    const base = (app, table) => `https://icnrjjpowor2.feishu.cn/base/${app}${table ? '?table=' + table : ''}`;
    const bindFile = [path.join(HOME, 'cache', 'feishu_bindings.json'), path.join(HOME, '..', 'cache', 'feishu_bindings.json')].find((f) => fs.existsSync(f));
    const bind = bindFile ? readJSON(bindFile, null) : null;
    const links = {
      todoMine: { name: '待办台账·我的', url: base(F.todoMine.app, F.todoMine.table) },
      todoRainbow: { name: '待办台账·彩虹的', url: base(F.todoRainbow.app, F.todoRainbow.table) },
      assets: { name: '资产台账', url: base(F.assets.app) },
      rainbow: { name: '彩虹出路', url: base(F.rainbow.app) },
      media: { name: '影视清单', url: base(F.media.app) },
    };
    if (bind && bind.app_token) links.bindings = { name: '园区绑定', url: base(bind.app_token, bind.table_id) };
    return send(res, 200, JSON.stringify({ links, bindingsFile: bindFile || null }));
  }

  if (p === '/api/agents') {
    try { return send(res, 200, JSON.stringify({ agents: await agents.probe(), fetchedAt: nowISO() })); }
    catch (e) { return send(res, 500, JSON.stringify({ error: String(e.message) })); }
  }

  return send(res, 404, JSON.stringify({ error: 'unknown api', path: p }));
}

module.exports = { handle };
