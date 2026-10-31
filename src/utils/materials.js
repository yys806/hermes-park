import * as THREE from 'three';
import { palette } from '../config.js';

const cache = new Map();

/** 复用材质，避免每个物件 new 一个（性能） */
export function mat(color, opts = {}) {
  const key = color + '|' + JSON.stringify(opts);
  if (cache.has(key)) return cache.get(key);
  const m = new THREE.MeshLambertMaterial({ color, ...opts });
  cache.set(key, m);
  return m;
}

/** 玻璃：半透明，不写深度，避免挡住内部物件 */
export function glassMat(color = palette.glass, opacity = 0.4) {
  const key = 'glass|' + color + '|' + opacity;
  if (cache.has(key)) return cache.get(key);
  const m = new THREE.MeshLambertMaterial({
    color, transparent: true, opacity, depthWrite: false,
  });
  cache.set(key, m);
  return m;
}

/** 自发光小块（窗、指示灯、星点） */
export function glowMat(color, opacity = 1) {
  const key = 'glow|' + color + '|' + opacity;
  if (cache.has(key)) return cache.get(key);
  const m = new THREE.MeshBasicMaterial({ color, transparent: opacity < 1, opacity });
  cache.set(key, m);
  return m;
}

/** 接触阴影：贴地薄片，深棕半透明，depthWrite=false 防止 z-fighting */
export function shadowMat(opacity = 0.16) {
  const key = 'shadow|' + opacity;
  if (cache.has(key)) return cache.get(key);
  const m = new THREE.MeshBasicMaterial({
    color: palette.brown, transparent: true, opacity, depthWrite: false,
  });
  cache.set(key, m);
  return m;
}
