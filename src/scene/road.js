import * as THREE from 'three';
import { makeRoundedBox } from '../utils/roundedBox.js';
import { mat } from '../utils/materials.js';
import { roadTexture } from '../utils/proceduralTextures.js';
import { palette, layout } from '../config.js';

// 路面高度：中心 y=0.025，厚 0.02，顶面 0.035
const ROAD_Y = 0.025;
const ROAD_TOP = ROAD_Y + 0.01;

export default function build(ctx) {
  const g = new THREE.Group();
  g.name = 'road';

  // 路面：程序化细纹纹理，主路与环道共用一份
  const roadMat = new THREE.MeshLambertMaterial({ map: roadTexture(ctx.renderer) });
  const dashMat = mat(palette.cream);
  const zebraMat = mat(palette.white);

  // 同尺寸几何体复用
  const geoCache = new Map();
  const geo = (w, h, d, r) => {
    const key = `${w}|${h}|${d}|${r}`;
    if (!geoCache.has(key)) geoCache.set(key, makeRoundedBox(w, h, d, r, 2));
    return geoCache.get(key);
  };

  // 放置一块贴地薄片：几何体长轴沿 X，heading 为朝向角（XZ 平面，从 +X 转向 +Z）
  const place = (geometry, material, x, y, z, heading) => {
    const m = new THREE.Mesh(geometry, material);
    m.position.set(x, y, z);
    m.rotation.y = -heading;
    m.castShadow = false; // 贴地薄片不投影，避免阴影噪点
    m.receiveShadow = true;
    g.add(m);
    return m;
  };

  const roadW = 1.1;
  const roadEnd = layout.ringRadius + 1;
  const roadStart = -roadW / 2; // 向中心多伸半个路宽，保证中心路口铺满
  const headings = [45, 135, 225, 315].map((d) => THREE.MathUtils.degToRad(d));
  const ringR = layout.ringRadius - 1.2;
  const ringW = 1.0;

  // ── 1. 主路：中心向外四条 ──
  const roadLen = roadEnd - roadStart;
  const roadGeo = geo(roadLen, 0.02, roadW, 0.01);
  for (const h of headings) {
    const mid = (roadStart + roadEnd) / 2;
    place(roadGeo, roadMat, Math.cos(h) * mid, ROAD_Y, Math.sin(h) * mid, h);
  }

  // ── 2. 中心环道：24 段切向薄块拼圆环 ──
  const ringSegs = 24;
  // 段长按外缘计算，保证外圈无缺口
  const segLen = 2 * (ringR + ringW / 2) * Math.tan(Math.PI / ringSegs) + 0.02;
  const ringGeo = geo(segLen, 0.02, ringW, 0.01);
  for (let i = 0; i < ringSegs; i++) {
    const a = (i / ringSegs) * Math.PI * 2;
    place(ringGeo, roadMat, Math.cos(a) * ringR, ROAD_Y + 0.001, Math.sin(a) * ringR, a + Math.PI / 2);
  }

  // ── 3. 中心线：每条主路一排短虚线，避开斑马线和环道路口 ──
  const dashGeo = geo(0.28, 0.012, 0.09, 0.006);
  const dashStep = 0.42;
  const dashFrom = 2.9; // 斑马线外侧
  const dashTo = roadEnd - 0.3;
  const dashY = ROAD_TOP + 0.006;
  for (const h of headings) {
    for (let d = dashFrom; d <= dashTo; d += dashStep) {
      if (Math.abs(d - ringR) < ringW / 2 + 0.2) continue; // 跳过与环道交叉段
      place(dashGeo, dashMat, Math.cos(h) * d, dashY, Math.sin(h) * d, h);
    }
  }

  // ── 4. 斑马线：半径 2.2 处，每条主路 4 条横跨路面的白条 ──
  const zebraGeo = geo(0.12, 0.014, 0.9, 0.007); // 长边横跨路面
  const zebraR = 2.2;
  const zebraStep = 0.22;
  const zebraY = ROAD_TOP + 0.007;
  for (const h of headings) {
    for (let j = 0; j < 4; j++) {
      const d = zebraR + (j - 1.5) * zebraStep;
      place(zebraGeo, zebraMat, Math.cos(h) * d, zebraY, Math.sin(h) * d, h);
    }
  }

  ctx.scene.add(g);
  return { update: () => {} };
}
