// 右侧业务面板：职责 / 此刻 / 待办·Cron（外协三块只有：职责 / 待办）
// 数据全部来自本地 API（/api/*），与 3D 视图解耦。
// G1：切地块立即清空 + 骨架，数据按块到达后逐块填入；每块 60s 缓存；聚焦 1.5s 后预取相邻 2 块。
import { sortTodos, sortCrons, agoText } from './order.js?v=20261031-p5';

const TTL = 60000;
const AGENT_IDS = new Set(['clawd', 'pi', 'codex']);
const AGENT_DUTY = {
  clawd: {
    name: 'Claude Code', duty: '大块代码与视觉执行：整块功能实现、3D 场景与界面改造、批量修模。',
    can: ['整块功能开发', '3D 场景 / 界面改造', '批量修模与资源整理', '按任务书逐项验收'],
    no: ['飞书群消息收发', 'cron 归属与投递调整', '云表数据写入'],
  },
  pi: {
    name: 'Pi', duty: '外部命令行自动化：脚本化的批处理、跨工具调用、无人值守的命令行任务。',
    can: ['批处理脚本', '跨工具命令行调用', '无人值守的定时作业'],
    no: ['需要看图判断的界面活', '大块业务代码重构', '直接面向用户的消息'],
  },
  codex: {
    name: 'ChatGPT 桌面端（Codex 模式）', duty: '长任务线程盯守：长时间运行的研究 / 代码线程，按节点汇报与续跑。',
    can: ['长时间研究线程', '分阶段代码线程续跑', '按节点汇报进度'],
    no: ['园区前端改造', 'cron / 云表改动', '需要本机进程控制的操作'],
  },
};
// 三态：有进程 = 运行中（绿）；装了没进程 = 空闲（灰）；没装 = 未安装（黄）。以服务端 status 为准，旧接口按进程数推
const agentState = (a) => (['running', 'idle', 'offline'].includes(a.status) && 'version' in a ? a.status : a.procs > 0 ? 'running' : a.note === '未安装' ? 'offline' : 'idle');
const STATUS_LABEL = { running: '运行中', idle: '空闲', offline: '未安装' };
const spanText = (ms) => {
  const m = Math.max(0, Math.floor(ms / 60000));
  if (m < 1) return '不到 1 分钟';
  if (m < 60) return `${m} 分钟`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h} 小时 ${m % 60} 分`;
  return `${Math.floor(h / 24)} 天 ${h % 24} 小时`;
};

// P5 云表入口：只跳转，不内嵌表格。链接以 /api/links 为准（园区绑定表从 feishu_bindings.json 读）；
// 接口没起来时，用已知的 5 张表兜底（园区绑定读不到就不显示）
const FEISHU = 'https://icnrjjpowor2.feishu.cn/base/';
const LINKS_FALLBACK = {
  todoMine: { name: '待办台账·我的', url: FEISHU + 'Kvkqbo32RaERuCstSTuckcfInmd?table=tblzIlEmdw2k0eJl' },
  todoRainbow: { name: '待办台账·彩虹的', url: FEISHU + 'Kvkqbo32RaERuCstSTuckcfInmd?table=tblgJhXwDhqitqyR' },
  assets: { name: '资产台账', url: FEISHU + 'Hs2CbbJDaa5QqCsNdVscJoyTnac' },
  rainbow: { name: '彩虹出路', url: FEISHU + 'FCltbRYiHa12Jbsm8fFczyXGnDg' },
  media: { name: '影视清单', url: FEISHU + 'GNOGby5g2aw8GRsZV9hcpDzNnad' },
};
// 每块地职责页顶部的入口：[链接键, 按钮文字（省略 = 用链接名）]；没列的地块（咨询新闻、外协）不显示
const PLOT_LINKS = {
  learn: [['todoMine']],
  daily: [['media'], ['todoMine']],
  family: [['todoMine']],
  rainbow: [['rainbow'], ['todoRainbow']],
  vault: [['assets']],
  clock: [['todoMine']],
  inventor: [['bindings']],
  control: [['todoMine', '待办台账'], ['bindings']],
};
// 顶部「云表」浮层：全部入口（待办台账两张合成一行）
const POP_ROWS = [
  { name: '待办台账', keys: [['todoMine', '我的'], ['todoRainbow', '彩虹的']] },
  { name: '资产台账', keys: [['assets', '打开']] },
  { name: '彩虹出路', keys: [['rainbow', '打开']] },
  { name: '影视清单', keys: [['media', '打开']] },
  { name: '园区绑定', keys: [['bindings', '打开']] },
];
let links = null, linksP = null;
function loadLinks() {
  if (!linksP) linksP = jget('/api/links').then((r) => (links = r.links)).catch(() => (links = { ...LINKS_FALLBACK }));
  return linksP;
}
const LINK_ICON = '<svg viewBox="0 0 16 16" aria-hidden="true"><rect x="2.5" y="3" width="11" height="10" rx="1.6"/><path d="M2.5 6.5h11M6.5 6.5V13"/></svg>';
function linkBtn(key, label) {
  const L = links && links[key];
  if (!L) return null;
  const a = el('a', 'linkbtn');
  a.href = L.url; a.target = '_blank'; a.rel = 'noreferrer';
  a.innerHTML = LINK_ICON;
  a.append(el('span', null, label || L.name));
  a.title = `在飞书打开：${L.name}`;
  return a;
}
function linkRow(plotId) {
  const spec = PLOT_LINKS[plotId];
  if (!spec) return null;
  const row = el('div', 'linkrow');
  for (const [k, label] of spec) { const b = linkBtn(k, label); if (b) row.append(b); }
  return row.childElementCount ? row : null;
}

const S = { plot: null, tab: 'duty', biz: null, bizP: null, prefetched: null };
const cache = new Map();          // plot → { at, todo, cron, agents, err: {} }
let agentsShared = null;          // /api/agents 三块共用一份
let AGENTS_LAST = null;           // 最近一次 /api/agents 结果（职责页显示版本号用）
let prefetchTimer = 0;

const el = (tag, cls, text) => { const n = document.createElement(tag); if (cls) n.className = cls; if (text != null) n.textContent = text; return n; };
const $ = (id) => document.getElementById(id);

async function jget(url) {
  const r = await fetch(url, { cache: 'no-store' });
  if (!r.ok) throw new Error(url + ' ' + r.status);
  return r.json();
}

function loadBiz() {
  if (!S.bizP) S.bizP = jget('/api/business').then((b) => (S.biz = b)).catch((e) => { S.bizP = null; throw e; });
  return S.bizP;
}

function loadAgents(force) {
  if (!force && agentsShared && Date.now() - agentsShared.at < TTL) return agentsShared.p;
  const ent = { at: Date.now(), data: null };
  ent.p = jget('/api/agents').then((r) => { ent.data = r; AGENTS_LAST = r; return r; }).catch((e) => { if (agentsShared === ent) agentsShared = null; throw e; });
  agentsShared = ent;
  return ent.p;
}

// 取一块的数据：返回缓存条目（字段到了才非空），每个字段一到就通知重绘对应块
function plotData(plot, { force = false, onPart } = {}) {
  let c = cache.get(plot);
  if (!force && c && Date.now() - c.at < TTL) return c;
  const keep = c;   // 静默刷新时先保留旧数据，不闪骨架
  c = { at: Date.now(), todo: keep?.todo || null, cron: keep?.cron || null, agents: null, err: {} };
  cache.set(plot, c);
  const part = (key, p) => p.then((r) => { c[key] = r; c.err[key] = null; onPart && onPart(plot, key); })
    .catch((e) => { c.err[key] = String(e.message || e); c.at = 0; onPart && onPart(plot, key); });
  if (AGENT_IDS.has(plot)) part('agents', loadAgents(force));
  else {
    part('todo', jget(`/api/todo?owner=all&scope=open&plot=${encodeURIComponent(plot)}`));
    part('cron', jget(`/api/cron?plot=${encodeURIComponent(plot)}`));
  }
  return c;
}

// ── 小部件 ──
function skeleton(box, n = 4) {
  const sk = el('div', 'skel');
  sk.setAttribute('aria-busy', 'true');
  for (let i = 0; i < n; i++) sk.append(el('div', 'skel__bar'));
  box.append(sk);
}

function todoRow(v, plotId) {
  const t = v.item;
  const row = el('div', 'todo' + (v.bucket === 0 ? ' is-overdue' : ''));
  const box = el('button', 'todo__done'); box.type = 'button'; box.title = '标为已完成'; box.textContent = '✓';
  box.addEventListener('click', async () => {
    box.disabled = true;
    try {
      const r = await fetch('/api/todo', { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ owner: t.owner, id: t.id, fields: { status: '已完成' } }) });
      if (!r.ok) throw new Error(String(r.status));
      cache.delete(plotId);
      if (S.plot === plotId) plotData(plotId, { force: true, onPart: repaint });
      window.__leftbar && window.__leftbar.refresh(true);
    } catch (e) { box.disabled = false; }
  });
  const main = el('div', 'todo__main');
  const title = el('div', 'todo__title');
  if (v.bucket === 0) title.append(el('span', 'dot dot--bad'));
  title.append(document.createTextNode(t.title));
  main.append(title);
  const meta = el('div', 'todo__meta');
  if (v.bucket === 0) meta.append(el('span', 'tag tag--bad', `逾期 ${v.overdue} 天`));
  meta.append(document.createTextNode(t.due ? `${t.due.slice(5)}（${v.diff === 0 ? '今天' : v.diff === 1 ? '明天' : v.diff < 0 ? '已过' : v.diff + ' 天后'}）` : '无日期'));
  main.append(meta);
  row.append(box, main);
  if (t.status === '进行中') row.append(el('span', 'todo__badge', '进行中'));
  return row;
}

function cronRow(v) {
  const j = v.item;
  const row = el('div', 'cron');
  row.title = v.tip;
  const dot = el('span', 'cron__dot is-' + v.color);
  const main = el('div', 'cron__main');
  main.append(el('div', 'cron__name', j.name));
  const meta = el('div', 'cron__meta');
  if (v.bucket === 0) meta.append(el('span', 'tag tag--bad', `逾期 ${v.overdue} 天`));
  meta.append(document.createTextNode(v.meta));
  main.append(meta);
  const acts = el('div', 'cron__acts');
  if (j.hasReport) {
    const b = el('button', 'mini', '报告'); b.type = 'button';
    b.addEventListener('click', () => window.__panelShowReport && window.__panelShowReport(j.id, j.name));
    acts.append(b);
  }
  row.append(dot, main, acts);
  return row;
}

// ── 各块：ready / draw ──
const BLOCKS = {
  duty: {
    need: 'biz',
    draw(box, plotId) {
      if (AGENT_IDS.has(plotId)) {
        const a = AGENT_DUTY[plotId];
        const rec = ((AGENTS_LAST && AGENTS_LAST.agents) || []).find((x) => x.id === plotId);
        const verEl = el('p', 'pane__ver', `当前版本：${rec && rec.version ? rec.version : '读取中…'}`);
        box.append(el('p', 'pane__lead', a.duty), el('p', 'pane__sub', `执行者：${a.name}（外协小摆件，不做业务绑定）`));
        box.append(verEl);
        // 版本号要单独去拿（外协块只读这一项，不拉待办/cron）
        jget('/api/agents').then((r) => {
          AGENTS_LAST = r;
          const it = ((r.agents) || []).find((x) => x.id === plotId);
          verEl.textContent = `当前版本：${it && it.version ? it.version : '未知'}`;
        }).catch(() => { verEl.textContent = '当前版本：未知'; });
        const can = el('div', 'chips');
        can.append(el('span', 'chips__label', '能接'));
        for (const t of a.can) can.append(el('span', 'chip', t));
        const no = el('div', 'chips chips--no');
        no.append(el('span', 'chips__label', '不接'));
        for (const t of a.no) no.append(el('span', 'chip chip--no', t));
        box.append(can, no);
        return;
      }
      const lr = linkRow(plotId);
      if (lr) box.append(lr);
      const p = S.biz && S.biz.plots && S.biz.plots[plotId];
      if (!p) { box.append(el('p', 'pane__empty', plotId === 'control' ? '中央大厅是调度与归档，不单独承接业务。' : '这块地还没有业务定义。')); return; }
      box.append(el('p', 'pane__lead', p.duty));
      if (p.group) box.append(el('p', 'pane__sub', `归属群：${p.group}`));
      const can = el('div', 'chips');
      can.append(el('span', 'chips__label', '能接'));
      for (const t of p.can_do || []) can.append(el('span', 'chip', t));
      box.append(can);
      if ((p.not_do || []).length) {
        const no = el('div', 'chips chips--no');
        no.append(el('span', 'chips__label', '不接'));
        for (const t of p.not_do) no.append(el('span', 'chip chip--no', t));
        box.append(no);
      }
    },
  },
  weekTodo: {
    need: 'todo',
    draw(box, plotId, c) {
      const vs = sortTodos(c.todo.items, { week: true });
      box.append(el('h4', 'pane__h', `本周待办（${vs.length}）`));
      if (!vs.length) box.append(el('p', 'pane__empty', '本周没有待办。'));
      for (const v of vs) box.append(todoRow(v, plotId));
    },
  },
  weekCron: {
    need: 'cron',
    draw(box, plotId, c) {
      const vs = sortCrons(c.cron.jobs, { week: true });
      box.append(el('h4', 'pane__h', `本周 cron（${vs.length}）`));
      if (!vs.length) box.append(el('p', 'pane__empty', '本周没有要跑的 cron。'));
      for (const v of vs) box.append(cronRow(v));
    },
  },
  allTodo: {
    need: 'todo',
    draw(box, plotId, c) {
      const vs = sortTodos(c.todo.items);
      box.append(el('h4', 'pane__h', `全部待办（${vs.length}）`));
      if (!vs.length) box.append(el('p', 'pane__empty', '这块地没有未完成待办。'));
      for (const v of vs) box.append(todoRow(v, plotId));
    },
  },
  allCron: {
    need: 'cron',
    draw(box, plotId, c) {
      const vs = sortCrons(c.cron.jobs);
      box.append(el('h4', 'pane__h', `全部 cron（${vs.length}）`));
      if (!vs.length) box.append(el('p', 'pane__empty', '这块地没有启用中的 cron。'));
      for (const v of vs) box.append(cronRow(v));
    },
  },
  agent: {
    need: 'agents',
    // P5：只讲现在——运行中：已跑多久 + 当前在做什么；没进程：当前没有运行中的会话。不列历史会话 / 日志文件
    draw(box, plotId, c) {
      const a = ((c.agents && c.agents.agents) || []).find((x) => x.id === plotId);
      if (!a) { box.append(el('p', 'pane__empty', '没有探测结果。')); return; }
      const st = agentState(a);
      const head = el('div', 'agent');
      head.append(el('span', 'agent__dot is-' + st));
      const main = el('div', 'agent__main');
      const title = el('div', 'agent__status');
      title.append(document.createTextNode(a.name + ' '), el('span', 'agent__state is-' + st, STATUS_LABEL[st]));
      main.append(title);
      main.append(el('div', 'agent__meta', `版本 ${a.version || '未知'}`));
      head.append(main);
      box.append(head);
      const now = el('div', 'agent__now');
      if (st === 'running') {
        const bits = ['运行中'];
        if (a.startedAt) bits.push('已跑 ' + spanText(Date.now() - Date.parse(a.startedAt)));
        if (a.cpuPct != null) bits.push(`CPU ${a.cpuPct}%`);
        if (a.procs > 1) bits.push(`${a.procs} 个进程`);
        now.append(el('div', 'agent__line', bits.join(' · ')));
        const doing = el('div', 'agent__doing');
        doing.append(el('span', 'agent__k', '当前在做'));
        doing.append(el('span', 'agent__v', a.doing || '最近 30 分钟没有新输出'));
        now.append(doing);
        if (a.doing && a.doingAt) now.append(el('div', 'agent__ago', '输出于 ' + agoText(Date.parse(a.doingAt))));
      } else if (st === 'idle') {
        now.append(el('p', 'pane__empty', a.note || '已安装 · 当前空闲'));
      } else {
        now.append(el('p', 'pane__empty', '本机没有检测到安装'));
      }
      box.append(now);
    },
  },
};

const TABS = {
  duty: ['duty'],
  now: ['weekTodo', 'weekCron'],
  work: ['allTodo', 'allCron'],
  agentWork: ['agent'],
};
const PANE_OF = { duty: 'paneDuty', now: 'paneNow', work: 'paneWork' };

function ready(key, plotId, c) {
  const need = BLOCKS[key].need;
  if (need === 'biz') return AGENT_IDS.has(plotId) || !!S.biz;   // 外协先出职责（版本号到货后再重绘一次）
  return !!(c && c[need]);
}

function paint(box, key, plotId, c, animate) {
  box.replaceChildren();
  const need = BLOCKS[key].need;
  if (ready(key, plotId, c)) BLOCKS[key].draw(box, plotId, c);
  else if (need !== 'biz' && c && c.err[need]) box.append(el('p', 'pane__empty', '数据加载失败（本地服务未启动？）'));
  else skeleton(box, key === 'duty' ? 3 : 4);
  box.dataset.state = ready(key, plotId, c) ? 'ready' : 'skel';
  if (animate) { box.classList.remove('is-in'); void box.offsetWidth; box.classList.add('is-in'); }
}

function blocksOf(tab, plotId) { return AGENT_IDS.has(plotId) && tab === 'work' ? TABS.agentWork : TABS[tab]; }

// 整页重建（切地块 / 切页签）：同步完成，旧内容立刻消失
function render() {
  const plotId = S.plot;
  for (const [tab, id] of Object.entries(PANE_OF)) $(id).hidden = tab !== S.tab;
  const pane = $(PANE_OF[S.tab]);
  pane.replaceChildren();
  if (!plotId) return;
  const c = cache.get(plotId);
  for (const key of blocksOf(S.tab, plotId)) {
    const box = el('section', 'blk');
    box.dataset.k = key;
    pane.append(box);
    paint(box, key, plotId, c, true);
  }
}

// 某份数据到了：只重绘还在等它（或要刷新）的块
function repaint(plotId, part) {
  if (plotId !== S.plot) return;
  const c = cache.get(plotId);
  const pane = $(PANE_OF[S.tab]);
  for (const box of pane.querySelectorAll('section.blk')) {
    const key = box.dataset.k;
    if (BLOCKS[key].need !== part && !(part === 'agents' && key === 'duty')) continue;   // 外协职责页等 agents 数据到了再画（要显示版本号）
    paint(box, key, plotId, c, box.dataset.state !== 'ready');
  }
}

let nowTab = null;   // 「此刻」「待办」两个按钮：外协块直接摘出 DOM（只留职责），业务块再插回
function syncTabs(plotId) {
  const agent = AGENT_IDS.has(plotId);
  if (agent && (S.tab === 'now' || S.tab === 'work')) S.tab = 'duty';
  const tabs = $('cardTabs');
  const nowBtn = nowTab || tabs.querySelector('button[data-tab="now"]');
  const workBtn = tabs.querySelector('button[data-tab="work"]');
  nowTab = nowBtn;
  if (agent) {
    nowBtn.remove();
    workBtn.hidden = true;            // 外协只留职责页
  } else {
    workBtn.hidden = false;
    if (!nowBtn.isConnected) tabs.insertBefore(nowBtn, workBtn);
  }
  tabs.querySelectorAll('button').forEach((b) => {
    b.setAttribute('aria-pressed', String(b.dataset.tab === S.tab && !b.hidden));
  });
}

function schedulePrefetch(plotId) {
  clearTimeout(prefetchTimer);
  if (!plotId) return;
  prefetchTimer = setTimeout(() => {
    if (S.plot !== plotId) return;
    const nb = (window.__park && window.__park.neighborsOf && window.__park.neighborsOf(plotId)) || [];
    for (const id of nb.slice(0, 2)) plotData(id);
    S.prefetched = { from: plotId, ids: nb.slice(0, 2), at: Date.now() };
  }, 1500);
}

window.__panel = {
  get S() { return S; }, cache, setPanelPlot: (x) => setPanelPlot(x),
  plotData: (id, o) => plotData(id, o), loadBiz,
};

export function setPanelPlot(plotId) {
  S.plot = plotId;
  if (!plotId) { clearTimeout(prefetchTimer); render(); return; }
  syncTabs(plotId);
  if (!links) loadLinks().then(() => repaint(plotId, 'biz'));
  if (!S.biz) loadBiz().then(() => repaint(plotId, 'biz')).catch(() => {});
  plotData(plotId, { onPart: repaint });
  render();
  schedulePrefetch(plotId);
}

// 顶部「云表」按钮 → 浮层列出全部入口；点外面 / Esc 关
function initCloudPop() {
  const btn = $('btnCloud'), pop = $('cloudPop');
  if (!btn || !pop) return;
  const fill = () => {
    const list = $('cloudList');
    list.replaceChildren();
    for (const r of POP_ROWS) {
      const btns = r.keys.map(([k, label]) => linkBtn(k, label)).filter(Boolean);
      if (!btns.length) continue;
      const row = el('div', 'cloudpop__row');
      row.append(el('span', 'cloudpop__name', r.name));
      const acts = el('div', 'cloudpop__acts');
      acts.append(...btns);
      row.append(acts);
      list.append(row);
    }
    if (!list.childElementCount) list.append(el('p', 'pane__empty', '入口加载失败'));
  };
  const close = () => { pop.hidden = true; btn.setAttribute('aria-expanded', 'false'); };
  btn.addEventListener('click', async (e) => {
    e.stopPropagation();
    if (!pop.hidden) { close(); return; }
    await loadLinks();
    fill();
    pop.hidden = false;
    btn.setAttribute('aria-expanded', 'true');
  });
  document.addEventListener('click', (e) => { if (!pop.hidden && !pop.contains(e.target)) close(); });
  window.addEventListener('keydown', (e) => { if (e.key === 'Escape') close(); });
}

export function initPanel() {
  initCloudPop();
  loadLinks();
  const tabs = $('cardTabs');
  if (tabs) tabs.addEventListener('click', (e) => {
    const b = e.target.closest('button[data-tab]');
    if (!b) return;
    S.tab = b.dataset.tab;
    tabs.querySelectorAll('button').forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
    if (S.plot) render();
  });
  // 报告浮层
  const wrap = $('reportWrap');
  if (wrap) {
    $('reportClose').addEventListener('click', () => { wrap.hidden = true; });
    window.__panelShowReport = async (id, name) => {
      $('reportTitle').textContent = name || '任务报告';
      $('reportBody').textContent = '加载中…';
      wrap.hidden = false;
      try {
        const r = await jget('/api/cron/report?id=' + encodeURIComponent(id));
        $('reportBody').textContent = (r && r.content) || '没有报表';
        $('reportMeta').textContent = r && r.ran_at ? '运行于 ' + new Date(r.ran_at).toLocaleString('zh-CN') : '';
      } catch (e) { $('reportBody').textContent = '读取失败：' + e.message; }
    };
  }
  // 30 秒静默刷新（面板打开时，不闪骨架）
  setInterval(() => {
    if (S.plot && !$('card').hidden) plotData(S.plot, { force: true, onPart: repaint });
  }, 30000);
}
