// 模型审核查看器：逐个加载 ../out/models/*.glb，任意角度拖动查看
import * as THREE from 'three';
window.__dbg = { THREE };   // 调试句柄，先初始化再挂属性，否则赋值会抛错中断整个模块

import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

const MODEL_DIR = '../out/models/';
const FOV = 32;
const FILL_H = 0.70;          // 模型占画面高度比例
const FILL_W_MAX = 0.86;      // 横向最多占画面宽度比例（竖屏手机兜底）
const ZOOM_IN = 6;            // 最远可缩到 fitDist 的 6 倍（大模型也装得下）
const ZOOM_OUT = 0.22;        // 最近可放到 fitDist 的 0.22 倍（小模型也能怼近看细节）
const deg = THREE.MathUtils.degToRad;
const HOME_POLAR = deg(45);   // 初始 45° 俯视（极角从 +Y 量起）
const HOME_AZIMUTH = deg(45);
const KEY_POS = new THREE.Vector3(-16, 24, 12);
const RIM_POS = new THREE.Vector3(14, 9, -10);
const GLB_MAGIC = 0x46546C67; // 'glTF'

// 灯光开关：材质名以 LGT_ 开头即视为一盏灯
const LAMP_PREFIX = 'LGT_';
const LAMP_EMISSIVE = 0xFFE9C4;
const LAMP_EMISSIVE_INTENSITY = 11.0;
// 同时存在的真实光源上限（每盏灯一次全场景光照计算，是卡顿的主因）
const LAMP_LIGHT_CAP = 8;
// 吊灯/室内灯：向下打的射灯参数
const LAMP_CEILING_INTENSITY = 60;
const LAMP_CEILING_RANGE = 16;
const LAMP_LIGHT_COLOR = 0xFFD9A8;
const LAMP_LIGHT_INTENSITY = 26;  // 物理光照单位（candela）
const LAMP_LIGHT_RANGE = 7;       // 光源有效半径（米）——小范围，光只照亮灯身边一小片，不穿墙
const LAMP_DECAY = 2;             // 物理衰减
const LAMP_RANGE = 0.45;           // 照射距离 = 模型半径 × 该比例
// 这些灯只让材质自己亮，不生成点光源（用户点名：屏幕类只换材质，不当光源）
const LAMP_NO_LIGHT = ['screen'];

// ⛔ 禁止光晕贴片（2026-10-27 用户明令：「总是有好多莫名其妙的点状光源，这些都删了」）。
// 灯必须靠「灯具自身发光 + 一个真实点光源」表现，不许在空气里加 sprite 光斑。
// 之前的 makeGlowSprite / makeGlowTexture 已删除，别再写回来。

// 可读名映射；找不到就显示去掉前缀后的原名
const LAMP_LABELS = {
  outdoor: '户外路灯',
  ceiling1F: '一楼吊灯',
  ceiling2F: '二楼吊灯 A',
  ceiling2F_b: '二楼吊灯 B',
  post_ceiling: '邮局天花灯',
  post_sign: '邮局招牌灯',
  castle_window: '城堡窗户灯',
  castle_interior: '城堡室内灯',
  castle_facility: '城堡设施灯',
  // 学习科研地块（按物件名识别，材质被合并成 L2_lamp_post 了）
  learn_street_W: '西侧路灯',
  learn_street_E: '东侧路灯',
  learn_lib_door: '图书馆门灯',
  learn_lab_door: '实验室门灯',
  learn_mailbox: '信箱灯',
  learn_window: '图书馆窗灯',
  lamp: '馆内灯',
  // 家人小屋 · 禹府（分区灯）
  gate: '门外门楼灯',
  courtyard: '院内灯',
  backyard: '后院灯',
  farm: '养殖区灯',
  wall: '围墙路灯',
};

// 同一组前缀的多个材质合并成一个开关（最长前缀优先）
// 例：LGT_castle_interior_wall / _floor / _ceil → 只有一个「城堡室内灯」
const PLOT_LABELS = {
  learn: '学习科研', gate: '禹府门楼', courtyard: '禹府院内', backyard: '禹府后院',
  farm: '禹府养殖', wall: '禹府围墙', castle: '彩虹城堡', post: '邮政局', library: '图书馆',
};

const LAMP_GROUPS = [
  { prefix: 'castle_interior', label: '城堡室内灯' },
];

function lampGroupKey(matName) {
  const base = matName.slice(LAMP_PREFIX.length);
  const g = LAMP_GROUPS
    .filter((x) => base.startsWith(x.prefix))
    .sort((a, b) => b.prefix.length - a.prefix.length)[0];
  return g ? { key: `${LAMP_PREFIX}${g.prefix}`, label: g.label } : { key: matName, label: null };
}

const $ = (id) => document.getElementById(id);
const ui = {
  stage: $('stage'), canvas: $('canvas'),
  progress: $('progress'), progressBar: $('progressBar'),
  notice: $('notice'), noticeTitle: $('noticeTitle'), noticeDetail: $('noticeDetail'), noticeNext: $('noticeNext'),
  panelToggle: $('panelToggle'), panelCurrent: $('panelCurrent'), list: $('modelList'), count: $('count'),
  btnRotate: $('btnRotate'), btnReset: $('btnReset'), btnNight: $('btnNight'), seasons: $('seasons'),
  infoName: $('infoName'), infoMeshes: $('infoMeshes'), infoTris: $('infoTris'), infoSize: $('infoSize'), infoPlot: $('infoPlot'),
  lamps: $('lamps'), lampList: $('lampList'), lampCount: $('lampCount'), lampAllOn: $('lampAllOn'), lampAllOff: $('lampAllOff'),
};

// ── 渲染器 / 场景 ──
// logarithmicDepthBuffer：透视相机下把深度精度按对数分布，1:10000 的近远比也不会出现
// 贴面件逐帧翻转（拖动闪）。这是渲染层根治，配合几何侧的 0.02~0.03 埋入量即可彻底解决。
// ⚠️ 不要同时给材质设 polygonOffset —— 两者会互相抵消，画面反而更乱。
const renderer = new THREE.WebGLRenderer({
  canvas: ui.canvas, antialias: true, alpha: true, logarithmicDepthBuffer: true,
});
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.setClearColor(0x000000, 0);  // 透明，露出 body 的 CSS 渐变
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.NeutralToneMapping;
const BASE_EXPOSURE = 1.0;      // 全局基准曝光
renderer.toneMappingExposure = BASE_EXPOSURE;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFShadowMap;
window.__dbg.renderer = renderer;

const scene = new THREE.Scene();
window.__dbg.scene = scene;  // 调试用：检查加载后的真实对象
const camera = new THREE.PerspectiveCamera(FOV, 1, 0.5, 100);
window.__dbg.camera = camera;  // near/far 在 applyFraming 里按相机距离动态收紧

const hemi = new THREE.HemisphereLight(0xDCEAF5, 0xCFC0A6, 0.30);
scene.add(hemi);

const keyLight = new THREE.DirectionalLight(0xFFF3DE, 1.60);
keyLight.position.copy(KEY_POS);
keyLight.castShadow = true;
keyLight.shadow.mapSize.set(2048, 2048);
keyLight.shadow.radius = 4;
keyLight.shadow.normalBias = 0.03;
scene.add(keyLight, keyLight.target);

const rimLight = new THREE.DirectionalLight(0xDCE8FF, 0.22);
rimLight.position.copy(RIM_POS);
scene.add(rimLight, rimLight.target);

// 地面圆盘：单位半径，按模型尺寸缩放；边缘 40% 径向淡出到背景
const ground = new THREE.Mesh(
  new THREE.CircleGeometry(1, 96).rotateX(-Math.PI / 2),
  new THREE.MeshStandardMaterial({
    color: 0xE8DFC9, roughness: 1, metalness: 0,
    alphaMap: makeRadialAlpha(0.6), transparent: true, depthWrite: false,
    polygonOffset: true, polygonOffsetFactor: 1, polygonOffsetUnits: 1,  // 防止与模型底面 z-fighting
  }),
);
ground.receiveShadow = true;
ground.visible = false;
scene.add(ground);

function makeRadialAlpha(solid) {
  const c = document.createElement('canvas');
  c.width = c.height = 256;
  const g = c.getContext('2d');
  const grad = g.createRadialGradient(128, 128, 0, 128, 128, 128);
  grad.addColorStop(0, '#fff');
  grad.addColorStop(solid, '#fff');
  grad.addColorStop(1, '#000');
  g.fillStyle = grad;
  g.fillRect(0, 0, 256, 256);
  return new THREE.CanvasTexture(c);
}

// ── 交互 ──
const controls = new OrbitControls(camera, ui.canvas);
controls.enableDamping = true;
controls.dampingFactor = 0.06;
controls.enablePan = true;                     // 右键拖动 = 平移（锚点可以脱离模型中心）
controls.screenSpacePanning = true;            // 沿屏幕平面平移，不像"贴地面"那样别扭
controls.panSpeed = 1.0;
controls.mouseButtons = { LEFT: THREE.MOUSE.ROTATE, MIDDLE: THREE.MOUSE.DOLLY, RIGHT: THREE.MOUSE.PAN };
// 右键菜单会打断拖动，直接屏蔽
ui.canvas.addEventListener('contextmenu', (e) => e.preventDefault());
controls.enableZoom = true;
controls.minAzimuthAngle = -Infinity;   // 水平 360° 自由
controls.maxAzimuthAngle = Infinity;
controls.minPolarAngle = deg(90 - 88);  // 仰角 88°：几乎正俯视
controls.maxPolarAngle = deg(90 - 5);   // 仰角 5°：贴地平视，不会钻到地下
controls.rotateSpeed = 0.8;
controls.zoomSpeed = 0.9;
controls.autoRotate = false;
controls.autoRotateSpeed = 1.2;
controls.touches = { ONE: THREE.TOUCH.ROTATE, TWO: THREE.TOUCH.DOLLY_PAN };  // 单指转，双指缩放+平移

const view = {
  box: new THREE.Box3(),     // 已居中、贴地后的包围盒
  radius: 1,
  fitDist: 10,               // 70% 取景对应的相机距离（1× 缩放）
};
const homeTarget = new THREE.Vector3(0, 0, 0);   // 模型中心：复位时把锚点拉回这里

let tween = null;
controls.addEventListener('start', () => { tween = null; });
controls.addEventListener('change', () => {
  const d = camera.position.distanceTo(controls.target);
  if (!d) return;
  // 深度精度：near/far 比值必须压到 ~1:20 以内，否则贴墙看时 1-3mm 的构件会逐帧翻转（拖动闪）
  // 旧公式在贴窗时退化成 near=0.02 / far=151（ratio 7560），这才是闪的真正原因
  const n = Math.max(0.08, d * 0.4);
  const f = Math.max(n * 9, d * 7);
  if (Math.abs(n - camera.near) > 0.01 || Math.abs(f - camera.far) > 0.01) {
    camera.near = n; camera.far = f; camera.updateProjectionMatrix();
  }
});

// 正交相机：计算包围盒在给定视角的投影宽高，返回 {height, width}（世界单位）
function computeOrthoSize(box, target, polar, azimuth) {
  const back = new THREE.Vector3().setFromSphericalCoords(1, polar, azimuth);
  const right = new THREE.Vector3().crossVectors(camera.up, back).normalize();
  const up = new THREE.Vector3().crossVectors(back, right);

  let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
  for (let i = 0; i < 8; i++) {
    const p = new THREE.Vector3(
      i & 1 ? box.max.x : box.min.x,
      i & 2 ? box.max.y : box.min.y,
      i & 4 ? box.max.z : box.min.z,
    ).sub(target);
    const x = p.dot(right), y = p.dot(up);
    minX = Math.min(minX, x); maxX = Math.max(maxX, x);
    minY = Math.min(minY, y); maxY = Math.max(maxY, y);
  }
  return { height: maxY - minY, width: maxX - minX };
}

// 透视相机：计算让模型在给定视角占画面 FILL_H 所需的相机距离
function computeFitDistance(box, target, polar, azimuth) {
  const proj = computeOrthoSize(box, target, polar, azimuth);
  const aspect = camera.aspect || 1;

  // 纵向：模型高度占画面 FILL_H → dist = height / (2 * tan(fovY/2)) / FILL_H
  const distFromHeight = proj.height / (2 * Math.tan(THREE.MathUtils.degToRad(FOV) / 2)) / FILL_H;

  // 横向兜底（竖屏时）：模型宽度不超过 FILL_W_MAX
  const fovX = 2 * Math.atan(Math.tan(THREE.MathUtils.degToRad(FOV) / 2) * aspect);
  const distFromWidth = proj.width / (2 * Math.tan(fovX / 2)) / FILL_W_MAX;

  // 取较大值，保证模型完整可见
  return Math.max(distFromHeight, distFromWidth);
}

function applyFraming() {
  view.fitDist = computeFitDistance(view.box, controls.target, HOME_POLAR, HOME_AZIMUTH);

  const dist = camera.position.distanceTo(controls.target) || view.fitDist;
  // 与 controls.change 里的公式保持一致（深度精度优先）
  camera.near = Math.max(0.08, dist * 0.4);
  camera.far  = Math.max(camera.near * 9, dist * 7);
  camera.aspect = ui.canvas.clientWidth / ui.canvas.clientHeight;
  camera.updateProjectionMatrix();
  console.log('[CAM]', camera.type, 'near=' + camera.near.toFixed(2), 'far=' + camera.far.toFixed(2), 'ratio=' + (camera.far / camera.near).toFixed(1));

  // 透视相机用距离限制控制缩放
  controls.minDistance = view.fitDist * ZOOM_OUT;
  controls.maxDistance = view.fitDist * ZOOM_IN;
  // 模型尺寸差异很大（小到 1 米、大到几十米）：近远比按包围盒自适应，别写死
  controls.zoomSpeed = 1.1;
}

function placeCamera(s) {
  camera.position.setFromSpherical(s).add(controls.target);
  camera.lookAt(controls.target);
}

function resetView(animate = true) {
  // 右键或双指平移过之后，锚点可能已经不在模型上；复位要把它一起拉回中心
  const from = new THREE.Spherical().setFromVector3(camera.position.clone().sub(controls.target));
  controls.target.copy(homeTarget);
  const to = new THREE.Spherical(view.fitDist, HOME_POLAR, HOME_AZIMUTH);
  if (!animate) { tween = null; placeCamera(to); return; }
  const TAU = Math.PI * 2;
  const dTheta = ((((to.theta - from.theta) % TAU) + TAU * 1.5) % TAU) - Math.PI;  // 走最短弧
  tween = { from, dTheta, t0: performance.now(), dur: 650 };
}

function stepTween(now) {
  const k = Math.min(1, (now - tween.t0) / tween.dur);
  const e = 1 - Math.pow(1 - k, 3);
  const { from } = tween;
  placeCamera(new THREE.Spherical(
    from.radius + (view.fitDist - from.radius) * e,
    from.phi + (HOME_POLAR - from.phi) * e,
    from.theta + tween.dTheta * e,
  ));
  if (k >= 1) tween = null;
}

// ── 尺寸 ──
function resize() {
  const w = ui.stage.clientWidth, h = ui.stage.clientHeight;
  if (!w || !h) return;
  renderer.setSize(w, h, false);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
}
new ResizeObserver(resize).observe(ui.stage);

// ── 资源释放 ──
function disposeObject(root) {
  const materials = new Set();
  const textures = new Set();
  root.traverse((o) => {
    o.geometry?.dispose();
    o.skeleton?.dispose();
    for (const m of [].concat(o.material ?? [])) materials.add(m);
  });
  for (const m of materials) {
    for (const v of Object.values(m)) if (v?.isTexture) textures.add(v);
    m.dispose();
  }
  for (const t of textures) {
    t.dispose();
    t.source?.data?.close?.();  // GLTFLoader 在 Chrome 下用 ImageBitmap，显式关闭
  }
}

// 黏土感（原生做法）：黏土的关键光学特性不是表面凹凸，是「漫反射主导 + 短半径次表面散射」——
// 光会透进材质一点点再散出来，物体因此有柔和的内部微光，而不是一块死平的色块。
// glb 导不出 Blender 的 SSS，就在查看器里做廉价近似：用材质自身颜色的极低强度自发光模拟内部散射，
// 同时把粗糙度拉满、金属度和环境反射清零。玻璃/水面/灯单独处理，不参与。
function clayify(m) {
  if (!m?.isMeshStandardMaterial || m.userData.clayDone) return;
  const name = (m.name || '').toLowerCase();
  if (name.startsWith(LAMP_PREFIX)) return;
  if (/glass|water|ice|window/.test(name)) return;
  m.userData.clayDone = true;
  m.roughness = 0.95;
  m.metalness = 0;
  m.envMapIntensity = 0;
  // 模型自带烘焙 AO 顶点色时，颜色和暗部都已经烘在顶点里了。
  // 这时绝不能再加自发光——底色是白的，加一点就等于给全场均匀铺灰光，把 AO 冲平，反而更塑料。
  if (m.vertexColors) {
    m.emissive = new THREE.Color(0, 0, 0);
    m.emissiveIntensity = 1;
    return;
  }
  // 没有顶点色的老模型：用自身颜色的一点自发光近似短半径次表面散射
  if (m.color) {
    m.emissive = m.color.clone().multiplyScalar(0.11);
    m.emissiveIntensity = 1;
  }
}

function tameMaterial(m) {
  if (!m?.isMeshStandardMaterial) return;
  // 玻璃/水面：保留原样的透明度与粗糙度，绝不能被 clayify 抹成不透明哑光
  const nm = (m.name || '').toLowerCase();
  if (/glass|water|ice|window/.test(nm)) return;
  m.roughness = Math.min(Math.max(m.roughness, 0.9), 1);
  m.metalness = Math.min(m.metalness, 0.4);
  m.envMapIntensity = 0;
  clayify(m);
}

// ── 模型挂载 ──
let current = null;   // { entry, root, stats }

function mount(entry, root, bytes) {
  const stats = { meshes: 0, tris: 0, bytes };
  // 模型里带四季变体和夜间点光源，导出时用 extras.default_visible=false 标了「默认隐藏」。
  // 必须在统计和包围盒之前先关掉，否则雪地、秋树、枯枝会全部叠在一起，
  // 画面变成一片发白、颜色错乱，看起来像「没有质感」。
  root.traverse((o) => {
    if (o.userData && o.userData.default_visible === false) o.visible = false;
  });
  // 模型里可能带着导出时烘焙的 KHR_lights_punctual 点光源（强度动辄几千、distance=0 就是无限范围），
  // 它们会全天候把整个场景照成一片白 —— 这就是「一盏灯都没开却特别亮」的真凶。
  // 查看器自己按开关创建光源，所以模型自带的光一律关掉。
  root.traverse((o) => {
    if (o.isLight) o.visible = false;
  });
  root.traverse((o) => {
    if (!o.isMesh) return;
    if (o.visible === false) return;
    stats.meshes++;
    // 灯具自身（LGT_ 材质）不投影：否则灯罩会把自己的光挡住，看起来像"没开灯"
    const isLampPart = [].concat(o.material).some((m) => m?.name?.startsWith(LAMP_PREFIX));
    o.castShadow = !isLampPart;
    o.receiveShadow = true;
    const g = o.geometry;
    const n = g.index ? g.index.count : g.attributes.position?.count ?? 0;
    stats.tris += Math.floor(n / 3) * (o.isInstancedMesh ? o.count : 1);
    // 全局灭火：除了灯罩/灯泡/灯笼这类发光体，任何材质一律不许自带自发光。
    // 模型里经常把整个灯的材质都写成发光，导致"杆子也亮"；这里按对象名+材质名双重判定后强制清零。
    const objName = (o.name || '').toLowerCase();
    const GLOW = /(shade|globe|bulb|lantern|_glow|lampglass)/;
    const objIsGlow = GLOW.test(objName);
    for (const m of [].concat(o.material)) {
      if (m) {
        // 记录模型里原本是否带自发光（glb 的 emissiveFactor），供建灯时判断哪个材质才是发光体
        // 阈值：自发光亮度 > 0.1 才算"这是一盏灯的发光件"，避免金属件上 0.02 这种残留自发光误判
        m.userData.glowBaked = !!(m.emissive && (m.emissive.r + m.emissive.g + m.emissive.b) > 0.3);
        if (!objIsGlow && !GLOW.test((m.name || '').toLowerCase())) {
          if (m.emissive) { m.emissive.setHex(0x000000); m.emissiveIntensity = 0; }
        }
      }
      tameMaterial(m);
    }
  });

  root.updateMatrixWorld(true);
  const box = new THREE.Box3().setFromObject(root, true);
  if (box.isEmpty()) throw new ViewerError('模型加载失败', '文件里没有可显示的几何体');

  // 居中到原点、底部贴地 y=0
  const center = box.getCenter(new THREE.Vector3());
  root.position.x -= center.x;
  root.position.y -= box.min.y;
  root.position.z -= center.z;
  box.translate(new THREE.Vector3(-center.x, -box.min.y, -center.z));

  unmount();
  current = { entry, root, stats };
  hasSeasons = detectSeasons(root);
  scene.add(root);
  root.updateMatrixWorld(true);  // 居中位移后刷新，灯的包围盒要用世界坐标

  const size = box.getSize(new THREE.Vector3());
  view.box.copy(box);
  view.radius = size.length() / 2;
  buildLamps(root);
  controls.target.set(0, size.y / 2, 0);
  homeTarget.copy(controls.target);   // 记下模型中心，复位时回到这里

  const footprint = Math.max(size.x, size.z) / 2;
  const groundR = Math.max(footprint * 1.9, view.radius * 1.2);
  ground.scale.setScalar(groundR);
  ground.visible = true;

  // 灯光方向保持设定值，距离与阴影相机随模型尺寸缩放
  const lightDist = Math.max(KEY_POS.length(), view.radius * 4);
  keyLight.position.copy(KEY_POS).setLength(lightDist).add(controls.target);
  keyLight.target.position.copy(controls.target);
  rimLight.position.copy(RIM_POS).setLength(lightDist).add(controls.target);
  rimLight.target.position.copy(controls.target);
  const sc = keyLight.shadow.camera;
  sc.left = sc.bottom = -groundR;
  sc.right = sc.top = groundR;
  sc.near = Math.max(0.1, lightDist - groundR * 2);
  sc.far = lightDist + groundR * 2;
  sc.updateProjectionMatrix();

  applyExposure();
  applyFraming();
  setSeason(seasonMode, true);   // 新模型挂上来时套用当前季节
  resetView(false);
  showInfo(entry, stats);
}

// ── 季节切换 ──
// 模型里同一棵树有绿/秋/枯/雪四套几何体，导出时都标了 default_visible=false（只有绿的那套例外）。
// 这里按名字前缀控制显隐，四季切换就只是换显隐，不重建模型。
// 命名约定：Foliage_*（绿）、Foliage_Autumn_*（秋黄）、Bare_*（枯枝）、Snow_*（积雪）
const SEASON_RULES = {
  spring: { show: [/^Foliage_(?!Autumn)/, /^(Ground|Belt|Port|Obj|Library|Lab|Maker|Mailbox|Bench|Fence|Props|LGT)/], hide: [/^Foliage_Autumn_/, /^Bare_/, /^Snow_/] },
  summer: { show: [/^Foliage_(?!Autumn)/, /^(Ground|Belt|Port|Obj|Library|Lab|Maker|Mailbox|Bench|Fence|Props|LGT)/], hide: [/^Foliage_Autumn_/, /^Bare_/, /^Snow_/] },
  autumn: { show: [/^Foliage_Autumn_/, /^Foliage_L5(bush|pot|planter|edge)/, /^(Ground|Belt|Port|Obj|Library|Lab|Maker|Mailbox|Bench|Fence|Props|LGT)/], hide: [/^Foliage_L5tree_/, /^Bare_/, /^Snow_/] },
  winter: { show: [/^Bare_/, /^Snow_/, /^(Ground|Belt|Port|Obj|Library|Lab|Maker|Mailbox|Bench|Fence|Props|LGT)/], hide: [/^Foliage_/, /^Snow_L5/] },
};
let seasonMode = 'spring';
let hasSeasons = false;

function detectSeasons(root) {
  let autumn = 0, bare = 0, snow = 0;
  root.traverse((o) => {
    const n = o.name || '';
    if (n.startsWith('Foliage_Autumn_')) autumn++;
    else if (n.startsWith('Bare_')) bare++;
    else if (n.startsWith('Snow_') && !/light/i.test(n)) snow++;
  });
  return autumn > 0 && bare > 0 && snow > 0;
}

// glTF 会把多材质节点拆成 name_1 / name_2，比较基名时要先削掉尾部编号
function stripIdx(n) {
  let k = n.length;
  while (k > 0 && n[k - 1] >= '0' && n[k - 1] <= '9') k--;
  if (k > 0 && n[k - 1] === '_') k--;
  return n.slice(0, k);
}

function setSeason(mode, silent) {
  seasonMode = SEASON_RULES[mode] ? mode : 'spring';
  if (current) {
    const rule = SEASON_RULES[seasonMode];
    // 冬季：先收集所有 Bare_ 物件的基名（Bare_tree_E -> tree_E）
    // 同一棵树既有枯枝版又有积雪版时，只显示枯枝版，否则两个会重叠。
    const bareBases = new Set();
    if (seasonMode === 'winter') {
      current.root.traverse((o) => {
        const n = o.name || '';
        // 枯枝版名字要原样记录（Bare_tree_N1 里的 N1 是名字的一部分，不是拆件编号）
        if (n.startsWith('Bare_')) bareBases.add(n.slice(5));
      });
    }
    current.root.traverse((o) => {
      const n = o.name || '';
      if (!n) return;
      // 灯的点光源单独由夜间开关管，季节不动它
      if (/^LGT_/.test(n) && /light/i.test(n)) return;
      // 冬季：有枯枝版的物件，跳过它的积雪版
      const snowRaw = n.startsWith('Snow_') ? n.slice(5) : '';
      if (seasonMode === 'winter' && snowRaw && (bareBases.has(snowRaw) || bareBases.has(stripIdx(snowRaw)))) {
        o.visible = false; return;
      }
      if (rule.hide.some((re) => re.test(n))) { o.visible = false; return; }
      if (rule.show.some((re) => re.test(n))) { o.visible = true; }
    });
  }
  document.querySelectorAll('.btn--season').forEach((b) => {
    b.setAttribute('aria-pressed', String(b.dataset.season === seasonMode));
  });
  if (ui.seasons) ui.seasons.hidden = !hasSeasons;
}

// 每块地的白墙占比不同，同一套光照下亮度差很多。
// models.json 里可以给单个模型写 exposure（默认 1），这里乘到基准曝光上。
function applyExposure() {
  const k = current && current.entry && typeof current.entry.exposure === 'number' ? current.entry.exposure : 1;
  renderer.toneMappingExposure = BASE_EXPOSURE * k;
}

function unmount() {
  if (!current) return;
  clearLamps();
  scene.remove(current.root);
  disposeObject(current.root);
  current = null;
  ground.visible = false;
}

// ── 灯光开关 ──
const lampGroup = new THREE.Group();
lampGroup.name = 'lampLights';
scene.add(lampGroup);
let lamps = [];   // { name, label, mats: [{ m, emissive, color }], center, range, on, light, el }

// 按最长前缀查映射表（ceiling2F_b 优先于 ceiling2F），返回 { label, rest }
function lampLabel(matName) {
  const base = matName.slice(LAMP_PREFIX.length);
  const key = Object.keys(LAMP_LABELS)
    .filter((k) => base.startsWith(k))
    .sort((a, b) => b.length - a.length)[0];
  if (!key) return { label: base, rest: '' };
  return { label: LAMP_LABELS[key], rest: base.slice(key.length).replace(/^[\s._-]+/, '') };
}

// 按材质名分组（GLTFLoader 可能克隆材质，克隆体同名），每组即一盏灯
function buildLamps(root) {
  const byName = new Map();
  const addTo = (key, groupLabel, mesh, mat, worldCenter, partH) => {
    let g = byName.get(key);
    if (!g) byName.set(key, g = { mats: new Set(), meshes: new Set(), points: [], parts: [], groupLabel });
    if (mat) g.mats.add(mat);
    g.meshes.add(mesh);
    if (worldCenter) {
      g.points.push(worldCenter);
      // emitter=true 表示这件是发光体（灯罩/灯泡）；灯具实体（杆/座/帽）为 false
      g.parts.push({ mesh, center: worldCenter, h: partH || 0, emitter: !!mat });
    }
  };
  root.traverse((o) => {
    if (!o.isMesh) return;
    if (o.visible === false) return;
    const oBox = new THREE.Box3().setFromObject(o);
    const c = oBox.getCenter(new THREE.Vector3());
    const okCenter = isFinite(c.x) && isFinite(c.y) && isFinite(c.z) ? c : null;
    const partH = oBox.isEmpty() ? 0 : oBox.getSize(new THREE.Vector3()).y;

    // ① 材质名以 LGT_ 开头 = 一盏可控灯（老口径，城堡/禹府这类对象名不带 LGT_ 的模型在用）
    //    ⚠️ 只要对象名本身以 LGT_ 开头，就走下面的对象名口径，否则同一盏灯的每个零件
    //    都会因为"材质名带 LGT_"被当成独立的灯，结果整根杆子都在发光。
    if (!(o.name || '').startsWith(LAMP_PREFIX)) {
      for (const m of [].concat(o.material)) {
        if (!m?.name?.startsWith(LAMP_PREFIX)) continue;
        const gk = lampGroupKey(m.name);
        addTo(gk.key, gk.label, o, m, okCenter, partH);
      }
    }
    // ② 物件名以 LGT_ 开头 = 一盏可控灯（新口径：材质被合并改名后，靠物件名兜底）
    //    这类灯共用同一份材质，必须就地克隆，否则开一盏会全亮。
    //    约定：LGT_<id>          = 灯罩（发光体）
    //          LGT_<id>_shade/_globe/_bulb/_head/_lantern = 也是发光体
    //          LGT_<id>_post/_pole/_foot/_base/_cap/_collar/_arm/_bracket/_frame/_body = 灯具实体
    //    灯具实体必须归到同一盏灯里、且绝不发光（否则整根杆子亮成一根发光棍）。
    const rawNm = o.name || '';
    // glTF 一个节点有多份材质时会被拆成 name_1 / name_2 …，去掉尾部编号才是同一盏灯
    // （不用正则，避免转义在多层字符串里被写坏）
    let nm = rawNm;
    let k = nm.length;
    while (k > 0 && nm[k - 1] >= '0' && nm[k - 1] <= '9') k--;
    if (k > 0 && nm[k - 1] === '_') nm = nm.slice(0, k - 1);

    if (nm.startsWith(LAMP_PREFIX)) {
      const lower = nm.toLowerCase();
      // 发光体白名单：只有这些零件发光；其余 LGT_ 零件（杆/座/帽/笼/螺栓/环箍/台阶…）一律算灯具实体。
      // 用一条正则同时剥掉「零件后缀 + 可选数字/小数 + glTF 拆分编号」，避免把
      // LGT_x_collar0.5 / LGT_x_shade_2 这类名字算成不同的灯。
      const PART = '(shade|globe|bulb|head|lantern|glow|lampglass|post|pole|foot|base|cap|cap2|collar|catch|arm|bracket|frame|holder|stand|body|light|cage|bolt|ring|bar|plate|stem|pipe|cord|wire|switch|joint|mount|cover|top|finial|socket|plinth|seat|knob|rod|tube|wireframe)';
      const rePart = new RegExp('_' + PART + '[0-9.]*(_[0-9]+)*$', 'i');
      const reEmit = new RegExp('_(shade|globe|bulb|head|lantern|glow|lampglass)[0-9.]*(_[0-9]+)*$', 'i');
      const mPart = nm.match(rePart);
      const groupKey = mPart ? nm.slice(0, mPart.index) : nm;
      const isEmitter = reEmit.test(nm) || (!mPart && nm.split('_').length <= 3);
      // 灯具实体：克隆材质并把自发光清零，永久不亮，只作为灯的支架存在
      if (!isEmitter) {
        const wasArray = Array.isArray(o.material);
        const list = wasArray ? o.material : [o.material];
        const cloned = list.map((m) => {
          if (!m) return m;
          const c2 = m.clone();
          c2.userData.lampBody = true;
          if (c2.emissive) { c2.emissive.setHex(0x000000); c2.emissiveIntensity = 0; }
          return c2;
        });
        o.material = wasArray ? cloned : cloned[0];
        addTo(groupKey, null, o, null, okCenter, partH);   // 只参与定位，不进发光材质表
        return;
      }
      {
        // ⚠️ 关键：必须保住「单材质 / 材质数组」的原始形态。
        // 把单材质一律 `[].concat(...)` 成数组再赋回，glTF 网格又没有 material groups，
        // three.js 会当作「按组取材质」而一个面都不画 —— 灯就在场景里却完全隐形。
        const wasArray = Array.isArray(o.material);
        const list = wasArray ? o.material : [o.material];
        const cloned = list.map((m) => {
          if (!m) return m;
          const c2 = m.clone();
          c2.userData.lampClone = true;
          return c2;
        });
        o.material = wasArray ? cloned : cloned[0];
        // 同一件网格可能挂了多个材质槽（灯罩 + 灯杆 + 玻璃），只有材质名像灯罩的才许发光
        // 发光体判定：名字像灯罩/玻璃/发光件 → 发光；名字明确是灯体结构件（杆/座/笼/帽…）→ 不发光。
        // 一个都不匹配时退回"整件发光"，避免像 PR_lamp_glass 这种混命名把灯整个判没了。
        const GLOWM = /(shade|globe|bulb|lantern|glow|glass|lgt_)/i;
        const BODYM = /(post|pole|base|cage|arm|bracket|cap|collar|bolt|ring|frame|stand|foot|plinth|seat|rod|stem|metal|iron|steel|brass|concrete|stone|wall)/i;
        // 材质名明确是灯体结构件（metal/post/foot/cage…）的一律不发光，即使烘了残留自发光
        const baked = cloned.filter((m) => m.userData && m.userData.glowBaked && !BODYM.test(m.name || ''));
        const picks = baked.length
          ? baked
          : cloned.filter((m) => GLOWM.test(m.name || '') && !BODYM.test(m.name || ''));
        // 一个发光件都没找到（材质没烘自发光、名字也不像灯罩）→ 这件只是灯具实体，
        // 归到同一盏灯里做定位，不参与发光、也不单独成为一个开关。
        if (!picks.length) {
          for (const m of cloned) if (m.emissive) { m.emissive.setHex(0x000000); m.emissiveIntensity = 0; }
          addTo(groupKey, null, o, null, okCenter, partH);
          return;
        }
        const chosen = picks;
        for (const m of cloned) {
          if (chosen.includes(m)) {
            addTo(groupKey, null, o, m, okCenter, partH);
          } else if (m.emissive) {
            m.emissive.setHex(0x000000);
            m.emissiveIntensity = 0;
          }
        }
      }
    }
  });

  lamps = [...byName].sort(([a], [b]) => a.localeCompare(b)).map(([name, g]) => {
    const box = new THREE.Box3();
    for (const mesh of g.meshes) box.expandByObject(mesh, true);
    const lampSize = box.getSize(new THREE.Vector3()).length();
    const lbl = g.groupLabel ? { label: g.groupLabel, rest: '' } : lampLabel(name);

    // 一盏灯往往由「底座 + 灯杆 + 灯罩」多件组成。
    // 只有灯头（最高那件）和明显小巧的件（灯罩/灯盘/灯泡）算发光体，
    // 灯杆和底座不许发光——整根杆子亮起来就不是灯了，是一根发光的棍子。
    const parts = g.parts || [];
    const tallest = parts.reduce((a, b) => (b.center.y > a.center.y ? b : a), parts[0] || null);
    const maxH = parts.reduce((m, p) => Math.max(m, p.h), 0.001);
    // 优先用「显式标记的发光体」；只有整盏灯都没标（老模型）才退回几何启发式
    const explicit = parts.filter((p) => p.emitter);
    const emitterMeshes = new Set(
      explicit.length
        ? explicit.map((p) => p.mesh)
        : parts.filter((p) => p === tallest || p.h <= Math.max(0.5, maxH * 0.3)).map((p) => p.mesh),
    );
    const emitterMats = new Set();
    for (const mesh of emitterMeshes) {
      for (const m of [].concat(mesh.material)) if (m) emitterMats.add(m);
    }
    // 一个网格可能挂多个材质槽（灯罩+灯杆+玻璃），这里只保留模型里原本带自发光的那个
    // 优先用「整组里带烘焙自发光的材质」——灯罩一定烘了自发光的，金属杆座没有。
    // 这样即使零件命名不规范（比如 LGT_pi_lamp_foot 被当成发光件），也不会连杆子一起亮。
    const groupBaked = new Set([...g.mats].filter((m) => m && m.userData && m.userData.glowBaked));
    const glowFiltered = new Set([...emitterMats].filter((m) => m && m.userData && m.userData.glowBaked));
    const useMats = groupBaked.size ? groupBaked
      : (glowFiltered.size ? glowFiltered : (emitterMats.size ? emitterMats : new Set([...g.mats])));

    return {
      name,
      ...lbl,
      mats: [...useMats].map((m) => ({ m, emissive: m.emissive?.clone(), color: m.color?.clone() })),
      points: g.points,
      // 光源只放一个，位置在灯头；不再按零件各放一个，避免光从地面和半空同时冒出来
      head: (explicit.length
        ? explicit.reduce((a, b) => (b.center.y > a.center.y ? b : a), explicit[0]).center
        : (tallest ? tallest.center : box.getCenter(new THREE.Vector3()))).clone(),
      center: box.getCenter(new THREE.Vector3()),
      range: Math.max(view.radius * LAMP_RANGE, lampSize * 2.2),
      on: false,
      lights: [],
      glows: [],
      el: null,
    };
  });
  // 多盏灯映射到同一可读名时，补上材质名剩余部分以区分
  const seen = new Map();
  for (const l of lamps) seen.set(l.label, (seen.get(l.label) ?? 0) + 1);
  for (const l of lamps) if (seen.get(l.label) > 1 && l.rest) l.label += ` · ${l.rest}`;
  for (const lamp of lamps) setLamp(lamp, false);  // 默认全灭
  renderLamps();
}

function setLamp(lamp, on) {
  lamp.on = on;
  // 吊灯自己不要亮成一团：灯罩只留一点微光，主要靠向下打的射灯照亮室内
  const isCeiling = /ceilingring|ceiling|pendant|chandelier/i.test(lamp.name);
  const emiIntensity = isCeiling ? 2.2 : LAMP_EMISSIVE_INTENSITY;
  for (const { m, emissive, color } of lamp.mats) {
    if (m.emissive) {
      // MeshStandardMaterial / Physical（以及 Lambert / Phong）
      m.emissive.copy(on ? new THREE.Color(LAMP_EMISSIVE) : emissive);
      m.emissiveIntensity = on ? emiIntensity : 0;
    } else if (m.isMeshBasicMaterial) {
      // KHR_materials_unlit → MeshBasicMaterial，没有 emissive，只能改底色
      m.color.copy(on ? new THREE.Color(LAMP_EMISSIVE) : color);
    }
  }
  // 一盏灯只放一个真实光源，位置就在灯头（灯罩/灯泡）上。
  // 之前的做法是按零件各放一个，结果底座和灯杆位置也在发光，
  // 看上去就是「地上凭空亮一片、上面却看不见灯」。
  const noLight = LAMP_NO_LIGHT.some((k) => lamp.name.toLowerCase().includes(k));
  // 同时存在的真实光源有上限：超了就只保留灯罩微光，不再建光源。
  // 一盏 PointLight 就是一次全场景光照计算，十几盏一起开会直接卡死。
  const activeLights = () => {
    let n = 0;
    for (const l of lamps) if (l.on) n += l.lights.length;
    return n;
  };
  if (on && !noLight && !lamp.lights.length && activeLights() < LAMP_LIGHT_CAP) {
    // 吊灯/吸顶灯/室内灯：改成**向下打的射灯**，灯罩本身只留一点微光，
    // 这样是"灯在照下面"，而不是"灯自己是一团亮球"。
    const isCeiling = /ceilingring|ceiling|pendant|chandelier/i.test(lamp.name);
    let light;
    if (isCeiling) {
      light = new THREE.SpotLight(LAMP_LIGHT_COLOR, LAMP_CEILING_INTENSITY,
                                  LAMP_CEILING_RANGE, Math.PI / 3.2, 0.75, 1.4);
      const tgt = new THREE.Object3D();
      tgt.position.copy(lamp.head || lamp.center).add(new THREE.Vector3(0, -8, 0));
      lampGroup.add(tgt);
      light.target = tgt;
      light.userData.targetObj = tgt;
    } else {
      light = new THREE.PointLight(LAMP_LIGHT_COLOR, LAMP_LIGHT_INTENSITY, LAMP_LIGHT_RANGE, 2);
    }
    light.name = `lamp:${lamp.name}`;
    // 只有室内灯投影；而且只让前 2 盏室内灯投影，其余只算光——阴影贴图是最大的开销来源
    const indoor = /ceiling|interior|indoor/i.test(lamp.name);
    const indoorShadowCount = lamps.filter((l) => l.on && /ceiling|interior|indoor/i.test(l.name)).length;
    light.castShadow = indoor && indoorShadowCount < 2;
    if (light.castShadow) {
      light.shadow.mapSize.set(512, 512);
      light.shadow.bias = -0.0025;
      light.shadow.normalBias = 0.06;
      light.shadow.camera.near = 0.5;
      light.shadow.camera.far = LAMP_CEILING_RANGE;
    }
    light.position.copy(lamp.head || lamp.center);
    lampGroup.add(light);
    lamp.lights.push(light);
  } else if (!on && lamp.lights.length) {
    for (const l of lamp.lights) {
      if (l.userData && l.userData.targetObj) lampGroup.remove(l.userData.targetObj);
      lampGroup.remove(l);
      l.dispose();
    }
    lamp.lights.length = 0;
  }
  lamp.el?.setAttribute('aria-checked', String(on));
}

function setAllLamps(on) {
  for (const lamp of lamps) if (lamp.on !== on) setLamp(lamp, on);
  updateLampSummary();
}

// ── 夜间模式：压暗天光，让灯光成为主照明 ──
let nightMode = false;
function setNight(on) {
  nightMode = on;
  document.body.classList.toggle('night', on);
  hemi.intensity = on ? 0.045 : 0.30;
  keyLight.intensity = on ? 0.05 : 1.60;
  rimLight.intensity = on ? 0.02 : 0.16;
  renderer.toneMappingExposure = on ? BASE_EXPOSURE * 0.95 : BASE_EXPOSURE * ((current && current.entry && current.entry.exposure) || 1);
  ui.btnNight?.setAttribute('aria-pressed', String(on));
  // 进夜间不自动开灯：用户要的是「夜间基本是黑的，只留自己想开的灯」。
  // 想看灯就手动开地块总开关，别替他决定。
}

function clearLamps() {
  for (const lamp of lamps) {
    for (const l of lamp.lights || []) { lampGroup.remove(l); l.dispose(); }
    for (const g of lamp.glows || []) { lampGroup.remove(g); g.material.dispose(); }
    lamp.lights = []; lamp.glows = [];
  }
  lamps = [];
  renderLamps();
}

function lampPlot(lamp) {
  const base = lamp.name.startsWith(LAMP_PREFIX) ? lamp.name.slice(LAMP_PREFIX.length) : lamp.name;
  const seg = base.split('_')[0] || '';
  return seg;
}

// 造一个开关按钮（总开关和单灯共用同一套外观）
function makeLampBtn({ label, title, on, isMaster, onClick, expandable }) {
  const btn = document.createElement('button');
  btn.type = 'button';
  btn.className = isMaster ? 'lamp lamp--master' : 'lamp';
  btn.setAttribute('role', 'switch');
  btn.setAttribute('aria-checked', String(on));
  btn.title = title || label;

  const bulb = document.createElement('span');
  bulb.className = 'lamp__bulb';
  const name = document.createElement('span');
  name.className = 'lamp__name';
  name.textContent = label;

  const sw = document.createElement('span');
  sw.className = 'switch';
  sw.setAttribute('aria-hidden', 'true');
  const knob = document.createElement('span');
  knob.className = 'switch__knob';
  sw.append(knob);

  if (expandable) {
    const caret = document.createElement('span');
    caret.className = 'lamp__caret';
    caret.textContent = '▸';
    btn.append(caret);
  }
  btn.append(bulb, name, sw);
  return btn;
}

function renderLamps() {
  ui.lamps.hidden = !lamps.length;

  // 按地块分组：默认只显示地块总开关，点开才看单灯
  const plots = new Map();
  lamps.forEach((lamp, i) => {
    const key = lampPlot(lamp) || '_';
    if (!plots.has(key)) plots.set(key, []);
    plots.get(key).push(i);
  });

  const nodes = [];
  for (const [plot, idxs] of plots) {
    const members = idxs.map((i) => lamps[i]);

    if (members.length === 1) {
      // 只有一盏就没必要套一层总开关
      const i = idxs[0];
      const lamp = lamps[i];
      const btn = makeLampBtn({ label: lamp.label, title: lamp.name, on: lamp.on });
      btn.dataset.index = i;
      lamp.el = btn;
      const li = document.createElement('li');
      li.append(btn);
      nodes.push(li);
      continue;
    }

    const masterOn = members.every((l) => l.on);
    const someOn = members.some((l) => l.on);
    const expanded = !!plotExpanded[plot];
    const label = PLOT_LABELS[plot] ? `${PLOT_LABELS[plot]}灯` : `${plot} 灯`;

    const master = makeLampBtn({
      label, title: `${label}（共 ${members.length} 盏）· 点左侧箭头单独控制`,
      on: masterOn, isMaster: true, expandable: true,
    });
    master.dataset.plot = plot;
    master.classList.toggle('lamp--partial', someOn && !masterOn);
    if (expanded) master.querySelector('.lamp__caret').textContent = '▾';

    const li = document.createElement('li');
    li.className = 'lamp-group';
    li.append(master);

    if (expanded) {
      const sub = document.createElement('ul');
      sub.className = 'lamp-sub';
      for (const i of idxs) {
        const lamp = lamps[i];
        const btn = makeLampBtn({ label: lamp.label, title: lamp.name, on: lamp.on });
        btn.dataset.index = i;
        lamp.el = btn;
        const sli = document.createElement('li');
        sli.append(btn);
        sub.append(sli);
      }
      li.append(sub);
    }
    nodes.push(li);
  }

  ui.lampList.replaceChildren(...nodes);
  updateLampSummary();
}

// 地块总开关 / 单灯 / 展开箭头
let plotExpanded = {};

function setPlot(lst, on) {
  for (const lamp of lst) setLamp(lamp, on);
  renderLamps();
}

ui.lampList.addEventListener('click', (e) => {
  const caret = e.target.closest('.lamp__caret');
  if (caret) {
    e.stopPropagation();
    const btn = caret.closest('.lamp');
    const plot = btn?.dataset.plot;
    if (plot) { plotExpanded[plot] = !plotExpanded[plot]; renderLamps(); }
    return;
  }
  const btn = e.target.closest('.lamp');
  if (!btn) return;
  if (btn.dataset.plot) {
    const plot = btn.dataset.plot;
    const lst = lamps.filter((l) => (lampPlot(l) || '_') === plot);
    const allOn = lst.every((l) => l.on);
    setPlot(lst, !allOn);
  }
});

function updateLampSummary() {
  const n = lamps.filter((l) => l.on).length;
  ui.lampCount.textContent = `${n} / ${lamps.length}`;
  ui.lampAllOn.disabled = n === lamps.length;
  ui.lampAllOff.disabled = n === 0;
}

ui.lampList.addEventListener('click', (e) => {
  const btn = e.target.closest('.lamp');
  if (!btn || btn.dataset.plot) return;   // 地块总开关由上面的处理器负责
  const lamp = btn && lamps[btn.dataset.index];
  if (!lamp) return;
  setLamp(lamp, !lamp.on);
  renderLamps();
});
ui.lampAllOn.addEventListener('click', () => setAllLamps(true));
ui.lampAllOff.addEventListener('click', () => setAllLamps(false));

// ── 加载（同一时间只有一个请求） ──
class ViewerError extends Error {
  constructor(title, detail) { super(detail); this.title = title; }
}

const loader = new GLTFLoader();
let loadSeq = 0;
let abortCtl = null;

async function loadModel(entry) {
  const seq = ++loadSeq;
  abortCtl?.abort();
  const ctl = abortCtl = new AbortController();
  const stale = () => seq !== loadSeq;

  hideNotice();
  setProgress(0);
  showInfo(entry, null);

  try {
    const url = new URL(MODEL_DIR + entry.file, location.href);
    let res;
    try {
      res = await fetch(url, { signal: ctl.signal, cache: 'no-cache' });
    } catch (err) {
      if (err.name === 'AbortError') throw err;
      throw new ViewerError('模型加载失败', `网络错误：${err.message}`);
    }
    if (res.status === 404) throw new ViewerError('该模型尚未生成', `找不到 ${entry.file}`);
    if (!res.ok) throw new ViewerError('模型加载失败', `HTTP ${res.status} · ${entry.file}`);

    const buf = await readWithProgress(res, (p) => { if (!stale()) setProgress(p); });
    if (stale()) return;
    if (!looksLikeGltf(buf)) {
      // 有些静态托管对缺失文件返回 200 + HTML 404 页
      throw new ViewerError('该模型尚未生成', `${entry.file} 不是有效的 glTF 文件`);
    }

    let gltf;
    try {
      gltf = await loader.parseAsync(buf, url.href.replace(/[^/]*$/, ''));
    } catch (err) {
      throw new ViewerError('模型加载失败', `解析出错：${err?.message || err}`);
    }
    if (stale()) { disposeObject(gltf.scene); return; }  // 解析期间用户已切走

    try {
      mount(entry, gltf.scene, buf.byteLength);
    } catch (err) {
      disposeObject(gltf.scene);
      throw err;
    }
  } catch (err) {
    if (stale() || err.name === 'AbortError') return;
    unmount();
    showNotice(err.title || '模型加载失败', err.message);
    showInfo(entry, null, true);
    console.warn('[viewer]', entry.file, err);
  } finally {
    if (!stale()) hideProgress();
  }
}

async function readWithProgress(res, onProgress) {
  const total = Number(res.headers.get('Content-Length')) || 0;
  if (!res.body || !total) {
    onProgress(-1);
    return res.arrayBuffer();
  }
  const reader = res.body.getReader();
  const chunks = [];
  let got = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    chunks.push(value);
    got += value.length;
    onProgress(Math.min(got / total, 0.99));  // gzip 时解压后字节数会超过 Content-Length
  }
  const out = new Uint8Array(got);
  let off = 0;
  for (const c of chunks) { out.set(c, off); off += c.length; }
  return out.buffer;
}

function looksLikeGltf(buf) {
  if (buf.byteLength < 12) return false;
  if (new DataView(buf).getUint32(0, true) === GLB_MAGIC) return true;
  const head = new TextDecoder().decode(new Uint8Array(buf, 0, Math.min(64, buf.byteLength))).trimStart();
  return head.startsWith('{');  // .gltf（JSON）
}

// ── UI ──
function setProgress(p) {
  ui.progress.hidden = false;
  ui.progress.classList.toggle('is-indeterminate', p < 0);
  ui.progressBar.style.width = p < 0 ? '' : `${Math.round(p * 100)}%`;
}
function hideProgress() { ui.progress.hidden = true; }

function showNotice(title, detail) {
  ui.noticeTitle.textContent = title;
  ui.noticeDetail.textContent = detail || '';
  const others = readyModels().filter((m) => m.id !== activeId).length;
  ui.noticeNext.textContent = others ? '下一个 →' : '重试';
  ui.notice.hidden = false;
}
function hideNotice() { ui.notice.hidden = true; }

function formatBytes(n) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(2)} MB`;
}

function showInfo(entry, stats, failed = false) {
  ui.infoName.textContent = entry ? entry.name : '—';
  // 地块尺寸（按标准：功能地 16×16、中央大厅 25×25、外协 20×20）
  const sz = entry && entry.size && entry.size.w ? `${entry.size.w}×${entry.size.h} m` : '';
  if (ui.infoPlot) {
    ui.infoPlot.textContent = sz;
    ui.infoPlot.hidden = !sz;
  }
  ui.infoMeshes.textContent = stats ? stats.meshes.toLocaleString('zh-CN') : '—';
  ui.infoTris.textContent = stats ? stats.tris.toLocaleString('zh-CN') : '—';
  ui.infoSize.textContent = stats ? formatBytes(stats.bytes) : failed ? '未加载' : '加载中…';
}

// ── 模型清单 ──
let models = [];
let activeId = null;

const isReady = (m) => m.status === 'ready';
const readyModels = () => models.filter(isReady);

function makeItemLI(m) {
  const li = document.createElement('li');
  const btn = document.createElement('button');
  btn.type = 'button';
  btn.className = 'item';
  btn.dataset.id = m.id;
  btn.disabled = !isReady(m);
  btn.title = isReady(m) ? m.name : `${m.name}（待做）`;

  const dot = document.createElement('span');
  dot.className = 'item__dot';
  const name = document.createElement('span');
  name.className = 'item__name';
  name.textContent = m.name;
  btn.append(dot, name);
  if (!isReady(m)) {
    const tag = document.createElement('span');
    tag.className = 'item__tag';
    tag.textContent = '待做';
    btn.append(tag);
  }
  li.append(btn);
  return li;
}

function renderList() {
  ui.count.textContent = `${readyModels().length} / ${models.length}`;
  if (!models.length) {
    const li = document.createElement('li');
    li.className = 'list__empty';
    li.textContent = 'models.json 里还没有模型';
    ui.list.replaceChildren(li);
    return;
  }
  // group: "archive" 的收进折叠区，不影响主列表
  const current = models.filter((m) => m.group !== 'archive');
  const archived = models.filter((m) => m.group === 'archive');

  const nodes = current.map(makeItemLI);
  if (!current.length) {
    const li = document.createElement('li');
    li.className = 'list__empty';
    li.textContent = '新版地块还没开始做';
    nodes.push(li);
  }
  if (archived.length) {
    const details = document.createElement('details');
    details.className = 'archive';
    const summary = document.createElement('summary');
    summary.className = 'archive__head';
    summary.textContent = `旧版存档 · ${archived.length}`;
    details.append(summary);
    const inner = document.createElement('ul');
    inner.className = 'archive__list';
    inner.append(...archived.map(makeItemLI));
    details.append(inner);
    const wrap = document.createElement('li');
    wrap.className = 'archive__wrap';
    wrap.append(details);
    nodes.push(wrap);
  }
  ui.list.replaceChildren(...nodes);
}

function markActive() {
  for (const btn of ui.list.querySelectorAll('.item')) {
    btn.setAttribute('aria-current', String(btn.dataset.id === activeId));
  }
  const entry = models.find((m) => m.id === activeId);
  ui.panelCurrent.textContent = entry ? entry.name : '';
}

function select(id) {
  const entry = models.find((m) => m.id === id);
  if (!entry) return;
  activeId = id;
  markActive();
  if (location.hash.slice(1) !== id) history.replaceState(null, '', `#${encodeURIComponent(id)}`);
  if (!isReady(entry)) {
    // 直接通过链接打开了待做模型
    ++loadSeq;
    abortCtl?.abort();
    hideProgress();
    unmount();
    showNotice('该模型尚未生成', `${entry.name} 状态为待做`);
    showInfo(entry, null, true);
    return;
  }
  loadModel(entry);
}

function step(dir) {
  const list = readyModels();
  if (!list.length) return;
  const i = list.findIndex((m) => m.id === activeId);
  const next = i < 0 ? (dir > 0 ? 0 : list.length - 1) : (i + dir + list.length) % list.length;
  select(list[next].id);
}

function setPanelOpen(open) {
  ui.panelToggle.setAttribute('aria-expanded', String(open));
}
const isMobile = () => window.matchMedia('(max-width: 720px)').matches;

ui.list.addEventListener('click', (e) => {
  const btn = e.target.closest('.item');
  if (!btn || btn.disabled) return;
  select(btn.dataset.id);
  if (isMobile()) setPanelOpen(false);
});
ui.panelToggle.addEventListener('click', () => {
  setPanelOpen(ui.panelToggle.getAttribute('aria-expanded') !== 'true');
});
ui.noticeNext.addEventListener('click', () => step(1));
ui.btnReset.addEventListener('click', () => resetView());
ui.btnNight?.addEventListener('click', () => setNight(!nightMode));
document.querySelectorAll('.btn--season').forEach((b) => {
  b.addEventListener('click', () => setSeason(b.dataset.season));
});
ui.btnRotate.addEventListener('click', () => {
  controls.autoRotate = !controls.autoRotate;
  ui.btnRotate.setAttribute('aria-pressed', String(controls.autoRotate));
});

// 双击复位（鼠标）+ 双指外的双击（触摸，dblclick 在移动端不可靠）
ui.canvas.addEventListener('dblclick', () => resetView());
let tapStart = null;
let lastTap = 0;
ui.canvas.addEventListener('pointerdown', (e) => {
  tapStart = e.pointerType === 'touch' && e.isPrimary ? { x: e.clientX, y: e.clientY, t: e.timeStamp } : null;
});
ui.canvas.addEventListener('pointerup', (e) => {
  if (!tapStart || e.pointerType !== 'touch' || !e.isPrimary) return;
  const isTap = Math.hypot(e.clientX - tapStart.x, e.clientY - tapStart.y) < 10 && e.timeStamp - tapStart.t < 300;
  tapStart = null;
  if (!isTap) { lastTap = 0; return; }
  if (e.timeStamp - lastTap < 320) { lastTap = 0; resetView(); } else lastTap = e.timeStamp;
});

window.addEventListener('keydown', (e) => {
  if (e.ctrlKey || e.metaKey || e.altKey) return;
  if (e.key === 'ArrowLeft') { e.preventDefault(); step(-1); }
  else if (e.key === 'ArrowRight') { e.preventDefault(); step(1); }
  else if (e.key === 'r' || e.key === 'R') resetView();
});

window.addEventListener('hashchange', () => {
  const id = decodeURIComponent(location.hash.slice(1));
  if (id && id !== activeId) select(id);
});

// ── 主循环 ──
renderer.setAnimationLoop((now) => {
  if (tween) stepTween(now);
  controls.update();
  renderer.render(scene, camera);
});

// 调试 / 审核脚本用
window.__viewer = { renderer, scene, camera, controls, view, get current() { return current; }, get lamps() { return lamps; } };

// ── 启动 ──
(async function init() {
  if (isMobile()) setPanelOpen(false);
  try {
    const res = await fetch('./models.json', { cache: 'no-cache' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    models = (Array.isArray(data.models) ? data.models : [])
      .filter((m) => m && m.id && m.file)
      .map((m) => ({ ...m, name: m.name || m.id }));
  } catch (err) {
    renderList();
    showNotice('无法读取模型清单', `models.json：${err.message}`);
    ui.noticeNext.hidden = true;
    return;
  }
  renderList();
  const fromHash = decodeURIComponent(location.hash.slice(1));
  const fromQuery = new URLSearchParams(location.search).get('b');  // ?b=<id>，hash 优先
  const first = models.find((m) => m.id === fromHash) || models.find((m) => m.id === fromQuery)
    || readyModels()[0] || models[0];
  if (first) select(first.id);
})();
