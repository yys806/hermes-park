// 园区环境：草地、石板步道、低多边形树林、地台软阴影。全部程序生成，InstancedMesh 控制 draw call。
import * as THREE from 'three';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';
import { patchInstancedSway } from './ambient.js?v=20261031-p5';

export const GROUND_Y = -0.1;      // 草地基准面：地块地台顶面在 y=0，留 0.1 m 薄高差
// B-6 浮岛沙盘：草地是一张圆形（噪声起伏的岸线）切片，外缘是 5 m 地层断面 + 下方收窄的岩底
const ISLAND_R = 176;              // 岸线平均半径
const ISLAND_WOBBLE = 5;           // 岸线起伏（米）
const FOREST_IN = 54;              // 树林内缘（半径）
const FOREST_OUT = 150;

// ── 噪声（确定性，不依赖 Math.random，每次打开长得一样） ──
function rng(seed) {
  let s = seed >>> 0;
  return () => {
    s = (s + 0x6D2B79F5) >>> 0;
    let t = s;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
function hash2(x, z, seed) {
  let h = Math.imul(x | 0, 374761393) ^ Math.imul(z | 0, 668265263) ^ Math.imul(seed, 2246822519);
  h = Math.imul(h ^ (h >>> 13), 1274126177);
  return ((h ^ (h >>> 16)) >>> 0) / 4294967296;
}
function vnoise(x, z, seed) {
  const xi = Math.floor(x), zi = Math.floor(z);
  const fx = x - xi, fz = z - zi;
  const ux = fx * fx * (3 - 2 * fx), uz = fz * fz * (3 - 2 * fz);
  const a = hash2(xi, zi, seed), b = hash2(xi + 1, zi, seed);
  const c = hash2(xi, zi + 1, seed), d = hash2(xi + 1, zi + 1, seed);
  return a + (b - a) * ux + (c - a) * uz + (a - b - c + d) * ux * uz;
}
function fbm(x, z, seed, oct = 4) {
  let v = 0, amp = 0.5, f = 1, sum = 0;
  for (let i = 0; i < oct; i++) { v += amp * vnoise(x * f, z * f, seed + i * 17); sum += amp; amp *= 0.5; f *= 2.03; }
  return v / sum;
}
const smooth = (a, b, x) => { const t = Math.min(1, Math.max(0, (x - a) / (b - a))); return t * t * (3 - 2 * t); };

// ── 布局几何：地块占地（方形可旋转 / 圆盘） ──
export function makeLayout(sceneDef) {
  const foot = sceneDef.plots.map((p) => {
    const r = THREE.MathUtils.degToRad(p.rotY || 0);
    return { id: p.id, x: p.pos[0], z: p.pos[1], c: Math.cos(r), s: Math.sin(r), hx: p.size[0] / 2, hz: p.size[1] / 2, round: p.round || 0 };
  });
  const byId = Object.fromEntries(foot.map((f) => [f.id, f]));
  // 传送带大致走线（地块中心连线），用于压平地形、避开树和石板
  const belts = sceneDef.belts.map((b) => [byId[b.from.plot], byId[b.to.plot]]).filter(([a, b]) => a && b);
  return { foot, belts };
}

// 点到地块的距离（外部为正，内部为负）
function footDist(f, x, z) {
  const dx = x - f.x, dz = z - f.z;
  if (f.round) return Math.hypot(dx, dz) - f.round;
  const lx = dx * f.c - dz * f.s, lz = dx * f.s + dz * f.c;
  const qx = Math.abs(lx) - f.hx, qz = Math.abs(lz) - f.hz;
  const out = Math.hypot(Math.max(qx, 0), Math.max(qz, 0));
  return out + Math.min(Math.max(qx, qz), 0);
}
function segDist(px, pz, a, b) {
  const vx = b.x - a.x, vz = b.z - a.z;
  const t = Math.max(0, Math.min(1, ((px - a.x) * vx + (pz - a.z) * vz) / (vx * vx + vz * vz)));
  return Math.hypot(px - a.x - vx * t, pz - a.z - vz * t);
}

export function createWorld(scene, layout) {
  const minFoot = (x, z) => { let d = Infinity; for (const f of layout.foot) d = Math.min(d, footDist(f, x, z)); return d; };
  const minBelt = (x, z) => { let d = Infinity; for (const [a, b] of layout.belts) d = Math.min(d, segDist(x, z, a, b)); return d; };
  const insideFoot = (x, z, margin = 0) => layout.foot.some((f) => footDist(f, x, z) < margin);

  // 地形：中心区平坦，离地块/传送带越远越起伏
  const heightAt = (x, z) => {
    const r = Math.hypot(x, z);
    const free = Math.min(minFoot(x, z), minBelt(x, z) + 2);
    const amp = smooth(6, 30, free) * (0.35 + 1.9 * smooth(50, 120, r));
    return GROUND_Y + amp * (fbm(x * 0.022, z * 0.022, 7) - 0.32);
  };
  // 支腿落脚点：在地块地台上踩 y=0，否则踩草地
  const groundAt = (x, z) => (insideFoot(x, z, 0.05) ? 0 : heightAt(x, z));

  const group = new THREE.Group();
  group.name = 'world';
  scene.add(group);

  // ── 岸线 ──
  const rimR = (a) => ISLAND_R + ISLAND_WOBBLE * 2 * (fbm(Math.cos(a) * 2.4 + 7, Math.sin(a) * 2.4 + 7, 51, 3) - 0.5)
    + 1.2 * (fbm(Math.cos(a) * 9 + 3, Math.sin(a) * 9 + 3, 52, 2) - 0.5);
  const LIP = 0.55;                // 草地在岸边往下圆过去的落差
  const lipDrop = (d) => LIP * (1 - smooth(0, 3.2, d)) ** 1.6;   // d = 离岸线距离

  // ── 草地（极坐标网格，外圈正好落在岸线上） ──
  const NA = 360;
  const TS = [];
  for (let k = 0; k <= 74; k++) TS.push(k / 76);
  for (const m of [3.2, 2.2, 1.4, 0.8, 0.35, 0]) TS.push(1 - m / ISLAND_R);
  const NR = TS.length;
  const gPos = new Float32Array(NA * NR * 3), col = new Float32Array(NA * NR * 3);
  const rimTop = new Float32Array(NA), rimRad = new Float32Array(NA);
  const cA = new THREE.Color('#A7C487'), cB = new THREE.Color('#8FB577'), cC = new THREE.Color('#BCCB8F'), cEdge = new THREE.Color('#7FA266'), tmp = new THREE.Color();
  for (let i = 0; i < NA; i++) {
    const a = i / NA * Math.PI * 2, R = rimR(a), sa = Math.sin(a), ca = Math.cos(a);
    rimRad[i] = R;
    for (let k = 0; k < NR; k++) {
      const r = TS[k] * R, x = sa * r, z = ca * r, d = R - r;
      const y = heightAt(x, z) - lipDrop(d);
      const v = (i * NR + k) * 3;
      gPos[v] = x; gPos[v + 1] = y; gPos[v + 2] = z;
      if (k === NR - 1) rimTop[i] = y;
      const n = fbm(x * 0.05, z * 0.05, 3, 3);
      const m = fbm(x * 0.013, z * 0.013, 11, 2);
      tmp.copy(cA).lerp(cB, smooth(0.35, 0.7, n)).lerp(cC, smooth(0.55, 0.8, m) * 0.6).lerp(cEdge, (1 - smooth(0, 5, d)) * 0.7);
      col[v] = tmp.r; col[v + 1] = tmp.g; col[v + 2] = tmp.b;
    }
  }
  const gIdx = [];
  for (let i = 0; i < NA; i++) {
    const i2 = (i + 1) % NA;
    for (let k = 0; k < NR - 1; k++) {
      const a = i * NR + k, b = i2 * NR + k, c = i2 * NR + k + 1, d = i * NR + k + 1;
      gIdx.push(a, d, b, b, d, c);
    }
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.BufferAttribute(gPos, 3));
  g.setAttribute('color', new THREE.BufferAttribute(col, 3));
  g.setIndex(gIdx);
  g.computeVertexNormals();
  const grass = new THREE.Mesh(g, new THREE.MeshLambertMaterial({ vertexColors: true }));
  grass.name = 'grass';
  grass.receiveShadow = true;
  group.add(grass);

  // ── 地层断面 + 岩底 ──
  // 每行：[离岸顶的深度, 向外(+)/向内(-)偏移, 颜色, 内外抖动幅度]。同一深度连写两行 = 两层之间的清晰分界
  const STRATA = [
    [0.02, -0.05, '#6E8F55', 0.05],   // 草皮下沿（与草地外圈接缝）
    [0.22, 0.10, '#5E4A38', 0.10],    // 表土（深褐）
    [0.95, 0.18, '#664F3A', 0.22],
    [1.25, 0.12, '#664F3A', 0.20],
    [1.27, 0.12, '#A9835C', 0.20],    // 黏土层（暖赭）
    [2.10, 0.30, '#B38D63', 0.32],
    [2.75, 0.05, '#9C7854', 0.28],
    [2.77, 0.05, '#8D847A', 0.28],    // 岩层（灰褐）
    [3.80, 0.22, '#958C80', 0.40],
    [4.70, -0.20, '#7E766C', 0.35],
    [5.30, -0.85, '#6F675E', 0.30],   // 断面下沿，往里收
  ];
  const UNDER = [[0.86, 8.5, '#6E665D'], [0.62, 14, '#655E56'], [0.34, 19.5, '#5D5750'], [0.0, 23, '#57514A']];
  const NS = STRATA.length + UNDER.length;
  const sPos = new Float32Array(NA * NS * 3), sCol = new Float32Array(NA * NS * 3);
  const SR = rng(777);
  for (let i = 0; i < NA; i++) {
    const a = i / NA * Math.PI * 2, sa = Math.sin(a), ca = Math.cos(a), R = rimRad[i], top = rimTop[i];
    let j = 0;
    for (const [dep, off, c, jit] of STRATA) {
      // 低频噪声 + 少量逐点随机：横向层理与凿痕
      const wob = (fbm(a * 40, dep * 1.7, 61, 2) - 0.5) * 2 * jit + (SR() - 0.5) * jit * 0.4;
      const r = R + off + wob;
      const v = (i * NS + j) * 3;
      sPos[v] = sa * r; sPos[v + 1] = top - dep; sPos[v + 2] = ca * r;
      tmp.set(c).offsetHSL(0, 0, (fbm(a * 25, dep * 3, 62, 2) - 0.5) * 0.08);
      sCol[v] = tmp.r; sCol[v + 1] = tmp.g; sCol[v + 2] = tmp.b;
      j++;
    }
    const bottom = top - STRATA[STRATA.length - 1][0];
    for (const [t, dep, c] of UNDER) {
      const r = (R - 0.85) * t * (1 + (fbm(a * 6, t * 4, 63, 2) - 0.5) * 0.12);
      const v = (i * NS + j) * 3;
      sPos[v] = sa * r; sPos[v + 1] = bottom - dep + (fbm(a * 8, t * 5, 64, 2) - 0.5) * 2.5; sPos[v + 2] = ca * r;
      tmp.set(c);
      sCol[v] = tmp.r; sCol[v + 1] = tmp.g; sCol[v + 2] = tmp.b;
      j++;
    }
  }
  const sIdx = [];
  for (let i = 0; i < NA; i++) {
    const i2 = (i + 1) % NA;
    for (let k = 0; k < NS - 1; k++) {
      const a = i * NS + k, b = i2 * NS + k, c = i2 * NS + k + 1, d = i * NS + k + 1;
      sIdx.push(a, d, b, b, d, c);
    }
  }
  const sg = new THREE.BufferGeometry();
  sg.setAttribute('position', new THREE.BufferAttribute(sPos, 3));
  sg.setAttribute('color', new THREE.BufferAttribute(sCol, 3));
  sg.setIndex(sIdx);
  sg.computeVertexNormals();
  const cliff = new THREE.Mesh(sg, new THREE.MeshLambertMaterial({ vertexColors: true, flatShading: true, side: THREE.DoubleSide }));
  cliff.name = 'cliff';
  group.add(cliff);

  // ── 地台软阴影：每块地下面一张柔边贴片（不占阴影贴图，远处地块也有落地感） ──
  const blobTex = makeBlobTexture();
  const sqTex = makeSquareBlobTexture();
  for (const f of layout.foot) {
    const isRound = !!f.round;
    const w = isRound ? f.round * 2 + 3.2 : f.hx * 2 + 3.2;
    const d = isRound ? f.round * 2 + 3.2 : f.hz * 2 + 3.2;
    const m = new THREE.Mesh(
      new THREE.PlaneGeometry(w, d).rotateX(-Math.PI / 2),
      new THREE.MeshBasicMaterial({ map: isRound ? blobTex : sqTex, color: 0x3C5A2E, transparent: true, opacity: 0.38, depthWrite: false }),
    );
    m.position.set(f.x, GROUND_Y + 0.015, f.z);
    m.rotation.y = Math.atan2(f.s, f.c);
    m.renderOrder = 1;
    m.name = `blob:${f.id}`;
    group.add(m);
  }

  // ── 石板步道 ──
  const paths = buildPathLines(layout);
  const stones = [];
  const R = rng(4242);
  for (const line of paths) {
    const pts = resample(line, 0.92);
    for (let i = 0; i < pts.length; i++) {
      const p = pts[i], q = pts[Math.min(i + 1, pts.length - 1)], o = pts[Math.max(i - 1, 0)];
      const tx = q.x - o.x, tz = q.z - o.z, tl = Math.hypot(tx, tz) || 1;
      const nx = -tz / tl, nz = tx / tl;
      for (const side of [-1, 1]) {
        const off = side * (0.42 + (R() - 0.5) * 0.12) + (i % 2 ? 0.16 : -0.16);
        const x = p.x + nx * off + (R() - 0.5) * 0.12, z = p.z + nz * off + (R() - 0.5) * 0.12;
        if (insideFoot(x, z, 0.7)) continue;
        stones.push({ x, z, y: heightAt(x, z), s: 0.62 + R() * 0.3, r: R() * Math.PI, c: R() });
      }
    }
  }
  const stoneGeo = new THREE.CylinderGeometry(0.5, 0.54, 0.09, 7, 1).translate(0, 0.045, 0);
  stoneGeo.scale(1, 1, 0.82);
  const stoneMesh = new THREE.InstancedMesh(stoneGeo, new THREE.MeshLambertMaterial({ flatShading: true }), stones.length);
  const sCols = ['#D8D2C5', '#C9C2B4', '#E2DCCF', '#BDB7AA'].map((c) => new THREE.Color(c));
  const M = new THREE.Matrix4(), Q = new THREE.Quaternion(), S = new THREE.Vector3(), P = new THREE.Vector3(), E = new THREE.Euler();
  stones.forEach((st, i) => {
    E.set((R() - 0.5) * 0.04, st.r, (R() - 0.5) * 0.04);
    M.compose(P.set(st.x, st.y - 0.035, st.z), Q.setFromEuler(E), S.set(st.s, 1, st.s));
    stoneMesh.setMatrixAt(i, M);
    stoneMesh.setColorAt(i, sCols[Math.floor(st.c * sCols.length)]);
  });
  stoneMesh.receiveShadow = true;
  stoneMesh.name = 'stones';
  group.add(stoneMesh);

  // ── 树林 ──
  const pathPts = paths.flatMap((l) => resample(l, 2));
  const nearPath = (x, z) => { for (const p of pathPts) if (Math.abs(p.x - x) < 3 && Math.abs(p.z - z) < 3 && Math.hypot(p.x - x, p.z - z) < 2.6) return true; return false; };
  const species = makeSpecies();
  const inst = species.map(() => []);
  const TR = rng(9001);
  const CELL = 3.3;
  for (let gx = -FOREST_OUT; gx <= FOREST_OUT; gx += CELL) {
    for (let gz = -FOREST_OUT; gz <= FOREST_OUT; gz += CELL) {
      const x = gx + (TR() - 0.5) * CELL * 0.9, z = gz + (TR() - 0.5) * CELL * 0.9;
      const r = Math.hypot(x, z);
      if (r < FOREST_IN - 4 || r > FOREST_OUT + fbm(x * 0.05, z * 0.05, 5) * 20 || r > rimR(Math.atan2(x, z)) - 6) continue;
      const df = minFoot(x, z);
      if (df < 6.5 || minBelt(x, z) < 6 || nearPath(x, z)) continue;
      // 疏密：内缘稀疏（看得见地块），往外渐密；大尺度噪声挖出林间空地
      const clearing = fbm(x * 0.028, z * 0.028, 21);
      const edge = smooth(FOREST_IN - 4, FOREST_IN + 18, r) * smooth(6.5, 16, df);
      const dens = edge * smooth(0.36, 0.56, clearing);
      if (TR() > dens * 0.95 + 0.03) continue;
      // 树种成片分布：用另一层噪声决定这一片以哪种树为主
      const patch = fbm(x * 0.018, z * 0.018, 33);
      const k = TR();
      let sp;
      if (r < FOREST_IN + 8 && k < 0.45) sp = 3;                 // 林缘多灌木
      else if (patch < 0.42) sp = k < 0.7 ? 1 : (k < 0.88 ? 0 : 3);  // 松林片区
      else if (patch > 0.6) sp = k < 0.55 ? 2 : (k < 0.9 ? 0 : 4);   // 杨树+阔叶
      else sp = k < 0.6 ? 0 : (k < 0.8 ? 4 : (k < 0.92 ? 1 : 3));     // 阔叶混交
      const grow = 0.7 + 0.75 * smooth(FOREST_IN, 125, r);
      const s = (0.62 + TR() * 0.7) * grow * (sp === 3 ? 0.8 : 1);
      inst[sp].push({ x, z, y: heightAt(x, z), s, r: TR() * Math.PI * 2, tilt: (TR() - 0.5) * 0.08, c: TR(), sy: 0.88 + TR() * 0.3 });
    }
  }
  // 林缘零散点缀几棵小树（内圈地块之间的空地），避免树林像一圈墙
  for (let i = 0; i < 70; i++) {
    const a = TR() * Math.PI * 2, r = 40 + TR() * 16;
    const x = Math.sin(a) * r, z = Math.cos(a) * r;
    if (minFoot(x, z) < 5 || minBelt(x, z) < 5 || nearPath(x, z)) continue;
    const sp = TR() < 0.5 ? 3 : 4;
    inst[sp].push({ x, z, y: heightAt(x, z), s: 0.55 + TR() * 0.4, r: TR() * 6.28, tilt: 0, c: TR(), sy: 1 });
  }

  // 岸边一圈灌木（草地到断面的过渡），疏密随噪声
  for (let i = 0; i < 520; i++) {
    const a = TR() * Math.PI * 2, R = rimR(a);
    if (TR() > 0.35 + 0.65 * smooth(0.35, 0.6, fbm(Math.cos(a) * 6, Math.sin(a) * 6, 71))) continue;
    const r = R - 1.6 - TR() * TR() * 9;
    const x = Math.sin(a) * r, z = Math.cos(a) * r;
    inst[3].push({ x, z, y: heightAt(x, z) - lipDrop(R - r), s: 0.45 + TR() * 0.6, r: TR() * 6.28, tilt: (TR() - 0.5) * 0.1, c: TR(), sy: 0.8 + TR() * 0.3 });
  }

  let treeCount = 0, treeTris = 0;
  const shadowTex = blobTex;
  const allTrees = [];
  species.forEach((sp, i) => {
    const list = inst[i];
    if (!list.length) return;
    treeCount += list.length;
    for (const part of sp.parts) {
      const mesh = new THREE.InstancedMesh(part.geo, part.mat, list.length);
      list.forEach((t, j) => {
        E.set(t.tilt, t.r, t.tilt * 0.6);
        M.compose(P.set(t.x, t.y - 0.05, t.z), Q.setFromEuler(E), S.set(t.s, t.s * t.sy, t.s));
        mesh.setMatrixAt(j, M);
        if (part.colors) mesh.setColorAt(j, part.colors[Math.floor(t.c * part.colors.length)].clone().offsetHSL(0, 0, (t.c - 0.5) * 0.04));
      });
      mesh.name = `tree:${sp.name}:${part.name}`;
      mesh.receiveShadow = false;
      mesh.computeBoundingSphere();
      group.add(mesh);
      treeTris += (part.geo.index ? part.geo.index.count : part.geo.attributes.position.count) / 3 * list.length;
    }
    allTrees.push(...list.map((t) => ({ ...t, rad: sp.radius })));
  });
  // 树下软阴影
  const blobGeo = new THREE.PlaneGeometry(1, 1).rotateX(-Math.PI / 2);
  const treeBlob = new THREE.InstancedMesh(blobGeo, new THREE.MeshBasicMaterial({ map: shadowTex, color: 0x2F4A25, transparent: true, opacity: 0.32, depthWrite: false }), allTrees.length);
  allTrees.forEach((t, j) => {
    const d = t.rad * t.s * 2.4;
    M.compose(P.set(t.x + 0.4 * t.s, t.y + 0.03, t.z - 0.3 * t.s), Q.identity(), S.set(d, 1, d));
    treeBlob.setMatrixAt(j, M);
  });
  treeBlob.renderOrder = 1;
  treeBlob.name = 'treeBlobs';
  group.add(treeBlob);

  // ── 岸边草丛：细锥簇，约三成探出断面顶沿、往外垂 ──
  const tuftGeo = mergeGeometries([[0, 0, 0.42], [0.09, 0.05, 0.34], [-0.08, 0.06, 0.3], [0.02, -0.09, 0.36]].map(([x, z, h], k) =>
    new THREE.ConeGeometry(0.06, h, 4, 1, true).translate(0, h / 2, 0).rotateZ((k - 1.5) * 0.18).rotateX(z * 2).translate(x, 0, z)));
  const tufts = [];
  for (let i = 0; i < 1300; i++) {
    const a = TR() * Math.PI * 2, R = rimR(a);
    const over = TR() < 0.3;
    const d = over ? 0.05 + TR() * 0.3 : 0.3 + TR() * TR() * 4.5;
    const r = R - d, x = Math.sin(a) * r, z = Math.cos(a) * r;
    tufts.push({ x, z, y: heightAt(x, z) - lipDrop(d) - 0.03, a, s: 0.8 + TR() * 0.9, out: over ? 0.5 + TR() * 0.5 : (TR() - 0.5) * 0.3, c: TR() });
  }
  const tuftMesh = new THREE.InstancedMesh(tuftGeo, new THREE.MeshLambertMaterial({ flatShading: true, side: THREE.DoubleSide }), tufts.length);
  patchInstancedSway(tuftMesh.material, { base: 0, k: 0.12 });
  const tCols = ['#7FA266', '#8DB36E', '#6E9459', '#9CBB78'].map((c) => new THREE.Color(c));
  tufts.forEach((t, i) => {
    // 往外倒：绕切线方向转 t.out 弧度
    Q.setFromAxisAngle(P.set(Math.cos(t.a), 0, -Math.sin(t.a)), t.out);
    M.compose(P.set(t.x, t.y, t.z), Q, S.set(t.s, t.s, t.s));
    tuftMesh.setMatrixAt(i, M);
    tuftMesh.setColorAt(i, tCols[Math.floor(t.c * tCols.length)]);
  });
  tuftMesh.name = 'rimTufts';
  tuftMesh.computeBoundingSphere();
  group.add(tuftMesh);

  return { group, heightAt, groundAt, insideFoot, rimR, stats: { trees: treeCount, treeTris: Math.round(treeTris), stones: stones.length, tufts: tufts.length, islandR: ISLAND_R } };
}

// 步道走线：地块间的大环、中央大厅外环、8 条辐条、南侧出入口、去外协的支线
function buildPathLines(layout) {
  const lines = [];
  const arc = (r, a0, a1, step = 2) => {
    const pts = [];
    const n = Math.max(2, Math.ceil(Math.abs(a1 - a0) * r / step));
    for (let i = 0; i <= n; i++) { const a = a0 + (a1 - a0) * i / n; pts.push({ x: Math.sin(a) * r, z: Math.cos(a) * r }); }
    return pts;
  };
  const deg = Math.PI / 180;
  lines.push(arc(34, 0, Math.PI * 2));
  lines.push(arc(19.5, 0, Math.PI * 2));
  for (let k = 0; k < 8; k++) {
    const a = (22.5 + 45 * k) * deg;
    lines.push([{ x: Math.sin(a) * 19.5, z: Math.cos(a) * 19.5 }, { x: Math.sin(a) * 34, z: Math.cos(a) * 34 }]);
  }
  // 南侧两条出入口小径，弯进树林
  for (const a of [22.5, -22.5, 67.5, -67.5]) {
    const r0 = 34, r1 = 66, aa = a * deg, bend = (a > 0 ? 6 : -6) * deg;
    lines.push(catmull([0, 0.33, 0.66, 1].map((t) => {
      const r = r0 + (r1 - r0) * t, ang = aa + bend * Math.sin(t * Math.PI);
      return { x: Math.sin(ang) * r, z: Math.cos(ang) * r };
    }), 10));
  }
  // 去外协：从大环出发，连到三块圆盘，再在圆盘之间连一段
  const f = Object.fromEntries(layout.foot.map((x) => [x.id, x]));
  const edge = (p, toward, extra = 1.2) => {
    const dx = toward.x - p.x, dz = toward.z - p.z, l = Math.hypot(dx, dz);
    const rr = (p.round || p.hx) + extra;
    return { x: p.x + dx / l * rr, z: p.z + dz / l * rr };
  };
  if (f.clawd && f.pi && f.codex) {
    const ringW = { x: Math.sin(202.5 * deg) * 34, z: Math.cos(202.5 * deg) * 34 };
    const ringE = { x: Math.sin(157.5 * deg) * 34, z: Math.cos(157.5 * deg) * 34 };
    const cw = edge(f.clawd, { x: f.clawd.x - 8, z: f.clawd.z + 16 });
    const ce = edge(f.codex, { x: f.codex.x + 8, z: f.codex.z + 16 });
    lines.push(catmull([ringW, { x: ringW.x - 4, z: ringW.z - 7 }, cw], 10));
    lines.push(catmull([ringE, { x: ringE.x + 4, z: ringE.z - 7 }, ce], 10));
    const a1 = edge(f.clawd, f.pi), b1 = edge(f.pi, f.clawd);
    const a2 = edge(f.codex, f.pi), b2 = edge(f.pi, f.codex);
    lines.push(catmull([a1, { x: (a1.x + b1.x) / 2, z: (a1.z + b1.z) / 2 - 2.5 }, b1], 8));
    lines.push(catmull([a2, { x: (a2.x + b2.x) / 2, z: (a2.z + b2.z) / 2 - 2.5 }, b2], 8));
  }
  return lines;
}
function catmull(pts, perSeg) {
  const curve = new THREE.CatmullRomCurve3(pts.map((p) => new THREE.Vector3(p.x, 0, p.z)), false, 'centripetal');
  return curve.getPoints((pts.length - 1) * perSeg).map((v) => ({ x: v.x, z: v.z }));
}
function resample(line, step) {
  const out = [line[0]];
  let carry = 0;
  for (let i = 1; i < line.length; i++) {
    const a = line[i - 1], b = line[i];
    const L = Math.hypot(b.x - a.x, b.z - a.z);
    let d = step - carry;
    while (d <= L) { out.push({ x: a.x + (b.x - a.x) * d / L, z: a.z + (b.z - a.z) * d / L }); d += step; }
    carry = L - (d - step);
  }
  return out;
}

// ── 低多边形树种：每种由 2 个 InstancedMesh（树干 + 树冠）组成 ──
function makeSpecies() {
  const trunkMat = new THREE.MeshLambertMaterial({ color: '#8A6E58', flatShading: true });
  const crownMat = new THREE.MeshLambertMaterial({ flatShading: true });
  patchInstancedSway(trunkMat);
  patchInstancedSway(crownMat);
  const C = (...a) => a.map((c) => new THREE.Color(c));
  const blob = (r, x, y, z, sx = 1, sy = 1, sz = 1, d = 1) => new THREE.IcosahedronGeometry(r, d).scale(sx, sy, sz).translate(x, y, z);
  const lowpoly = (geos) => { const g = mergeGeometries(geos.map((x) => (x.index ? x.toNonIndexed() : x))); g.computeVertexNormals(); return g; };
  return [
    { name: 'round', radius: 1.6, parts: [
      { name: 'trunk', geo: new THREE.CylinderGeometry(0.15, 0.24, 1.9, 6).translate(0, 0.95, 0), mat: trunkMat },
      { name: 'crown', geo: lowpoly([blob(1.45, 0, 2.75, 0, 1, 0.95, 1), blob(0.95, 0.85, 2.35, 0.3, 1, 1, 1, 0), blob(0.85, -0.7, 2.45, -0.45, 1, 1, 1, 0)]), mat: crownMat,
        colors: C('#8DB36E', '#9CBF78', '#7FA96A', '#A9C27C', '#8EAF80') },
    ] },
    { name: 'pine', radius: 1.3, parts: [
      { name: 'trunk', geo: new THREE.CylinderGeometry(0.12, 0.2, 1.2, 6).translate(0, 0.6, 0), mat: trunkMat },
      { name: 'crown', geo: lowpoly([
        new THREE.ConeGeometry(1.5, 1.9, 7).translate(0, 1.85, 0),
        new THREE.ConeGeometry(1.15, 1.6, 7).translate(0, 2.85, 0),
        new THREE.ConeGeometry(0.78, 1.35, 7).translate(0, 3.75, 0)]), mat: crownMat,
        colors: C('#6E9A74', '#5F8C6C', '#7AA27B', '#688F78') },
    ] },
    { name: 'poplar', radius: 0.9, parts: [
      { name: 'trunk', geo: new THREE.CylinderGeometry(0.11, 0.17, 1.6, 6).translate(0, 0.8, 0), mat: trunkMat },
      { name: 'crown', geo: lowpoly([blob(0.95, 0, 3.4, 0, 0.9, 2.1, 0.9)]), mat: crownMat,
        colors: C('#A3BE70', '#B2C47A', '#94B46A', '#C2C682') },
    ] },
    { name: 'bush', radius: 0.9, parts: [
      { name: 'crown', geo: lowpoly([blob(0.7, 0, 0.45, 0, 1, 0.75, 1, 0), blob(0.55, 0.6, 0.35, 0.2, 1, 0.8, 1, 0), blob(0.5, -0.45, 0.32, -0.35, 1, 0.8, 1, 0)]), mat: crownMat,
        colors: C('#8DB36E', '#9DBB76', '#7FA36C', '#B4C482') },
    ] },
    { name: 'oak', radius: 2.0, parts: [
      { name: 'trunk', geo: new THREE.CylinderGeometry(0.2, 0.32, 2.2, 6).translate(0, 1.1, 0), mat: trunkMat },
      { name: 'crown', geo: lowpoly([blob(1.7, 0, 3.2, 0, 1.15, 0.8, 1.15), blob(1.1, 1.1, 2.9, 0.6, 1, 0.85, 1, 0), blob(1.0, -1.0, 3.0, -0.7, 1, 0.85, 1, 0), blob(0.9, 0.2, 3.9, -0.3, 1, 1, 1, 0)]), mat: crownMat,
        colors: C('#86A96A', '#7C9F66', '#93B277', '#A0B06E') },
    ] },
  ];
}

function makeBlobTexture() {
  const c = document.createElement('canvas');
  c.width = c.height = 128;
  const g = c.getContext('2d');
  const grad = g.createRadialGradient(64, 64, 0, 64, 64, 64);
  grad.addColorStop(0, 'rgba(255,255,255,1)');
  grad.addColorStop(0.55, 'rgba(255,255,255,0.55)');
  grad.addColorStop(1, 'rgba(255,255,255,0)');
  g.fillStyle = grad;
  g.fillRect(0, 0, 128, 128);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}
function makeSquareBlobTexture() {
  const c = document.createElement('canvas');
  c.width = c.height = 128;
  const g = c.getContext('2d');
  g.filter = 'blur(9px)';
  g.fillStyle = '#fff';
  g.beginPath();
  g.roundRect(18, 18, 92, 92, 14);
  g.fill();
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}
