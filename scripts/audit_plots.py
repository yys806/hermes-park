"""地块细节审计：不只看文件大小，看"零件密度"。
统计每块的网格数、小件数（窗框/门把/栏杆/瓦垄/抽屉等命名词根）、
玻璃透明材质数、灯数，判断是不是"装出来的"。
"""
import json, os, struct, sys, collections

OUT = r"D:/hermes/home/out/models"
PLOTS = ["learn", "daily", "family", "vault", "clock", "press",
         "inventor", "rainbow", "clawd", "pi", "codex", "control"]
PARTS = ("frame", "trim", "handle", "rail", "slat", "tile", "panel", "hinge",
         "glass", "window", "door", "eave", "ridge", "stud", "bolt", "bracket",
         "shelf", "drawer", "seat", "leg", "step", "post", "beam", "rib", "band")


def audit(name):
    p = os.path.join(OUT, name + ".glb")
    if not os.path.exists(p):
        return None
    d = open(p, "rb").read()
    n = struct.unpack("<I", d[12:16])[0]
    js = json.loads(d[20:20 + n])
    names = [x.get("name", "") for x in js["nodes"]]
    mesh_objs = [x.get("name", "") for x in js["nodes"] if "mesh" in x]
    mats = js.get("materials", [])
    tris = sum(js["accessors"][pr["indices"]]["count"] // 3
               for m in js["meshes"] for pr in m["primitives"] if "indices" in pr)
    part_hits = sum(1 for x in mesh_objs if any(k in x.lower() for k in PARTS))
    glass = [m.get("name", "") for m in mats
             if m.get("alphaMode") == "BLEND" or "glass" in m.get("name", "").lower()]
    return dict(
        mb=round(os.path.getsize(p) / 1048576, 1),
        tris=tris,
        meshes=len(mesh_objs),
        parts=part_hits,
        part_ratio=round(part_hits / max(len(mesh_objs), 1), 2),
        mats=len(mats),
        glass=len(glass),
        lamps=len([x for x in names if x.startswith("LGT_")]),
        images=len(js.get("images", [])),
    )


rows = []
for p in PLOTS:
    a = audit(p)
    if a:
        rows.append((p, a))

print(f"{'地块':10s} {'MB':>6s} {'面数':>10s} {'网格':>5s} {'零件':>5s} {'占比':>5s} {'材质':>4s} {'玻璃':>4s} {'灯':>3s}")
for p, a in rows:
    print(f"{p:10s} {a['mb']:6.1f} {a['tris']:10,} {a['meshes']:5d} {a['parts']:5d} "
          f"{a['part_ratio']:5.2f} {a['mats']:4d} {a['glass']:4d} {a['lamps']:3d}")

print("\n判定口径：MB≥12、面数≥40万、网格≥150、零件占比≥0.25、玻璃≥1（大建筑地块）")
for p, a in rows:
    ok = a["mb"] >= 12 and a["tris"] >= 400000 and a["meshes"] >= 150
    print(f"  {p:10s} {'合格' if ok else '不达标'}", end="")
    if a["part_ratio"] < 0.25:
        print("  ← 零件太少（缺窗框/栏杆/瓦垄这类小件）", end="")
    if a["glass"] == 0 and p in ("learn", "family", "vault", "control"):
        print("  ← 没有透明玻璃", end="")
    print()
