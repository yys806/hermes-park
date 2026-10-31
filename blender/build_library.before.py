import sys, os, math, random
import bpy
from mathutils import Matrix, Vector
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib_building as L
# 灯光开关：True=亮，False=灭。数值是自发光强度。
LIGHTS = {
    'outdoor':  {'on': False, 'strength': 3.0},   # 户外路灯（已有）
    'ceiling1F':{'on': False, 'strength': 3.5},   # 一楼中央吊灯（本轮新增）
    'ceiling2F':{'on': False, 'strength': 3.0},   # 二楼吊灯 A
    'ceiling2F_b':{'on': False,'strength': 3.0},  # 二楼吊灯 B
}

L.reset_scene()
# ── 材质 ──
M = {
 'wall':  L.mat('wall',  '#F3EEE2', 0.82),
 'trim':  L.mat('trim',  '#E0D6C2', 0.80),
 'roof':  L.mat('roof',  '#B7C9BE', 0.75),
 'ridge': L.mat('ridge', '#A8BCB1', 0.75),
 'wood':  L.mat('wood',  '#C9A27A', 0.78),
 'woodD': L.mat('woodD', '#A8845F', 0.78),
 'glass': L.mat('glass', '#CFE3EA', 0.05, 0.0, 0.15),   # 高透：alpha 0.15
 'stone': L.mat('stone', '#E8DFC9', 0.85),
 'metal': L.mat('metal', '#B9A37A', 0.35, 0.6),
 'grass': L.mat('grass', '#8FBA84', 0.9),
 'flwA':  L.mat('flwA',  '#E8A0BF', 0.8),
 'flwB':  L.mat('flwB',  '#F0C86A', 0.8),
 'book1': L.mat('book1', '#C46B5A', 0.8),
 'book2': L.mat('book2', '#5B8FA8', 0.8),
 'book3': L.mat('book3', '#D8B25E', 0.8),
 'dark':  L.mat('dark',  '#8A7A63', 0.85),
 'floor': L.mat('floor', '#C9B79A', 0.85),
 'inWall': L.mat('inWall', '#FBF6EA', 0.85),
 'lamp':  L.mat('lamp',  '#FFEFD0', 0.4),
 'ink':   L.mat('ink',   '#4A3A2A', 0.7),
}
# 自发光（lib.mat 不管 emission，这里单独补）：发光色取其 Base Color。glTF 不导出 Blender 灯光（export_glb 未开
# export_lights），故室内补光全靠 emissive：灯泡/屏幕强发光，室内专用的内墙衬板与地板弱发光 → 从窗外看室内不发黑
def glow(m, k):
    bs = next(n for n in M[m].node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    bs.inputs['Emission' if 'Emission' in bs.inputs else 'Emission Color'].default_value = bs.inputs['Base Color'].default_value[:]
    bs.inputs['Emission Strength'].default_value = k
for m, k in (('lamp', 5.0), ('inWall', 0.35), ('floor', 0.25)):
    glow(m, k)
for k, v in LIGHTS.items():   # 每盏灯独占材质 LGT_<key> → 合并后为独立对象，可单独点亮；灭时仍是暖白磨砂罩
    M['LGT_' + k] = L.mat('LGT_' + k, '#FFE6A8' if k == 'outdoor' else '#FFEFD0', 0.4)
    glow('LGT_' + k, v['strength'] if v['on'] else 0.0)
parts = []   # 所有构件追加到这里
CHK = []     # 自检：(墙板名, side, 洞口外表面中心)
D = math.radians

def B(n, size, loc, m, rot=(0, 0, 0), bv=0.02):
    o = L.box(n, size, loc, rot, M[m], bevel=bv); parts.append(o); return o
def C(n, r, h, loc, m, rot=(0, 0, 0), v=24):
    o = L.cyl(n, r, h, loc, rot, M[m], verts=v, bevel=0.01); parts.append(o); return o
def S(n, r, loc, m):
    o = L.sphere(n, r, loc, M[m]); parts.append(o); return o
def P_of(side, u0, z0):
    """墙面局部坐标 → 世界：u 沿墙面，dn 沿外法线，dz 竖直；返回 (P, rot_z)。"""
    ax, s, f = side
    def P(du, dn, dz):
        return (u0 + du, s * (f + dn), z0 + dz) if ax == 'y' else (s * (f + dn), u0 + du, z0 + dz)
    return P, (0 if ax == 'y' else D(90))
def semi(r):  # 压扁 0.6 的半圆轮廓
    return [(r * math.cos(math.pi * i / 12), 0.6 * r * math.sin(math.pi * i / 12)) for i in range(13)]
def win(wall, side, u0, z0, w, h, arch=False):
    """通窗：切割体中心置于 dn=-0.16（外墙 0.3 + 内衬 0.02 的中线）、深 CUT=0.6，外墙板与内衬板各切一次 → 贯穿；
    洞侧衬条 + 高透玻璃 + 2 竖棂 + 1 横档 + 外挑窗台；arch 时加压扁半圆拱（同样贯穿）。"""
    P, rz = P_of(side, u0, z0)
    wall, inner = wall[side[:2]], INNER[wall[side[:2]].name[:5]][side[:2]]
    fw, fh = w + 0.13, h + 0.13
    for o in (wall, inner):
        L.window_recess(o, fw, fh, CUT, P(0, -0.16, 0), rz); o['cut_depth'] = CUT
    tp = [P(0, 0.2, 0)] + ([P(0, 0.2, h / 2 + 0.15 * fw)] if arch else [])   # 射线起点：墙外 0.2，洞心 / 拱心
    CHK.append((wall, inner, tp, Vector(P(0, -1, 0)) - Vector(P(0, 0, 0)), int(side[0] == 'y'), abs(u0) + fw / 2, z0, fh))
    for k in (-1, 1):   # 洞侧衬条：只填洞边→玻璃边的 0.065 缝，深 0.32 盖住外墙+内衬的切口
        B('winJ', (0.065, 0.32, h), P(k * (w + fw) / 4, -0.16, 0), 'trim', (0, 0, rz), 0.005)
        B('winJ', (fw, 0.32, 0.065), P(0, -0.16, k * (h + fh) / 4), 'trim', (0, 0, rz), 0.005)
    B('winG', (w, 0.05, h), P(0, -0.10, 0), 'glass', (0, 0, rz))
    for k in (-1, 1):
        B('winM', (0.055, 0.08, h), P(k * w / 6, -0.08, 0), 'trim', (0, 0, rz))
        # 玻璃前的外框条：以玻璃边为中线、宽 0.06 → 外沿比玻璃外扩 0.03
        B('winR', (0.06, 0.06, h + 0.06), P(k * w / 2, -0.07, 0), 'trim', (0, 0, rz), 0.01)
        B('winR', (w + 0.06, 0.06, 0.06), P(0, -0.07, k * h / 2), 'trim', (0, 0, rz), 0.01)
    B('winT', (w, 0.08, 0.04), P(0, -0.08, h * 0.18), 'trim', (0, 0, rz))
    B('winS', (w + 0.25, 0.26, 0.06), P(0, 0.12, -fh / 2 - 0.03), 'stone', (0, 0, rz))
    if arch:  # 仅用于正面（-Y），panel 沿 -Y 挤出
        R = (D(90), 0, 0)
        arc = lambda n, r, t, dn, m, bv: L.panel(n, semi(r), t, P(0, dn, h / 2), R, m and M[m], bevel=bv)
        for o in (wall, inner):   # dn=-0.46 起向外挤 0.6 → 覆盖 dn -0.46~+0.14，穿透外墙与内衬
            L.boolean_cut(o, arc('arcCut', fw / 2, CUT, -0.46, None, 0))
        parts.append(arc('arcG', fw / 2 - 0.01, 0.05, -0.125, 'glass', 0.02))   # 原实心拱框板会堵洞，去掉
        B('key', (0.12, 0.06, 0.16), P(0, 0.02, h / 2 + 0.3 * fw), 'stone')

def door(wall, side, W, H, n):
    """挖门洞 → 门框衬板 + n 扇门 + 把手。"""
    P, rz = P_of(side, 0, 0.28 + H / 2)
    wall = wall[side[:2]]
    L.window_recess(wall, W, H + 0.12, 0.5, P(0, 0, -0.06), rz)
    B('doorF', (W, 0.12, H), P(0, -0.19, 0), 'woodD', (0, 0, rz))
    lw = (W - 0.16 - (n - 1) * 0.02) / n
    for i in range(n):
        u = (i - (n - 1) / 2) * (lw + 0.02)
        B('leaf', (lw, 0.08, H - 0.16), P(u, -0.11, -0.08), 'wood', (0, 0, rz))
        hu = u - math.copysign(lw / 2 - 0.08, u) if n > 1 else lw / 2 - 0.1
        C('handle', 0.03, 0.12, P(hu, -0.04, -0.15), 'metal', (D(90), 0, rz), 12)

# ── 1-2 台基 / 前廊平台 / 台阶 ──
B('plinth', (6.4, 6.4, 0.28), (0, 0, 0.14), 'stone', bv=0.05)
B('porch', (4.4, 0.82, 0.28), (0, -3.6, 0.14), 'stone', bv=0.04)
for i in range(3):
    hh = 0.09 * (3 - i)
    B('step', (1.8, 0.32, hh), (0, -4.0 - 0.16 - i * 0.32, hh / 2), 'stone')
for s in (-1, 1):
    B('cheek', (0.12, 0.96, 0.3), (s * 0.96, -4.48, 0.15), 'trim')
# ── 3-5 墙体 / 腰线 ──
def shell(name, half, t, z0, z1, bv=0.04, m='wall'):
    """四面墙板围合（顶底敞开）：前后板通长 2*half；左右板夹在其间，两端各插入前后板 2*bv —
    恰好填满双方端部倒角留下的凹槽，且两板平直外表面只在一条线上相接、无共面重叠（不闪面）。
    原点烘焙回世界原点 → window_recess 的「墙局部坐标」即世界坐标。返回 {(轴, ±1): 板}。"""
    zc, h, d, Wd = (z0 + z1) / 2, z1 - z0, half - t / 2, {}
    for s in (-1, 1):
        Wd['y', s] = B(name + 'FB'[s > 0], (2 * half, t, h), (0, s * d, zc), m, bv=bv)
        Wd['x', s] = B(name + 'LR'[s > 0], (t, 2 * (half - t + 2 * bv), h), (s * d, 0, zc), m, bv=bv)
    for o in Wd.values():
        o.data.transform(Matrix.Translation(o.location)); o.location = (0, 0, 0)
    return Wd
# 墙厚 0.3 不变：外轮廓一层 5.5 / 二层 4.8，内净 4.9 / 4.2，内墙衬板、书架、门洞切割体均按此推算
W1 = shell('wall1', 2.75, 0.3, 0.28, 3.18)
BT = B('belt', (5.86, 5.86, 0.14), (0, 0, 0.28 + 2.9 + 0.07), 'trim', bv=0.03)
W2 = shell('wall2', 2.4, 0.3, 3.25, 5.65)
# 内墙衬板也做成四面板（原点在世界原点），窗切割体可同样精确作用于它；一层 z 到楼板底、二层从楼板顶起
INNER = {'wall1': shell('inW1', 2.45, 0.02, 0.34, 3.18, 0, 'inWall'), 'wall2': shell('inW2', 2.1, 0.02, 3.32, 5.4, 0, 'inWall')}
CUT = 0.6   # 窗切割体深度 > 外墙 0.3 + 内衬 0.02，居中放置 → 内外各余 0.14
B('slab2', (4.19, 4.19, 0.14), (0, 0, 3.25), 'floor', bv=0.01)   # 二层楼板，嵌在腰线掏空的 4.2 方孔里
L.boolean_cut(BT, L.box('hollow', (4.2, 4.2, 0.5), (0, 0, 3.25), bevel=0))   # 腰线掏空，与二层内净一致
# ── 6-8 屋顶：双坡板 / 山墙 / 屋脊 / 檐口 / 齿饰 / 瓦带 / 烟囱 ──
a, zr = D(22), 6.81   # zr：屋脊处坡面上表面高度
for s in (-1, 1):
    rot = (-s * a, 0, 0)
    dvec = (s * math.cos(a), -math.sin(a))     # 沿坡向下 (y, z)
    nvec = (s * math.sin(a), math.cos(a))      # 坡面法线 (y, z)
    B('roof', (6.0, 3.4, 0.18), (0, 1.7 * dvec[0] - 0.09 * nvec[0], zr + 1.7 * dvec[1] - 0.09 * nvec[1]),
      'roof', rot, 0.03)
    for k in range(5):
        t = 0.4 + k * 0.65
        B('tile', (6.0, 0.06, 0.04), (0, t * dvec[0] + 0.04 * nvec[0], zr + t * dvec[1] + 0.04 * nvec[1]),
          'ridge', rot)
    for k in range(6):  # 顺坡瓦垄，沿 X 等距，与横向瓦带成网格
        B('rib', (0.05, 3.4, 0.03), (-2.5 + k, 1.7 * dvec[0] + 0.035 * nvec[0], zr + 1.7 * dvec[1] + 0.035 * nvec[1]),
          'ridge', rot, 0.005)
    parts.append(L.panel('gable', [(-2.4, 0), (2.4, 0), (0, 2.4 * math.tan(a))], 0.2,
                         (s * 2.3 - 0.1, 0, 5.65), (D(90), 0, D(90)), M['wall'], 0.02))
    B('eaveFB', (5.5, 0.35, 0.1), (0, s * 2.575, 5.55), 'trim')
    B('eaveLR', (0.35, 5.5, 0.1), (s * 2.575, 0, 5.55), 'trim')
    for k in range(12):
        u = -2.2 + k * 0.4
        B('dentil', (0.1, 0.12, 0.08), (u, s * 2.46, 5.46), 'trim')
        B('dentil', (0.12, 0.1, 0.08), (s * 2.46, u, 5.46), 'trim')
C('ridgeBar', 0.12, 6.09, (0, 0, zr), 'ridge', (0, D(90), 0))
B('chimney', (0.5, 0.5, 0.9), (1.6, 1.0, zr - 1.0 * math.tan(a) + 0.25), 'book1', bv=0.03)
B('chimCap', (0.62, 0.62, 0.08), (1.6, 1.0, zr - 1.0 * math.tan(a) + 0.74), 'trim')
# ── 9-11 雨篷 / 廊柱 / 招牌 ──
parts.append(L.panel('canopy', [(-2.1, -2.75), (2.1, -2.75), (2.1, -3.85), (-2.1, -3.85)], 0.16,
                     (0, 0, 3.12), material=M['trim'], bevel=0.03))
# 雨篷挑出 1.1，由 4 片三角托架（墙面 z2.52 → 雨篷底外挑 0.9）支撑；托架厚 0.06，
# x=±0.94 / ±1.715 恰落在 门洞|x|≤0.85、窗洞 1.035~1.665 两侧的墙垛上，正视投影不压门不压窗
# 外侧 2 根廊柱（中间挡门的 2 根已删）：x=±1.92 立在前廊平台顶 z0.28 上，顶到雨篷底 z3.12；
# 柱脚/柱头圆盘 r0.15 → |x| 1.77~2.07，外不出雨篷 ±2.1、内不碰 x±1.715 托架（外沿 1.745）
for s in (-1, 1):
    C('colBase', 0.15, 0.08, (s * 1.92, -3.55, 0.32), 'trim')
    C('colShaft', 0.11, 2.68, (s * 1.92, -3.55, 1.70), 'wall')
    C('colCap', 0.15, 0.08, (s * 1.92, -3.55, 3.08), 'trim')
for x in (-1.715, -0.94, 0.94, 1.715):
    parts.append(L.panel('bracket', [(0, 0), (-0.9, 0), (0, -0.6)], 0.06, (x - 0.03, -2.75, 3.12),
                         (D(90), 0, D(90)), M['woodD'], 0.01))
B('signBack', (3.06, 0.04, 0.78), (0, -3.72, 3.55), 'woodD')
B('sign', (2.9, 0.08, 0.62), (0, -3.78, 3.55), 'wood', bv=0.03)   # 板面 y=-3.82
cu = bpy.data.curves.new(name='signText', type='FONT')   # 内置 Bfont
cu.body = "Shen's Library"
cu.align_x, cu.align_y = 'CENTER', 'CENTER'
cu.size, cu.extrude, cu.bevel_depth, cu.bevel_resolution = 0.28, 0.012, 0.004, 2
txt = bpy.data.objects.new('signText', cu)
bpy.context.collection.objects.link(txt)
txt.location, txt.rotation_euler = (0, -3.832, 3.55), (D(90), 0, 0)   # 立在 XZ 面、朝 -Y，背面嵌入板 4mm
txt.data.materials.append(M['ink'])
L.select_only([txt])
bpy.ops.object.convert(target='MESH')
parts.append(bpy.context.view_layer.objects.active)
# ── 12-17 门窗（布尔挖凹洞） ──
F1, B1, F2, B2 = ('y', -1, 2.75), ('y', 1, 2.75), ('y', -1, 2.4), ('y', 1, 2.4)
# 正门：1.7×2.3×0.5 切割体（y 内移到 -2.6 才能切穿 0.3 厚墙）+ 洞内衬 + 两扇外开门
for o in (W1['y', -1], INNER['wall1']['y', -1]):   # 外墙 + 一层前内衬（y -2.45~-2.43）同切
    L.boolean_cut(o, L.box('doorCut', (1.7, 0.5, 2.3), (0, -2.6, 0.28 + 1.15), bevel=0))
for s in (-1, 1):
    B('doorJamb', (0.06, 0.3, 2.3), (s * 0.82, -2.6, 1.43), 'wall', bv=0.01)
B('doorHead', (1.7, 0.3, 0.06), (0, -2.6, 2.55), 'wall', bv=0.01)
for s in (-1, 1):  # s=±1：右/左扇，铰链在门洞外侧竖边 (±0.85, -2.78)
    th = s * D(95)
    tpl = L.box('leafTpl', (0.82, 0.05, 2.22), material=M['wood'], bevel=0.01)
    tpl.data.transform(Matrix.Translation((-s * 0.41, 0, 0)))   # 原点移到铰链边，门板朝洞中心伸出
    parts.append(L.dupe(tpl, (s * 0.85, -2.78, 1.42), (0, 0, th)))
    bpy.data.objects.remove(tpl, do_unlink=True)
    lx = -s * 0.72   # 把手：门板本地 x，随门板一起转 th
    C('handle', 0.02, 0.16, (s * 0.85 + lx * math.cos(th), -2.78 + lx * math.sin(th), 1.35), 'metal',
      (D(90), 0, th), 12)
B('doormat', (0.7, 0.4, 0.02), (0, -2.98, 0.29), 'dark')
# 正面（-Y）不开窗：shell() 建出的前墙板完整，一层只切上面的门洞，二层前墙不切
for s in (-1, 1):
    for u in (-1.3, 1.3):
        win(W1, ('x', s, 2.75), u, 1.55, 0.9, 1.2)
        win(W2, ('x', s, 2.4), u * 0.85, 4.45, 0.9, 1.1)
door(W1, B1, 1.2, 2.1, 1)
for u in (-1.6, 1.6):
    win(W1, B1, u, 1.6, 0.7, 0.9)
    win(W2, B2, u * 0.75, 4.45, 0.7, 0.9)
# ── 18-19 落水管 / 踢脚 / 壁柱 ──
for sx in (-1, 1):
    for sy in (-1, 1):
        C('pipe', 0.06, 3.3, (sx * 2.83, sy * 2.55, 1.65), 'dark', v=12)
        C('pipeUp', 0.06, 2.3, (sx * 2.48, sy * 2.2, 4.47), 'dark', v=12)
        B('pilaster', (0.1, 0.1, 2.9), (sx * 2.77, sy * 2.77, 0.28 + 1.45), 'wall')
for s, gap in ((-1, 0.88), (1, 0.6)):
    ln = 2.81 - gap
    for k in (-1, 1):
        B('skirt', (ln, 0.06, 0.12), (k * (gap + ln / 2), s * 2.76, 0.34), 'trim')
    B('skirt', (0.06, 5.62, 0.12), (s * 2.76, 0, 0.34), 'trim')
# ── 20 环境小物 ──
B('returnBox', (0.45, 0.4, 0.55), (-2.9, -3.6, 0.275), 'wood')
B('returnLid', (0.5, 0.45, 0.04), (-2.9, -3.62, 0.58), 'trim', (D(15), 0, 0))
B('benchSeat', (0.9, 0.35, 0.08), (2.9, -3.6, 0.42), 'wood')
B('benchBack', (0.9, 0.06, 0.3), (2.9, -3.43, 0.64), 'wood')
for lx in (-0.38, 0.38):
    for ly in (-0.13, 0.13):
        C('benchLeg', 0.04, 0.4, (2.9 + lx, -3.6 + ly, 0.2), 'dark', v=12)
for bx in (-1.6, 1.6):
    B('bed', (0.9, 0.9, 0.4), (bx, -4.5, 0.2), 'stone', bv=0.04)
    B('bedGrass', (0.78, 0.78, 0.06), (bx, -4.5, 0.38), 'grass')
    for j, (fx, fy) in enumerate(((0, 0), (0.22, 0.22), (-0.22, 0.22), (0.22, -0.22), (-0.22, -0.22))):
        S('flower', 0.06, (bx + fx, -4.5 + fy, 0.47), 'flwA' if j % 2 else 'flwB')
# 路灯立在长椅右端外侧：长椅座面 x 2.45~3.35，灯座 r0.14 → x 3.46~3.74，净距 0.11，y 与座面中心对齐
LX, LY = 3.6, -3.6
C('LGT_outdoor_base', 0.14, 0.1, (LX, LY, 0.05), 'dark')
C('LGT_outdoor_pole', 0.05, 1.6, (LX, LY, 0.9), 'dark', v=12)
S('LGT_outdoor_bulb', 0.12, (LX, LY, 1.76), 'LGT_outdoor')
C('LGT_outdoor_cap', 0.15, 0.04, (LX, LY, 1.9), 'dark')
for k, by in enumerate((-1.0, -0.65)):
    for j in range(4):
        B('book', (0.22, 0.16, 0.05), (-3.6, by, 0.025 + j * 0.05), ('book1', 'book2', 'book3')[(j + k) % 3],
          (0, 0, (j % 2) * 0.25 - 0.1 + k * 0.15))
for k in (-1, 1):
    C('signPost', 0.04, 0.9, (3.7 + k * 0.26, -2.3, 0.45), 'wood', v=12)
B('signPanel', (0.6, 0.04, 0.4), (3.7, -2.33, 0.8), 'wood', (D(-15), 0, 0))
# 板面正面法线 = Rx(-15°)·(0,-1,0) = (0,-cos15,sin15)；文字 Rx(75°) 同朝此向，中心沿法线外移 半厚0.02 + 挤出0.012 → 背面贴板
cu = bpy.data.curves.new(name='SIGN_welcome', type='FONT')
cu.body, cu.align_x, cu.align_y = 'welcome!', 'CENTER', 'CENTER'
cu.size, cu.extrude, cu.bevel_depth, cu.bevel_resolution = 0.1, 0.012, 0.003, 2
sw = bpy.data.objects.new('SIGN_welcome', cu)
bpy.context.collection.objects.link(sw); bpy.context.view_layer.update()
cu.size *= 0.5 / sw.dimensions.x   # 拉到 0.5 宽：板宽 0.6，左右各留 0.05
nv = Vector((0, -math.cos(D(15)), math.sin(D(15))))
sw.location, sw.rotation_euler = Vector((3.7, -2.33, 0.8)) + 0.032 * nv, (D(75), 0, 0)
sw.data.materials.append(M['ink'])
L.select_only([sw]); bpy.ops.object.convert(target='MESH'); sw = bpy.context.view_layer.objects.active; parts.append(sw)
for bx, by in ((-3.6, -2.2), (3.6, 0.5)):
    C('bin', 0.22, 0.5, (bx, by, 0.25), 'dark')
    C('binLid', 0.24, 0.05, (bx, by, 0.525), 'trim')

# ── 21 室内：地板 / 内墙衬板 / 书架 / 服务台 / 阅览桌椅 / 吊灯 ──
B('floor', (4.8, 4.8, 0.06), (0, 0, 0.31), 'floor', bv=0.01)
B('ceil', (4.2, 4.2, 0.02), (0, 0, 5.39), 'inWall', bv=0)
rnd = random.Random(7)
def shelf(cx, cy, zb, W, rz, n):
    """书架（u 沿架长、v 指向墙）：背板 + 侧板 + 5 层板，4 层 × n 本书（4 本一簇，四色轮换，前后随机错位）。"""
    c, sn, R = math.cos(rz), math.sin(rz), (0, 0, rz)
    P = lambda u, v, z: (cx + u * c - v * sn, cy + u * sn + v * c, zb + z)
    B('shBack', (W, 0.02, 1.17), P(0, 0.15, 0.585), 'woodD', R, 0)
    for k in (-1, 1):
        B('shSide', (0.04, 0.32, 1.17), P(k * (W / 2 - 0.02), 0, 0.585), 'woodD', R, 0.01)
    for t in range(5):
        B('shBoard', (W, 0.32, 0.02), P(0, 0, t * 0.2875 + 0.01), 'woodD', R, 0.005)
    for t in range(4):   # 书顶 0.30 落在上层板厚度内，不穿出板面
        for j in range(n):
            cl, b = divmod(j, 4)
            u = (cl + 0.5) * W / (n // 4) - W / 2 + (b - 1.5) * 0.065
            B('book', (0.06, 0.2, 0.28), P(u, 0.03 + rnd.uniform(-0.03, 0.02), t * 0.2875 + 0.16),
              ('book1', 'book2', 'book3', 'trim')[(j + t) % 4], R, 0)
for g in range(2):   # 后墙：2 组上下叠（顶 2.68 < 楼板底 3.18），宽 2.2 夹在后窗 |x|≥1.185 之间，不挡窗
    shelf(0, 1.92, 0.34 + g * 1.17, 2.2, 0, 8)
for s in (-1, 1):    # 左右墙：各 2 组上下叠，y -0.19~0.71 与 1.86~2.42，避开服务台与侧窗
    for g in range(2):   # 拆成两段，避开侧窗 y 0.785~1.815
        for cy, W in ((0.26, 0.9), (2.14, 0.56)):
            shelf(s * 2.27, cy, 0.34 + g * 1.17, W, -s * D(90), 4)
B('desk', (2.4, 0.7, 1.05), (1.05, -0.6, 0.865), 'wood')
B('deskTop', (2.52, 0.82, 0.04), (1.05, -0.6, 1.41), 'trim', bv=0.01)
for tx, ty in ((-1.15, 0.75), (1.15, 0.75)):
    B('table', (1.5, 0.85, 0.06), (tx, ty, 1.09), 'wood', bv=0.015)
    for lx in (-0.65, 0.65):
        for ly in (-0.32, 0.32):
            C('tLeg', 0.045, 0.72, (tx + lx, ty + ly, 0.70), 'woodD', v=12)
    for k in (-1, 1):   # 长边两侧各一把椅子，靠背朝外
        cy = ty + k * 0.62
        B('seat', (0.42, 0.42, 0.06), (tx, cy, 0.82), 'wood', bv=0.015)
        B('chairBack', (0.42, 0.04, 0.45), (tx, cy + k * 0.19, 1.075), 'wood', bv=0.01)
        for lx in (-0.17, 0.17):
            for ly in (-0.17, 0.17):
                C('cLeg', 0.02, 0.45, (tx + lx, cy + ly, 0.565), 'woodD', v=8)
    for zt, k in ((3.18, None), (5.38, 'ceiling2F' if tx < 0 else 'ceiling2F_b')):   # 一层吊在楼板底 / 二层吊在顶棚下（左 A 右 B，各用独立材质）
        nm = lambda s: f'LGT_{k}_{s.lower()}' if k else 'lamp' + s
        C(nm('Rod'), 0.02, 0.5, (tx, ty, zt - 0.25), 'dark', v=8)
        C(nm('Shade'), 0.22, 0.12, (tx, ty, zt - 0.56), 'metal')
        S(nm('Bulb'), 0.1, (tx, ty, zt - 0.64), 'LGT_' + k if k else 'lamp')
# 一层中央吊灯：挂楼板底 z3.18，房间中心 (0,0)；顶座 → 吊杆 → 发光芯筒 + 6 辐条 → 外环 r0.40 → 6 只垂吊球
# 最低点 z2.42（地板顶 0.34 上净高 2.08，不挡视线）；外缘 r0.48 < 桌灯灯罩内缘 |x|0.93，与服务台顶 1.43 远离
C('LGT_ceiling1F_canopy', 0.12, 0.04, (0, 0, 3.16), 'metal')
C('LGT_ceiling1F_rod', 0.012, 0.42, (0, 0, 2.93), 'dark', v=8)
C('LGT_ceiling1F_cap', 0.2, 0.02, (0, 0, 2.73), 'metal')
C('LGT_ceiling1F_core', 0.16, 0.1, (0, 0, 2.67), 'LGT_ceiling1F')
bpy.ops.mesh.primitive_torus_add(major_radius=0.4, minor_radius=0.015, major_segments=48, minor_segments=8, location=(0, 0, 2.67))
rg = bpy.context.view_layer.objects.active; rg.name = 'LGT_ceiling1F_ring'; rg.data.materials.append(M['metal']); parts.append(rg)
for i in range(6):
    a = i * D(60); ca, sa = math.cos(a), math.sin(a)
    B('LGT_ceiling1F_spoke', (0.24, 0.015, 0.015), (0.28 * ca, 0.28 * sa, 2.67), 'metal', (0, 0, a), 0)
    C('LGT_ceiling1F_drop', 0.006, 0.1, (0.4 * ca, 0.4 * sa, 2.62), 'dark', v=6)
    S('LGT_ceiling1F_globe', 0.075, (0.4 * ca, 0.4 * sa, 2.495), 'LGT_ceiling1F')
# ── 22 二层（楼板顶 z=3.32）：后墙白板 / 中央实验台 / 前部两个工位（屏幕朝拱窗） ──
B('wbFrame', (1.4, 0.04, 1.0), (0, 2.06, 4.45), 'metal', bv=0.01)
B('whiteboard', (1.3, 0.02, 0.9), (0, 2.03, 4.45), 'inWall', bv=0)
B('labBench', (2.0, 0.75, 0.85), (0, 0.6, 3.745), 'trim')
B('labTop', (2.1, 0.85, 0.05), (0, 0.6, 4.195), 'dark', bv=0.01)
for j, x in enumerate((-0.6, -0.3, 0.3, 0.6)):
    C('beaker', 0.05, 0.18, (x, 0.6, 4.31), ('book2', 'book3')[j % 2], v=12)
for x in (-1.1, 1.1):
    B('wsDesk', (1.2, 0.6, 0.04), (x, -1.2, 4.06), 'wood', bv=0.01)
    for k in (-1, 1):
        B('wsLeg', (0.04, 0.56, 0.72), (x + k * 0.56, -1.2, 3.68), 'woodD', bv=0.005)
    B('wsNeck', (0.05, 0.03, 0.1), (x, -0.98, 4.13), 'dark', bv=0)
    B('monitor', (0.5, 0.03, 0.32), (x, -0.98, 4.34), 'dark', bv=0.01)
    B('screen', (0.46, 0.005, 0.28), (x, -0.997, 4.34), 'lamp', bv=0)
    C('wsPost', 0.03, 0.43, (x, -1.75, 3.535), 'dark', v=8)
    B('wsSeat', (0.42, 0.42, 0.06), (x, -1.75, 3.78), 'wood', bv=0.015)
    B('wsBack', (0.42, 0.04, 0.4), (x, -1.94, 4.03), 'wood', bv=0.01)

# ── 临时自检：墙板数 / 一层内净 / 洞口对齐 / 家具是否切入墙板 ──
bpy.context.view_layer.update()
wv = lambda o: [o.matrix_world @ Vector(v) for v in o.bound_box]
bb = lambda o: [(min(v[i] for v in wv(o)), max(v[i] for v in wv(o))) for i in range(3)]
print(f'CHK panels: floor1={len(W1)} floor2={len(W2)}')
ix = bb(W1['x', 1])[0][0] - bb(W1['x', -1])[0][1]; iy = bb(W1['y', 1])[1][0] - bb(W1['y', -1])[1][1]
print(f'CHK floor1 inner net: {ix:.3f} x {iy:.3f}')
# 通孔判据：从墙外 0.2 沿内法线射 0.8（到 dn=-0.6），外墙板与内衬板都 ray_cast 不中 → 贯穿
th = lambda o, n: bb(o)[n][1] - bb(o)[n][0]
res = [(wl.name, f'{th(wl, n):.2f}', inn.name, f'{th(inn, n):.2f}', wl['cut_depth'],
        all(not o.ray_cast(Vector(p), dv, distance=0.8)[0] for o in (wl, inn) for p in tp))
       for wl, inn, tp, dv, n, *_ in CHK]
for r in res:
    print('CHECK hole', r)
for f in '12':
    print(f'CHECK floor{f} windows through: {sum(r[-1] for r in res if r[0][4] == f)}/{sum(r[0][4] == f for r in res)}')
print('CHECK ray_sanity solid pier hit =', W1['y', -1].ray_cast(Vector((0.94, -3.0, 1.5)), Vector((0, 1, 0)), distance=0.8)[0])
print('CHECK cut_pairs', [(w.name, w.get('cut_depth', 0)) for d in (W1, W2, *INNER.values()) for w in d.values()])
# 转角 / 腰线余量：洞边到内净面（一层 2.43 / 二层 2.08）、一层洞顶到楼板底 3.18、二层洞底到楼板顶 3.32
print('CHECK min corner margin', round(min((2.43 if c[0].name[4] == '1' else 2.08) - c[5] for c in CHK), 3),
      'belt margin', round(min(3.18 - c[6] - c[7] / 2 if c[0].name[4] == '1' else c[6] - c[7] / 2 - 3.32 for c in CHK), 3))
print('CHECK columns', [(c.name, round(c.location.x,2), round(c.location.y,2)) for c in parts if c.name.lower().startswith('col')])
cols, cb = [c for c in parts if c.name.lower().startswith('col')], bb(next(o for o in parts if o.name.startswith('canopy')))
print('CHECK columns detail: min|x| edge', round(min(min(abs(bb(c)[0][0]), abs(bb(c)[0][1])) for c in cols), 3),
      'in_door', [c.name for c in cols if bb(c)[0][0] < 0.85 and bb(c)[0][1] > -0.85],
      'top', round(max(bb(c)[2][1] for c in cols), 3), 'canopy bottom', round(cb[2][0], 3),
      'bottom', round(min(bb(c)[2][0] for c in cols), 3))
blk = [o.name for o in parts if o.name.split('.')[0] not in ('leaf', 'handle') and bb(o)[1][1] < -2.75 + 1e-4 and
       bb(o)[0][0] < 0.85 and bb(o)[0][1] > -0.85 and bb(o)[2][0] < 2.58 and bb(o)[2][1] > 0.31]
print('CHECK columns_not_blocking', not blk, blk[:5], '判据: 墙面 y=-2.75 以外、AABB 落入门洞 |x|<0.85 且 z 0.31~2.58 的构件数=0（门扇/把手本身除外）')
FURN = ('shBack', 'shSide', 'shBoard', 'book', 'desk', 'deskTop', 'table', 'tLeg', 'seat', 'chairBack', 'cLeg', 'floor')
hit = [o.name for o in parts if o.name.split('.')[0] in FURN and max(map(abs, o.location[:2])) < 2.75 and
       any(abs(c) > (2.45 if bb(o)[2][1] < 3.25 else 2.1) + 1e-4 for c in (*bb(o)[0], *bb(o)[1]))]
print(f'CHK furniture beyond inner face: {len(hit)} {hit[:5]}')
nomat = [o.name for o in parts if not o.active_material]
print(f'SELFTEST parts={len(parts)} no_material={len(nomat)} {nomat[:5]}')
assert not nomat
# 正面通孔：5cm 网格从 y-3.0 沿 +Y 射 1.0，外墙板与内衬都不中 = 通孔格；4 邻接连通块数 = 洞数（门洞算 1）
def front_holes(f, z0, z1):
    g = {(i, j) for i in range(-52, 53) for j in range(int(z0 * 20), int(z1 * 20)) if not any(o.ray_cast(
         Vector((i / 20, -3.0, j / 20)), Vector((0, 1, 0)), distance=1.0)[0] for o in ((W1, W2)[f - 1]['y', -1], INNER[f'wall{f}']['y', -1]))}
    n = 0
    while g:
        n += 1; st = [g.pop()]
        while st:
            i, j = st.pop()
            for c in ((i + 1, j), (i - 1, j), (i, j + 1), (i, j - 1)):
                if c in g: g.remove(c); st.append(c)
    return n
print('CHECK front_holes_1F', front_holes(1, 0.3, 3.15), '期望 1（仅大门）')
print('CHECK front_holes_2F', front_holes(2, 3.3, 5.6), '期望 0')
print('CHECK side_windows', {k: sum(c[0].name[5] == k for c in CHK) for k in 'LRB'}, '应与改前一致（改前 L4 R4 B4）')
# ── 18 二层正面阳台：底板 + 2 根 45° 斜撑（栏杆下一轮）──
# 底板顶 z3.65 < 二层窗台底 3.675；底 3.50 > 腰线顶 3.32 / 雨篷顶 3.28；外沿 y-3.60 距招牌背板 -3.70 余 0.1
B('BAL_slab', (4.8, 1.22, 0.15), (0, -2.99, 3.575), 'trim', bv=0.03)
# 斜撑 x=±2.25 在雨篷 ±2.1、廊柱 2.07 之外：脚落一层墙面 (y-2.75, z2.65)，45° 上斜到底板外沿底 (y-3.60, z3.50)；
# 过腰线外沿 y-2.93 处杆顶 z≈2.90 < 腰线底 3.18，不穿插
for s in (-1, 1):
    B('BAL_strut', (0.1, 0.85 * math.sqrt(2), 0.1), (s * 2.25, -3.175, 3.075), 'wood', (D(-45), 0, 0), 0.01)
print('CHECK balcony_slab', [ (o.name, round(o.location.z,2)) for o in parts if o.name.startswith('BAL_') ])
# ── 19 阳台三面栏杆：尺寸取 BAL_slab 实际包围盒；扶手/下横杆各三段，侧段外端多伸 t/2 与前段在角柱处搭接 ──
bpy.context.view_layer.update(); sb = bb(next(o for o in parts if o.name == 'BAL_slab'))
x1, y1, yw, zt = sb[0][1] - 0.05, sb[1][0] + 0.05, sb[1][1] - 0.02, sb[2][1]   # 外沿内收 0.05；yw=二层墙外皮 -2.40
RH, SP = 0.8, 0.12   # 扶手顶 0.8m（约二层墙高 2.4 的 1/3，原 1.0 显得像围墙）；立柱目标间距 12cm
hr = []
for nm, z, t in (('BAL_handrail', zt + RH - 0.035, 0.07), ('BAL_lowrail', zt + 0.12, 0.04)):
    o = [B(nm, (2 * x1 + t, t, t), (0, y1, z), 'woodD', bv=0.01)]
    o += [B(nm, (t, yw - y1 + t / 2, t), (s * x1, (yw + y1 - t / 2) / 2, z), 'woodD', bv=0.01) for s in (-1, 1)]
    hr += o if nm == 'BAL_handrail' else []
for s in (-1, 1):   # 角柱 ×2 + 靠墙端柱 ×2，0.07 方，略粗于 Ø0.03 立柱
    for y in (y1, yw - 0.035):
        B('BAL_post', (0.07, 0.07, RH), (s * x1, y, zt + RH / 2), 'woodD', bv=0.01)
segs = [((-x1, y1), (x1, y1))] + [((s * x1, y1), (s * x1, yw - 0.035)) for s in (-1, 1)]
nb, sps = 0, []
for (ax, ay), (bx, by) in segs:
    n = round(math.hypot(bx - ax, by - ay) / SP); sps.append(round(math.hypot(bx - ax, by - ay) / n, 3))
    for i in range(1, n):
        C('BAL_baluster', 0.015, RH - 0.19, (ax + (bx - ax) * i / n, ay + (by - ay) * i / n, zt + 0.12 + (RH - 0.19) / 2), 'trim', v=8); nb += 1
bpy.context.view_layer.update(); F = bb(hr[0])   # 侧段须与前段 x、y 区间都有重叠（角部搭接），且后端顶到墙皮
ok = all(F[0][0] - 1e-4 <= bb(o)[0][0] and bb(o)[0][1] <= F[0][1] + 1e-4 and bb(o)[1][0] <= F[1][1] and bb(o)[1][1] >= yw - 1e-4 for o in hr[1:])
print('CHECK rail_posts', nb, '+4 角/端柱', 'spacing≈', sps)
print('CHECK rail_handrail', [o.name for o in hr], '闭合连续' if ok else '有断口')
pt = max(bb(o)[2][1] for o in parts if o.name.startswith(('BAL_post', 'BAL_baluster')))
print('CHECK rail_height', round(F[2][1] - zt, 3), '立柱顶', round(pt - zt, 3))
# ── 20 阳台门：二层前墙 wall2F（y-2.40~-2.10，厚 0.3）与内衬 inW2F（y-2.10~-2.08）同切，切深 CUT=0.6 → y-2.55~-1.95 贯穿；
# 洞 |x|≤0.45 远离栏杆靠墙端柱 x±2.35；洞底 = 底板顶 3.65 > 腰线顶 3.32，洞顶 5.35 < 吊顶 5.39 → 不切栏杆、不切腰线
DW, DH, DZ, BA = 0.9, 1.7, 3.65 + 0.85, D(95)
for o in (W2['y', -1], INNER['wall2']['y', -1]):
    L.boolean_cut(o, L.box('BAL_doorCut', (DW, CUT, DH), (0, -2.25, DZ), bevel=0))
for s in (-1, 1):   # 内衬与一层大门同为 'wall'，深 0.32 盖住墙 + 内衬
    B('BAL_doorJamb', (0.06, 0.32, DH), (s * (DW / 2 - 0.03), -2.24, DZ), 'wall', bv=0.01)
    B('BAL_doorHead' if s > 0 else 'BAL_doorSill', (DW, 0.32, 0.06), (0, -2.24, DZ + s * (DH / 2 - 0.03)), 'wall', bv=0.01)
tpl = L.box('leafTpl', (0.86, 0.05, DH - 0.1), material=M['wood'], bevel=0.01)
tpl.data.transform(Matrix.Translation((-0.43, 0, 0)))   # 同一层大门：原点移到铰链边，铰链在门框外侧竖边 (x+0.45, 墙外皮 y-2.43)
dr = L.dupe(tpl, (DW / 2, -2.43, DZ), (0, 0, BA)); dr.name = 'BAL_door'; parts.append(dr)
bpy.data.objects.remove(tpl, do_unlink=True)
C('BAL_doorHandle', 0.02, 0.16, (DW / 2 - 0.76 * math.cos(BA), -2.43 - 0.76 * math.sin(BA), DZ - 0.1), 'metal', (D(90), 0, BA), 12)
bpy.context.view_layer.update(); hb = bb(W2['y', -1])
print('CHECK balcony_door_hole', front_holes(2, 3.3, 5.6) == 1, '门洞尺寸', DW, 'x', DH, '中心', (0, -2.25, DZ), '墙厚', round(hb[1][1] - hb[1][0], 3), '切深', CUT)
print('CHECK balcony_door_angle_deg', round(math.degrees(dr.rotation_euler.z), 1))
print('CHECK lamp_pos', [(o.name, round(o.location.x,2), round(o.location.y,2)) for o in parts if o.name.startswith('LGT_outdoor')][:4])
print('CHECK lights', {k: (v['on'], v['strength']) for k,v in LIGHTS.items()})
print('CHECK light_materials', [m.name for m in bpy.data.materials if m.name.startswith('LGT_')])
print('CHECK light_objects', {k: [o.name for o in parts if o.name.startswith('LGT_'+k)] for k in LIGHTS})
print('CHECK bench_pos', [(o.name, tuple(round(c, 2) for c in o.location)) for o in parts if o.name.startswith('bench')][:2])
print('CHECK sign_text', sw.name, '内容', 'welcome!', 'dims', tuple(round(c, 3) for c in sw.dimensions))
merged = L.join_by_material(parts)
os.makedirs('out/models', exist_ok=True)
L.export_glb(os.path.abspath('out/models/library.glb'), merged)
