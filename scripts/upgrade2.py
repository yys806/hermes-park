"""园区模型返工流水线 v2（任务从 tasks_upgrade.json 读取）。

用法：
  python upgrade2.py                      # 全部任务
  python upgrade2.py --only=control2,pi2  # 只跑指定
  python upgrade2.py --stop-after=2       # 跑两个就停
"""
import json, os, shutil, socket, struct, subprocess, sys, threading, time, uuid
from datetime import datetime

HOME = r"D:/hermes/home"
OUT = os.path.join(HOME, "out", "models")
VIEWER = os.path.join(HOME, "viewer", "models.json")
REPORT = os.path.join(HOME, "out", "报告-返工.md")
TASKS_JSON = os.path.join(HOME, "scripts", "tasks_upgrade.json")
TASKS_DIR = os.path.join(HOME, "prompts", "upgrade")
BLENDER = r"D:/hermes/home/tools/blender-4.5.9-windows-x64/blender.exe"

TOOLS = ("mcp__blender__execute_blender_code,mcp__blender__look,"
         "mcp__blender__get_scene_info,mcp__blender__get_addon_status,Read,Write,Edit")

COMMON = """
【通用要求】
- 绝不能用 read_factory_settings / read_homefile（会断开 MCP）。
- 只改指定场景 {scene}，不要动其它场景。
- 每隔几步保存一次 D:/hermes/home/out/models/all_plots.blend。
- 每次 execute_blender_code 不超过 70 行，一类一类做，做完用 look 看一眼。
- 导出：只导本场景，顶点色层名 AO，名字不要带 .001 后缀。
- 所有几何体必须在半个地块（{half} 米）范围内。

【精度基准】
- 文件 15 MB 以上、三角面 50 万以上。
- 每样东西都像"装出来的"：窗有窗框窗台窗棂、门有门框门板门把、屋顶有瓦垄檐口屋脊、
  地面铺装分块有缝、家具道具带零件。
- 卡通黏土风：大圆角、哑光、低饱和、柔光；不用贴图。

【绝对不要渲染】
- 一律不渲染，提示词里凡是写"渲染 xxx.png"的全部跳过。
- 自检只用 mcp__blender__look。
- 做完直接导出 glb。

【导出是最后一步，漏了等于没做】
- 收尾必须真的调用导出代码，把 D:/hermes/home/out/models/{scene}.glb 写出来，
  并打印导出后的文件大小、网格数、材质数。
- 如果做到一半发现时间不够，先把当前进度保存 .blend 并导出 glb，再继续细节；
  不要出现"场景做好了但 glb 没更新"的情况。

【直接动手】这是执行任务，不是写计划。不要输出步骤清单、不要复述要求。
"""


def log(msg):
    line = f"- `{datetime.now().strftime('%m-%d %H:%M')}` {msg}\n"
    open(REPORT, "a", encoding="utf-8").write(line)
    print(line.strip(), flush=True)


def blender_alive():
    try:
        s = socket.create_connection(("127.0.0.1", 9876), timeout=2)
        s.close()
        return True
    except Exception:
        return False


_BL_LOCK = threading.Lock()


def ensure_blender():
    with _BL_LOCK:
        if blender_alive():
            return True
        # 先把残留实例全清掉：多个 Blender 抢同一个 9876 会互相把对方搞崩
        kill_all_blender()
        time.sleep(5)
        subprocess.Popen([BLENDER, os.path.join(OUT, "all_plots.blend"),
                          "--python-expr", "import bpy;bpy.ops.blendermcp.start_server()"], cwd=HOME)
        for _ in range(40):
            time.sleep(3)
            if blender_alive():
                return True
        return False


def kill_all_blender():
    try:
        subprocess.run(["powershell", "-NoProfile", "-Command",
                        "Get-Process blender -ErrorAction SilentlyContinue | Stop-Process -Force"],
                       capture_output=True, timeout=60)
    except Exception:
        pass


def restart_blender():
    """每块跑完重启一次 Blender：12 个场景的 blend 跑久了内存会碎，崩溃都发生在第二三轮之后。"""
    try:
        subprocess.run(["powershell", "-NoProfile", "-Command",
                        "Get-Process blender -ErrorAction SilentlyContinue | Stop-Process -Force"],
                       capture_output=True, timeout=60)
    except Exception:
        pass
    time.sleep(4)
    return ensure_blender()


def watchdog():
    def loop():
        while True:
            time.sleep(20)
            if not blender_alive():
                log("看门狗：Blender 掉了，正在重启")
                ensure_blender()
    threading.Thread(target=loop, daemon=True).start()


def glb_stat(name, target):
    p = os.path.join(OUT, name + ".glb")
    if not os.path.exists(p):
        return None
    d = open(p, "rb").read()
    n = struct.unpack("<I", d[12:16])[0]
    js = json.loads(d[20:20 + n])
    lo = [1e9] * 3
    hi = [-1e9] * 3
    for nd in js["nodes"]:
        if "mesh" not in nd:
            continue
        tr = nd.get("translation", [0, 0, 0])
        sc = nd.get("scale", [1, 1, 1])
        for pr in js["meshes"][nd["mesh"]]["primitives"]:
            a = js["accessors"][pr["attributes"]["POSITION"]]
            if not a.get("min"):
                continue
            for k in range(3):
                lo[k] = min(lo[k], a["min"][k] * sc[k] + tr[k])
                hi[k] = max(hi[k], a["max"][k] * sc[k] + tr[k])
    size = (round(hi[0] - lo[0], 1), round(hi[2] - lo[2], 1))
    mats = [m.get("name", "") for m in js["materials"]]
    names = [x.get("name", "") for x in js["nodes"]]
    tris = sum(js["accessors"][pr["indices"]]["count"] // 3
               for m in js["meshes"] for pr in m["primitives"] if "indices" in pr)
    cols = set()
    for m in js["materials"]:
        bc = m.get("pbrMetallicRoughness", {}).get("baseColorFactor")
        if bc:
            cols.add(tuple(round(v, 2) for v in bc[:3]))
    return dict(size=size, ok=abs(size[0] - target) < 1.0 and abs(size[1] - target) < 1.0,
                tris=tris, mats=len(mats), colors=len(cols),
                lamps=len([m for m in mats if m.startswith("LGT_")]),
                mb=round(os.path.getsize(p) / 1048576, 1),
                glass=len([m for m in mats if m.lower().startswith("glass")]),
                loop=len([x for x in names if x.startswith("Loop_")]),
                geng=len([x for x in names if x.startswith("Geng")]),
                meshes=len([x for x in js["nodes"] if "mesh" in x]),
                images=len(js.get("images", [])))


def run_task(t, common):
    glbf = t.get("glbfile", t["id"])
    src = os.path.join(OUT, glbf + ".glb")
    before = glb_stat(glbf, t["size"])
    bak = os.path.join(OUT, "_bak", f"{glbf}_{datetime.now():%m%d%H%M%S}.glb")
    os.makedirs(os.path.dirname(bak), exist_ok=True)
    if os.path.exists(src):
        shutil.copy2(src, bak)

    os.makedirs(TASKS_DIR, exist_ok=True)
    pp = os.path.join(TASKS_DIR, t["id"] + ".txt")
    open(pp, "w", encoding="utf-8").write(t["prompt"] + common.format(scene=t["scene"], half=t["size"] / 2))

    log(f"开始返工 **{t['name']}**（改前 {before['mb'] if before else '?'} MB / "
        f"{before['tris'] if before else '?'} 面）")
    t0 = time.time()
    mtime0 = os.path.getmtime(src) if os.path.exists(src) else 0
    for attempt in range(1, 4):
        if attempt > 1:
            log(f"  第 {attempt - 1} 次没改动，等 60 秒重试")
            time.sleep(60)
            ensure_blender()
        session = str(uuid.uuid5(uuid.NAMESPACE_DNS,
                                 f"hermes-up-{t['id']}-{attempt}-{datetime.now():%Y%m%d%H%M%S}"))
        sh = (f'cd /d/hermes/home && claude -p "$(cat {pp.replace(chr(92), "/")})" '
              f'--session-id {session} --permission-mode acceptEdits --allowedTools "{TOOLS}"')
        outlog = os.path.join(HOME, "cache", "scratch", f"claude_{t['id']}_{attempt}.log")
        with open(outlog, "w", encoding="utf-8", errors="replace") as fh:
            proc = subprocess.Popen(["bash", "-lc", sh], cwd=HOME, stdout=fh,
                                    stderr=subprocess.STDOUT, start_new_session=True)
            try:
                proc.wait(timeout=4500)
                tail = open(outlog, encoding="utf-8", errors="replace").read()[-400:]
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(os.getpgid(proc.pid), 9)
                except Exception:
                    proc.kill()
                tail = "达到 75 分钟上限，已强制结束"
        mtime1 = os.path.getmtime(src) if os.path.exists(src) else 0
        if mtime1 > mtime0:
            break
        log(f"  ⚠️ 未改动：{(tail or '无输出').replace(chr(10), ' ')[-150:]}")

    # 统一由我自己导出：agent 自己导的时候会把别的场景的对象一起写进来（一版 control.glb 混进 400 个外场对象），
    # 所以每轮结束都用 export_scene_glb.py 重新导一遍——它会把其它场景直接删掉，只留目标场景。
    blend = os.path.join(OUT, "all_plots.blend")
    if os.path.exists(blend):
        log("  统一重导出（只导目标场景）")
        tmp_src = os.path.join(HOME, "cache", "scratch", f"exp_{t['id']}.blend")
        tmp_out = os.path.join(OUT, f"_{glbf}_clean.glb")
        try:
            shutil.copy2(blend, tmp_src)
            subprocess.run([BLENDER, "-b", tmp_src, "--python",
                            os.path.join(HOME, "scripts", "export_scene_glb.py"),
                            "--", t["scene"], tmp_out],
                           cwd=HOME, capture_output=True, text=True, timeout=1200)
        except Exception as e:
            log(f"  重导出失败：{e}")
        if os.path.exists(tmp_out) and os.path.getsize(tmp_out) > 500000:
            os.replace(tmp_out, src)
            log(f"  已用干净版覆盖 {round(os.path.getsize(src)/1048576,1)} MB")

    after = glb_stat(glbf, t["size"])
    worse = False
    if after and before and not t.get("no_guard"):
        cand_dir = os.path.join(OUT, "_cand")
        os.makedirs(cand_dir, exist_ok=True)
        shutil.copy2(src, os.path.join(cand_dir, f"{glbf}_{datetime.now():%m%d%H%M%S}.glb"))
        if after["mb"] < before["mb"] * 0.75:
            worse = True
        if after["tris"] < before["tris"] * 0.7:
            worse = True
        if before["lamps"] > 0 and after["lamps"] == 0:
            worse = True
    if worse:
        shutil.copy2(bak, src)
        log(f"  ⏪ 比改前明显缩水（{after['mb']}MB/{after['tris']:,}面 → 原 "
            f"{before['mb']}MB/{before['tris']:,}面），已回滚")
        after = glb_stat(glbf, t["size"])

    if after:
        meshes = after.get("meshes", 0)
        ok = after["ok"] and meshes >= 250 and after["mb"] >= 12
        log(f"  {t['name']}：{after['size'][0]}×{after['size'][1]} m / {after['tris']:,} 面 / "
            f"{after['mats']} 材质 / {after['colors']} 色 / 灯 {after['lamps']} / "
            f"网格 {after.get('meshes',0)} / 玻璃 {after['glass']} / Loop {after['loop']} / Geng {after['geng']} / {after['mb']} MB"
            f" → {'✅达标' if ok else '⚠️未达 15MB'}")
        if after["ok"]:
            d = json.load(open(VIEWER, encoding="utf-8"))
            for m in d["models"]:
                if m["id"] == glbf:
                    m["status"] = "ready"
            json.dump(d, open(VIEWER, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    else:
        log(f"  ❌ {t['name']} 没有产出 glb")
    log(f"  用时 {int((time.time() - t0) / 60)} 分钟")


def main():
    only, stop = None, None
    for a in sys.argv[1:]:
        if a.startswith("--only="):
            only = a.split("=", 1)[1].split(",")
        if a.startswith("--stop-after="):
            stop = int(a.split("=", 1)[1])
    tasks = json.load(open(TASKS_JSON, encoding="utf-8"))
    # 干净起步：残留的 Blender 会占着 9876 不放，导致新实例起不来、MCP 客户端连到坏实例
    kill_all_blender()
    time.sleep(5)
    if not os.path.exists(REPORT):
        open(REPORT, "w", encoding="utf-8").write(f"# 返工报告\n\n开始：{datetime.now():%m-%d %H:%M}\n\n")
    watchdog()
    done = 0
    for t in tasks:
        if only and t["id"] not in only:
            continue
        if not ensure_blender():
            log("Blender 起不来，中止")
            break
        run_task(t, COMMON)
        done += 1
        log(f"  重启 Blender 释放内存")
        restart_blender()
        if stop and done >= stop:
            break
    log("返工流水线结束")


if __name__ == "__main__":
    main()
