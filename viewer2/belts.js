// 园区传送带：按《园区共性规范》第一节汇总段规格程序生成。
// 走线 = 两端接口位置 + 出带方向 → 三次贝塞尔（大曲率圆弧过渡），按弧长等距采样后扫掠截面。
import * as THREE from 'three';

export const SPEC = {
  width: 0.90,        // 带面宽
  height: 0.55,       // 带面离地高（顶面）
  thick: 0.06,        // 带面厚
  guardH: 0.12,       // 挡边高出带面
  guardT: 0.04,       // 挡边厚
  legSize: 0.08,      // 支腿方柱
  legStep: 1.5,       // 支腿间距
  pad: [0.20, 0.20, 0.04],
  flange: 1.00,       // 法兰方环外边长
  flangeT: 0.05,      // 法兰厚
  groove: 0.12,       // 横向滚筒纹间距
  colors: { bed: '#5A5F66', guard: '#A8ADB3', leg: '#8C9196', flange: '#B4B9BF' },
};

const STEP = 0.1;           // 采样间距（米）
const SPEED = 0.9;          // 货箱速度 m/s（全园统一）
const CARGO_GAP = 2.6;      // 货箱间距

let shared = null;
function materials() {
  if (shared) return shared;
  const c = SPEC.colors;
  shared = {
    bedTop: new THREE.MeshLambertMaterial({ map: makeGrooveTexture() }),
    bed: new THREE.MeshLambertMaterial({ color: c.bed }),
    guard: new THREE.MeshLambertMaterial({ color: c.guard }),
    leg: new THREE.MeshLambertMaterial({ color: c.leg }),
    flange: new THREE.MeshLambertMaterial({ color: c.flange }),
    bolt: new THREE.MeshLambertMaterial({ color: '#7E848B' }),
    cargo: new THREE.MeshLambertMaterial({ color: 0xffffff, emissive: 0x000000 }),
    dot: new THREE.MeshBasicMaterial({ color: '#7FE3F0', toneMapped: false }),
  };
  return shared;
}

// 带面横向滚筒纹：每 0.12 m 一道浅槽（槽色略深 + 一侧高光，模拟 0.008 深的凹槽）
function makeGrooveTexture() {
  const c = document.createElement('canvas');
  c.width = 8; c.height = 64;
  const g = c.getContext('2d');
  g.fillStyle = SPEC.colors.bed; g.fillRect(0, 0, 8, 64);
  g.fillStyle = '#474B51'; g.fillRect(0, 0, 8, 6);
  g.fillStyle = '#6C7178'; g.fillRect(0, 6, 8, 2);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.anisotropy = 4;
  return t;
}

// a, b: { pos: Vector3(world, y=带面顶), dir: Vector3(水平单位向量，指向带子延伸方向) }
// a.dir 从起点往外；b.dir 是终点接口的出带方向（指向接口外），带子沿 -b.dir 进入接口
export function planBelt(a, b) {
  const p0 = a.pos.clone().setY(0), p3 = b.pos.clone().setY(0);
  const chord = p0.distanceTo(p3);
  const L = chord * 0.38;
  const curve = new THREE.CubicBezierCurve3(
    p0, p0.clone().addScaledVector(a.dir, L), p3.clone().addScaledVector(b.dir, L), p3);
  const approx = curve.getLength();
  const n = Math.max(8, Math.ceil(approx / STEP));
  const pts = curve.getSpacedPoints(n);
  // 弧长
  const s = [0];
  for (let i = 1; i < pts.length; i++) s.push(s[i - 1] + pts[i].distanceTo(pts[i - 1]));
  const len = s[s.length - 1];
  // 高度：两端贴合接口实测高度，中段回到规范 0.55，坡段 smoothstep 过渡
  const y0 = a.pos.y, y1 = b.pos.y, cruise = SPEC.height;
  const ramp = Math.min(3.2, len / 3);
  const sm = (x) => x * x * (3 - 2 * x);
  for (let i = 0; i < pts.length; i++) {
    const k0 = 1 - sm(Math.min(1, s[i] / ramp));
    const k1 = sm(Math.max(0, Math.min(1, (s[i] - (len - ramp)) / ramp)));
    pts[i].y = cruise + (y0 - cruise) * k0 + (y1 - cruise) * k1;
  }
  // 局部坐标架：切线 t、水平侧向 side、上向 up
  const frames = pts.map((p, i) => {
    const pa = pts[Math.max(0, i - 1)], pb = pts[Math.min(pts.length - 1, i + 1)];
    const t = pb.clone().sub(pa).normalize();
    const side = new THREE.Vector3().crossVectors(t, THREE.Object3D.DEFAULT_UP).normalize();
    const up = new THREE.Vector3().crossVectors(side, t).normalize();
    return { p, t, side, up, s: s[i] };
  });
  // 首尾切线锁定为接口方向，保证与接口对正
  frames[0].t.copy(a.dir); frames[frames.length - 1].t.copy(b.dir).negate();
  for (const f of [frames[0], frames[frames.length - 1]]) {
    f.side.crossVectors(f.t, THREE.Object3D.DEFAULT_UP).normalize();
    f.up.crossVectors(f.side, f.t).normalize();
  }
  // 最小转弯半径（自检用）
  let minR = Infinity;
  for (let i = 2; i < pts.length - 2; i += 2) {
    const A = pts[i - 2], B = pts[i], C = pts[i + 2];
    const ab = A.distanceTo(B), bc = B.distanceTo(C), ca = C.distanceTo(A);
    const area = Math.abs((B.x - A.x) * (C.z - A.z) - (C.x - A.x) * (B.z - A.z)) / 2;
    if (area > 1e-6) minR = Math.min(minR, (ab * bc * ca) / (4 * area));
  }
  return { frames, len, minR };
}

// 沿采样帧扫掠一个矩形截面（x: 侧向偏移区间，y: 相对带面顶的高度区间），返回带 groups 的几何体
// group 0 = 顶面，group 1 = 其余面
function sweepBox(frames, x0, x1, y0, y1, vScale) {
  const P = [], N = [], U = [], I = [];
  const faces = [
    { a: [x0, y1], b: [x1, y1], n: [0, 1], top: true },
    { a: [x1, y1], b: [x1, y0], n: [1, 0] },
    { a: [x1, y0], b: [x0, y0], n: [0, -1] },
    { a: [x0, y0], b: [x0, y1], n: [-1, 0] },
  ];
  const groups = [];
  const tmp = new THREE.Vector3();
  for (const f of faces) {
    const start = I.length;
    const base = P.length / 3;
    for (const fr of frames) {
      for (const [ox, oy] of [f.a, f.b]) {
        tmp.copy(fr.p).addScaledVector(fr.side, ox).addScaledVector(fr.up, oy);
        P.push(tmp.x, tmp.y, tmp.z);
      }
      const n = tmp.copy(fr.side).multiplyScalar(f.n[0]).addScaledVector(fr.up, f.n[1]);
      N.push(n.x, n.y, n.z, n.x, n.y, n.z);
      U.push(0, fr.s / vScale, 1, fr.s / vScale);
    }
    for (let i = 0; i < frames.length - 1; i++) {
      const k = base + i * 2;
      I.push(k, k + 1, k + 2, k + 1, k + 3, k + 2);
    }
    groups.push({ start, count: I.length - start, top: !!f.top });
  }
  // 端面
  const capStart = I.length;
  for (const [fr, sgn] of [[frames[0], -1], [frames[frames.length - 1], 1]]) {
    const base = P.length / 3;
    for (const [ox, oy] of [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]) {
      tmp.copy(fr.p).addScaledVector(fr.side, ox).addScaledVector(fr.up, oy);
      P.push(tmp.x, tmp.y, tmp.z);
      N.push(fr.t.x * sgn, fr.t.y * sgn, fr.t.z * sgn);
      U.push(0, 0);
    }
    if (sgn > 0) I.push(base, base + 2, base + 1, base, base + 3, base + 2);
    else I.push(base, base + 1, base + 2, base, base + 2, base + 3);
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(P, 3));
  g.setAttribute('normal', new THREE.Float32BufferAttribute(N, 3));
  g.setAttribute('uv', new THREE.Float32BufferAttribute(U, 2));
  g.setIndex(I);
  g.addGroup(0, groups[0].count, 0);
  g.addGroup(groups[0].count, capStart + 12 - groups[0].count, 1);
  return g;
}

function flangeGeometry() {
  const F = SPEC.flange, T = SPEC.flangeT, w = 0.12;
  const shape = new THREE.Shape();
  shape.moveTo(-F / 2, -F / 2); shape.lineTo(F / 2, -F / 2); shape.lineTo(F / 2, F / 2); shape.lineTo(-F / 2, F / 2); shape.closePath();
  const hole = new THREE.Path();
  const h = F / 2 - w;
  hole.moveTo(-h, -h); hole.lineTo(-h, h); hole.lineTo(h, h); hole.lineTo(h, -h); hole.closePath();
  shape.holes.push(hole);
  const g = new THREE.ExtrudeGeometry(shape, { depth: T, bevelEnabled: true, bevelThickness: 0.008, bevelSize: 0.008, bevelSegments: 1 });
  g.translate(0, 0, -T / 2);
  return g;
}

// 带面高 0.55，法兰中心比带面高 0.2，让带子截面落在方环下半部、上方留货箱通过空间
const FLANGE_LIFT = 0.2;

export class BeltSystem {
  constructor(scene, groundAt) {
    this.group = new THREE.Group();
    this.group.name = 'belts';
    scene.add(this.group);
    this.groundAt = groundAt;
    this.belts = [];
    this.night = false;
    const m = materials();
    this.mats = m;
    this.legGeo = new THREE.BoxGeometry(SPEC.legSize, 1, SPEC.legSize).translate(0, 0.5, 0);
    this.padGeo = new THREE.BoxGeometry(...SPEC.pad).translate(0, SPEC.pad[2] / 2, 0);
    this.flangeGeo = flangeGeometry();
    this.boltGeo = new THREE.CylinderGeometry(0.03, 0.03, 0.09, 8).rotateX(Math.PI / 2);
    this.cargoGeo = roundedBox(0.36, 0.24, 0.32, 0.05);
    this.dotGeo = new THREE.SphereGeometry(0.055, 10, 8);
  }

  // a/b 同 planBelt；opts.flangeA/flangeB 是否在该端生成法兰（模型自带法兰的一端不重复生成）
  add(id, a, b, opts = {}) {
    const plan = planBelt(a, b);
    const { frames, len } = plan;
    const m = this.mats;
    const g = new THREE.Group();
    g.name = `belt:${id}`;
    const half = SPEC.width / 2;
    const bedGeo = sweepBox(frames, -half, half, -SPEC.thick, 0, SPEC.groove);
    const bed = new THREE.Mesh(bedGeo, [m.bedTop, m.bed]);
    bed.receiveShadow = true;
    g.add(bed);
    const gl = sweepBox(frames, -half - SPEC.guardT, -half, -SPEC.thick, SPEC.guardH, 1);
    const gr = sweepBox(frames, half, half + SPEC.guardT, -SPEC.thick, SPEC.guardH, 1);
    g.add(new THREE.Mesh(gl, m.guard), new THREE.Mesh(gr, m.guard));

    // 支腿（每 1.5 m 一对，带面两侧各一根）+ 垫板
    const legs = [];
    for (let s = 0.75; s < len - 0.35; s += SPEC.legStep) legs.push(sampleAt(frames, s));
    const legMesh = new THREE.InstancedMesh(this.legGeo, m.leg, legs.length * 2);
    const padMesh = new THREE.InstancedMesh(this.padGeo, m.leg, legs.length * 2);
    const M = new THREE.Matrix4(), Q = new THREE.Quaternion(), S = new THREE.Vector3(), P = new THREE.Vector3();
    let k = 0;
    for (const fr of legs) {
      const yaw = Math.atan2(fr.t.x, fr.t.z);
      Q.setFromAxisAngle(THREE.Object3D.DEFAULT_UP, yaw);
      for (const sd of [-1, 1]) {
        P.copy(fr.p).addScaledVector(fr.side, sd * (half - 0.06));
        const gy = this.groundAt(P.x, P.z);
        const top = fr.p.y - SPEC.thick;
        const hLeg = Math.max(0.02, top - (gy + SPEC.pad[2]));
        M.compose(new THREE.Vector3(P.x, gy + SPEC.pad[2], P.z), Q, S.set(1, hLeg, 1));
        legMesh.setMatrixAt(k, M);
        M.compose(new THREE.Vector3(P.x, gy, P.z), Q, S.set(1, 1, 1));
        padMesh.setMatrixAt(k, M);
        k++;
      }
    }
    legMesh.computeBoundingSphere(); padMesh.computeBoundingSphere();
    g.add(legMesh, padMesh);

    // 法兰
    const ends = [];
    if (opts.flangeA) ends.push(frames[0]);
    if (opts.flangeB) ends.push(frames[frames.length - 1]);
    for (const fr of ends) {
      const holder = new THREE.Group();
      holder.position.copy(fr.p).addScaledVector(fr.up, FLANGE_LIFT);
      holder.quaternion.setFromRotationMatrix(new THREE.Matrix4().makeBasis(fr.side.clone().negate(), fr.up, fr.t));
      holder.add(new THREE.Mesh(this.flangeGeo, m.flange));
      const o = SPEC.flange / 2 - 0.06;
      for (const [bx, by] of [[-o, -o], [o, -o], [o, o], [-o, o]]) {
        const bolt = new THREE.Mesh(this.boltGeo, m.bolt);
        bolt.position.set(bx, by, 0);
        holder.add(bolt);
      }
      // 法兰下面的支撑柱，避免法兰悬空
      const gy = this.groundAt(holder.position.x, holder.position.z);
      const postH = holder.position.y - SPEC.flange / 2 - gy;
      if (postH > 0.03) {
        const post = new THREE.Mesh(this.legGeo, m.leg);
        post.scale.set(1.6, postH, 1.6);
        post.position.set(0, -SPEC.flange / 2 - postH, 0);
        holder.add(post);
      }
      g.add(holder);
    }

    // 数据流：货箱 + 光点，匀速同向（起点 → 终点）
    const nCargo = Math.max(1, Math.floor(len / CARGO_GAP));
    const cargo = new THREE.InstancedMesh(this.cargoGeo, m.cargo, nCargo);
    const dots = new THREE.InstancedMesh(this.dotGeo, m.dot, nCargo);
    const palette = ['#E9B77E', '#93C4B7', '#E39F8C', '#F0E2C0', '#A9B9DF'].map((c) => new THREE.Color(c));
    for (let i = 0; i < nCargo; i++) cargo.setColorAt(i, palette[(i + id.length) % palette.length]);
    cargo.frustumCulled = false; dots.frustumCulled = false;
    g.add(cargo, dots);

    this.group.add(g);
    const belt = { id, group: g, frames, len, plan, cargo, dots, nCargo, phase: Math.random() * CARGO_GAP, a, b };
    this.belts.push(belt);
    this.updateCargo(belt, performance.now() / 1000);
    return belt;
  }

  updateCargo(belt, t) {
    const M = new THREE.Matrix4(), Q = new THREE.Quaternion(), S = new THREE.Vector3(), P = new THREE.Vector3();
    const gap = belt.len / belt.nCargo;
    for (let i = 0; i < belt.nCargo; i++) {
      const s = (belt.phase + i * gap + SPEED * t) % belt.len;
      const fr = sampleAt(belt.frames, s);
      const fade = Math.min(1, s / 0.6, (belt.len - s) / 0.6);
      const k = Math.max(0.001, fade);
      Q.setFromRotationMatrix(M.makeBasis(fr.side.clone().negate(), fr.up, fr.t));
      P.copy(fr.p).addScaledVector(fr.up, 0.12 * k);
      M.compose(P, Q, S.set(k, k, k));
      belt.cargo.setMatrixAt(i, M);
      // 光点在两箱中间
      const s2 = (s + gap / 2) % belt.len;
      const f2 = sampleAt(belt.frames, s2);
      const k2 = Math.max(0.001, Math.min(1, s2 / 0.6, (belt.len - s2) / 0.6));
      M.compose(P.copy(f2.p).addScaledVector(f2.up, 0.06), Q, S.set(k2, k2, k2));
      belt.dots.setMatrixAt(i, M);
    }
    belt.cargo.instanceMatrix.needsUpdate = true;
    belt.dots.instanceMatrix.needsUpdate = true;
  }

  update(t) { for (const b of this.belts) this.updateCargo(b, t); }

  setNight(on) {
    this.night = on;
    // 夜里全园不亮灯：货箱也不自发光（P0 亮度基线）
    this.mats.cargo.emissive.set('#000000');
    this.mats.dot.color.set(on ? '#B8F6FF' : '#7FE3F0');
    this.mats.dot.color.multiplyScalar(on ? 2.2 : 1);
  }
}

function sampleAt(frames, s) {
  const step = frames[1].s - frames[0].s || STEP;
  let i = Math.min(frames.length - 2, Math.max(0, Math.floor(s / step)));
  while (i < frames.length - 2 && frames[i + 1].s < s) i++;
  while (i > 0 && frames[i].s > s) i--;
  const a = frames[i], b = frames[i + 1];
  const k = Math.min(1, Math.max(0, (s - a.s) / ((b.s - a.s) || 1)));
  return {
    p: a.p.clone().lerp(b.p, k),
    t: a.t.clone().lerp(b.t, k).normalize(),
    side: a.side.clone().lerp(b.side, k).normalize(),
    up: a.up.clone().lerp(b.up, k).normalize(),
    s,
  };
}

function roundedBox(w, h, d, r) {
  const shape = new THREE.Shape();
  const x = -w / 2, y = -h / 2;
  shape.moveTo(x + r, y);
  shape.lineTo(x + w - r, y); shape.quadraticCurveTo(x + w, y, x + w, y + r);
  shape.lineTo(x + w, y + h - r); shape.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
  shape.lineTo(x + r, y + h); shape.quadraticCurveTo(x, y + h, x, y + h - r);
  shape.lineTo(x, y + r); shape.quadraticCurveTo(x, y, x + r, y);
  const g = new THREE.ExtrudeGeometry(shape, { depth: d - 0.04, bevelEnabled: true, bevelThickness: 0.02, bevelSize: 0.02, bevelSegments: 2, curveSegments: 3 });
  g.translate(0, h / 2, -(d - 0.04) / 2);
  g.computeVertexNormals();
  return g;
}
