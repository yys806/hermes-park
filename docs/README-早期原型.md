# 园区中控台 · Hermes 自动化可视化

等距微缩 3D 园区，把 8 个飞书群做成 8 座工厂、3 个外部 agent 做成园区外的外协单位，中心是中控塔。

## 目录

```
index.html            入口（含 importmap）
src/
  main.js             渲染器 / 正交等距相机 / 三层光照 / OrbitControls / 模块加载
  config.js           配色、布局、8 个工厂与 3 个外协的定义
  utils/
    roundedBox.js     圆角立方体几何（解决「太硬」的核心）
    materials.js      材质工厂（复用、玻璃、自发光、接触阴影）
    contactShadow.js  贴地假 AO 薄片
  scene/              场景模块（每个物件一个文件，缺文件自动跳过）
    base.js           地台
    road.js           道路
    controlTower.js   中控塔
    factories.js      8 座工厂
    agents.js         3 个外协（Clawd / Pi / Codex）
    props.js          树、路灯、货箱、栅栏、告示牌等环境细节
  state/
    mock.json         假数据（后端未接通时用）
server/
  server.js           静态服务器 + /api/state
vendor/three/         three.js 本地副本（ESM + OrbitControls）
```

## 本地运行

必须用 HTTP 打开（ES module 在 file:// 下会被 CORS 拦）：

```bash
node server/server.js
# 浏览器打开 http://127.0.0.1:8788
```

## 部署

前端是纯静态（vendor + src + index.html 一起上传即可），可放 Netlify / nginx / S3。
`/api/state` 需要一个常驻 Node 进程；若前端与后端不同源，把 `src/main.js` 里的 fetch 地址改成后端公网地址。

## 扩展

- 加一个工厂：在 `config.js` 的 `factories` 里加一条，在 `src/scene/factories.js` 里加对应 `type` 的构建分支
- 换配色：只改 `config.js` 的 `palette`
- 接真实数据：改 `server/server.js` 的 `/api/state`，前端无需改动（轮询逻辑后续加）
