import * as THREE from 'three';
import { shadowMat } from './materials.js';
import { roundedRectShape } from './roundedBox.js';

// 贴片高度默认 0.022：高于草皮分格线顶面（0.015），否则分格线会从阴影里「透」出来；低于路面顶面（0.035）
const SHADOW_Y = 0.022;

/**
 * 在物件底部垫一片半透明暗色薄片（假 AO）。
 * 这是解决「物件像飘着」最有效的一招，每个落地物件都要加。
 * @param {number} y 贴片所在高度（单面薄片，不再是 0.02 厚的盒子）
 */
export function addContactShadow(parent, w, d, y = SHADOW_Y, opacity = 0.16, radius = 0.2) {
  // 原来用 0.02 厚的 makeRoundedBox：r 被夹到 0.01，radius 参数实际无效（阴影是直角）；
  // 且透明盒子的侧面会叠出一圈更深的边。改为单面圆角矩形贴片
  const geo = new THREE.ShapeGeometry(roundedRectShape(w, d, Math.min(radius, w / 2, d / 2)), 6);
  const mesh = new THREE.Mesh(geo, shadowMat(opacity));
  mesh.rotation.x = -Math.PI / 2;
  mesh.position.y = y;
  // 贴地阴影是最底层的透明物，先于玻璃等透明件绘制（原 renderOrder=1 会画在玻璃之后，叠到玻璃上）
  mesh.renderOrder = -1;
  parent.add(mesh);
  return mesh;
}

/** 圆形接触阴影（给圆柱类物件用） */
export function addCircleShadow(parent, r, y = SHADOW_Y, opacity = 0.16) {
  const geo = new THREE.CircleGeometry(r, 28);
  const mesh = new THREE.Mesh(geo, shadowMat(opacity));
  mesh.rotation.x = -Math.PI / 2;
  mesh.position.y = y;
  mesh.renderOrder = -1; // 同上
  parent.add(mesh);
  return mesh;
}
