// P5 天空：渐变天穹 + 日轮光晕 + 程序化软边云（多层旋转噪声，无格点直线），跟着镜头走，不进雾。
// 太阳方向 = 场景平行光方向（手动模式固定、跟随模式真实轨迹、演示模式 06:00→22:00）；颜色随太阳高度角变（低太阳偏暖）。
// 地面云影（fx.js FX_CLOUD）用同一个 cloudField 函数和同一个云量，风向一致。
import * as THREE from 'three';

// 云场：p 为「云层平面」上的坐标（米 / 尺度），返回 0..1 覆盖度。CLOUD_OCT 控制层数（低画质 3 层）
export const CLOUD_GLSL = /* glsl */`
  float skyHash(vec2 p) { p = fract(p * vec2(123.34, 456.21)); p += dot(p, p + 45.32); return fract(p.x * p.y); }
  float skyNoise(vec2 p) {
    vec2 i = floor(p), f = fract(p);
    vec2 u = f * f * f * (f * (f * 6.0 - 15.0) + 10.0);
    return mix(mix(skyHash(i), skyHash(i + vec2(1.0, 0.0)), u.x), mix(skyHash(i + vec2(0.0, 1.0)), skyHash(i + vec2(1.0, 1.0)), u.x), u.y);
  }
  // 每层旋转约 37°、频率 ×2.03：格点方向互相错开，叠出来没有横平竖直的边
  float skyFbm(vec2 p, int oct) {
    const mat2 R = mat2(0.80, 0.60, -0.60, 0.80);
    float v = 0.0, a = 0.5, s = 0.0;
    for (int i = 0; i < 6; i++) {
      if (i >= oct) break;
      v += a * skyNoise(p); s += a;
      p = R * p * 2.03 + vec2(17.1, 9.2);
      a *= 0.5;
    }
    return v / s;
  }
  // cover：0 = 晴空，1 = 满天云；soft：边缘渐变宽度
  float cloudField(vec2 p, float cover, float soft, int oct) {
    vec2 q = vec2(skyFbm(p * 0.55 + vec2(3.1, 7.7), 3), skyFbm(p * 0.55 + vec2(8.3, 2.8), 3));
    float n = skyFbm(p + (q - 0.5) * 1.6, oct);
    float th = mix(0.72, 0.30, cover);
    return smoothstep(th - soft, th + soft, n);
  }
`;

const VS = /* glsl */`
  varying vec3 vDir;
  void main() {
    vDir = normalize(position);
    vec4 mv = modelViewMatrix * vec4(position, 1.0);
    gl_Position = projectionMatrix * mv;
    gl_Position.z = 0.0;   // 反向深度：0 = 最远，天穹永远在最后面
  }
`;
const FS = /* glsl */`
  uniform vec3 uSunDir, uHorizon, uZenith, uGround, uSunCol, uCloudLit, uCloudShade;
  uniform float uSunVis, uCover, uTime, uCloudScale, uNight;
  uniform vec2 uWind;
  varying vec3 vDir;
  ${CLOUD_GLSL}
  void main() {
    vec3 d = normalize(vDir);
    float h = d.y;
    // 天色：地平线 → 天顶；地平线以下用雾色（远处岛外看到的是雾）
    // P5b：地平线以上很快转蓝（低仰角那一条也看得出是天，不和雾色混成一片）
    vec3 col = mix(uHorizon, uZenith, pow(smoothstep(0.0, 0.5, h), 0.55));
    col = mix(uGround, col, smoothstep(-0.06, 0.02, h));
    float cs = max(dot(d, uSunDir), 0.0);
    // 太阳附近的天空泛暖（低太阳更明显）
    float lowSun = 1.0 - smoothstep(0.0, 0.45, uSunDir.y);
    col += uSunCol * (pow(cs, 8.0) * (0.05 + 0.3 * lowSun) + pow(cs, 220.0) * 0.22) * uSunVis;
    // 日轮 + 光晕：日轮约 1.4° 宽、HDR 值远高于周围；光晕收窄，免得太阳那一侧整片发白看不出日轮
    float disc = smoothstep(0.99962, 0.99972, cs);
    col += uSunCol * (disc * 9.0 + pow(cs, 2600.0) * 1.1 + pow(cs, 320.0) * 0.45 + pow(cs, 48.0) * 0.12) * uSunVis;
    // 云：把视线投到一层「云平面」上（越靠地平线投得越远、越扁），远处淡进地平线
    if (h > -0.02) {
      vec2 p = d.xz / (max(h, 0.0) + 0.09) * uCloudScale + uWind * uTime;
      float c = cloudField(p, uCover, 0.16, CLOUD_OCT);
      float thick = cloudField(p + vec2(0.07, 0.05), uCover, 0.28, CLOUD_OCT);   // 偏移采样当厚度：迎光面亮、背光面暗
      vec3 cc = mix(uCloudShade, uCloudLit, clamp(0.55 + (c - thick) * 2.5 + pow(cs, 8.0) * 0.25 * uSunVis, 0.0, 1.0));
      // 太阳从云后透出来的银边
      cc += uSunCol * pow(cs, 40.0) * (1.0 - thick) * 0.5 * uSunVis;
      // P5b：云一直铺到地平线附近才淡（原来 10° 以下全淡掉，平视镜头里一朵都看不到）；远处云向地平线色偏一点（空气透视）
      float fade = smoothstep(0.0, 0.035, h);
      cc = mix(uHorizon, cc, 0.55 + 0.45 * smoothstep(0.02, 0.2, h));
      col = mix(col, cc, c * fade * (0.95 - 0.25 * uNight));
    }
    gl_FragColor = vec4(col, 1.0);
    #include <tonemapping_fragment>
    #include <colorspace_fragment>
  }
`;

const DAY_ZENITH = new THREE.Color('#5E95C9');
const NIGHT_ZENITH = new THREE.Color('#070B16');
const SUN_NOON = new THREE.Color('#FFF4DE'), SUN_LOW = new THREE.Color('#FF9A4D');
// 各天气的云量、日轮可见度
const WEATHER_SKY = {
  sunny: { cover: 0.42, sun: 1.0 },
  overcast: { cover: 0.86, sun: 0.22 },
  rain: { cover: 0.97, sun: 0.06 },
  snow: { cover: 0.9, sun: 0.18 },
};

export class Sky {
  constructor(scene, { radius = 700, windX = 1.6, windZ = 1.2 } = {}) {
    this.uniforms = {
      uSunDir: { value: new THREE.Vector3(0, 1, 0) },
      uHorizon: { value: new THREE.Color() }, uZenith: { value: new THREE.Color() }, uGround: { value: new THREE.Color() },
      uSunCol: { value: new THREE.Color() }, uCloudLit: { value: new THREE.Color() }, uCloudShade: { value: new THREE.Color() },
      uSunVis: { value: 1 }, uCover: { value: 0.4 }, uTime: { value: 0 }, uCloudScale: { value: 1.1 }, uNight: { value: 0 },
      // 天上云的漂移（云平面坐标 / 秒），与地面云影同向
      uWind: { value: new THREE.Vector2(windX, windZ).multiplyScalar(0.0045) },
    };
    this.material = new THREE.ShaderMaterial({
      vertexShader: VS, fragmentShader: FS, uniforms: this.uniforms, defines: { CLOUD_OCT: 5 },
      side: THREE.BackSide, depthWrite: false, depthTest: false, fog: false,
    });
    this.mesh = new THREE.Mesh(new THREE.SphereGeometry(radius, 48, 24), this.material);
    this.mesh.name = 'sky';
    this.mesh.frustumCulled = false;
    this.mesh.renderOrder = -10;
    this.mesh.onBeforeRender = (r, s, cam) => { this.mesh.position.copy(cam.position); this.mesh.updateMatrixWorld(); };
    scene.add(this.mesh);
    // 看得见的日轮：径向渐变贴图 + 加法混合，位置钉在太阳方向上
    const cv = document.createElement('canvas');
    cv.width = cv.height = 256;
    const cx = cv.getContext('2d');
    const g = cx.createRadialGradient(128, 128, 0, 128, 128, 128);
    g.addColorStop(0.0, 'rgba(255,255,255,1)');
    g.addColorStop(0.18, 'rgba(255,250,235,0.98)');
    g.addColorStop(0.34, 'rgba(255,235,190,0.55)');
    g.addColorStop(0.62, 'rgba(255,220,170,0.16)');
    g.addColorStop(1.0, 'rgba(255,210,160,0)');
    cx.fillStyle = g;
    cx.fillRect(0, 0, 256, 256);
    const tex = new THREE.CanvasTexture(cv);
    tex.colorSpace = THREE.SRGBColorSpace;
    this.sunSprite = new THREE.Sprite(new THREE.SpriteMaterial({
      map: tex, blending: THREE.AdditiveBlending, transparent: true, depthWrite: false, depthTest: false, fog: false,
    }));
    this.sunSprite.name = 'sunDisc';
    this.sunSprite.scale.setScalar(150);
    this.sunSprite.renderOrder = -9;
    scene.add(this.sunSprite);

    this.vis = { sun: 1, cover: 0.4, night: 0 };
    this._tmp = new THREE.Color();
  }

  setTier(tier) {
    const oct = tier === 'low' ? 3 : 5;
    if (this.material.defines.CLOUD_OCT !== oct) { this.material.defines.CLOUD_OCT = oct; this.material.needsUpdate = true; }
  }

  // 每帧：sunDir 指向太阳；skyColor = 当前天色（雾色）；night / weather 为环境目标，内部平滑过渡
  update(t, dt, { sunDir, skyColor, night, weather }) {
    const u = this.uniforms;
    u.uTime.value = t;
    u.uSunDir.value.copy(sunDir).normalize();
    if (this.sunSprite) {
      const R = 620;
      this.sunSprite.position.copy(sunDir).multiplyScalar(R);
      this.sunSprite.visible = sunDir.y > -0.06 && !night;
      const warm = 1 - THREE.MathUtils.clamp(sunDir.y / 0.45, 0, 1);
      this.sunSprite.material.color.setRGB(1.0, 0.98 - warm * 0.22, 0.9 - warm * 0.42);
      this.sunSprite.material.opacity = 0.55 + warm * 0.45;
      this.sunSprite.scale.setScalar(150 + warm * 60);
    }
    const W = WEATHER_SKY[weather] || WEATHER_SKY.sunny;
    const k = 1 - Math.exp(-dt / 1.2);   // 约 1.2 秒的指数平滑，跟着观感渐变走
    const sunUp = THREE.MathUtils.smoothstep(sunDir.y, -0.02, 0.06);
    this.vis.sun += ((night ? 0 : W.sun * sunUp) - this.vis.sun) * k;
    this.vis.cover += (W.cover - this.vis.cover) * k;
    this.vis.night += ((night ? 1 : 0) - this.vis.night) * k;
    u.uSunVis.value = this.vis.sun;
    u.uCover.value = this.vis.cover;
    u.uNight.value = this.vis.night;
    const alt = THREE.MathUtils.clamp(sunDir.y / 0.5, 0, 1);
    u.uSunCol.value.copy(SUN_LOW).lerp(SUN_NOON, alt);
    // 地平线 = 当前天色（与雾一致，接缝看不出来）；天顶更深更蓝，阴雨天向灰收
    u.uHorizon.value.copy(skyColor);
    u.uGround.value.copy(skyColor);
    const grey = this.vis.cover > 0.8 ? (this.vis.cover - 0.8) / 0.2 : 0;
    this._tmp.copy(DAY_ZENITH).lerp(skyColor, 0.25 + 0.6 * grey);
    u.uZenith.value.copy(this._tmp).lerp(NIGHT_ZENITH, this.vis.night);
    // 云色：迎光面 = 白 → 低太阳时染橙；背光面 = 天色压暗；夜里整体压到很暗
    const low = 1 - alt;
    u.uCloudLit.value.setRGB(1.0, 1.0, 1.0).lerp(this._tmp.set('#FFC79A'), low * 0.75 * this.vis.sun).lerp(skyColor, grey * 0.5)
      .multiplyScalar(1 - 0.82 * this.vis.night);
    u.uCloudShade.value.copy(skyColor).multiplyScalar(0.62 - 0.15 * grey).lerp(this._tmp.set('#6A7488'), 0.35)
      .multiplyScalar(1 - 0.75 * this.vis.night);
  }
}
