// cron 数据聚合（只读）：任务清单 + 最近运行 + 报表原文
'use strict';
const fs = require('fs');
const path = require('path');
const { execFile } = require('child_process');

const HOME = path.resolve(__dirname, '..');
const HERMES = path.resolve(HOME, '..');
const JOBS = path.join(HERMES, 'cron', 'jobs.json');
const OUTPUT = path.join(HERMES, 'cron', 'output');

// 群 chat_id → 地块 id
const CHAT_PLOT = {
  oc_9f18480e1e4ea70504ae2f8954f7b7fe: 'control',
  oc_91703634e58ed8f3c258e7345f0c5354: 'learn',
  oc_c73e1da1943d50e50b2645b8bb391471: 'daily',
  oc_99819e11b0dfda58e81193cece50700f: 'rainbow',
  oc_297f2b68127d9f96411e7d9ceb7bfb1b: 'family',
  oc_58468b4626a37ec8dd47038dc4d56e77: 'inventor',
  oc_92aabb918636f083f664e197e82d6279: 'clock',
  oc_ddea1b31f5c72999e3b9625eb5273226: 'vault',
  oc_adbdc29db37955177a603586f065f819: 'press',
};

// 名字关键词兜底
const NAME_HINT = [
  [/文献|论文|arXiv|深度学习|课程|作业|毕设|组会|PPT|LaTeX|考研复习/i, 'learn'],
  [/服务器|域名|备份|中转|盈利|agent|github|巡检|到期|监控|上游|额度|隧道/i, 'vault'],
  [/彩虹|考公|国考|省考|求职|招聘|烟草|银行/i, 'rainbow'],
  [/家人|爸爸|妈妈|弟弟|体检|医院|就医/i, 'family'],
  [/情报|新闻|资讯|AI|雷达|要闻|工具库/i, 'press'],
  [/晨报|晚报|提醒|待办|签到|修复|组会提醒|研习室/i, 'clock'],
  [/娱乐|B站|抖音|博主|点子|表情/i, 'inventor'],
  [/购物|书|电影|影视|跑步|健身|天气|行程|票/i, 'daily'],
];

function loadJobs() {
  const raw = JSON.parse(fs.readFileSync(JOBS, 'utf8'));
  const list = Array.isArray(raw.jobs) ? raw.jobs : Object.values(raw.jobs || {});
  return list;
}

// Hermes 维护的显式映射（job_id → 地块），优先于推导；按 mtime 热加载
const PLOT_MAP = path.join(HOME, 'cache', 'plot_map.json');
const PLOT_KEYS = new Set(['control', 'learn', 'daily', 'family', 'rainbow', 'vault', 'press', 'clock', 'inventor']);
let plotMap = { mtime: -1, map: {} };
function loadPlotMap() {
  let mt = 0;
  try { mt = fs.statSync(PLOT_MAP).mtimeMs; } catch (e) { return {}; }
  if (mt !== plotMap.mtime) {
    try { plotMap = { mtime: mt, map: JSON.parse(fs.readFileSync(PLOT_MAP, 'utf8')) || {} }; }
    catch (e) { /* 文件写到一半：沿用上一版 */ }
  }
  return plotMap.map;
}

function plotOf(job) {
  const hit = loadPlotMap()[job.id];
  if (hit && PLOT_KEYS.has(hit.plot)) return { plot: hit.plot, why: 'map' };
  const name = job.name || '';
  const d = String(job.deliver || '');
  const m = /oc_[0-9a-f]{32}/.exec(d);
  const byDeliver = m && CHAT_PLOT[m[0]] ? CHAT_PLOT[m[0]] : null;
  let byName = null;
  for (const [re, id] of NAME_HINT) if (re.test(name)) { byName = id; break; }
  // 「通知待办」是全局收件箱，很多任务都投到那儿；名称能更准确指认归属时以名称为准
  if (byName && (!byDeliver || byDeliver === 'clock')) return { plot: byName, why: 'name' };
  if (byDeliver) return { plot: byDeliver, why: 'deliver' };
  if (byName) return { plot: byName, why: 'name' };
  return { plot: 'control', why: 'default' };
}

function kindOf(schedule) {
  const s = (schedule && typeof schedule === 'object')
    ? String(schedule.expr || schedule.display || schedule.kind || '')
    : String(schedule || '');
  if (/^\*\/\d+/.test(s)) return '每 N 分钟';
  if (/^once|^\d{4}-\d{2}-\d{2}/.test(s)) return '一次性';
  if (/every\s+(\d+)m/i.test(s)) return '每 N 分钟';
  if (/every\s+(\d+)h/i.test(s)) return '每 N 小时';
  if (/每天|daily|^\S+ \S+ \* \* \*$/.test(s)) return '每天';
  if (/每周|weekly|\* \* \S+$/.test(s)) return '每周';
  if (/每月|monthly/.test(s)) return '每月';
  return s || '未知';
}

// 重复类型 + 人话时间：daily 每天 HH:MM / interval 每 N 分钟 / weekly / monthly / once
const WD = '日一二三四五六';
const pad = (n) => String(n).padStart(2, '0');
function recurOf(schedule) {
  const s = schedule && typeof schedule === 'object' ? schedule : { expr: String(schedule || '') };
  if (s.kind === 'once' || s.run_at) {
    const t = s.run_at ? new Date(s.run_at) : null;
    return { recur: 'once', label: t ? `${t.getMonth() + 1}/${t.getDate()} ${pad(t.getHours())}:${pad(t.getMinutes())}` : '一次性' };
  }
  const f = String(s.expr || '').trim().split(/\s+/);
  if (f.length !== 5) return { recur: 'other', label: s.display || s.expr || '' };
  const [mi, hr, dom, mon, dow] = f;
  const iv = /^\*\/(\d+)$/.exec(mi);
  if (iv && hr === '*') return { recur: 'interval', label: `每 ${iv[1]} 分钟` };
  const hiv = /^\*\/(\d+)$/.exec(hr);
  if (hiv && /^\d+$/.test(mi)) return { recur: 'interval', label: `每 ${hiv[1]} 小时` };
  const hm = /^\d+$/.test(mi) ? hr.split(',').map((h) => `${pad(h)}:${pad(mi)}`).join('/') : `${hr}:${mi}`;
  if (dom === '*' && mon === '*' && dow === '*') return { recur: 'daily', label: `每天 ${hm}` };
  if (dom === '*' && mon === '*') return { recur: 'weekly', label: `每周${dow.split(',').map((d) => WD[Number(d) % 7] || d).join('、')} ${hm}` };
  return { recur: 'monthly', label: `${mon === '*' ? '每月' : mon + ' 月'} ${dom} 日 ${hm}` };
}

// 近 N 次运行（走 CLI，不需要 sqlite 依赖）。CLI 一次 ~13s，绝不能同步阻塞服务：
// 永远立即返回缓存，过期则后台异步刷新；冷启动时缓存为空，summary() 退回 jobs.json 里的 last_run_at / last_status
let runsCache = { at: 0, limit: 0, rows: [], busy: false };
function refreshRuns(limit) {
  if (runsCache.busy) return;
  runsCache.busy = true;
  const done = (txt) => {
    const rows = [];
    for (const line of String(txt || '').split(/\r?\n/)) {
      const m = /^(\S+)\s+(\S+)\s+job=(\S+)\s+source=\S+\s+(\S+)/.exec(line.trim());
      if (m) rows.push({ exec: m[1], status: m[2], job: m[3], at: m[4] });
    }
    if (rows.length || !runsCache.rows.length) runsCache.rows = rows;
    runsCache.at = Date.now(); runsCache.limit = limit; runsCache.busy = false;
  };
  const args = ['cron', 'runs', '--limit', String(limit)];
  execFile('hermes', args, { encoding: 'utf8', timeout: 30000, windowsHide: true }, (err, so) => {
    if (!err) return done(so);
    execFile('hermes.cmd', args, { encoding: 'utf8', timeout: 30000, windowsHide: true, shell: true }, (e2, so2) => done(e2 ? '' : so2));
  });
}
function recentRuns(limit = 400) {
  if (Date.now() - runsCache.at > 30000 || runsCache.limit < limit) refreshRuns(Math.max(limit, runsCache.limit));
  return runsCache.rows;
}
refreshRuns(600);

function outputDir(jobId) { return path.join(OUTPUT, jobId); }

function listOutputs(jobId) {
  const d = outputDir(jobId);
  try {
    return fs.readdirSync(d).filter((f) => f.endsWith('.md'))
      .map((f) => ({ file: path.join(d, f), name: f, mtime: fs.statSync(path.join(d, f)).mtimeMs }))
      .sort((a, b) => b.mtime - a.mtime);
  } catch (e) { return []; }
}

function readReport(jobId, n = 1) {
  const files = listOutputs(jobId);
  const f = files[n - 1] || files[0];
  if (!f) return null;
  const txt = fs.readFileSync(f.file, 'utf8');
  return { content: txt, file: path.relative(HERMES, f.file), ran_at: new Date(f.mtime).toISOString() };
}

function summary() {
  const jobs = loadJobs();
  const runs = recentRuns(400);
  const byJob = new Map();
  for (const r of runs) {
    const arr = byJob.get(r.job) || [];
    arr.push(r);
    byJob.set(r.job, arr);
  }
  const out = jobs.map((j) => {
    const { plot, why } = plotOf(j);
    const rs = byJob.get(j.id) || [];
    const last = rs[0] || null;
    const { recur, label } = recurOf(j.schedule);
    return {
      id: j.id,
      name: j.name,
      plot,
      plotWhy: why,
      kind: kindOf(j.schedule),
      recur,
      timeLabel: label,
      schedule: (j.schedule && (j.schedule.display || j.schedule.expr)) || j.schedule_display || '',
      enabled: j.enabled !== false,
      state: j.state || '',
      nextRun: j.next_run_at || null,
      lastRun: (last && last.at) || j.last_run_at || null,
      lastStatus: (last && last.status) || j.last_status || null,
      runs: rs.length,
      hasReport: listOutputs(j.id).length > 0,
    };
  });
  const counts = { total: out.length, enabled: out.filter((x) => x.enabled).length, failed: out.filter((x) => x.lastStatus && x.lastStatus !== 'completed' && x.lastStatus !== 'ok').length };
  return { jobs: out, counts, fetchedAt: new Date().toISOString() };
}

module.exports = { summary, readReport, listOutputs, recentRuns, plotOf, CHAT_PLOT };
