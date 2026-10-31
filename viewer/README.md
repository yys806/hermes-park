# 模型查看器

逐个审核 `out/models/*.glb` 的单页查看器。可任意角度拖动、缩放，每个模型有独立链接（`#<id>`）。

## 本地访问

在项目根目录运行：

```bash
node server/server.js
```

然后打开 <http://127.0.0.1:8788/viewer/>。单个模型直接用 hash 定位，例如 <http://127.0.0.1:8788/viewer/#library>。

页面依赖 ES module 与 `fetch`，不能用 `file://` 直接双击打开。

## 添加 / 更新模型

1. 把导出的 `<id>.glb` 放到 `out/models/`
2. 在 `viewer/models.json` 里登记，或把对应条目的 `status` 从 `pending` 改成 `ready`

```json
{ "id": "post", "name": "邮政局 · 日常事务", "file": "post.glb", "status": "ready" }
```

`pending` 的条目在列表里灰显、不可点；文件缺失或解析失败时页面显示原因，可以切到下一个。

## 操作

| 操作 | 桌面 | 移动端 |
| --- | --- | --- |
| 旋转 | 左键拖动 | 单指拖动 |
| 缩放 | 滚轮 | 双指捏合 |
| 复位 | 双击 / `R` / 「复位」按钮 | 双击 / 「复位」按钮 |
| 切换模型 | `←` `→` / 左侧列表 | 顶部「模型库」下拉 |
| 自动旋转 | 右上角开关 | 右上角开关 |

## 部署

所有路径都是相对的（`../vendor/three/`、`../out/models/`、`./models.json`），把项目根目录整体上传到任意静态托管即可，访问 `<站点>/viewer/`。需要一起上传的目录：

```
viewer/
vendor/three/
out/models/
```

注意托管要把 `.glb` 当二进制下发（多数托管默认 `application/octet-stream` 或 `model/gltf-binary`，都可以）。
