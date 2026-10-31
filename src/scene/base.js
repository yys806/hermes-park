import * as THREE from 'three';
import { mat } from '../utils/materials.js';
import { grassTexture, pavingTexture } from '../utils/proceduralTextures.js';
import { palette, layout } from '../config.js';

// 固定种子随机（mulberry32）：每次刷新布局一致
function rng(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6D2B79F5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// 贴地高度分层（路面在 0.015~0.035，这里全部压在它之下）
const Y_GRID = 0.004;
const Y_PATCH = 0.006;
const Y_PLAZA_TOP = 0.012;

export default function build(ctx) {
  const g = new THREE.Group();
  g.name = 'base';
  const rand = rng(20261025);

  // ── 1. 一大片地面：无厚度、无边缘，外沿远在雾里 ──
  // 程序化草地纹理（颗粒 + 明暗斑），平铺 24×24；颜色全在贴图里，材质色为白。
  // 带贴图的材质不走 mat() 缓存（缓存键会把 map 也 JSON 序列化）
  const groundGeo = new THREE.PlaneGeometry(layout.groundSize, layout.groundSize);
  groundGeo.rotateX(-Math.PI / 2);
  const ground = new THREE.Mesh(groundGeo, new THREE.MeshLambertMaterial({ map: grassTexture(ctx.renderer) }));
  ground.receiveShadow = true;
  g.add(ground);

  // ── 2. 地面分格：只铺到半径 30，最后 6 个单位渐变回草色，不留硬边 ──
  // 每条线切成 1.6 长的小段，用一个 InstancedMesh + 逐实例颜色做渐隐
  const GRID_R = 30;
  const FADE_FROM = 24;
  const step = 1.6;
  const lineW = 0.035;
  const n = Math.floor(GRID_R / step);
  const segGeo = new THREE.PlaneGeometry(step, lineW);
  segGeo.rotateX(-Math.PI / 2);

  const segs = [];
  for (let i = -n; i <= n; i++) {
    const off = i * step;
    for (let k = -n; k < n; k++) {
      const t = (k + 0.5) * step; // 段中心
      const r = Math.hypot(off, t);
      if (r > GRID_R) continue;
      const fade = THREE.MathUtils.smoothstep(r, FADE_FROM, GRID_R);
      segs.push({ x: t, z: off, rot: 0, fade });       // 沿 X 的线
      segs.push({ x: off, z: t, rot: Math.PI / 2, fade }); // 沿 Z 的线
    }
  }

  // 材质用白色，颜色全交给 instanceColor
  const grid = new THREE.InstancedMesh(segGeo, mat(0xffffff), segs.length);
  const lineCol = new THREE.Color(0xB6D6A8);
  const grassCol = new THREE.Color(palette.grass);
  const tmpCol = new THREE.Color();
  const dummy = new THREE.Object3D();
  segs.forEach((s, i) => {
    dummy.position.set(s.x, Y_GRID, s.z);
    dummy.rotation.set(0, s.rot, 0);
    dummy.updateMatrix();
    grid.setMatrixAt(i, dummy.matrix);
    grid.setColorAt(i, tmpCol.copy(lineCol).lerp(grassCol, s.fade));
  });
  grid.instanceMatrix.needsUpdate = true;
  grid.instanceColor.needsUpdate = true;
  grid.receiveShadow = true;
  grid.frustumCulled = false;
  g.add(grid);

  // ── 3. 中心广场：方砖铺地圆形地坪 + 稍深的环形镶边 ──
  // 圆柱顶盖 UV 把圆盘映射到 [0,1]²，砖纹平铺 3×3（直径上约 24 块砖）
  const plazaR = 5.2;
  const plazaH = 0.02;
  const plazaMat = new THREE.MeshLambertMaterial({ map: pavingTexture(ctx.renderer) });
  const plaza = new THREE.Mesh(new THREE.CylinderGeometry(plazaR, plazaR, plazaH, 72), plazaMat);
  plaza.position.y = Y_PLAZA_TOP - plazaH / 2;
  plaza.receiveShadow = true;
  g.add(plaza);

  const rimGeo = new THREE.RingGeometry(plazaR, plazaR + 0.3, 72);
  rimGeo.rotateX(-Math.PI / 2);
  const rim = new THREE.Mesh(rimGeo, mat(0xD6C8AE));
  rim.position.y = Y_PLAZA_TOP + 0.001;
  rim.receiveShadow = true;
  g.add(rim);

  // ── 4. 草坪色带：近处撒几块不规则半透明薄片，打破单调 ──
  const patchGeo = new THREE.CircleGeometry(1, 32);
  patchGeo.rotateX(-Math.PI / 2);
  const patchMats = [0xB6D6A8, 0x7FB37A].map((c) =>
    mat(c, { transparent: true, opacity: 0.35, depthWrite: false })
  );
  const patchCount = 7;
  for (let i = 0; i < patchCount; i++) {
    // 角度分层抖动，避免几块挤在一起
    const a = ((i + 0.2 + rand() * 0.6) / patchCount) * Math.PI * 2;
    const r = 8 + rand() * 18;
    const pr = 1.5 + rand() * 1.5;
    const p = new THREE.Mesh(patchGeo, patchMats[i % 2]);
    // 非等比缩放 + 随机朝向，圆片变成不规则椭圆
    p.scale.set(pr * (0.75 + rand() * 0.5), 1, pr * (0.75 + rand() * 0.5));
    p.rotation.y = rand() * Math.PI;
    p.position.set(Math.cos(a) * r, Y_PATCH + i * 0.0004, Math.sin(a) * r);
    p.receiveShadow = true;
    g.add(p);
  }

  ctx.scene.add(g);
  return { update: () => {} };
}
