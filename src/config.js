// 全局配置：配色、布局、相机
export const palette = {
  bg:       0xF7F3E9,
  cream:    0xF7F3E9,
  towerBody: 0xEFE9DC, // 中控塔主体：比 cream 略暗，避免顶面打爆
  mint:     0xA8D5BA,
  wood:     0xD9B382,
  sky:      0xBFE3F2,
  orange:   0xF2A65A,
  brown:    0x4A3B2A,
  grass:    0x9CC48F,
  soil:     0xB08968,
  metal:    0xC9C6C0,
  glass:    0xDDEFF7,
  clawd:    0xDA7758,
  codexA:   0x4C6FFF,
  codexB:   0x8B5CF6,
  white:    0xFFFDF7,
};

// 园区布局（半径单位 = 世界单位）
export const layout = {
  groundSize: 120,    // 地面一大片（无边缘、无厚度），边缘远在雾里
  ringRadius: 11.5,   // 工厂环半径
  agentRadius: 19,    // 外协位置半径（方位角在画面最右）
  outerRadius: 19,    // agents.js 仍读这个名字，保持与 agentRadius 一致
  treeRingInner: 20,  // 树林内圈半径（以内不放树）
  treeRingOuter: 46,  // 树林外圈半径
};

// 8 个飞书群对应的工厂（id 与后端状态 key 对应）
// angle 单位为度；0° 指向 +X，角度增大时从 +Y 俯视看为顺时针。
// 位置由主循环按 x = cos(a)*r, z = sin(a)*r 计算。
export const factories = [
  { id: 'study',   name: '学习科研', type: 'library',  angle: 200, color: 0x8FB8D8 },
  { id: 'daily',   name: '日常事务', type: 'post',     angle: 245, color: 0xA8D5BA },
  { id: 'rainbow', name: '彩虹事务', type: 'arch',     angle: 290, color: 0xE8A8C8 },
  { id: 'family',  name: '家人事务', type: 'house',    angle: 335, color: 0xF2C98A },
  { id: 'idea',    name: '奇思妙想', type: 'inventor', angle: 20,  color: 0xC3A8E8 },
  { id: 'notify',  name: '通知待办', type: 'clock',    angle: 65,  color: 0xF2A65A },
  { id: 'asset',   name: '资产管理', type: 'vault',    angle: 110, color: 0xD9B382 },
  { id: 'news',    name: '咨询新闻', type: 'press',    angle: 155, color: 0x9FB6C9 },
];

// 3 个外协 agent
export const agents = [
  // 正面直视时 +X 即画面右侧：-20/0/20 度三个外协竖排在最右
  { id: 'clawd', name: 'Claude', type: 'clawd', angle: -20, color: palette.clawd },
  { id: 'pi',    name: 'Pi',     type: 'pi',    angle: 0,   color: 0xFFFDF7 },
  { id: 'codex', name: 'Codex',  type: 'codex', angle: 20,  color: palette.codexA },
];

export const cameraCfg = {
  halfHeight: 11.5,      // 正交可视高度（越大看到越多）；拉近让设施在画面里更大
  target: [0, 2.2, 0],
  radius: 46,
  // 正面朝向：相机放在 +Z 正前方，朝 -Z 看
  theta: Math.PI / 2,
  // phi 是与 +Y 轴夹角：π/2 为水平直视，越小越俯。π/4 ≈ 0.7854，即俯角 45°
  phi: Math.PI / 4,
  minZoom: 0.7,
  maxZoom: 2.6,
  // 正交相机裁剪面。BokehPass 用 near/far 把深度图还原成视空间深度；
  // 45° 俯视下画面内最近的物体深度也在 ~20 以上，near=0.1 不会裁掉前景
  near: 0.1,
  far: 200,
};
