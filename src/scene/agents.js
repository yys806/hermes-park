import * as THREE from 'three';
import { roundedBox, makeRoundedSlab } from '../utils/roundedBox.js';
import { mat, glowMat } from '../utils/materials.js';
import { addCircleShadow, addContactShadow } from '../utils/contactShadow.js';
import { agents, layout, palette } from '../config.js';

// 小圆台尺寸：半径 1.3，厚 0.22，顶面高度 PT
const PED_R = 1.3;
const PED_H = 0.22;
const PT = PED_H;

// 外协小岛台：边长 3.4，厚 0.34，俯视圆角 0.18；顶面 y=0 与主地台顶面齐平
const ISLAND_W = 3.4;
const ISLAND_H = 0.34;
const ISLAND_R = 0.18;
// 外协模型本体放大倍数（世界尺度）
const AGENT_SCALE = 1.75;
// 岛台 + 圆台的缩放：岛台世界边长固定 4.0，不跟着本体放大到 5.95
const BASE_SCALE = 4.0 / ISLAND_W;

// 统一的圆角块：圆角半径按短边比例取，默认 13.5%（落在 12%~15%）
function rb(w, h, d, material, ratio = 0.135) {
  const m = roundedBox(w, h, d, Math.min(w, h, d) * ratio, material, 3);
  m.castShadow = true;
  m.receiveShadow = true;
  return m;
}

// 颜色插值（返回 hex，交给 mat() 缓存）
function mixHex(a, b, k) {
  return new THREE.Color(a).lerp(new THREE.Color(b), k).getHex();
}

// ── 脚下圆台：圆角圆柱 + 台面浅色环线 + 圆形接触阴影 ──
function buildPedestal(parent, tint) {
  const pedColor = mixHex(palette.cream, tint, 0.25);

  // 车削轮廓：底边、下圆角、侧壁、上圆角、顶面，得到边缘圆润的圆台
  const rr = 0.06;
  const pts = [new THREE.Vector2(0, 0), new THREE.Vector2(PED_R - rr, 0)];
  for (let i = 1; i <= 6; i++) {
    const a = -Math.PI / 2 + (i / 6) * (Math.PI / 2);
    pts.push(new THREE.Vector2(PED_R - rr + Math.cos(a) * rr, rr + Math.sin(a) * rr));
  }
  for (let i = 0; i <= 6; i++) {
    const a = (i / 6) * (Math.PI / 2);
    pts.push(new THREE.Vector2(PED_R - rr + Math.cos(a) * rr, PED_H - rr + Math.sin(a) * rr));
  }
  pts.push(new THREE.Vector2(0, PED_H));
  const ped = new THREE.Mesh(new THREE.LatheGeometry(pts, 48), mat(pedColor));
  ped.castShadow = true;
  ped.receiveShadow = true;
  parent.add(ped);

  // 台面环线刻线（贴面薄片，不投影）
  const ringGeo = new THREE.RingGeometry(1.0, 1.045, 64);
  ringGeo.rotateX(-Math.PI / 2);
  const ring = new THREE.Mesh(ringGeo, mat(mixHex(pedColor, palette.white, 0.7)));
  ring.position.y = PT + 0.003;
  ring.castShadow = false;
  ring.receiveShadow = true;
  parent.add(ring);

  addCircleShadow(parent, PED_R + 0.25, 0.006, 0.22);
}

// ── 外协独立小岛台：泥土底座 + 草皮顶层，顶面 y=0；下方垫接触阴影 ──
function buildIsland(parent) {
  // 泥土层：略内缩 0.02，让草皮层在边缘压出一圈细唇边，同时避免侧面共面闪烁
  const soilH = 0.26;
  const soil = new THREE.Mesh(
    makeRoundedSlab(ISLAND_W - 0.04, soilH, ISLAND_W - 0.04, ISLAND_R - 0.02, 0.05, 6),
    mat(palette.soil),
  );
  soil.position.y = -ISLAND_H + soilH / 2;
  soil.castShadow = true;
  soil.receiveShadow = true;
  parent.add(soil);

  // 草皮层：0.1 厚，底部插入泥土层 0.02；顶面比泥土亮一档
  const grassH = 0.1;
  const grass = new THREE.Mesh(
    makeRoundedSlab(ISLAND_W, grassH, ISLAND_W, ISLAND_R, 0.04, 6),
    mat(mixHex(palette.grass, palette.white, 0.06)),
  );
  grass.position.y = -grassH / 2;
  grass.castShadow = true;
  grass.receiveShadow = true;
  parent.add(grass);

  // 接触阴影：比岛台大 8%，贴在岛台底面
  const sw = ISLAND_W * 1.08;
  addContactShadow(parent, sw, sw, -ISLAND_H + 0.005, 0.13, ISLAND_R * 1.08);
}

// ── A. Clawd：Claude Code 像素螃蟹（宽扁身体 + 分节钳子 + 宽距方眼 + 四条短腿）──
function buildClawd(color) {
  const body = new THREE.Group();
  const shell = mat(color);
  const eyeMat = mat(palette.brown);
  const dotMat = mat(0x1a120c);

  // 四条短腿：一排站在台面上
  const legH = 0.34;
  for (const x of [-0.55, -0.2, 0.2, 0.55]) {
    const leg = rb(0.2, legH, 0.24, shell, 0.22);
    leg.position.set(x, PT + legH / 2, 0.05);
    body.add(leg);
  }

  // 身体：一整块宽扁圆角体（宽 1.4 > 高 0.95 > 深 0.75），腿顶插入 0.04
  const BW = 1.4, BH = 0.95, BD = 0.75;
  const by = PT + legH - 0.04 + BH / 2;
  const torso = rb(BW, BH, BD, shell, 0.2);
  torso.position.y = by;
  body.add(torso);

  // 钳子：内段（关节）+ 外段（钳头），两段之间留 0.05 分缝，外段略外翻上举
  for (const s of [-1, 1]) {
    const inner = rb(0.18, 0.26, 0.4, shell, 0.2);
    inner.position.set(s * 0.77, by + 0.05, 0);
    body.add(inner);

    const outer = rb(0.28, 0.4, 0.5, shell, 0.2);
    outer.position.set(s * 1.05, by + 0.13, 0);
    outer.rotation.z = -s * 0.12;
    body.add(outer);
  }

  // 眼睛：方形、间距拉宽，深色；眼内再叠一颗更小的深色点
  const front = BD / 2;
  for (const s of [-1, 1]) {
    const eye = rb(0.16, 0.22, 0.06, eyeMat, 0.15);
    eye.position.set(s * 0.38, by + 0.14, front + 0.015);
    body.add(eye);

    const dot = rb(0.07, 0.07, 0.03, dotMat, 0.15);
    dot.position.set(s * 0.38 + 0.03, by + 0.19, front + 0.055);
    body.add(dot);
  }

  // 头顶淡淡的光点：独立材质实例（克隆自 glowMat），用于明灭动画；
  // 半透明发光片不投影，避免在身体上压出实心阴影
  const glowMaterial = glowMat(0xffd9c2, 0.45).clone();
  glowMaterial.transparent = true;
  const glow = roundedBox(0.3, 0.05, 0.3, 0.02, glowMaterial, 3);
  glow.position.y = by + BH / 2 + 0.24;
  glow.castShadow = false;
  glow.receiveShadow = false;
  body.add(glow);

  return { body, glow };
}

// ── B. Pi：方块化立体「P」+ 独立「i」点（前层奶白、后层浅灰做暗面）──
function buildPi() {
  const body = new THREE.Group();
  const front = mat(palette.white);
  const back = mat(0xe2dfd8);

  // [x中心, y中心, 宽, 高]，y 以台面为 0；四段拼出带方孔的 P
  const pieces = [
    [-0.37, 0.80, 0.36, 1.60], // 竖笔
    [0.18, 1.43, 0.78, 0.34],  // 上横
    [0.40, 1.01, 0.34, 0.54],  // 碗部右竖（与上横、中横围出方孔）
    [0.18, 0.59, 0.78, 0.34],  // 中横
    [0.40, 0.19, 0.30, 0.30],  // i 的点：独立浮在右下方
  ];

  for (const [x, y, w, h] of pieces) {
    // 前层：奶白主体
    const f = rb(w, h, 0.3, front);
    f.position.set(x, PT + y, 0.06);
    body.add(f);

    // 后层：浅灰暗面，四周内缩 0.03，形成厚度台阶
    const b = rb(w - 0.06, h - 0.06, 0.24, back);
    b.position.set(x, PT + y, -0.08);
    body.add(b);
  }

  return { body };
}

// ── C. Codex：蓝紫渐变云 + 白色 >_ 终端提示符 ──
// 渐变三段色：左上浅紫蓝 → 中间 → 右下宝蓝
const GRAD = [new THREE.Color(0xa5b4ff), new THREE.Color(0x6e86ff), new THREE.Color(0x2b3bff)];
function gradAt(s) {
  s = THREE.MathUtils.clamp(s, 0, 1);
  return s < 0.5
    ? GRAD[0].clone().lerp(GRAD[1], s * 2)
    : GRAD[1].clone().lerp(GRAD[2], (s - 0.5) * 2);
}

function buildCodex() {
  const body = new THREE.Group();
  const cloud = new THREE.Group();
  const sphere = new THREE.SphereGeometry(1, 28, 20);

  // 云块 [x, y, 半径, z 压扁比]：7 个外缘凸起左右对称 + 1 个核心块（底部中央也露出圆弧）
  const CORE = { x: 0, y: -0.08, r: 0.62, zs: 0.48 };
  const blobs = [
    [0, 0.40, 0.46, 0.55],     // 顶
    [-0.50, 0.24, 0.38, 0.55], // 左上
    [0.50, 0.24, 0.38, 0.55],  // 右上
    [-0.80, -0.10, 0.32, 0.55],// 左
    [0.80, -0.10, 0.32, 0.55], // 右
    [-0.44, -0.44, 0.34, 0.55],// 左下
    [0.44, -0.44, 0.34, 0.55], // 右下
  ];

  // 按位置取色：s = 0 在左上，s = 1 在右下；外缘略压暗，核心略提亮
  for (const [x, y, r, zs] of blobs) {
    const c = gradAt(0.5 + (x - y) / 2).multiplyScalar(0.95);
    const m = new THREE.Mesh(sphere, mat(c.getHex()));
    m.position.set(x, y, 0);
    m.scale.set(r, r, r * zs);
    m.castShadow = true;
    m.receiveShadow = true;
    cloud.add(m);
  }
  const coreColor = gradAt(0.5 + (CORE.x - CORE.y) / 2).lerp(GRAD[0], 0.2);
  const core = new THREE.Mesh(sphere, mat(coreColor.getHex()));
  core.position.set(CORE.x, CORE.y, 0);
  core.scale.set(CORE.r, CORE.r, CORE.r * CORE.zs);
  core.castShadow = true;
  core.receiveShadow = true;
  cloud.add(core);

  // 核心块前表面的 z（符号贴在这一层上）
  const surfZ = (x, y) => {
    const dx = x - CORE.x, dy = y - CORE.y;
    return Math.sqrt(Math.max(CORE.r * CORE.r - dx * dx - dy * dy, 0)) * CORE.zs;
  };

  // >_ 符号：正中央偏下，近白发光材质
  const symMat = glowMat(0xffffff, 1);
  const T = 0.09; // 笔画粗细
  const stroke = (len, cx, cy, rotZ) => {
    const s = roundedBox(len, T, 0.1, T * 0.45, symMat, 3); // 圆角接近半粗细，两端圆润
    s.position.set(cx, cy, surfZ(cx, cy) + 0.01);
    s.rotation.z = rotZ;
    s.castShadow = true;
    s.receiveShadow = true;
    cloud.add(s);
  };
  const ang = Math.atan2(0.13, 0.22);
  stroke(0.3, -0.23, -0.135, -ang); // 「>」上笔：向右下
  stroke(0.3, -0.23, -0.265, ang);  // 「>」下笔：向右上
  stroke(0.3, 0.15, -0.33, 0);      // 「_」底部短横

  // 顶部偏左的浅色高光块：沿顶块圆弧切向贴放
  const hl = rb(0.3, 0.07, 0.16, mat(0xe8ecff), 0.3);
  hl.position.set(-0.3, 0.72, 0.1);
  hl.rotation.z = 0.77;
  cloud.add(hl);

  // 整朵云缩到 0.9，底边离台面 0.12 浮空
  const S = 0.9;
  cloud.scale.setScalar(S);
  cloud.position.y = PT + 0.12 + 0.78 * S;
  body.add(cloud);

  return { body };
}

export default function build(ctx) {
  const root = new THREE.Group();
  root.name = 'agents';
  ctx.scene.add(root);

  const builders = { clawd: buildClawd, pi: buildPi, codex: buildCodex };
  const phases = { clawd: 0, pi: 2.1, codex: 4.2 };

  const units = [];
  let clawdGlow = null;

  for (const a of agents) {
    const fn = builders[a.type];
    if (!fn) continue;

    const g = new THREE.Group();
    g.name = `agent-${a.id}`;
    // 方位角约定与 factories.js 一致，位置仍按角度公式算；
    // 外协正面（眼睛 / P 前层 / >_）在 +Z，不再旋转，统一朝向镜头
    const rad = a.angle * Math.PI / 180;
    g.position.set(Math.cos(rad) * layout.outerRadius, 0, Math.sin(rad) * layout.outerRadius);
    g.rotation.y = 0;
    g.scale.setScalar(BASE_SCALE);

    // 小岛台顶面 y=0，圆台直接坐在岛台顶面上
    buildIsland(g);
    buildPedestal(g, a.type === 'pi' ? palette.metal : a.color);
    const unit = fn(a.color);
    // 本体单独再放大到世界 AGENT_SCALE 倍；本体内部以台面 PT 为脚底，
    // 下移 PT·(k-1) 让脚底仍落在圆台顶面上
    const k = AGENT_SCALE / BASE_SCALE;
    const bodyScale = new THREE.Group();
    bodyScale.scale.setScalar(k);
    bodyScale.position.y = PT * (1 - k);
    bodyScale.add(unit.body);
    g.add(bodyScale);
    if (unit.glow) clawdGlow = unit.glow;

    units.push({ body: unit.body, phase: phases[a.type] ?? 0 });
    root.add(g);
  }

  return {
    update(dt, t) {
      // 极轻呼吸浮动，幅度 0.03，相位错开
      for (const u of units) u.body.position.y = Math.sin(t * 1.4 + u.phase) * 0.03;
      // Clawd 头顶光点缓慢明灭
      if (clawdGlow) clawdGlow.material.opacity = 0.25 + 0.3 * (0.5 + 0.5 * Math.sin(t * 1.1));
    },
  };
}
