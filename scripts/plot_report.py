"""汇总各地块建模成果，供晨报使用。"""
import json, os, struct, re

HOME = r"D:/hermes/home"
OUT = os.path.join(HOME, "out", "models")
VIEWER = os.path.join(HOME, "viewer", "models.json")

PLOTS = [
    ("learn", "学习科研", 16), ("daily", "日常事务", 16),
    ("family", "家人事务", 16), ("rainbow", "彩虹事务", 16),
    ("inventor", "奇思妙想", 16), ("clock", "通知待办", 16),
    ("vault", "资产管理", 16), ("press", "咨询新闻", 16),
    ("control", "中央大厅", 25),
    ("clawd", "Claude", 20), ("pi", "Pi", 20), ("codex", "Codex", 20),
]


def check(pid, target):
    p = os.path.join(OUT, pid + ".glb")
    if not os.path.exists(p):
        return None
    d = open(p, "rb").read()
    n = struct.unpack("<I", d[12:16])[0]
    js = json.loads(d[20:20 + n])
    nodes = js["nodes"]
    prims = [pr for m in js["meshes"] for pr in m["primitives"]]
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
                lo[k] = min(lo[k], mn[k] * sc[k] + tr[k]); hi[k] = max(hi[k], mx[k] * sc[k] + tr[k])
    size = (round(hi[0] - lo[0], 1), round(hi[2] - lo[2], 1))
    mats = [m.get("name", "") for m in js["materials"]]
    names = [x.get("name", "") for x in nodes]
    color = sum(1 for pr in prims if "COLOR_0" in pr.get("attributes", {}))
    return dict(
        size=size, ok=abs(size[0] - target) < 1.0 and abs(size[1] - target) < 1.0,
        nodes=len(nodes), tris=sum(js["accessors"][pr["indices"]]["count"] // 3
                                  for m in js["meshes"] for pr in m["primitives"] if "indices" in pr),
        color=f"{color}/{len(prims)}",
        lamps=len([m for m in mats if m.startswith("LGT_")]) or len([x for x in names if x.startswith("LGT_") and not x.endswith("_light") and "_body" not in x and "_shade" not in x]),
        mb=round(os.path.getsize(p) / 1048576, 1),
        mtime=os.path.getmtime(p),
    )


def main():
    import time
    print("【园区模型成果】")
    done = []
    for pid, name, target in PLOTS:
        r = check(pid, target)
        if not r:
            print(f"  · {name}：未完成")
            continue
        flag = "✅" if r["ok"] else "⚠️尺寸不符"
        print(f"  {flag} {name}（{r['size'][0]}×{r['size'][1]} m）"
              f"{r['nodes']} 节点 / {r['tris']:,} 面 / 灯 {r['lamps']} 盏 / {r['mb']} MB")
        if r["ok"]:
            done.append(name)
    print(f"\n共 {len(done)}/{len(PLOTS)} 块合格")


if __name__ == "__main__":
    main()
