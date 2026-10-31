import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { ShaderPass } from 'three/addons/postprocessing/ShaderPass.js';
import { BokehPass } from 'three/addons/postprocessing/BokehPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { VignetteShader } from 'three/addons/shaders/VignetteShader.js';
import { palette, cameraCfg } from './config.js';

// ── 后处理参数（集中调参） ─────────────────────────────────
// aperture：景深强度，模糊量 ≈ |到焦平面的深度差| × aperture（UV 单位，再被 maxblur 截断）
// vignette：VignetteShader 按 mix(原色, 1-darkness, (offset·r)²) 压暗，角落 r²=0.5；
//   offset=1.05 时角落混入 55% 近黑色，会黑成一圈，所以 offset 取 0.6（角落约压暗 18%，边中点约 9%）
const POST = { aperture: 0.00014, maxblur: 0.008, vignetteOffset: 0.6, vignetteDarkness: 0.95 };

// ── 光照参数（集中调参）：晴天上午户外 = 太阳直射（暖）+ 天空漫射（冷）+ 地面反弹（暖褐） ──
// shadowMapSize：树多掉帧时可降到 3072，不要低于 2048
const LIGHT = {
  sunColor: 0xFFF2DC, sunIntensity: 1.15, sunPos: [-16, 24, 12],
  skyColor: 0xDCEAF5, groundColor: 0xB9A98F, hemiIntensity: 0.50,
  fillColor: 0xDCE8FF, fillIntensity: 0.16, fillPos: [14, 9, -10],
  exposure: 1.00,
  shadowMapSize: 4096,
};

// ── 场景模块清单：按顺序加载，缺文件不会中断整体 ──────────────────
const MODULE_PATHS = [
  './scene/base.js',
  './scene/treering.js',
  './scene/road.js',
  './scene/controlTower.js',
  './scene/factories.js',
  './scene/agents.js',
  './scene/props.js',
];

const app = document.getElementById('app');
const hudSub = document.getElementById('hud-sub');

// ── 渲染器 ────────────────────────────────────────────────
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.setSize(innerWidth, innerHeight);
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.outputColorSpace = THREE.SRGBColorSpace;
// 主光加强后顶面会接近 1.0，需要色调映射压高光。选 Neutral 而不是 ACES：
// ACES 会明显压暗、去饱和马卡龙色；Neutral 在 0.76 以下几乎不改色，只柔和压亮部。
// 接入后处理后，色调映射和 sRGB 转换改由最后的 OutputPass 统一做（背景也一起参与映射）
renderer.toneMapping = THREE.NeutralToneMapping;
renderer.toneMappingExposure = LIGHT.exposure; // 1.05 时中控塔顶面打爆
app.appendChild(renderer.domElement);

// ── 场景 ──────────────────────────────────────────────────
const scene = new THREE.Scene();
scene.background = new THREE.Color(palette.bg);
// 越往外越淡：雾色必须 = 背景色（与 scene.background 同一个值），否则交界处出色带。
// 默认 Fog 按「到相机平面的深度」算：45° 俯视、radius=52 时园区中心深度约 53，
// 26~66 的深度雾会把园区本身吃掉七成，而且只淡化画面上方，下沿和左右两侧一点不淡。
// 所以把雾距离改成「到园区中心的水平距离」（世界 XZ 半径），四个方向一致地向外渐隐：
// r<26 完全不受雾（工厂、外协都在 16 以内）；树环 r=36 约 16%，r=46 约 50%；地面外沿 r=60 约 93%。
// 只替换 fog_vertex 一个 chunk，所有内置材质统一生效；必须在任何材质编译之前设置
THREE.ShaderChunk.fog_vertex = /* glsl */ `
#ifdef USE_FOG
  vFogDepth = length( ( inverse( viewMatrix ) * mvPosition ).xz );
#endif
`;
scene.fog = new THREE.Fog(palette.bg, 26, 66);

// ── 正交正视相机 ──────────────────────────────────────────
const aspect = innerWidth / innerHeight;
const H = cameraCfg.halfHeight;
// 45° 俯视下画面底边（minZoom 时）对应的地面深度约 34，画面内最近的树冠约 20，near=0.1 不会裁掉前景
// （以前轻俯角时地面前沿会跑到相机平面之后，才用了负 near）。
// far=200 覆盖地面后沿（z=-60，深度约 96）和树环；BokehPass 用 near/far 解码深度，两者都必须是正确值
const camera = new THREE.OrthographicCamera(-H * aspect, H * aspect, H, -H, cameraCfg.near, cameraCfg.far);
const target = new THREE.Vector3(...cameraCfg.target);
camera.position.set(
  target.x + cameraCfg.radius * Math.sin(cameraCfg.phi) * Math.cos(cameraCfg.theta),
  target.y + cameraCfg.radius * Math.cos(cameraCfg.phi),
  target.z + cameraCfg.radius * Math.sin(cameraCfg.phi) * Math.sin(cameraCfg.theta)
);
camera.lookAt(target);

// ── 控制：固定正面构图，只允许缩放（点击拾取不受影响） ────────
const controls = new OrbitControls(camera, renderer.domElement);
controls.target.copy(target);
controls.enableDamping = true;
controls.dampingFactor = 0.08;
controls.enableRotate = false;
controls.enablePan = false;
controls.enableZoom = true;
controls.zoomSpeed = 0.9;
controls.minZoom = cameraCfg.minZoom;
controls.maxZoom = cameraCfg.maxZoom;
controls.update();
// target / position / zoom 都已就位并 update 过，此时保存的才是真正的初始视角
controls.saveState();

// 双击复位：reset() 不清阻尼残留的旋转/平移增量，复位后相机还会继续滑一段。
// 先关阻尼 update 一次把残留增量清零，再 reset
renderer.domElement.addEventListener('dblclick', () => {
  const damping = controls.enableDamping;
  controls.enableDamping = false;
  controls.update();
  controls.reset();
  controls.enableDamping = damping;
});

// ── 户外三层光照：太阳 + 天空/地面半球光 + 冷补光（只有太阳投影） ──────────
// 半球光替代均匀环境光：朝上的面收天空色（偏冷蓝），朝下的面收地面色（暖褐），竖直面两者各半、接近中性
const hemi = new THREE.HemisphereLight(LIGHT.skyColor, LIGHT.groundColor, LIGHT.hemiIntensity);
scene.add(hemi);

// 太阳：暖白，左上前方 → 阴影投向右下；抬高位置让阴影拉长并覆盖整个园区
const sun = new THREE.DirectionalLight(LIGHT.sunColor, LIGHT.sunIntensity);
sun.position.set(...LIGHT.sunPos);
sun.castShadow = true;
sun.shadow.mapSize.set(LIGHT.shadowMapSize, LIGHT.shadowMapSize);
// 注意：r180 的 PCFSoftShadowMap 采样偏移固定 1 texel，不读 radius；只有 PCFShadowMap 会用它
sun.shadow.radius = 6;
sun.shadow.bias = -0.0004;
sun.shadow.normalBias = 0.03;
const sc = sun.shadow.camera;
// 阴影框 ±26：覆盖园区和树林内圈（半径 20~26）；太阳距原点约 31，far=90 留足内圈树的纵深
sc.left = -26; sc.right = 26; sc.top = 26; sc.bottom = -26; sc.near = 1; sc.far = 90;
sc.updateProjectionMatrix(); // 改了视锥参数要显式更新，不依赖渲染器首次建 shadow map 时的隐式调用
scene.add(sun);

// 补光：弱、冷，只从右后方勾暗面轮廓，不投影
const fill = new THREE.DirectionalLight(LIGHT.fillColor, LIGHT.fillIntensity);
fill.position.set(...LIGHT.fillPos);
fill.castShadow = false;
scene.add(fill);

// ── 后处理：RenderPass → BokehPass（移轴景深）→ 暗角 → OutputPass ──────
// composer 默认的离屏目标不带 MSAA，renderer 的 antialias 对它无效；
// 自建 4×MSAA 的 HalfFloat 目标，保住边缘抗锯齿和色调映射前的高光余量
const composer = new EffectComposer(
  renderer,
  new THREE.WebGLRenderTarget(innerWidth, innerHeight, { type: THREE.HalfFloatType, samples: 4 })
);
composer.setPixelRatio(Math.min(devicePixelRatio, 2));
composer.setSize(innerWidth, innerHeight);
composer.addPass(new RenderPass(scene, camera));

// 焦平面 = 相机到 controls.target 的距离：相机正对 target，这个距离就是 target 在视空间的深度（=radius）。
// 正交缩放只改视锥大小、不动相机位置，理论上 focus 不随缩放变化；
// 仍在 controls change / resize 时重算一次，保证中控塔平面始终精确落在焦平面上
const bokeh = new BokehPass(scene, camera, {
  focus: camera.position.distanceTo(controls.target),
  aperture: POST.aperture,
  maxblur: POST.maxblur,
});
function syncFocus() {
  bokeh.uniforms.focus.value = camera.position.distanceTo(controls.target);
}
controls.addEventListener('change', syncFocus);
// BokehShader 默认按透视相机解码深度（perspectiveDepthToViewZ），正交相机的深度是线性的，
// 不切换的话整屏的离焦量都是错的；切到 orthographicDepthToViewZ
bokeh.materialBokeh.defines.PERSPECTIVE_CAMERA = 0;
bokeh.materialBokeh.needsUpdate = true;
composer.addPass(bokeh); // addPass 内部会调 setSize，顺带修正 aspect（正交相机没有 camera.aspect）

// 暗角：在 OutputPass 之前（线性空间）压暗四角
const vignette = new ShaderPass(VignetteShader);
vignette.uniforms.offset.value = POST.vignetteOffset;
vignette.uniforms.darkness.value = POST.vignetteDarkness;
composer.addPass(vignette);

// 必须是最后一个 pass：负责色调映射（Neutral + exposure）与 sRGB 转换
composer.addPass(new OutputPass());

// ── 状态（先读 mock，后续换后端） ──────────────────────────
const ctx = { scene, camera, renderer, controls, clock: new THREE.Clock(), state: null, updaters: [] };

async function loadState() {
  try {
    const r = await fetch('./src/state/mock.json', { cache: 'no-store' });
    if (r.ok) return await r.json();
    console.warn('[状态] mock.json 请求失败', r.status); // 404 等非 2xx 原来静默返回 null
  } catch (e) {
    // file:// 打不开或 JSON 格式错误都会到这里；JSON 写错不该无声无息
    console.warn('[状态] mock.json 读取失败', e);
  }
  return null;
}

// ── 加载场景模块 ──────────────────────────────────────────
async function boot() {
  ctx.state = await loadState();
  const loaded = [];
  const failed = [];
  for (const p of MODULE_PATHS) {
    // 原来一个 catch 同时吞掉「文件还没写」和「build 里真报错」，且只打 message 丢了堆栈。
    // 拆成两段：缺文件/语法错 → warn；build 运行时异常 → error 带完整堆栈
    let mod;
    try {
      mod = await import(p);
    } catch (e) {
      console.warn('[跳过模块] 无法导入（文件缺失或语法错误）', p, e);
      continue;
    }
    const build = mod.default;
    if (typeof build !== 'function') {
      console.warn('[跳过模块] 没有 default 导出的 build 函数', p); // 原来静默 continue
      continue;
    }
    try {
      const ret = build(ctx);
      if (ret && typeof ret.update === 'function') ctx.updaters.push(ret);
      loaded.push(p.split('/').pop().replace('.js', ''));
    } catch (e) {
      console.error('[模块构建失败]', p, e);
      failed.push(p);
    }
  }
  if (hudSub) {
    hudSub.textContent = loaded.length
      ? `${loaded.length} 个场景模块 · ${ctx.state?.summary?.running ?? '–'} 运行中` +
        (failed.length ? ` · ${failed.length} 个构建失败` : '') // 构建失败要在界面上可见
      : '场景模块未加载';
  }
  console.info('已加载场景模块：', loaded);
}

// ── 主循环 ────────────────────────────────────────────────
function tick() {
  const dt = ctx.clock.getDelta();
  const t = ctx.clock.elapsedTime;
  controls.update(dt);
  for (const u of ctx.updaters) u.update(dt, t);
  composer.render();
  requestAnimationFrame(tick);
}

// ── resize ────────────────────────────────────────────────
function onResize() {
  const a = innerWidth / innerHeight;
  const hh = cameraCfg.halfHeight;
  camera.left = -hh * a;
  camera.right = hh * a;
  camera.top = hh;
  camera.bottom = -hh;
  // 只改视锥边界，camera.zoom 不动；updateProjectionMatrix 会把 zoom 重新乘进去，缩放级别保持
  camera.updateProjectionMatrix();
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2)); // 窗口拖到不同 DPI 的屏幕时同步像素比
  renderer.setSize(innerWidth, innerHeight);
  composer.setPixelRatio(Math.min(devicePixelRatio, 2));
  composer.setSize(innerWidth, innerHeight); // 同步两个离屏目标和各 pass（含 Bokeh 深度图与 aspect）
  syncFocus();
}
addEventListener('resize', onResize);

boot();
tick();
