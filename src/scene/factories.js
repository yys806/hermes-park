import * as THREE from 'three';
import { roundedBox } from '../utils/roundedBox.js';
import { mat, glowMat, glassMat } from '../utils/materials.js';
import { addContactShadow } from '../utils/contactShadow.js';
import { factories, layout, palette } from '../config.js';

const DEG = Math.PI / 180;
const solid = (m) => { m.castShadow = m.receiveShadow = true; return m; };
// 圆角块：挂到 parent 并定位
const box = (p, w, h, d, r, m, x, y, z) => {
  const o = solid(roundedBox(w, h, d, r, m, 3)); o.position.set(x, y, z); p.add(o); return o;
};
// 任意几何体；cast=false 用于发光/半透明件
const mesh = (p, geo, m, x, y, z, cast = true) => {
  const o = new THREE.Mesh(geo, m); o.position.set(x, y, z);
  if (cast) solid(o); p.add(o); return o;
};
const darker = (c, k = 0.8) => new THREE.Color(c).multiplyScalar(k);

// 学习科研群：图书馆塔
function buildLibrary(f) {
  const g = new THREE.Group();
  const body = mat(palette.white), trim = mat(f.color), wood = mat(palette.wood), dark = mat(palette.brown);
  box(g, 2.4, 3.2, 2.4, 0.12, body, 0, 1.6, 0);
  box(g, 0.62, 0.9, 0.08, 0.04, dark, 0, 0.45, 1.21);
  const bookMats = [palette.mint, palette.sky, palette.orange, palette.wood].map((c) => mat(c));
  [1.3, 1.95, 2.6].forEach((y, row) => {
    box(g, 2.0, 0.05, 0.24, 0.02, wood, 0, y, 1.32);
    for (let i = 0; i < 7; i++) {
      const b = box(g, 0.09, 0.3 - (i % 3) * 0.03, 0.16, 0.015, bookMats[(i + row) % 4],
        -0.72 + i * 0.24, y + 0.025 + (0.3 - (i % 3) * 0.03) / 2, 1.32);
      if (i === 6) b.rotation.z = 0.18;
    }
  });
  // 望远镜罩 + 斜镜筒（仰角 25°）
  mesh(g, new THREE.SphereGeometry(0.72, 24, 12, 0, Math.PI * 2, 0, Math.PI / 2), trim, 0, 3.2, 0);
  const tube = mesh(g, new THREE.CylinderGeometry(0.09, 0.11, 0.95, 12), mat(palette.metal), 0, 3.75, 0.45);
  tube.rotation.x = (90 - 25) * DEG;
  // 门口两摞书
  [-0.75, 0.75].forEach((x, s) => {
    for (let i = 0; i < 3; i++) {
      const b = box(g, 0.36, 0.08, 0.26, 0.02, bookMats[(i + s * 2) % 4], x, 0.04 + i * 0.085, 1.65);
      b.rotation.y = (i - 1) * 0.2 + s * 0.3;
    }
  });
  addContactShadow(g, 2.8, 2.8, 0.01, 0.35, 1.6);
  return g;
}

// 日常事务群：小邮局
function buildPost(f) {
  const g = new THREE.Group();
  const body = mat(f.color), roof = mat(darker(f.color, 0.75)), dark = mat(palette.brown);
  box(g, 2.8, 1.6, 2.0, 0.12, body, 0, 0.8, 0);
  box(g, 3.0, 0.16, 2.2, 0.06, roof, 0, 1.68, 0);
  const awn = box(g, 2.2, 0.06, 0.7, 0.03, mat(palette.cream), 0, 1.36, 1.3);
  awn.rotation.x = 20 * DEG;
  box(g, 0.6, 0.95, 0.08, 0.04, dark, -0.5, 0.48, 1.01);
  mesh(g, new THREE.BoxGeometry(0.7, 0.45, 0.04), glowMat(0xfff2b0, 0.9), 0.55, 0.85, 1.02, false);
  // 红邮筒：筒身 + 圆盖 + 投信口
  const red = mat(0xd9534f);
  mesh(g, new THREE.CylinderGeometry(0.16, 0.16, 0.62, 16), red, 1.05, 0.31, 1.55);
  mesh(g, new THREE.SphereGeometry(0.17, 16, 8, 0, Math.PI * 2, 0, Math.PI / 2), red, 1.05, 0.62, 1.55);
  box(g, 0.18, 0.03, 0.03, 0.01, mat(0x3a2a2a), 1.05, 0.5, 1.71);
  // 侧面包裹，两层斜叠
  const kraft = mat(palette.wood);
  [[0.5, -0.1, 0.25, 0.1], [0.4, 0.35, 0.2, -0.25], [0.38, 0.05, 0.69, 0.35], [0.34, 0.15, 1.06, -0.15]]
    .forEach(([s, z, y, ry]) => { box(g, s, s * 0.8, s, 0.04, kraft, 1.75, y, z).rotation.y = ry; });
  addContactShadow(g, 3.6, 2.8, 0.01, 0.35, 1.8);
  return g;
}

// 彩虹事务群：彩虹拱门
function buildArch(f) {
  const g = new THREE.Group();
  const rainbow = [0xe8a8c8, palette.orange, 0xf5d77a, palette.mint, palette.sky, 0xb8a0d8, 0xe8a8c8];
  const R = 1.05, base = 0.5;
  box(g, 0.26, base, 0.26, 0.06, mat(f.color), -R, base / 2, 0.4);
  box(g, 0.26, base, 0.26, 0.06, mat(f.color), R, base / 2, 0.4);
  rainbow.forEach((c, i) => {
    const th = Math.PI - (i / 6) * Math.PI;
    const s = box(g, 0.34, 0.22, 0.26, 0.06, mat(c), Math.cos(th) * R, base + Math.sin(th) * R, 0.4);
    s.rotation.z = th + Math.PI / 2;
  });
  // 拱下门房
  box(g, 1.0, 1.0, 0.9, 0.1, mat(palette.cream), 0, 0.5, -0.1);
  box(g, 0.4, 0.6, 0.06, 0.03, mat(darker(f.color, 0.7)), 0, 0.3, 0.36);
  // 糖果管道：竖管 + 弯头 + 横管
  const pink = mat(0xf4b6cf), white = mat(palette.white);
  mesh(g, new THREE.CylinderGeometry(0.12, 0.12, 1.3, 16), pink, 1.65, 0.65, -0.3);
  mesh(g, new THREE.SphereGeometry(0.15, 16, 12), white, 1.65, 1.35, -0.3);
  mesh(g, new THREE.CylinderGeometry(0.12, 0.12, 1.0, 16), pink, 1.15, 1.35, -0.3).rotation.z = Math.PI / 2;
  addContactShadow(g, 3.6, 2.2, 0.01, 0.3, 1.6);
  return g;
}

// 家人事务群：温馨小屋（烟囱冒烟）
function buildHouse(f, updates) {
  const g = new THREE.Group();
  const body = mat(f.color), roof = mat(darker(f.color, 0.72)), wood = mat(palette.wood);
  box(g, 2.2, 1.6, 1.8, 0.12, body, 0, 0.8, 0);
  const L = 1.25 / Math.cos(30 * DEG);
  [-1, 1].forEach((s) => {
    box(g, L, 0.08, 2.0, 0.03, roof, s * 0.625, 1.6 + 0.36, 0).rotation.z = -s * 30 * DEG;
  });
  box(g, 0.5, 0.85, 0.06, 0.04, mat(palette.brown), 0, 0.43, 0.91);
  const glow = glowMat(0xfff2b0, 0.95);
  [-0.68, 0.68].forEach((x) => mesh(g, new THREE.BoxGeometry(0.38, 0.38, 0.04), glow, x, 0.95, 0.92, false));
  box(g, 0.24, 0.7, 0.24, 0.04, mat(palette.brown), 0.6, 2.15, -0.4);
  // 烟团：不同相位上升 + 淡出
  const puffs = [0, 1, 2].map(() => mesh(g, new THREE.SphereGeometry(0.13, 12, 8),
    mat(palette.white, { transparent: true, opacity: 0.6, depthWrite: false }), 0.6, 2.6, -0.4, false));
  updates.push((dt, t) => puffs.forEach((p, i) => {
    const k = (t * 0.35 + i / 3) % 1;
    p.position.set(0.6 + Math.sin(k * 4 + i) * 0.08, 2.6 + k * 0.9, -0.4);
    p.scale.setScalar(0.6 + k * 0.9);
    p.material.opacity = 0.6 * (1 - k);
  }));
  // 屋前半圈篱笆
  const R = 1.6;
  for (let i = 0; i < 8; i++) {
    const a = (i / 7) * Math.PI;
    box(g, 0.06, 0.3, 0.06, 0.02, wood, Math.cos(a) * R, 0.15, Math.sin(a) * R);
  }
  [0.1, 0.22].forEach((y) => {
    mesh(g, new THREE.TorusGeometry(R, 0.018, 4, 32, Math.PI), wood, 0, y, 0).rotation.x = Math.PI / 2;
  });
  addContactShadow(g, 3.4, 3.4, 0.01, 0.35, 1.8);
  return g;
}

// 奇思妙想群：歪塔发明家（塔身倾斜 7°，灯泡漂浮）
function buildInventor(f, updates) {
  const grp = new THREE.Group();
  const purple = mat(f.color), trim = mat(darker(f.color, 0.75)), copper = mat(0xC9853F), metal = mat(palette.metal);
  const sub = new THREE.Group();
  sub.rotation.z = THREE.MathUtils.degToRad(7);
  grp.add(sub);
  // 三段塔身 + 段间腰线
  let y = 0;
  [[2.4, 1.7], [2.1, 1.6], [1.8, 1.5]].forEach(([w, h], i) => {
    box(sub, w, h, w, 0.1, purple, 0, y + h / 2, 0);
    y += h;
    if (i < 2) box(sub, 2.5, 0.14, 2.5, 0.04, trim, 0, y, 0);
  });
  // 螺旋铜管：10 节绕塔身由下而上
  const pipe = new THREE.CylinderGeometry(0.09, 0.09, 0.35, 10);
  for (let i = 0; i < 10; i++) {
    const a = i * 0.9;
    mesh(sub, pipe, copper, Math.cos(a) * 1.35, 0.6 + i * 0.45, Math.sin(a) * 1.35);
  }
  // 外挂小平台（1/3、2/3 高度，朝 -X / -Z），各放小方块 + 小球
  [[-1.75, 1.6, 0], [0, 3.2, -1.6]].forEach(([x, py, z], i) => {
    box(sub, 1.1, 0.12, 1.1, 0.03, trim, x, py, z);
    box(sub, 0.3, 0.3, 0.3, 0.04, i ? copper : metal, x - 0.2, py + 0.21, z);
    mesh(sub, new THREE.SphereGeometry(0.14, 14, 10), i ? metal : copper, x + 0.25, py + 0.2, z + 0.1);
  });
  // 塔顶：细天线 + 发光顶球 + 一圈紫色灯点
  mesh(sub, new THREE.CylinderGeometry(0.03, 0.03, 1.2, 8), metal, 0, y + 0.6, 0);
  mesh(sub, new THREE.SphereGeometry(0.12, 14, 10), glowMat(0xF2D06A), 0, y + 1.25, 0, false);
  const dotMat = glowMat(0xC3A8E8), dot = new THREE.SphereGeometry(0.05, 8, 6);
  for (let i = 0; i < 6; i++) {
    const a = (i / 6) * Math.PI * 2;
    mesh(sub, dot, dotMat, Math.cos(a) * 0.6, y + 0.06, Math.sin(a) * 0.6, false);
  }
  // 漂浮灯泡（不随塔倾斜）：玻璃球 + 金属灯头
  const bulb = new THREE.Group();
  bulb.position.set(2.0, 2.2, 0);
  grp.add(bulb);
  mesh(bulb, new THREE.SphereGeometry(0.4, 20, 14), glassMat(0xF2D06A, 0.45), 0, 0, 0, false);
  mesh(bulb, new THREE.CylinderGeometry(0.14, 0.14, 0.2, 12), metal, 0, -0.46, 0);
  updates.push((dt, t) => {
    bulb.position.y = 2.2 + Math.sin(t * 1.5) * 0.12;
    bulb.rotation.y += dt * 0.4;
  });
  addContactShadow(grp, 5.0, 5.0, 0.012, 0.16, 0.25);
  return grp;
}

// 通知待办群：钟楼（转动指针 + 广播喇叭）
function buildClock(f, updates) {
  const grp = new THREE.Group();
  const body = mat(f.color), trim = mat(darker(f.color, 0.72)), dark = mat(palette.brown), white = mat(palette.white), metal = mat(palette.metal);
  // 三层塔身 + 层间腰线
  let y = 0;
  [[2.6, 1.7], [2.3, 1.6], [2.0, 1.5]].forEach(([w, h], i) => {
    box(grp, w, h, w, 0.1, body, 0, y + h / 2, 0);
    y += h;
    if (i < 2) box(grp, 2.4, 0.14, 2.4, 0.04, trim, 0, y, 0);
  });
  // 钟面（中层 +Z 面）：白盘 + 深色外环 + 12 刻度 + 时针/分针
  const face = new THREE.Group();
  face.position.set(0, 2.5, 1.15);
  grp.add(face);
  mesh(face, new THREE.CylinderGeometry(0.95, 0.95, 0.1, 32), white, 0, 0, 0.05).rotation.x = Math.PI / 2;
  mesh(face, new THREE.TorusGeometry(0.98, 0.06, 8, 32), dark, 0, 0, 0.1);
  const tick = new THREE.CylinderGeometry(0.05, 0.05, 0.04, 8);
  for (let i = 0; i < 12; i++) {
    const a = (i / 12) * Math.PI * 2;
    mesh(face, tick, dark, Math.cos(a) * 0.8, Math.sin(a) * 0.8, 0.11).rotation.x = Math.PI / 2;
  }
  const hand = (len, th, z, r0) => {
    const h = new THREE.Group(); h.position.z = z; h.rotation.z = r0; face.add(h);
    mesh(h, new THREE.BoxGeometry(len, th, th), dark, len / 2, 0, 0); return h;
  };
  const hourHand = hand(0.55, 0.06, 0.14, Math.PI / 3), minHand = hand(0.75, 0.05, 0.19, Math.PI / 2);
  updates.push((dt) => { hourHand.rotation.z -= dt * 0.02; minHand.rotation.z -= dt * 0.24; });
  // 上层四面百叶窗
  for (let k = 0; k < 4; k++) {
    const side = new THREE.Group(); side.rotation.y = k * Math.PI / 2; grp.add(side);
    for (let i = 0; i < 4; i++) box(side, 1.6, 0.09, 0.08, 0.02, trim, 0, 3.7 + i * 0.25, 1.03);
  }
  // 底层大门 + 门楣
  box(grp, 0.8, 1.3, 0.1, 0.05, dark, 0, 0.65, 1.3);
  box(grp, 1.0, 0.14, 0.14, 0.03, trim, 0, 1.37, 1.33);
  // 广播喇叭（塔右侧）：锥筒朝 +X + 支柱 + 三条斜撑 + 两道音波弧
  mesh(grp, new THREE.CylinderGeometry(0.12, 0.45, 0.7, 12), metal, 2.0, 1.4, 0).rotation.z = Math.PI / 2;
  mesh(grp, new THREE.CylinderGeometry(0.07, 0.07, 0.9, 10), metal, 1.8, 0.75, 0);
  for (let i = 0; i < 3; i++) {
    const lg = new THREE.Group(); lg.position.set(1.8, 0, 0); lg.rotation.y = (i / 3) * Math.PI * 2; grp.add(lg);
    mesh(lg, new THREE.CylinderGeometry(0.025, 0.025, 0.4, 6), metal, 0.12, 0.17, 0).rotation.z = 0.55;
  }
  const wave = new THREE.TorusGeometry(0.5, 0.02, 6, 16, Math.PI * 0.6);
  [1, 1.3].forEach((s) => {
    const w = mesh(grp, wave, trim, 1.9, 1.4, 0, false);
    w.rotation.z = -Math.PI * 0.3; w.scale.setScalar(s);
  });
  // 屋顶：四棱尖顶 + 风向标
  mesh(grp, new THREE.ConeGeometry(0.9, 0.7, 4), trim, 0, y + 0.35, 0).rotation.y = Math.PI / 4;
  mesh(grp, new THREE.CylinderGeometry(0.02, 0.02, 0.6, 6), metal, 0, y + 1.0, 0);
  mesh(grp, new THREE.CylinderGeometry(0.16, 0.16, 0.02, 3), metal, 0.14, y + 1.15, 0).rotation.x = Math.PI / 2;
  addContactShadow(grp, 5.0, 5.0, 0.012, 0.16, 0.25);
  return grp;
}

// 资产管理群：金铜金库（圆门转轮 + 集装箱堆场）
function buildVault(f, updates) {
  const grp = new THREE.Group();
  const gold = mat(0xD9B382), goldDk = mat(0xC29A6B), steel = mat(0x5A5F66), metal = mat(palette.metal);
  // 主体 + 四角厚墙柱
  box(grp, 3.0, 2.6, 3.0, 0.14, gold, 0, 1.3, 0);
  [[-1, -1], [-1, 1], [1, -1], [1, 1]].forEach(([sx, sz]) => box(grp, 0.35, 2.6, 0.35, 0.06, goldDk, sx * 1.45, 1.3, sz * 1.45));
  // 正面圆形金库门：外环 + 门板 + 四铆钉 + 十字转轮
  const door = new THREE.Group();
  door.position.set(0, 1.3, 1.5);
  grp.add(door);
  mesh(door, new THREE.TorusGeometry(0.95, 0.1, 10, 32), goldDk, 0, 0, 0.08);
  mesh(door, new THREE.CylinderGeometry(0.85, 0.85, 0.12, 32), steel, 0, 0, 0.06).rotation.x = Math.PI / 2;
  const rivet = new THREE.SphereGeometry(0.07, 10, 8);
  [[-1, -1], [-1, 1], [1, -1], [1, 1]].forEach(([sx, sy]) => mesh(door, rivet, metal, sx * 0.5, sy * 0.5, 0.13));
  const wheel = new THREE.Group();
  wheel.position.z = 0.19;
  door.add(wheel);
  box(wheel, 1.3, 0.12, 0.12, 0.04, metal, 0, 0, 0);
  box(wheel, 0.12, 1.3, 0.12, 0.04, metal, 0, 0, 0);
  updates.push((dt) => { wheel.rotation.z += dt * 0.35; });
  // 右侧集装箱堆场：下层 3 个沿 Z 并排，上层 1 个错位压上；外侧面 3 条竖纹
  const crate = (c, x, y, z, ry) => {
    const g = new THREE.Group(); g.position.set(x, y, z); g.rotation.y = ry; grp.add(g);
    box(g, 1.5, 0.8, 0.9, 0.05, mat(c), 0, 0, 0);
    const dk = mat(darker(c));
    [-0.25, 0, 0.25].forEach((dz) => { box(g, 0.06, 0.7, 0.04, 0.01, dk, 0.77, 0, dz).rotation.y = Math.PI / 2; });
  };
  crate(0xF2A65A, 3.2, 0.4, -1.0, 0);
  crate(0xA8D5BA, 3.2, 0.4, 0, 0);
  crate(0x8FB8D8, 3.2, 0.4, 1.0, 0);
  crate(0xD9B382, 3.3, 1.2, -0.5, 0.15);
  // 屋顶护栏：12 立柱（4×4 网格的外圈）+ 4 根横杆方框
  const P = [-1.35, -0.45, 0.45, 1.35];
  P.forEach((x, i) => P.forEach((z, j) => {
    if (i === 0 || i === 3 || j === 0 || j === 3) box(grp, 0.08, 0.3, 0.08, 0.02, goldDk, x, 2.75, z);
  }));
  [-1, 1].forEach((s) => {
    box(grp, 2.78, 0.06, 0.06, 0.02, goldDk, 0, 2.88, s * 1.35);
    box(grp, 0.06, 0.06, 2.78, 0.02, goldDk, s * 1.35, 2.88, 0);
  });
  addContactShadow(grp, 5.0, 5.0, 0.012, 0.16, 0.25);
  return grp;
}

// 咨询新闻群：蓝灰印刷厂（锯齿天窗 + 卫星盘 + 报纸垛）
function buildPress(f, updates) {
  const grp = new THREE.Group();
  const blue = mat(0x9FB6C9), blueDk = mat(darker(0x9FB6C9, 0.72)), stripe = mat(darker(0x9FB6C9, 0.6));
  const metal = mat(palette.metal), paper = mat(0xF4F1EA), glow = glowMat(0xCFE9F7, 0.85);
  // 长条厂房
  box(grp, 4.2, 2.0, 2.8, 0.12, blue, 0, 1.0, 0);
  // 正面三扇卷帘门，各 5 条横纹
  [-1.3, 0, 1.3].forEach((x) => {
    box(grp, 0.9, 1.2, 0.08, 0.03, blueDk, x, 0.6, 1.44);
    for (let i = 0; i < 5; i++) box(grp, 0.8, 0.05, 0.03, 0.01, stripe, x, 0.2 + i * 0.2, 1.495);
  });
  // 屋顶锯齿天窗：斜板 35° + 淡蓝发光薄片
  [-1.3, 0, 1.3].forEach((x) => {
    const tooth = new THREE.Group(); tooth.position.set(x, 2.3, 0.2); tooth.rotation.x = -35 * DEG; grp.add(tooth);
    box(tooth, 1.2, 0.1, 0.9, 0.03, blueDk, 0, 0, 0);
    mesh(tooth, new THREE.BoxGeometry(1.0, 0.03, 0.7), glow, 0, 0.065, 0, false);
  });
  // 卫星接收盘（右侧）：立柱 + 斜连杆 + 碗形盘面（整体朝右上倾 40°）+ 馈源
  mesh(grp, new THREE.CylinderGeometry(0.1, 0.1, 1.4, 12), metal, 3.0, 0.7, 0);
  box(grp, 0.08, 1.1, 0.08, 0.02, metal, 2.8, 1.25, 0).rotation.z = -40 * DEG;
  const dish = new THREE.Group(); dish.position.set(3.0, 1.75, 0); dish.rotation.z = -40 * DEG; grp.add(dish);
  const bowl = mesh(dish, new THREE.SphereGeometry(0.9, 20, 12, 0, Math.PI * 2, 0, Math.PI * 0.5),
    mat(0xD5DAE0, { side: THREE.DoubleSide }), 0, 0.4, 0);
  bowl.rotation.x = Math.PI; bowl.scale.y = 0.45;
  mesh(dish, new THREE.CylinderGeometry(0.03, 0.03, 0.7, 8), metal, 0, 0.35, 0);
  // 门口报纸卷垛（三卷叠放）
  for (let i = 0; i < 3; i++) mesh(grp, new THREE.CylinderGeometry(0.45, 0.45, 0.35, 20), paper, -1.6 + i * 0.06, 0.175 + i * 0.36, 2.0);
  // 报架：两立柱 + 两横杆 + 三片斜放报纸
  [0.3, 1.3].forEach((x) => box(grp, 0.06, 1.2, 0.06, 0.02, metal, x, 0.6, 2.0));
  [0.5, 1.0].forEach((y) => box(grp, 1.06, 0.05, 0.05, 0.02, metal, 0.8, y, 2.0));
  [0.45, 0.8, 1.15].forEach((x) => { box(grp, 0.3, 0.4, 0.03, 0.01, paper, x, 0.78, 2.06).rotation.x = -0.35; });
  addContactShadow(grp, 5.0, 5.0, 0.012, 0.16, 0.25);
  return grp;
}

// 工厂整体放大倍数
const FACTORY_SCALE = 1.28;

// 已实现的构建器
const BUILDERS = {
  library: buildLibrary, post: buildPost, arch: buildArch, house: buildHouse, inventor: buildInventor, clock: buildClock,
  vault: buildVault, press: buildPress,
};

export default function build(ctx) {
  const g = new THREE.Group();
  const updates = [];
  for (const f of factories) {
    const b = BUILDERS[f.type];
    if (!b) continue;            // 暂无构建器的类型直接跳过
    const grp = b(f, updates);
    const rad = f.angle * Math.PI / 180;
    grp.position.set(Math.cos(rad) * layout.ringRadius, 0, Math.sin(rad) * layout.ringRadius);
    grp.rotation.y = 0;   // 全部正面朝 +Z，即朝向镜头
    // 整体放大：占地 5.0→6.4、主体高 ~5.0–5.5→6.4–7.0；接触阴影在组内一起放大到 6.4，与占地对齐
    grp.scale.setScalar(FACTORY_SCALE);
    g.add(grp);
  }
  ctx.scene.add(g);
  return { update(dt, t) { updates.forEach(fn => fn(dt, t)); } };
}
