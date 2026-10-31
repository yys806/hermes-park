// P0.5 观感：自建后期管线（不用 EffectComposer，所有屏幕效果并进一个合成 pass，省带宽）+ 接触阴影贴片。
//   场景 → HDR 渲染目标（4×MSAA + 深度纹理）
//   景深 A-1：半分辨率「下采样 + 算弥散圈」→ 半分辨率圆盘模糊（按采样点弥散圈加权，清晰物体不往背景渗色）
//   Bloom A-3：1/4 分辨率亮部提取 → 两级高斯模糊
//   合成：景深混合 → 云影 A-5（深度重建世界坐标，程序化云场）→ Bloom → 色调映射 → sRGB → P0 基础分级 → 暖调 LUT → 暗角
// 参数都在 park.js 顶部 FX_PARAMS，这里只认 uniform。
import * as THREE from 'three';
import { FullScreenQuad } from 'three/addons/postprocessing/Pass.js';
import { CLOUD_GLSL } from './sky.js?v=20261031-p5';

const VS = /* glsl */`
  varying vec2 vUv;
  void main() { vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }
`;

// 反向深度（clip control 0..1）：近 = 1，远 = 0。视深 D = n·f / (d·(f − n) + n)
const DEPTH_FN = /* glsl */`
  uniform sampler2D tDepth;
  uniform float uNear, uFar;
  float viewDepth(vec2 uv) {
    float d = texture2D(tDepth, uv).x;
    return uNear * uFar / (d * (uFar - uNear) + uNear);
  }
  // 弥散圈 0..1：离焦点前后超过 uFocusRange 开始虚，画面边缘（以焦点屏幕位置为中心的竖向椭圆）也虚
  uniform float uFocusDist, uFocusRange, uFocusFade, uEdge0, uEdge1, uEdgeK, uAspect, uDofAmt;
  uniform vec2 uFocusUv;
  float cocAt(vec2 uv, float D) {
    float dz = abs(D - uFocusDist) / uFocusDist;
    float c = smoothstep(uFocusRange, uFocusRange + uFocusFade, dz);
    vec2 e = (uv - uFocusUv) * vec2(uAspect * 0.6, 1.0);
    c = max(c, uEdgeK * smoothstep(uEdge0, uEdge1, length(e)));
    // 天穹不写深度（= 远平面）：只给一点虚化，否则日轮 / 云边整片糊掉
    if (D > uFar * 0.999) c *= 0.3;
    return c * uDofAmt;
  }
`;

const DOWN_FS = /* glsl */`
  uniform sampler2D tColor;
  uniform vec2 uTexel;
  varying vec2 vUv;
  ${DEPTH_FN}
  void main() {
    // 4 点双线性 = 16 像素盒式下采样，压掉高光闪烁
    vec3 c = texture2D(tColor, vUv + uTexel * vec2(-0.5, -0.5)).rgb + texture2D(tColor, vUv + uTexel * vec2(0.5, -0.5)).rgb
           + texture2D(tColor, vUv + uTexel * vec2(-0.5, 0.5)).rgb + texture2D(tColor, vUv + uTexel * vec2(0.5, 0.5)).rgb;
    gl_FragColor = vec4(c * 0.25, cocAt(vUv, viewDepth(vUv)));
  }
`;

// 16 点泊松圆盘
const DISC = [
  [-0.613, 0.617], [0.170, -0.040], [-0.299, 0.791], [0.645, 0.493], [-0.651, 0.717], [0.421, 0.027], [-0.817, -0.271], [-0.705, -0.668],
  [0.977, -0.108], [0.063, -0.546], [0.159, 0.698], [-0.014, 0.140], [0.811, 0.523], [0.454, -0.810], [-0.268, -0.418], [-0.344, 0.095],
];
const BLUR_FS = /* glsl */`
  uniform sampler2D tHalf;
  uniform vec2 uTexel;
  uniform float uMaxR;
  varying vec2 vUv;
  void main() {
    vec4 c0 = texture2D(tHalf, vUv);
    float r = uMaxR * c0.a;
    vec3 sum = c0.rgb; float wsum = 1.0;
    ${DISC.map(([x, y]) => `{ vec4 s = texture2D(tHalf, vUv + vec2(${x.toFixed(3)}, ${y.toFixed(3)}) * r * uTexel); float w = s.a; sum += s.rgb * w; wsum += w; }`).join('\n    ')}
    gl_FragColor = vec4(sum / wsum, c0.a);
  }
`;

const BRIGHT_FS = /* glsl */`
  uniform sampler2D tColor;
  uniform vec2 uTexel;
  uniform float uThreshold, uKnee;
  varying vec2 vUv;
  void main() {
    vec3 c = vec3(0.0);
    for (int i = 0; i < 4; i++) {
      vec2 o = vec2(i == 1 || i == 3 ? 1.0 : -1.0, i >= 2 ? 1.0 : -1.0) * uTexel;
      c += texture2D(tColor, vUv + o).rgb;
    }
    c *= 0.25;
    float l = max(c.r, max(c.g, c.b));
    float soft = clamp(l - uThreshold + uKnee, 0.0, 2.0 * uKnee);
    soft = soft * soft / (4.0 * uKnee + 1e-4);
    float k = max(soft, l - uThreshold) / max(l, 1e-4);
    gl_FragColor = vec4(c * k, 1.0);
  }
`;
const GAUSS_FS = /* glsl */`
  uniform sampler2D tSrc;
  uniform vec2 uDir;
  varying vec2 vUv;
  void main() {
    // 9 点高斯折成 5 次双线性采样
    vec3 c = texture2D(tSrc, vUv).rgb * 0.2270270;
    c += (texture2D(tSrc, vUv + uDir * 1.3846154).rgb + texture2D(tSrc, vUv - uDir * 1.3846154).rgb) * 0.3162162;
    c += (texture2D(tSrc, vUv + uDir * 3.2307692).rgb + texture2D(tSrc, vUv - uDir * 3.2307692).rgb) * 0.0702703;
    gl_FragColor = vec4(c, 1.0);
  }
`;

const FINAL_FS = /* glsl */`
  uniform sampler2D tColor, tBlur, tBloomA, tBloomB;
  uniform float uCloudCover;
  uniform float uExposure, uContrast, uSaturation, uWarm;
  uniform float uLut, uVignette, uVigMul, uBloom, uCloud, uTime;
  uniform vec3 uCloudWind;   // xy = 风向 × 速度（米/秒），z = 噪声平铺尺寸（米）
  uniform vec2 uCloudFade;   // 视深超过 x 开始淡出，到 y 完全没有云影
  uniform mat4 uInvProj, uCamWorld;
  uniform vec3 uShadowTint, uHighTint;
  varying vec2 vUv;
  ${DEPTH_FN}
  #ifdef FX_CLOUD
  ${CLOUD_GLSL}
  #endif

  vec3 NeutralToneMapping(vec3 color) {
    const float StartCompression = 0.8 - 0.04;
    const float Desaturation = 0.15;
    color *= uExposure;
    float x = min(color.r, min(color.g, color.b));
    float offset = x < 0.08 ? x - 6.25 * x * x : 0.04;
    color -= offset;
    float peak = max(color.r, max(color.g, color.b));
    if (peak < StartCompression) return color;
    float d = 1. - StartCompression;
    float newPeak = 1. - d * d / (peak + d - StartCompression);
    color *= newPeak / peak;
    float g = 1. - 1. / (Desaturation * (peak - newPeak) + 1.);
    return mix(color, vec3(newPeak), g);
  }
  vec3 toSRGB(vec3 v) { return mix(pow(v, vec3(0.41666)) * 1.055 - vec3(0.055), v * 12.92, vec3(lessThanEqual(v, vec3(0.0031308)))); }

  void main() {
    vec3 c = texture2D(tColor, vUv).rgb;
    #if defined(FX_DOF) || defined(FX_CLOUD)
      float D = viewDepth(vUv);
    #endif
    #ifdef FX_DOF
      // 全分辨率算弥散圈，边缘跟着清晰的几何走；模糊结果来自半分辨率
      float coc = cocAt(vUv, D);
      c = mix(c, texture2D(tBlur, vUv).rgb, smoothstep(0.04, 0.45, coc));
    #endif
    #ifdef FX_CLOUD
      // P5：程序化云影（多层旋转噪声 + 宽边渐变，跟天上云量一致），不再平铺噪声贴图（格点值噪声会叠出横平竖直的长条暗块）
      if (D < uFar * 0.98) {
        vec4 v = uInvProj * vec4(vUv * 2.0 - 1.0, texture2D(tDepth, vUv).x, 1.0);
        vec3 w = (uCamWorld * vec4(v.xyz / v.w, 1.0)).xyz;
        if (w.y < 40.0) {
          vec2 p = (w.xz - uCloudWind.xy * uTime) / uCloudWind.z;
          float sh = cloudField(p, uCloudCover, 0.22, 4) * (1.0 - smoothstep(uCloudFade.x, uCloudFade.y, D));
          c *= 1.0 - uCloud * sh;
        }
      }
    #endif
    #ifdef FX_BLOOM
      c += (texture2D(tBloomA, vUv).rgb * 0.6 + texture2D(tBloomB, vUv).rgb * 0.8) * uBloom;
    #endif
    c = toSRGB(clamp(NeutralToneMapping(c), 0.0, 1.0));

    // P0 基础分级（fx 全关时画面与 P0 一致）
    float l = dot(c, vec3(0.2126, 0.7152, 0.0722));
    vec3 x = mix(vec3(l), c, uSaturation);
    x = (x - 0.5) * uContrast + 0.5;
    x += vec3(uWarm, uWarm * 0.35, -uWarm) * smoothstep(0.0, 0.25, l);
    x = clamp(x, 0.0, 1.0);

    #ifdef FX_GRADE
      // 暖调 LUT：两端钉死的 S 曲线（只加对比、不抬黑位），暗部偏暖棕、亮部偏奶油色，都是乘法不会发灰
      vec3 s = x * x * (3.0 - 2.0 * x);
      x = mix(x, s, 0.35 * uLut);
      float lx = dot(x, vec3(0.2126, 0.7152, 0.0722));
      x *= mix(vec3(1.0), mix(uShadowTint, uHighTint, smoothstep(0.15, 0.85, lx)), uLut);
      x = clamp(x, 0.0, 1.0);
    #endif
    #ifdef FX_VIGNETTE
      vec2 q = (vUv - 0.5) * vec2(uAspect, 1.0) / length(vec2(uAspect, 1.0)) * 2.0;
      // P5b：聚焦时 uVigMul → 0（焦点只靠虚化表达，邻居不压暗）
      x *= 1.0 - uVignette * uVigMul * smoothstep(0.45, 1.05, length(q));
    #endif
    gl_FragColor = vec4(x, 1.0);
  }
`;

const rt = (opts = {}) => new THREE.WebGLRenderTarget(1, 1, { type: THREE.HalfFloatType, depthBuffer: false, ...opts });

export class Post {
  constructor(renderer) {
    this.renderer = renderer;
    this.size = new THREE.Vector2(1, 1);
    // 场景目标：4×MSAA，深度解析到深度纹理（反向深度要 32 位浮点）
    this.rtScene = rt({ samples: 4, depthBuffer: true });
    this.rtScene.depthTexture = new THREE.DepthTexture(1, 1, THREE.FloatType);
    this.rtHalf = rt(); this.rtBlur = rt();
    this.rtBloomA = rt(); this.rtBloomA2 = rt(); this.rtBloomB = rt(); this.rtBloomB2 = rt();
    for (const r of [this.rtHalf, this.rtBlur, this.rtBloomA, this.rtBloomA2, this.rtBloomB, this.rtBloomB2]) r.texture.generateMipmaps = false;

    const depthU = () => ({
      tDepth: { value: this.rtScene.depthTexture }, uNear: { value: 0.1 }, uFar: { value: 900 },
      uFocusDist: this.focusU.dist, uFocusRange: this.focusU.range, uFocusFade: this.focusU.fade,
      uEdge0: this.focusU.edge0, uEdge1: this.focusU.edge1, uEdgeK: this.focusU.edgeK, uAspect: this.focusU.aspect, uFocusUv: this.focusU.uv,
      uDofAmt: this.focusU.amt,
    });
    // 景深的焦点参数几个 pass 共用同一组 uniform 对象；amt = 0 时全清楚（全景）
    this.focusU = { dist: { value: 50 }, range: { value: 0.2 }, fade: { value: 0.5 }, edge0: { value: 0.3 }, edge1: { value: 0.8 }, edgeK: { value: 0.6 },
      aspect: { value: 1 }, uv: { value: new THREE.Vector2(0.5, 0.5) }, amt: { value: 0 } };
    const mat = (fs, uniforms, defines = {}) => new THREE.ShaderMaterial({ vertexShader: VS, fragmentShader: fs, uniforms, defines, depthTest: false, depthWrite: false });

    this.down = mat(DOWN_FS, { tColor: { value: this.rtScene.texture }, uTexel: { value: new THREE.Vector2() }, ...depthU() });
    this.blur = mat(BLUR_FS, { tHalf: { value: this.rtHalf.texture }, uTexel: { value: new THREE.Vector2() }, uMaxR: { value: 4 } });
    this.bright = mat(BRIGHT_FS, { tColor: { value: this.rtScene.texture }, uTexel: { value: new THREE.Vector2() }, uThreshold: { value: 1 }, uKnee: { value: 0.3 } });
    this.gauss = mat(GAUSS_FS, { tSrc: { value: null }, uDir: { value: new THREE.Vector2() } });
    this.final = mat(FINAL_FS, {
      tColor: { value: this.rtScene.texture }, tBlur: { value: this.rtBlur.texture },
      tBloomA: { value: this.rtBloomA.texture }, tBloomB: { value: this.rtBloomB.texture }, uCloudCover: { value: 0.42 },
      uExposure: { value: 1 }, uContrast: { value: 1 }, uSaturation: { value: 1 }, uWarm: { value: 0 },
      uLut: { value: 0 }, uVignette: { value: 0 }, uVigMul: { value: 1 }, uBloom: { value: 0 }, uCloud: { value: 0 }, uTime: { value: 0 },
      uCloudWind: { value: new THREE.Vector3(2, 1, 120) }, uCloudFade: { value: new THREE.Vector2(200, 400) },
      uInvProj: { value: new THREE.Matrix4() }, uCamWorld: { value: new THREE.Matrix4() },
      uShadowTint: { value: new THREE.Color(1, 0.97, 0.93) }, uHighTint: { value: new THREE.Color(1.03, 1, 0.93) },
      ...depthU(),
    });
    for (const m of [this.down, this.blur, this.bright, this.gauss, this.final]) m.toneMapped = false;
    this.quad = new FullScreenQuad(this.down);
    this.on = {};
  }

  // on: { dof, bloom, cloud, grade, vignette } —— 改变时重编译合成着色器（只在切画质 / 切 fx 时发生）
  setEnabled(on) {
    const key = Object.keys(on).filter((k) => on[k]).sort().join(',');
    if (key === this._key) return;
    this._key = key;
    this.on = { ...on };
    const d = {};
    if (on.dof) d.FX_DOF = '';
    if (on.bloom) d.FX_BLOOM = '';
    if (on.cloud) d.FX_CLOUD = '';
    if (on.grade) d.FX_GRADE = '';
    if (on.vignette) d.FX_VIGNETTE = '';
    this.final.defines = d;
    this.final.needsUpdate = true;
  }

  setSize(w, h) {
    // w, h 为实际像素
    if (this.size.x === w && this.size.y === h) return;
    this.size.set(w, h);
    this.rtScene.setSize(w, h);
    const hw = Math.max(1, Math.round(w / 2)), hh = Math.max(1, Math.round(h / 2));
    this.rtHalf.setSize(hw, hh); this.rtBlur.setSize(hw, hh);
    const qw = Math.max(1, Math.round(w / 4)), qh = Math.max(1, Math.round(h / 4));
    this.rtBloomA.setSize(qw, qh); this.rtBloomA2.setSize(qw, qh);
    this.rtBloomB.setSize(Math.max(1, qw >> 1), Math.max(1, qh >> 1)); this.rtBloomB2.setSize(Math.max(1, qw >> 1), Math.max(1, qh >> 1));
    this.down.uniforms.uTexel.value.set(1 / w, 1 / h);
    this.blur.uniforms.uTexel.value.set(1 / hw, 1 / hh);
    this.bright.uniforms.uTexel.value.set(1 / w, 1 / h);
    this.focusU.aspect.value = w / h;
  }

  pass(material, target) {
    this.quad.material = material;
    this.renderer.setRenderTarget(target);
    this.quad.render(this.renderer);
  }
  gaussian(src, tmp, dst) {
    const u = this.gauss.uniforms;
    u.tSrc.value = src.texture; u.uDir.value.set(1 / src.width, 0); this.pass(this.gauss, tmp);
    u.tSrc.value = tmp.texture; u.uDir.value.set(0, 1 / src.height); this.pass(this.gauss, dst);
  }

  render(scene, camera, t) {
    const r = this.renderer;
    const on = this.on;
    r.setRenderTarget(this.rtScene);
    r.render(scene, camera);
    for (const m of [this.down, this.final]) { m.uniforms.uNear.value = camera.near; m.uniforms.uFar.value = camera.far; }
    if (on.dof && this.focusU.amt.value > 0.001) { this.pass(this.down, this.rtHalf); this.pass(this.blur, this.rtBlur); }
    if (on.bloom && this.final.uniforms.uBloom.value > 0.001) {
      this.pass(this.bright, this.rtBloomA2);
      this.gaussian(this.rtBloomA2, this.rtBloomA, this.rtBloomA2);
      // 第二级：从第一级再降一半，光晕更宽更柔
      this.gauss.uniforms.tSrc.value = this.rtBloomA2.texture; this.gauss.uniforms.uDir.value.set(0.5 / this.rtBloomA2.width, 0.5 / this.rtBloomA2.height);
      this.pass(this.gauss, this.rtBloomB2);
      this.gaussian(this.rtBloomB2, this.rtBloomB, this.rtBloomB2);
      this.final.uniforms.tBloomA.value = this.rtBloomA2.texture;
      this.final.uniforms.tBloomB.value = this.rtBloomB2.texture;
    }
    const u = this.final.uniforms;
    if (on.cloud) {
      u.uTime.value = t;
      u.uInvProj.value.copy(camera.projectionMatrixInverse);
      u.uCamWorld.value.copy(camera.matrixWorld);
    }
    this.pass(this.final, null);
  }

  dispose() {
    for (const r of [this.rtScene, this.rtHalf, this.rtBlur, this.rtBloomA, this.rtBloomA2, this.rtBloomB, this.rtBloomB2]) r.dispose();
  }
}

// ── 接触阴影 A-2：每个落地物件底下一张贴地柔边贴片（圆角矩形 SDF，外沿和内沿都渐隐 → 只在接触线附近变暗），
// 乘算混合，一块地一个 InstancedMesh（1 个 draw call）。items: [{ x, y, z, rot, hx, hz, fall, k }]（地块本地坐标）
const CONTACT_VS = /* glsl */`
  attribute vec4 aBox;     // hx, hz, 渐隐宽度, 浓度
  varying vec2 vP;
  varying vec4 vBox;
  #include <common>
  #include <fog_pars_vertex>
  void main() {
    vBox = aBox;
    vP = position.xz * 2.0 * (aBox.xy + aBox.z);
    vec4 mvPosition = modelViewMatrix * instanceMatrix * vec4(vP.x, 0.0, vP.y, 1.0);
    gl_Position = projectionMatrix * mvPosition;
    #include <fog_vertex>
  }
`;
const CONTACT_FS = /* glsl */`
  uniform float uStrength;
  uniform vec3 uTint;
  varying vec2 vP;
  varying vec4 vBox;
  #include <common>
  #include <fog_pars_fragment>
  void main() {
    vec2 h = vBox.xy;
    float r = min(h.x, h.y) * 0.45;
    vec2 q = abs(vP) - h + r;
    float sd = length(max(q, 0.0)) + min(max(q.x, q.y), 0.0) - r;   // 圆角矩形符号距离（米）
    float f = vBox.z;
    float a = sd > 0.0 ? 1.0 - smoothstep(0.0, f, sd) : 1.0 - smoothstep(0.0, f * 1.6, -sd);
    a = a * a * vBox.w * uStrength;
    vec3 m = mix(vec3(1.0), uTint, a);
    #ifdef USE_FOG
      float depth = vFogDepth;
      float fogF = smoothstep(fogNear, fogFar, depth);
      m = mix(m, vec3(1.0), fogF);
    #endif
    gl_FragColor = vec4(m, 1.0);
  }
`;
// 全部地块共用一个材质：uStrength / uTint 改一处全场生效。乘算：结果 = 底色 × 贴片色
export function makeContactMaterial(strength, tint) {
  const uniforms = THREE.UniformsUtils.merge([THREE.UniformsLib.fog, { uStrength: { value: strength }, uTint: { value: new THREE.Color(tint) } }]);
  return new THREE.ShaderMaterial({
    vertexShader: CONTACT_VS, fragmentShader: CONTACT_FS, uniforms,
    fog: true, transparent: true, depthWrite: false,
    blending: THREE.CustomBlending, blendEquation: THREE.AddEquation, blendSrc: THREE.ZeroFactor, blendDst: THREE.SrcColorFactor,
    polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -2,
    toneMapped: false,
  });
}
export function buildContactMesh(items, material) {
  const g = new THREE.PlaneGeometry(1, 1).rotateX(-Math.PI / 2);
  const box = new Float32Array(items.length * 4);
  const mesh = new THREE.InstancedMesh(g, material, items.length);
  const M = new THREE.Matrix4(), Q = new THREE.Quaternion(), Y = new THREE.Vector3(0, 1, 0), P = new THREE.Vector3(), S = new THREE.Vector3(1, 1, 1);
  items.forEach((it, i) => {
    M.compose(P.set(it.x, it.y, it.z), Q.setFromAxisAngle(Y, it.rot), S);
    mesh.setMatrixAt(i, M);
    box.set([it.hx, it.hz, it.fall, it.k], i * 4);
  });
  g.setAttribute('aBox', new THREE.InstancedBufferAttribute(box, 4));
  mesh.frustumCulled = false;   // 实例散在整块地上；整块地本来就在视野里
  mesh.renderOrder = 1;
  mesh.name = 'contact';
  return mesh;
}
