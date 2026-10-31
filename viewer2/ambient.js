// B-7 环境动态件：树梢摇摆、旗子飘动。全部在顶点着色器里做，CPU 每帧只推一个时间 uniform。
// 烟囱 / 水面：当前 12 块模型里没有 chimney / smoke / water 节点，按任务书「有才做」，不做。
// 画质：低 = 全关（幅度 0）；中 = 树；高 = 树 + 旗
import * as THREE from 'three';

export const windU = {
  uWindT: { value: 0 },
  uTreeAmp: { value: 1 },
  uFlagAmp: { value: 1 },
};
const TIER = { low: { tree: 0, flag: 0 }, mid: { tree: 1, flag: 0 }, high: { tree: 1, flag: 1 } };

const SWAY_FN = `
uniform float uWindT, uTreeAmp, uFlagAmp;
float windWave(float ph, float f) { return sin(uWindT * f + ph) * 0.7 + sin(uWindT * f * 2.37 + ph * 1.9) * 0.3; }
`;

// 程序生成的树林（InstancedMesh）：按本地高度的平方偏移 xz，相位取实例位置。base 以下不动（树干根部）
export function patchInstancedSway(mat, { base = 0.6, k = 0.004 } = {}) {
  mat.onBeforeCompile = (sh) => {
    Object.assign(sh.uniforms, windU);
    sh.vertexShader = sh.vertexShader
      .replace('#include <common>', '#include <common>\n' + SWAY_FN)
      .replace('#include <begin_vertex>', `#include <begin_vertex>
{
#ifdef USE_INSTANCING
  vec2 ip = vec2(instanceMatrix[3][0], instanceMatrix[3][2]);
#else
  vec2 ip = vec2(0.0);
#endif
  float hh = max(transformed.y - ${base.toFixed(3)}, 0.0);
  transformed.xz += vec2(0.87, 0.5) * (windWave(ip.x * 0.37 + ip.y * 0.21, 1.15) * uTreeAmp * ${k.toFixed(5)} * hh * hh);
}`);
  };
  mat.customProgramCacheKey = () => `sway:${base}:${k}`;
}

// 地块合批后的材质：顶点属性 aWob = (偏移方向 × 幅度 xyz, 相位)。kind: tree（慢）/ flag（快，沿旗面传波）
export function patchMergedWobble(mat, kind) {
  const amp = kind === 'flag' ? 'uFlagAmp' : 'uTreeAmp';
  const f = kind === 'flag' ? '4.6' : '1.15';
  const prev = mat.onBeforeCompile;
  mat.onBeforeCompile = (sh, r) => {
    if (prev) prev(sh, r);
    Object.assign(sh.uniforms, windU);
    sh.vertexShader = sh.vertexShader
      .replace('#include <common>', '#include <common>\nattribute vec4 aWob;\n' + SWAY_FN)
      .replace('#include <begin_vertex>', `#include <begin_vertex>\ntransformed += aWob.xyz * windWave(aWob.w, ${f}) * ${amp};`);
  };
  const prevKey = mat.customProgramCacheKey;
  mat.customProgramCacheKey = () => (prevKey ? prevKey.call(mat) : '') + ':wob:' + kind;
  mat.userData.wob = kind;
}

const TREE_NAME = /^(Foliage|Bare|Snow)_.*tree/i;
const FLAG_MAT = /flag/i;
const POLE = /(pole|staff)/i;
const WIND = new THREE.Vector3(0.87, 0, 0.5);

// prepare 阶段（合并前）调用：给树 / 旗 mesh 算出逐顶点 aWob（根节点空间），并标出材质种类。
// 返回 Map<mesh, Float32Array(4 × 顶点数)>
export function buildWobble(root, meshes) {
  const out = new Map();
  const nameOf = (o) => { for (let a = o; a && a !== root; a = a.parent) if (TREE_NAME.test(a.name || '') && !/treepit/i.test(a.name)) return a.name; return null; };
  const poles = [];
  for (const o of meshes) if (POLE.test(o.material?.name || '') || POLE.test(o.name || '')) poles.push(new THREE.Box3().setFromObject(o).getCenter(new THREE.Vector3()));
  const v = new THREE.Vector3();
  for (const o of meshes) {
    if (o.isInstancedMesh) continue;
    const mname = o.material?.name || '';
    const isFlag = FLAG_MAT.test(mname) && !POLE.test(mname);
    const isTree = !isFlag && !!nameOf(o);
    if (!isFlag && !isTree) continue;
    const pos = o.geometry.attributes.position, n = pos.count;
    const b = new THREE.Box3().setFromObject(o), c = b.getCenter(new THREE.Vector3()), sz = b.getSize(new THREE.Vector3());
    const a = new Float32Array(n * 4);
    if (isTree) {
      const H = Math.max(sz.y, 0.5), ph = c.x * 0.37 + c.z * 0.21;
      const k = 0.012 * Math.min(H, 6);
      for (let i = 0; i < n; i++) {
        v.fromBufferAttribute(pos, i).applyMatrix4(o.matrixWorld);
        const t = Math.max(0, (v.y - b.min.y) / H - 0.25) / 0.75;
        const w = t * t * k;
        a[i * 4] = WIND.x * w; a[i * 4 + 2] = WIND.z * w; a[i * 4 + 3] = ph;
      }
      o.material.userData.wobKind = 'tree';
    } else {
      // 旗：水平长轴 = 飘向；离旗杆近的一端固定；旗面法线 = 另一水平轴
      const alongX = sz.x >= sz.z;
      let pole = null, best = Infinity;
      for (const p of poles) { const d = p.distanceToSquared(c); if (d < best) { best = d; pole = p; } }
      const lo = alongX ? b.min.x : b.min.z, hi = alongX ? b.max.x : b.max.z, L = Math.max(hi - lo, 0.05);
      const fromLo = pole ? Math.abs((alongX ? pole.x : pole.z) - lo) < Math.abs((alongX ? pole.x : pole.z) - hi) : true;
      const amp = Math.min(0.06, L * 0.12);
      for (let i = 0; i < n; i++) {
        v.fromBufferAttribute(pos, i).applyMatrix4(o.matrixWorld);
        const s = alongX ? v.x : v.z;
        const u = THREE.MathUtils.clamp(fromLo ? (s - lo) / L : (hi - s) / L, 0, 1);
        const w = u * amp;
        if (alongX) a[i * 4 + 2] = w; else a[i * 4] = w;
        a[i * 4 + 1] = u * u * amp * 0.25;
        a[i * 4 + 3] = c.x * 1.3 - u * 3.2;   // 沿旗面往外传的波
      }
      o.material.userData.wobKind = 'flag';
    }
    out.set(o, a);
  }
  return out;
}

export function setAmbientTier(q) {
  const t = TIER[q] || TIER.mid;
  windU.uTreeAmp.value = t.tree;
  windU.uFlagAmp.value = t.flag;
}
export function updateAmbient(nowSec) { windU.uWindT.value = nowSec; }
