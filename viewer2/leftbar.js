// 左栏总览：本周待办 与 本周 cron 分两区（各自标题 + 各自排序），带地块徽标，点条目聚焦地块
// 排序 / 口径与右栏共用 order.js
import { sortTodos, sortCrons } from './order.js?v=20261031-p5';

const PLOT_SHORT = { control: '中央', learn: '学习', daily: '日常', family: '家人', vault: '资产', clock: '待办', press: '新闻', inventor: '奇想', rainbow: '彩虹', clawd: 'Claude', pi: 'Pi', codex: 'Codex' };
const PLOT_COLOR = { control: '#6C7A89', learn: '#4F7FB5', daily: '#7BA05B', family: '#C08A4E', vault: '#8A6FB0', clock: '#C25A4E', press: '#4E9AA8', inventor: '#C79A3C', rainbow: '#C9779A', clawd: '#D2694A', pi: '#6FA8C2', codex: '#6F7BFF' };

let D = { todo: null, cron: null, at: 0, open: true, active: null };
const el = (t, c, x) => { const n = document.createElement(t); if (c) n.className = c; if (x != null) n.textContent = x; return n; };
const $ = (id) => document.getElementById(id);

function badge(plot) {
  const b = el('span', 'badge', PLOT_SHORT[plot] || plot);
  b.style.background = (PLOT_COLOR[plot] || '#888') + '22';
  b.style.color = PLOT_COLOR[plot] || '#666';
  return b;
}

function render() {
  const list = $('lbList');
  if (!list) return;
  list.replaceChildren();
  const todos = sortTodos((D.todo && D.todo.items) || [], { week: true });
  const crons = sortCrons((D.cron && D.cron.jobs) || [], { week: true });
  $('lbTodoCount').textContent = D.todo ? todos.length : '–';
  $('lbCronCount').textContent = D.cron ? crons.length : '–';
  if ($('lbFabN')) $('lbFabN').textContent = D.todo || D.cron ? String(todos.length + crons.length) : '';

  // ── 待办区 ──
  const tSec = el('section', 'lb__sec');
  tSec.append(el('h3', 'lb__h', `本周待办（${todos.length}）`));
  if (!todos.length) tSec.append(el('p', 'lb__empty', D.todo ? '本周没有待办' : '加载中…'));
  for (const v of todos) {
    const t = v.item;
    const key = 'todo:' + t.id;
    const row = el('div', 'lb__item' + (v.bucket === 0 ? ' is-overdue' : '') + (D.active === key ? ' is-active' : ''));
    row.dataset.key = key;
    row.append(badge(t.plot));
    const main = el('div', 'lb__main');
    const title = el('div', 'lb__title');
    if (v.bucket === 0) title.append(el('span', 'dot dot--bad'));
    title.append(document.createTextNode(t.title));
    main.append(title);
    const meta = el('div', 'lb__meta');
    if (v.bucket === 0) meta.append(el('span', 'tag tag--bad', `逾期 ${v.overdue} 天`));
    meta.append(document.createTextNode(t.due ? t.due.slice(5) + (v.diff === 0 ? ' 今天' : v.diff === 1 ? ' 明天' : '') : '无日期'));
    main.append(meta);
    row.append(main);
    const done = el('button', 'lb__done'); done.type = 'button'; done.textContent = '✓'; done.title = '标为已完成';
    done.addEventListener('click', async (e) => {
      e.stopPropagation();
      done.disabled = true;
      try {
        const r = await fetch('/api/todo', { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ owner: t.owner, id: t.id, fields: { status: '已完成' } }) });
        if (!r.ok) throw new Error(String(r.status));
        if (window.__panel) window.__panel.cache.delete(t.plot);
        await refresh(true);
      } catch (err) { done.disabled = false; }
    });
    row.append(done);
    row.addEventListener('click', () => pick(row, key, t.plot));
    tSec.append(row);
  }
  list.append(tSec);

  // ── cron 区 ──
  const cSec = el('section', 'lb__sec');
  cSec.append(el('h3', 'lb__h', `本周 cron（${crons.length}）`));
  if (!crons.length) cSec.append(el('p', 'lb__empty', D.cron ? '本周没有要跑的 cron' : '加载中…'));
  for (const v of crons) {
    const j = v.item;
    const key = 'cron:' + j.id;
    const row = el('div', 'lb__item' + (D.active === key ? ' is-active' : ''));
    row.dataset.key = key;
    row.title = v.tip;
    row.append(badge(j.plot));
    const main = el('div', 'lb__main');
    main.append(el('div', 'lb__title', j.name));
    const meta = el('div', 'lb__meta');
    if (v.bucket === 0) meta.append(el('span', 'tag tag--bad', `逾期 ${v.overdue} 天`));
    meta.append(document.createTextNode(v.meta));
    main.append(meta);
    row.append(main, el('span', 'lb__dot is-' + v.color));
    row.addEventListener('click', () => pick(row, key, j.plot));
    cSec.append(row);
  }
  list.append(cSec);
}

// 先切高亮（右栏骨架在 focusPlot 内同步出现），再飞镜头
function pick(row, key, plot) {
  D.active = key;
  for (const r of $('lbList').querySelectorAll('.lb__item.is-active')) r.classList.remove('is-active');
  row.classList.add('is-active');
  if (window.__park && window.__park.focusPlot) window.__park.focusPlot(plot);
}

async function refresh(force) {
  if (!force && Date.now() - D.at < 30000) return;
  try {
    const [todo, cron] = await Promise.all([
      fetch('/api/todo?owner=all&scope=open', { cache: 'no-store' }).then((r) => r.json()),
      fetch('/api/cron', { cache: 'no-store' }).then((r) => r.json()),
    ]);
    D.todo = todo; D.cron = cron; D.at = Date.now();
    render();
  } catch (e) { /* 静默，页面其它部分不受影响 */ }
}

window.__leftbar = { refresh: (f) => refresh(f), get D() { return D; } };

export function initLeftBar() {
  const bar = $('leftbar');
  if (!bar) return;
  // P5：折叠后栏整个收起，左边缘出现悬浮球（带本周条目数），点球展开
  const fab = $('lbFab');
  const setOpen = (open) => {
    D.open = open;
    bar.classList.toggle('is-collapsed', !open);
    bar.inert = !open;
    if (fab) fab.hidden = open;
    (open ? $('lbToggle') : fab)?.focus({ preventScroll: true });
  };
  $('lbToggle').addEventListener('click', () => setOpen(false));
  if (fab) fab.addEventListener('click', () => setOpen(true));
  render();
  refresh(true);
  setInterval(() => refresh(false), 30000);
}
