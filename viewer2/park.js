// 园区总场景：按 scene.json 把 12 块地接成一个园区，传送带程序生成。
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { MeshoptDecoder } from 'three/addons/libs/meshopt_decoder.module.js';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';
import { createWorld, makeLayout, GROUND_Y } from './world.js?v=20261031-p5';
import { BeltSystem, SPEC } from './belts.js?v=20261031-p5';
import { Precip } from './weather.js?v=20261031-p5';
import { Post, makeContactMaterial, buildContactMesh } from './fx.js?v=20261031-p5';
import { solarPosition, hhmm as hhmmLive, weatherFromWmo } from './sun.js?v=20261031-p5';
import { initPanel, setPanelPlot } from './panel.js?v=20261031-p5';
import { initLeftBar } from './leftbar.js?v=20261031-p5';
import { CargoSystem } from './cargo.js?v=20261031-p7';
import { Sky } from './sky.js?v=20261031-p6';
import { buildWobble, patchMergedWobble, setAmbientTier, updateAmbient, windU } from './ambient.js?v=20261031-p5';

const T0 = performance.now();
const deg = THREE.MathUtils.degToRad;

// ════════════════ 可调参数 ════════════════
const DETAIL_R = 0.3;               // 小零件判定半径（米）
const DETAIL_DIST = 75;             // 镜头离地块超过这个距离就隐藏小零件批次
const SHADOW_NEAR_PLOTS = 3;        // 高画质、未聚焦时：除中央大厅外，离镜头最近的几块投影
const DBLCLICK_MS = 230;            // 单击等这么久确认不是双击
// B-8 镜头语言：聚焦到位后绕注视点极缓慢摆动（±orbitAmp，一个来回 orbitPeriod 毫秒）；回全景沿上抛弧线拉远；自动旋转三档速度
const CAM = { orbitAmp: 5, orbitPeriod: 24000, orbitRamp: 1500, homeLift: 0.07, spin: { slow: 0.3, mid: 0.6, fast: 1.2 } };
const KEY_DIR = new THREE.Vector3(0.55, 0.9, 0.42).normalize();
// 跟随模式下由真实太阳方向替换（默认仍是固定方向，手动模式不受影响）
const sunDir = KEY_DIR.clone();

// 夜灯：只给聚焦地块。灯罩自发光 + 最多 LIGHT_CAP 个真实点光源
const LIGHT_CAP = 8;
const LAMP_COLOR = 0xFFD9A8;
const LAMP_EMISSIVE = new THREE.Color(0xFFE2B0);
const LAMP_EMISSIVE_K = 2.6;
const LAMP_POWER = { ceiling: 18, outdoor: 24 };
const LAMP_RANGE = { ceiling: 10, outdoor: 8 };
const LAMP_MIN_RANGE = 2.5;          // 光源照程最少这么多米；再往外收到「不碰邻块」为止
const LAMP_SHADOW_MAP = 512;         // 高画质下室内灯投影贴图

// 画质三档。dpr 为像素比；casters：阴影投射体（none / hall=只中央大厅 / focus=聚焦块+左右邻居+大厅）；
// detail：小零件显示规则（distance=按距离 / focus=只给聚焦块与邻居）；lampShadows：室内灯真实投影盏数
const QUALITY = {
  low:  { label: '低', dpr: () => 1, post: false, shadows: false, shadowMap: 1024, casters: 'none', detail: 'distance', particles: false, lampShadows: 0, fog: [250, 560] },
  mid:  { label: '中', dpr: () => Math.min(window.devicePixelRatio || 1, 1.25), post: true, shadows: true, shadowMap: 1024, casters: 'hall', detail: 'distance', particles: true, lampShadows: 0, fog: [250, 480] },
  high: { label: '高', dpr: () => Math.min(window.devicePixelRatio || 1, 1.5), post: true, shadows: true, shadowMap: 1024, casters: 'focus', detail: 'focus', particles: true, lampShadows: 1, fog: [250, 480] },
};
const QUALITY_DEFAULT = 'mid';
// P5：聚焦不再临时升画质（升档会换投影体 / 开云影与接触阴影，焦点块和邻居被压暗）。null = 聚焦时保持用户所选
const QUALITY_ON_FOCUS = null;
// P5：地块模型几乎全是双面材质，开阴影接收会大面积自阴影（实测中央大厅 164 → 102、聚焦三块 -35%~-43%）。
// 地块只往草地 / 步道上投影，自身不接收太阳阴影，12 块明暗与画质档、聚焦无关
const PLOT_RECEIVE_SHADOW = false;

// ── P0.5 观感效果（fx.js）。每档开哪些；URL ?fx=all / ?fx=none / ?fx=dof,grade 或 __park.fx.set(...) 覆盖（覆盖时不看画质档）
// dof=A-1 景深（只在聚焦时起作用）  contact=A-2 接触阴影  grade=A-3 暖调 LUT  vignette=A-3 暗角  bloom=A-3 灯罩光晕
// fade=A-4 昼夜/天气渐变  lamps=A-4 灯逐盏亮  cloud=A-5 云影
// fx 全关时：中/高画质仍走后期做色调映射 + P0 的 LIGHTING.grade 基础分级，画面与 P0 相同
const FX_KEYS = ['dof', 'contact', 'grade', 'vignette', 'bloom', 'fade', 'lamps', 'cloud'];
const FX_TIER = {
  low: [],
  // P5：中档也开地面云影（程序化，无矩形边）；天上的云与日轮由 sky.js 画，三档都有（低档云层数少）
  mid: ['dof', 'grade', 'vignette', 'cloud'],
  high: FX_KEYS,
};
const FX_PARAMS = {
  // 景深：焦点 = 镜头注视点。range：焦点前后 ±(地块半径 × rangeK / 焦距) 内全清楚，再过 fade（相对焦距）虚到最大
  // edge：以焦点屏幕位置为中心的椭圆半径（屏幕高度为 1），edge0 内清楚、edge1 外虚到 edgeK；maxBlur：最大模糊半径（占屏幕高度）
  dof: { rangeK: 0.8, rangeMin: 0.1, rangeMax: 0.6, fade: 0.9, edge0: 0.32, edge1: 0.85, edgeK: 0.75, maxBlur: 0.0085, rampMs: 700 },
  // 接触阴影：物件底部离地台 ≤ maxBase 米、高 ≥ minH、占地长边在 [minSize, maxSize] 之间才贴；fall = 渐隐宽度（米，按高度取）
  contact: { strength: 0.5, tint: '#2E2620', maxBase: 0.3, minH: 0.18, minSize: 0.1, maxSize: 14, fallK: 0.22, fallMin: 0.08, fallMax: 0.45 },
  // Bloom：HDR 亮度阈值（曝光前）与软膝；强度按 LIGHTING[].bloom
  bloom: { threshold: 1.15, knee: 0.5 },
  // LUT 两端色：暗部偏暖棕、亮部偏奶油（乘在 sRGB 上，强度按 LIGHTING[].lut）
  grade: { shadowTint: [1.0, 0.975, 0.94], highTint: [1.025, 1.0, 0.935] },
  // 云影：风速（米/秒）、方向、噪声平铺尺寸（米）；视深 fade[0]→fade[1] 米淡出；强度按 LIGHTING[].cloud
  cloud: { speed: 2.0, dir: [0.8, 0.6], tile: 170, fade: [160, 330] },
  // 渐变：时长；夜里灯在渐变走到 lampAt 比例时开始逐盏亮；相邻灯间隔 stagger[0..1] 毫秒，每盏亮起用 lampRise 秒
  fade: { ms: 4000, lampAt: 0.45, stagger: [60, 150], lampRise: 0.35, lampOffMs: 600 },
};

// 天光：昼夜 × 天气。sky=背景/雾色；hemi=[天色, 地色, 强度]；sun=[色, 强度]；shadow=阴影浓度；
// fogK=雾距离缩放；grade=后期色彩分级 [对比, 饱和, 暖调]（低画质没有后期，只靠灯光）
// P0.5 扩展（对应 fx 开关）：lut=暖调 LUT 强度、vig=暗角、bloom=灯罩光晕强度、cloud=云影浓度（0 = 不起作用）
// 夜里不开月光（平行光有方向，转了角度的地块明暗会不同），只留半球环境光，保证 12 块亮度一致
const LIGHTING = {
  day: {
    sunny:    { sky: '#CFE4EF', hemi: ['#EAF2F8', '#B9C29A', 1.05], sun: ['#FFE6C4', 2.15], shadow: 1.0,  exposure: 1.0,  fogK: 1.0,  grade: [1.08, 1.06, 0.025], lut: 1.0,  vig: 0.2,  bloom: 0,    cloud: 0.1 },
    overcast: { sky: '#C3C9CE', hemi: ['#E1E5E9', '#A7AC9F', 1.65], sun: ['#E8EBEE', 0.3],  shadow: 0.3,  exposure: 1.0,  fogK: 0.8,  grade: [0.93, 0.86, 0],     lut: 0.8,  vig: 0.2,  bloom: 0,    cloud: 0.17 },
    rain:     { sky: '#8996A6', hemi: ['#B4BFCC', '#7A8276', 1.3],  sun: ['#C9D3DE', 0.15], shadow: 0.15, exposure: 0.9,  fogK: 0.6,  grade: [0.97, 0.8, -0.02],  lut: 0.6,  vig: 0.22, bloom: 0,    cloud: 0.14 },
    snow:     { sky: '#D3DCE6', hemi: ['#E6EEF8', '#D6DEE8', 1.45], sun: ['#DCE6FF', 0.55], shadow: 0.4,  exposure: 1.0,  fogK: 0.7,  grade: [0.97, 0.84, -0.035], lut: 0.6, vig: 0.18, bloom: 0,    cloud: 0.1 },
  },
  night: {
    sunny:    { sky: '#141B2B', hemi: ['#6F7FA8', '#2A3226', 0.34], sun: ['#9FB2E0', 0], shadow: 0, exposure: 1.0, fogK: 1.0, grade: [1.0, 0.95, 0], lut: 0.55, vig: 0.24, bloom: 0.55, cloud: 0 },
    overcast: { sky: '#12161E', hemi: ['#687080', '#2A2D2A', 0.3],  sun: ['#9FB2E0', 0], shadow: 0, exposure: 1.0, fogK: 0.8, grade: [1.0, 0.85, 0], lut: 0.5,  vig: 0.24, bloom: 0.55, cloud: 0 },
    rain:     { sky: '#0E131C', hemi: ['#5C6A80', '#22272A', 0.27], sun: ['#9FB2E0', 0], shadow: 0, exposure: 1.0, fogK: 0.6, grade: [1.0, 0.8, 0],  lut: 0.5,  vig: 0.24, bloom: 0.6,  cloud: 0 },
    snow:     { sky: '#1A2232', hemi: ['#7C8CB0', '#4A5262', 0.36], sun: ['#9FB2E0', 0], shadow: 0, exposure: 1.0, fogK: 0.7, grade: [1.0, 0.85, 0], lut: 0.5,  vig: 0.22, bloom: 0.5,  cloud: 0 },
  },
};
// 弱光明暗校准（同模型库 models.json 按模型写 exposure 的思路）：各块材质整体颜色不同（白瓷砖 / 深色圆盘 / 红色外协），
// 只有环境光时平均亮度能差 2 倍多。按光照条件（昼夜.天气）给每块一个材质颜色增益，让弱光下 12 块明暗一致。
// 晴天白天只校准中央大厅（P5：地块不再接收阳光阴影后，白色穹顶比其它块亮 15%，压到同一基线）。键 = 昼夜.天气[.winter]。数值由 tmp_scripts/v2_p0/calibrate.js 在全景下实测迭代得出；删掉某个条件即关闭
const PLOT_GAIN = {
  'day.sunny': { control: 0.814 },
  'day.sunny.winter': { control: 0.814 },
  'night.sunny': { control: 0.946, daily: 1.04, learn: 0.977, family: 1.022, inventor: 0.907, rainbow: 0.959, clock: 1.005, vault: 0.967, press: 0.957, codex: 1.123, clawd: 1.262, pi: 1.029 },
  'night.overcast': { control: 0.972, daily: 0.956, learn: 0.979, family: 1.029, inventor: 0.927, rainbow: 0.872, clock: 1.034, vault: 0.991, press: 0.988, codex: 1.224, clawd: 1.217, pi: 1.086 },
  'night.rain': { control: 0.952, daily: 1.005, learn: 0.973, family: 1.025, inventor: 0.908, rainbow: 0.918, clock: 1.024, vault: 0.972, press: 0.963, codex: 1.16, clawd: 1.268, pi: 1.079 },
  'night.snow': { control: 0.981, daily: 0.969, learn: 1.006, family: 1.007, inventor: 0.895, rainbow: 0.946, clock: 0.979, vault: 0.95, press: 0.92, codex: 1.245, clawd: 1.377, pi: 1.096 },
  'day.overcast': { control: 0.821, daily: 1.147, learn: 0.989, family: 1.044, inventor: 0.88, rainbow: 0.981, clock: 0.989, vault: 0.953, press: 0.941, codex: 1.079, clawd: 1.376, pi: 0.963 },
  'day.rain': { control: 0.836, daily: 1.097, learn: 0.988, family: 1.049, inventor: 0.89, rainbow: 0.972, clock: 1.005, vault: 0.96, press: 0.946, codex: 1.105, clawd: 1.265, pi: 0.979 },
  'day.snow': { control: 0.864, daily: 0.989, learn: 0.997, family: 1.023, inventor: 0.889, rainbow: 0.927, clock: 0.947, vault: 0.953, press: 0.908, codex: 1.182, clawd: 1.56, pi: 1.032 },
  'night.sunny.winter': { control: 0.981, daily: 0.964, learn: 1.012, family: 1.006, inventor: 0.891, rainbow: 0.944, clock: 0.978, vault: 0.948, press: 0.918, codex: 1.239, clawd: 1.41, pi: 1.119 },
  'night.overcast.winter': { control: 0.987, daily: 0.955, learn: 1.0, family: 0.987, inventor: 0.908, rainbow: 0.946, clock: 0.999, vault: 0.963, press: 0.924, codex: 1.294, clawd: 1.279, pi: 1.12 },
  'night.rain.winter': { control: 0.98, daily: 0.949, learn: 1.001, family: 0.998, inventor: 0.894, rainbow: 0.938, clock: 0.983, vault: 0.948, press: 0.915, codex: 1.245, clawd: 1.355, pi: 1.145 },
  'day.overcast.winter': { control: 0.861, daily: 0.988, learn: 1.002, family: 1.023, inventor: 0.886, rainbow: 0.925, clock: 0.949, vault: 0.955, press: 0.907, codex: 1.183, clawd: 1.56, pi: 1.041 },
  'day.rain.winter': { control: 0.871, daily: 0.976, learn: 1.012, family: 1.023, inventor: 0.892, rainbow: 0.934, clock: 0.959, vault: 0.955, press: 0.91, codex: 1.207, clawd: 1.449, pi: 1.059 },
};
const WET_DARKEN = 0.78;             // 雨天材质颜色乘这个系数（Lambert 没有 roughness，用压暗模拟湿感）

// 降水粒子（weather.js）。area：粒子铺在注视点周围宽 W 的方块里，W = 镜头距离 × widthPerDist（夹在 min/max 之间），
// 离注视点 W×fadeIn 开始淡出、W×fadeOut 完全消失；离镜头 near 米内淡掉
const PRECIP = {
  rain: { count: 7000, speed: 24, height: 30, len: 0.9, wind: [0.12, 0, 0.05], color: '#C8D4E4', alpha: 0.42 },
  snow: { count: 6000, speed: 1.5, height: 30, size: 0.16, color: '#FFFFFF', alpha: 0.9 },
  area: { widthPerDist: 0.75, minW: 34, maxW: 120, fadeIn: 0.28, fadeOut: 0.5, near: 6, ground: GROUND_Y },
  nightDim: 0.35,
};

// 季节。四季变体在模型里按前缀区分：Foliage_（绿）/ Foliage_Spring_（春花）/ Foliage_Autumn_（秋黄）/ Bare_（枯枝）/ Snow_（积雪）
// 同一株植物（去掉前缀后同名）按下面的优先级取第一个存在的变体显示，其余隐藏
const SEASONS = ['spring', 'summer', 'autumn', 'winter'];
const SEASON_PICK = {
  spring: ['Foliage_Spring_', 'Foliage_'],
  summer: ['Foliage_', 'Foliage_Spring_'],
  autumn: ['Foliage_Autumn_', 'Foliage_'],
  winter: ['Bare_', 'Snow_'],
};
const SEASON_PREFIX = /^(Foliage_Spring_|Foliage_Autumn_|Foliage_|Bare_|Snow_)/;
const SNOW_VEG = /(bush|tree|flower)/i;   // 带这些词的 Snow_ 件是冬季植物替换体；其余（屋顶/地面/围栏/道具）是积雪覆盖层
const SNOW_SKIP = /^Snow_L5/;             // 学习科研的积雪灌木形体有问题，模型库里也不显示
const NON_SEASON_SHOW = /^(Ground|Belt|Port|Obj|Library|Lab|Maker|Mailbox|Bench|Fence|Props|LGT)/;

// 环境默认值（手动模式）。season: 'auto' = 按今天的气象季节（3-5 春 / 6-8 夏 / 9-11 秋 / 12-2 冬）
const ENV_DEFAULT = { season: 'auto', night: false, weather: 'sunny' };

// 右上角 HUD
const LOCATION = { name: '上海·嘉定', lat: 31.38, lon: 121.25, tz: 8, timeZone: 'Asia/Shanghai' };
const WEATHER_TEXT = { sunny: '晴', overcast: '阴', rain: '雨', snow: '雪' };
// 手动模式没有实况气温，按季节 × 天气给一个典型值（嘉定气候）
const MANUAL_TEMP = {
  spring: { sunny: 18, overcast: 15, rain: 13, snow: 3 },
  summer: { sunny: 33, overcast: 29, rain: 26, snow: 3 },
  autumn: { sunny: 20, overcast: 17, rain: 15, snow: 2 },
  winter: { sunny: 7, overcast: 4, rain: 4, snow: -1 },
};

const $ = (id) => document.getElementById(id);
const ui = {
  btnDemo: $('btnDemo'),
  stage: $('stage'), canvas: $('canvas'),
  load: $('load'), loadBar: $('loadBar'), loadText: $('loadText'),
  plate: $('plate'), focusPlate: $('focusPlate'), focusChip: $('focusChip'), focusName: $('focusName'),
  card: $('card'), cardTitle: $('cardTitle'), cardBody: $('cardBody'), cardClose: $('cardClose'),
  btnHome: $('btnHome'), btnRotate: $('btnRotate'), hud: $('hud'), qualityNote: $('qualityNote'),
  envTime: $('envTime'), envDate: $('envDate'), envPlace: $('envPlace'), envIcon: $('envIcon'), envWeather: $('envWeather'),
  envMode: $('envMode'), envSun: $('envSun'),
};
const log = (...a) => console.log('[park]', ...a);

// ── 渲染器 ──
// 反向深度缓冲：大场景（近 0.1 / 远 900）也不会出现共面闪烁，且不像 logarithmicDepthBuffer 那样写 gl_FragDepth 关掉 early-z
const renderer = new THREE.WebGLRenderer({ canvas: ui.canvas, antialias: true, reversedDepthBuffer: true, powerPreference: 'high-performance' });
renderer.setPixelRatio(QUALITY[QUALITY_DEFAULT].dpr());
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.NeutralToneMapping;
renderer.toneMappingExposure = 1.0;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFShadowMap;
renderer.info.autoReset = false;   // 后期是多次 render，每帧开头手动清零，性能条才统计得到整帧

const scene = new THREE.Scene();
scene.background = new THREE.Color(LIGHTING.day.sunny.sky);
scene.fog = new THREE.Fog(scene.background.clone(), 200, 480);

const camera = new THREE.PerspectiveCamera(36, 1, 0.1, 900);

const hemi = new THREE.HemisphereLight(0xEAF2F8, 0xB9C29A, 1.15);
scene.add(hemi);
const sun = new THREE.DirectionalLight(0xFFF1DC, 1.9);
// 月光：只做全局微亮（偏冷、无投影），夜间 0.35、白天 0；不破坏「夜间只亮聚焦地块」的灯效
const moonLight = new THREE.DirectionalLight(0x9FB6E8, 0);
moonLight.position.set(-0.45, 0.82, 0.35).normalize().multiplyScalar(300);
moonLight.castShadow = false;
scene.add(moonLight);
sun.castShadow = true;
sun.shadow.mapSize.set(2048, 2048);
sun.shadow.radius = 3;
sun.shadow.bias = -0.0015;
sun.shadow.normalBias = 0.14;
scene.add(sun, sun.target);

// ── 后期（中/高画质）：fx.js 的 Post。场景 → HDR（4×MSAA + 深度）→ 景深 / 云影 / Bloom → 色调映射 + sRGB → 分级 → 暗角 ──
const post = new Post(renderer);
{
  const pu = post.final.uniforms;
  // 乘数原样传（不做色彩空间换算）
  pu.uShadowTint.value.fromArray(FX_PARAMS.grade.shadowTint);
  pu.uHighTint.value.fromArray(FX_PARAMS.grade.highTint);
  pu.uCloudWind.value.set(FX_PARAMS.cloud.dir[0] * FX_PARAMS.cloud.speed, FX_PARAMS.cloud.dir[1] * FX_PARAMS.cloud.speed, FX_PARAMS.cloud.tile);
  pu.uCloudFade.value.fromArray(FX_PARAMS.cloud.fade);
  post.bright.uniforms.uThreshold.value = FX_PARAMS.bloom.threshold;
  post.bright.uniforms.uKnee.value = FX_PARAMS.bloom.knee;
}
// P5 天空：渐变天穹 + 日轮 + 程序化云，方向跟 sunDir（手动固定 / 跟随真实 / 演示 06→22 点）
const sky = new Sky(scene, { windX: FX_PARAMS.cloud.dir[0], windZ: FX_PARAMS.cloud.dir[1] });
const contactMat = makeContactMaterial(FX_PARAMS.contact.strength, FX_PARAMS.contact.tint);

// ── 控制 ──
const controls = new OrbitControls(camera, ui.canvas);
controls.enableDamping = true;
controls.dampingFactor = 0.07;
controls.screenSpacePanning = false;          // 平移贴着地面走
controls.mouseButtons = { LEFT: THREE.MOUSE.ROTATE, MIDDLE: THREE.MOUSE.DOLLY, RIGHT: THREE.MOUSE.PAN };
controls.minDistance = 4;
controls.maxDistance = 330;
controls.minPolarAngle = deg(4);
controls.maxPolarAngle = deg(84);
controls.autoRotateSpeed = 0.6;
controls.zoomSpeed = 1.1;
ui.canvas.addEventListener('contextmenu', (e) => e.preventDefault());

// ── 状态 ──
let def = null;
const plots = new Map();        // id → plot
const loader = new GLTFLoader()
loader.setMeshoptDecoder(MeshoptDecoder);;
let beltSys = null;
let world = null;
let precip = null;
const env = { season: meteoSeason(new Date()), night: ENV_DEFAULT.night, weather: ENV_DEFAULT.weather, source: 'manual' };
if (ENV_DEFAULT.season !== 'auto') env.season = ENV_DEFAULT.season;
let night = env.night;
let focused = null;                 // 全站唯一的聚焦地块；null = 全景
const demo = { on: false, t0: 0, timer: 0, saved: null, date: new Date(), lastSun: 0, dusk: false };   // B-9 演示状态
let qualityUser = QUALITY_DEFAULT;  // 用户选的档
let qualityCur = null;              // 实际生效的档（聚焦时临时升高）
const lampLights = [];
const timings = { firstScreen: null, allLoaded: null, plots: {} };
const nextFrame = () => new Promise((r) => requestAnimationFrame(() => r()));
const sanitize = (n) => THREE.PropertyBinding.sanitizeNodeName(n || '');

// ── 材质：黏土哑光 ──
const GLOW_OBJ = /(shade|globe|bulb|lantern|_glow|lampglass)/i;
const GLOWM = /(shade|globe|bulb|lantern|glow|glass|lgt_)/i;
const BODYM = /(post|pole|base|cage|arm|bracket|cap|collar|bolt|ring|frame|stand|foot|plinth|seat|rod|stem|metal|iron|steel|brass|concrete|stone|wall)/i;
const PART = '(shade|globe|bulb|head|lantern|glow|lampglass|post|pole|foot|base|cap|cap2|collar|catch|arm|bracket|frame|holder|stand|body|light|cage|bolt|ring|bar|plate|stem|pipe|cord|wire|switch|joint|mount|cover|top|finial|socket|plinth|seat|knob|rod|tube|wireframe)';
const RE_PART = new RegExp('_' + PART + '[0-9.]*(_[0-9]+)*$', 'i');
const RE_EMIT = new RegExp('_(shade|globe|bulb|head|lantern|glow|lampglass)[0-9.]*(_[0-9]+)*$', 'i');
const stripIdx = (n) => { let k = n.length; while (k > 0 && n[k - 1] >= '0' && n[k - 1] <= '9') k--; return k > 0 && n[k - 1] === '_' ? n.slice(0, k - 1) : n; };

// 把 glTF 的 Standard/Physical 换成 Lambert（哑光黏土、片元开销低很多）；玻璃换 Phong 保留一点高光
function convertMaterial(m, emitter, glowU) {
  const name = (m.name || '').toLowerCase();
  const glassy = /glass|ice|window/.test(name) || m.transmission > 0 || (m.transparent && m.opacity < 0.95);
  const common = {
    name: m.name, color: m.color ? m.color.clone() : new THREE.Color(1, 1, 1), map: m.map || null,
    vertexColors: !!m.vertexColors, side: m.side, alphaTest: m.alphaTest || 0,
  };
  let out;
  if (glassy && !emitter) {
    out = new THREE.MeshPhongMaterial({ ...common, transparent: true, opacity: m.transmission > 0 ? 0.32 : Math.min(m.opacity, 0.55),
      depthWrite: false, shininess: 70, specular: new THREE.Color(0x3A3A3A) });
  } else {
    out = new THREE.MeshLambertMaterial({ ...common, transparent: !!m.transparent, opacity: m.opacity ?? 1, depthWrite: m.depthWrite !== false });
  }
  // 亮度基线统一：所有材质的基础自发光一律为 0（原来没有 AO 顶点色的材质会带 10% 自身色自发光，
  // 导致有的地块在没光时比别的亮）。只有灯罩材质会在「夜间 + 本块被聚焦」时发光，见 applyGlow
  out.emissive.setRGB(0, 0, 0);
  out.userData = { emitter, glassy, baseColor: out.color.clone(), gain: 1 };
  // 灯罩逐盏亮（A-4）：合批后每个顶点带所属灯的点亮延迟 aLampDelay（秒），
  // 自发光 × uLampMul × smoothstep(延迟, 延迟 + 亮起时长, uLampT)；uniform 每块地一组
  if (emitter && glowU) {
    out.onBeforeCompile = (sh) => {
      Object.assign(sh.uniforms, glowU);
      sh.vertexShader = sh.vertexShader
        .replace('#include <common>', '#include <common>\nattribute float aLampDelay;\nvarying float vLampDelay;')
        .replace('#include <begin_vertex>', '#include <begin_vertex>\nvLampDelay = aLampDelay;');
      sh.fragmentShader = sh.fragmentShader
        .replace('#include <common>', '#include <common>\nuniform float uLampT, uLampMul, uLampStag, uLampRise;\nvarying float vLampDelay;')
        .replace('#include <emissivemap_fragment>', '#include <emissivemap_fragment>\n{ float d = vLampDelay * uLampStag; totalEmissiveRadiance *= uLampMul * smoothstep(d, d + uLampRise, uLampT); }');
    };
    out.customProgramCacheKey = () => 'lampStagger';
  }
  return out;
}

// ── 加载单个地块 ──
async function fetchGlb(p, onProgress) {
  // 默认用压缩版（meshopt + webp，体积约为原来的 16%）；?opt=0 可回退原版
  const useOpt = new URLSearchParams(location.search).get('opt') !== '0' && !!def.modelDirOpt;   // 默认压缩版（结构保全版）；?opt=0 回退原版
  const dir = useOpt ? def.modelDirOpt : def.modelDir;
  const url = new URL(dir + p.file, location.href);
  const res = await fetch(url);
  if (!res.ok) throw new Error(`HTTP ${res.status} · ${p.file}`);
  const total = Number(res.headers.get('Content-Length')) || 0;
  if (!res.body || !total) return { buf: await res.arrayBuffer(), url };
  const reader = res.body.getReader();
  const chunks = []; let got = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    chunks.push(value); got += value.length;
    onProgress(Math.min(got / total, 1));
  }
  const out = new Uint8Array(got);
  let o = 0; for (const c of chunks) { out.set(c, o); o += c.length; }
  return { buf: out.buffer, url };
}

// 季节可见掩码：第 (季节序号 × 2 + 是否下雪) 位为 1 表示该状态下可见。非季节物件 = 全 1
const MASK_ALL = (1 << (SEASONS.length * 2)) - 1;
const maskBit = (season, snowing) => 1 << (SEASONS.indexOf(season) * 2 + (snowing ? 1 : 0));

function seasonMasks(root) {
  // 找每个季节物件的最上层季节节点（多材质节点会拆成 Group + 子 mesh，以 Group 为准）
  const tops = [];
  root.traverse((o) => {
    const n = o.name || '';
    if (!SEASON_PREFIX.test(n)) return;
    for (let a = o.parent; a && a !== root; a = a.parent) if (SEASON_PREFIX.test(a.name || '')) return;
    const kind = n.match(SEASON_PREFIX)[1];
    tops.push({ o, kind, base: n.slice(kind.length) });
  });
  // 同一株植物的各个变体：base → Set(kind)
  const variants = new Map(), stripped = new Map();
  const add = (m, k, kind) => { if (!m.has(k)) m.set(k, new Set()); m.get(k).add(kind); };
  for (const t of tops) {
    if (t.kind === 'Snow_' && (!SNOW_VEG.test(t.base) || SNOW_SKIP.test(t.o.name))) continue;
    add(variants, t.base, t.kind); add(stripped, stripIdx(t.base), t.kind);
  }
  const masks = new Map();   // 季节节点 → 掩码
  for (const t of tops) {
    let mask = 0;
    const overlay = t.kind === 'Snow_' && !SNOW_VEG.test(t.base);
    for (const s of SEASONS) for (const snowing of [false, true]) {
      let on;
      if (overlay) on = s === 'winter' || snowing;                     // 屋顶/地面积雪：冬季或下雪天
      else if (t.kind === 'Snow_' && SNOW_SKIP.test(t.o.name)) on = false;
      else {
        const have = variants.get(t.base) || stripped.get(stripIdx(t.base)) || new Set([t.kind]);
        on = SEASON_PICK[s].find((k) => have.has(k)) === t.kind;
      }
      if (on) mask |= maskBit(s, snowing);
    }
    masks.set(t.o, mask);
  }
  return masks;
}

function prepare(root, p) {
  root.updateMatrixWorld(true);
  // 分区热点：在合并前按最近的 Obj_* 祖先统计每块「建筑」的世界包围盒（合并后名字就丢了）
  const entities = new Map();
  {
    const wb = new THREE.Box3();
    root.traverse((o) => {
      if (!o.isMesh) return;
      let a = o, nm = null;
      for (; a && a !== root; a = a.parent) { const n = a.name || ''; if (/^Obj_/.test(n)) { nm = n; break; } }
      if (!nm) return;
      if (!o.geometry.boundingBox) o.geometry.computeBoundingBox();
      wb.copy(o.geometry.boundingBox).applyMatrix4(o.matrixWorld);
      const cur = entities.get(nm);
      if (cur) cur.union(wb); else entities.set(nm, wb.clone());
    });
    p.entities = entities;
  }

  // 1. 去掉模型自带光源、默认隐藏的非季节物件（直接删，不占显存）；四季变体全部保留，按掩码切显隐
  const masks = seasonMasks(root);
  const seasonal = new Set();
  for (const o of masks.keys()) o.traverse((c) => seasonal.add(c));
  root.traverse((o) => {
    if (seasonal.has(o)) { o.visible = true; return; }
    if (o.userData && o.userData.default_visible === false) o.visible = false;
    const n = o.name || '';
    if (!n || (/^LGT_/.test(n) && /light/i.test(n))) return;
    if (NON_SEASON_SHOW.test(n)) o.visible = true;
  });
  const drop = [];
  root.traverse((o) => { if (o !== root && (o.isLight || o.visible === false)) drop.push(o); });
  for (const o of drop) o.parent?.remove(o);
  root.updateMatrixWorld(true);
  const maskOf = (o) => {
    for (let a = o; a && a !== root; a = a.parent) if (masks.has(a)) return masks.get(a);
    return MASK_ALL;
  };
  const springBit = maskBit('spring', false);

  // 2. 统计 + 识别灯 + 材质转换
  const stats = { meshes: 0, tris: 0 };
  const glowU = { uLampT: { value: 0 }, uLampMul: { value: 0 }, uLampStag: { value: 1 }, uLampRise: { value: FX_PARAMS.fade.lampRise } };
  const contact = [];
  const summerBit = maskBit('summer', false);
  const matMap = new Map();          // 原材质 uuid + 是否发光体 → 新材质
  const lamps = new Map();           // 灯 key → { head: Vector3, ceiling }
  const meshes = [];
  const box = new THREE.Box3();
  root.traverse((o) => {
    if (!o.isMesh) return;
    o.userData.vmask = maskOf(o);
    const g = o.geometry;
    const n = g.index ? g.index.count : g.attributes.position.count;
    // 统计口径：春季晴天下可见的部分（四季变体不重复计）
    if (o.userData.vmask & springBit) { stats.meshes++; stats.tris += Math.floor(n / 3) * (o.isInstancedMesh ? o.count : 1); }
    const src = o.material;
    // 多材质节点会被拆成「同名 Group + 若干子 mesh」，子 mesh 不带节点名，要往上找 LGT_ 祖先
    let named = o;
    while (named && named !== root && !(named.name || '').startsWith('LGT_')) named = named.parent;
    const raw = stripIdx((named && named !== root ? named : o).name || '');
    const mname = src?.name || '';
    const glowBaked = !!(src?.emissive && (src.emissive.r + src.emissive.g + src.emissive.b) > 0.3);
    let emitter = false, lampKey = null;
    if (raw.startsWith('LGT_')) {
      const mp = raw.match(RE_PART);
      lampKey = mp ? raw.slice(0, mp.index) : raw;
      const isBodyPart = mp && !RE_EMIT.test(raw);
      // 灯具实体（杆/座/帽…）永不发光；其余零件里只有烘了自发光、或名字像灯罩的材质槽发光
      emitter = !isBodyPart && (glowBaked || (GLOWM.test(mname) && !BODYM.test(mname)));
    } else if (mname.startsWith('LGT_') && glowBaked) { emitter = true; lampKey = mname; }
    else if (GLOW_OBJ.test(raw) && glowBaked) { emitter = true; lampKey = raw; }
    const key = src.uuid + (emitter ? ':E' : '');
    let m = matMap.get(key);
    if (!m) { m = convertMaterial(src, emitter, glowU); matMap.set(key, m); }
    o.material = m;
    o.castShadow = !emitter;
    o.receiveShadow = true;
    o.userData.lampKey = emitter ? lampKey : null;
    if (!emitter && !m.transparent && (o.userData.vmask & summerBit) && !o.isInstancedMesh && !/^(Ground|Belt|Port|Track|Snow_)/i.test(raw)) {
      const c = contactItem(o);
      if (c) contact.push(c);
    }
    if (emitter && lampKey) {
      const c = new THREE.Box3().setFromObject(o).getCenter(new THREE.Vector3());
      const L = lamps.get(lampKey);
      if (!L || c.y > L.head.y) lamps.set(lampKey, { head: c, ceiling: /ceiling|pendant|chandelier|indoor|interior/i.test(lampKey) });
    }
    meshes.push(o);
    box.expandByObject(o);
  });
  return { stats, meshes, lamps: [...lamps].map(([k, v]) => ({ key: k, ...v })), box, mats: [...matMap.values()], glowU, contact: mergeContact(contact), entities };
}

// 接触阴影候选：物件的有向包围盒（绕 Y 旋转）落在地台上、够高、占地不过大 → 一张贴地柔边贴片（地块本地坐标）
const _cv = new THREE.Vector3();
function contactItem(o) {
  const P = FX_PARAMS.contact;
  const g = o.geometry;
  if (!g.boundingBox) g.computeBoundingBox();
  const e = o.matrixWorld.elements;
  const rot = Math.atan2(-e[2], e[0]);
  const c = Math.cos(rot), s = Math.sin(rot);
  let x0 = Infinity, x1 = -Infinity, z0 = Infinity, z1 = -Infinity, y0 = Infinity, y1 = -Infinity;
  const b = g.boundingBox;
  for (let i = 0; i < 8; i++) {
    _cv.set(i & 1 ? b.max.x : b.min.x, i & 2 ? b.max.y : b.min.y, i & 4 ? b.max.z : b.min.z).applyMatrix4(o.matrixWorld);
    // 转到物件朝向的坐标系里量长宽
    const u = _cv.x * c - _cv.z * s, v = _cv.x * s + _cv.z * c;
    x0 = Math.min(x0, u); x1 = Math.max(x1, u); z0 = Math.min(z0, v); z1 = Math.max(z1, v);
    y0 = Math.min(y0, _cv.y); y1 = Math.max(y1, _cv.y);
  }
  const h = y1 - Math.max(y0, 0), hx = (x1 - x0) / 2, hz = (z1 - z0) / 2;
  const long = Math.max(hx, hz) * 2;
  if (y0 > P.maxBase || h < P.minH || long < P.minSize || long > P.maxSize) return null;
  // 又大又矮的（平台、地垫、台阶）不贴
  if (hx * hz * 4 > 40 && h < 1.2) return null;
  const u = (x0 + x1) / 2, v = (z0 + z1) / 2;
  return {
    x: u * c + v * s, z: -u * s + v * c, y: Math.max(y0, 0) + 0.012, rot, hx, hz, h,
    fall: THREE.MathUtils.clamp(h * P.fallK, P.fallMin, P.fallMax), k: THREE.MathUtils.clamp(0.45 + h * 0.4, 0.45, 1),
  };
}
// 同一物件拆成多个 mesh（灯座 + 灯杆、桌腿…）会叠出黑块：中心几乎重合、尺寸相近的合成一个
function mergeContact(list) {
  list.sort((a, b) => b.hx * b.hz - a.hx * a.hz);
  const out = [];
  const grid = new Map();
  const cell = 1.0;
  const keyOf = (x, z) => `${Math.floor(x / cell)},${Math.floor(z / cell)}`;
  for (const it of list) {
    let hit = null;
    const gx = Math.floor(it.x / cell), gz = Math.floor(it.z / cell);
    for (let i = -1; i <= 1 && !hit; i++) for (let j = -1; j <= 1 && !hit; j++) {
      for (const q of grid.get(`${gx + i},${gz + j}`) || []) {
        const d = Math.hypot(q.x - it.x, q.z - it.z);
        // 小的整个落在大的里面（或几乎同心）→ 并掉
        const rq = Math.max(q.hx, q.hz), ri = Math.max(it.hx, it.hz);
        if (d + ri <= rq + 0.15 && ri > rq * 0.4 && Math.abs(q.y - it.y) < 0.1) { hit = q; break; }
      }
    }
    if (hit) { hit.k = Math.max(hit.k, it.k); hit.fall = Math.max(hit.fall, it.fall); continue; }
    out.push(it);
    const k = keyOf(it.x, it.z);
    if (!grid.has(k)) grid.set(k, []);
    grid.get(k).push(it);
  }
  return out;
}

// 合并：同一地块内按材质合批（4900 个 mesh → 每块几十个 draw call）
function mergeByMaterial(meshes) {
  const groups = new Map();
  const keep = [];
  for (const o of meshes) {
    if (o.isInstancedMesh || o.isSkinnedMesh || o.morphTargetInfluences) { keep.push(o); continue; }
    // 小零件（包围球半径 < DETAIL_R）单独合批，远看时整批隐藏
    if (!o.geometry.boundingSphere) o.geometry.computeBoundingSphere();
    const r = o.geometry.boundingSphere.radius * o.matrixWorld.getMaxScaleOnAxis();
    // 季节掩码不同的物件分开合批，四季切换只改批次显隐
    const vmask = o.userData.vmask ?? MASK_ALL;
    const key = o.material.uuid + (r < DETAIL_R ? ':d' : '') + ':' + vmask;
    if (!groups.has(key)) groups.set(key, { mat: o.material, detail: r < DETAIL_R, vmask, list: [] });
    groups.get(key).list.push(o);
  }
  const out = [];
  const tmpM = new THREE.Matrix4();
  for (const { mat, detail, vmask, list } of groups.values()) {
    const want = ['position', 'normal'];
    if (mat.map) want.push('uv');
    if (mat.vertexColors) want.push('color');
    if (mat.userData.emitter) want.push('aLampDelay');
    if (mat.userData.wobKind) want.push('aWob');
    const geos = [];
    for (const o of list) {
      let g = o.geometry.clone();
      for (const k of Object.keys(g.attributes)) if (!want.includes(k)) g.deleteAttribute(k);
      for (const k of Object.keys(g.morphAttributes)) delete g.morphAttributes[k];
      if (!g.attributes.normal) g.computeVertexNormals();
      if (mat.userData.emitter) g.setAttribute('aLampDelay', new THREE.Float32BufferAttribute(new Float32Array(g.attributes.position.count).fill(o.userData.lampDelay || 0), 1));
      if (mat.userData.wobKind) g.setAttribute('aWob', new THREE.Float32BufferAttribute(o.userData.wob || new Float32Array(g.attributes.position.count * 4), 4));
      if (want.includes('uv') && !g.attributes.uv) g.setAttribute('uv', new THREE.Float32BufferAttribute(new Float32Array(g.attributes.position.count * 2), 2));
      if (want.includes('color')) {
        const c = g.attributes.color;
        if (!c) g.setAttribute('color', new THREE.Float32BufferAttribute(new Float32Array(g.attributes.position.count * 3).fill(1), 3));
        else if (c.itemSize === 4 || c.normalized || !(c.array instanceof Float32Array)) {
          const a = new Float32Array(c.count * 3);
          for (let i = 0; i < c.count; i++) { a[i * 3] = c.getX(i); a[i * 3 + 1] = c.getY(i); a[i * 3 + 2] = c.getZ(i); }
          g.setAttribute('color', new THREE.Float32BufferAttribute(a, 3));
        }
      }
      for (const k of want) {
        const at = g.attributes[k];
        if (at && (at.isInterleavedBufferAttribute || at.normalized || !(at.array instanceof Float32Array))) {
          const a = new Float32Array(at.count * at.itemSize);
          const get = [at.getX, at.getY, at.getZ, at.getW];
          for (let i = 0; i < at.count; i++) for (let j = 0; j < at.itemSize; j++) a[i * at.itemSize + j] = get[j].call(at, i);
          g.setAttribute(k, new THREE.Float32BufferAttribute(a, at.itemSize));
        }
      }
      if (!g.index) {
        const n = g.attributes.position.count;
        const idx = n > 65535 ? new Uint32Array(n) : new Uint16Array(n);
        for (let i = 0; i < n; i++) idx[i] = i;
        g.setIndex(new THREE.BufferAttribute(idx, 1));
      }
      tmpM.copy(o.matrixWorld);
      g.applyMatrix4(tmpM);
      // 镜像变换烘进顶点后要翻转三角形绕序，否则会被背面剔除
      if (tmpM.determinant() < 0) {
        const ix = g.index.array;
        for (let i = 0; i < ix.length; i += 3) { const t = ix[i + 1]; ix[i + 1] = ix[i + 2]; ix[i + 2] = t; }
      }
      geos.push(g);
    }
    const merged = geos.length === 1 ? geos[0] : mergeGeometries(geos, false);
    for (const g of geos) if (g !== merged) g.dispose();
    if (!merged) { console.warn('[park] merge failed', mat.name); continue; }
    merged.computeBoundingSphere();
    merged.computeBoundingBox();
    if (mat.userData.wobKind && !mat.userData.wob) patchMergedWobble(mat, mat.userData.wobKind);
    const mesh = new THREE.Mesh(merged, mat);
    mesh.name = `m:${mat.name}${detail ? ':detail' : ''}`;
    mesh.userData.detail = detail;
    mesh.userData.vmask = vmask;
    mesh.castShadow = list[0].castShadow;
    mesh.receiveShadow = PLOT_RECEIVE_SHADOW;
    if (mat.transparent) mesh.renderOrder = 2;
    out.push(mesh);
  }
  for (const o of keep) {
    o.updateMatrixWorld(true);
    const c = o.clone();
    c.matrixAutoUpdate = false;
    c.matrix.copy(o.matrixWorld);
    c.receiveShadow = PLOT_RECEIVE_SHADOW;
    out.push(c);
  }
  return out;
}

// 接口实测：找节点，取沿出带方向最远端的顶点，求端面中心（地块本地坐标）
function measurePort(root, spec) {
  const target = sanitize(spec.node);
  let node = null;
  // 模型重导出后节点名可能带后缀（Port_Main_rainbow.rb），这时按 extras.cl_name 认
  root.traverse((o) => { if (!node && (o.name === target || o.name === spec.node || o.userData?.cl_name === spec.node)) node = o; });
  if (!node) return null;
  const ax = spec.axis[0], az = spec.axis[1];
  const pts = [];
  const v = new THREE.Vector3();
  node.updateMatrixWorld(true);
  node.traverse((o) => {
    if (!o.isMesh) return;
    const pa = o.geometry.attributes.position;
    for (let i = 0; i < pa.count; i++) { v.fromBufferAttribute(pa, i).applyMatrix4(o.matrixWorld); pts.push(v.clone()); }
  });
  if (!pts.length) return null;
  let max = -Infinity;
  for (const p of pts) max = Math.max(max, p.x * ax + p.z * az);
  const far = pts.filter((p) => p.x * ax + p.z * az > max - 0.03);
  const c = new THREE.Vector3();
  let ymax = -Infinity, ymin = Infinity;
  for (const p of far) { c.add(p); ymax = Math.max(ymax, p.y); ymin = Math.min(ymin, p.y); }
  c.divideScalar(far.length);
  // Track_*_belt 是带面本体：顶面即带面高；Port_Main_* 是法兰方环：取环心
  const isBelt = /belt/i.test(spec.node) && !/^Port/.test(spec.node);
  c.y = isBelt ? ymax : (ymin + ymax) / 2;
  return { local: c, ymin, ymax, verts: far.length };
}

// 地块端带面高度：在接口内侧往下打射线，取 Belt_* 物件上最高的朝上平面（避开挡边/货箱）
function measureBeltSurface(root, portLocal, spec) {
  const cands = [];
  root.traverse((o) => { if (o.isMesh && /^(Belt|Port)/.test(o.name) && !/guard|rail|parcel|cargo|box|crate|tape|bolt|leg/i.test(o.name)) cands.push(o); });
  if (!cands.length) return null;
  const rc = new THREE.Raycaster();
  const ys = [];
  for (const back of [0.35, 0.6, 0.9]) {
    const o = new THREE.Vector3(portLocal.x - spec.axis[0] * back, 3, portLocal.z - spec.axis[1] * back);
    rc.set(o, new THREE.Vector3(0, -1, 0));
    rc.far = 3.2;
    const hits = rc.intersectObjects(cands, false).filter((h) => h.face && h.face.normal.clone().transformDirection(h.object.matrixWorld).y > 0.9 && h.point.y < 1.3 && h.point.y > 0.15);
    if (hits.length) ys.push(hits[0].point.y);
  }
  if (!ys.length) return null;
  ys.sort((a, b) => a - b);
  return ys[Math.floor(ys.length / 2)];
}

function makeProxy(p, box) {
  const size = box.getSize(new THREE.Vector3());
  const c = box.getCenter(new THREE.Vector3());
  const m = new THREE.Mesh(new THREE.BoxGeometry(size.x, Math.max(1, size.y), size.z), new THREE.MeshBasicMaterial({ visible: false }));
  m.position.copy(c);
  m.userData.plotId = p.id;
  m.name = `proxy:${p.id}`;
  return m;
}

async function loadPlot(p, fetched) {
  const t0 = performance.now();
  const { buf, url } = await fetched;
  const tFetch = performance.now();
  await nextFrame();
  const gltf = await loader.parseAsync(buf, url.href.replace(/[^/]*$/, ''));
  const tParse = performance.now();
  await nextFrame();
  const root = gltf.scene;
  root.updateMatrixWorld(true);
  const prep = prepare(root, p);
  // 接口要在合并前从原始节点上量
  const ports = {};
  for (const b of def.belts) for (const end of [b.from, b.to]) {
    if (end.plot !== p.id || !end.node) continue;
    const m = measurePort(root, end);
    if (!m) { console.warn('[park] 找不到接口节点', p.id, end.node); continue; }
    if (/^Port_Main/.test(end.node)) {
      const ys = measureBeltSurface(root, m.local, end);
      m.surface = ys;
    }
    ports[end.node] = m;
  }
  // 灯的点亮顺序：从地块中心往外，相邻两盏间隔 stagger[0]..stagger[1] 毫秒（确定性抖动）
  const [sa, sb] = FX_PARAMS.fade.stagger;
  const lampDelay = new Map();
  let acc = 0;
  [...prep.lamps].sort((a, b) => Math.hypot(a.head.x, a.head.z) - Math.hypot(b.head.x, b.head.z)).forEach((l, i) => {
    lampDelay.set(l.key, acc / 1000);
    l.delay = acc / 1000;
    const r = Math.sin((i + 1) * 78.233 + p.id.length * 12.9898) * 43758.5453;
    acc += sa + (sb - sa) * (r - Math.floor(r));
  });
  for (const o of prep.meshes) if (o.userData.lampKey) o.userData.lampDelay = lampDelay.get(o.userData.lampKey) || 0;
  // B-7：树 / 旗的逐顶点摆动量（合并前，用原始节点名与包围盒）
  const wob = buildWobble(root, prep.meshes);
  for (const [o, a] of wob) o.userData.wob = a;
  prep.wobble = { tree: 0, flag: 0 };
  for (const o of wob.keys()) prep.wobble[o.material.userData.wobKind]++;
  await nextFrame();
  const merged = mergeByMaterial(prep.meshes);
  // 释放原始几何
  root.traverse((o) => { if (o.isMesh) o.geometry.dispose(); });
  const tMerge = performance.now();

  const holder = new THREE.Group();
  holder.name = `plot:${p.id}`;
  holder.position.set(p.pos[0], p.kind === 'partner' ? GROUND_Y : 0, p.pos[1]);
  holder.rotation.y = deg(p.rotY || 0);
  holder.add(...merged);
  const proxy = makeProxy(p, prep.box);
  holder.add(proxy);
  const contact = prep.contact.length ? buildContactMesh(prep.contact, contactMat) : null;
  if (contact) { contact.visible = !!fxOn.contact; holder.add(contact); }
  scene.add(holder);
  holder.updateMatrixWorld(true);

  const center = new THREE.Vector3(p.pos[0], 0, p.pos[1]);
  const lamps = prep.lamps.map((l) => ({ ...l, world: holder.localToWorld(l.head.clone()), plot: p.id }));
  const plot = {
    def: p, holder, meshes: merged, proxy, mats: prep.mats, stats: prep.stats, lamps, ports, center,
    box: prep.box, height: prep.box.max.y, belts: 0, bytes: buf.byteLength, castShadow: true, entities: prep.entities,
    contact, glowU: prep.glowU, glow: { on: false, t0: 0, mul: 0 }, wobble: prep.wobble,
  };
  plots.set(p.id, plot);
  neighborCache.clear();
  applyGlow(plot);
  applyTint();
  refreshVisibility(plot);
  timings.plots[p.id] = { fetch: Math.round(tFetch - t0), parse: Math.round(tParse - tFetch), merge: Math.round(tMerge - tParse), drawCalls: merged.length };
  log(`${p.id} 就绪 · ${prep.stats.meshes} mesh / ${prep.stats.tris.toLocaleString()} 三角面 → ${merged.length} 批 · 解析 ${Math.round(tParse - tFetch)}ms 合并 ${Math.round(tMerge - tParse)}ms`);
  tryBuildBelts();
  updateShadowCasters(true);
  updateDetail(true);
  if (focused) assignLampLights();
  return plot;
}

// ── 传送带 ──
const CARGO_ALWAYS = false;
let cargoSys = null;
let cargoPollAt = 0;   // true = 传送带常亮货箱（旧行为，用户不要）
const built = new Set();
const beltChecks = [];
function endpoint(end) {
  const plot = plots.get(end.plot);
  if (!plot) return null;
  const h = plot.holder;
  const dirLocal = new THREE.Vector3(end.axis[0], 0, end.axis[1]).normalize();
  const dir = dirLocal.applyQuaternion(h.quaternion).normalize();
  let local, flange = false, measured = null;
  if (end.node) {
    const m = plot.ports[end.node];
    if (!m) return null;
    local = m.local.clone();
    measured = m;
    if (typeof end.y === 'number') local.y = end.y;
    else if (m.surface != null) local.y = m.surface;
  } else {
    local = new THREE.Vector3(...end.local);
    flange = true;
  }
  const pos = h.localToWorld(local.clone());
  if (end.local) pos.y = end.local[1];      // 代码生成接口：y 直接是世界带面高
  return { pos, dir, flange, plot, measured };
}

function tryBuildBelts() {
  if (!beltSys) return;
  for (const b of def.belts) {
    if (built.has(b.id)) continue;
    const a = endpoint(b.from), z = endpoint(b.to);
    if (!a || !z) continue;
    // 起点的 Track_*_belt 末端没有法兰（模型里法兰在大厅内侧），这里补一个接口法兰
    const fromTrack = !!(b.from.node && /^Track_/.test(b.from.node));
    const belt = beltSys.add(b.id, a, z, { flangeA: a.flange || fromTrack, flangeB: z.flange });
    built.add(b.id);
    a.plot.belts++; z.plot.belts++;
    // 用户要求：没有真实业务时传送带上不该有货在跑。默认全部藏起来，
    // 由 P3 的「真实事件驱动包裹」在任务运行时才点亮（见 cargo 相关逻辑）。
    if (belt.cargo) belt.cargo.visible = CARGO_ALWAYS;
    if (belt.dots) belt.dots.visible = CARGO_ALWAYS;
    beltChecks.push({
      id: b.id, from: b.from.plot, to: b.to.plot, length: +belt.len.toFixed(2), minTurnRadius: +belt.plan.minR.toFixed(1),
      start: a.pos.toArray().map((v) => +v.toFixed(3)), end: z.pos.toArray().map((v) => +v.toFixed(3)),
      startGap: +belt.frames[0].p.distanceTo(a.pos).toFixed(4), endGap: +belt.frames[belt.frames.length - 1].p.distanceTo(z.pos).toFixed(4),
    });
  }
}

// ── 邻居：离某块最近的两块（环上就是左右相邻） ──
const neighborCache = new Map();
function neighborsOf(p) {
  if (!p) return [];
  if (!neighborCache.has(p)) {
    neighborCache.set(p, [...plots.values()].filter((q) => q !== p)
      .sort((a, b) => a.center.distanceToSquared(p.center) - b.center.distanceToSquared(p.center)).slice(0, 2));
  }
  return neighborCache.get(p);
}

// ── 阴影投射体：按画质档 ──
let lastShadowCheck = 0;
function updateShadowCasters(force) {
  const now = performance.now();
  if (!force && now - lastShadowCheck < 400) return;
  lastShadowCheck = now;
  const q = QUALITY[qualityCur || qualityUser];
  const list = [...plots.values()];
  const hall = plots.get('control');
  let casters;
  if (!q.shadows || q.casters === 'none') casters = new Set();
  else if (q.casters === 'hall') casters = new Set([hall].filter(Boolean));
  else if (focused) casters = new Set([hall, focused, ...neighborsOf(focused)].filter(Boolean));
  else {
    const others = list.filter((p) => p.def.kind !== 'hall')
      .sort((a, b) => a.center.distanceToSquared(camera.position) - b.center.distanceToSquared(camera.position));
    casters = new Set([hall, ...others.slice(0, SHADOW_NEAR_PLOTS)].filter(Boolean));
  }
  for (const p of list) {
    const on = casters.has(p);
    if (p.castShadow === on) continue;
    p.castShadow = on;
    for (const m of p.meshes) m.castShadow = on && !m.material.userData.emitter && !m.material.transparent;
  }
  shadowState.casters = [...casters].map((p) => p.def.id);
  // 阴影相机包住所有投影体
  const pts = [];
  for (const p of casters) { const r = Math.max(...p.def.size) * 0.75; pts.push(p.center.clone().add(new THREE.Vector3(r, 0, r)), p.center.clone().add(new THREE.Vector3(-r, 14, -r))); }
  if (!pts.length) return;
  const sphere = new THREE.Sphere().setFromPoints(pts);
  const R = sphere.radius + 4;
  sun.target.position.copy(sphere.center);
  sun.position.copy(sphere.center).addScaledVector(sunDir, R + 60);
  const sc = sun.shadow.camera;
  sc.left = sc.bottom = -R; sc.right = sc.top = R;
  // 远平面放到整座岛：低太阳时远处草地不在 far 之内会被误判为阴影（演示 / 跟随模式的早晚可见）
  sc.near = 1; sc.far = R * 2 + 320;
  sc.updateProjectionMatrix();
}
const shadowState = { casters: [] };

// 小零件批次（螺栓、瓦片、草丛…）：中/低画质按距离隐藏；高画质只给聚焦块和左右邻居
let lastDetail = 0;
function updateDetail(force) {
  const now = performance.now();
  if (!force && now - lastDetail < 250) return;
  lastDetail = now;
  const q = QUALITY[qualityCur || qualityUser];
  const near = q.detail === 'focus' && focused ? new Set([focused, ...neighborsOf(focused)]) : null;
  for (const p of plots.values()) {
    const show = near ? near.has(p) : camera.position.distanceTo(p.center) - Math.max(...p.def.size) / 2 < DETAIL_DIST;
    if (p.detailShown === show && !force) continue;
    p.detailShown = show;
    refreshVisibility(p);
  }
}

// 批次显隐 = 季节掩码 × 小零件规则
function refreshVisibility(p) {
  const bit = maskBit(env.season, env.weather === 'snow');
  for (const m of p.meshes) {
    const vm = m.userData.vmask ?? MASK_ALL;
    m.visible = !!(vm & bit) && (!m.userData.detail || p.detailShown !== false);
  }
}

// ── 夜灯：只有「夜间 + 被聚焦」的那一块发光，其余所有地块的自发光为 0 ──
// 亮起：灯罩按 aLampDelay 逐盏亮（uLampT 从 t0 起计秒），真实点光源跟着同一盏灯的延迟；熄灭：整体 lampOffMs 内淡出
function applyGlow(p, delayMs = 0) {
  const on = night && p === focused;
  const g = p.glow;
  const now = performance.now();
  if (on && !g.on) {
    g.on = true;
    // 不逐盏亮时一次全亮（同 P0）
    g.t0 = fxOn.lamps ? now + delayMs : now - 1e6;
    for (const m of p.mats) if (m.userData.emitter) { m.emissive.copy(LAMP_EMISSIVE); m.emissiveIntensity = LAMP_EMISSIVE_K; }
  } else if (!on && g.on) {
    g.on = false;
    g.offT0 = fxOn.fade ? now : now - 1e6;
  }
  if (!g.on && g.mul <= 0) for (const m of p.mats) if (m.userData.emitter) { m.emissive.setRGB(0, 0, 0); m.emissiveIntensity = 1; }
}
const lampK = (p, delay) => {
  const u = p.glowU;
  const d = delay * u.uLampStag.value;
  return u.uLampMul.value * THREE.MathUtils.smoothstep(u.uLampT.value, d, d + u.uLampRise.value);
};
function updateGlow(now) {
  for (const p of plots.values()) {
    const g = p.glow, u = p.glowU;
    if (g.on) { g.mul = 1; u.uLampT.value = (now - g.t0) / 1000; }
    else if (g.mul > 0) {
      g.mul = Math.max(0, 1 - (now - g.offT0) / FX_PARAMS.fade.lampOffMs);
      if (g.mul <= 0) applyGlow(p);
    }
    u.uLampMul.value = g.mul;
  }
  for (const l of lampLights) {
    const a = l.userData.assign;
    l.intensity = a ? a.base * lampK(a.plot, a.delay) : 0;
  }
}

// 材质颜色 = 原色 × 雨天压暗（湿感）× 地块弱光校准；首次见到的材质先记下原色。
// fade = true：不直接改色，交给 stepLook 在渐变里从当前倍率插到目标倍率
function applyTint(fade = false) {
  const k = env.weather === 'rain' ? WET_DARKEN : 1;
  // 冬季有屋顶 / 地面积雪，各块积雪面积不同，单独一组（下雪天本来就带积雪，与冬季共用 *.snow）
  const gkey = `${night ? 'night' : 'day'}.${env.weather}${env.season === 'winter' && env.weather !== 'snow' ? '.winter' : ''}`;
  const gains = PLOT_GAIN[gkey] || {};
  const want = new Map();
  for (const p of plots.values()) {
    const g = (gains[p.def.id] ?? 1) * k;
    for (const m of p.mats) want.set(m, g);
  }
  scene.traverse((o) => {
    if (!o.isMesh && !o.isInstancedMesh) return;
    const mats = Array.isArray(o.material) ? o.material : [o.material];
    for (const m of mats) {
      if (!m || want.has(m) || !(m.isMeshLambertMaterial || m.isMeshPhongMaterial)) continue;
      if (!m.userData.baseColor) m.userData.baseColor = m.color.clone();
      want.set(m, k);
    }
  });
  look.tints = [];
  for (const [m, g] of want) {
    const from = m.userData.gain ?? 1;
    if (fade && Math.abs(from - g) > 1e-4) look.tints.push({ m, from, to: g });
    else { m.userData.gain = g; m.color.copy(m.userData.baseColor).multiplyScalar(g); }
  }
}

// ── 观感渐变（A-4）：applyEnv 只算目标值，stepLook 每帧从起点插到目标（天空 / 雾 / 半球光 / 太阳 / 曝光 / 分级 / 材质倍率 / 降水）──
const LOOK_COLORS = ['sky', 'hemiC', 'hemiG', 'sunC'];
const LOOK_NUMS = ['hemiI', 'sunI', 'shadow', 'exposure', 'fogNear', 'fogFar', 'contrast', 'sat', 'warm', 'lut', 'vig', 'bloom', 'cloud'];
const look = { cur: null, from: null, to: null, t0: null, dur: 0, tints: [], precip: null };
function lookTarget(L, q) {
  return {
    sky: new THREE.Color(L.sky), hemiC: new THREE.Color(L.hemi[0]), hemiG: new THREE.Color(L.hemi[1]), sunC: new THREE.Color(L.sun[0]),
    hemiI: L.hemi[2], sunI: L.sun[1], shadow: L.shadow, exposure: L.exposure,
    // 雾起点固定（全景镜头下 12 块都在雾外，远近地块不会被雾染出明暗差），天气只把雾的终点拉近
    fogNear: q.fog[0], fogFar: Math.max(q.fog[0] + 50, q.fog[1] * L.fogK),
    contrast: L.grade[0], sat: L.grade[1], warm: L.grade[2], lut: L.lut, vig: L.vig, bloom: L.bloom, cloud: L.cloud,
  };
}
const cloneLook = (v) => { const o = { ...v }; for (const k of LOOK_COLORS) o[k] = v[k].clone(); return o; };
const sameLook = (a, b) => LOOK_COLORS.every((k) => a[k].equals(b[k])) && LOOK_NUMS.every((k) => Math.abs(a[k] - b[k]) < 1e-6);
function writeLook(v) {
  scene.background.copy(v.sky);
  scene.fog.color.copy(v.sky);
  scene.fog.near = v.fogNear; scene.fog.far = v.fogFar;
  hemi.color.copy(v.hemiC); hemi.groundColor.copy(v.hemiG); hemi.intensity = v.hemiI;
  sun.color.copy(v.sunC); sun.intensity = v.sunI;
  sun.shadow.intensity = v.shadow;
  renderer.toneMappingExposure = v.exposure;
  const u = post.final.uniforms;
  u.uExposure.value = v.exposure;
  u.uContrast.value = v.contrast; u.uSaturation.value = v.sat; u.uWarm.value = v.warm;
  // 聚焦时把暗角压到 40%，否则推近后四周会像被压暗（用户 2026-10-31 反馈）
  const FOCUS_VIG_K = 0.4;
  const vigK = focused ? FOCUS_VIG_K : 1;
  u.uLut.value = v.lut; u.uVignette.value = v.vig * vigK; u.uBloom.value = v.bloom; u.uCloud.value = v.cloud;
}
function stepLook(now) {
  if (look.t0 == null) return;
  const k = look.dur > 0 ? THREE.MathUtils.clamp((now - look.t0) / look.dur, 0, 1) : 1;
  const e = k * k * (3 - 2 * k);
  const c = look.cur;
  for (const key of LOOK_COLORS) c[key].copy(look.from[key]).lerp(look.to[key], e);
  for (const key of LOOK_NUMS) c[key] = look.from[key] + (look.to[key] - look.from[key]) * e;
  for (const t of look.tints) { const g = t.from + (t.to - t.from) * e; t.m.userData.gain = g; t.m.color.copy(t.m.userData.baseColor).multiplyScalar(g); }
  // 降水：同种只调浓度；换种时前半程淡出旧的、后半程淡入新的
  const pr = look.precip;
  if (pr && precip) {
    if (pr.from === pr.to) precip.set(pr.to, pr.en, pr.dimFrom + (pr.dimTo - pr.dimFrom) * e);
    else if (e < 0.5) precip.set(pr.from, pr.en, pr.dimFrom * (1 - 2 * e));
    else precip.set(pr.to, pr.en, pr.dimTo * (2 * e - 1));
  }
  writeLook(c);
  if (k >= 1) { look.t0 = null; look.tints = []; look.precip = null; settleEnv(); }
}
// 渐变结束后才关的东西（提前关会硬切）：太阳阴影、白天的灯光源
function settleEnv() {
  const L = LIGHTING[night ? 'night' : 'day'][env.weather];
  const q = QUALITY[qualityCur || qualityUser];
  const sunShadow = q.shadows && L.sun[1] > 0.01 && L.shadow > 0.01;
  if (sun.castShadow !== sunShadow) sun.castShadow = sunShadow;
  if (!night && lampLights.length) {
    for (const l of lampLights) { scene.remove(l); l.dispose(); }
    lampLights.length = 0;
  }
}

// ── 环境：季节 × 昼夜 × 天气 ──
function meteoSeason(d) {
  const mon = Number(new Intl.DateTimeFormat('en-US', { timeZone: LOCATION.timeZone, month: 'numeric' }).format(d));
  return mon >= 3 && mon <= 5 ? 'spring' : mon >= 6 && mon <= 8 ? 'summer' : mon >= 9 && mon <= 11 ? 'autumn' : 'winter';
}

let precipShown = { kind: null, dim: 1 };
// opts.instant：跳过渐变（截图 / 测帧用）
function applyEnv({ instant = false } = {}) {
  const wasNight = night;
  night = env.night;
  const L = LIGHTING[night ? 'night' : 'day'][env.weather];
  const q = QUALITY[qualityCur || qualityUser];
  document.body.classList.toggle('night', night);
  document.body.dataset.weather = env.weather;
  const to = lookTarget(L, q);
  const fadeMs = fxOn.fade && !instant && look.cur ? FX_PARAMS.fade.ms : 0;
  // 目标没变（切画质 / 聚焦触发的重算）就不重启渐变
  const changed = !look.to || !sameLook(look.to, to);
  if (changed || instant) {
    look.from = cloneLook(look.cur || to);
    look.cur = cloneLook(look.from);
    look.to = to;
    look.t0 = performance.now();
    look.dur = fadeMs;
  }
  // 阴影只在渐变开始时打开（关闭放到 settleEnv）
  const sunShadow = q.shadows && L.sun[1] > 0.01 && L.shadow > 0.01;
  if (sunShadow && !sun.castShadow) sun.castShadow = true;
  for (const p of plots.values()) refreshVisibility(p);
  if (changed || instant || look.t0 == null) applyTint(fadeMs > 0);
  // 天黑过程中走到 lampAt 才开始点灯
  const lampDelay = fadeMs && night && !wasNight ? fadeMs * FX_PARAMS.fade.lampAt : 0;
  for (const p of plots.values()) applyGlow(p, lampDelay);
  beltSys?.setNight(night);
  const kind = env.weather === 'rain' || env.weather === 'snow' ? env.weather : null;
  const dim = night ? PRECIP.nightDim : 1;
  if (fadeMs && (kind !== precipShown.kind || dim !== precipShown.dim)) {
    look.precip = { from: precipShown.kind, to: kind, en: q.particles, dimFrom: precipShown.dim, dimTo: dim };
  } else if (look.precip) look.precip.en = q.particles;
  else precip?.set(kind, q.particles, dim);
  precipShown = { kind, dim };
  // 真实光源：固定 LIGHT_CAP 个，夜间才进场景（数量只在切换昼夜时变一次，避免反复重编译着色器）；天亮时等渐变结束再撤
  if (night && !lampLights.length) {
    for (let i = 0; i < LIGHT_CAP; i++) {
      const l = new THREE.PointLight(LAMP_COLOR, 0, 9, 2);
      l.name = `lampLight${i}`;
      l.shadow.mapSize.set(LAMP_SHADOW_MAP, LAMP_SHADOW_MAP);
      l.shadow.bias = -0.004;
      l.shadow.camera.near = 0.2;
      lampLights.push(l);
      scene.add(l);
    }
  }
  assignLampLights();
  if (!fadeMs) stepLook(performance.now());
  updateGlow(performance.now());
  syncEnvButtons();
  updateEnvHud(true);
}

// 夜间着色器预热：8 盏点光进场 / 太阳阴影关掉 / 室内灯开投影都会让全场材质重编译（实测各卡 3~4 秒，演示傍晚整页冻住）。
// 只备当前画质档入夜会用到的两套（太阳阴影开 → 渐变结束后关）：临时摆灯 → compile → 撤灯，同一个任务内完成，不出帧。
// 后期开着时场景画进 post.rtScene（不做 tone mapping，程序键与直出屏幕不同），所以要按实际目标编译
const nightWarm = new Set();
function prewarmNight() {
  const tier = qualityCur || qualityUser, q = QUALITY[tier];
  if (nightWarm.has(tier) || lampLights.length) return;
  nightWarm.add(tier);
  const t0 = performance.now();
  const tmp = Array.from({ length: LIGHT_CAP }, () => new THREE.PointLight(LAMP_COLOR, 0, 9, 2));
  const sunShadow = sun.castShadow, prevTarget = renderer.getRenderTarget();
  tmp[0].castShadow = q.lampShadows > 0;
  for (const l of tmp) scene.add(l);
  try {
    renderer.setRenderTarget(usePost() ? post.rtScene : null);
    for (const on of q.shadows ? [true, false] : [false]) { sun.castShadow = on; renderer.compile(scene, camera); }
  } finally {
    renderer.setRenderTarget(prevTarget);
    sun.castShadow = sunShadow;
    for (const l of tmp) { scene.remove(l); l.dispose(); }
  }
  timings.nightWarm = Math.round(performance.now() - t0);
}

function setEnv(patch, opts) {
  Object.assign(env, patch);
  applyEnv(opts);
}
// 旧接口保留
function setNight(on) { setEnv({ night: !!on }); }

// 聚焦地块的灯按离地块中心远近分给 LIGHT_CAP 个光源；照程收到碰不到别的地块为止。
// 没有聚焦 / 白天：全部 0。实际亮度每帧在 updateGlow 里乘上该灯的点亮进度
function assignLampLights() {
  if (!lampLights.length) return;
  const q = QUALITY[qualityCur || qualityUser];
  const list = night && focused ? [...focused.lamps].sort((a, b) => a.world.distanceToSquared(focused.center) - b.world.distanceToSquared(focused.center)) : [];
  const others = [...plots.values()].filter((p) => p !== focused);
  let shadowsLeft = q.lampShadows;
  lampLights.forEach((l, i) => {
    const lamp = list[i];
    let wantShadow = false;
    if (!lamp) { l.intensity = 0; l.userData.lamp = null; l.userData.assign = null; }
    else {
      l.position.copy(lamp.world);
      if (lamp.ceiling) l.position.y -= 0.4;
      // 到最近一块别的地块边缘的水平距离
      let gap = Infinity;
      for (const p of others) {
        const r = p.def.round || Math.max(...p.def.size) / 2 * Math.SQRT2;
        gap = Math.min(gap, Math.hypot(l.position.x - p.center.x, l.position.z - p.center.z) - r);
      }
      l.userData.assign = { plot: focused, delay: lamp.delay || 0, base: lamp.ceiling ? LAMP_POWER.ceiling : LAMP_POWER.outdoor };
      l.distance = Math.max(LAMP_MIN_RANGE, Math.min(lamp.ceiling ? LAMP_RANGE.ceiling : LAMP_RANGE.outdoor, gap));
      l.userData.lamp = `${lamp.plot}:${lamp.key}`;
      if (lamp.ceiling && shadowsLeft > 0) { wantShadow = true; shadowsLeft--; l.shadow.camera.far = l.distance; }
    }
    if (l.castShadow !== wantShadow) l.castShadow = wantShadow;
  });
}

// ── 画质 ──
function applyQuality() {
  const want = focused && QUALITY_ON_FOCUS ? QUALITY_ON_FOCUS : qualityUser;
  const changed = want !== qualityCur;
  qualityCur = want;
  const q = QUALITY[qualityCur];
  refreshFx();
  setAmbientTier(qualityCur);
  sky.setTier(qualityCur);
  if (changed) {
    renderer.setPixelRatio(q.dpr());
    resize();
    renderer.shadowMap.enabled = q.shadows;
    if (sun.shadow.mapSize.x !== q.shadowMap) {
      sun.shadow.mapSize.set(q.shadowMap, q.shadowMap);
      sun.shadow.map?.dispose(); sun.shadow.map = null;
    }
  }
  updateShadowCasters(true);
  updateDetail(true);
  applyEnv();
  document.querySelectorAll('[data-group="quality"] button').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.v === qualityUser)));
  ui.qualityNote.hidden = qualityCur === qualityUser;
  ui.qualityNote.textContent = `聚焦中·临时${q.label}`;
}
function setQuality(v) {
  if (!QUALITY[v]) return;
  qualityUser = v;
  applyQuality();
}

// ── 观感效果开关：画质档决定默认，URL ?fx= 或 __park.fx.set() 覆盖 ──
function parseFx(v) {
  if (v == null) return null;
  const s = String(v).trim().toLowerCase();
  if (s === '' || s === 'tier' || s === 'auto') return null;
  if (s === 'all' || s === 'on') return [...FX_KEYS];
  if (s === 'none' || s === 'off') return [];
  const list = s.split(/[\s,]+/).filter((k) => FX_KEYS.includes(k));
  const bad = s.split(/[\s,]+/).filter((k) => k && !FX_KEYS.includes(k));
  if (bad.length) console.warn('[park] 不认识的 fx：', bad.join(','), '可选：', FX_KEYS.join(','));
  return list;
}
let fxOverride = parseFx(new URLSearchParams(location.search).get('fx'));
const fxOn = Object.fromEntries(FX_KEYS.map((k) => [k, false]));
const POST_FX = ['dof', 'grade', 'vignette', 'bloom', 'cloud'];
function refreshFx() {
  const list = fxOverride ?? FX_TIER[qualityCur || qualityUser];
  for (const k of FX_KEYS) fxOn[k] = list.includes(k);
  post.setEnabled(Object.fromEntries(POST_FX.map((k) => [k, fxOn[k]])));
  for (const p of plots.values()) {
    if (p.contact) p.contact.visible = fxOn.contact;
    p.glowU.uLampStag.value = fxOn.lamps ? 1 : 0;
  }
}
// 后期：中/高画质一直走（色调映射 + P0 基础分级）；低画质只有被 fx 覆盖打开了屏幕效果才走
const usePost = () => QUALITY[qualityCur || qualityUser].post || POST_FX.some((k) => fxOn[k]);

// 景深：只在聚焦且镜头飞到位后渐入，退出聚焦 / 开始飞行时渐出（全景 amt = 0，全清楚）
const dofState = { amt: 0, R: 10 };
function updateDof(dt) {
  const P = FX_PARAMS.dof;
  const want = fxOn.dof && focused && !tween ? 1 : 0;
  const step = dt / P.rampMs;
  dofState.amt = want > dofState.amt ? Math.min(1, dofState.amt + step) : Math.max(0, dofState.amt - step * 2);
  const fu = post.focusU;
  fu.amt.value = dofState.amt * dofState.amt * (3 - 2 * dofState.amt);
  // P5b：暗角跟聚焦状态走（含飞行途中），聚焦时压到 0，全景恢复
  const vk = focused ? 0 : 1;
  dofState.vig = (dofState.vig ?? 1) + (vk - (dofState.vig ?? 1)) * Math.min(1, dt / P.rampMs * 2);
  post.final.uniforms.uVigMul.value = dofState.vig;
  if (dofState.amt <= 0) return;
  if (focused) dofState.R = Math.max(...focused.def.size) / 2;
  const dist = camera.position.distanceTo(controls.target);
  fu.dist.value = dist;
  fu.range.value = THREE.MathUtils.clamp(dofState.R * P.rangeK / dist, P.rangeMin, P.rangeMax);
  fu.fade.value = P.fade;
  fu.edge0.value = P.edge0; fu.edge1.value = P.edge1; fu.edgeK.value = P.edgeK;
  plateV.copy(controls.target).project(camera);
  fu.uv.value.set(plateV.x * 0.5 + 0.5, plateV.y * 0.5 + 0.5);
  post.blur.uniforms.uMaxR.value = P.maxBlur * post.size.y / 2;   // 半分辨率像素
}

// ── 聚焦状态机：null = 全景。点地块 → 聚焦（切换）；全景按钮 / 双击空白 / R → 退出 ──
function setFocus(p, { fly = true } = {}) {
  const prev = focused;
  focused = p || null;
  for (const q of [prev, focused]) if (q) applyGlow(q);
  if (focused) {
    showCard(focused);           // 先换标题 + 骨架（同步），再飞镜头
    if (fly) focusPlot(focused);
    ui.focusName.textContent = focused.def.name;
    ui.focusPlate.textContent = focused.def.name;
  } else {
    hideCard();
  }
  ui.focusChip.hidden = !focused;
  ui.focusPlate.hidden = !focused;
  if (hovered) setHover(hovered, true);
  applyQuality();
}
function exitFocus() {
  focusOrbit = null;
  setFocus(null);
  goHome();
}

// ── 悬停 / 点击 ──
// 悬停只显示名牌气泡（跟着鼠标），不改任何材质
const raycaster = new THREE.Raycaster();
const pointer = new THREE.Vector2();
let hovered = null;
let pointerDirty = false;
let pointerIn = false;
let downAt = null;
const lastPointer = { x: 0, y: 0 };

function pick(clientX, clientY) {
  const r = ui.canvas.getBoundingClientRect();
  pointer.set(((clientX - r.left) / r.width) * 2 - 1, -((clientY - r.top) / r.height) * 2 + 1);
  raycaster.setFromCamera(pointer, camera);
  const proxies = [...plots.values()].map((p) => p.proxy);
  const hit = raycaster.intersectObjects(proxies, false)[0];
  return hit ? plots.get(hit.object.userData.plotId) : null;
}
function setHover(p, force) {
  if (p === hovered && !force) return;
  hovered = p;
  // 聚焦块已经常驻强调色名牌，不再叠一个悬停气泡
  ui.plate.hidden = !p || p === focused;
  if (p) ui.plate.textContent = p.def.name;
  ui.canvas.style.cursor = p ? 'pointer' : '';
  placeHoverPlate();
}
function placeHoverPlate() {
  if (ui.plate.hidden) return;
  // 气泡放在鼠标右上方，离开指针一段距离，不挡住指着的那一块
  const w = ui.plate.offsetWidth, h = ui.plate.offsetHeight;
  const x = Math.min(window.innerWidth - w - 8, lastPointer.x + 16);
  const y = Math.max(8, lastPointer.y - h - 18);
  ui.plate.style.transform = `translate(${x}px, ${y}px)`;
}
ui.canvas.addEventListener('pointermove', (e) => {
  pointerIn = true; pointer.userData = e; pointerDirty = true;
  lastPointer.x = e.clientX; lastPointer.y = e.clientY;
  placeHoverPlate();
});
ui.canvas.addEventListener('pointerleave', () => { pointerIn = false; setHover(null); });
ui.canvas.addEventListener('pointerdown', (e) => { downAt = { x: e.clientX, y: e.clientY }; });
let clickTimer = null;
ui.canvas.addEventListener('click', (e) => {
  if (demo.on) return;
  if (!downAt || Math.hypot(e.clientX - downAt.x, e.clientY - downAt.y) > 5) return;
  const p = pick(e.clientX, e.clientY);
  clearTimeout(clickTimer);
  // 等一下看是不是双击；单击空白不改变聚焦
  clickTimer = setTimeout(() => { if (p) setFocus(p); }, DBLCLICK_MS);
});
ui.canvas.addEventListener('dblclick', (e) => {
  if (demo.on) return;
  clearTimeout(clickTimer);
  const p = pick(e.clientX, e.clientY);
  if (p) setFocus(p); else exitFocus();
});

// ── 相机动画 ──
let tween = null;
let focusOrbit = null;               // { t0, applied }：聚焦到位后的轻轨道摆动
// 鼠标一按（拖 / 滚轮）立即接管：飞行、聚焦摆动都停
controls.addEventListener('start', () => { tween = null; focusOrbit = null; });
function flyTo(target, position, dur = 1100, { lift = 0, onDone = null } = {}) {
  tween = { t0: performance.now(), dur, fromT: controls.target.clone(), fromP: camera.position.clone(), toT: target, toP: position, lift, onDone };
}
function flyToPoint(center, dist = 26) {
  const dir = camera.position.clone().sub(controls.target).normalize();
  const pos = center.clone().addScaledVector(dir, dist).setY(Math.max(center.y + dist * 0.55, 6));
  flyTo(center.clone(), pos, 900);
}
function homePose() {
  const c = def.camera;
  const t = new THREE.Vector3(...c.homeTarget);
  const p = new THREE.Vector3().setFromSphericalCoords(c.homeDistance, deg(c.homePolarDeg), deg(c.homeAzimuthDeg)).add(t);
  return { t, p };
}
function goHome(animate = true) {
  const { t, p } = homePose();
  hideCard();
  focusOrbit = null;
  if (!animate) { controls.target.copy(t); camera.position.copy(p); controls.update(); return; }
  // 拉远时沿弧线先升后落，带一点上升感
  flyTo(t, p, 1500, { lift: p.distanceTo(t) * CAM.homeLift });
}
function focusPlot(p) {
  const size = Math.max(...p.def.size);
  const t = p.center.clone().setY(Math.min(3, p.height * 0.3));
  let dir = camera.position.clone().sub(controls.target).setY(0);
  if (dir.lengthSq() < 1e-3) dir.set(0, 0, 1);
  dir.normalize();
  const dist = size * 2.0 + p.height * 0.8;
  const pos = t.clone().addScaledVector(dir, dist * Math.sin(deg(52))).add(new THREE.Vector3(0, dist * Math.cos(deg(52)), 0));
  focusOrbit = null;
  flyTo(t, pos, 1100, { onDone: () => { if (focused === p) focusOrbit = { t0: performance.now(), applied: 0 }; } });
}
function stepTween(now) {
  const k = THREE.MathUtils.clamp((now - tween.t0) / tween.dur, 0, 1);
  const e = k < 0.5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2;
  controls.target.lerpVectors(tween.fromT, tween.toT, e);
  camera.position.lerpVectors(tween.fromP, tween.toP, e);
  // 上升感：高度比水平方向先走（缓出），中途再多抬 lift 米后落回
  if (tween.lift) camera.position.y = THREE.MathUtils.lerp(tween.fromP.y, tween.toP.y, 1 - Math.pow(1 - k, 2.4)) + tween.lift * Math.sin(Math.PI * Math.pow(k, 0.8));
  if (k >= 1) { const done = tween.onDone; tween = null; if (done) done(); }
}
const _ov = new THREE.Vector3();
function stepFocusOrbit(now) {
  const t = now - focusOrbit.t0;
  const off = deg(CAM.orbitAmp) * Math.sin(2 * Math.PI * t / CAM.orbitPeriod) * THREE.MathUtils.smoothstep(t, 0, CAM.orbitRamp);
  const d = off - focusOrbit.applied;
  focusOrbit.applied = off;
  _ov.copy(camera.position).sub(controls.target).applyAxisAngle(THREE.Object3D.DEFAULT_UP, d);
  camera.position.copy(controls.target).add(_ov);
}
function setSpin(v) {
  if (!CAM.spin[v]) return;
  controls.autoRotateSpeed = CAM.spin[v];
  controls.autoRotate = true;
  ui.btnRotate.setAttribute('aria-pressed', 'true');
  document.querySelectorAll('[data-group="spin"] button').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.v === v)));
}

// ── 信息卡 ──
function showCard(p) {
  ui.cardTitle.textContent = p.def.name;
  const rows = [
    ['尺寸', `${p.def.size[0]} × ${p.def.size[1]} m${p.def.round ? '（圆盘）' : ''}`],
    ['网格数', p.stats.meshes.toLocaleString('zh-CN')],
    ['三角面', p.stats.tris.toLocaleString('zh-CN')],
    ['传送带', `${p.belts} 条`],
    ['坐标', `x ${p.def.pos[0]} · z ${p.def.pos[1]}`],
    ['文件', `${p.def.file} · ${(p.bytes / 1048576).toFixed(1)} MB`],
  ];
  ui.cardBody.replaceChildren(...rows.map(([k, v]) => {
    const dt = document.createElement('dt'); dt.textContent = k;
    const dd = document.createElement('dd'); dd.textContent = v;
    const div = document.createElement('div'); div.append(dt, dd);
    return div;
  }));
  if (p.def.desc) {
    const d = document.createElement('p'); d.className = 'card__desc'; d.textContent = p.def.desc;
    ui.cardBody.append(d);
  }
  ui.card.hidden = false;
  setPanelPlot(p.def.id);
}
function hideCard() { ui.card.hidden = true; setPanelPlot(null); }
ui.cardClose.addEventListener('click', hideCard);

// ── 按钮 ──
ui.btnHome.addEventListener('click', () => exitFocus());
ui.btnDemo.addEventListener('click', () => (demo.on ? exitDemo() : enterDemo()));
ui.btnRotate.addEventListener('click', () => {
  controls.autoRotate = !controls.autoRotate;
  ui.btnRotate.setAttribute('aria-pressed', String(controls.autoRotate));
});
// 环境 / 画质分段按钮：data-group = season | time | weather | quality
document.querySelectorAll('.seg').forEach((g) => g.addEventListener('click', (e) => {
  const b = e.target.closest('button[data-v]');
  if (!b) return;
  const v = b.dataset.v;
  if (g.dataset.group === 'season') setEnv({ season: v });
  else if (g.dataset.group === 'time') setEnv({ night: v === 'night' });
  else if (g.dataset.group === 'weather') setEnv({ weather: v });
  else if (g.dataset.group === 'quality') setQuality(v);
  else if (g.dataset.group === 'source') setLiveMode(v === 'live');
  else if (g.dataset.group === 'spin') setSpin(v);
}));
function syncEnvButtons() {
  const cur = { season: env.season, time: env.night ? 'night' : 'day', weather: env.weather, source: env.source };
  for (const [k, v] of Object.entries(cur)) {
    document.querySelectorAll(`[data-group="${k}"] button`).forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.v === v)));
  }
}
window.addEventListener('keydown', (e) => {
  if (demo.on) { if (e.key === 'Escape') exitDemo(); return; }
  if (e.key === 'Escape') hideCard();
  if (e.key === 'r' || e.key === 'R') exitFocus();
});


// ── 跟随模式（P1）：真实时间 + 嘉定天气 + 真实太阳角度 ──
const LIVE = { weather: null, temp: null, text: null, fetchedAt: 0, ok: false, rise: null, set: null, alt: null, az: null };
const LIVE_URL = 'https://api.open-meteo.com/v1/forecast?latitude=31.38&longitude=121.25'
  + '&current=temperature_2m,weather_code&daily=sunrise,sunset&timezone=Asia%2FShanghai&forecast_days=1';
const LIVE_TTL = 10 * 60 * 1000;

// 把实况写进环境（source 切到 live）。原来是 __park 对象上的方法，这里补一个模块内函数。
function applyLiveEnv(v) {
  if (demo.on) return;      // 演示期间到达的实况不生效
  liveEnv = v || null;
  env.source = v ? 'live' : 'manual';
  if (v?.weather) env.weather = v.weather;
  applyEnv();
}

// 由真实太阳高度角/方位角驱动平行光。方位角自正北顺时针；场景里 +X 东、+Z 南。
function applySolar(force = false) {
  if (env.source !== 'live' && !demo.on) return;
  const now = demo.on ? demo.date : new Date();
  const { altitude, azimuth } = solarPosition(now, LOCATION.lat, LOCATION.lon, LOCATION.tz);
  LIVE.alt = altitude; LIVE.az = azimuth;
  const a = deg(azimuth), h = deg(altitude);
  sunDir.set(Math.sin(a) * Math.cos(h), Math.max(0.02, Math.sin(h)), -Math.cos(a) * Math.cos(h)).normalize();
  updateShadowCasters(true);
  // 渐变进行中不要抢颜色/强度，等渐变结束再说
  if (look.t0 != null) return;
  const nightNow = altitude < -0.833;
  if (env.night !== nightNow) { setEnv({ night: nightNow }); return; }
  const k = THREE.MathUtils.clamp(altitude / 28, 0, 1);           // 0=贴近地平线，1=高天
  const warm = new THREE.Color(0xFFB36B), noon = new THREE.Color(0xFFF3E0);
  sun.color.copy(warm).lerp(noon, k);
  const baseI = LIGHTING[env.night ? 'night' : 'day'][env.weather].sun[1];
  sun.intensity = env.night ? baseI : baseI * (0.25 + 0.75 * k);
  if (force) updateEnvHud(true);
}

function _pickTime(iso) { const m = /T(\d{2}:\d{2})/.exec(String(iso || '')); return m ? m[1] : null; }

async function fetchLive(force = false) {
  if (env.source !== 'live') return;
  const now = Date.now();
  if (!force && LIVE.fetchedAt && now - LIVE.fetchedAt < LIVE_TTL) return;
  try {
    const ctl = new AbortController();
    const timer = setTimeout(() => ctl.abort(), 9000);
    const r = await fetch(LIVE_URL, { cache: 'no-store', signal: ctl.signal });
    clearTimeout(timer);
    if (!r.ok) throw new Error('http ' + r.status);
    const j = await r.json();
    const t = j?.current?.temperature_2m;
    const code = j?.current?.weather_code;
    const { weather, text } = weatherFromWmo(code, t);
    LIVE.weather = weather; LIVE.temp = t == null ? null : Math.round(t); LIVE.text = text;
    LIVE.rise = _pickTime(j?.daily?.sunrise?.[0]);
    LIVE.set = _pickTime(j?.daily?.sunset?.[0]);
    LIVE.fetchedAt = Date.now(); LIVE.ok = true;
    setEnv({ weather, season: meteoSeason(new Date()) });
    applyLiveEnv({ weather, temp: LIVE.temp, text: LIVE.text, rise: LIVE.rise, set: LIVE.set, offline: false });
  } catch (e) {
    LIVE.ok = false;
    LIVE.fetchedAt = Date.now() - LIVE_TTL + 60 * 1000;    // 一分钟后重试
    // 降级：拉不到就用上次的值/手动值，HUD 标「离线」，页面不报错
    const w = LIVE.weather || env.weather;
    const tmp = LIVE.temp ?? MANUAL_TEMP[env.season][w];
    applyLiveEnv({ weather: w, temp: tmp, text: (LIVE.text || WEATHER_TEXT[w]) + '·离线', rise: LIVE.rise, set: LIVE.set, offline: true });
  }
  updateEnvHud(true);
}

function setLiveMode(on) {
  if (on) {
    env.source = 'live';
    LIVE.fetchedAt = 0;
    fetchLive(true);
    applySolar(true);
  } else {
    env.source = 'manual';
    liveEnv = null;
    sunDir.copy(KEY_DIR);
    updateShadowCasters(true);
    applyEnv();
    updateEnvHud(true);
  }
  syncEnvButtons();
}

// ── 右上角 HUD：时间 / 日期星期 / 地点 / 天气 / 日出日落 ──
// 本轮只有手动模式：时间取系统真实时间（按嘉定时区显示），天气取手动选择，气温为季节 × 天气典型值。
// 跟随模式（P1）接口：__park.setLiveEnv({ weather, temp, text })，填入后 HUD 显示「实况」
const fmtTime = new Intl.DateTimeFormat('zh-CN', { timeZone: LOCATION.timeZone, hour: '2-digit', minute: '2-digit', hour12: false });
const fmtDate = new Intl.DateTimeFormat('zh-CN', { timeZone: LOCATION.timeZone, month: 'long', day: 'numeric', weekday: 'short' });
const fmtYMD = new Intl.DateTimeFormat('en-CA', { timeZone: LOCATION.timeZone, year: 'numeric', month: '2-digit', day: '2-digit' });
const WEATHER_ICON = {
  sunny: '<circle cx="8" cy="8" r="3" /><path d="M8 1.5v1.6M8 12.9v1.6M1.5 8h1.6M12.9 8h1.6M3.4 3.4l1.1 1.1M11.5 11.5l1.1 1.1M3.4 12.6l1.1-1.1M11.5 4.5l1.1-1.1" />',
  overcast: '<path d="M4.5 12.5h7a2.8 2.8 0 0 0 .3-5.6A4 4 0 0 0 4.2 7.6a2.5 2.5 0 0 0 .3 4.9z" />',
  rain: '<path d="M4.5 9.5h7a2.6 2.6 0 0 0 .3-5.2A3.8 3.8 0 0 0 4.2 5a2.3 2.3 0 0 0 .3 4.5z" /><path d="M5.5 11.5l-.8 2M8.5 11.5l-.8 2M11.5 11.5l-.8 2" />',
  snow: '<path d="M8 1.5v13M2.4 4.8l11.2 6.4M2.4 11.2l11.2-6.4" /><path d="M6.6 2.6 8 3.6l1.4-1M6.6 13.4 8 12.4l1.4 1" />',
};
let liveEnv = null;
let hudKey = '';

// NOAA 简化算法：当天日出 / 日落（含大气折射 0.833°），返回本地分钟数
function sunTimes(ymd, lat, lon, tz) {
  const [y, m, d] = ymd.split('-').map(Number);
  const n = Math.round((Date.UTC(y, m - 1, d) - Date.UTC(y, 0, 1)) / 864e5) + 1;
  const g = 2 * Math.PI / 365 * (n - 1);
  const eq = 229.18 * (0.000075 + 0.001868 * Math.cos(g) - 0.032077 * Math.sin(g) - 0.014615 * Math.cos(2 * g) - 0.040849 * Math.sin(2 * g));
  const dec = 0.006918 - 0.399912 * Math.cos(g) + 0.070257 * Math.sin(g) - 0.006758 * Math.cos(2 * g) + 0.000907 * Math.sin(2 * g) - 0.002697 * Math.cos(3 * g) + 0.00148 * Math.sin(3 * g);
  const phi = deg(lat);
  const ha = Math.acos(Math.cos(deg(90.833)) / (Math.cos(phi) * Math.cos(dec)) - Math.tan(phi) * Math.tan(dec)) * 180 / Math.PI;
  return { rise: 720 - 4 * (lon + ha) - eq + tz * 60, set: 720 - 4 * (lon - ha) - eq + tz * 60 };
}
const hhmm = (min) => { const t = Math.round(min); return `${String(Math.floor(t / 60)).padStart(2, '0')}:${String(t % 60).padStart(2, '0')}`; };

function updateEnvHud(force) {
  const now = demo.on ? demo.date : new Date();
  const time = fmtTime.format(now);
  const ymd = fmtYMD.format(now);
  const w = liveEnv?.weather || env.weather;
  const temp = liveEnv?.temp ?? MANUAL_TEMP[env.season][env.weather];
  const key = [time, ymd, w, temp, env.source, demo.on].join('|');
  if (!force && key === hudKey) return;
  hudKey = key;
  ui.envTime.textContent = time;
  ui.envTime.dateTime = now.toISOString();
  ui.envDate.textContent = fmtDate.format(now).replace(/\s+/g, ' ');
  ui.envPlace.textContent = LOCATION.name;
  ui.envIcon.innerHTML = WEATHER_ICON[w];
  ui.envWeather.textContent = `${liveEnv?.text || WEATHER_TEXT[w]} · ${temp}°C`;
  ui.envMode.textContent = demo.on ? '演示' : env.source === 'live' ? '实况' : '手动';
  ui.envMode.classList.toggle('is-live', !demo.on && env.source === 'live');
  ui.envMode.classList.toggle('is-demo', demo.on);
  const st = sunTimes(ymd, LOCATION.lat, LOCATION.lon, LOCATION.tz);
  const rise = liveEnv?.rise || hhmmLive(st.rise);
  const set = liveEnv?.set || hhmmLive(st.set);
  ui.envSun.textContent = `日出 ${rise} · 日落 ${set}`;
}
setInterval(() => updateEnvHud(false), 1000);
// 跟随模式：太阳每 30 秒重算一次（阴影方向跟着走），天气每 10 分钟拉一次
setInterval(() => { if (env.source === 'live') applySolar(false); }, 30000);
setInterval(() => { if (env.source === 'live') fetchLive(false); }, 60000);
initPanel();
setInterval(() => {
  if (!cargoSys) return;
  if (performance.now() - cargoPollAt < 18000) return;
  cargoPollAt = performance.now();
  fetch('/api/cron', { cache: 'no-store' }).then((r) => r.json()).then((d) => cargoSys.onJobs(d.jobs || [])).catch(() => {});
}, 20000);
// 进度环读真实状态：/api/live 每 15 秒拉一次（busy = 该群最近 180 秒有会话活动）
function pollLive() {
  fetch('../api/live', { cache: 'no-store' })
    .then((r) => r.json())
    .then((d) => {
      const busy = Object.entries(d.plots || {}).filter(([, v]) => v && v.busy).map(([k]) => k);
      if (cargoSys) cargoSys.setLive(busy);
      window.__liveState = d;
    })
    .catch(() => {});
}
pollLive();
setInterval(pollLive, 10000);
initLeftBar();

// ── B-9 演示模式：一天压成 60 秒（06:00 → 22:00），太阳角度 / 色温 / 影子 / 灯全跟着走；期间锁交互，退出还原 ──
// 虚拟时间严格线性：06:00 → 22:00 用 60 秒走完，即每秒 16 分钟；按墙钟计时（不靠 rAF 帧时间，后台降帧也不跑偏）
const DEMO = {
  ms: 60000, hold: 1000, spin: 0.35, focusAlt: 6, focusPlot: 'control',
  from: 360, to: 1320,
};
const demoMinutes = (s) => DEMO.from + (DEMO.to - DEMO.from) * Math.min(1, Math.max(0, s * 1000 / DEMO.ms));
function demoDate(min) {
  const [y, mo, d] = fmtYMD.format(new Date()).split('-').map(Number);
  return new Date(Date.UTC(y, mo - 1, d) + (min - LOCATION.tz * 60) * 60000);
}
function enterDemo() {
  if (demo.on) return;
  prewarmNight();   // 当前画质档没预热过就补上（已预热则是空操作）
  demo.saved = {
    source: env.source, season: env.season, night: env.night, weather: env.weather, quality: qualityUser,
    focused: focused?.def.id || null, autoRotate: controls.autoRotate, speed: controls.autoRotateSpeed,
    camT: controls.target.clone(), camP: camera.position.clone(),
  };
  if (env.source === 'live') setLiveMode(false);
  demo.on = true;
  demo.dusk = false;
  demo.date = demoDate(DEMO.from);
  document.body.classList.add('is-demo');
  controls.enabled = false;
  setHover(null);
  focusOrbit = null;
  if (focused) setFocus(null, { fly: false });
  setEnv({ weather: 'sunny' });
  applySolar(true);
  goHome();
  controls.autoRotateSpeed = DEMO.spin;
  controls.autoRotate = true;
  ui.btnDemo.setAttribute('aria-pressed', 'true');
  ui.btnDemo.querySelector('span').textContent = '退出演示';
  demo.t0 = performance.now();   // 点下即起表：0 秒 = 06:00
  updateEnvHud(true);
  clearInterval(demo.timer);
  demo.timer = setInterval(stepDemo, 100);   // HUD / 退出不依赖渲染帧
  log('演示开始');
}
function exitDemo() {
  if (!demo.on) return;
  const s = demo.saved;
  demo.on = false;
  clearInterval(demo.timer);
  document.body.classList.remove('is-demo');
  controls.enabled = true;
  controls.autoRotate = s.autoRotate;
  controls.autoRotateSpeed = s.speed;
  ui.btnRotate.setAttribute('aria-pressed', String(s.autoRotate));
  ui.btnDemo.setAttribute('aria-pressed', 'false');
  ui.btnDemo.querySelector('span').textContent = '演示';
  focusOrbit = null;
  setFocus(s.focused ? plots.get(s.focused) : null, { fly: false });
  flyTo(s.camT, s.camP, 1200);
  sunDir.copy(KEY_DIR);
  setQuality(s.quality);
  look.to = null;           // 太阳颜色 / 强度被演示改过：强制从当前观感渐变回目标
  setEnv({ season: s.season, night: s.night, weather: s.weather });
  if (s.source === 'live') setLiveMode(true);
  else updateShadowCasters(true);
  updateEnvHud(true);
  log('演示结束，已还原');
}
function stepDemo() {
  if (!demo.on) return;
  const now = performance.now();
  const el = (now - demo.t0) / 1000;
  if (el * 1000 >= DEMO.ms + DEMO.hold) { exitDemo(); return; }   // 22:00 停 1 秒再退出，终点看得见
  demo.date = demoDate(demoMinutes(el));
  if (now - demo.lastSun > 40) { demo.lastSun = now; applySolar(false); }
  // 太阳快落山时推到中央大厅：夜里只有聚焦块亮灯（不破坏「夜间只亮聚焦地块」）
  if (!demo.dusk && LIVE.alt != null && LIVE.alt < DEMO.focusAlt && el > 30) {
    demo.dusk = true;
    const p = plots.get(DEMO.focusPlot);
    if (p) setFocus(p);
  }
  updateEnvHud(false);
}

// ── 尺寸 ──
function resize() {
  const w = ui.stage.clientWidth, h = ui.stage.clientHeight;
  if (!w || !h) return;
  renderer.setSize(w, h, false);
  const px = renderer.getDrawingBufferSize(new THREE.Vector2());
  post.setSize(px.x, px.y);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
}
new ResizeObserver(resize).observe(ui.stage);

// ── 主循环 ──
let perfCount = 0;
function renderFrame() {
  perfCount++;
  window.__perf = { renders: perfCount, at: performance.now() };
  renderer.info.reset();
  if (usePost()) post.render(scene, camera, performance.now() / 1000);
  else { renderer.setRenderTarget(null); renderer.render(scene, camera); }
}
let lastFrame = performance.now();
const fps = { frames: 0, t0: performance.now(), value: 0, samples: [] };
const plateV = new THREE.Vector3();
renderer.shadowMap.autoUpdate = false;
renderer.shadowMap.needsUpdate = true;
const sunShadowRef = new THREE.Vector3(9, 9, 9);
let lastActive = performance.now();
function markActive() { lastActive = performance.now(); }
['pointermove', 'pointerdown', 'wheel', 'touchstart', 'keydown'].forEach((ev) =>
  ui.canvas.addEventListener(ev, markActive, { passive: true }));
window.addEventListener('resize', markActive);
document.addEventListener('visibilitychange', () => { lastActive = performance.now(); renderer.shadowMap.needsUpdate = true; });
window.__markActive = markActive;

renderer.setAnimationLoop((now) => {
  if (demo.on) stepDemo();
  if (tween) stepTween(now);
  else if (focusOrbit && focused && !demo.on) stepFocusOrbit(now);
  controls.update();
  if (pointerDirty && pointerIn && !tween && !demo.on) {
    pointerDirty = false;
    const e = pointer.userData;
    if (e && e.buttons === 0) setHover(pick(e.clientX, e.clientY));
  }
  // 聚焦块常驻名牌（强调色），钉在地块上方
  if (focused) {
    plateV.copy(focused.center).setY(focused.height + 1.2).project(camera);
    const r = ui.canvas.getBoundingClientRect();
    ui.focusPlate.style.transform = `translate(${(plateV.x * 0.5 + 0.5) * r.width}px, ${(-plateV.y * 0.5 + 0.5) * r.height}px) translate(-50%, -100%)`;
    ui.focusPlate.hidden = plateV.z > 1;
  }
  updateShadowCasters(false);
  updateDetail(false);
  const dt = Math.min(100, now - lastFrame); lastFrame = now;
  stepLook(performance.now());
  // 月光跟随夜间程度平滑过渡（约 1.2 秒渐变），天气越阴沉越弱
  if (moonLight) {
    const k = 1 - Math.exp(-dt / 1200);
    const wetK = env.weather === 'rain' ? 0.5 : env.weather === 'overcast' ? 0.75 : 1;
    moonLight.intensity += ((night ? 1.0 * wetK : 0) - moonLight.intensity) * k;   // 实测 +9% 画面亮度，晚上看得见轮廓但不刺眼
  }
  updateGlow(performance.now());
  updateDof(dt);
  sky.update(now / 1000, dt / 1000, { sunDir, skyColor: scene.background, night: env.night, weather: env.weather });
  post.final.uniforms.uCloudCover.value = sky.vis.cover;
  beltSys?.update(now / 1000);
  updateAmbient(now / 1000);
  if (cargoSys) { const dtc = Math.min(0.1, (now - (cargoSys._last || now)) / 1000); cargoSys._last = now; cargoSys.update(dtc); }
  precip?.update(now / 1000, camera, controls.target, ui.stage.clientHeight * renderer.getPixelRatio());
  // 太阳方向变了才重算阴影（原来是每帧算一次，显卡一大开销）
  if (sunShadowRef.distanceToSquared(sunDir) > 1e-6) { sunShadowRef.copy(sunDir); renderer.shadowMap.needsUpdate = true; }
  // 空闲判定：3 秒没操作、没有连续动画 → 降到 8fps；切到后台直接不画
  const animating = !!tween || demo.on || !!focusOrbit || (cargoSys && cargoSys.items && cargoSys.items.length > 0) || !!precip?.active;
  const idle = !animating && performance.now() - lastActive > 3000;
  if (document.hidden) { fps.frames = 0; fps.t0 = now; return; }
  if (idle) {
    if (!renderer.__idleAt || now - renderer.__idleAt > 120) { renderer.__idleAt = now; renderFrame(); }
  } else { renderer.__idleAt = 0; renderFrame(); }
  fps.frames++;
  if (now - fps.t0 >= 1000) {
    fps.value = Math.round(fps.frames * 1000 / (now - fps.t0));
    fps.samples.push(fps.value); if (fps.samples.length > 30) fps.samples.shift();
    fps.frames = 0; fps.t0 = now;
    const info = renderer.info.render;
    ui.hud.textContent = `${fps.value} fps · ${(info.triangles / 1e6).toFixed(2)} M 三角面 · ${info.calls} 批 · 画质 ${QUALITY[qualityCur || qualityUser].label}${fxOverride ? ` · fx ${fxOverride.join(',') || 'none'}` : ''}`;
  }
});

// ── 进度 ──
const progress = new Map();   // id → 0..1
function renderProgress(label) {
  const n = def.plots.length;
  let sum = 0; for (const v of progress.values()) sum += v;
  const done = [...plots.keys()].length;
  ui.loadBar.style.width = `${Math.round((sum / n) * 100)}%`;
  ui.loadText.textContent = done >= n ? `全部 ${n} 块已加载` : `加载中 ${done} / ${n}${label ? ' · ' + label : ''}`;
}

// ── 调试 / 验收接口 ──
window.__park = {
  THREE, renderer, scene, camera, controls, plots, timings, shadowState, fps,
  get belts() { return beltChecks; },
  get beltSys() { return beltSys; },
  get rings() { return cargoSys ? cargoSys.ringState() : {}; },
  get lights() { return lampLights.map((l) => ({ lamp: l.userData.lamp, pos: l.position.toArray().map((v) => +v.toFixed(2)) })); },
  setPlotGain(key, table) { PLOT_GAIN[key] = table; applyTint(); },
  sky, renderFrame, setNight, setEnv, setQuality, goHome, exitFocus, post, windU, CAM, setSpin, enterDemo, exitDemo, DEMO,
  get demo() { return { on: demo.on, elapsed: demo.on ? (performance.now() - demo.t0) / 1000 : 0, time: fmtTime.format(demo.date), alt: LIVE.alt, night: env.night, dusk: demo.dusk }; },
  get cam() { const v = camera.position.clone().sub(controls.target); return { azimuth: THREE.MathUtils.radToDeg(Math.atan2(v.x, v.z)), polar: THREE.MathUtils.radToDeg(Math.acos(v.y / v.length())), dist: v.length(), y: camera.position.y, tween: !!tween, orbit: focusOrbit ? THREE.MathUtils.radToDeg(focusOrbit.applied) : null, autoRotate: controls.autoRotate, speed: controls.autoRotateSpeed }; },
  // 观感效果：__park.fx.set('all' | 'none' | 'dof,grade' | null=回到画质档)；params 可现场改（改 contact / grade / cloud / bloom 后调 apply()）
  fx: {
    keys: FX_KEYS, tiers: FX_TIER, params: FX_PARAMS,
    get on() { return { ...fxOn }; },
    get override() { return fxOverride; },
    set(v) { fxOverride = Array.isArray(v) ? v.filter((k) => FX_KEYS.includes(k)) : parseFx(v); refreshFx(); applyEnv({ instant: true }); return { ...fxOn }; },
    apply() {
      const P = FX_PARAMS, pu = post.final.uniforms;
      contactMat.uniforms.uStrength.value = P.contact.strength; contactMat.uniforms.uTint.value.set(P.contact.tint);
      pu.uShadowTint.value.fromArray(P.grade.shadowTint); pu.uHighTint.value.fromArray(P.grade.highTint);
      pu.uCloudWind.value.set(P.cloud.dir[0] * P.cloud.speed, P.cloud.dir[1] * P.cloud.speed, P.cloud.tile); pu.uCloudFade.value.fromArray(P.cloud.fade);
      post.bright.uniforms.uThreshold.value = P.bloom.threshold; post.bright.uniforms.uKnee.value = P.bloom.knee;
      for (const p of plots.values()) p.glowU.uLampRise.value = P.fade.lampRise;
    },
    get dof() { return { amt: post.focusU.amt.value, dist: post.focusU.dist.value, range: post.focusU.range.value }; },
    get contactCount() { return [...plots.values()].reduce((n, p) => n + (p.contact ? p.contact.count : 0), 0); },
  },
  focusPlot: (id) => plots.get(id) && setFocus(plots.get(id)),
  setFocus: (id, opts) => setFocus(id ? plots.get(id) : null, opts),
  get state() { return { ...env, focused: focused?.def.id || null, qualityUser, qualityCur, precip: precip?.count || 0 }; },
  // P1 跟随模式接口占位：传 null 回到手动
  setLiveEnv(v) { liveEnv = v || null; env.source = v ? 'live' : 'manual'; if (v?.weather) env.weather = v.weather; applyEnv(); },
  neighborsOf: (id) => neighborsOf(plots.get(id)).map((p) => p.def.id),
  report() {
    return {
      plots: [...plots.values()].map((p) => ({
        id: p.def.id, name: p.def.name, pos: [p.def.pos[0], p.def.pos[1]], rotY: p.def.rotY, belts: p.belts,
        meshes: p.stats.meshes, tris: p.stats.tris, drawCalls: p.meshes.length, lamps: p.lamps.length, detailTris: p.meshes.filter((m) => m.userData.detail).reduce((n, m) => n + m.geometry.index.count / 3, 0),
        ports: Object.fromEntries(Object.entries(p.ports).map(([k, v]) => [k, { local: v.local.toArray().map((x) => +x.toFixed(3)), surface: v.surface != null ? +v.surface.toFixed(3) : null, y: [+v.ymin.toFixed(3), +v.ymax.toFixed(3)] }])),
      })),
      belts: beltChecks, timings, world: world?.stats, shadowCasters: shadowState.casters,
      reversedDepth: renderer.capabilities.reversedDepthBuffer, dpr: renderer.getPixelRatio(),
    };
  },
  // 碰撞自检：沿每条带子在带面以上 0.08 / 0.35 m 处做水平射线，检测是否穿过地块几何（端点 0.4 m 内不算）
  collide(opts = {}) {
    const res = [];
    const rc = new THREE.Raycaster();
    const all = [...plots.values()];
    for (const b of beltSys.belts) {
      const hits = [];
      const fr = b.frames;
      for (let i = 0; i < fr.length - 3; i += 3) {
        const a = fr[i], z = fr[i + 3];
        if (a.s < 0.4 || z.s > b.len - 0.4) continue;
        for (const lift of [0.08, 0.35]) for (const off of [-0.4, 0, 0.4]) {
          const o = a.p.clone().addScaledVector(a.up, lift).addScaledVector(a.side, off);
          const e = z.p.clone().addScaledVector(z.up, lift).addScaledVector(z.side, off);
          const d = e.clone().sub(o); const L = d.length();
          rc.set(o, d.normalize()); rc.far = L;
          const near = all.filter((p) => p.center.distanceTo(o) < Math.max(...p.def.size) * 0.75 + 2);
          for (const p of near) {
            const hs = rc.intersectObjects(p.meshes, false).filter((h) => !h.object.material.userData.glassy || opts.glass);
            if (hs.length) hits.push({ s: +a.s.toFixed(1), lift, off, plot: p.def.id, mat: hs[0].object.material.name, at: hs[0].point.toArray().map((v) => +v.toFixed(2)) });
          }
        }
      }
      res.push({ id: b.id, len: +b.len.toFixed(1), hits: hits.length, sample: hits.slice(0, 6) });
    }
    return res;
  },
};

// ── 启动 ──
(async function init() {
  const res = await fetch('./scene.json', { cache: 'no-cache' });
  if (!res.ok) throw new Error(`scene.json HTTP ${res.status}`);
  def = await res.json();
  camera.fov = def.camera.fov || 36;
  camera.updateProjectionMatrix();
  goHome(false);

  const layout = makeLayout(def);
  world = createWorld(scene, layout);
  beltSys = new BeltSystem(scene, world.groundAt);
  cargoSys = new CargoSystem(scene, beltSys, plots);
  pollLive();   // 首次立刻拉一次真实会话状态，别等 15 秒
  window.__cargoRef = cargoSys;   // 方便验收：window.__cargoRef.onJobs([...])
  precip = new Precip(scene, PRECIP);
  applyQuality();
  log('环境生成', world.stats, Math.round(performance.now() - T0) + 'ms');

  // 加载顺序：中央 → 离初始镜头近的 → 远的
  const home = homePose().p;
  const order = [...def.plots].sort((a, b) => {
    if (a.kind === 'hall') return -1;
    if (b.kind === 'hall') return 1;
    return Math.hypot(a.pos[0] - home.x, a.pos[1] - home.z) - Math.hypot(b.pos[0] - home.x, b.pos[1] - home.z);
  });
  for (const p of def.plots) progress.set(p.id, 0);
  renderProgress();

  // 下载最多领先 2 个，解析/合并逐个进行，每步之间让出一帧
  const fetches = new Map();
  const startFetch = (i) => {
    const p = order[i];
    if (!p || fetches.has(p.id)) return;
    fetches.set(p.id, fetchGlb(p, (k) => { progress.set(p.id, k * 0.7); renderProgress(p.name); }));
  };
  startFetch(0); startFetch(1); startFetch(2);
  let failed = 0;
  for (let i = 0; i < order.length; i++) {
    const p = order[i];
    try {
      await loadPlot(p, fetches.get(p.id));
    } catch (err) {
      failed++;
      console.error('[park] 加载失败', p.id, err);
    }
    progress.set(p.id, 1);
    renderProgress(order[i + 1]?.name);
    startFetch(i + 3);
    if (plots.size >= 5 && timings.firstScreen == null) {
      timings.firstScreen = Math.round(performance.now() - T0);
      log('首屏（中央 + 4 块）', timings.firstScreen + 'ms');
    }
    await nextFrame();
  }
  timings.allLoaded = Math.round(performance.now() - T0);
  log('全部加载完成', timings.allLoaded + 'ms', failed ? `失败 ${failed}` : '');
  renderProgress();
  ui.load.classList.add('is-done');
  setTimeout(() => { ui.load.hidden = true; }, 1600);
  window.__park.ready = true;
  pollLive();
  setTimeout(prewarmNight, 1200);
})().catch((err) => {
  console.error('[park] 启动失败', err);
  ui.loadText.textContent = `启动失败：${err.message}`;
});
