// 事件驱动包裹：只有真实任务在跑的时候，传送带上才有货在走
// 判定：任务的 nextRun 已到、且 lastRun 还没更新到这次（即「已触发、未回执」）→ 视为在跑
import * as THREE from 'three';

const SPEED = 7;            // m/s
const RING_R = 2.6;
const RING_H = 2.2;

export class CargoSystem {
  constructor(scene, beltSys, plots) {
    this.scene = scene;
    this.beltSys = beltSys;
    this.plots = plots;
    this.group = new THREE.Group();
    this.group.name = 'CargoLayer';
    scene.add(this.group);
    this.items = [];
    this.rings = new Map();
    this.active = new Map();   // jobId -> {plot, spawnAt}
    this.projects = new Set(); // 已废弃：假标记，保留兼容
    this.live = new Set();     // 真实会话进行中的地块（/api/live 的 busy=true）
    this.boxGeo = new THREE.BoxGeometry(0.55, 0.42, 0.55);
    this.boxMat = new THREE.MeshStandardMaterial({ color: 0xF3CE86, emissive: 0xB07A18, emissiveIntensity: 0.55, roughness: 0.55, metalness: 0.05 });
    this.ringGeo = new THREE.TorusGeometry(RING_R, 0.12, 8, 48);
    this.ringMat = new THREE.MeshBasicMaterial({ color: 0xF0B34A, transparent: true, opacity: 0.75 });
  }

  beltFor(plotId) {
    return this.beltSys.belts.find((b) => b.b && b.b.plot && b.b.plot.def && b.b.plot.def.id === plotId) || null;
  }

  // dir: 'in' 中央→地块；'out' 地块→中央
  spawn(plotId, dir, jobName) {
    const belt = this.beltFor(plotId);
    if (!belt || !belt.frames || belt.frames.length < 2) return null;
    const box = new THREE.Mesh(this.boxGeo, this.boxMat);
    box.name = 'cargo:' + plotId;
    box.castShadow = false;
    this.group.add(box);
    const item = { box, belt, plotId, dir, u: 0, jobName, len: belt.len || 1 };
    this.items.push(item);
    this.place(item);
    return item;
  }

  place(item) {
    const F = item.belt.frames;
    // 'in' 从中央那端走到地块那端；'out' 反过来
    const k = item.dir === 'in' ? item.u : 1 - item.u;
    const idx = Math.max(0, Math.min(F.length - 1, Math.round(k * (F.length - 1))));
    const f = F[idx];
    item.box.position.copy(f.p);
    item.box.position.y += 0.24;
    if (f.t) {
      const look = f.t.clone().setY(0).normalize();
      item.box.rotation.y = Math.atan2(look.x, look.z);
    }
  }

  ensureRing(plotId) {
    const cur = this.rings.get(plotId);
    if (cur) { if (cur.fade) { cur.fade = 0; cur.mesh.material.opacity = 0.75; } return cur; }
    const p = this.plots.get(plotId);
    if (!p) return null;
    const mesh = new THREE.Mesh(this.ringGeo, this.ringMat.clone());
    mesh.rotation.x = -Math.PI / 2;
    mesh.position.copy(p.center).setY((p.height || 6) + RING_H);
    mesh.name = 'ring:' + plotId;
    this.group.add(mesh);
    const obj = { mesh, born: performance.now(), fade: 0 };
    this.rings.set(plotId, obj);
    return obj;
  }

  // 环的判定：cron 在跑 或 该群会话正在进行（真数据）
  wantRing(plotId) {
    if (this.live.has(plotId)) return true;
    for (const a of this.active.values()) if (a.plot === plotId) return true;
    return false;
  }
  // 真实会话状态：['vault','inventor'] → 环变青绿；空数组 → 只剩 cron 的环
  setLive(ids) {
    const next = new Set(ids || []);   // 不过滤：地块可能还没加载完，update 里补建环
    const touched = new Set([...this.live, ...next]);
    this.live = next;
    // 颜色统一：所有环都用同一个琥珀色（用户 2026-10-31 要求）
    for (const id of touched) this.syncRing(id);
  }
  syncRing(plotId) {
    if (this.wantRing(plotId)) this.ensureRing(plotId); else this.dropRing(plotId);
  }
  // map: { plotId: true/false, ... }（其它字段忽略）
  setProjects(map) {
    const next = new Set(Object.entries(map || {}).filter(([k, v]) => v === true && this.plots.has(k)).map(([k]) => k));
    const touched = new Set([...this.projects, ...next]);
    this.projects = next;
    for (const id of touched) this.syncRing(id);
  }
  ringState() {
    return Object.fromEntries([...this.rings].map(([id, r]) => [id, { visible: r.mesh.visible && !r.fade && r.mesh.parent === this.group, opacity: +r.mesh.material.opacity.toFixed(2), project: this.projects.has(id) }]));
  }

  dropRing(plotId) {
    const r = this.rings.get(plotId);
    if (!r) return;
    r.fade = 1;
  }

  // jobs: /api/cron 的 jobs 数组
  onJobs(jobs) {
    const now = Date.now();
    const seen = new Set();
    for (const j of jobs) {
      const plot = j.plot;
      if (!plot || plot === 'control') continue;
      const next = j.nextRun ? Date.parse(j.nextRun) : 0;
      const last = j.lastRun ? Date.parse(j.lastRun) : 0;
      if (!next) continue;
      // 已到点、且没有新的回执 → 判定在跑
      const running = now >= next && now - next < 15 * 60 * 1000 && last < next;
      if (running) {
        seen.add(j.id);
        if (!this.active.has(j.id)) {
          this.active.set(j.id, { plot, spawnAt: now, name: j.name });
          this.spawn(plot, 'in', j.name);
          this.ensureRing(plot);
        }
      }
    }
    // 已结束的：包裹回中央、环淡出
    for (const [id, info] of [...this.active]) {
      if (seen.has(id)) continue;
      this.active.delete(id);
      this.spawn(info.plot, 'out', info.name);
      this.syncRing(info.plot);
    }
  }

  update(dt) {
    // 地块是异步加载的：已经 busy 但当时还没加载的地块，在这里补建环
    for (const id of this.live) if (!this.rings.has(id)) this.ensureRing(id);
    for (const item of [...this.items]) {
      item.u += (SPEED * dt) / Math.max(2, item.len);
      if (item.u >= 1) {
        item.u = 1;
        this.place(item);
        this.group.remove(item.box);
        this.items.splice(this.items.indexOf(item), 1);
        continue;
      }
      this.place(item);
    }
    for (const [plotId, r] of [...this.rings]) {
      const t = performance.now();
      r.mesh.rotation.z = t * 0.0006;
      const pulse = 1 + Math.sin(t * 0.003) * 0.06;
      r.mesh.scale.setScalar(pulse);
      if (r.fade) {
        r.fade += dt * 1.2;
        r.mesh.material.opacity = Math.max(0, 0.75 * (1 - r.fade));
        if (r.fade >= 1) { this.group.remove(r.mesh); r.mesh.material.dispose(); this.rings.delete(plotId); }
      }
    }
  }
}
