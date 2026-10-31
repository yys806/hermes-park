"""检测 glb 是否左右镜像对称（沿 X 轴）与中心对称（绕 Y 轴转 180 度）。
做法：把所有顶点按 1cm 网格量化，镜像后统计有多少顶点能在原集合里找到对应点。
用法：python check_symmetry.py out/models/codex.glb
"""
import json, struct, sys, os, collections

GRID = 0.01


def load_positions(path):
    d = open(path, "rb").read()
    off = 12
    js = None
    bin_chunk = None
    while off < len(d):
        clen, ctype = struct.unpack("<II", d[off:off + 8])
        body = d[off + 8: off + 8 + clen]
        if ctype == 0x4E4F534A:
            js = json.loads(body)
        elif ctype == 0x004E4942:
            bin_chunk = body
        off += 8 + clen
    pos = []
    for mesh in js["meshes"]:
        for pr in mesh["primitives"]:
            ai = pr["attributes"].get("POSITION")
            if ai is None:
                continue
            acc = js["accessors"][ai]
            bv = js["bufferViews"][acc["bufferView"]]
            start = bv.get("byteOffset", 0) + acc.get("byteOffset", 0)
            count = acc["count"]
            stride = bv.get("byteStride") or 12
            for i in range(count):
                o = start + i * stride
                x, y, z = struct.unpack("<fff", bin_chunk[o:o + 12])
                pos.append((x, y, z))
    return pos


def key(p):
    return (round(p[0] / GRID), round(p[1] / GRID), round(p[2] / GRID))


def symmetry_ratio(pos, mapping):
    s = set(key(p) for p in pos)
    hit = 0
    for p in pos:
        if key(mapping(p)) in s:
            hit += 1
    return hit / max(len(pos), 1)


def main(path):
    pos = load_positions(path)
    n = len(pos)
    bx = sum(p[0] for p in pos) / n
    by = sum(p[1] for p in pos) / n
    bz = sum(p[2] for p in pos) / n
    xs = [p[0] for p in pos]
    print(f"文件 {os.path.basename(path)}  顶点 {n:,}")
    print(f"质心 ({bx:.3f}, {by:.3f}, {bz:.3f})  X 范围 {min(xs):.2f} ~ {max(xs):.2f}")
    sx = symmetry_ratio(pos, lambda p: (-p[0], p[1], p[2]))
    sy = symmetry_ratio(pos, lambda p: (p[0], p[1], -p[2]))
    s180 = symmetry_ratio(pos, lambda p: (-p[0], p[1], -p[2]))
    print(f"左右镜像(X轴)一致率 {sx*100:.1f}%")
    print(f"前后镜像(Z轴)一致率 {sy*100:.1f}%")
    print(f"绕竖轴转180度一致率 {s180*100:.1f}%")
    ok = sx > 0.85 and s180 > 0.85
    print("判定:", "✅ 双对称成立" if ok else "❌ 不满足双对称（要求左右≥85%、转180度≥85%）")


if __name__ == "__main__":
    main(sys.argv[1])
