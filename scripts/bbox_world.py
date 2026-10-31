"""正确计算 glb 的世界包围盒：走完整父子层级，支持 matrix 与 TRS。
用法：python bbox_world.py a.glb [b.glb ...]
"""
import json
import struct
import sys
import os


def mul(a, b):
    return [sum(a[i * 4 + k] * b[k * 4 + j] for k in range(4))
            for i in range(4) for j in range(4)]


def local_matrix(nd):
    if "matrix" in nd:
        m = nd["matrix"]  # 列主序
        return [m[0], m[4], m[8], m[12],
                m[1], m[5], m[9], m[13],
                m[2], m[6], m[10], m[14],
                m[3], m[7], m[11], m[15]]
    t = nd.get("translation", [0, 0, 0])
    r = nd.get("rotation", [0, 0, 0, 1])
    s = nd.get("scale", [1, 1, 1])
    x, y, z, w = r
    xx, yy, zz = x * x, y * y, z * z
    m = [
        (1 - 2 * (yy + zz)) * s[0], (2 * (x * y - z * w)) * s[0], (2 * (x * z + y * w)) * s[0], 0,
        (2 * (x * y + z * w)) * s[1], (1 - 2 * (xx + zz)) * s[1], (2 * (y * z - x * w)) * s[1], 0,
        (2 * (x * z - y * w)) * s[2], (2 * (y * z + x * w)) * s[2], (1 - 2 * (xx + yy)) * s[2], 0,
        t[0], t[1], t[2], 1,
    ]
    return m


def apply(m, p):
    return [m[0] * p[0] + m[4] * p[1] + m[8] * p[2] + m[12],
            m[1] * p[0] + m[5] * p[1] + m[9] * p[2] + m[13],
            m[2] * p[0] + m[6] * p[1] + m[10] * p[2] + m[14]]


def main(paths):
    for path in paths:
        d = open(path, "rb").read()
        off, js = 12, None
        while off < len(d):
            clen, ctype = struct.unpack("<II", d[off:off + 8])
            if ctype == 0x4E4F534A:
                js = json.loads(d[off + 8: off + 8 + clen])
            off += 8 + clen
        nodes = js["nodes"]
        lo = [1e18] * 3
        hi = [-1e18] * 3
        per = {}

        def walk(i, parent):
            nd = nodes[i]
            m = mul(parent, local_matrix(nd))
            if "mesh" in nd:
                nlo = [1e18] * 3
                nhi = [-1e18] * 3
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
                                    nlo[k] = min(nlo[k], w[k])
                                    nhi[k] = max(nhi[k], w[k])
                per[nd.get("name", "?")] = [round(nhi[k] - nlo[k], 2) for k in range(3)]
            for c in nd.get("children", []):
                walk(c, m)

        ident = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]
        for root in js["scenes"][js.get("scene", 0)]["nodes"]:
            walk(root, ident)
        print(f"{os.path.basename(path):14s} 世界包围盒 {[round(hi[k]-lo[k],1) for k in range(3)]}")
        big = sorted(per.items(), key=lambda kv: -(kv[1][0] * kv[1][2]))[:4]
        print("   最大件:", [(n, d) for n, d in big])


if __name__ == "__main__":
    main(sys.argv[1:])
