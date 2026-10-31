import * as THREE from 'three';

/**
 * 圆角立方体几何：BoxGeometry 细分后，把每个顶点收到「内缩盒」的圆角半径上。
 * 这是卡通场景「不硬」的核心——所有可见块体都应该用它。
 * @param {number} w 宽
 * @param {number} h 高
 * @param {number} d 深
 * 注意：所有棱共用一个 r，且 r 会被夹到最短边的一半——薄而大的板（地台）请用 makeRoundedSlab。
 * @param {number} r 圆角半径（会被夹到最短边的一半以内）
 * @param {number} seg 每段圆角弧的细分段数：小件 2~3，中件 4，大件 6~8
 */
export function makeRoundedBox(w, h, d, r = 0.08, seg = 4) {
  r = Math.min(r, w / 2, h / 2, d / 2);
  // r=0 时所有顶点 dir 为零，原实现会把法线全设成 +Y，直接退回普通盒子
  if (r <= 1e-6) return new THREE.BoxGeometry(w, h, d);
  seg = Math.max(1, Math.round(seg));
  // 原实现均匀细分：顶点间距 = 边长/seg（地台为 5.5）远大于 r，圆角带内没有顶点，
  // 只有棱上那一个顶点被斜推一下，视觉上仍是直角。改为每轴 2*seg+1 段：
  // 两端各 seg 段落在圆角带 [half-r, half] 内，中间 1 段覆盖整个平面区。
  const n = seg * 2 + 1;
  const geo = new THREE.BoxGeometry(w, h, d, n, n, n);
  const pos = geo.attributes.position;
  const nor = geo.attributes.normal;
  const hw = w / 2 - r, hh = h / 2 - r, hd = d / 2 - r;

  // 均匀网格坐标 → 网格序号 k → 圆角带内的等距坐标
  const remap = (c, half) => {
    const k = Math.round((c / (2 * half) + 0.5) * n);
    return k <= seg ? -half + (r * k) / seg : half - (r * (n - k)) / seg;
  };

  const v = new THREE.Vector3();
  const inner = new THREE.Vector3();
  const dir = new THREE.Vector3();

  for (let i = 0; i < pos.count; i++) {
    v.fromBufferAttribute(pos, i);
    v.set(remap(v.x, w / 2), remap(v.y, h / 2), remap(v.z, d / 2));
    inner.set(
      Math.max(-hw, Math.min(hw, v.x)),
      Math.max(-hh, Math.min(hh, v.y)),
      Math.max(-hd, Math.min(hd, v.z))
    );
    dir.copy(v).sub(inner);
    if (dir.lengthSq() < 1e-12) dir.set(0, 1, 0);
    else dir.normalize();
    v.copy(inner).addScaledVector(dir, r);
    pos.setXYZ(i, v.x, v.y, v.z);
    nor.setXYZ(i, dir.x, dir.y, dir.z);
  }
  pos.needsUpdate = true;
  nor.needsUpdate = true;
  geo.computeBoundingSphere();
  return geo;
}

/** 圆角矩形轮廓（XY 平面，逆时针）。从 base.js 挪到这里，供地台、贴片、接触阴影共用 */
export function roundedRectShape(w, h, r) {
  r = Math.min(r, w / 2, h / 2);
  const x = -w / 2;
  const y = -h / 2;
  const s = new THREE.Shape();
  s.moveTo(x + r, y);
  s.lineTo(x + w - r, y);
  s.absarc(x + w - r, y + r, r, -Math.PI / 2, 0, false);
  s.lineTo(x + w, y + h - r);
  s.absarc(x + w - r, y + h - r, r, 0, Math.PI / 2, false);
  s.lineTo(x + r, y + h);
  s.absarc(x + r, y + h - r, r, Math.PI / 2, Math.PI, false);
  s.lineTo(x, y + r);
  s.absarc(x + r, y + r, r, Math.PI, Math.PI * 1.5, false);
  return s;
}

/**
 * 圆角厚板：俯视轮廓圆角 rPlan 与上下棱倒角 bevel 相互独立。
 * makeRoundedBox 的单一 r 会被夹到 h/2，0.3 厚的草皮层俯视圆角最多 0.15，
 * 所以地台这类「大而薄」的板必须走这里。几何体中心在原点，Y 轴为厚度方向。
 * @param {number} rPlan 俯视圆角半径
 * @param {number} bevel 上下棱倒角（会被夹到 h 的 45% 以内）
 * @param {number} seg 圆角/倒角细分，大件 6~8
 */
export function makeRoundedSlab(w, h, d, rPlan, bevel = 0.06, seg = 6) {
  const b = Math.min(bevel, h * 0.45, rPlan);
  // 倒角会向外扩 b，所以轮廓先内缩 b，保证外形尺寸正好是 w×d、圆角正好是 rPlan
  const shape = roundedRectShape(w - 2 * b, d - 2 * b, Math.max(rPlan - b, 0.001));
  const geo = new THREE.ExtrudeGeometry(shape, {
    depth: h - 2 * b,
    bevelEnabled: b > 0,
    bevelThickness: b,
    bevelSize: b,
    bevelSegments: Math.max(1, Math.ceil(seg / 2)),
    curveSegments: seg, // 圆弧实际取 2*seg 段
  });
  geo.rotateX(-Math.PI / 2); // 挤出方向 +Z → +Y
  geo.translate(0, -(h - 2 * b) / 2, 0);
  // 无倒角时焊接会把顶面与侧墙的硬棱也抹圆，只在有倒角时平滑
  return b > 0 ? smoothNormals(geo) : geo;
}

/**
 * ExtrudeGeometry 是非索引几何，computeVertexNormals 只能得到面法线（圆角一棱一棱）。
 * 按位置焊接顶点后再算法线，得到平滑圆角；vendor 里没有 BufferGeometryUtils，这里手写最小版本。
 */
function smoothNormals(geo) {
  const src = geo.attributes.position;
  const map = new Map();
  const verts = [];
  const index = [];
  for (let i = 0; i < src.count; i++) {
    const x = src.getX(i), y = src.getY(i), z = src.getZ(i);
    const key = `${Math.round(x * 1e4)}|${Math.round(y * 1e4)}|${Math.round(z * 1e4)}`;
    let id = map.get(key);
    if (id === undefined) {
      id = verts.length / 3;
      map.set(key, id);
      verts.push(x, y, z);
    }
    index.push(id);
  }
  const out = new THREE.BufferGeometry();
  out.setAttribute('position', new THREE.Float32BufferAttribute(verts, 3));
  out.setIndex(index);
  out.computeVertexNormals();
  out.computeBoundingSphere();
  geo.dispose(); // 中间几何体用完即释放
  return out;
}

/** 便捷：直接造一个圆角方块 Mesh */
export function roundedBox(w, h, d, r, material, seg = 4) {
  return new THREE.Mesh(makeRoundedBox(w, h, d, r, seg), material);
}
