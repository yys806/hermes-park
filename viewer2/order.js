// 排序与状态口径（右栏 panel.js 与左栏 leftbar.js 共用，只此一套）
// 排序：逾期 → 今天 → 明天 → 本周内 → 更晚 → 无日期（垫底）；待办与 cron 各自排，不混排
// cron 三色：最近一次失败 = bad（红）；今天跑完 = ok（绿）；今天没跑 = idle（灰）

const pad = (n) => String(n).padStart(2, '0');
export const dayKey = (d) => { const t = new Date(d); return `${t.getFullYear()}-${pad(t.getMonth() + 1)}-${pad(t.getDate())}`; };
const startOfDay = (d) => { const t = new Date(d); t.setHours(0, 0, 0, 0); return t; };

// 相对今天的天数（负 = 逾期）；没日期返回 null
export function dayDiff(d, now = Date.now()) {
  if (!d) return null;
  const t = typeof d === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(d) ? new Date(d + 'T00:00:00') : new Date(d);
  if (Number.isNaN(+t)) return null;
  return Math.round((startOfDay(t) - startOfDay(now)) / 864e5);
}

export const BUCKET_NAME = ['逾期', '今天', '明天', '本周', '更晚', '无日期'];
export function bucketOf(diff) {
  if (diff == null) return 5;
  if (diff < 0) return 0;
  if (diff === 0) return 1;
  if (diff === 1) return 2;
  if (diff <= 6) return 3;
  return 4;
}

const isOk = (s) => s === 'ok' || s === 'completed' || s === 'success';

export function agoText(ms, now = Date.now()) {
  const m = Math.max(0, Math.round((now - ms) / 60000));
  if (m < 120) return `${m} 分钟前`;
  if (m < 48 * 60) return `${Math.round(m / 60)} 小时前`;
  return `${Math.round(m / 1440)} 天前`;
}

// ── 待办 ──
export function todoView(t, now = Date.now()) {
  const diff = dayDiff(t.due, now);
  const bucket = bucketOf(diff);
  return { item: t, diff, bucket, minute: 0, name: t.title || '', overdue: bucket === 0 ? -diff : 0 };
}

// ── cron ──
const firstMinute = (label) => { const m = /(\d{1,2}):(\d{2})/.exec(label || ''); return m ? Number(m[1]) * 60 + Number(m[2]) : 0; };

export function cronView(j, now = Date.now()) {
  const today = dayKey(now);
  const lastMs = j.lastRun ? Date.parse(j.lastRun) : 0;
  const ranToday = !!lastMs && dayKey(lastMs) === today;
  const failed = !!j.lastStatus && !isOk(j.lastStatus);
  const color = failed ? 'bad' : ranToday ? 'ok' : 'idle';
  const repeating = j.recur === 'daily' || j.recur === 'interval';
  let diff = null, minute = 0;
  if (repeating) { diff = j.enabled ? 0 : null; minute = j.recur === 'daily' ? firstMinute(j.timeLabel) : 0; }
  else {
    // 一次性 / 每周 / 每月：按下次运行日；已停用但今天刚跑完的一次性按今天计
    const at = j.enabled && j.nextRun ? Date.parse(j.nextRun) : ranToday ? lastMs : 0;
    if (at) { diff = dayDiff(at, now); const t = new Date(at); minute = t.getHours() * 60 + t.getMinutes(); }
  }
  // 一次性已错过且没跑：逾期
  const bucket = bucketOf(diff);
  let meta;
  if (repeating) meta = `${j.timeLabel} · ${ranToday ? '今天已跑' : '今天未跑'}`;
  else if (j.recur === 'once') meta = `${j.timeLabel}${ranToday ? ' · 今天已跑' : ''}`;
  else {
    const nx = j.nextRun ? new Date(j.nextRun) : null;
    meta = `${j.timeLabel || j.schedule}${nx ? ` · 下次 ${nx.getMonth() + 1}/${nx.getDate()} ${pad(nx.getHours())}:${pad(nx.getMinutes())}` : ''}`;
  }
  const tip = lastMs ? `上次：${agoText(lastMs, now)} · ${failed ? '失败' : '成功'}` : '上次：还没跑过';
  return { item: j, diff, bucket, minute, name: j.name || '', overdue: bucket === 0 ? -diff : 0, color, ranToday, failed, repeating, meta, tip };
}

// 共用比较器：桶 → 天数 → 当天时刻 → 名称
export function compareView(a, b) {
  return (a.bucket - b.bucket) || ((a.diff ?? 0) - (b.diff ?? 0)) || (a.minute - b.minute) || a.name.localeCompare(b.name, 'zh-CN');
}

// 本周口径（D4）：逾期 + 今天起 7 天内 + 无日期（垫底）
export const inWeek = (v) => v.bucket <= 3 || v.bucket === 5;

export function sortTodos(items, { week = false, now = Date.now() } = {}) {
  let vs = (items || []).map((t) => todoView(t, now));
  if (week) vs = vs.filter(inWeek);
  return vs.sort(compareView);
}

// cron 只列启用中的 + 今天刚跑完的；同名同时刻只留一条（G8：每天重复的不铺七份）
export function sortCrons(jobs, { week = false, now = Date.now() } = {}) {
  const seen = new Map();
  for (const j of jobs || []) {
    const v = cronView(j, now);
    if (!j.enabled && !v.ranToday) continue;
    if (v.diff == null) continue;
    if (week && !(v.bucket <= 3)) continue;
    const key = `${j.name}|${j.timeLabel}`;
    const prev = seen.get(key);
    // 合并时保留更需要注意的那条：红 > 灰 > 绿
    const rank = { bad: 0, idle: 1, ok: 2 };
    if (!prev || rank[v.color] < rank[prev.color]) seen.set(key, v);
  }
  return [...seen.values()].sort(compareView);
}
