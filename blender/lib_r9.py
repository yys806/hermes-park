"""第 9 轮：楼阁式八角佛塔构件（八棱柱、出檐裙、平座栏杆、塔刹）。依赖 lib_building / lib_r6。"""
import bpy, bmesh, math
from mathutils import Vector
from lib_building import box, cyl, sphere, new_obj
from lib_r6 import _tube, rail_run, tent_roof2

A0 = math.pi / 8   # 角点起始角：让八边形的平面正对 ±X / ±Y


def corners(cx, cy, r, z=0.0, n=8, a0=A0):
    return [Vector((cx + r * math.cos(a0 + 2 * math.pi * i / n), cy + r * math.sin(a0 + 2 * math.pi * i / n), z)) for i in range(n)]


def oct_prism(nm, cx, cy, r, z0, h, m, bevel=0.03, n=8):
    """正八棱柱（r 为外接圆半径），平面朝向轴向，底面 z0。"""
    o = new_obj(nm)
    bm = bmesh.new()
    lo = [bm.verts.new(p) for p in corners(cx, cy, r, z0, n)]
    hi = [bm.verts.new(p) for p in corners(cx, cy, r, z0 + h, n)]
    bm.faces.new(lo[::-1]); bm.faces.new(hi)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((lo[i], lo[j], hi[j], hi[i]))
    bm.to_mesh(o.data); bm.free()
    o.data.materials.append(m)
    if bevel > 0:
        bv = o.modifiers.new('Bevel', 'BEVEL'); bv.width, bv.segments, bv.limit_method = bevel, 2, 'ANGLE'
    wn = o.modifiers.new('WeightedNormal', 'WEIGHTED_NORMAL'); wn.keep_sharp = True
    return o


def face_frame(cx, cy, r, k, out=0.0):
    """第 k 个平面（法线角 k·45°）的中心点与朝向角。"""
    th = k * math.pi / 4
    a = r * math.cos(math.pi / 8) + out
    return Vector((cx + a * math.cos(th), cy + a * math.sin(th))), th


def eave_skirt(nm, cx, cy, z_out, r_out, r_in, rise, M, flare=0.28, push=0.22, step=0.32,
               amp=0.045, nu_per=3, nv=6, t=0.08):
    """八角出檐裙：内缘插进塔身，外缘出檐、角部起翘外伸；坡面起瓦垄，角脊弧管 + 檐口管。"""
    C = Vector((cx, cy, 0))
    co, ci = corners(cx, cy, r_out), corners(cx, cy, r_in)
    side = (co[1] - co[0]).length
    nu = max(8, int(side / step * nu_per))

    def surf(i, u, v, bump=True):
        j = (i + 1) % 8
        E, I = co[i].lerp(co[j], u), ci[i].lerp(ci[j], u)
        f = abs(2 * u - 1) ** 4 * (1 - v) ** 2
        P = E.lerp(I, v) + (E - C).normalized() * push * f
        p = Vector((P.x, P.y, z_out + rise * v ** 1.5 + flare * f))
        if bump:
            w = side * (1 - v) + (ci[1] - ci[0]).length * v
            x = (u - 0.5) * w
            k = (0.5 + 0.5 * math.cos(2 * math.pi * x / step)) ** 1.5 * (1 - abs(2 * u - 1) ** 8)
            p.z += amp * k
        return p

    bm = bmesh.new()
    for i in range(8):
        g = [[bm.verts.new(surf(i, iu / nu, iv / nv)) for iu in range(nu + 1)] for iv in range(nv + 1)]
        for iv in range(nv):
            for iu in range(nu):
                bm.faces.new((g[iv][iu], g[iv][iu + 1], g[iv + 1][iu + 1], g[iv + 1][iu]))
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.004)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    o = new_obj(nm + '_tiles'); bm.to_mesh(o.data); bm.free()
    if o.data.polygons[0].normal.z < 0:
        for p in o.data.polygons: p.flip()
    o.data.polygons.foreach_set('use_smooth', [True] * len(o.data.polygons))
    o.data.materials.append(M['tile'])
    so = o.modifiers.new('Solidify', 'SOLIDIFY'); so.thickness, so.offset = t, -1
    out = [o]
    for i in range(8):   # 角脊：沿角线，末端翘出
        pts = [surf(i, 0, iv / nv, False) + Vector((0, 0, 0.08)) for iv in range(nv, -1, -1)]
        tip = pts[-1] + (pts[-1] - pts[-2]).normalized() * 0.22 + Vector((0, 0, 0.14))
        out.append(_tube(f'{nm}_hip{i}', pts + [tip], 0.07, M['ridge']))
    ev = [surf(i, iu / nu, 0, False) + Vector((0, 0, -0.02)) for i in range(8) for iu in range(0, nu, 2)]
    out.append(_tube(nm + '_eave', ev + [ev[0]], 0.06, M['ridge']))
    return out


def storey_body(nm, cx, cy, r, z0, h, M, ground=False):
    """一层塔身：石腰线 + 红墙八棱柱 + 角柱 + 额枋 + 斗拱带；四正面开门/隔扇，四斜面开窗。"""
    out = [oct_prism(nm + '_wall', cx, cy, r, z0, h, M['brick'], 0.02),
           oct_prism(nm + '_band', cx, cy, r + 0.07, z0, 0.16, M['stone'], 0.02),
           oct_prism(nm + '_lintel', cx, cy, r + 0.05, z0 + h - 0.24, 0.2, M['wood'], 0.02),
           oct_prism(nm + '_bracket', cx, cy, r + 0.15, z0 + h - 0.06, 0.12, M['win'], 0.02)]
    for i, p in enumerate(corners(cx, cy, r + 0.02)):
        out.append(cyl(f'{nm}_col{i}', 0.075, h - 0.2, (p.x, p.y, z0 + 0.16 + (h - 0.2) / 2), material=M['wood'], verts=8, bevel=0))
    fw = 2 * r * math.sin(math.pi / 8)
    for k in range(8):
        c, th = face_frame(cx, cy, r, k, 0.02)
        rz = th + math.pi / 2
        if k % 2 == 0:
            dw, dh = fw * (0.58 if ground else 0.5), h * (0.66 if ground else 0.62)
            zc = z0 + 0.16 + dh / 2
            out.append(box(f'{nm}_doorFrame{k}', (dw + 0.14, 0.06, dh + 0.1), (c.x, c.y, zc + 0.03), (0, 0, rz), M['wood'], bevel=0.015))
            out.append(box(f'{nm}_door{k}', (dw, 0.08, dh), (c.x, c.y, zc), (0, 0, rz), M['door' if ground else 'win'], bevel=0.01))
            if not ground:
                c2, _ = face_frame(cx, cy, r, k, 0.065)
                out.append(box(f'{nm}_mull{k}', (0.05, 0.03, dh * 0.9), (c2.x, c2.y, zc), (0, 0, rz), M['wood'], bevel=0))
        else:
            s = fw * 0.42
            zc = z0 + h * 0.55
            out.append(box(f'{nm}_winFrame{k}', (s + 0.12, 0.06, s + 0.12), (c.x, c.y, zc), (0, 0, rz), M['wood'], bevel=0.015))
            out.append(box(f'{nm}_win{k}', (s, 0.08, s), (c.x, c.y, zc), (0, 0, rz), M['win'], bevel=0.01))
    return out


def pingzuo(nm, cx, cy, r, z_top, M, t=0.34, rail_h=0.5):
    """平座：塔身外一圈木平台（下沿插进下层檐），沿八边围栏杆。"""
    out = [oct_prism(nm + '_deck', cx, cy, r, z_top - t, t, M['wood'], 0.02)]
    cs = corners(cx, cy, r - 0.08)
    for i in range(8):
        a, b = cs[i], cs[(i + 1) % 8]
        out += rail_run(f'{nm}_rail{i}', (a.x, a.y), (b.x, b.y), z_top, M, h=rail_h, step=0.26)
    for i, p in enumerate(cs):
        out.append(box(f'{nm}_post{i}', (0.12, 0.12, rail_h + 0.12), (p.x, p.y, z_top + (rail_h + 0.12) / 2), material=M['wood'], bevel=0.015))
    return out


def spire(nm, cx, cy, z, M, gold):
    """塔刹：刹座（八角须弥座 + 仰莲）+ 刹杆 + 七重相轮 + 宝盖 + 宝珠。"""
    out = [oct_prism(nm + '_seat', cx, cy, 0.42, z - 0.05, 0.22, M['ridge'], 0.03),
           oct_prism(nm + '_seat2', cx, cy, 0.34, z + 0.17, 0.14, M['ridge'], 0.03)]
    lotus = sphere(nm + '_lotus', 0.34, (cx, cy, z + 0.4), gold, 16, 8)
    lotus.scale = (1, 1, 0.55); out.append(lotus)
    out.append(cyl(nm + '_mast', 0.045, 1.9, (cx, cy, z + 1.35), material=gold, verts=10, bevel=0))
    for i in range(7):
        rr = 0.27 - i * 0.022
        out.append(cyl(f'{nm}_ring{i}', rr, 0.07, (cx, cy, z + 0.68 + i * 0.17), material=gold, verts=16, bevel=0.015))
    cap = cyl(nm + '_canopy', 0.3, 0.06, (cx, cy, z + 1.92), material=gold, verts=16, bevel=0.02)
    out.append(cap)
    out.append(sphere(nm + '_pearlA', 0.13, (cx, cy, z + 2.1), gold, 14, 8))
    out.append(sphere(nm + '_pearlB', 0.09, (cx, cy, z + 2.32), gold, 12, 8))
    return out
