"""按标准流水线批量生成剩余地块。

用法：python build_all_plots.py [--only id1,id2] [--stop-after N]
每块地：生成提示词 -> 调 claude CLI -> 解析 glb 验收 -> 更新 models.json -> 追加报告
"""
import json, os, re, subprocess, sys, time, struct, socket, uuid
from datetime import datetime

HOME = r"D:/hermes/home"
DESIGN = os.path.join(HOME, "prompts", "地块设计-提示词合集-20261028.md")
PROMPT_DIR = os.path.join(HOME, "prompts")
OUT = os.path.join(HOME, "out", "models")
REPORT = os.path.join(HOME, "out", "报告-批量建模.md")

# 板块定义：id / 名称 / 尺寸 / 灯命名用的地块键 / 设计文档里的章节号
PLOTS = [
    dict(id="clawd",  name="Claude · 外协",   size=20, key="clawd",  sec="Claude（Clawd）",  handiwork=True),
    dict(id="pi",     name="Pi · 外协",       size=20, key="pi",     sec="Codex",            handiwork=True),  # 章节按需覆盖
    dict(id="codex",  name="Codex · 外协",    size=20, key="codex",  sec="Codex",            handiwork=True),
    dict(id="family", name="家人事务",         size=16, key="family", sec="三、家人事务（`house` → 家人）"),
    dict(id="clock",  name="通知待办",         size=16, key="clock",  sec="四、通知待办（`clock`）"),
    dict(id="vault",  name="资产管理",         size=16, key="vault",  sec="五、资产管理（`vault`）"),
    dict(id="press",  name="咨询新闻",         size=16, key="press",  sec="六、咨询新闻（`press`）"),
    dict(id="inventor", name="奇思妙想",       size=16, key="inventor", sec="七、奇思妙想（`inventor`）"),
    dict(id="rainbow", name="彩虹事务",         size=16, key="rainbow", sec="八、彩虹事务 · 老婆（`arch` v2）"),
    dict(id="control", name="中央大厅 · 全园中枢", size=25, key="control", sec="十、总控 · 中央大厅（`control`，Hermes / 更 Vigil 本体）"),
]

STANDARD = """
============================================================
【硬标准（用户 2026-10-28 定稿，违反即返工）】
============================================================
尺寸：本块地位 {size}×{size} 米，南面为正入口。
比例：虚拟人物 1.7 m 为基准；门洞净高 2.0-2.2 m、净宽 0.9-1.2 m；层高 2.8-3.2 m；
      台阶 0.15×0.30 m；栏杆 0.9-1.1 m；窗台 0.9 m。
复杂度：对齐已定稿的「学习科研」地块（24 mesh 级别的主体建筑 + 完整配景）。

资产优先复用（本地 CC0 库，别手搓）：
  D:/hermes/home/assets/lib/clay/
    quaternius-ultimate-nature/        树/灌木/草/花/岩石（.blend 可 append，四季变体齐全）
    quaternius-stylized-nature-megakit/ 蕨/蘑菇/卵石/草丛（fbx）
    quaternius-fantasy-props/          长椅/书架/书堆/木桶/纸箱/瓶（fbx）
    quaternius-medieval-village/       门窗/地板/阳台/楼梯（fbx）

四季结构（必须有）：
  绿植用 Foliage_*，同时放 Foliage_Autumn_*（秋黄）、Bare_*（枯枝）、Snow_*（积雪）三套，
  位置一一对应，全部标 extras.default_visible = false。
  冬季雪必须包含：地面雪层 Snow_ground、每个屋顶 Snow_roof_<建筑>（要高出女儿墙/屋脊、
  边缘外挑下垂，不能被女儿墙夹住看不见）、道具顶面积雪 Snow_props、篱笆顶 Snow_fence。
  注意：某物件同时有 Bare_ 版时不要再给它的 Snow_ 版（会重叠）。

传送带五层接口（命名必须精确）：
  Port_<元素>        每个功能实体一个，0.8×0.35 m，带宽法兰+螺栓
  Belt_Sub_<元素>    子带，宽度 0.5-0.7 m，允许不等宽
  Belt_Hub_{key}     汇总节点，院子中心，浅木圆角方台
  Belt_Main_{key}    主干带约 1.0 m，从汇总节点笔直往南
  Port_Main_{key}    地块总出口 1.2×0.5 m，朝正南，停在边界内 0.2 m

灯具（硬规则）：
  命名 LGT_{key}_<灯名>；灯罩单独一个以 LGT_ 开头的材质。
  每盏灯必须有实体：底座 + 灯杆 + 灯头（灯笼/灯罩），高 2.2-3.0 m。
  只有灯罩发光；灯杆、底座、托架一律普通材质（整根杆发亮是错的）。
  一盏灯一个点光源，位置在灯头；室内灯必须 castShadow。
  绝不造光晕贴片。灯要摆在开阔处、沿主路，不许贴边界篱笆。
  室内不要做吊灯（用户明确说过：只要该有的，不要擅自加）。

材质（黏土感）：
  Roughness 0.90-0.95、Specular 0、Metallic 0、Subsurface Weight 0.2
  （Radius 0.02/0.015/0.01，Scale 0.05）。
  所有改拓扑的修改器先应用再加细分/倒角；贴图一律清空只留纯色。
  把 AO 烘进顶点色（导出时 export_vertex_color 指定 AO 层），这是网页里保留柔和暗部的唯一办法。

其它命名：
  Obj_<元素>    可点击的功能实体
  Ground_*      base / paving / grass / mat / woodpath 等
  Fence_south   南侧矮篱笆

============================================================
【工作方式】
============================================================
- 绝不能用 read_factory_settings / read_homefile（会断开 MCP）。
- 这块地建在一个**新场景**里，场景名用 "{key}"；不要改动其它场景。
- 保存：每隔一类（地基/建筑/传送带/灯/四季/烘 AO）就存一次
  D:/hermes/home/out/models/all_plots.blend（崩溃会白做，务必勤存）。
- 每次 execute_blender_code ≤ 70 行；一类一类做；每做完一类 look 看一眼。
- 三角面控制在 60 万以内；所有几何体必须落在 ±{half} 米以内（地块边界）。

【收尾（必须全做）】
1) 渲染到 D:/hermes/cache/scratch/{key}_iso.png（等距全景）+ {key}_winter.png（冬季）
2) 保存 blend，导出 D:/hermes/home/out/models/{id}.glb（只导 {key} 场景，
   顶点色层名 AO，贴图清空，名字不要带 .001 后缀）
3) print 清单：总对象数/三角面/材质数/世界包围盒（必须是 {size}×{size}）；
   所有 Port_/Belt_/LGT_{key}_/Obj_ 物件名；四季物件数量；每盏灯高度与坐标
4) 中文报告：各实体怎么做的、传送带走线、灯怎么布的、哪里还没做到
"""


def read_design():
    txt = open(DESIGN, encoding="utf-8").read()
    return txt


def section_of(design, sec):
    """按章节标题粗切设计文档的一节。"""
    idx = design.find(sec)
    if idx < 0:
        return ""
    nxt = design.find("\n## ", idx + len(sec))
    if nxt < 0:
        nxt = len(design)
    return design[idx:nxt].strip()


def build_prompt(plot, design):
    body = section_of(design, plot["sec"])
    if plot["id"] == "pi":
        # Pi 的设计在「三个外部 Agent」里，取 Pi 小节
        idx = design.find("### Pi")
        nxt = design.find("###", idx + 5)
        body = design[idx:nxt if nxt > 0 else len(design)].strip()
    if not body:
        body = "（设计文档里没找到这一节，按下方标准与名称自行设计）"
    # 把设计里的 10×10 改成实际尺寸
    body = body.replace("10×10 米", f"{plot['size']}×{plot['size']} 米").replace("10X10", f"{plot['size']}X{plot['size']}")
    std = STANDARD.format(
        size=plot["size"], key=plot["key"], id=plot["id"],
        half=plot["size"] / 2,
    )
    if plot.get("handiwork"):
        std = std.replace("传送带五层接口（命名必须精确）：", "【手办地块：不需要传送带】下面这节跳过：")
    return f"""【任务授权声明】Hermes 派发的建模任务（地块 {plot['id']} · {plot['name']}），用户已授权，你直接操作 Blender。

============================================================
【设计（已定稿，照做，可自行丰富细节）】
============================================================
{body}

{std}
"""


def glb_check(path):
    if not os.path.exists(path):
        return dict(ok=False, err="glb 不存在")
    d = open(path, "rb").read()
    n = struct.unpack("<I", d[12:16])[0]
    js = json.loads(d[20:20 + n])
    off = 20 + n + 8
    nodes = js["nodes"]
    prims = [pr for m in js["meshes"] for pr in m["primitives"]]
    mats = [m.get("name", "") for m in js["materials"]]
    names = [x.get("name", "") for x in nodes]

    # 世界包围盒（逐顶点，带节点变换）
    lo = [1e9] * 3; hi = [-1e9] * 3
    for nd in nodes:
        if "mesh" not in nd:
            continue
        tr = nd.get("translation", [0, 0, 0]); sc = nd.get("scale", [1, 1, 1])
        for pr in js["meshes"][nd["mesh"]]["primitives"]:
            a = js["accessors"][pr["attributes"]["POSITION"]]
            mn, mx = a.get("min"), a.get("max")
            if not mn:
                continue
            for k in range(3):
                lo[k] = min(lo[k], mn[k] * sc[k] + tr[k])
                hi[k] = max(hi[k], mx[k] * sc[k] + tr[k])
    size = [hi[k] - lo[k] for k in range(3)]

    color_ok = sum(1 for pr in prims if "COLOR_0" in pr.get("attributes", {}))
    return dict(
        ok=True,
        nodes=len(nodes), mats=len(mats), prims=len(prims),
        color=f"{color_ok}/{len(prims)}",
        size=[round(v, 2) for v in size],
        lgt_mats=len([m for m in mats if m.startswith("LGT_")]),
        ports=len([x for x in names if x.startswith("Port_")]),
        belts=len([x for x in names if x.startswith("Belt_")]),
        objs=len([x for x in names if x.startswith("Obj_")]),
        autumn=len([x for x in names if x.startswith("Foliage_Autumn_")]),
        bare=len([x for x in names if x.startswith("Bare_")]),
        snow=len([x for x in names if x.startswith("Snow_")]),
        hidden=sum(1 for x in nodes if (x.get("extras") or {}).get("default_visible") is False),
        dots=len([x for x in names if re.search(r"\.\d{3}$", x)]),
    )


def update_models(plot):
    p = os.path.join(HOME, "viewer", "models.json")
    d = json.load(open(p, encoding="utf-8"))
    for m in d["models"]:
        if m["id"] == plot["id"]:
            m["status"] = "ready"
            m["file"] = plot["id"] + ".glb"
            m["size"] = {"w": plot["size"], "h": plot["size"]}
    json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)


def blender_alive():
    try:
        s = socket.create_connection(("127.0.0.1", 9876), timeout=2)
        s.close()
        return True
    except Exception:
        return False


def ensure_blender():
    """Blender 崩了就重启并打开工作文件，保证下一块地能继续。"""
    if blender_alive():
        return True
    log("⚠️ 检测到 Blender 不在，正在重启")
    work = os.path.join(OUT, "all_plots.blend")
    if not os.path.exists(work):
        work = os.path.join(OUT, "daily.blend")
    exe = r"D:/hermes/home/tools/blender-4.5.9-windows-x64/blender.exe"
    starter = "import bpy;bpy.ops.blendermcp.start_server()"
    subprocess.Popen([exe, work, "--python-expr", starter], cwd=HOME)
    for _ in range(60):
        time.sleep(3)
        if blender_alive():
            log("  Blender 已恢复监听")
            return True
    log("  ❌ Blender 重启失败，跳过后续地块")
    return False


def log(msg):
    line = f"- `{datetime.now().strftime('%m-%d %H:%M')}` {msg}\n"
    with open(REPORT, "a", encoding="utf-8") as f:
        f.write(line)
    print(line.strip())


def run_plot(plot, design):
    tag = plot["id"]
    prompt_path = os.path.join(PROMPT_DIR, f"auto-{tag}.txt")
    prompt = build_prompt(plot, design)
    # 清洗：emoji / 树状线会被中转站 400
    prompt = prompt.replace("🔴", "【必读】")
    prompt = re.sub(r"[\U0001F300-\U0001FAFF\u2600-\u27BF\uFE0F]", "", prompt)
    prompt = prompt.replace("├──", "- ").replace("└──", "- ").replace("│", "")
    open(prompt_path, "w", encoding="utf-8").write(prompt)

    glb = os.path.join(OUT, tag + ".glb")
    if os.path.exists(glb):
        os.remove(glb)  # 避免把旧文件当新成果

    session = str(uuid.uuid5(uuid.NAMESPACE_DNS, "hermes-plot-" + tag))
    # 用 bash 调 claude（Windows 上 claude 是 npm shim，直接 Popen 找不到）
    tools = ("mcp__blender__execute_blender_code,mcp__blender__look,"
             "mcp__blender__get_scene_info,mcp__blender__get_addon_status,Read,Write,Edit")
    bash_prompt = prompt_path.replace("\\", "/")   # bash 里反斜杠会被吃掉
    sh = (f'cd /d/hermes/home && claude -p "$(cat {bash_prompt})" '
          f'--session-id {session} --permission-mode acceptEdits '
          f'--allowedTools "{tools}"')
    cmd = ["bash", "-lc", sh]
    log(f"开始 **{plot['name']}**（{plot['size']}×{plot['size']}）")
    t0 = time.time()
    try:
        r = subprocess.run(cmd, cwd=HOME, capture_output=True, text=True, timeout=3600)
        tail = (r.stdout or "")[-800:] + (r.stderr or "")[-400:]
    except subprocess.TimeoutExpired:
        tail = "超时（60 分钟）"

    chk = glb_check(glb)
    if chk.get("ok"):
        target = plot["size"]
        ok_size = abs(chk["size"][0] - target) < 0.6 and abs(chk["size"][2] - target) < 0.6
        log(f"  {plot['name']} 产出：{chk['size'][0]}×{chk['size'][2]} m"
            f"{'（尺寸合格）' if ok_size else '（⚠️ 尺寸不合）'}，"
            f"{chk['nodes']} 节点 / {chk['mats']} 材质 / 顶点色 {chk['color']} / "
            f"LGT 材质 {chk['lgt_mats']} / Port {chk['ports']} / Belt {chk['belts']} / "
            f"Obj {chk['objs']} / 秋 {chk['autumn']} 枯 {chk['bare']} 雪 {chk['snow']} / "
            f"隐藏标记 {chk['hidden']} / .001 残留 {chk['dots']}")
        if ok_size and chk["dots"] == 0:
            update_models(plot)
            log(f"  ✅ {plot['name']} 已上线查看器")
        else:
            log(f"  ⚠️ {plot['name']} 需要返工（尺寸或命名不合格）")
    else:
        log(f"  ❌ {plot['name']} 没产出 glb：{chk.get('err')}｜末行输出：{tail[-200:].replace(chr(10),' ')}")
    log(f"  用时 {int((time.time()-t0)/60)} 分钟")


def main():
    only = None
    stop_after = None
    for a in sys.argv[1:]:
        if a.startswith("--only="):
            only = a.split("=", 1)[1].split(",")
        if a.startswith("--stop-after="):
            stop_after = int(a.split("=", 1)[1])
    design = read_design()
    todo = [p for p in PLOTS if (only is None or p["id"] in only)]
    if not os.path.exists(REPORT):
        open(REPORT, "w", encoding="utf-8").write(
            f"# 批量建模报告\n\n开始时间：{datetime.now():%Y-%m-%d %H:%M}\n\n")
    done = 0
    for plot in todo:
        run_plot(plot, design)
        done += 1
        if stop_after and done >= stop_after:
            break
    log("本轮流水线结束")


if __name__ == "__main__":
    main()
