import * as THREE from 'three';

// 程序化 Canvas 纹理：不依赖任何外部图片。固定种子随机，每次刷新一致；
// 跨边界的图元从对边补画一份，RepeatWrapping 平铺时没有接缝。

// 固定种子随机（mulberry32）
function rng(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6D2B79F5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function canvas2d(size) {
  const c = document.createElement('canvas');
  c.width = c.height = size;
  return [c, c.getContext('2d')];
}

// 在 (x, y) 画一个外接半径 r 的图元；靠边时在对边（含对角）再画一份
function wrapped(size, x, y, r, draw) {
  for (const dx of [-size, 0, size]) {
    if (x + dx + r < 0 || x + dx - r > size) continue;
    for (const dy of [-size, 0, size]) {
      if (y + dy + r < 0 || y + dy - r > size) continue;
      draw(x + dx, y + dy);
    }
  }
}

// colorSpace 必须标成 sRGB：Canvas 像素本来就是 sRGB，不标的话会被当成线性值，颜色发灰
function toTexture(canvas, renderer, rx, ry) {
  const tex = new THREE.CanvasTexture(canvas);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
  tex.repeat.set(rx, ry);
  tex.anisotropy = renderer?.capabilities?.getMaxAnisotropy?.() ?? 4;
  return tex;
}

/** 草地：#9CC48F 底 + 1500~2500 个 1~3px 草粒 + 20~30 块柔和深色斑，512²，平铺 24×24 */
export function grassTexture(renderer) {
  const S = 512;
  const [c, g] = canvas2d(S);
  const rand = rng(51207);

  g.fillStyle = '#9CC48F';
  g.fillRect(0, 0, S, S);

  // 草粒
  const DOTS = ['#8FBA84', '#A8CF9B', '#93C087'];
  const dotCount = 1500 + Math.floor(rand() * 1001);
  for (let i = 0; i < dotCount; i++) {
    const x = rand() * S;
    const y = rand() * S;
    const d = 1 + rand() * 2;
    g.fillStyle = DOTS[Math.floor(rand() * DOTS.length)];
    wrapped(S, x, y, d, (px, py) => g.fillRect(px, py, d, d));
  }

  // 明暗起伏：#7FAE76 径向渐变斑，中心不透明度 0.06~0.12，边缘淡到 0
  const blotchCount = 20 + Math.floor(rand() * 11);
  for (let i = 0; i < blotchCount; i++) {
    const x = rand() * S;
    const y = rand() * S;
    const r = 20 + rand() * 40;
    const a = 0.06 + rand() * 0.06;
    wrapped(S, x, y, r, (px, py) => {
      const grd = g.createRadialGradient(px, py, 0, px, py, r);
      grd.addColorStop(0, `rgba(127,174,118,${a.toFixed(3)})`);
      grd.addColorStop(1, 'rgba(127,174,118,0)');
      g.fillStyle = grd;
      g.fillRect(px - r, py - r, r * 2, r * 2);
    });
  }

  return toTexture(c, renderer, 24, 24);
}

/** 广场方砖：#EDE4D3 底，每 64px 一条 2px 砖缝（8×8 块），砖内随机色差与淡色斑点，512²，平铺 3×3 */
export function pavingTexture(renderer) {
  const S = 512;
  const CELL = 64;
  const JOINT = 2;
  const [c, g] = canvas2d(S);
  const rand = rng(64011);

  g.fillStyle = '#EDE4D3';
  g.fillRect(0, 0, S, S);

  for (let bx = 0; bx < S; bx += CELL) {
    for (let by = 0; by < S; by += CELL) {
      // 每块砖整体略偏亮或偏暗一点
      g.fillStyle = rand() < 0.5
        ? `rgba(255,252,244,${(rand() * 0.25).toFixed(3)})`
        : `rgba(205,190,165,${(rand() * 0.12).toFixed(3)})`;
      g.fillRect(bx, by, CELL, CELL);

      // 砖内淡色斑点，留出砖缝边距
      const spots = 6 + Math.floor(rand() * 8);
      for (let k = 0; k < spots; k++) {
        const r = 1 + rand() * 2.5;
        const x = bx + JOINT + r + rand() * (CELL - JOINT - r * 2);
        const y = by + JOINT + r + rand() * (CELL - JOINT - r * 2);
        g.fillStyle = rand() < 0.6
          ? `rgba(250,246,236,${(0.3 + rand() * 0.4).toFixed(3)})`
          : `rgba(214,201,180,${(0.15 + rand() * 0.2).toFixed(3)})`;
        g.beginPath();
        g.arc(x, y, r, 0, Math.PI * 2);
        g.fill();
      }
    }
  }

  // 砖缝：线落在每格起点，平铺后间距仍是 64px
  g.fillStyle = '#D6C9B4';
  for (let p = 0; p < S; p += CELL) {
    g.fillRect(p, 0, JOINT, S);
    g.fillRect(0, p, S, JOINT);
  }

  return toTexture(c, renderer, 3, 3);
}

/**
 * 路面：#E8DFC9 底 + 细密横向浅纹，256²。
 * 路面几何 u 沿路长（被拉伸约 10 倍）、v 横跨路宽；纹路是等 v 的横线，沿 u 拉伸不变形。
 * v 只取 0.4 份，纹路间距在默认缩放下约 3~5 屏幕像素，不会被 mipmap 糊成一片
 */
export function roadTexture(renderer) {
  const S = 256;
  const [c, g] = canvas2d(S);
  const rand = rng(25601);

  g.fillStyle = '#E8DFC9';
  g.fillRect(0, 0, S, S);

  for (let y = rand() * 4; y < S; y += 6 + rand() * 8) {
    g.fillStyle = rand() < 0.65
      ? `rgba(247,242,230,${(0.35 + rand() * 0.35).toFixed(3)})`
      : `rgba(212,200,176,${(0.18 + rand() * 0.22).toFixed(3)})`;
    g.fillRect(0, y, S, 1 + Math.floor(rand() * 2));
  }

  return toTexture(c, renderer, 1, 0.4);
}
