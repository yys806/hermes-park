import * as THREE from 'three';
import { makeRoundedBox } from '../utils/roundedBox.js';
import { mat, glassMat, glowMat } from '../utils/materials.js';
import { addCircleShadow } from '../utils/contactShadow.js';
import { palette } from '../config.js';

// 园区中心：中控塔（主角建筑）
export default function build(ctx) {
  const parent = ctx.root || ctx.world || ctx.scene;
  const tower = new THREE.Group();
  tower.name = 'controlTower';
  tower.position.y = ctx.groundY ?? 0;
  parent.add(tower);

  // ── 通用工具：实体件投影/受影，玻璃与发光件不参与阴影 ──
  const solid = (geo, material, host = tower) => {
    const m = new THREE.Mesh(geo, material);
    m.castShadow = true;
    m.receiveShadow = true;
    host.add(m);
    return m;
  };
  const lit = (geo, material, host = tower) => {
    const m = new THREE.Mesh(geo, material);
    m.castShadow = false;
    m.receiveShadow = false;
    host.add(m);
    return m;
  };
  const ring = (r, tube, material, y, host = tower, radialSeg = 10, tubularSeg = 96) => {
    const m = solid(new THREE.TorusGeometry(r, tube, radialSeg, tubularSeg), material, host);
    m.rotation.x = Math.PI / 2;
    m.position.y = y;
    return m;
  };
  // 沿圆周放置：局部 +Z 朝外
  const placeOnCircle = (mesh, angle, r, y) => {
    mesh.position.set(Math.sin(angle) * r, y, Math.cos(angle) * r);
    mesh.rotation.y = angle;
  };

  // ── 材质（统一复用）──
  const metalOpts = { roughness: 0.45, metalness: 0.25 };
  const M = {
    cream: mat(palette.towerBody), // 塔身、底级台阶、转盘
    creamLight: mat(0xFAF7EF),
    white: mat(palette.white),
    seam: mat(0xE9E2D1),
    lip: mat(0xE6DECB),
    metal: mat(palette.metal, metalOpts),
    metalLight: mat(0xDEDBD4, metalOpts),
    mint: mat(palette.mint),
    sky: mat(palette.sky),
    orange: mat(palette.orange),
    brown: mat(palette.brown),
    glass: glassMat(0xBBDCF0, 0.38),
    window: glowMat(0xCFE9F7),
    lamp: glowMat(0xF2A65A),
  };
  // 顶部信标单独克隆一份，呼吸时不影响其他灯点
  const beaconMat = glowMat(0xF2A65A).clone();
  beaconMat.transparent = true;

  // ════ 1. 塔基：三级同心圆台阶（由下往上 cream → 偏白）════
  const STEP_H = 0.14;
  const steps = [
    { r: 2.7, m: M.cream },
    { r: 2.35, m: M.creamLight },
    { r: 2.0, m: M.white },
  ];
  steps.forEach((s, i) => {
    const step = solid(new THREE.CylinderGeometry(s.r, s.r + 0.017, STEP_H, 72), s.m);
    step.position.y = STEP_H * i + STEP_H / 2;
    // 台阶上沿收边细环
    ring(s.r - 0.013, 0.015, M.lip, STEP_H * (i + 1), tower, 8, 120);
  });
  addCircleShadow(tower, 2.9, 0.005, 0.16);

  // ════ 2. 塔身：三段圆柱 + 段间环带 + 竖向分缝 ════
  const BODY_R = 1.7;
  const BODY_Y0 = STEP_H * steps.length;          // 0.42
  const SEG_HS = [1.17, 1.66, 1.17];              // 中段略高，容纳竖条窗
  const BODY_H = SEG_HS.reduce((a, b) => a + b, 0); // 4.0
  let segY = BODY_Y0;
  SEG_HS.forEach((h, i) => {
    const seg = solid(new THREE.CylinderGeometry(BODY_R, BODY_R, h, 64), M.cream);
    seg.position.y = segY + h / 2;
    segY += h;
    // 段与段之间的环带
    if (i < SEG_HS.length - 1) {
      const band = solid(new THREE.CylinderGeometry(1.75, 1.75, 0.12, 64), M.metalLight);
      band.position.y = segY;
    }
  });
  // 塔身底部踢脚
  const skirt = solid(new THREE.CylinderGeometry(1.77, 1.79, 0.085, 64), M.metal);
  skirt.position.y = BODY_Y0 + 0.0425;

  // 面板竖向分缝 ×8（错开窗位）
  const seamGeo = makeRoundedBox(0.026, BODY_H - 0.1, 0.02, 0.008, 2);
  for (let i = 0; i < 8; i++) {
    const seam = solid(seamGeo, M.seam);
    placeOnCircle(seam, (i + 0.5) * (Math.PI / 4), BODY_R + 0.005, BODY_Y0 + BODY_H / 2);
  }

  // ════ 3. 竖条窗：中段一圈 12 个发光窗 ════
  const WIN_COUNT = 12;
  const winGeo = makeRoundedBox(0.14, 1.3, 0.05, 0.022, 3);
  const winY = BODY_Y0 + SEG_HS[0] + SEG_HS[1] / 2;
  for (let i = 0; i < WIN_COUNT; i++) {
    const win = lit(winGeo, M.window);
    placeOnCircle(win, (i / WIN_COUNT) * Math.PI * 2, 1.71, winY);
  }

  // ════ 4. 观景层：外挑平台 + 栏杆 ════
  const BODY_TOP = BODY_Y0 + BODY_H;              // 4.42
  const PLAT_H = 0.15;
  const PLAT_TOP = BODY_TOP + PLAT_H;             // 4.57
  // 平台下托座
  const collar = solid(new THREE.CylinderGeometry(1.85, 1.72, 0.1, 64), M.metalLight);
  collar.position.y = BODY_TOP - 0.05;
  const platform = solid(new THREE.CylinderGeometry(2.0, 2.0, PLAT_H, 72), M.white);
  platform.position.y = BODY_TOP + PLAT_H / 2;
  // 平台侧沿橙色饰带
  const platBand = solid(new THREE.CylinderGeometry(2.02, 2.02, 0.045, 72), M.orange);
  platBand.position.y = BODY_TOP + PLAT_H / 2;

  // 栏杆立柱 ×20
  const RAIL_R = 1.91;
  const POST_H = 0.29;
  const postGeo = makeRoundedBox(0.05, POST_H, 0.05, 0.017, 2);
  for (let i = 0; i < 20; i++) {
    const post = solid(postGeo, M.metal);
    placeOnCircle(post, (i / 20) * Math.PI * 2, RAIL_R, PLAT_TOP + POST_H / 2);
  }
  // 扶手 + 中横杆
  ring(RAIL_R, 0.024, M.metalLight, PLAT_TOP + POST_H, tower, 10, 128);
  ring(RAIL_R, 0.012, M.metal, PLAT_TOP + POST_H * 0.5, tower, 8, 128);

  // ════ 5. 玻璃穹顶 + 放射骨架 + 底沿环箍 ════
  const DOME_R = 1.7;
  const dome = lit(
    new THREE.SphereGeometry(DOME_R, 64, 32, 0, Math.PI * 2, 0, Math.PI / 2),
    M.glass,
  );
  dome.position.y = PLAT_TOP;
  dome.renderOrder = 2;

  // 底沿环箍
  ring(DOME_R + 0.026, 0.06, M.metalLight, PLAT_TOP + 0.043, tower, 12, 128);

  // 骨架条 ×6：沿经线的弧形细管，共享一份几何
  const RIB_R = DOME_R + 0.034;
  const RIB_TOP_E = 1.34; // 收拢处仰角
  const ribPts = [];
  for (let k = 0; k <= 14; k++) {
    const e = 0.06 + (RIB_TOP_E - 0.06) * (k / 14);
    ribPts.push(new THREE.Vector3(Math.cos(e) * RIB_R, Math.sin(e) * RIB_R, 0));
  }
  const ribGeo = new THREE.TubeGeometry(new THREE.CatmullRomCurve3(ribPts), 48, 0.03, 8, false);
  for (let i = 0; i < 6; i++) {
    const rib = solid(ribGeo, M.metalLight);
    rib.position.y = PLAT_TOP;
    rib.rotation.y = (i / 6) * Math.PI * 2;
  }
  // 顶部收拢冠环 + 冠盖
  const crownR = Math.cos(RIB_TOP_E) * RIB_R;
  ring(crownR, 0.05, M.metalLight, PLAT_TOP + Math.sin(RIB_TOP_E) * RIB_R, tower, 10, 48);
  const crownCap = solid(new THREE.CylinderGeometry(0.425, 0.45, 0.1, 40), M.white);
  crownCap.position.y = PLAT_TOP + 1.69;
  const CROWN_TOP = PLAT_TOP + 1.74;

  // ════ 6. 穹顶内分拣转盘（缓慢自转）════
  // 静止底座
  const pedestal = solid(new THREE.CylinderGeometry(0.36, 0.41, 0.12, 32), M.metal);
  pedestal.position.y = PLAT_TOP + 0.06;

  const spinner = new THREE.Group();
  spinner.position.y = PLAT_TOP;
  tower.add(spinner);

  const column = solid(new THREE.CylinderGeometry(0.15, 0.15, 0.6, 24), M.metalLight, spinner);
  column.position.y = 0.12 + 0.3;
  const DISC_Y = 0.77;
  const DISC_T = 0.1;
  const disc = solid(new THREE.CylinderGeometry(1.23, 1.23, DISC_T, 64), M.cream, spinner);
  disc.position.y = DISC_Y;
  ring(1.23, 0.03, M.orange, DISC_Y, spinner, 8, 96);
  const hub = solid(new THREE.CylinderGeometry(0.22, 0.22, 0.085, 32), M.orange, spinner);
  hub.position.y = DISC_Y + DISC_T / 2 + 0.0425;

  // 格子 ×6：mint / sky 交替
  const binGeo = makeRoundedBox(0.36, 0.17, 0.36, 0.043, 3);
  for (let i = 0; i < 6; i++) {
    const bin = solid(binGeo, i % 2 ? M.sky : M.mint, spinner);
    placeOnCircle(bin, (i / 6) * Math.PI * 2, 0.81, DISC_Y + DISC_T / 2 + 0.085);
  }

  // ════ 7. 塔顶：灯点 + 天线 + 呼吸信标 ════
  // 天线下方一圈 3 个小灯点（带灯座）
  for (let i = 0; i < 3; i++) {
    const a = (i / 3) * Math.PI * 2;
    const housing = solid(new THREE.CylinderGeometry(0.05, 0.06, 0.045, 16), M.brown);
    placeOnCircle(housing, a, 0.27, CROWN_TOP + 0.0225);
    const lamp = lit(new THREE.SphereGeometry(0.043, 16, 12), M.lamp);
    placeOnCircle(lamp, a, 0.27, CROWN_TOP + 0.077);
  }
  const antBase = solid(new THREE.CylinderGeometry(0.085, 0.12, 0.12, 20), M.metal);
  antBase.position.y = CROWN_TOP + 0.06;
  const ANT_H = 0.95;
  const antenna = solid(new THREE.CylinderGeometry(0.03, 0.03, ANT_H, 12), M.metal);
  antenna.position.y = CROWN_TOP + 0.12 + ANT_H / 2;
  const beacon = lit(new THREE.SphereGeometry(0.095, 24, 16), beaconMat);
  beacon.position.y = CROWN_TOP + 0.12 + ANT_H + 0.068;

  // ════ 8. 指示牌：塔基侧面立杆 + 圆角牌 + 3 条色条 ════
  const SIGN_A = Math.PI * 0.25;
  const sign = new THREE.Group();
  placeOnCircle(sign, SIGN_A, 3.15, 0);
  tower.add(sign);

  const foot = solid(new THREE.CylinderGeometry(0.12, 0.14, 0.05, 24), M.metal, sign);
  foot.position.y = 0.025;
  const pole = solid(new THREE.CylinderGeometry(0.026, 0.026, 0.77, 12), M.metal, sign);
  pole.position.y = 0.05 + 0.385;
  const BOARD_Y = 0.73;
  const BOARD_Z = 0.048;
  const board = solid(makeRoundedBox(0.6, 0.34, 0.045, 0.017, 3), M.white, sign);
  board.position.set(0, BOARD_Y, BOARD_Z);

  const bars = [
    { w: 0.43, m: M.orange },
    { w: 0.31, m: M.mint },
    { w: 0.37, m: M.sky },
  ];
  bars.forEach((b, i) => {
    const bar = solid(makeRoundedBox(b.w, 0.043, 0.01, 0.004, 2), b.m, sign);
    bar.position.set(-0.23 + b.w / 2, BOARD_Y + 0.085 - i * 0.085, BOARD_Z + 0.0225 + 0.005);
  });

  // ════ 动画 ════
  return {
    update(dt, t) {
      // 转盘自转
      spinner.rotation.y += dt * 0.22;
      // 信标呼吸：缩放 0.9~1.1，亮度同步起伏
      const pulse = Math.sin(t * 2);
      beacon.scale.setScalar(1 + 0.1 * pulse);
      beaconMat.opacity = 0.8 + 0.2 * pulse;
    },
  };
}
