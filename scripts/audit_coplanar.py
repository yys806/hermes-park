"""共面闪烁检测：找出可能 z-fighting 的贴面件。

原理：两个不同材质的网格，若在某一轴上极值面几乎重合（<TOL），且另外两轴的投影有足够重叠，
渲染时这两张面会争夺同一深度 → 拖动视角时逐帧翻转（闪烁）。

用法：python audit_coplanar.py [glb1 glb2 ...]     不给参数则扫描全部地块
"""
import glob
import json
import os
import struct
import sys

TOL = 0.004          # 4 毫米内视为共面
OVERLAP = 0.5        # 另两轴投影重叠超过 50%
OUT = r"D:/hermes/home/out/models"


def load(path):
    d = open(path, "rb").read()
    off, js, binc = 12, None, None
    while off < len(d):
        clen, ctype = struct.unpack("<II", d[off:off + 8])
        body = d[off + 8: off + 8 + clen]
        if ctype == 0x4E4F534A:
            js = json.loads(body)
        elif ctype == 0x004E4942:
            binc = body
        off += 8 + clen
    boxes = []
    for nd in js["nodes"]:
        if "mesh" not in nd:
            continue
        name = nd.get("name", "?")
        tr = nd.get("translation", [0, 0, 0])
        mats = set()
        lo = [1e18] * 3
        hi = [-1e18] * 3
        for pr in js["meshes"][nd["mesh"]]["primitives"]:
            acc = js["accessors"][pr["attributes"]["POSITION"]]
            if not acc.get("min"):
                continue
            for k in range(3):
                lo[k] = min(lo[k], acc["min"][k] + tr[k])
                hi[k] = max(hi[k], acc["max"][k] + tr[k])
            mi = pr.get("material")
            if mi is not None and mi < len(js["materials"]):
                mats.add(js["materials"][mi].get("name", str(mi)))
        if hi[0] < 1e17:
            boxes.append((name, lo, hi, tuple(sorted(mats)) or ("<none>",)))
    return boxes


def scan(path):
    boxes = load(path)
    hits = []
    for i in range(len(boxes)):
        n1, lo1, hi1, m1 = boxes[i]
        for j in range(i + 1, len(boxes)):
            n2, lo2, hi2, m2 = boxes[j]
            if m1 == m2:
                continue          # 同材质会合并，内部不 z-fight
            for axis in range(3):
                a, b = (0, 1) if axis == 2 else ((1, 2) if axis == 0 else (0, 2))
                ov_a = min(hi1[a], hi2[a]) - max(lo1[a], lo2[a])
                ov_b = min(hi1[b], hi2[b]) - max(lo1[b], lo2[b])
                if ov_a <= 0 or ov_b <= 0:
                    continue
                span_a = max(hi1[a], hi2[a]) - min(lo1[a], lo2[a])
                span_b = max(hi1[b], hi2[b]) - min(lo1[b], lo2[b])
                if span_a <= 0 or span_b <= 0:
                    continue
                if ov_a / span_a < OVERLAP or ov_b / span_b < OVERLAP:
                    continue
                for side, v1, v2 in (("max", hi1[axis], hi2[axis]), ("min", lo1[axis], lo2[axis])):
                    if abs(v1 - v2) < TOL:
                        hits.append((n1, n2, "xyz"[axis] + side, round(abs(v1 - v2) * 1000, 1)))
    return buckets(hits)


def buckets(hits):
    agg = {}
    for a, b, face, d in hits:
        key = (a, b)
        if key not in agg or d < agg[key][1]:
            agg[key] = (face, d)
    return sorted(((k[0], k[1], v[0], v[1]) for k, v in agg.items()), key=lambda x: x[3])


def main():
    targets = sys.argv[1:] or sorted(glob.glob(os.path.join(OUT, "*.glb")))
    for t in targets:
        name = os.path.basename(t)
        if name.startswith("_"):
            continue
        res = scan(t)
        print(f"=== {name}  共面嫌疑 {len(res)} 对")
        for a, b, face, d in res[:8]:
            print(f"    {a[:38]:38s} x {b[:38]:38s} {face:5s} 差 {d} mm")
        if len(res) > 8:
            print(f"    … 另有 {len(res)-8} 对")


if __name__ == "__main__":
    main()
