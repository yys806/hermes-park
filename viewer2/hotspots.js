// 分区热点：聚焦某地块时，在该地块的建筑上方浮出圆形编号徽标（HTML 层，不动 3D 明暗）
// 点徽标 → 相机推到该建筑 + 右侧面板切到分区级
import * as THREE from 'three';

const norm = (n) => String(n || '').toLowerCase().replace(/[^a-z0-9]/g, '').replace(/(\d+|[a-z]{1,3})$/, '');

export class Hotspots {
  constructor(camera, plots, layer) {
    this.camera = camera;
    this.plots = plots;
    this.layer = layer;                 // DOM 容器
    this.biz = null;
    this.plot = null;
    this.items = [];
    this.v = new THREE.Vector3();
  }

  async setBiz(biz) { this.biz = biz; if (this.plot) this.show(this.plot); }

  clear() {
    this.layer.replaceChildren();
    this.items = [];
  }

  show(plotId) {
    this.plot = plotId;
    this.clear();
    if (!this.biz || !plotId) return;
    const p = this.plots.get(plotId);
    const def = this.biz.plots && this.biz.plots[plotId];
    if (!p || !def || !def.subsections || !p.entities) return;
    // 实体名归一化索引
    const idx = new Map();
    for (const [name, box] of p.entities) idx.set(norm(name), { name, box });
    let n = 0;
    for (const s of def.subsections) {
      const hit = idx.get(norm(s.node));
      if (!hit) continue;
      n++;
      const badge = document.createElement('button');
      badge.type = 'button';
      badge.className = 'hs';
      badge.innerHTML = `<b>${n}</b><span>${s.name}</span>`;
      badge.title = s.duty || s.name;
      badge.addEventListener('click', (e) => {
        e.stopPropagation();
        this.activate(plotId, s, hit);
      });
      this.layer.append(badge);
      // 采集时是在地块本地坐标系，这里用 holder 的世界矩阵转成世界坐标
      const wbox = hit.box.clone().applyMatrix4(p.holder.matrixWorld);
      const c = new THREE.Vector3();
      wbox.getCenter(c);
      this.items.push({ el: badge, pos: c.setY(wbox.max.y + 0.6), sub: s, box: wbox });
    }
  }

  activate(plotId, sub, hit) {
    if (window.__park && window.__park.flyToPoint) {
      const c = new THREE.Vector3();
      hit.box.getCenter(c);
      window.__park.flyToPoint(c, Math.max(18, hit.box.getSize(new THREE.Vector3()).length() * 1.6));
    }
    if (window.__panelShowSection) window.__panelShowSection(plotId, sub);
  }

  update() {
    if (!this.items.length) return;
    const w = window.innerWidth, h = window.innerHeight;
    for (const it of this.items) {
      this.v.copy(it.pos).project(this.camera);
      const x = (this.v.x * 0.5 + 0.5) * w;
      const y = (-this.v.y * 0.5 + 0.5) * h;
      const vis = this.v.z < 1 && x > -60 && x < w + 60 && y > -40 && y < h + 40;
      it.el.style.display = vis ? '' : 'none';
      it.el.style.transform = `translate(${x}px, ${y}px) translate(-50%, -100%)`;
    }
  }
}
