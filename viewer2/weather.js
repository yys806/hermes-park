// 降水粒子：雨丝（线段）+ 飘雪（点精灵）。位置全在 GPU 里按时间算，CPU 每帧只改几个 uniform。
// 粒子只铺在镜头注视点周围一圈（中景），按到注视点的水平距离淡出；离镜头太近的也淡掉，免得糊在镜头上。
import * as THREE from 'three';

const COMMON_VS = /* glsl */`
  uniform float uTime, uSpeed, uH, uGround, uW, uNear, uFadeIn, uFadeOut;
  uniform vec3 uCenter;
  attribute vec3 seed;
  varying float vFade;
  // 世界坐标里按 uW 平铺：粒子不跟着镜头平移跑，只是在注视点周围循环出现
  vec3 placeDrop(float speedJitter) {
    vec3 p;
    p.x = uCenter.x + mod(seed.x * uW - uCenter.x + uW * 0.5, uW) - uW * 0.5;
    p.z = uCenter.z + mod(seed.z * uW - uCenter.z + uW * 0.5, uW) - uW * 0.5;
    p.y = uGround + mod(seed.y * uH - uTime * uSpeed * speedJitter, uH);
    return p;
  }
  float fadeOf(vec3 p, float camDist) {
    float r = distance(p.xz, uCenter.xz);
    return smoothstep(uNear, uNear * 2.0, camDist) * (1.0 - smoothstep(uFadeIn, uFadeOut, r))
      * smoothstep(0.0, 1.5, p.y - uGround) * (1.0 - smoothstep(uH - 3.0, uH, p.y - uGround));
  }
`;

const RAIN_VS = COMMON_VS + /* glsl */`
  uniform float uLen;
  uniform vec3 uWind;
  attribute float tip;
  void main() {
    vec3 p = placeDrop(0.85 + 0.3 * fract(seed.x * 7.13));
    vec3 vel = normalize(vec3(uWind.x, -1.0, uWind.z));
    p -= vel * uLen * tip;
    vec4 mv = modelViewMatrix * vec4(p, 1.0);
    vFade = fadeOf(p, -mv.z) * (1.0 - 0.6 * tip);
    gl_Position = projectionMatrix * mv;
  }
`;

const SNOW_VS = COMMON_VS + /* glsl */`
  uniform float uSize, uScale;
  void main() {
    vec3 p = placeDrop(0.7 + 0.6 * fract(seed.z * 5.31));
    float ph = seed.x * 6.2832;
    p.x += sin(uTime * 0.7 + ph) * 0.55;
    p.z += cos(uTime * 0.55 + seed.z * 6.2832) * 0.55;
    vec4 mv = modelViewMatrix * vec4(p, 1.0);
    vFade = fadeOf(p, -mv.z);
    gl_PointSize = max(1.0, uSize * (0.6 + 0.8 * fract(seed.y * 3.7)) * uScale / -mv.z);
    gl_Position = projectionMatrix * mv;
  }
`;

const RAIN_FS = /* glsl */`
  uniform vec3 uColor;
  uniform float uAlpha;
  varying float vFade;
  void main() {
    gl_FragColor = vec4(uColor, uAlpha * vFade);
    #include <tonemapping_fragment>
    #include <colorspace_fragment>
  }
`;

const SNOW_FS = /* glsl */`
  uniform vec3 uColor;
  uniform float uAlpha;
  varying float vFade;
  void main() {
    float r = length(gl_PointCoord - 0.5);
    float a = smoothstep(0.5, 0.15, r) * uAlpha * vFade;
    if (a < 0.01) discard;
    gl_FragColor = vec4(uColor, a);
    #include <tonemapping_fragment>
    #include <colorspace_fragment>
  }
`;

function baseUniforms(cfg) {
  return {
    uTime: { value: 0 }, uSpeed: { value: cfg.speed }, uH: { value: cfg.height }, uGround: { value: 0 },
    uW: { value: 60 }, uNear: { value: 4 }, uFadeIn: { value: 20 }, uFadeOut: { value: 30 },
    uCenter: { value: new THREE.Vector3() }, uColor: { value: new THREE.Color(cfg.color) }, uAlpha: { value: cfg.alpha },
  };
}

export class Precip {
  // cfg = { rain: {...}, snow: {...}, area: {...} }，见 park.js 顶部 PRECIP
  constructor(scene, cfg) {
    this.cfg = cfg;
    this.kind = null;
    this.enabled = true;
    this.dim = 1;

    // 雨：每滴 2 个顶点（tip 0 = 下端，1 = 上端）
    const n = cfg.rain.count;
    const seedR = new Float32Array(n * 6), tip = new Float32Array(n * 2);
    for (let i = 0; i < n; i++) {
      const s = [Math.random(), Math.random(), Math.random()];
      seedR.set(s, i * 6); seedR.set(s, i * 6 + 3);
      tip[i * 2 + 1] = 1;
    }
    const gr = new THREE.BufferGeometry();
    gr.setAttribute('position', new THREE.BufferAttribute(new Float32Array(n * 6), 3));
    gr.setAttribute('seed', new THREE.BufferAttribute(seedR, 3));
    gr.setAttribute('tip', new THREE.BufferAttribute(tip, 1));
    const ru = { ...baseUniforms(cfg.rain), uLen: { value: cfg.rain.len }, uWind: { value: new THREE.Vector3(...cfg.rain.wind) } };
    this.rain = new THREE.LineSegments(gr, new THREE.ShaderMaterial({
      uniforms: ru, vertexShader: RAIN_VS, fragmentShader: RAIN_FS, transparent: true, depthWrite: false,
    }));

    // 雪：点精灵
    const m = cfg.snow.count;
    const seedS = new Float32Array(m * 3);
    for (let i = 0; i < m * 3; i++) seedS[i] = Math.random();
    const gs = new THREE.BufferGeometry();
    gs.setAttribute('position', new THREE.BufferAttribute(new Float32Array(m * 3), 3));
    gs.setAttribute('seed', new THREE.BufferAttribute(seedS, 3));
    const su = { ...baseUniforms(cfg.snow), uSize: { value: cfg.snow.size }, uScale: { value: 500 } };
    this.snow = new THREE.Points(gs, new THREE.ShaderMaterial({
      uniforms: su, vertexShader: SNOW_VS, fragmentShader: SNOW_FS, transparent: true, depthWrite: false,
    }));

    for (const o of [this.rain, this.snow]) {
      o.frustumCulled = false;
      o.visible = false;
      o.renderOrder = 5;
      o.name = `precip:${o === this.rain ? 'rain' : 'snow'}`;
      scene.add(o);
    }
  }

  // kind: 'rain' | 'snow' | null；enabled 由画质决定；dim 用于夜间压暗
  set(kind, enabled, dim = 1) {
    this.kind = kind; this.enabled = enabled; this.dim = dim;
    this.rain.visible = enabled && kind === 'rain';
    this.snow.visible = enabled && kind === 'snow';
    this.rain.material.uniforms.uAlpha.value = this.cfg.rain.alpha * dim;
    this.snow.material.uniforms.uAlpha.value = this.cfg.snow.alpha * dim;
  }

  get active() { return this.rain.visible || this.snow.visible; }

  update(t, camera, target, viewportH) {
    if (!this.active) return;
    const a = this.cfg.area;
    const camDist = camera.position.distanceTo(target);
    const W = THREE.MathUtils.clamp(camDist * a.widthPerDist, a.minW, a.maxW);
    for (const o of [this.rain, this.snow]) {
      if (!o.visible) continue;
      const u = o.material.uniforms;
      u.uTime.value = t;
      u.uCenter.value.copy(target);
      u.uGround.value = a.ground;
      u.uW.value = W;
      u.uFadeIn.value = W * a.fadeIn;
      u.uFadeOut.value = W * a.fadeOut;
      u.uNear.value = a.near;
      if (u.uScale) u.uScale.value = viewportH * 0.5 / Math.tan(THREE.MathUtils.degToRad(camera.fov) / 2);
    }
  }

  get count() { return (this.rain.visible ? this.cfg.rain.count : 0) + (this.snow.visible ? this.cfg.snow.count : 0); }
}
