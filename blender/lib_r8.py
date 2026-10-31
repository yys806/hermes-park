"""第 8 轮：庄园外墙（墙段、扶壁墩、角楼、大门、后门）与卡通动物（猪、鸡）。依赖 lib_building / lib_house / lib_r6。"""
import bpy, math
from mathutils import Vector, Matrix
from lib_building import box, cyl, sphere, select_only, window_recess
from lib_house import gable_roof, gable_wall, lattice_window
from lib_r6 import tent_roof2

H, T = 6.0, 0.9            # 外墙高、厚（院墙是 4.5 / 0.5）


def estate_wall(nm, a, b, M, h=H, t=T, z0=0.0):
    """庄园外墙段（须沿 X 或 Y）：高石勒脚 + 红墙身 + 石腰线 + 压顶 + 带瓦垄的双坡墙帽。"""
    a, b = Vector((*a, 0)), Vector((*b, 0))
    L = (b - a).length
    c = (a + b) / 2
    ax = 'X' if abs(b.x - a.x) > abs(b.y - a.y) else 'Y'
    sz = lambda l, w, hh: (l, w, hh) if ax == 'X' else (w, l, hh)
    out = [box(nm + '_plinth', sz(L, t + 0.22, 1.0), (c.x, c.y, z0 + 0.5), material=M['stone'], bevel=0.04),
           box(nm, sz(L, t, h), (c.x, c.y, z0 + h / 2), material=M['brick'], bevel=0.03),
           box(nm + '_band', sz(L, t + 0.1, 0.14), (c.x, c.y, z0 + h - 0.75), material=M['stone'], bevel=0.02),
           box(nm + '_coping', sz(L, t + 0.16, 0.14), (c.x, c.y, z0 + h + 0.07), material=M['ridge'], bevel=0.02)]
    out += gable_roof(nm + '_cap', c.x, c.y, z0 + h + 0.14, L, t, 0.45, M, ax,
                      over=0.32, eave_over=0.0, t=0.1, rib_step=0.32)
    return out


def pier(nm, x, y, M, h=H, w=1.5, d=None, z0=0.0):
    """扶壁墩：比墙略宽略高，石脚、石帽、四坡小瓦顶。"""
    d = d or T + 0.5
    out = [box(nm + '_base', (w + 0.2, d + 0.2, 1.1), (x, y, z0 + 0.55), material=M['stone'], bevel=0.05),
           box(nm, (w, d, h + 0.9), (x, y, z0 + (h + 0.9) / 2), material=M['brick'], bevel=0.04),
           box(nm + '_cap', (w + 0.24, d + 0.24, 0.16), (x, y, z0 + h + 0.98), material=M['ridge'], bevel=0.03)]
    out += tent_roof2(nm + '_roof', x, y, z0 + h + 1.06, math.hypot(w, d) / 2 + 0.25, 0.55, M, sides=4,
                      rot0=math.atan2(d, w), step=0.28, amp=0.04, flare=0.08, push=0.06, rt=0.06, nu_per=3, nv=6, t=0.08)
    return out


def corner_tower(nm, x, y, M, sx, sy, s=3.2, h=H + 2.4):
    """转角角楼：方墩 + 外侧两面格窗 + 攒尖瓦顶。sx/sy 为朝外方向（±1）。"""
    body = box(nm, (s, s, h), (x, y, h / 2), material=M['brick'], bevel=0.04)
    out = [body, box(nm + '_base', (s + 0.3, s + 0.3, 1.2), (x, y, 0.6), material=M['stone'], bevel=0.05),
           box(nm + '_band', (s + 0.12, s + 0.12, 0.16), (x, y, h - 0.9), material=M['stone'], bevel=0.02),
           box(nm + '_cap', (s + 0.3, s + 0.3, 0.18), (x, y, h + 0.09), material=M['ridge'], bevel=0.03)]
    zc = h - 2.0
    for k, (dx, dy) in (('X', (sx, 0)), ('Y', (0, sy))):
        fx, fy = x + dx * (s / 2 + 0.01), y + dy * (s / 2 + 0.01)
        if k == 'X':
            out.append(box(f'{nm}_winBack{k}', (0.04, 1.0, 1.1), (fx, y, zc), material=M['plaque'], bevel=0))
            out += lattice_window(f'{nm}_win{k}', fx + dx * 0.03, y, zc, 1.0, 1.1, M, n=3, axis='Y')
        else:
            out.append(box(f'{nm}_winBack{k}', (1.0, 0.04, 1.1), (x, fy, zc), material=M['plaque'], bevel=0))
            out += lattice_window(f'{nm}_win{k}', x, fy + dy * 0.03, zc, 1.0, 1.1, M, n=3, axis='X')
    out += tent_roof2(nm + '_roof', x, y, h + 0.18, s * 0.707 + 0.9, 1.7, M, sides=4, rot0=math.pi / 4,
                      step=0.3, amp=0.05, flare=0.3, push=0.25, rt=0.12, nu_per=4, nv=10)
    return out


def _join(nm, objs, loc, rz):
    """把局部（朝 +X、脚底 z=0）搭好的部件合成一个对象，再摆到 loc、绕 Z 转 rz。"""
    from lib_building import apply_all_modifiers
    for o in objs:
        apply_all_modifiers(o)
    select_only(objs)
    bpy.ops.object.join()
    o = bpy.context.view_layer.objects.active
    o.name = o.data.name = nm
    o.data.transform(o.matrix_world)          # 原点归到局部 (0,0,0)，即脚底中心
    o.matrix_world = Matrix.Identity(4)
    o.data.polygons.foreach_set('use_smooth', [True] * len(o.data.polygons))
    o.location, o.rotation_euler = loc, (0, 0, rz)
    return o


def _ell(nm, c, r, m, sc=(1, 1, 1), rot=(0, 0, 0), seg=18, ring=10):
    """椭球部件：UV 球 + 非等比缩放 + 旋转。"""
    s = sphere(nm, r, c, m, seg, ring)
    s.scale, s.rotation_euler = sc, rot
    return s


def pig(nm, loc, rz, A, pose='stand'):
    """卡通猪（体长约 1.2 m）。pose: stand 站立 / eat 低头拱食 / lie 侧卧。A 为动物材质表。"""
    lie = pose == 'lie'
    zb = 0.32 if lie else 0.58               # 躯干中心高度
    P = [_ell(nm + '_body', (0, 0, zb), 0.42, A['pig'], (1.42, 1.08 if lie else 1.0, 0.78 if lie else 0.92))]
    hx, hz, tilt = 0.62, zb + 0.06, 0.0
    if pose == 'eat':
        hx, hz, tilt = 0.64, zb - 0.16, 0.5
    P.append(_ell(nm + '_head', (hx, 0, hz), 0.27, A['pig'], (1.0, 1.05, 0.95)))
    sx, sz = hx + 0.25 * math.cos(tilt), hz - 0.25 * math.sin(tilt) - 0.03
    P.append(cyl(nm + '_snout', 0.13, 0.12, (sx, 0, sz), (0, math.pi / 2 + tilt, 0), A['pigDark'], verts=18, bevel=0.03))
    for s in (1, -1):
        P.append(_ell(f'{nm}_nos{s}', (sx + 0.06 * math.cos(tilt), s * 0.045, sz - 0.06 * math.sin(tilt)), 0.025, A['eye'], (0.6, 1, 1.3), seg=8, ring=6))
        P.append(_ell(f'{nm}_eye{s}', (hx + 0.17, s * 0.13, hz + 0.09 - 0.1 * tilt), 0.035, A['eye'], seg=10, ring=6))
        P.append(_ell(f'{nm}_ear{s}', (hx - 0.05, s * 0.17, hz + 0.24 - 0.1 * tilt), 0.12, A['pigDark'],
                      (0.55, 0.9, 0.22), (s * 0.5, -0.9 - 0.4 * tilt, s * 0.3), seg=12, ring=6))
        for fx in (0.32, -0.32):             # 四条短腿 + 深色蹄；侧卧时只露前腿
            if lie:
                if fx > 0:
                    P.append(_ell(f'{nm}_legL{s}', (fx + 0.22, s * 0.2, 0.1), 0.1, A['pig'], (1.6, 0.8, 0.7)))
                continue
            P.append(cyl(f'{nm}_leg{s}{fx}', 0.085, 0.3, (fx, s * 0.2, 0.2), material=A['pig'], verts=12, bevel=0.03))
            P.append(cyl(f'{nm}_hoof{s}{fx}', 0.09, 0.07, (fx, s * 0.2, 0.035), material=A['pigDark'], verts=12, bevel=0.02))
    for i in range(7):                        # 卷尾：一串小球绕成螺旋
        t = i / 6 * 4.4
        P.append(_ell(f'{nm}_tail{i}', (-0.6 - 0.05 * math.cos(t) - i * 0.012, 0.06 * math.sin(t), zb + 0.12 + 0.05 * math.cos(t) + i * 0.012),
                      0.03, A['pig'], seg=8, ring=6))
    return _join(nm, P, loc, rz)


def chicken(nm, loc, rz, A, pose='stand', hen='hen'):
    """卡通鸡（高约 0.45 m）。pose: stand 站立 / peck 低头啄食 / sit 卧。hen 为羽色材质键。"""
    sit = pose == 'sit'
    zb = 0.17 if sit else 0.27
    body = A[hen]
    P = [_ell(nm + '_body', (0, 0, zb), 0.16, body, (1.25, 0.95, 0.95))]
    P.append(_ell(nm + '_tail', (-0.2, 0, zb + 0.1), 0.1, body, (0.5, 0.35, 1.0), (0, -0.5, 0), seg=12, ring=8))
    for s in (1, -1):
        P.append(_ell(f'{nm}_wing{s}', (-0.01, s * 0.14, zb + 0.01), 0.11, body, (1.25, 0.28, 0.7), (0, -0.2, 0), seg=12, ring=8))
    hx, hz, bt = (0.2, zb - 0.02, 1.2) if pose == 'peck' else (0.13, zb + 0.2, 0.0)
    P.append(_ell(nm + '_neck', ((hx + 0.04) / 2 + 0.02, 0, (hz + zb) / 2 + 0.02), 0.075, body, (0.9, 0.9, 1.3), (0, 0.5 + bt * 0.6, 0), seg=12, ring=8))
    P.append(_ell(nm + '_head', (hx, 0, hz), 0.075, body, seg=14, ring=8))
    a = bt * 0.8
    bx, bz = hx + 0.075 * math.cos(a), hz - 0.075 * math.sin(a)
    P.append(cyl(nm + '_beak', 0.028, 0.07, (bx + 0.02 * math.cos(a), 0, bz - 0.02 * math.sin(a)), (0, math.pi / 2 + a, 0), A['beak'], verts=10, bevel=0))
    for i in range(3):                        # 鸡冠三瓣 + 肉垂
        P.append(_ell(f'{nm}_comb{i}', (hx - 0.03 + i * 0.03 + 0.06 * math.sin(a), 0, hz + 0.07 - 0.02 * abs(i - 1) - 0.05 * math.sin(a)),
                      0.028, A['comb'], (1, 0.5, 1.2), seg=8, ring=6))
    P.append(_ell(nm + '_wattle', (bx - 0.01, 0, bz - 0.05), 0.022, A['comb'], (0.8, 0.6, 1.4), seg=8, ring=6))
    for s in (1, -1):
        P.append(_ell(f'{nm}_eye{s}', (hx + 0.035, s * 0.055, hz + 0.02), 0.014, A['eye'], seg=8, ring=6))
        if not sit:
            P.append(cyl(f'{nm}_leg{s}', 0.014, 0.16, (0.0, s * 0.06, 0.08), material=A['beak'], verts=6, bevel=0))
            for k in (-0.5, 0.0, 0.5):
                P.append(box(f'{nm}_toe{s}{k}', (0.07, 0.014, 0.012), (0.03 * math.cos(k), s * 0.06 + 0.03 * math.sin(k), 0.006), (0, 0, k), A['beak'], bevel=0))
    return _join(nm, P, loc, rz)
