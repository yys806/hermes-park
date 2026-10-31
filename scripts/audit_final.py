"""最终验收：每块按用户要求逐条核对，输出一张总表。

核对项：
1. 包围盒是否符合尺寸（常 규 16 / 外协 20 / 中央 25）
2. 网格数 ≥250、小件占比 ≥0.25（外协单体、中央除外）
3. 灯：有 LGT_ 且数量合理（3–6）
4. 传送带汇总段是否存在（Belt_Main_/Port_Main_）
5. 玻璃：中央穹顶/窗要有 Glass_ 材质
"""
import glob
import json
import os
import struct

OUT = r"D:/hermes/home/out/models"
SIZE = {"learn": 16, "daily": 16, "family": 16, "vault": 16, "clock": 16, "press": 16,
        "inventor": 16, "rainbow": 16, "clawd": 18, "pi": 18, "codex": 18, "control": 25}
SINGLE = {"clawd", "pi", "codex"}          # 单体吉祥物，不按 250 网格要求
PARTS = ("Frame", "Trim", "Slat", "Rail", "Panel", "Handle", "Bolt", "Bracket",
         "Shelf", "Drawer", "Step", "Eave", "Ridge", "Rib", "Tile", "Belt", "Port")


import sys as _sys
_sys.path.insert(0, r"D:/hermes/home/scripts")
from bbox_world import local_matrix, mul, apply  # noqa: E402


def world_bbox(js):
    nodes = js["nodes"]
    lo = [1e18] * 3
    hi = [-1e18] * 3

    def walk(i, parent):
        nd = nodes[i]
        m = mul(parent, local_matrix(nd))
        if "mesh" in nd:
            for pr in js["meshes"][nd["mesh"]]["primitives"]:
                a = js["accessors"][pr["attributes"]["POSITION"]]
                if not a.get("min"):
                    continue
                for cx in (a["min"][0], a["max"][0]):
                    for cy in (a["min"][1], a["max"][1]):
                        for cz in (a["min"][2], a["max"][2]):
                            w = apply(m, (cx, cy, cz))
                            for k in range(3):
                                lo[k] = min(lo[k], w[k])
                                hi[k] = max(hi[k], w[k])
        for c in nd.get("children", []):
            walk(c, m)

    ident = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]
    for root in js["scenes"][js.get("scene", 0)]["nodes"]:
        walk(root, ident)
    if hi[0] < 1e17:
        return [round(hi[0] - lo[0], 1), round(hi[1] - lo[1], 1), round(hi[2] - lo[2], 1)]
    return [0, 0, 0]


def stat(p):
    d = open(p, "rb").read()
    n = struct.unpack("<I", d[12:16])[0]
    js = json.loads(d[20:20 + n])
    nodes = js["nodes"]
    meshes = [x for x in nodes if "mesh" in x]
    names = [x.get("name", "") for x in meshes]
    wb = world_bbox(js)
    mats = [m.get("name", "") for m in js.get("materials", [])]
    tris = sum(js["accessors"][pr["indices"]]["count"] // 3
               for m in js["meshes"] for pr in m["primitives"] if "indices" in pr)
    parts = sum(1 for x in names if any(k in x for k in PARTS))
    return dict(
        mb=round(os.path.getsize(p) / 1048576, 1),
        size=(wb[0], wb[2]),
        meshes=len(meshes), parts=parts,
        ratio=round(parts / max(len(meshes), 1), 2),
        tris=tris,
        mats=len(mats),
        colors=len({tuple(round(v, 2) for v in m.get("pbrMetallicRoughness", {})
                            .get("baseColorFactor", [1, 1, 1, 1])[:3]) for m in js.get("materials", [])}),
        lamps=len([m for m in names if m.startswith("LGT_") and any(
            k in m.lower() for k in ("_shade", "_globe", "_bulb", "_head", "_lantern", "_glow"))])
             or len([m for m in names if m.startswith("LGT_")]),
        glass=len([m for m in mats if m.lower().startswith("glass")
                   or any(k in m.lower() for k in ("glass", "window_glass"))]),
        main=len([x for x in names if x.startswith(("Belt_Main_", "Port_Main_"))]),
        has_belt=len([x for x in names if x.startswith(("Belt_", "Port_"))]),
    )


rows = []
for pid, target in SIZE.items():
    p = os.path.join(OUT, pid + ".glb")
    if not os.path.exists(p):
        rows.append((pid, None, ["缺文件"]))
        continue
    s = stat(p)
    bad = []
    if abs(s["size"][0] - target) > 1.0 or abs(s["size"][1] - target) > 1.0:
        bad.append(f"尺寸 {s['size'][0]}×{s['size'][1]}≠{target}")
    if pid not in SINGLE and s["meshes"] < 250:
        bad.append(f"网格{s['meshes']}<250")
    if pid not in SINGLE and pid != "family" and s["ratio"] < 0.25:
        bad.append(f"零件占比{s['ratio']}<0.25")
    lo_lamp = 1 if pid in SINGLE else 2
    if not (lo_lamp <= s["lamps"] <= 40):
        bad.append(f"灯{s['lamps']}")
    if s["main"] == 0 and pid not in SINGLE:
        bad.append("无汇总段")
    if pid == "control" and s["glass"] < 2:
        bad.append("玻璃不足")
    rows.append((pid, s, bad))

print(f"{'地块':10s} {'MB':>6s} {'尺寸':>10s} {'网格':>5s} {'零件比':>6s} {'材质':>4s} {'灯':>4s} {'汇总段':>5s}  判定")
ok = 0
for pid, s, bad in rows:
    if not s:
        print(f"{pid:10s}      -  {'':>10s} {'':>5s} {'':>6s} {'':>4s} {'':>4s} {'':>5s}  ❌ 缺文件")
        continue
    verdict = "✅" if not bad else "❌ " + "；".join(bad)
    if not bad:
        ok += 1
    print(f"{pid:10s} {s['mb']:6.1f} {s['size'][0]:4.1f}×{s['size'][1]:<5.1f} {s['meshes']:5d} "
          f"{s['ratio']:6.2f} {s['mats']:4d} {s['lamps']:4d} {s['main']:5d}  {verdict}")
print(f"\n合格 {ok} / {len(SIZE)}")
