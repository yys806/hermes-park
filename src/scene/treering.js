import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { layout, factories } from '../config.js';

// 外围景观：Kenney Nature Kit 模型铺环形树林 + 灌木 + 前景框景 + 地被草。
// 模型异步加载，加载完之前场景照常运行；每个模型只加载一次，之后 clone 节点（几何共享），
// 材质按「原材质 × 4 种基础色 × 3 档距离褪色」缓存复用，不改原始材质，也不逐棵 clone。

const SEED = 46201;
const R_IN = 19;                  // 树林内半径：以内一棵树都不放
const R_OUT = layout.treeRingOuter; // 46
const TREE_H = 4.2;               // tree_default 归一化后的高度（世界单位），其余模型按同一比例缩放，保留相对大小
const TILT = 0.03;                // 树干随机倾斜上限（弧度），绕 X / Z 各自独立

// 4 种基础色：色相 ±0.02，附带一点亮度差（替代原来的 4 个亮度档）。每个实例按 index % 4 取
const BASE_TINTS = [
  { h: -0.02, l: -0.02 },
  { h: -0.007, l: 0.01 },
  { h: 0.007, l: -0.01 },
  { h: 0.02, l: 0.02 },
];

// 3 档距离褪色：越外越亮、越灰，与雾和背景色衔接；最外一档再降一点不透明度
const FADE_TIERS = [
  { light: 0.02, sat: 0 },                   // r < 28（含内侧地被草）
  { light: 0.08, sat: 0.15 },                // 28 ≤ r < 36
  { light: 0.16, sat: 0.35, opacity: 0.85 }, // r ≥ 36
];
const fadeTier = (r) => (r < 28 ? 0 : r < 36 ? 1 : 2);

const TREE_TABLE = [
  ['tree_default', 14],
  ['tree_default_dark', 10],
  ['tree_detailed', 12],
  ['tree_detailed_dark', 9],
  ['tree_oak', 11],
  ['tree_oak_dark', 8],
  ['tree_cone', 8],
  ['tree_cone_dark', 6],
  ['tree_fat', 7],
  ['tree_fat_darkh', 5],
  ['tree_blocks', 5],
  ['tree_palm', 3],
];
const BUSH_NAMES = ['plant_bush', 'plant_bushLarge', 'plant_bushSmall'];
const FG_NAMES = ['tree_detailed', 'tree_oak'];
const GRASS_NAMES = ['grass', 'grass_large'];
const ALL_NAMES = [...new Set([...TREE_TABLE.map(([n]) => n), ...BUSH_NAMES, ...FG_NAMES, ...GRASS_NAMES])];

// 固定种子随机（mulberry32）
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

const lerp = THREE.MathUtils.lerp;
const TAU = Math.PI * 2;

// 环形内按面积均匀取半径（否则内圈会偏密）
const ringR = (r0, r1, u) => Math.sqrt(lerp(r0 * r0, r1 * r1, u));

// 加载全部模型：失败的 console.warn 后跳过，返回 name → { proto, reach }
// proto 已把底部对齐到 y=0、水平居中，并按统一比例缩放；reach 为缩放后水平半宽
async function loadModels() {
  const loader = new GLTFLoader();
  const load = (name) => new Promise((res, rej) =>
    loader.load(`./vendor/models/${name}.glb`, (g) => res(g.scene), undefined, rej));

  const scenes = await Promise.all(ALL_NAMES.map((name) =>
    load(name).catch((err) => {
      console.warn(`[treering] 模型 ${name} 加载失败，跳过`, err);
      return null;
    })));

  const boxes = {};
  ALL_NAMES.forEach((name, i) => {
    if (scenes[i]) boxes[name] = { scene: scenes[i], box: new THREE.Box3().setFromObject(scenes[i]) };
  });

  // 统一比例：以 tree_default 的高度为基准；它缺失时退到任意一棵已加载的树
  const ref = boxes.tree_default ?? TREE_TABLE.map(([n]) => boxes[n]).find(Boolean);
  if (!ref) return {};
  const refH = ref.box.max.y - ref.box.min.y;
  const unit = refH > 0 ? TREE_H / refH : 1;

  const models = {};
  const size = new THREE.Vector3();
  const center = new THREE.Vector3();
  for (const [name, { scene, box }] of Object.entries(boxes)) {
    box.getSize(size);
    box.getCenter(center);
    scene.scale.setScalar(unit);
    scene.position.set(-center.x * unit, -box.min.y * unit, -center.z * unit);
    const proto = new THREE.Group();
    proto.add(scene);
    models[name] = { proto, reach: Math.max(size.x, size.z) * 0.5 * unit };
  }
  return models;
}

// 材质变体缓存：同名同色的原材质 × 基础色 × 褪色档 只建一份（每个原材质最多 12 份，与树的数量无关）
const matCache = new Map();
function variantMat(m, base, tier) {
  if (!m.color) return m;
  const key = `${m.name}|${m.color.getHexString()}|${base}|${tier}`;
  let out = matCache.get(key);
  if (!out) {
    const b = BASE_TINTS[base];
    const f = FADE_TIERS[tier];
    out = m.clone();
    out.color.offsetHSL(b.h, -f.sat, b.l + f.light);
    if (f.opacity !== undefined) {
      out.transparent = true;
      out.opacity = f.opacity;
    }
    matCache.set(key, out);
  }
  return out;
}

// 放一个模型实例：克隆节点（几何共享）、按距离选褪色档换成变体材质、开阴影，静态物体关掉矩阵自动更新
// base：基础色序号（0~3）；tx / tz：绕 X / Z 的轻微倾斜
function spawn(g, model, base, x, z, s, yaw, tx = 0, tz = 0) {
  const tier = fadeTier(Math.hypot(x, z));
  const o = model.proto.clone(true);
  o.position.set(x, 0, z);
  o.rotation.set(tx, yaw, tz);
  o.scale.setScalar(s);
  o.traverse((n) => {
    if (n.isMesh) {
      n.castShadow = true;
      n.receiveShadow = true;
      n.material = Array.isArray(n.material)
        ? n.material.map((m) => variantMat(m, base, tier))
        : variantMat(n.material, base, tier);
    }
    n.updateMatrix();
    n.matrixAutoUpdate = false;
  });
  g.add(o);
}

// 按权重挑模型，缺失的模型自动排除
function weightedPick(table, models, rand) {
  const u = rand();
  const avail = table.filter(([n]) => models[n]);
  if (!avail.length) return null;
  let left = u * avail.reduce((sum, [, w]) => sum + w, 0);
  for (const [n, w] of avail) {
    if ((left -= w) < 0) return models[n];
  }
  return models[avail[avail.length - 1][0]];
}
const uniformPick = (names, models, rand) => weightedPick(names.map((n) => [n, 1]), models, rand);

// 随机倾斜 ±TILT
const tilt = (rand) => (rand() * 2 - 1) * TILT;

// 树环：三个同心带只控制密度（内稀外密）；每带角度分层抖动，避免成团或留大缺口。
// 尺寸连续随机 0.7~2.2：一半权重给距离（越外越大），一半纯随机，不再按带分档跳变
function scatterTrees(g, models) {
  const rand = rng(SEED + 1);
  // 每环 55 / 85 / 130 的比例按总数 280 加权
  const bands = [
    { r0: R_IN, r1: 28, count: 57 },
    { r0: 28, r1: 36, count: 88 },
    { r0: 36, r1: R_OUT, count: 135 },
  ];
  let n = 0;
  let idx = 0;
  for (const b of bands) {
    const phase = rand() * TAU;
    for (let i = 0; i < b.count; i++, idx++) {
      const model = weightedPick(TREE_TABLE, models, rand);
      const a = phase + ((i + 0.15 + rand() * 0.7) / b.count) * TAU;
      let r = ringR(b.r0, b.r1, rand());
      const d = (r - R_IN) / (R_OUT - R_IN);
      const s = 0.7 + (0.5 * d + 0.5 * rand()) * 1.5;
      const yaw = rand() * TAU;
      const tx = tilt(rand);
      const tz = tilt(rand);
      if (!model) continue;
      r = Math.max(r, R_IN + model.reach * s); // 树冠外沿也不进 R_IN
      spawn(g, model, idx % 4, Math.cos(a) * r, Math.sin(a) * r, s, yaw, tx, tz);
      n++;
    }
  }
  return n;
}

// 底层灌木：同一环形区域撒满，填树与树之间的缝
function scatterBushes(g, models) {
  const rand = rng(SEED + 2);
  let n = 0;
  for (let i = 0; i < 180; i++) {
    const model = uniformPick(BUSH_NAMES, models, rand);
    const a = rand() * TAU;
    let r = ringR(R_IN, R_OUT, rand());
    const s = lerp(0.9, 1.8, rand());
    const yaw = rand() * TAU;
    if (!model) continue;
    r = Math.max(r, R_IN + model.reach * s);
    spawn(g, model, i % 4, Math.cos(a) * r, Math.sin(a) * r, s, yaw);
    n++;
  }
  return n;
}

// 前景框景：画面下方一排大树，挡住下半画幅，形成「从林中看园区」的纵深；同样按距离褪色
function scatterForeground(g, models) {
  const rand = rng(SEED + 3);
  const count = 35;
  let n = 0;
  for (let i = 0; i < count; i++) {
    // detailed / oak 交替，各占一半；缺一种时用另一种
    const model = models[FG_NAMES[i % 2]] ?? models[FG_NAMES[(i + 1) % 2]];
    const x = -38 + ((i + 0.1 + rand() * 0.8) / count) * 76;
    const z = 30 + rand() * 10;
    const s = lerp(1.6, 2.2, rand());
    const yaw = rand() * TAU;
    const tx = tilt(rand);
    const tz = tilt(rand);
    if (!model) continue;
    spawn(g, model, i % 4, x, z, s, yaw, tx, tz);
    n++;
  }
  return n;
}

// 地被草：半径 6~20 的地面，避开每座工厂中心 4 以内
function scatterGrass(g, models) {
  const rand = rng(SEED + 4);
  const centers = factories.map((f) => {
    const rad = f.angle * Math.PI / 180;
    return [Math.cos(rad) * layout.ringRadius, Math.sin(rad) * layout.ringRadius];
  });
  const clear2 = 4 * 4;
  const target = 150;
  let n = 0;
  for (let tries = 0; n < target && tries < target * 20; tries++) {
    const model = uniformPick(GRASS_NAMES, models, rand);
    const a = rand() * TAU;
    const r = ringR(6, 20, rand());
    const s = lerp(0.7, 1.3, rand());
    const yaw = rand() * TAU;
    if (!model) return n;
    const x = Math.cos(a) * r;
    const z = Math.sin(a) * r;
    if (centers.some(([cx, cz]) => (x - cx) ** 2 + (z - cz) ** 2 < clear2)) continue;
    spawn(g, model, n % 4, x, z, s, yaw);
    n++;
  }
  return n;
}

export default function build(ctx) {
  const g = new THREE.Group();
  g.name = 'treering';
  ctx.scene.add(g);

  loadModels()
    .then((models) => {
      if (!Object.keys(models).length) {
        console.warn('[treering] 没有可用的树模型，外围景观跳过');
        return;
      }
      const trees = scatterTrees(g, models);
      const bushes = scatterBushes(g, models);
      const fg = scatterForeground(g, models);
      const grass = scatterGrass(g, models);
      console.info(`[treering] 树 ${trees + fg} 棵（环 ${trees} + 前景 ${fg}），灌木 ${bushes}，草 ${grass}，变体材质 ${matCache.size} 份`);
    })
    .catch((err) => console.warn('[treering] 外围景观铺设失败，跳过', err));

  return {
    update(dt, t) { /* 静态 */ },
  };
}
