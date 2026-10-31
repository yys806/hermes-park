"""日常事务地块：四个功能实体（书店 / 影院 / 超市 / 健身角）。依赖 lib_daily。Blender 4.5"""
import bpy, math, random
from mathutils import Vector
import lib_daily as D
import lib_learn2 as L2
import lib_learn4 as L4

B, C, M = D.B, D.C, D.M
BL = L2.ball

def walls_box(nm, x0, x1, y0, y1, z0, h, m, t=0.2, skip=()):
    """四面墙（不含 skip 里的面：'S','N','E','W'）。"""
    out = []
    if 'S' not in skip: out.append(B(nm, (x1 - x0, t, h), ((x0 + x1) / 2, y0 + t / 2, z0 + h / 2), m, r=0.05))
    if 'N' not in skip: out.append(B(nm, (x1 - x0, t, h), ((x0 + x1) / 2, y1 - t / 2, z0 + h / 2), m, r=0.05))
    if 'W' not in skip: out.append(B(nm, (t, y1 - y0 - 2 * t, h), (x0 + t / 2, (y0 + y1) / 2, z0 + h / 2), m, r=0.04))
    if 'E' not in skip: out.append(B(nm, (t, y1 - y0 - 2 * t, h), (x1 - t / 2, (y0 + y1) / 2, z0 + h / 2), m, r=0.04))
    return out

def front_wall(nm, x0, x1, y, z0, h, holes, m, t=0.2):
    """沿 X 的立面墙，按 holes=[(xa, xb, za, zb)] 留洞（局部 z 相对 z0）。拆成竖条 + 洞上下的块。"""
    out = []; xs = sorted({x0, x1, *[v for hh in holes for v in hh[:2]]})
    for xa, xb in zip(xs, xs[1:]):
        hole = next((hh for hh in holes if hh[0] <= xa + 1e-6 and hh[1] >= xb - 1e-6), None)
        cx = (xa + xb) / 2; w = xb - xa
        if hole is None:
            out.append(B(nm, (w, t, h), (cx, y + t / 2, z0 + h / 2), m, r=0.006)); continue
        za, zb = hole[2], hole[3]
        if za > 0.01: out.append(B(nm, (w, t, za), (cx, y + t / 2, z0 + za / 2), m, r=0.006))
        if zb < h - 0.01: out.append(B(nm, (w, t, h - zb), (cx, y + t / 2, z0 + (zb + h) / 2), m, r=0.006))
    return out

def books_row(nm, x0, x1, y, z, depth, rnd, h=(0.2, 0.3), lean=True, axis='X', rz=0.0):
    """一排彩色书脊（沿 X），底在 z。"""
    out = []; x = x0
    cols = ['red', 'blue', 'yellow', 'green', 'purple', 'pink', 'cream', 'orange']
    while x < x1 - 0.04:
        w = rnd.uniform(0.035, 0.07); hh = rnd.uniform(*h)
        if x + w > x1: break
        o = B(nm, (w - 0.005, depth, hh), (x + w / 2, y, z + hh / 2), M(rnd.choice(cols)), r=0.008, seg=1)
        if lean and rnd.random() < 0.08: o.rotation_euler.y = rnd.uniform(-0.25, 0.25)
        out.append(o); x += w
    if rz:
        for o in out:
            p = Vector(o.location) - Vector((x0, y, 0)); p.rotate(__import__('mathutils').Matrix.Rotation(rz, 3, 'Z'))
            o.location = Vector((x0, y, 0)) + p; o.rotation_euler.z += rz
    return out

def shelf_unit(nm, cx, y, z, w, d, h, levels, rnd):
    """开放书架：两侧板 + 层板 + 背板 + 每层一排书。正面朝 -Y。"""
    out = [B(nm, (0.05, d, h), (cx - w / 2 + 0.025, y, z + h / 2), M('shelf'), r=0.012),
           B(nm, (0.05, d, h), (cx + w / 2 - 0.025, y, z + h / 2), M('shelf'), r=0.012),
           B(nm, (w, 0.03, h), (cx, y + d / 2 - 0.015, z + h / 2), M('wood_dark'), r=0.01)]
    for k in range(levels + 1):
        zz = z + 0.04 + k * (h - 0.08) / levels
        out.append(B(nm, (w - 0.02, d, 0.035), (cx, y, zz), M('shelf'), r=0.01))
        if k < levels:
            out += books_row(nm + '_bk', cx - w / 2 + 0.06, cx + w / 2 - 0.06, y + 0.02, zz + 0.018, d * 0.7, rnd, h=(0.17, (h - 0.08) / levels - 0.06))
    return out

# ═════════ 实体二 · 小书店（西北角）═════════
BK = dict(x0=-7.4, x1=-2.6, y0=2.6, y1=6.6, f=0.24, h=3.0)

def build_bookstore():
    D.coll(); rnd = random.Random(21)
    x0, x1, y0, y1, f, h = BK['x0'], BK['x1'], BK['y0'], BK['y1'], BK['f'], BK['h']
    P = []
    P.append(B('bk', (x1 - x0 + 0.12, y1 - y0 + 0.12, f - D.G + 0.04), ((x0 + x1) / 2, (y0 + y1) / 2, (f + D.G - 0.04) / 2), M('stone'), r=0.04))
    P += walls_box('bk', x0, x1, y0, y1, f, h, M('cream'), skip=('S',))
    door = (-7.15, -6.15, 0.0, 2.15); win = (-5.85, -3.85, 0.42, 2.42)
    P += front_wall('bk', x0, x1, y0, f, h, [door, win], M('cream'))
    P.append(B('bk', (x1 - x0 + 0.06, 0.24, 0.12), ((x0 + x1) / 2, y0 + 0.08, f + h - 0.06), M('trim'), r=0.03))   # 檐下腰线
    P.append(B('bk', (x1 - x0 + 0.06, 0.24, 0.14), ((x0 + x1) / 2, y0 + 0.08, f + 0.07), M('trim'), r=0.03))       # 勒脚
    # 室内：地板 + 后墙两组书架 + 中间一张矮书台
    P.append(B('bk', (x1 - x0 - 0.4, y1 - y0 - 0.4, 0.03), ((x0 + x1) / 2, (y0 + y1) / 2, f + 0.015), M('deck2'), r=0.01))
    P.append(B('bk', (x1 - x0 - 0.4, y1 - y0 - 0.4, 0.05), ((x0 + x1) / 2, (y0 + y1) / 2, f + h - 0.1), M('interior'), r=0.0))
    for cx in (-6.3, -4.9, -3.6):
        P += shelf_unit('bk_sh', cx, y1 - 0.42, f + 0.03, 1.2, 0.36, 2.2, 5, rnd)
    for cx in (-5.5, -4.1):
        P += shelf_unit('bk_sh', cx, 4.3, f + 0.03, 1.1, 0.34, 1.3, 3, rnd)
    # 橱窗 + 门
    P += L4.window('bk_win', (-4.85, y0 + 0.05, f + 1.42), 2.0, 2.0, 'S', cols=3, rows=1, frame_m=M('door_green'),
                   glass=M('glass'), trim=M('trim'), sill=True, lintel=True, depth=0.08)
    P += books_row('bk_disp', -5.7, -4.0, y0 + 0.32, f + 0.47, 0.14, rnd, h=(0.18, 0.28))   # 橱窗台上一排展示书
    P.append(B('bk', (2.0, 0.34, 0.05), (-4.85, y0 + 0.33, f + 0.445), M('shelf'), r=0.01))
    P += L4.door('bk_door', (-6.65, y0 + 0.12, f), 0.98, 2.12, 'S', M('door_green'), M('trim'), M('brass'),
                 mat_m=M('wood_dark'), glass=M('glass'))
    # 门楣小木牌 + 字
    P.append(B('bk', (1.1, 0.06, 0.32), (-6.65, y0 - 0.06, f + 2.62), M('sign'), r=0.03))
    for sx in (-1, 1):
        P.append(C('bk', 0.012, 0.25, (-6.65 + sx * 0.4, y0 - 0.04, f + 2.86), M('brass'), verts=8, rr=0.004))
    P.append(D.text('bk_txt', 'BOOKS', 0.2, (-6.65, y0 - 0.1, f + 2.62), M('wood_dark'), depth=0.012))
    # 暖木双坡屋顶
    P += D.gable('bk_roof', x0, x1, y0, y1, f + h, f + h + 1.25, 0.38, 0.14, M('roof'), M('roof2'), M('cream'), n_boards=14)
    # 西山墙小窗（不透明玻璃）
    P += L4.window('bk_sw', (x0 - 0.01, 4.6, f + 1.6), 0.8, 1.0, 'W', cols=2, rows=2, frame_m=M('door_green'),
                   glass=M('glass_side'), trim=M('trim'), depth=0.06)
    return D.finish(P, 'Obj_Bookstore', 'Bookstore')

def drape(nm, x0, x1, y, z0, h, m, folds=6, open_side=0):
    """帘幕：一排压扁的竖圆柱当褶子，底部略收向 open_side（-1 左 / 1 右 / 0 不收）。"""
    out = []; w = (x1 - x0) / folds
    for k in range(folds):
        cx = x0 + w * (k + 0.5)
        o = C(nm, w * 0.62, h, (cx, y + (0.02 if k % 2 else -0.01), z0 + h / 2), m, verts=12, rr=0.02)
        o.scale.y = 0.55; out.append(o)
    if open_side:
        tie = x1 - 0.05 if open_side > 0 else x0 + 0.05
        out.append(C(nm + '_tie', 0.05, 0.1, (tie, y - 0.04, z0 + h * 0.45), M('brass'), verts=12, rr=0.01, rot=(math.pi / 2, 0, 0)))
    return out

# ═════════ 实体三 · 小影院（东北角）═════════
CN = dict(x0=2.6, x1=7.4, y0=2.6, y1=6.8, f=0.24, h=3.7)

def build_cinema():
    D.coll(); rnd = random.Random(31)
    x0, x1, y0, y1, f, h = CN['x0'], CN['x1'], CN['y0'], CN['y1'], CN['f'], CN['h']
    cx = (x0 + x1) / 2; P = []
    P.append(B('cn', (x1 - x0 + 0.12, y1 - y0 + 0.12, f - D.G + 0.04), (cx, (y0 + y1) / 2, (f + D.G - 0.04) / 2), M('stone'), r=0.04))
    P += walls_box('cn', x0, x1, y0, y1, f, h, M('cinema'), skip=('S',))
    tick = (3.95, 4.65, 0.95, 1.6); door = (5.15, 6.35, 0.0, 2.2)
    P += front_wall('cn', x0, x1, y0, f, h, [tick, door], M('cinema'))
    P.append(B('cn', (x1 - x0 - 0.4, y1 - y0 - 0.4, h - 0.1), (cx, (y0 + y1) / 2, f + h / 2), M('cinema_dark'), r=0.0))   # 暗室内
    # 平屋顶 + 一圈矮檐（挑出的檐口 + 女儿墙）
    P.append(B('cn', (x1 - x0 + 0.36, y1 - y0 + 0.36, 0.16), (cx, (y0 + y1) / 2, f + h + 0.08), M('cinema_dark'), r=0.05))
    P.append(B('cn', (x1 - x0 + 0.2, y1 - y0 + 0.2, 0.08), (cx, (y0 + y1) / 2, f + h - 0.06), M('trim'), r=0.03))
    zt = f + h + 0.16
    for (sx, sy, px, py) in ((x1 - x0 + 0.3, 0.16, cx, y0 - 0.1), (x1 - x0 + 0.3, 0.16, cx, y1 + 0.1),
                             (0.16, y1 - y0 + 0.2, x0 - 0.1, (y0 + y1) / 2), (0.16, y1 - y0 + 0.2, x1 + 0.1, (y0 + y1) / 2)):
        P.append(B('cn', (sx, sy, 0.24), (px, py, zt + 0.12), M('cinema'), r=0.05))
    P.append(B('cn', (x1 - x0 - 0.1, y1 - y0 - 0.1, 0.04), (cx, (y0 + y1) / 2, zt + 0.02), M('stone'), r=0.01))
    P.append(B('cn', (0.9, 0.7, 0.45), (6.2, 5.6, zt + 0.25), M('metal'), r=0.06))   # 屋顶小设备箱
    # 大银幕：深框 + 浅幕 + 上下胶片孔
    zs = f + 3.0
    P.append(B('cn', (4.1, 0.12, 1.25), (cx, y0 - 0.05, zs), M('cinema_dark'), r=0.04))
    P.append(B('cn', (3.8, 0.06, 0.92), (cx, y0 - 0.12, zs), M('screen'), r=0.03))
    for k in range(18):
        for sz in (-1, 1):
            P.append(B('cn', (0.09, 0.03, 0.06), (cx - 1.87 + k * 0.22, y0 - 0.115, zs + sz * 0.54), M('screen'), r=0.01, seg=1))
    P.append(D.text('cn_txt', 'CINEMA', 0.36, (cx, y0 - 0.16, zs + 0.02), M('curtain'), depth=0.02))
    # 暖黄小灯串：铜线 + 小灯泡（灯泡用 LGT_ 发光材质）
    pts = [Vector((x0 + 0.15 + k * (x1 - x0 - 0.3) / 16, y0 - 0.14, zs + 0.78 - 0.07 * math.sin(math.pi * ((k % 4) / 4)))) for k in range(17)]
    P.append(L4.tube('cn_wire', pts, [0.008] * len(pts), M('dark'), 6))
    bulb = D.lamp_mat('cinema_bulbs', '#FFD27A', 5.0)
    for k, p in enumerate(pts[1:-1]):
        P.append(BL('cn_bulb', 0.045, (p.x, p.y, p.z - 0.07), bulb, (1, 1, 1.25)))
        P.append(B('cn', (0.03, 0.03, 0.04), (p.x, p.y, p.z - 0.02), M('brass'), r=0.008, seg=1))
    # 售票窗：窗框 + 玻璃 + 台面 + 小雨棚 + 牌子
    P += L4.window('cn_tk', (4.3, y0 + 0.05, f + 1.275), 0.7, 0.65, 'S', cols=1, rows=1, frame_m=M('trim'), glass=M('glass'),
                   trim=M('cinema_dark'), sill=False, lintel=False, depth=0.06)
    P.append(B('cn', (0.95, 0.32, 0.06), (4.3, y0 - 0.1, f + 0.92), M('shelf'), r=0.02))
    P.append(B('cn', (1.0, 0.36, 0.06), (4.3, y0 - 0.16, f + 1.83), M('curtain'), r=0.025, rot=(-0.25, 0, 0)))
    P.append(B('cn', (0.86, 0.04, 0.2), (4.3, y0 - 0.04, f + 2.05), M('board'), r=0.02))
    P.append(D.text('cn_tk_txt', 'TICKETS', 0.1, (4.3, y0 - 0.07, f + 2.05), M('yellow'), depth=0.008))
    # 帘幕门：门框 + 横杆 + 帷幔 + 左右两幅红帘
    for sx in (-1, 1):
        P.append(B('cn', (0.14, 0.2, 2.3), (5.75 + sx * 0.67, y0 - 0.03, f + 1.15), M('brass'), r=0.04))
    P.append(B('cn', (1.5, 0.22, 0.16), (5.75, y0 - 0.03, f + 2.32), M('brass'), r=0.05))
    P += drape('cn_dr', 5.17, 5.73, y0 + 0.06, f + 0.02, 2.12, M('curtain'), 5, -1)
    P += drape('cn_dr', 5.77, 6.33, y0 + 0.06, f + 0.02, 2.12, M('curtain'), 5, 1)
    P += drape('cn_val', 5.15, 6.35, y0 - 0.06, f + 1.86, 0.32, M('curtain'), 9)
    P.append(B('cn', (1.3, 0.7, 0.025), (5.75, y0 - 0.4, D.G + 0.03), M('curtain'), r=0.012))   # 门口红毯
    # 场次小黑板：木框 + 黑板 + 粉笔字
    P.append(B('cn', (0.72, 0.05, 0.92), (6.95, y0 - 0.03, f + 1.45), M('shelf'), r=0.025))
    P.append(B('cn', (0.6, 0.03, 0.8), (6.95, y0 - 0.055, f + 1.45), M('board'), r=0.012))
    for k, s in enumerate(('TODAY', '14:00', '17:30', '20:15')):
        P.append(D.text('cn_ch', s, 0.1 if k else 0.085, (6.95, y0 - 0.075, f + 1.72 - k * 0.17), M('chalk'), depth=0.005))
    # 西侧墙两张海报
    for k, (py, col) in enumerate(((3.7, 'orange'), (5.2, 'blue'))):
        P.append(B('cn', (0.05, 0.8, 1.15), (x0 - 0.03, py, f + 1.5), M('brass'), r=0.02))
        P.append(B('cn', (0.03, 0.68, 1.02), (x0 - 0.05, py, f + 1.5), M(col), r=0.01))
        P.append(B('cn', (0.02, 0.5, 0.36), (x0 - 0.065, py, f + 1.62), M('screen'), r=0.01))
    return D.finish(P, 'Obj_Cinema', 'Cinema')

def arc_profile(y_out, z_top, z_bot, t, n=10):
    """遮阳棚剖面：墙面 (0,z_top) 起向外弯到 (y_out,z_bot) 的四分之一椭圆，厚 t。返回闭合多边形。"""
    outer = [(y_out * math.sin(a), z_bot + (z_top - z_bot) * math.cos(a)) for a in (k / n * math.pi / 2 for k in range(n + 1))]
    inner = [(y * (1 - t / abs(y_out)) if y else 0.0, z - t) for y, z in outer]
    return outer + inner[::-1]

def cart(nm, c, rz):
    """浅灰购物车：管框篮子 + 栅格 + 推把 + 四轮。局部 +x 为车头。"""
    P = []; m = M('metal'); zb, zt = 0.5, 0.85
    corners = [(-0.3, -0.21), (0.32, -0.19), (0.32, 0.19), (-0.3, 0.21)]
    for z in (zb, zt):
        ring = [(x, y, z) for x, y in corners] + [(corners[0][0], corners[0][1], z)]
        P.append(L4.tube(nm, ring, [0.012] * 5, m, 6))
    for k in range(9):   # 侧面竖条
        t = k / 8
        for sy in (-1, 1):
            x = -0.3 + 0.62 * t; y = sy * (0.21 - 0.02 * t)
            P.append(L4.tube(nm, [(x, y, zb), (x, y, zt)], [0.006, 0.006], m, 5))
    for k in range(5):   # 底网
        y = -0.18 + k * 0.09
        P.append(L4.tube(nm, [(-0.3, y, zb), (0.32, y, zb)], [0.006, 0.006], m, 5))
    for sy in (-1, 1):   # 车架 + 推把立杆
        P.append(L4.tube(nm, [(-0.36, sy * 0.2, 0.1), (-0.3, sy * 0.2, zb), (-0.36, sy * 0.21, zt + 0.12)], [0.014] * 3, m, 6))
        P.append(L4.tube(nm, [(-0.36, sy * 0.18, 0.1), (0.3, sy * 0.14, 0.1)], [0.014] * 2, m, 6))
    P.append(C(nm, 0.025, 0.46, (-0.37, 0, zt + 0.13), M('orange'), verts=12, rr=0.01, rot=(math.pi / 2, 0, 0)))
    for x, y in ((-0.34, -0.2), (-0.34, 0.2), (0.28, -0.15), (0.28, 0.15)):
        P.append(C(nm, 0.045, 0.03, (x, y, 0.045), M('dark'), verts=14, rr=0.01, rot=(math.pi / 2, 0, 0)))
    return L4.place(P, c, rz)

# ═════════ 实体四 · 小超市（东南角，门朝西）═════════
SM = dict(c=(4.4, -4.7), w=3.4, d=3.1, f=0.24, h=3.2)

def build_supermarket():
    D.coll(); rnd = random.Random(41)
    w, d, f, h = SM['w'], SM['d'], SM['f'], SM['h']; x0, x1 = -w / 2, w / 2
    P = []   # 局部坐标：立面沿 x，-y 朝外（西），y∈[0,d]
    P.append(B('sm', (w + 0.12, d + 0.12, f - D.G + 0.04), (0, d / 2, (f + D.G - 0.04) / 2), M('stone'), r=0.04))
    P += walls_box('sm', x0, x1, 0, d, f, h, M('white'), skip=('S',))
    door = (-0.85, 0.85, 0.0, 2.2)
    P += front_wall('sm', x0, x1, 0, f, h, [door], M('white'))
    P.append(B('sm', (w - 0.4, d - 0.4, h - 0.1), (0, d / 2, f + h / 2), M('cream'), r=0.0))
    # 女儿墙 + 压顶 + 招牌
    P.append(B('sm', (w + 0.16, d + 0.16, 0.36), (0, d / 2, f + h + 0.18), M('white'), r=0.05))
    P.append(B('sm', (w + 0.26, d + 0.26, 0.07), (0, d / 2, f + h + 0.39), M('tile_grout'), r=0.03))
    P.append(B('sm', (w - 0.3, d - 0.3, 0.06), (0, d / 2, f + h + 0.37), M('stone'), r=0.01))
    P.append(B('sm', (2.3, 0.05, 0.36), (0, -0.1, f + h + 0.05), M('awning'), r=0.03))
    P.append(D.text('sm_txt', 'MARKET', 0.24, (0, -0.135, f + h + 0.05), M('white'), depth=0.015))
    P.append(B('sm', (w + 0.02, 0.24, 0.12), (0, 0.08, f + 0.06), M('tile_grout'), r=0.03))   # 勒脚
    # 两扇玻璃门：金属框 + 玻璃 + 色块贴纸 + 推把
    for k, sx in enumerate((-1, 1)):
        cx = sx * 0.425
        for fx in (-0.39, 0.39):
            P.append(B('sm', (0.06, 0.08, 2.18), (cx + fx, 0.06, f + 1.09), M('metal'), r=0.02))
        for fz in (0.06, 2.15):
            P.append(B('sm', (0.84, 0.08, 0.08), (cx, 0.06, f + fz), M('metal'), r=0.02))
        P.append(B('sm', (0.84, 0.08, 0.2), (cx, 0.06, f + 0.16), M('metal'), r=0.02))
        P.append(B('sm', (0.74, 0.02, 1.88), (cx, 0.07, f + 1.18), M('glass'), r=0.008, seg=1))
        for j, (col, gx, gz) in enumerate((('red', -0.2, 1.55), ('yellow', 0.0, 1.55), ('blue', 0.2, 1.55))):
            P.append(B('sm', (0.14, 0.01, 0.14), (cx + gx * sx, 0.055, f + gz), M(col), r=0.02, seg=1))
        P.append(B('sm', (0.6, 0.01, 0.06), (cx, 0.055, f + 1.33), M('green' if k else 'orange'), r=0.02, seg=1))
        P.append(C('sm', 0.018, 0.5, (cx - sx * 0.25, -0.02, f + 1.1), M('dark'), verts=10, rr=0.006))
    P.append(B('sm', (2.0, 0.3, 0.14), (0, 0.05, f + 2.33), M('metal'), r=0.03))
    P.append(B('sm', (1.5, 0.6, 0.02), (0, -0.45, D.G + 0.025), M('dark'), r=0.01))
    # 浅蓝圆角遮阳棚（蓝白条）+ 波浪垂边 + 两根撑杆
    prof = arc_profile(-1.05, f + 2.95, f + 2.45, 0.06)
    n = 8; aw = 2.6
    for k in range(n):
        xa = -aw / 2 + k * aw / n; xb = xa + aw / n
        P.append(D.prism('sm_aw', prof, xa, xb, M('awning' if k % 2 == 0 else 'awning2'), r=0.008))
    for k in range(13):
        P.append(BL('sm_sc', 0.1, (-aw / 2 + 0.1 + k * (aw - 0.2) / 12, -1.04, f + 2.42), M('awning' if k % 2 == 0 else 'awning2'), (1, 0.35, 0.7)))
    for sx in (-1, 1):
        P.append(C('sm', 0.13, 0.04, (sx * aw / 2, -0.52, f + 2.72), M('metal'), verts=16, rr=0.01, rot=(0, math.pi / 2, 0)))
    # 南侧墙小窗（局部 +x 端）
    P += L4.window('sm_sw', (x1 + 0.01, d / 2, f + 1.6), 1.1, 1.0, 'E', cols=2, rows=1, frame_m=M('metal'),
                   glass=M('glass_side'), trim=M('tile_grout'), depth=0.06)
    P = L4.place(P, (*SM['c'], 0), D.FACE['W'])
    P += cart('sm_cart', (4.0, -5.85, D.G + 0.005), math.radians(100))
    return D.finish(P, 'Obj_Supermarket', 'Supermarket')

# ═════════ 实体一 · 露天健身角（西南角）═════════
TM = dict(c=(-5.0, -4.75), rz=0.0)
RACK = dict(c=(-6.5, -6.0), rz=math.radians(28))

def treadmill():
    """圆润跑步机（局部 +x 为前/控制台）。"""
    P = []; z0 = D.G + 0.015; body, band = M('tm_body'), M('tm_band')
    P.append(B('tm', (1.72, 0.78, 0.16), (0, 0, z0 + 0.1), body, r=0.07))                     # 底座
    P.append(B('tm', (1.78, 0.84, 0.03), (0, 0, z0 + 0.025), M('dark'), r=0.015))              # 防滑底边
    P.append(B('tm', (1.42, 0.52, 0.035), (-0.12, 0, z0 + 0.19), band, r=0.015))              # 跑带
    for k in range(18):                                                                        # 跑带横纹
        P.append(B('tm', (0.022, 0.5, 0.01), (-0.8 + k * 0.08, 0, z0 + 0.208), M('tm_line'), r=0.004, seg=1))
    for sy in (-1, 1):
        P.append(B('tm', (1.5, 0.11, 0.06), (-0.1, sy * 0.33, z0 + 0.2), body, r=0.025))      # 两侧踏边
        P.append(B('tm', (1.3, 0.012, 0.03), (-0.12, sy * 0.39, z0 + 0.12), M('orange'), r=0.005, seg=1))   # 橙色腰线
        P.append(C('tm', 0.06, 0.04, (-0.83, sy * 0.33, z0 + 0.12), M('dark'), verts=16, rr=0.01, rot=(math.pi / 2, 0, 0)))
    P.append(B('tm', (0.36, 0.8, 0.3), (0.72, 0, z0 + 0.2), body, r=0.12))                    # 前电机罩
    P.append(B('tm', (0.2, 0.5, 0.012), (0.72, 0, z0 + 0.355), M('orange'), r=0.005, seg=1))
    for sy in (-1, 1):                                                                         # 立柱 + 上扬扶手
        P.append(L4.tube('tm', [(0.72, sy * 0.36, z0 + 0.25), (0.7, sy * 0.37, z0 + 0.8), (0.62, sy * 0.38, z0 + 1.15),
                                (0.45, sy * 0.39, z0 + 1.08), (0.22, sy * 0.39, z0 + 1.0), (0.12, sy * 0.39, z0 + 1.06)],
                         [0.035, 0.032, 0.03, 0.026, 0.026, 0.024], M('tm_body'), 10))
        P.append(C('tm', 0.028, 0.18, (0.32, sy * 0.39, z0 + 1.04), M('orange'), verts=12, rr=0.01, rot=(0, math.pi / 2 - 0.22, 0)))
    P.append(C('tm', 0.022, 0.76, (0.62, 0, z0 + 1.12), M('tm_body'), verts=10, rr=0.008, rot=(math.pi / 2, 0, 0)))
    con = [B('tm', (0.16, 0.56, 0.24), (0, 0, 0), body, r=0.06),
           B('tm', (0.02, 0.36, 0.14), (-0.08, 0, 0.02), M('screen_dk'), r=0.02),
           B('tm', (0.012, 0.28, 0.07), (-0.088, 0, 0.03), M('awning'), r=0.01, seg=1)]
    for k in range(3):
        con.append(C('tm', 0.018, 0.02, (-0.085, -0.12 + k * 0.12, -0.08), M('orange'), verts=10, rr=0.005, rot=(0, math.pi / 2, 0)))
    for o in con:
        o.location = Vector(o.location) + Vector((0.66, 0, z0 + 1.27)); o.rotation_euler.y = -0.35
    P += con
    return P

def dumbbell_rack():
    """矮哑铃架：两层斜托 + 三个小哑铃（局部）。"""
    P = []; z0 = D.G + 0.015
    for sx in (-1, 1):
        P.append(B('rk', (0.06, 0.34, 0.5), (sx * 0.42, 0, z0 + 0.25), M('tm_body'), r=0.025))
        P.append(B('rk', (0.12, 0.42, 0.04), (sx * 0.42, 0, z0 + 0.02), M('dark'), r=0.015))
    for zz, yy in ((0.26, -0.06), (0.46, 0.06)):
        P.append(B('rk', (0.84, 0.16, 0.035), (0, yy, z0 + zz), M('tm_body'), r=0.012))
        P.append(B('rk', (0.84, 0.02, 0.06), (0, yy - 0.08, z0 + zz + 0.03), M('tm_body'), r=0.008))
    for k, (x, zz, yy, col) in enumerate(((-0.24, 0.26, -0.06, 'orange'), (0.2, 0.26, -0.06, 'tm_band'), (-0.02, 0.46, 0.06, 'orange'))):
        z = z0 + zz + 0.075
        P.append(C('db', 0.018, 0.26, (x, yy, z), M('metal'), verts=10, rr=0.005, rot=(0, math.pi / 2, 0)))
        for s in (-1, 1):
            P.append(C('db', 0.058, 0.05, (x + s * 0.1, yy, z), M(col), verts=16, rr=0.015, rot=(0, math.pi / 2, 0)))
    return P

def port_pedestal():
    """跑步机接口的落地小机箱（Port_Treadmill 挂在它北面）。"""
    z0 = D.G + 0.015
    return [B('pp', (1.3, 0.5, 0.95), (-5.4, -3.45, z0 + 0.475), M('stone'), r=0.08),
            B('pp', (1.4, 0.6, 0.06), (-5.4, -3.45, z0 + 0.98), M('trim'), r=0.03),
            B('pp', (0.6, 0.02, 0.12), (-5.4, -3.71, z0 + 0.8), M('orange'), r=0.02)]

def build_fitness():
    D.coll()
    P = L4.place(treadmill(), (*TM['c'], 0), TM['rz'])
    P += L4.place(dumbbell_rack(), (*RACK['c'], 0), RACK['rz'])
    P += port_pedestal()
    return D.finish(P, 'Obj_Treadmill', 'Treadmill')

# ═════════ 配景 ═════════
import lib_learn5 as L5

def build_fence():
    """南侧白色矮篱笆（入口留 3.6 m 口）：尖头竖板 + 两道横档 + 方柱。"""
    D.coll(); D.wipe(('Fence_',)); P = []; y = -7.72; m = M('fence')
    for xa, xb in ((-7.85, -1.85), (1.85, 7.85)):
        L_ = xb - xa; cx = (xa + xb) / 2
        for z in (0.28, 0.58):
            P.append(B('fe', (L_, 0.04, 0.07), (cx, y + 0.035, z), m, r=0.015))
        n = int(L_ / 0.16)
        for k in range(n + 1):
            x = xa + k * L_ / n
            post = k % 8 == 0 or k == n
            if post:
                P.append(B('fe', (0.1, 0.1, 0.78), (x, y, 0.04 + 0.39), m, r=0.03))
                P.append(BL('fe', 0.055, (x, y, 0.86), m))
            else:
                P.append(B('fe', (0.075, 0.025, 0.6), (x, y - 0.01, 0.04 + 0.3), m, r=0.012, seg=2))
                P.append(L2.ball('fe', 0.038, (x, y - 0.01, 0.64), m, (1, 0.34, 1.15)))
    return L2.join(P, 'Fence_south')

def build_stools():
    D.coll(); D.wipe(('Stool_',)); out = []
    for k, x in enumerate((-1.9, 1.9)):
        P = [C('st', 0.26, 0.36, (x, 0.95, D.G + 0.18), M('stone'), verts=32, rr=0.06),
             C('st', 0.3, 0.07, (x, 0.95, D.G + 0.39), M('stone'), verts=32, rr=0.03),
             C('st', 0.31, 0.03, (x, 0.95, D.G + 0.015), M('grout'), verts=32, rr=0.01)]
        out.append(L2.join(P, 'Stool_%d' % (k + 1)))
    return out

def low_table(nm, x, y, rz=0.0):
    """书摊矮木桌 0.8×0.5×0.55。"""
    z0 = D.G + 0.01; P = [B(nm, (0.82, 0.52, 0.05), (0, 0, z0 + 0.53), M('shelf'), r=0.02)]
    P.append(B(nm, (0.72, 0.42, 0.06), (0, 0, z0 + 0.48), M('wood_dark'), r=0.01))
    for sx in (-1, 1):
        for sy in (-1, 1):
            P.append(B(nm, (0.05, 0.05, 0.5), (sx * 0.34, sy * 0.2, z0 + 0.25), M('shelf'), r=0.015))
    P.append(B(nm, (0.7, 0.03, 0.04), (0, 0, z0 + 0.12), M('shelf'), r=0.01))
    return L4.place(P, (x, y, 0), rz)

def prop(pack, name, newname, x, y, z, height=None, scale=None, rz=0.0):
    o = L5.import_gltf(pack, name, newname, coll=D.COLL)
    L5.normalize(o, height=height, scale=scale, loc=(x, y), z=z, rz=rz, center=True)
    return o

def build_props():
    """书摊（两张矮桌 + 书堆 + 小椅子）、超市门口两只货箱、健身角长椅。"""
    D.coll(); D.wipe(('Props_',)); zt = D.G + 0.01 + 0.555; out = []
    tb = low_table('tb', -5.35, 0.98) + low_table('tb', -4.35, 0.98)
    out.append(L2.join(tb, 'Props_bookstall'))
    for k, (nm, x, y, h, rz) in enumerate((('Book_Stack_1', -5.55, 0.95, 0.16, 0.3), ('BookGroup_Small_1', -5.15, 1.02, 0.2, 0.0),
                                           ('Book_Stack_2', -4.55, 0.92, 0.18, -0.4), ('BookGroup_Small_3', -4.15, 1.02, 0.2, 0.1))):
        out.append(prop('props', nm, 'Props_books_%d' % k, x, y, zt, height=h, rz=rz))
    out.append(prop('props', 'Chair_1', 'Props_chair', -6.05, 0.95, D.G + 0.01, height=0.85, rz=math.radians(-110)))
    out.append(prop('props', 'FarmCrate_Apple', 'Props_crate_1', 3.9, -3.5, D.G, height=0.42, rz=0.1))
    out.append(prop('props', 'FarmCrate_Carrot', 'Props_crate_2', 3.35, -3.4, D.G, height=0.42, rz=-0.25))
    out.append(prop('props', 'Bench', 'Props_bench_fit', -7.0, -4.5, D.G + 0.015, height=0.75, rz=math.pi / 2))
    return out

def _hide(o, hidden=True):
    o['default_visible'] = not hidden; o.hide_render = hidden; o.hide_set(hidden)

def _season_link(o):
    for c in list(o.users_collection): c.objects.unlink(o)
    bpy.data.collections[D.SEASON].objects.link(o)

def twig_bush(nm, x, y, z, r, seed):
    """枯枝灌木（Bare_）：从根部散开的细枝。"""
    rnd = random.Random(seed); P = []
    for k in range(9):
        a = k / 9 * math.tau + rnd.uniform(-0.3, 0.3); rr = r * rnd.uniform(0.7, 1.05); hh = r * rnd.uniform(1.0, 1.5)
        pts = L4.bez((0, 0, 0), (math.cos(a) * rr * 0.3, math.sin(a) * rr * 0.3, hh * 0.5), (math.cos(a) * rr, math.sin(a) * rr, hh), 5)
        P.append(L4.tube(nm, [(p.x + x, p.y + y, p.z + z) for p in pts], [0.03, 0.024, 0.018, 0.012, 0.006], L5.clay('q_wood', '#8C5E40'), 6))
    return L2.join(P, nm)

TREES = {'SW': (-6.8, -6.75, 1, 0.4), 'SE': (6.8, -6.75, 2, 2.2), 'N1': (-1.4, 6.7, 3, 1.0), 'N2': (1.5, 5.6, 4, 4.0)}
BUSHES = {'1': (-3.45, -2.6, 1), '2': (-2.25, -3.2, 2), '3': (-2.25, -4.05, 1),
          'bk': (-7.5, 3.5, 2), 'cn': (7.55, 4.2, 1), 'sm': (7.5, -6.85, 2), 'mid': (0.0, 4.2, 1)}

def build_greens():
    """树 + 灌木：Foliage_（绿，默认显示）+ Foliage_Autumn_ / Bare_ / Snow_（隐藏，位置一一对应）。"""
    D.coll(); D.coll(D.SEASON); D.coll()
    D.wipe(('Foliage_', 'Bare_', 'Snow_'))
    out = []
    for k, (x, y, n, rz) in TREES.items():
        g = L5.append_nature('CommonTree_%d' % n, 'Foliage_tree_' + k, coll=D.COLL)
        s = L5.normalize(g, height=4.4, loc=(x, y), z=0.04, rz=rz); g['default_visible'] = True; out.append(g)
        for src, pre in (('CommonTree_Autumn_%d', 'Foliage_Autumn_tree_'), ('CommonTree_Dead_%d', 'Bare_tree_'), ('CommonTree_Snow_%d', 'Snow_tree_')):
            v = L5.append_nature(src % n, pre + k, coll=D.SEASON)
            L5.normalize(v, scale=s, loc=(x, y), z=0.04, rz=rz); _hide(v); out.append(v)
    for k, (x, y, n) in BUSHES.items():
        g = L5.append_nature('Bush_%d' % n, 'Foliage_bush_' + k, coll=D.COLL)
        s = L5.normalize(g, height=0.8, loc=(x, y), z=0.03, rz=x + y); g['default_visible'] = True; out.append(g)
        a = g.copy(); a.data = g.data.copy(); a.name = a.data.name = 'Foliage_Autumn_bush_' + k
        bpy.data.collections[D.SEASON].objects.link(a)
        for sl in a.material_slots:
            if sl.material and 'green' in sl.material.name: sl.material = L5.clay('q_orange', '#E8984E')
        _hide(a); out.append(a)
        sn = L5.append_nature('Bush_Snow_%d' % n, 'Snow_bush_' + k, coll=D.SEASON)
        L5.normalize(sn, scale=s, loc=(x, y), z=0.03, rz=x + y); _hide(sn); out.append(sn)
        D.coll(D.SEASON); b = twig_bush('Bare_bush_' + k, x, y, 0.03, 0.42, hash(k) % 97); D.coll()
        _hide(b); out.append(b)
    for o in out: L5.ensure_ao(o)
    return out

import lib_learn6 as L6
LAMPS = {   # 灯名: (x, y, 落地面高度)
    'path_W': (-2.05, -5.9, 0.04), 'path_E': (2.05, -5.9, D.G),
    'fitness': (-3.3, -3.75, D.G + 0.015), 'bookstore': (-7.05, 1.65, D.G + 0.01),
    'cinema': (6.95, 1.65, D.G + 0.01), 'supermarket': (3.85, -6.35, D.G),
}

def street_lamp(lid, x, y, z0, H=2.2, energy=45):
    """底座 + 锥度灯杆 + 八角灯笼头。body 普通材质，只有 shade 用 LGT_daily_<lid> 发光；点光源在灯头中心。"""
    D.wipe(('LGT_daily_' + lid,))
    cone, ball, tag = L6.cone, L6.ball, L6.tag
    bm = __import__('bmesh').new()
    cone(bm, 0.22, 0.22, 0.05, 0.0, 8); cone(bm, 0.17, 0.12, 0.24, 0.05, 8); cone(bm, 0.085, 0.075, 0.06, 0.29, 16)
    cone(bm, 0.055, 0.038, H - 0.9, 0.35, 16)
    zc = H - 0.56
    cone(bm, 0.065, 0.085, 0.05, zc - 0.08, 16); cone(bm, 0.05, 0.16, 0.08, zc - 0.03, 8); cone(bm, 0.18, 0.18, 0.035, zc + 0.05, 8)
    for k in range(8):
        a = (k + 0.5) / 8 * math.tau
        cone(bm, 0.012, 0.012, 0.32, zc + 0.085, 6, xy=(0.158 * math.cos(a), 0.158 * math.sin(a)))
    cone(bm, 0.19, 0.19, 0.03, zc + 0.405, 8); cone(bm, 0.25, 0.06, 0.15, zc + 0.435, 8); cone(bm, 0.045, 0.028, 0.05, zc + 0.585, 8)
    ball(bm, 0.04, (0, 0, zc + 0.67))
    n0 = len(bm.faces)
    for k in range(2):
        a = k * math.pi; cone(bm, 0.022, 0.011, 0.11, zc - 0.24, 6, xy=(0.065 * math.cos(a), 0.065 * math.sin(a)))
    tag(bm, 1, n0)
    body = L6.mesh('LGT_daily_%s_body' % lid, bm, [M('lamp_post'), M('bolt')])
    bs = __import__('bmesh').new(); cone(bs, 0.14, 0.14, 0.32, zc + 0.085, 8)
    shade = L6.mesh('LGT_daily_%s_shade' % lid, bs, [D.lamp_mat(lid, '#FFE2A8', 6.0)])
    nm = 'LGT_daily_' + lid
    e = bpy.data.objects.new(nm, None); e.empty_display_size = 0.3; bpy.data.collections[D.COLL].objects.link(e)
    e.location = (x, y, z0); e['castShadow'] = True; e['lgt_kind'] = 'street'
    ld = bpy.data.lights.new(nm + '_light', 'POINT'); ld.energy = energy; ld.color = (1.0, 0.82, 0.58)
    ld.shadow_soft_size = 0.06; ld.use_shadow = True
    lo = bpy.data.objects.new(nm + '_light', ld); bpy.data.collections[D.COLL].objects.link(lo)
    lo.location = (0, 0, zc + 0.245); lo['castShadow'] = True
    for o in (body, shade, lo): o.parent = e
    shade.visible_shadow = False
    return e

def build_lamps():
    D.coll()
    return [street_lamp(k, *v) for k, v in LAMPS.items()]

# ═════════ 传送带 ═════════
HUB = (0.0, -0.4)
TOP = D.TOP
# 元素: (宽, 折线点, 接口位置, 接口朝向)
SUBS = {
    'Bookstore':   (0.6,  [(-1.0, 0.1), (-3.22, 0.1), (-3.22, 2.42)],   (-3.22, 2.51), 'S'),
    'Cinema':      (0.7,  [(1.0, 0.1), (3.22, 0.1), (3.22, 2.42)],      (3.22, 2.51), 'S'),
    'Treadmill':   (0.5,  [(-1.0, -0.9), (-5.4, -0.9), (-5.4, -3.02)],  (-5.4, -3.11), 'N'),
    'Supermarket': (0.65, [(1.0, -0.9), (5.9, -0.9), (5.9, -2.82)],     (5.9, -2.91), 'N'),
}

def _belt(nm, pts, w, Mb):
    parts = []
    for a, b in zip(pts, pts[1:]):
        parts += L2.belt_seg(nm, a, b, w, Mb, top=TOP)
        d = Vector((b[0] - a[0], b[1] - a[1], 0)).normalized(); rz = math.atan2(d.y, d.x)
        n = Vector((-d.y, d.x, 0))
        for q in (a, b):   # 段两端滚筒端盖
            for s in (-1, 1):
                c = Vector((*q, 0)) + n * s * (w / 2 + 0.01) - d * (0.06 if q is b else -0.06)
                parts.append(C(nm + '_axle', 0.04, 0.025, (c.x, c.y, TOP - 0.08), Mb['bolt'], verts=12, rr=0.006, rot=(math.pi / 2, 0, rz)))
    for p in pts[1:-1]:
        parts += L2.belt_corner(nm, p, w, Mb, top=TOP)
    return parts

def build_belts():
    D.coll(); D.wipe(('Belt_', 'Port_')); Mb = D.belt_mats(); out = []
    for k, (w, pts, ploc, face) in SUBS.items():
        out.append(L2.join(_belt('bs', pts, w, Mb), 'Belt_Sub_' + k))
        out.append(L2.port('Port_' + k, (*ploc, TOP + 0.18), face, Mb, w=0.8, h=0.35))
    out.append(L2.join(_belt('bm', [(HUB[0], HUB[1] - 1.0), (0.0, -7.62)], 1.0, Mb), 'Belt_Main_daily'))
    out.append(L2.port('Port_Main_daily', (0.0, -7.71, TOP + 0.22), 'S', Mb, w=1.2, h=0.5))
    # 汇总节点：浅木圆角方台 + 深木底座 + 转盘 + 圆顶小盖
    hx, hy = HUB; hp = [
        B('hub', (2.0, 2.0, 0.2), (hx, hy, D.G + 0.1), M('wood_dark'), r=0.08),
        B('hub', (1.9, 1.9, 0.24), (hx, hy, D.G + 0.32), M('hub'), r=0.22),
        B('hub', (1.96, 1.96, 0.05), (hx, hy, D.G + 0.46), M('hub2'), r=0.02),
        C('hub', 0.62, 0.05, (hx, hy, D.G + 0.51), M('hub2'), verts=40, rr=0.02),
        C('hub', 0.5, 0.04, (hx, hy, D.G + 0.555), M('belt'), verts=40, rr=0.015),
        C('hub', 0.2, 0.18, (hx, hy, D.G + 0.66), M('hub'), verts=32, rr=0.05),
        BL('hub', 0.12, (hx, hy, D.G + 0.76), M('orange'), (1, 1, 0.8))]
    for sx in (-1, 1):
        for sy in (-1, 1):
            hp.append(BL('hub', 0.03, (hx + sx * 0.8, hy + sy * 0.8, D.G + 0.49), M('bolt')))
    for a in range(8):   # 转盘分格线
        t = a / 8 * math.tau
        hp.append(B('hub', (0.42, 0.02, 0.012), (hx + 0.25 * math.cos(t), hy + 0.25 * math.sin(t), D.G + 0.578), M('slit'), r=0.004, seg=1, rot=(0, 0, t)))
    out.append(L2.join(hp, 'Belt_Hub_daily'))
    return out
