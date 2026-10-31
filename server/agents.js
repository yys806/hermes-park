// 外协三块（claude / pi / codex）真实状态探测（只读：列进程 + 读版本号 + 看最近会话日志尾部，不执行任何 agent 任务）
// P5：只讲「现在」——有进程 = 运行中（已跑多久 + 当前在做什么），没进程 = 空闲，装都没装 = 未安装；不再列历史文件
'use strict';
const fs = require('fs');
const path = require('path');
const os = require('os');
const { execFile } = require('child_process');

const U = os.homedir();
const NOW_MS = 30 * 60 * 1000;
const ACTIVE_MS = 10 * 60 * 1000;   // 10 分钟内有新输出 = 在干活      // 会话日志 30 分钟内有写入，才当作「当前在做什么」
const TAIL_BYTES = 96 * 1024;       // 只读日志末尾这么多字节
const VERSION_TTL = 10 * 60 * 1000;

const AGENTS = [
  {
    id: 'clawd', name: 'Claude Code',
    proc: (p) => /^claude(\.exe)?$/i.test(p.name) || /@anthropic-ai[\\/]claude-code|claude-code[\\/]cli/i.test(p.cmd),
    version: { cmd: 'claude', args: ['--version'] },
    install: [path.join(U, '.claude')],
    logs: { dir: path.join(U, '.claude', 'projects'), match: /\.jsonl$/i },
  },
  {
    id: 'pi', name: 'Pi',
    proc: (p) => /^pi(\.exe)?$/i.test(p.name) || /pi-coding-agent|[\\/]\.pi[\\/]agent[\\/]bin|(^|[\\/\s"])pi(\.cmd|\.exe)?("|\s|$)/i.test(p.cmd),
    version: { cmd: `"${path.join(U, '.pi', 'agent', 'bin', 'pi.cmd')}"`, args: ['--version'] },
    install: [path.join(U, '.pi', 'agent', 'bin')],
    logs: { dir: path.join(U, '.pi', 'agent', 'sessions'), match: /\.jsonl$/i },
  },
  {
    id: 'codex', name: 'ChatGPT 桌面端（Codex 模式）',
    proc: (p) => /^chatgpt\.exe$/i.test(p.name),
    // Codex 真正跑任务时会拉起执行器：node_repl / codex-command-runner / codex-windows-sandbox-service
    work: (p) => /^(node_repl|codex-command-runner|codex-windows-sandbox)/i.test(p.name),
    version: { exe: 'ChatGPT.exe', appx: 'OpenAI.Codex' },
    install: [path.join(U, '.codex')],
    logs: { dir: path.join(U, '.codex', 'sessions'), match: /\.jsonl$/i },
  },
];

const ps = (script, timeout = 15000) => new Promise((resolve) => {
  execFile('powershell.exe', ['-NoProfile', '-NonInteractive', '-Command', script], { timeout, maxBuffer: 32 * 1024 * 1024, windowsHide: true },
    (err, so) => resolve(err ? null : String(so || '')));
});

// 进程表：PowerShell CIM（带命令行与启动时间，能认出 node 托管的 claude / pi），15 秒缓存
let procCache = { at: 0, rows: null };
async function listProcs() {
  if (procCache.rows && Date.now() - procCache.at < 15000) return procCache.rows;
  const so = await ps("Get-CimInstance Win32_Process | Select-Object ProcessId,Name,CommandLine,ExecutablePath,@{n='Start';e={if($_.CreationDate){$_.CreationDate.ToUniversalTime().ToString('o')}}} | ConvertTo-Json -Compress");
  let rows = null;
  if (so != null) {
    try {
      const j = JSON.parse(so || '[]');
      rows = (Array.isArray(j) ? j : [j]).map((x) => ({ pid: x.ProcessId || null, name: String(x.Name || ''), cmd: String(x.CommandLine || ''), exe: String(x.ExecutablePath || ''), start: x.Start ? Date.parse(x.Start) : null }));
    } catch (e) { rows = null; }
  }
  if (rows) procCache = { at: Date.now(), rows };
  return rows || procCache.rows || [];
}

// 版本号：命令行工具跑 --version；ChatGPT 读程序文件版本（进程在就读它的 exe，否则读 Appx 包版本）。读不到 = null（前端写「未知」）
const verCache = new Map();
function runVersion(cmd, args) {
  return new Promise((resolve) => {
    execFile(cmd, args, { timeout: 20000, windowsHide: true, shell: true }, (err, so) => {
      const m = !err && /\d+(\.\d+)+/.exec(String(so || ''));
      resolve(m ? m[0] : null);
    });
  });
}
async function fileVersion(spec, procs) {
  const hit = procs.find((p) => p.name.toLowerCase() === spec.exe.toLowerCase() && p.exe);
  // 商店版装在 WindowsApps\<包名>_<版本>_x64__…\，路径里就是应用版本（exe 自身的 ProductVersion 是 Chromium 内核版本，不用）
  const m = hit && /_(\d+(\.\d+)+)_/.exec(hit.exe);
  if (m) return m[1];
  const q = (s) => "'" + s.replace(/'/g, "''") + "'";
  const so = await ps(`$p = Get-AppxPackage -Name ${q(spec.appx)} | Select-Object -First 1; if ($p) { $p.Version } elseif (${hit ? 1 : 0}) { (Get-Item -LiteralPath ${q(hit ? hit.exe : 'x')}).VersionInfo.FileVersion }`);
  const v = so && /\d+(\.\d+)+/.exec(so);
  return v ? v[0] : null;
}
async function versionOf(a, procs) {
  const c = verCache.get(a.id);
  if (c && Date.now() - c.at < VERSION_TTL) return c.v;
  const v = a.version.exe ? await fileVersion(a.version, procs) : await runVersion(a.version.cmd, a.version.args);
  verCache.set(a.id, { at: Date.now(), v });
  return v;
}

// 最新的一份会话日志（深度 ≤ 4，最多扫 6000 项）
function newestLog(spec) {
  let best = null, budget = 6000;
  const walk = (d, depth) => {
    let ents;
    try { ents = fs.readdirSync(d, { withFileTypes: true }); } catch (e) { return; }
    for (const e of ents) {
      if (--budget < 0) return;
      const fp = path.join(d, e.name);
      if (e.isDirectory()) { if (depth < 4) walk(fp, depth + 1); continue; }
      if (!spec.match.test(e.name)) continue;
      try { const m = fs.statSync(fp).mtimeMs; if (!best || m > best.mtime) best = { path: fp, mtime: m }; } catch (err) { /* 忽略 */ }
    }
  };
  walk(spec.dir, 0);
  return best;
}

// 从一行日志里挑一句人话：工具调用的说明 / 助手文字 / 任务完成消息
const SKIP_KEY = /^(id|uuid|parentId|parentUuid|signature|sessionId|cwd|timestamp|model|type|role|stop_reason|encrypted_content|data|image_url|source)$/i;
function sayOf(obj, depth = 0) {
  if (!obj || typeof obj !== 'object' || depth > 7) return null;
  if (Array.isArray(obj)) {
    for (let i = obj.length - 1; i >= 0; i--) { const s = sayOf(obj[i], depth + 1); if (s) return s; }
    return null;
  }
  if (obj.type === 'tool_use' && obj.input) return (obj.input.description || obj.name) ? `调用 ${obj.name}${obj.input.description ? '：' + obj.input.description : ''}` : null;
  for (const k of ['description', 'last_agent_message', 'text', 'message', 'summary']) {
    const v = obj[k];
    if (typeof v === 'string' && v.trim().length > 3 && !/^[{[]/.test(v.trim())) return v;
  }
  for (const [k, v] of Object.entries(obj)) {
    if (SKIP_KEY.test(k) || typeof v !== 'object') continue;
    const s = sayOf(v, depth + 1);
    if (s) return s;
  }
  return null;
}
function doingNow(spec) {
  const f = newestLog(spec);
  if (!f || Date.now() - f.mtime > NOW_MS) return { text: null, at: f ? f.mtime : null };
  let buf;
  try {
    const fd = fs.openSync(f.path, 'r');
    const size = fs.fstatSync(fd).size, n = Math.min(size, TAIL_BYTES);
    buf = Buffer.alloc(n);
    fs.readSync(fd, buf, 0, n, size - n);
    fs.closeSync(fd);
  } catch (e) { return { text: null, at: f.mtime }; }
  const lines = buf.toString('utf8').split('\n').slice(1).filter(Boolean);
  for (let i = lines.length - 1; i >= 0; i--) {
    let j;
    try { j = JSON.parse(lines[i]); } catch (e) { continue; }
    // 只看助手 / 工具这一侧（白名单：用户输入、系统附件、提醒都不算「在做什么」）
    const role = j.message?.role || j.payload?.role || j.role;
    const assistant = role === 'assistant' || j.type === 'assistant' || /^(agent_message|function_call|custom_tool_call|task_complete)$/.test(j.payload?.type || '');
    if (!assistant) continue;
    const s = sayOf(j);
    if (s) return { text: s.replace(/\s+/g, ' ').trim().slice(0, 140), at: f.mtime };
  }
  return { text: null, at: f.mtime };
}

// CPU 采样：两次取 TotalProcessorTime 求差 → 占单核百分比。守护进程空转 ≈ 0%，真干活才起来
const CORES = os.cpus().length || 1;
function psCpu(pids) {
  if (!pids.length) return Promise.resolve(null);
  const ids = pids.join(',');
  return ps(`$s=0; foreach($id in @(${ids})){ try { $s += (Get-Process -Id $id -ErrorAction Stop).TotalProcessorTime.TotalSeconds } catch {} }; $s`);
}
async function cpuPctOf(pids) {
  if (!pids.length) return 0;
  const a = await psCpu(pids); const t0 = Date.now();
  await new Promise((r) => setTimeout(r, 1200));
  const b = await psCpu(pids); const dt = (Date.now() - t0) / 1000;
  const av = a != null ? parseFloat(String(a).trim().replace(',', '.')) : NaN;
  const bv = b != null ? parseFloat(String(b).trim().replace(',', '.')) : NaN;
  if (!isFinite(av) || !isFinite(bv) || dt <= 0) return null;
  return Math.max(0, ((bv - av) / dt / CORES) * 100);
}

let probeCache = { at: 0, data: null };
async function probe() {
  if (probeCache.data && Date.now() - probeCache.at < 60000) return probeCache.data;   // 60 秒缓存：CPU 采样+进程表较重
  const procs = await listProcs();
  const data = await Promise.all(AGENTS.map(async (a) => {
    const hits = procs.filter(a.proc);
    const installed = a.install.some((d) => fs.existsSync(d));
    const version = installed || hits.length ? await versionOf(a, procs) : null;
    const workHits = a.work ? procs.filter(a.work) : [];
    const pids = hits.map((p) => p.pid).filter(Boolean).concat(workHits.map((p) => p.pid).filter(Boolean));
    const cpu = await cpuPctOf(pids);
    const d = doingNow(a.logs);                       // 含 lastActive 时间
    const logAge = d.at ? Date.now() - d.at : Infinity;
    const starts = hits.map((p) => p.start).filter(Boolean);
    const startedAt = starts.length ? new Date(Math.min(...starts)).toISOString() : null;

    // 真判据：Claude 只在任务时才有进程；Pi / ChatGPT 是常驻进程，必须看它在不在干活
    const daemonish = a.id !== 'clawd';
    const busyByCpu = cpu != null && cpu >= 12;       // 持续时间较长的 >12% 单核才算真在算（GUI 空转也会瞬时冲 6%）
    const busyByLog = logAge < ACTIVE_MS;
    const busyByWork = workHits.length > 0;           // Codex/Pi 执行器进程存在 = 正在跑任务（做没做由执行器本身证明）
    const running = hits.length + workHits.length > 0 && (daemonish ? (busyByWork || busyByCpu || busyByLog) : true);
    const why = busyByWork ? `执行器 ${workHits.length} 个在跑` : busyByCpu ? `CPU ${cpu.toFixed(1)}%` : busyByLog ? '10 分钟内有新输出' : '';
    const status = running ? 'running' : (installed || version || hits.length) ? 'idle' : 'offline';

    const out = {
      id: a.id, name: a.name, status, version, procs: hits.length, startedAt,
      cpuPct: cpu == null ? null : Math.round(cpu * 10) / 10,
      lastActiveAt: d.at ? new Date(d.at).toISOString() : null,
      workProcs: workHits.length,
      runningWhy: running ? why : '',
      doing: running ? d.text : null,
      doingAt: running && d.at ? new Date(d.at).toISOString() : null,
    };
    if (status === 'running') out.note = [why, `${hits.length + workHits.length} 个进程`, cpu == null ? null : `CPU ${out.cpuPct}%`].filter(Boolean).join(' · ');
    else if (status === 'idle') out.note = hits.length
      ? `已安装 · 当前空闲（CPU ${out.cpuPct ?? 0}%，最近无新输出）`
      : '当前没有运行中的会话';
    else out.note = '未安装';
    return out;
  }));
  probeCache = { at: Date.now(), data };
  return data;
}

module.exports = { probe };
// 起服务时先热一次，面板第一次打开就不用等 6-8 秒
setTimeout(() => { probe().catch(() => {}); }, 1500);
setInterval(() => { probe().catch(() => {}); }, 40000);   // 后台常热，面板打开时版本号秒出
