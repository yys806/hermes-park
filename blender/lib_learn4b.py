"""第4轮：图书馆 / 实验室 细节重建（原位、原尺寸、原父级）。Blender 4.5"""
import bpy, math, random
from mathutils import Vector, Matrix
import lib_building as lb
import lib_learn2 as L
import lib_learn4 as L4

R, CY, BL = L.rbox, L.rcyl, L.ball

def P():
    return bpy.app.driver_namespace['L2P']

def cut(o, size, loc):
    k = lb.box('cut', size, loc, bevel=0)
    lb.boolean_cut(o, k)

def outer_bevel(o, w=0.12):
    bpy.app.driver_namespace['outer_bevel'](o, w)

def clear_children(empty_name, keep_prefix=()):
    e = bpy.data.objects[empty_name]
    for c in list(e.children):
        if not c.name.startswith(keep_prefix):
            bpy.data.objects.remove(c, do_unlink=True)
    return e

def finish(parts, empty_name, prefix):
    e = bpy.data.objects[empty_name]
    keep = [o for o in parts if o.name.startswith('Foliage_')]
    rest = [o for o in parts if o not in keep]
    merged = lb.join_by_material(rest)
    for m in merged:
        m.name = m.data.name = prefix + '_' + m.name[2:].replace('L2_', '')
    L.parent(merged + keep, e)
    return merged

def append_merge(parts, empty_name, prefix):
    """新零件按材质合并后并入父级下同材质的已有对象（没有就新建 prefix_<mat>）。"""
    e = bpy.data.objects[empty_name]
    keep = [o for o in parts if o.name.startswith('Foliage_')]
    merged = lb.join_by_material([o for o in parts if o not in keep])
    out = []
    for m in merged:
        nm = prefix + '_' + m.name[2:].replace('L2_', '')
        old = next((c for c in e.children if c.name == nm), None)
        if old and not old.modifiers:
            lb.select_only([old, m]); bpy.ops.object.join(); out.append(old)
        elif old:   # 旧对象带修改器（如黏土细分/置换），不合并，另存为 _detail
            m.name = m.data.name = nm + '_detail'; L.parent([m], e); out.append(m)
        else:
            m.name = m.data.name = nm; L.parent([m], e); out.append(m)
    L.parent(keep, e)
    return out

def belt_detail(nm, p0, p1, w, top=0.42, leg_gap=1.4, drum0=False, drum1=False):
    """直线带段细节：侧面滚筒轴端盖、挡边支架、腿间横撑、端部滚筒。和 lib_learn2.belt_seg 同参数对齐。"""
    p = P(); G = L.G
    a, b = Vector((*p0, 0)), Vector((*p1, 0)); d = b - a; Ln = d.length; u = d / Ln
    n = Vector((-u.y, u.x, 0)); rz = math.atan2(u.y, u.x)
    out = []
    k = max(2, int(Ln / 0.35))
    for i in range(k):   # 轴端盖
        q = a + d * ((i + 0.5) / k)
        for s in (-1, 1):
            c = q + n * s * (w / 2 + 0.005)
            out.append(CY(nm + '_axle', 0.028, 0.02, (c.x, c.y, top - 0.08), p['bolt'], r=0.006, verts=10, rot=(math.pi / 2, 0, rz)))
    k = max(2, int(Ln / 0.7) + 1)
    for i in range(k):   # 挡边支架（把挡边扣到带床侧面）
        q = a + d * (0.06 + 0.88 * i / (k - 1))
        for s in (-1, 1):
            c = q + n * s * (w / 2 + 0.012)
            out.append(R(nm + '_rbrk', (0.05, 0.025, 0.2), (c.x, c.y, top - 0.02), p['rail'], r=0.008, rot=(0, 0, rz)))
            out.append(BL(nm + '_rbolt', 0.012, (c.x + n.x * s * 0.015, c.y + n.y * s * 0.015, top - 0.07), p['bolt']))
    nl = max(2, int(Ln / leg_gap) + 1)
    for i in range(nl):   # 腿间横撑 + 斜撑
        q = a + d * (0.08 + 0.84 * i / (nl - 1))
        hw = w / 2 - 0.1
        out.append(L4.tube(nm + '_brace', [q - n * hw + Vector((0, 0, G + 0.13)), q + n * hw + Vector((0, 0, G + 0.13))], [0.018, 0.018], p['leg'], 8))
        out.append(L4.tube(nm + '_diag', [q - n * hw + Vector((0, 0, G + 0.14)), q + n * hw + Vector((0, 0, top - 0.17))], [0.012, 0.012], p['leg'], 6))
    for flag, q, sgn in ((drum0, a, 1), (drum1, b, -1)):   # 端部滚筒 + 两侧轴承座
        if not flag: continue
        c = q + u * sgn * 0.02
        out.append(CY(nm + '_drum', 0.07, w - 0.08, (c.x, c.y, top - 0.05), p['belt'], r=0.015, verts=20, rot=(math.pi / 2, 0, rz)))
        for s in (-1, 1):
            e = c + n * s * (w / 2 + 0.02)
            out.append(R(nm + '_bear', (0.1, 0.05, 0.12), (e.x, e.y, top - 0.05), p['port'], r=0.02, rot=(0, 0, rz)))
    return out

def downpipe(nm, x, y, z_top, m, facing_y=-1):
    """雨水管：斗 + 竖管 + 3 个管卡 + 底部弯头。"""
    ps = [R(nm + '_hopper', (0.18, 0.16, 0.16), (x, y, z_top - 0.08), m, r=0.04),
          CY(nm + '_pipe', 0.045, z_top - 0.4, (x, y, 0.3 + (z_top - 0.4) / 2), m, r=0.0, verts=12)]
    for z in (1.0, 2.6, z_top - 0.6):
        ps.append(R(nm + '_clip', (0.13, 0.1, 0.05), (x, y - facing_y * 0.03, z), m, r=0.015))
    ps.append(L4.tube(nm + '_shoe', [(x, y, 0.36), (x, y, 0.22), (x, y + facing_y * 0.1, 0.14), (x, y + facing_y * 0.22, 0.13)],
                      [0.045, 0.045, 0.045, 0.05], m, 12))
    return ps

def flower_box(nm, x, y, z, w, rnd):
    p = P()
    ps = [R(nm + '_box', (w, 0.18, 0.15), (x, y, z + 0.075), p['orange'], r=0.04),
          R(nm + '_rim', (w + 0.04, 0.2, 0.03), (x, y, z + 0.15), p['wood2'], r=0.012)]
    fol = []
    for i in range(5):
        fx = x - w / 2 + 0.08 + i * (w - 0.16) / 4
        fol.append(BL(nm + '_lf', 0.07, (fx, y, z + 0.2), p['bush'], (1.2, 0.9, 0.8)))
        if i % 2 == 0:
            fol.append(BL(nm + '_fl', 0.035, (fx + 0.03, y - 0.06, z + 0.27), p[rnd.choice(['red', 'white', 'book3'])]))
    return ps, fol

def build_library():
    p = P(); rnd = random.Random(7)
    e = clear_children('Obj_Library')
    X0, X1, Y0, Y1 = -6.8, -2.4, 2.4, 6.4
    cx, cy, w, d = (X0 + X1) / 2, (Y0 + Y1) / 2, X1 - X0, Y1 - Y0
    B, F = [], []
    # 基座 + 基座线脚 + 墙角壁柱
    B.append(R('lib_plinth', (w + 0.3, d + 0.3, 0.26), (cx, cy, 0.13), p['trim'], r=0.08))
    B.append(R('lib_plinthcap', (w + 0.36, d + 0.36, 0.07), (cx, cy, 0.29), p['trim'], r=0.03))
    f1 = R('lib_f1', (w, d, 3.0), (cx, cy, 1.8), p['wall'], r=0.12)
    f2 = R('lib_f2', (w - 0.1, d - 0.1, 2.7), (cx, cy, 4.85), p['wall'], r=0.12)
    cut(f1, (1.9, 0.6, 2.2), (-5.65, Y0, 1.65)); cut(f1, (0.6, 1.8, 2.2), (X0, 3.7, 1.65))
    cut(f1, (1.05, 0.5, 2.25), (-4.0, Y0, 1.425))
    for x in (-5.6, -3.6):
        cut(f2, (0.95, 0.5, 1.05), (x, Y0 + 0.05, 4.725))
    cut(f2, (0.5, 0.95, 1.05), (X0 + 0.05, 4.4, 4.725))
    outer_bevel(f1); outer_bevel(f2); B += [f1, f2]
    for (px, py) in ((X0, Y0), (X1, Y0), (X0, Y1), (X1, Y1)):
        B.append(R('lib_pil1', (0.24, 0.24, 2.95), (px, py, 1.8), p['trim'], r=0.06))
        B.append(R('lib_pil2', (0.22, 0.22, 2.7), (px + (0.05 if px < cx else -0.05), py + (0.05 if py < cy else -0.05), 4.85), p['trim'], r=0.06))
        B.append(R('lib_pilcap', (0.3, 0.3, 0.08), (px, py, 3.25), p['trim'], r=0.03))
    # 腰线（两道）+ 檐口（两层叠涩）
    B.append(R('lib_band', (w + 0.25, d + 0.25, 0.22), (cx, cy, 3.4), p['trim'], r=0.08))
    B.append(R('lib_band2', (w + 0.12, d + 0.12, 0.06), (cx, cy, 3.22), p['trim'], r=0.025))
    B.append(R('lib_eave', (w + 0.2, d + 0.2, 0.16), (cx, cy, 6.28), p['trim'], r=0.06))
    B.append(R('lib_eave2', (w + 0.08, d + 0.08, 0.06), (cx, cy, 6.17), p['trim'], r=0.025))
    return e, B, F, (X0, X1, Y0, Y1, cx, cy, w, d), rnd

def _lib_shelves(B, X0, Y0):
    p = P(); rnd = random.Random(3)
    B.append(R('lib_shelfback', (1.85, 0.06, 2.15), (-5.65, Y0 + 0.27, 1.65), p['wood'], r=0.02))
    B.append(R('lib_shelfbackW', (0.06, 1.75, 2.15), (X0 + 0.27, 3.7, 1.65), p['wood'], r=0.02))
    for z in (0.75, 1.3, 1.85, 2.4):
        B.append(R('lib_shelf', (1.85, 0.22, 0.05), (-5.65, Y0 + 0.17, z), p['wood2'], r=0.015))
        B.append(R('lib_shelfW', (0.22, 1.7, 0.05), (X0 + 0.17, 3.7, z), p['wood2'], r=0.015))
        for (a0, a1, fy, axis) in ((-6.52, -4.8, Y0 + 0.18, 'x'), (2.88, 4.5, X0 + 0.18, 'y')):
            t = a0
            while t < a1:
                bw = rnd.uniform(0.06, 0.12); bh = rnd.uniform(0.28, 0.44); tilt = rnd.random() < 0.08
                loc = (t + bw / 2, fy, z + 0.025 + bh / 2) if axis == 'x' else (fy, t + bw / 2, z + 0.025 + bh / 2)
                sz = (bw, 0.16, bh) if axis == 'x' else (0.16, bw, bh)
                B.append(R('lib_book', sz, loc, p[rnd.choice(['book1', 'book2', 'book3', 'paper', 'mail'])], r=0.012, seg=1,
                           rot=((0, 0.18, 0) if tilt and axis == 'x' else (0, 0, 0))))
                t += bw + 0.01
    for dv in (0.75, 1.3, 1.85):
        B.append(R('lib_shelfdiv', (0.04, 0.2, 0.5), (-5.65, Y0 + 0.17, dv + 0.27), p['wood2'], r=0.01))

def _lib_front(B, F, X0, X1, Y0):
    p = P(); rnd = random.Random(5)
    curt = L4.mat('curtain', '#F6E7C8', sss=0.15)
    matm = L4.mat('doormat', '#8E6B4E')
    tint = L4.mat('win_tint', '#9CC6E2', bump=0, rough=0.45)
    B += L4.window('lib_shop', (-5.65, Y0 + 0.02, 1.65), 1.9, 2.2, 'S', cols=3, rows=2, frame_m=p['wood'], glass=p['glass'],
                   trim=p['trim'], depth=0.12)
    B += L4.window('lib_shopW', (X0 + 0.02, 3.7, 1.65), 1.8, 2.2, 'W', cols=2, rows=2, frame_m=p['wood'], glass=p['glass'],
                   trim=p['trim'], lintel=False, depth=0.12)
    B += L4.door('lib_door', (-4.0, Y0 + 0.12, 0.3), 0.95, 2.15, 'S', p['wood'], p['trim'], p['metal'],
                 leaves=1, glass=p['win'], panels=(2, 1))
    B += L4.steps('lib_steps', (-4.0, Y0 - 0.15, 0), 1.2, 3, 0.08, 0.26, 'S', p['trim'], cheek_m=p['stone'])
    B.append(R('lib_mat', (0.85, 0.4, 0.02), (-4.0, Y0 - 0.2, 0.31), matm, r=0.01))
    for yy in (Y0 - 0.85, Y0 - 0.35):   # 西侧扶手：两立柱 + 弯头扶手
        B.append(CY('lib_rp', 0.025, 0.85, (-4.68, yy, 0.36 + 0.42), p['lamppost'], r=0.01, verts=10))
    B.append(L4.tube('lib_rail', [(-4.68, Y0 - 0.9, 1.2), (-4.68, Y0 - 0.15, 1.2), (-4.68, Y0 - 0.08, 1.05)], [0.03] * 3, p['lamppost'], 10))
    for x in (-5.6, -3.6):
        B += L4.window('lib_w2_%d' % x, (x, Y0 + 0.07, 4.725), 0.95, 1.05, 'S', cols=2, rows=2, frame_m=p['trim'], glass=p['win'],
                       glass2=tint, trim=p['trim'], curtain=curt)
        ps, fl = flower_box('lib_fb', x, Y0 - 0.12, 4.08, 0.8, rnd); B += ps; F += fl
    B += L4.window('lib_w2W', (X0 + 0.07, 4.4, 4.725), 0.95, 1.05, 'W', cols=2, rows=2, frame_m=p['trim'], glass=p['win'],
                   glass2=tint, trim=p['trim'], curtain=curt)
    for x in (X0 + 0.22, X1 - 0.22):
        B += downpipe('lib_dp', x, Y0 - 0.12, 6.15, p['metal'])
    for z in (1.2, 4.6):
        B.append(R('lib_vent', (0.05, 0.4, 0.3), (X1 + 0.02, 5.4, z), p['metal'], r=0.02))
        for k in range(4):
            B.append(R('lib_ventfin', (0.04, 0.34, 0.03), (X1 + 0.05, 5.4, z - 0.1 + k * 0.065), p['pipe'], r=0.01))

def _lib_roof(B, X0, X1):
    p = P(); rnd = random.Random(9)
    cyr, run, rise, zb = 4.4, 2.4, 1.6, 6.42
    ang = math.atan2(rise, run); Ls = math.hypot(run, rise); L_x = X1 - X0 + 0.7; xc = (X0 + X1) / 2
    roof2 = L4.mat('roof_tile2', '#6F7A8A')
    for s in (-1, 1):
        M = Matrix.Translation((xc, cyr + s * run / 2, zb + rise / 2 + 0.06)) @ Matrix.Rotation(-s * ang, 4, 'X')
        slab = R('lib_roofslab', (L_x, Ls + 0.08, 0.12), (0, 0, 0), p['roof'], r=0.04)
        slab.matrix_basis = M @ slab.matrix_basis; B.append(slab)
        nx, ny = 10, 6
        for j in range(ny):
            for i in range(nx + 1):
                u = -Ls / 2 + Ls * (j + 0.5) / ny
                xx = -L_x / 2 + L_x * (i + 0.5 - (0.5 if j % 2 else 0)) / nx
                if xx < -L_x / 2 + 0.2 or xx > L_x / 2 - 0.2: continue
                t = R('lib_tile', (L_x / nx - 0.035, Ls / ny + 0.04, 0.06), (xx, u * s, 0.09 + 0.004 * j),
                      p['roof'] if rnd.random() > 0.25 else roof2, r=0.02, seg=2)
                t.matrix_basis = M @ Matrix.Rotation(0.05 * s, 4, 'X') @ t.matrix_basis; B.append(t)
        for xe in (-L_x / 2 - 0.02, L_x / 2 + 0.02):   # 封檐板
            bb = R('lib_barge', (0.08, Ls + 0.12, 0.24), (xe, 0, 0.04), p['trim'], r=0.03)
            bb.matrix_basis = M @ bb.matrix_basis; B.append(bb)
        ye = cyr + s * (run + 0.08)
        B.append(L4.tube('lib_gutter', [(xc - L_x / 2, ye, zb - 0.02), (xc + L_x / 2, ye, zb - 0.02)], [0.075, 0.075], p['metal'], 12))
        for xe in (xc - L_x / 2, xc + L_x / 2):
            B.append(CY('lib_gutcap', 0.08, 0.03, (xe, ye, zb - 0.02), p['metal'], r=0.01, rot=(0, math.pi / 2, 0)))
        B.append(R('lib_fascia', (L_x, 0.06, 0.16), (xc, cyr + s * (run + 0.01), zb + 0.04), p['trim'], r=0.02))
    for i in range(11):   # 分节屋脊
        xx = xc - L_x / 2 + 0.25 + i * (L_x - 0.5) / 10
        B.append(CY('lib_ridgeseg', 0.13, (L_x - 0.5) / 10 - 0.03, (xx, cyr, zb + rise + 0.12), p['roof'], r=0.04, rot=(0, math.pi / 2, 0)))
    for xe in (xc - L_x / 2 + 0.1, xc + L_x / 2 - 0.1):
        B.append(BL('lib_ridgeend', 0.15, (xe, cyr, zb + rise + 0.12), p['roof']))
    for x, sgn in ((X0 + 0.02, -1), (X1 - 0.02, 1)):   # 山墙 + 圆形百叶
        B.append(lb.panel('lib_gable', [(-2.0, 0), (2.0, 0), (0, 1.38)], 0.2, (x - 0.1, cyr, zb), (math.pi / 2, 0, math.pi / 2), p['wall'], bevel=0.05))
        B.append(CY('lib_gvring', 0.26, 0.06, (x + sgn * 0.11, cyr, zb + 0.6), p['trim'], r=0.02, rot=(0, math.pi / 2, 0)))
        B.append(CY('lib_gvin', 0.2, 0.04, (x + sgn * 0.11, cyr, zb + 0.6), p['port_in'], r=0.01, rot=(0, math.pi / 2, 0)))
        for k in range(4):
            B.append(R('lib_gvfin', (0.04, 0.36 - abs(k - 1.5) * 0.08, 0.035), (x + sgn * 0.14, cyr, zb + 0.48 + k * 0.08), p['trim'], r=0.01))

def _lib_sign(B, Y0):
    p = P(); sx, sz = -2.95, 1.6
    B.append(R('lib_sgback', (0.98, 0.05, 0.72), (sx, Y0 - 0.03, sz), p['wood2'], r=0.03))
    B.append(R('lib_sgframe', (1.04, 0.07, 0.78), (sx, Y0 - 0.06, sz), p['wood'], r=0.05))
    B.append(R('lib_sgface', (0.9, 0.04, 0.64), (sx, Y0 - 0.1, sz), p['book2'], r=0.03))
    for s in (-1, 1):
        B.append(R('lib_pgstack', (0.36, 0.05, 0.47), (sx + s * 0.19, Y0 - 0.13, sz - 0.01), p['trim'], r=0.03, rot=(0, 0, s * 0.18)))
        B.append(R('lib_page', (0.35, 0.03, 0.46), (sx + s * 0.19, Y0 - 0.16, sz), p['paper'], r=0.04, rot=(0, 0, s * 0.18)))
        for z in (0.13, 0.05, -0.03, -0.11):
            B.append(R('lib_txt', (0.22 if z != -0.11 else 0.14, 0.02, 0.022), (sx + s * 0.19, Y0 - 0.18, sz + z), p['book2'], r=0.008, rot=(0, 0, s * 0.18)))
        for zz in (0.33, -0.33):
            B.append(BL('lib_sgbolt', 0.02, (sx + s * 0.46, Y0 - 0.1, sz + zz), p['metal']))
    B.append(R('lib_spine', (0.05, 0.05, 0.5), (sx, Y0 - 0.17, sz), p['wood2'], r=0.02))
    B.append(R('lib_bookmark', (0.05, 0.02, 0.3), (sx + 0.08, Y0 - 0.19, sz - 0.33), p['red'], r=0.01))
    bx, by = -4.95, Y0 - 0.5   # 门边立式告示板
    for s in (-1, 1):
        B.append(R('lib_np_leg', (0.05, 0.05, 0.9), (bx + s * 0.22, by, 0.06 + 0.45), p['wood2'], r=0.015))
    B.append(R('lib_np_board', (0.55, 0.04, 0.42), (bx, by, 0.75), p['wood'], r=0.02))
    B.append(R('lib_np_paper', (0.2, 0.01, 0.26), (bx - 0.1, by - 0.025, 0.76), p['paper'], r=0.005, rot=(0, 0.08, 0)))
    B.append(R('lib_np_paper2', (0.16, 0.01, 0.2), (bx + 0.13, by - 0.025, 0.78), p['book3'], r=0.005, rot=(0, -0.1, 0)))
    B.append(R('lib_np_roof', (0.62, 0.12, 0.04), (bx, by, 0.99), p['wood2'], r=0.015))

def gas_tanks(B, pts, Y0):
    """气瓶组：瓶身 + 肩部圆顶 + 瓶颈 + 阀门 + 手轮 + 两道绑带 + 墙上托架。"""
    p = P()
    for k, (x, y) in enumerate(pts):
        m = p['orange'] if k == 0 else p['mail']
        B.append(CY('lab_tank', 0.16, 1.05, (x, y, 0.08 + 0.525), m, r=0.05, verts=24))
        B.append(BL('lab_tankdome', 0.16, (x, y, 1.13), m, (1, 1, 0.55)))
        B.append(CY('lab_tankneck', 0.05, 0.12, (x, y, 1.26), p['metal'], r=0.01, verts=12))
        B.append(R('lab_valve', (0.08, 0.08, 0.08), (x, y, 1.35), p['metal'], r=0.02))
        B.append(CY('lab_valvenz', 0.02, 0.1, (x + 0.07, y, 1.35), p['metal'], r=0.005, verts=8, rot=(0, math.pi / 2, 0)))
        B.append(L4.tube('lab_wheel', [(x + 0.07 * math.cos(a / 16 * math.tau), y + 0.07 * math.sin(a / 16 * math.tau), 1.43) for a in range(17)],
                         [0.012] * 17, p['red'], 6, cap=False))
        B.append(CY('lab_wheelhub', 0.015, 0.06, (x, y, 1.42), p['metal'], r=0.0, verts=8))
        B.append(CY('lab_tankfoot', 0.17, 0.05, (x, y, 0.085), p['metal'], r=0.015, verts=24))
    x0 = min(q[0] for q in pts) - 0.22; x1 = max(q[0] for q in pts) + 0.22; ym = sum(q[1] for q in pts) / len(pts)
    for z in (0.55, 0.95):
        B.append(L4.tube('lab_strap', [(x0, Y0, z), (x0, ym - 0.18, z), (x1, ym - 0.18, z), (x1, Y0, z)], [0.018] * 4, p['metal'], 6))
    for x in (x0, x1):
        B.append(R('lab_brk', (0.06, 0.05, 0.6), (x, Y0 - 0.02, 0.75), p['metal'], r=0.015))

def roof_vent(B, x, y, z, h, p, mush=False):
    """屋面通风管：方底座 + 法兰 + 立管 + 弯头/蘑菇帽。"""
    B.append(R('lab_vbase', (0.32, 0.32, 0.12), (x, y, z + 0.06), p['trim'], r=0.03))
    B.append(CY('lab_vflange', 0.13, 0.04, (x, y, z + 0.14), p['metal'], r=0.01, verts=20))
    if mush:
        B.append(CY('lab_vpipe', 0.08, h, (x, y, z + 0.14 + h / 2), p['pipe'], r=0.0, verts=16))
        for zz in (0.35, h - 0.2):
            B.append(CY('lab_vring', 0.095, 0.04, (x, y, z + 0.14 + zz), p['metal'], r=0.01, verts=16))
        B.append(CY('lab_vcapst', 0.02, 0.1, (x, y, z + 0.14 + h + 0.05), p['metal'], r=0.0, verts=8))
        B.append(BL('lab_vcap', 0.2, (x, y, z + 0.14 + h + 0.12), p['metal'], (1, 1, 0.35)))
    else:
        top = z + 0.14 + h
        B.append(L4.tube('lab_velbow', [(x, y, z + 0.14), (x, y, top - 0.12), (x, y - 0.04, top - 0.02), (x, y - 0.16, top + 0.01), (x, y - 0.24, top + 0.01)],
                         [0.07] * 5, p['pipe'], 14))
        B.append(CY('lab_vmouth', 0.085, 0.05, (x, y - 0.26, top + 0.01), p['metal'], r=0.01, verts=16, rot=(math.pi / 2, 0, 0)))

def build_lab():
    p = P(); e = clear_children('Obj_Lab')
    X0, X1, Y0, Y1, H = 2.3, 6.9, 2.4, 6.4, 4.6
    cx, cy, w, d = (X0 + X1) / 2, (Y0 + Y1) / 2, X1 - X0, Y1 - Y0
    warn = L4.mat('warn', '#F2C230'); tint = bpy.data.materials['L2_win_tint']
    B, F = [], []
    B.append(R('lab_plinth', (w + 0.3, d + 0.3, 0.26), (cx, cy, 0.13), p['trim'], r=0.08))
    B.append(R('lab_plinthcap', (w + 0.36, d + 0.36, 0.07), (cx, cy, 0.29), p['trim'], r=0.03))
    wall = R('lab_wall', (w, d, H - 0.3), (cx, cy, 0.3 + (H - 0.3) / 2), p['wall2'], r=0.12)
    WX = (2.85, 3.45, 5.75, 6.35)
    for x in WX:
        cut(wall, (0.46, 0.5, 2.3), (x, Y0, 2.25))
    for y in (3.3, 4.2, 5.4):
        cut(wall, (0.5, 0.6, 1.6), (X1, y, 2.25))
    cut(wall, (1.42, 0.5, 2.36), (4.6, Y0, 0.3 + 1.18))
    outer_bevel(wall); B.append(wall)
    for x in (X0, 4.0 - 0.1, 5.2 + 0.1, X1):   # 壁柱（角 + 门两侧）
        B.append(R('lab_pil', (0.22, 0.22, H - 0.3), (x, Y0, 0.3 + (H - 0.3) / 2), p['trim'], r=0.05))
    for (x, y) in ((X0, Y1), (X1, Y1)):
        B.append(R('lab_pil', (0.22, 0.22, H - 0.3), (x, y, 0.3 + (H - 0.3) / 2), p['trim'], r=0.05))
    B.append(R('lab_band', (w + 0.16, d + 0.16, 0.1), (cx, cy, 3.65), p['trim'], r=0.04))
    B.append(R('lab_cornice', (w + 0.24, d + 0.24, 0.14), (cx, cy, H - 0.02), p['trim'], r=0.05))
    # 女儿墙 + 压顶 + 屋面 + 排水口
    for (sx, sy, lx, ly) in ((cx, Y0 + 0.09, w, 0.18), (cx, Y1 - 0.09, w, 0.18), (X0 + 0.09, cy, 0.18, d), (X1 - 0.09, cy, 0.18, d)):
        B.append(R('lab_parapet', (lx, ly, 0.42), (sx, sy, H + 0.21), p['wall2'], r=0.04))
        B.append(R('lab_coping', (lx + (0.1 if lx > 1 else 0.26), ly + (0.1 if ly > 1 else 0.26) - (0.0), 0.07), (sx, sy, H + 0.455), p['trim'], r=0.025))
    B.append(R('lab_roofdeck', (w - 0.36, d - 0.36, 0.06), (cx, cy, H + 0.03), p['stone'], r=0.02))
    for x in (X0 + 0.25, X1 - 0.6):
        B.append(R('lab_scupper', (0.16, 0.3, 0.1), (x, Y0 - 0.02, H + 0.08), p['metal'], r=0.02))
    B += downpipe('lab_dp', X0 + 0.25, Y0 - 0.14, H + 0.05, p['metal'])
    for x in WX:
        B += L4.window('lab_win', (x, Y0 + 0.02, 2.25), 0.46, 2.3, 'S', cols=1, rows=3, frame_m=p['metal'], glass=p['win'],
                       glass2=tint, trim=p['trim'], depth=0.1)
    for y in (3.3, 4.2, 5.4):
        B += L4.window('lab_winE', (X1 - 0.02, y, 2.25), 0.5, 1.6, 'E', cols=1, rows=2, frame_m=p['metal'], glass=p['win'],
                       glass2=tint, trim=p['trim'], depth=0.1)
    B += L4.door('lab_door', (4.6, Y0 + 0.1, 0.3), 1.3, 2.3, 'S', p['door'], p['trim'], p['metal'], leaves=2, glass=p['win'], panels=(2, 1))
    B += L4.steps('lab_steps', (4.6, Y0 - 0.15, 0), 1.6, 3, 0.08, 0.26, 'S', p['trim'], cheek_m=p['stone'], rail_m=p['lamppost'])
    B.append(R('lab_mat', (1.1, 0.4, 0.02), (4.6, Y0 - 0.2, 0.31), bpy.data.materials['L2_doormat'], r=0.01))
    _lab_extras(B, X0, X1, Y0, Y1, H, cx, cy, warn)
    n = len(B) + len(F)
    return n, finish(B + F, 'Obj_Lab', 'Lab')

def _lab_extras(B, X0, X1, Y0, Y1, H, cx, cy, warn):
    p = P()
    # 雨棚：板 + 前缘封边 + 两根斜撑
    B.append(R('lab_canopy', (2.1, 0.8, 0.1), (4.6, Y0 - 0.38, 2.95), p['awn'], r=0.03))
    B.append(R('lab_canfascia', (2.14, 0.06, 0.16), (4.6, Y0 - 0.78, 2.94), p['metal'], r=0.02))
    for sx in (-0.85, 0.85):
        B.append(L4.tube('lab_canbr', [(4.6 + sx, Y0, 2.45), (4.6 + sx, Y0 - 0.4, 2.7), (4.6 + sx, Y0 - 0.7, 2.9)], [0.025] * 3, p['metal'], 8))
        B.append(R('lab_canplate', (0.1, 0.04, 0.16), (4.6 + sx, Y0 - 0.01, 2.45), p['metal'], r=0.01))
    # 门上名牌 + 门板黄色三角安全标识
    B.append(R('lab_nameboard', (1.3, 0.05, 0.3), (4.6, Y0 - 0.03, 3.3), p['white'], r=0.03))
    for k in range(5):
        B.append(R('lab_letter', (0.12, 0.02, 0.16), (4.6 - 0.36 + k * 0.18, Y0 - 0.065, 3.3), p['pipe'], r=0.01))
    for sx in (-0.33, 0.33):
        B.append(L.rbox('lab_warnbk', (0.3, 0.02, 0.27), (4.6 + sx, Y0 - 0.04, 1.05), p['pipe'], r=0.0))
        tri = lb.panel('lab_warn', [(-0.13, -0.11), (0.13, -0.11), (0, 0.12)], 0.02, (4.6 + sx, Y0 - 0.05, 1.05), (math.pi / 2, 0, 0), warn, bevel=0.01)
        B.append(tri)
        B.append(R('lab_warnmark', (0.025, 0.01, 0.09), (4.6 + sx, Y0 - 0.075, 1.05), p['pipe'], r=0.005))
    gas_tanks(B, ((6.35, 1.95), (6.75, 2.0)), Y0)
    # 屋顶：通风管 ×3 + 高排气筒 + 空调外机 + 检修口 + 栏杆
    z = H + 0.06
    for (x, y, h) in ((3.0, 5.6, 0.55), (3.6, 5.6, 0.45), (5.0, 5.8, 0.5)):
        roof_vent(B, x, y, z, h, p)
    roof_vent(B, 6.1, 5.5, z, 1.5, p, mush=True)
    B.append(R('lab_ac', (0.9, 0.6, 0.65), (3.4, 3.4, z + 0.33), p['white'], r=0.05))
    B.append(CY('lab_acfan', 0.22, 0.03, (3.4, 3.4 - 0.31, z + 0.35), p['pipe'], r=0.01, rot=(math.pi / 2, 0, 0)))
    for k in range(5):
        B.append(R('lab_acgrill', (0.44, 0.02, 0.02), (3.4, 3.4 - 0.33, z + 0.17 + k * 0.09), p['metal'], r=0.005))
    for sx in (-0.35, 0.35):
        B.append(R('lab_acfoot', (0.08, 0.66, 0.06), (3.4 + sx, 3.4, z + 0.0), p['metal'], r=0.02))
    B.append(R('lab_hatch', (0.8, 0.8, 0.25), (5.2, 3.6, z + 0.125), p['trim'], r=0.04))
    B.append(R('lab_hatchlid', (0.86, 0.86, 0.06), (5.2, 3.6, z + 0.28), p['metal'], r=0.02))
    B.append(L4.tube('lab_hatchh', [(5.05, 3.6, z + 0.31), (5.05, 3.6, z + 0.37), (5.35, 3.6, z + 0.37), (5.35, 3.6, z + 0.31)], [0.015] * 4, p['pipe'], 6))
    rx0, rx1, ry = 4.5, 6.6, 4.4
    for x in (rx0, (rx0 + rx1) / 2, rx1):
        B.append(CY('lab_rlpost', 0.025, 0.85, (x, ry, z + 0.425), p['lamppost'], r=0.008, verts=10))
    for zz in (0.45, 0.85):
        B.append(L4.tube('lab_rlbar', [(rx0, ry, z + zz), (rx1, ry, z + zz)], [0.022, 0.022], p['lamppost'], 8))
    e, B, F, dims, rnd = build_library()
    X0, X1, Y0, Y1 = dims[:4]
    _lib_shelves(B, X0, Y0)
    _lib_front(B, F, X0, X1, Y0)
    _lib_roof(B, X0, X1)
    _lib_sign(B, Y0)
    n = len(B) + len(F)
    return n, finish(B + F, 'Obj_Library', 'Library')
