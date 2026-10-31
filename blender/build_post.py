# 邮政局 / post —— 第 2 栋，本轮只做主体骨架（无门窗、内饰、招牌）
import sys, os; sys.path.insert(0, os.path.dirname(__file__)); from lib_building import *

BV = {'L': (0.12, 12), 'M': (0.05, 8), 'S': (0.01, 5)}

# 可开关灯（查看器靠 LGT_ 前缀生成开关；默认全关，strength 由查看器使用）
LIGHTS = {'post_ceiling': {'on': False, 'strength': 3.0}, 'post_sign': {'on': False, 'strength': 2.0}}

def light_mat(name, hexcolor, on, strength):
    m = mat(name, hexcolor, roughness=0.4)
    bsdf = m.node_tree.nodes.get('Principled BSDF')
    if bsdf:
        r, g, b = (srgb_to_linear(int(hexcolor.lstrip('#')[i:i+2], 16)/255) for i in (0, 2, 4))
        bsdf.inputs['Emission Color'].default_value = (r, g, b, 1.0)
        bsdf.inputs['Emission Strength'].default_value = strength if on else 0.0
    return m

def b(name, size, loc, material, lv):
    return box(name, size, loc, (0, 0, 0), material, bevel=BV[lv][0], seg=BV[lv][1])

reset_scene()

# 材质
wall = mat('WALL', '#7FBF9A')    # 薄荷绿
base = mat('BASE', '#EDE6DA')    # 米白
floor = mat('FLOOR', '#C9A57B')  # 暖木
roof = mat('ROOF', '#5E9C7A')    # 深绿
shutter = mat('SHUTTER', '#E8E2D5')         # 米白帘面
shutter_rail = mat('SHUTTER_RAIL', '#8C8C8C')  # 灰导轨
winframe = mat('WINFRAME', '#F2EFE6')           # 米白窗框
glass = mat('GLASS', '#A8C8E8', roughness=0.05, alpha=0.32)  # 透明淡蓝 + alpha 0.32 可见色
_gb = next((n for n in glass.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
if _gb and 'Specular IOR Level' in _gb.inputs:
    _gb.inputs['Specular IOR Level'].default_value = 0.1  # 压低高光，避免"白板"感
if _gb:  # 加一点淡蓝自发光：室内暗时也能一眼看出是"淡蓝色玻璃"
    try:
        _gb.inputs['Emission Color'].default_value = (0.42, 0.62, 0.88, 1.0)
        _gb.inputs['Emission Strength'].default_value = 0.22
    except Exception:
        pass
glass.use_backface_culling = False

parts = []
# 台基 z: -0.18 ~ 0
parts.append(b('Base', (6.8, 6.8, 0.18), (0, 0, -0.09), base, 'L'))
# 室内地板 z: 0 ~ 0.12
parts.append(b('Floor', (6.0, 6.0, 0.12), (0, 0, 0.06), floor, 'M'))

# 四面墙（空心，四角搭接，不封顶）z: 0.12 ~ 3.72
parts.append(b('Wall_Front', (6.4, 0.22, 3.6), (0, -3.0, 1.92), wall, 'L'))
parts.append(b('Wall_Back',  (6.4, 0.22, 3.6), (0,  3.0, 1.92), wall, 'L'))
parts.append(b('Wall_Left',  (0.22, 6.4, 3.6), (-3.0, 0, 1.92), wall, 'L'))
parts.append(b('Wall_Right', (0.22, 6.4, 3.6), ( 3.0, 0, 1.92), wall, 'L'))

# 正面开洞：window_recess 的 loc 是墙局部坐标，墙原点在 z=1.92 → 局部 z = 世界 z - 1.92
front = [p for p in parts if p.name == 'Wall_Front'][0]
WZ = 1.92
# 先应用墙的 Bevel/WeightedNormal：否则布尔切在原始网格上，洞口边缘的倒角会把开口重新封住
apply_all_modifiers(front)
# 卷帘门洞 4.00×2.70，世界 z 0.12~2.82；底边向下多切 0.02 避免与墙底共面
window_recess(front, w=4.00, h=2.72, depth=0.60, loc=(1.05, 0, (0.10 + 2.82) / 2 - WZ))
# 窗洞 1.60×1.60，世界 x -2.85~-1.25，z 1.00~2.60（距门洞左缘 -0.95 留 0.30 墙垛）
window_recess(front, w=1.60, h=1.60, depth=0.60, loc=(-2.05, 0, 1.80 - WZ))

# 卷起的卷帘：卷轴（沿 X 横放，长度缩短 0.04 避免两端与导轨共面）+ 半垂帘片 + 两侧导轨，均外凸于墙面 y≈-3.11
parts.append(cyl('Shutter_Roll', radius=0.17, height=3.96, loc=(1.05, -3.02, 2.95),
                 rot=(0, math.pi / 2, 0), material=shutter, verts=32))
parts.append(b('Shutter_Slat', (3.96, 0.06, 0.32), (1.05, -3.05, 2.72), shutter, 'S'))
rz = (0.125 + 2.84) / 2  # 底部从 z=0.125 开始，避免与地板 z=0.12 共面
# 导轨左右各向门洞外跨 0.02，盖住门洞切面（门洞 x -0.950~3.050）
parts.append(b('Shutter_Rail_L', (0.09, 0.12, 2.715), (1.05 - 2.00 - 0.045 - 0.02, -3.04, rz), shutter_rail, 'S'))  # x 中心左移 0.02
parts.append(b('Shutter_Rail_R', (0.09, 0.12, 2.715), (1.05 + 2.00 + 0.045 + 0.02, -3.04, rz), shutter_rail, 'S'))  # x 中心右移 0.02

# 窗框：上下横条 + 左右竖条 + 中竖梃，框厚 0.16 骑在墙面 y≈-3.11（外凸 0.08、埋进 0.08）
# 框条 X/Z 方向超出洞口 0.03，避免侧面与洞口切面共面；整体沿 -Y 外移 0.015 避免与洞内侧共面
# 四条边各向洞口内跨进 0.025，盖住洞口切面，避免与切面重合导致 z-fighting
parts.append(b('Win_Top',    (1.69, 0.16, 0.09), (-2.05, -3.080, 2.625), winframe, 'S'))  # z 中心下移 0.020
parts.append(b('Win_Bottom', (1.69, 0.16, 0.09), (-2.05, -3.080, 0.975), winframe, 'S'))  # z 中心上移 0.020
parts.append(b('Win_Left',   (0.09, 0.16, 1.69), (-2.875, -3.080, 1.80), winframe, 'S'))  # x 中心右移 0.020
parts.append(b('Win_Right',  (0.09, 0.16, 1.69), (-1.225, -3.080, 1.80), winframe, 'S'))  # x 中心左移 0.020
parts.append(b('Win_Mullion', (0.05, 0.16, 1.60), (-2.05, -3.080, 1.80), winframe, 'S'))

# 两扇窗扇朝外(-Y)大开 150°：铰链 x=-2.82 / -1.28 不变，扇宽 0.77 不变；
# 铰链 y 由 -3.00 外挑到 -3.235（与左墙前端齐平），再往外挪 0.015 确保左扇与左墙任何面 ≥ 0.012
HY, HW, GO = -3.235, 0.385, 0.035  # 铰链 y、半扇宽、玻璃沿扇局部 +Y（转过 90° 后朝外）偏移
sashes = []
for side, hx, sgn, ang in (('L', -2.82, 1, math.radians(-150)), ('R', -1.28, -1, math.radians(150))):
    c, s = math.cos(ang), math.sin(ang)
    sc = (hx + sgn * HW * c, HY + sgn * HW * s, 1.80)  # 中心 = 铰链 + 半扇宽 × 转后扇向
    sashes.append((side, sc, (sc[0] - GO * s, sc[1] + GO * c, 1.80), ang))
for side, sc, gc, ang in sashes:
    # 窗扇改空心：四边框 + 中横梃，玻璃分上下两格嵌进框内（四周 0.005 搭接）
    ft, bt, c, s = 0.07, 0.05, math.cos(ang), math.sin(ang)
    wld = lambda d: (sc[0] + d[0] * c - d[1] * s, sc[1] + d[0] * s + d[1] * c, sc[2] + d[2])
    for nm, sz, d in (('Top', (0.77, bt, ft), (0, 0, 0.745)), ('Bot', (0.77, bt, ft), (0, 0, -0.745)),
                      ('L', (ft, bt, 1.42), (-0.35, 0, 0)), ('R', (ft, bt, 1.42), (0.35, 0, 0)),
                      ('Mid', (0.63, bt, ft), (0, 0, -0.16))):
        parts.append(box(f'Win_Sash_{side}_{nm}', sz, wld(d), (0, 0, ang), winframe, bevel=BV['S'][0], seg=BV['S'][1]))
    for tag, gz, gh in (('U', 0.2925, 0.823), ('D', -0.4525, 0.503)):
        parts.append(box(f'Win_Glass_{side}_{tag}', (0.606, 0.015, gh), wld((0, 0, gz)), (0, 0, ang), glass, bevel=0, seg=0))
    hk = -1 if side == 'L' else 1  # 开合边：短圆柱把手 + 小柄（沿扇法线外移 0.012 避免与玻璃共面）
    parts.append(cyl(f'Win_Handle_{side}', 0.012, 0.09, wld((hk * 0.30, 0.042, -0.28)),
                     Quaternion((0, -s, c), math.pi / 2).to_euler(), winframe, verts=12, bevel=0, seg=0))
    parts.append(box(f'Win_HandleStem_{side}', (0.012, 0.012, 0.03), wld((hk * 0.30, 0.034, -0.28)),
                     (0, 0, ang), winframe, bevel=0, seg=0))
sash_check = [(f'Win_Sash_{s}', sc, math.degrees(ang)) for s, sc, _, ang in sashes]

# 平顶 z: 3.72 ~ 3.96
parts.append(b('Roof', (6.6, 6.6, 0.24), (0, 0, 3.84), roof, 'L'))

# 女儿墙：厚 0.16、高 0.20，贴屋顶四边，z: 3.96 ~ 4.16
pz, po = 3.96 + 0.10, 3.3 - 0.08
parts.append(b('Parapet_Front', (6.6, 0.16, 0.20), (0, -po, pz), roof, 'M'))
parts.append(b('Parapet_Back',  (6.6, 0.16, 0.20), (0,  po, pz), roof, 'M'))
parts.append(b('Parapet_Left',  (0.16, 6.28, 0.20), (-po, 0, pz), roof, 'M'))
parts.append(b('Parapet_Right', (0.16, 6.28, 0.20), ( po, 0, pz), roof, 'M'))

# 外墙水平线条：墙裙 + 压条 / 腰线 / 两层檐口。内面贴墙外表面 ±3.11，四边沿全长贯通；
# 墙端头伸出邻墙面 0.09（到 ±3.20），转角块把端头包住补齐；正面按门窗 / 招牌 / 吊盆 / 挑臂灯让开
wall_dk = mat('WALL_DARK', '#5E9C7A')
WF, WE, WI = 3.11, 3.20, 2.91  # 墙外表面 / 墙端头外沿 / 转角块内沿（再往里腰线会蹭到左窗扇铰链端）
DOOR, WIN = (-1.04, 3.14), (-2.91, -1.19)  # 门洞含卷帘导轨、窗洞含窗框
BD_X = -0.27                                # 背门洞中心 x：后墙内侧唯一无包裹段 x -0.70~0.60（#5 右沿 -0.705 / #15 左沿 0.60）里偏左
BDOOR = (BD_X - 0.50, BD_X + 0.50)          # 背门洞 ±0.45 + 门套 0.05（后墙墙裙 / 压条 / 分格让开）
CORN_CUT = [(-2.36, -1.74), (-1.52, 2.12), (2.64, 2.80)]  # 正面檐口让开：中间吊盆盆沿/吊杆、招牌、挑臂灯底座
DADO_Z, WAIST_Z, CORN_Z = 0.67, 2.25, (3.37, 3.62)
WIN_FRAME = (-2.91, -1.19)  # 窗洞含窗框的完整 x 范围（窗框左沿 -2.88-0.03=-2.91，右沿 -1.22+0.03=-1.19）
TRIMS = [  # (名, z0, z1, 距墙面外凸, 材质, 正面让开区间)
    ('Dado', 0.0, DADO_Z, 0.04, wall_dk, [DOOR]),  # 下延到台基顶面 z=0，盖住墙底外侧 0~0.12 的缝
    ('DadoCap', DADO_Z, DADO_Z + 0.05, 0.055, base, [DOOR]),
    ('Waist', WAIST_Z - 0.025, WAIST_Z + 0.025, 0.02, base, [WIN_FRAME, DOOR]),  # 腰线在窗框位置断开，避免与框共面
    ('Cornice1', CORN_Z[0], 3.50, 0.06, base, CORN_CUT),
    ('Cornice2', 3.50, CORN_Z[1], 0.11, base, CORN_CUT)]
def spans(lo, hi, cuts):  # [lo, hi] 扣掉让开区间，丢掉 <5cm 的碎段
    out = []
    for c0, c1 in sorted(cuts) + [(hi, hi)]:
        if min(c0, hi) - lo > 0.05:
            out.append((lo, min(c0, hi)))
        lo = max(lo, c1)
    return out
def tb(name, size, loc, m):
    return box(name, size, loc, (0, 0, 0), m, bevel=min(BV['S'][0], min(size) * 0.3), seg=2)
for tag, z0, z1, t, m, cuts in TRIMS:
    zc, h, L, n = (z0 + z1) / 2, z1 - z0, WF + t, WF + t / 2
    for side, nx, ny in (('F', 0, -1), ('B', 0, 1), ('L', -1, 0), ('R', 1, 0)):
        bcut = [BDOOR] if side == 'B' and tag.startswith('Dado') else []  # 腰线 z≥2.225 高过背门套顶 2.20，不断开
        for i, (a0, a1) in enumerate(spans(-L, L, cuts if side == 'F' else bcut)):
            c = (a0 + a1) / 2
            # 各面法线：前墙 -Y、后墙 +Y、左墙 -X、右墙 +X
            if nx == 0:  # 前/后墙（沿 Y）
                size = (a1 - a0, t, h)
                loc = (c, ny * n, zc)
            else:  # 左/右墙（沿 X）
                size = (t, a1 - a0, h)
                loc = (nx * n, c, zc)
            parts.append(tb(f'Trim_{tag}_{side}{i}', size, loc, m))
    k = WE + t - WI  # 转角块边长：从 2.91 包到端头外再外凸 t
    for sx, sy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
        parts.append(tb(f'Trim_{tag}_Corner_{sx:+d}{sy:+d}', (k + 0.02, k + 0.02, h), (sx * (WI + k / 2), sy * (WI + k / 2), zc), m))
print('[CHECK] dado_z=%.2f waist_z=%.2f cornice_z=%.2f' % (DADO_Z, WAIST_Z, CORN_Z[1]))  # 墙裙顶 / 腰线中心 / 檐口顶

# 竖向分格条：背 / 左 / 右三面各 5 条，截面 0.06 宽 × 外凸 0.02，沿墙长 ±3.20 六等分；
# 底压在墙裙压条里，顶止于腰线下沿（与腰线同为外凸 0.02，伸进去会外表面共面闪烁）
PW, PT, PZ = 0.06, 0.02, (DADO_Z, WAIST_Z - 0.025)
PIL_CUT = {'B': [BDOOR], 'L': [], 'R': []}  # 各面需让开的洞口区间（后墙中间一条让给背门）
n_pil = 0
for side, nx, ny in (('B', 0, 1), ('L', -1, 0), ('R', 1, 0)):
    for i in range(5):
        c = -WE + 2 * WE * (i + 1) / 6
        if any(a0 - PW / 2 < c < a1 + PW / 2 for a0, a1 in PIL_CUT[side]):
            continue
        size = (PW, PT, PZ[1] - PZ[0]) if nx == 0 else (PT, PW, PZ[1] - PZ[0])
        loc = (c, ny * (WF + PT / 2), sum(PZ) / 2) if nx == 0 else (nx * (WF + PT / 2), c, sum(PZ) / 2)
        parts.append(tb(f'Trim_Pilaster_{side}{i}', size, loc, wall_dk))
        n_pil += 1
# 外墙角护角：两墙端头在外角留出 3.11~3.20 的方形缺口，护角 3.135~3.215 嵌入并外凸 0.015 包住
# 沿 -Y 方向外移 0.012，让护角明显凸出墙角，避免与左窗扇共面；z 0.12 ~ 檐口顶
CG, CGC = 0.08, 3.175
for sx, sy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
    parts.append(tb(f'Trim_CornerGuard_{sx:+d}{sy:+d}', (CG, CG, CORN_Z[1] - 0.12),
                    (sx * CGC, sy * (CGC + 0.012), (0.12 + CORN_Z[1]) / 2), wall_dk))

# --- 统一外移所有 Trim 构件，避免与墙面共面 ---
TRIM_OFFSET = 0.012
trim_moved, trim_unknown = 0, []
for o in parts:
    if not o.name.startswith('Trim_'):
        continue
    # 从名字判断所属墙面：_F*/-Y、_B*/+Y、_L*/-X、_R*/+X
    dirs = []
    if '_F' in o.name:
        dirs.append(('y', -TRIM_OFFSET))
    if '_B' in o.name:
        dirs.append(('y', TRIM_OFFSET))
    if '_L' in o.name:
        dirs.append(('x', -TRIM_OFFSET))
    if '_R' in o.name:
        dirs.append(('x', TRIM_OFFSET))
    if not dirs:
        trim_unknown.append(o.name)
        continue
    for ax, delta in dirs:
        if ax == 'x':
            o.location.x += delta
        else:
            o.location.y += delta
    trim_moved += 1
if trim_unknown:
    print('[TRIM] unknown wall:', trim_unknown)
print('[TRIM] moved %d Trim objects by %.3f' % (trim_moved, TRIM_OFFSET))

# 招牌：门洞顶 z=2.84 与墙顶 z=3.72 之间，底板 + "SHEN'S LIFE OFFICE" 3D 文字（朝 -Y）
import bpy
from mathutils import Vector, Quaternion
sign = mat('SIGN', '#F5F1E6')   # 米白
ink = mat('INK', '#1F4034')     # 深墨绿
SIGN_W = 3.75  # 招牌底板宽度（原 4.80 太大，缩到 3.75）
sign_board = b('Sign_Board', (SIGN_W, 0.10, 0.55), (0, -3.192, 3.26), sign, 'M')  # 沿 -Y 外移 0.012 避免与檐口共面
parts.append(sign_board)
sign_text, t = None, None
try:
    bpy.ops.object.select_all(action='DESELECT')
    # 文字默认在 XY 平面朝 +Z，绕 X 转 +90° 后朝 -Y，字头朝 +Z
    bpy.ops.object.text_add(location=(0, -3.257, 3.26), rotation=(math.pi / 2, 0, 0))  # 随底板同步外移 0.012
    t = bpy.context.active_object
    t.name = 'Sign_Text'
    t.data.body = "SHEN'S LIFE OFFICE"
    t.data.size = 0.23  # 原 0.28，随底板缩小调整字号
    t.data.extrude = 0.035
    t.data.bevel_depth = 0.006
    t.data.align_x, t.data.align_y = 'CENTER', 'CENTER'
    bpy.ops.object.convert(target='MESH')
    sign_text = bpy.context.active_object
    sign_text.data.materials.append(ink)
    parts.append(sign_text)
    print('[CHECK] sign text=%r board_x=[%.2f,%.2f] width=%.2f' % (t.data.body if hasattr(t, 'data') and hasattr(t.data, 'body') else "SHEN'S LIFE OFFICE", -SIGN_W/2, SIGN_W/2, SIGN_W))
except Exception as e:
    print('[CHECK] sign text failed:', e)
    sign_text = None
    if t is not None and t not in parts:  # 转换失败时清掉残留的 FONT 对象，不阻断导出
        bpy.data.objects.remove(t, do_unlink=True)

# 合并前记录招牌板 / 文字的世界包围盒中心（合并后对象引用会失效）
sign_check = []
try:
    bpy.context.view_layer.update()
    for o in (sign_board, sign_text):
        if o is not None:
            cs = [o.matrix_world @ Vector(c) for c in o.bound_box]
            sign_check.append((o.name, sum(cs, Vector()) / 8))
except Exception as e:
    print('[CHECK] sign bbox failed:', e)

# 室内办事窗口：贯穿左右墙的整条隔断，y=DY 以前(-Y)为顾客区、以后(+Y)为工作区
# 从左到右三段：左 1/3 敞开（只有立柱 + 台面）/ 中 1/3 整片玻璃 / 右 1/3 玻璃带递件小口
wood = mat('WOOD', '#A9784F')         # 立柱 / 裙板 / 横梁
wood2 = mat('WOOD_LIGHT', '#C9A57B')  # 台面 / 小口框
wood_d = mat('WOOD_DARK', '#6E4A2E')  # 裙板竖向凹槽线
X0, X1, DY = -2.88, 2.88, 1.10        # 两端距墙内面（±2.89）0.01 防共面；DY 在进深中后部
TOP, GT, CEIL = 1.08, 2.15, 3.72      # 台面顶 / 玻璃上沿 / 天花（屋顶底面）
XS = (X0 + (X1 - X0) / 3, X0 + 2 * (X1 - X0) / 3)  # 三段分界 x = -0.96 / 0.96
PS = 0.18                             # 立柱截面
counter = b('Counter_Body', (X1 - X0, 0.30, TOP - 0.07 - 0.12), (0, DY, (0.12 + TOP - 0.07) / 2), wood, 'M')  # 裙板 z 0.12 ~ 1.01
counter_top = b('Counter_Top', (X1 - X0, 0.52, 0.07), (0, DY - 0.04, TOP - 0.035), wood2, 'S')  # 前挑 0.15、后挑 0.07
parts += [counter, counter_top]
NG = 18  # 裙板正面（-Y）竖向凹槽线，外凸 0.006
for i in range(NG):
    parts.append(box(f'Counter_Groove_{i}', (0.025, 0.016, 0.70), (X0 + (X1 - X0) * (i + 0.5) / NG, DY - 0.152, 0.565),
                     (0, 0, 0), wood_d, bevel=0.003, seg=2))
# 立柱 z 0.12 ~ 2.15（两端贴墙 + 两个分界），横梁 z 2.15 ~ 2.33，上方封板接天花
for i, x in enumerate((X0 + PS / 2, XS[0], XS[1], X1 - PS / 2)):
    parts.append(b(f'Divider_Post_{i}', (PS, PS, GT - 0.12), (x, DY, (0.12 + GT) / 2), wood, 'M'))
parts.append(b('Divider_Beam', (X1 - X0, 0.22, 0.18), (0, DY, GT + 0.09), wood, 'M'))
parts.append(b('Divider_Header', (X1 - X0, 0.10, CEIL - GT - 0.18), (0, DY, (GT + 0.18 + CEIL) / 2), wood, 'S'))
# 玻璃（沿用窗玻璃 glass）：中段整片；右段在递件小口（贴台面、含框）两侧和上方各一片
OX, OW, OH, FW = 1.95, 0.50, 0.35, 0.04  # 小口中心 x / 宽 / 高 / 框宽
o0, o1, oz = OX - OW / 2 - FW, OX + OW / 2 + FW, TOP + OH + FW
panes = [(XS[0] + PS / 2, XS[1] - PS / 2, TOP, GT),
         (XS[1] + PS / 2, o0, TOP, GT), (o1, X1 - PS, TOP, GT), (o0, o1, oz, GT)]
for i, (x0, x1, z0, z1) in enumerate(panes):
    parts.append(box(f'Divider_Glass_{i}', (x1 - x0, 0.02, z1 - z0), ((x0 + x1) / 2, DY, (z0 + z1) / 2), (0, 0, 0),
                     glass, bevel=0.005, seg=BV['S'][1]))
glass_area = sum((x1 - x0) * (z1 - z0) for x0, x1, z0, z1 in panes)
for side, x in (('L', o0 + FW / 2), ('R', o1 - FW / 2)):  # 小口框：左右竖框 + 上框
    parts.append(b(f'Divider_Slot_{side}', (FW, 0.06, OH + FW), (x, DY, TOP + (OH + FW) / 2), wood2, 'S'))
parts.append(b('Divider_Slot_Top', (o1 - o0, 0.06, FW), (OX, DY, oz - FW / 2), wood2, 'S'))
# 办事员座椅：座面 z 0.49 ~ 0.55，四腿 z 0.12 ~ 0.56
# 座椅 x 0.09~0.51、y 2.46~2.88：退出后墙内面 2.89（原 y 2.85 伸进墙厚），右下角让开 #17 斜边
parts.append(b('Clerk_Seat', (0.42, 0.42, 0.06), (0.30, 2.67, 0.52), wood2, 'S'))
for i, (dx, dy) in enumerate(((-0.16, -0.16), (0.16, -0.16), (-0.16, 0.16), (0.16, 0.16))):
    parts.append(b(f'Clerk_Leg_{i}', (0.05, 0.05, 0.44), (0.30 + dx, 2.67 + dy, 0.12 + 0.22), wood2, 'S'))

# 寄信处 + 邮件堆材质
card = mat('CARD', '#C89B6E')    # 牛皮纸
paper = mat('PAPER', '#F7F3E8')  # 信封白
tape = mat('TAPE', '#D9534F')    # 红色胶带/封条

# 寄信处台子：贴右墙内侧（门洞进来右手边），台身 z 0.12 ~ 0.98，台面 z 0.985 ~ 1.055
parts.append(b('Drop_Top',  (0.95, 0.60, 0.07), (2.62, -0.60, 1.02), wood2, 'S'))
parts.append(b('Drop_Body', (0.88, 0.54, 0.86), (2.62, -0.60, 0.55), wood, 'M'))
parts.append(b('Drop_Slot', (0.10, 0.44, 0.05), (2.66, -0.60, 1.075), ink, 'S'))
parts.append(b('Drop_Sign', (0.42, 0.04, 0.26), (2.62, -0.90, 1.42), paper, 'S'))
parts.append(b('Drop_Box',  (0.40, 0.36, 0.32), (2.55, -1.35, 0.28), card, 'S'))

# 工作区（隔断后 y 1.32~2.89）邮件包裹 + 服务口内外对坐椅 + 顾客区左侧信件堆
from mathutils import Euler
label = mat('LABEL', '#FFFFFF')  # 运单标签白
T, new_objs = 0.004, []          # 胶带厚；叠放件底 z = 下件顶 + T（压在胶带上，不悬空）
def nb(name, size, loc, rot, m):
    o = box(name, size, loc, rot, m, bevel=min(BV['S'][0], min(size) * 0.3), seg=BV['S'][1]); new_objs.append(o); return o
def parcel(i, w, d, h, x, y, z0, rz=0, tx=0, ty=0, m=card):  # z0 = 世界最低点；顶面封箱胶带 + 前后折边 + 前脸(-Y)运单
    rot = tuple(math.radians(a) for a in (tx, ty, rz)); R = Euler(rot).to_matrix()
    c = Vector((x, y, z0 + sum(abs(R[2][k]) * s for k, s in enumerate((w, d, h))) / 2))
    at = lambda lx, ly, lz: c + R @ Vector((lx, ly, lz))
    body = nb(f'Parcel_{i}', (w, d, h), c, rot, m)
    nb(f'Parcel_{i}_Tape', (0.06, d + 2 * T, T), at(0, 0, h / 2 + T / 2), rot, tape)
    for s in (-1, 1):
        nb(f'Parcel_{i}_TapeFlap_{s}', (0.06, T, h * 0.25), at(0, s * (d / 2 + T / 2), h * 0.375), rot, tape)
    lw, lh = min(0.14, w * 0.4), min(0.09, h * 0.35)
    nb(f'Parcel_{i}_Label', (lw, 0.003, lh), at(w * 0.25, -d / 2 - 0.0015, -h * 0.1), rot, label)
    nb(f'Parcel_{i}_Code', (lw * 0.7, 0.001, lh * 0.25), at(w * 0.25, -d / 2 - 0.0035, -h * 0.12 - lh * 0.2), rot, ink)
    return body
def stack(tag, x, y, z0, n, rz):  # 信封叠：逐层 x 错开 ±1.5cm、y ±1cm、转角 ±6°，每 3 封夹一封牛皮纸
    for k in range(n):
        nb(f'{tag}_{k}', (0.24, 0.16, 0.012), (x + (-1) ** k * 0.015, y + (k % 3 - 1) * 0.01, z0 + 0.006 + k * 0.012),
           (0, 0, math.radians(rz + (k % 4 - 1.5) * 4)), card if k % 3 == 2 else paper)
    return n
P_SPECS = [  # (w, d, h, x, y, z0, rz, tx, ty, m)；左后：三层大摞 + 斜靠板 + 立放 + 两层；右后：三层摞 + 靠墙板；台面后方：两层 + 白色软包
    (0.62, 0.52, 0.46, -2.35, 2.50, 0.12, 0), (0.44, 0.38, 0.30, -2.30, 2.48, 0.584, 8), (0.30, 0.24, 0.18, -2.34, 2.46, 0.888, -12),
    (0.50, 0.44, 0.40, -1.55, 2.55, 0.12, -5), (0.36, 0.30, 0.24, -1.57, 2.56, 0.524, 15), (0.40, 0.30, 0.12, -0.95, 2.55, 0.12, 25),
    (0.40, 0.06, 0.45, -1.948, 2.50, 0.12, 90, -15, 0),  # 斜靠在 #0 右侧面 x=-2.04（顶部胶带贴面）
    (0.34, 0.24, 0.14, -2.40, 1.75, 0.12, 10, 0, 0, paper), (0.40, 0.08, 0.30, -1.90, 1.70, 0.12, -20),  # 白色软包 / 立放扁箱
    (0.48, 0.42, 0.40, -1.20, 1.85, 0.12, 6), (0.30, 0.30, 0.20, -1.18, 1.86, 0.524, -10, 0, 0, paper),
    (0.55, 0.50, 0.42, 2.40, 2.55, 0.12, 0), (0.40, 0.34, 0.28, 2.38, 2.52, 0.544, -10), (0.26, 0.20, 0.12, 2.40, 2.50, 0.828, 20, 0, 0, paper),
    (0.46, 0.40, 0.34, 1.60, 2.55, 0.12, 12), (0.50, 0.06, 0.55, 0.85, 2.795, 0.12, 0, -12, 0),  # 斜靠后墙（顶角 y≈2.886）
    (0.36, 0.30, 0.26, 0.90, 1.90, 0.12, -18), (0.30, 0.22, 0.10, 0.60, 2.35, 0.12, 35, 0, 0, paper), (0.24, 0.18, 0.10, 0.92, 1.88, 0.384, 10),
    (0.30, 0.16, 0.20, -0.55, 1.22, TOP, 0), (0.22, 0.14, 0.14, -0.50, 1.22, TOP + 0.204, 6), (0.26, 0.14, 0.10, 0.40, 1.22, TOP, -4, 0, 0, paper)]
mail = [parcel(i, *s) for i, s in enumerate(P_SPECS)]
n_let = sum(stack(*s) for s in (('Env_W0', -0.95, 2.55, 0.244, 5, 25), ('Env_W1', 0.30, 1.60, 0.12, 6, -10),
                                 ('Env_W2', 0.05, 1.215, TOP, 4, 0), ('Env_W3', -2.55, 2.05, 0.12, 7, 8),     # W0 压在 #5 胶带上，W2 在台面后方
                                 ('Env_C0', -2.30, 0.40, 0.12, 6, 12), ('Env_C1', -1.90, 0.45, 0.12, 4, -8),  # 顾客区左侧地面 4 叠
                                 ('Env_C2', -2.55, -0.10, 0.12, 8, 25), ('Env_C3', -1.60, 0.05, 0.12, 3, -30),
                                 ('RegLetter', -2.20, -0.70, 0.45, 5, 15)))  # 矮凳上的挂号信
nb('RegLetter_Mark', (0.06, 0.10, 0.002), (-2.185, -0.70, 0.45 + 5 * 0.012 + 0.001), (0, 0, math.radians(9)), tape)  # 顶封红色挂号条
nb('Stool_Seat', (0.40, 0.40, 0.05), (-2.20, -0.70, 0.425), (0, 0, 0), wood2)  # 矮凳面 z 0.40~0.45
for i in range(4):  # 凳腿 z 0.12~0.40
    nb(f'Stool_Leg_{i}', (0.04, 0.04, 0.28), (-2.20 + (i % 2 * 2 - 1) * 0.16, -0.70 + (i // 2 * 2 - 1) * 0.16, 0.26), (0, 0, 0), wood)
LOOSE = ((-1.40, -0.40, 40), (-2.00, -0.25, -65), (-1.30, 0.55, 15))
for i, (x, y, r) in enumerate(LOOSE):  # 散落地面
    nb(f'Letter_Loose_{i}', (0.24, 0.16, 0.006), (x, y, 0.123), (0, 0, math.radians(r)), paper)
n_let += len(LOOSE)
SVC = (('Cust', 0.45, -1), ('Clerk', 1.75, 1))  # 椅心 y、靠背侧：顾客椅背朝 -Y、职员椅背朝 +Y → 隔着小口面对面
for tag, cy, s in SVC:
    nb(f'SvcChair_{tag}_Seat', (0.44, 0.44, 0.05), (OX, cy, 0.47), (0, 0, 0), wood2)              # 座面 z 0.445~0.495
    nb(f'SvcChair_{tag}_Back', (0.40, 0.03, 0.24), (OX, cy + s * 0.18, 0.80), (0, 0, 0), wood2)  # 靠背板 z 0.68~0.92
    for i, (dx, dy) in enumerate(((-0.18, -0.18), (0.18, -0.18), (-0.18, 0.18), (0.18, 0.18))):
        hl = 0.83 if dy * s > 0 else 0.325  # 后腿加高兼靠背立柱
        nb(f'SvcChair_{tag}_Leg_{i}', (0.04, 0.04, hl), (OX + dx, cy + dy, 0.12 + hl / 2), (0, 0, 0), wood)
parts += new_objs

# 合并前记录邮件堆各对象世界包围盒 z 最小值
mail_zmin, new_zmin = [], None
try:
    bpy.context.view_layer.update()
    for o in mail:
        mail_zmin.append((o.name, min((o.matrix_world @ Vector(c)).z for c in o.bound_box)))
    new_zmin = min((o.matrix_world @ Vector(c)).z for o in new_objs for c in o.bound_box)
except Exception as e:
    print('[CHECK] mail bbox failed:', e)

# 合并前记录柜台（主体 + 台面）世界包围盒 z 范围
counter_z = None
try:
    bpy.context.view_layer.update()
    zs = [(o.matrix_world @ Vector(c)).z for o in (counter, counter_top) for c in o.bound_box]
    counter_z = (min(zs), max(zs))
except Exception as e:
    print('[CHECK] counter bbox failed:', e)

# 正面窗下室外长椅（贴墙外表面 y≈-3.11）
wood3 = mat('BENCH_WOOD', '#B08050')  # 长椅木条
iron = mat('IRON', '#4A4A4A')         # 椅腿铁件
leafA = mat('LEAF_A', '#4F8A5B')      # 深叶
leafB = mat('LEAF_B', '#6BA368')      # 浅叶
pot = mat('POT', '#B5713F')           # 花盆
BX, PY, S = -2.05, -3.32, BV['S']
# 长椅离墙放置、整体压矮：靠背顶 z=0.96 < 窗台 1.00
bench = [b(f'Bench_Seat_{i}', (1.58, 0.15, 0.055), (BX, y, 0.44), wood3, 'S') for i, y in enumerate((-3.62, -3.78, -3.94))]
bench += [b(f'Bench_Back_{i}', (1.58, 0.055, 0.12), (BX, -3.58, z), wood3, 'S') for i, z in enumerate((0.62, 0.76, 0.90))]
for side, dx, lx in (('L', -0.72, -0.55), ('R', 0.72, 0.55)):
    bench.append(b(f'Bench_Post_{side}', (0.055, 0.07, 0.56), (BX + dx, -3.60, 0.68), iron, 'S'))  # z 0.40 ~ 0.96
    bench.append(b(f'Bench_Leg_{side}', (0.065, 0.62, 0.42), (BX + dx, -3.76, 0.24), iron, 'S'))  # z 0.03 ~ 0.45，底坐在脚垫顶上
    bench += [b(f'Bench_Foot_{side}{j}', (0.09, 0.09, 0.03), (BX + dx, y, 0.015), iron, 'S')
              for j, y in enumerate((-3.55, -3.97))]  # 脚垫 z 0.00 ~ 0.03，底贴室外地面
    # 背后小连接件：表现长椅是独立家具，不嵌墙
    bench.append(b(f'Bench_Link_{side}', (0.10, 0.30, 0.06), (BX + lx, -3.42, 0.62), iron, 'S'))
bench.append(b('Bench_Brace', (1.44, 0.05, 0.045), (BX, -3.76, 0.0825), iron, 'S'))  # 底部横撑 z 0.06 ~ 0.105，压在脚垫顶上
# 室外家具接地基准对齐台基底 z=-0.18：查看器会把包围盒最低点抬到地面圆盘，z=0 落地会被整体抬高 0.18
for o in bench:
    o.location.z -= 0.18
parts += bench
try:
    bpy.context.view_layer.update()
    _bz = min((o.matrix_world @ Vector(c)).z for o in bench for c in o.bound_box)
    print('[CHECK] bench z_min=%.3f y_back=%.3f back_top=%.3f' % (_bz, -3.58, 0.96))
except Exception as e:
    print('[CHECK] bench bbox failed:', e)

# 檐下垂挂绿植 ×4（避开招牌 x -1.5~2.1）：檐口立面钉垫片+螺栓 → L 形钩臂外伸到盆心正上方 → 细吊杆拉到盆沿
# (x, 盆半径, 盆高, 盆沿 z, 吊杆数, 各藤蔓段数)；藤蔓首段顶 = 盆沿-0.06，段高 0.30、段距 0.26
# 盆底 z 3.02~3.20；窗上方两盆藤蔓止于 z≥2.60（窗洞上沿），右段两盆可垂到 2.2~2.4
PLANTERS = [(-2.78, 0.17, 0.20, 3.32, 3, (2, 1, 2, 2)), (-2.05, 0.25, 0.28, 3.48, 3, (3, 2, 3, 1, 3, 2)),
            (2.38, 0.21, 0.24, 3.36, 3, (4, 2, 3, 4, 2)), (3.00, 0.15, 0.18, 3.20, 2, (3, 2, 3))]
PLY, FY, HZ, TZ = -3.45, -3.30, 3.84, 3.74  # 盆心 y（离墙面 -3.11 / 卷帘轴 -3.19 留空）、檐口立面 y、挂钉 z、钩尖 z
vines, leaves, pots = [], [], []
for p, (px, r, h, rz, nr, ns) in enumerate(PLANTERS):
    parts.append(cyl(f'Planter_Nail_Plate_{p}', radius=0.05, height=0.02, loc=(px, FY, HZ), rot=(math.pi / 2, 0, 0),
                     material=iron, verts=16))
    parts.append(cyl(f'Planter_Nail_Bolt_{p}', radius=0.016, height=0.02, loc=(px, FY - 0.02, HZ + 0.025),
                     rot=(math.pi / 2, 0, 0), material=iron, verts=6))
    parts.append(b(f'Planter_Hook_Arm_{p}', (0.022, 0.16, 0.022), (px, (FY + PLY) / 2, HZ - 0.02), iron, 'S'))
    parts.append(b(f'Planter_Hook_Drop_{p}', (0.022, 0.022, 0.09), (px, PLY, TZ + 0.045), iron, 'S'))
    pots.append(cyl(f'Planter_Pot_{p}', radius=r, height=h, loc=(px, PLY, rz - h / 2), material=pot,
                    verts=32, bevel=S[0], seg=S[1]))
    parts += [pots[-1], cyl(f'Planter_Rim_{p}', radius=r + 0.03, height=0.05, loc=(px, PLY, rz), material=pot, verts=32)]
    # 吊杆：钩尖 → 盆沿均布点；轴向 = d/|d| → rot = (0, acos(dz/|d|), atan2(dy, dx))
    for i in range(nr):
        a = math.pi / 2 + 2 * math.pi * i / nr if nr == 3 else math.pi * i
        d = Vector(((r + 0.02) * math.cos(a), (r + 0.02) * math.sin(a), rz + 0.02 - TZ))
        parts.append(cyl(f'Planter_Rope_{p}_{i}', radius=0.008, height=d.length, loc=(px + d.x / 2, PLY + d.y / 2, TZ + d.z / 2),
                         rot=(0, math.acos(d.z / d.length), math.atan2(d.y, d.x)), material=iron, verts=6, bevel=0.003, seg=1))
    # 盆口叶丛：内外两圈 6 球，顶部低于钩尖，露出挂钩
    for i in range(6):
        a, rr = i * math.pi / 3, r * (0.6 if i % 2 else 0.25)
        parts.append(sphere(f'Planter_Bush_{p}_{i}', r * (0.5 if i % 2 else 0.38),
                            (px + rr * math.cos(a), PLY + rr * math.sin(a), rz - 0.03 + 0.05 * (i % 3)), (leafA, leafB)[(i + p) % 2]))
    # 藤蔓只从朝外半圈（-Y 侧）垂下，不碰墙面和卷帘轴；每段挂 2 片叶
    for j, n in enumerate(ns):
        a = math.pi * (1 + (j + 0.5) / len(ns))
        for k in range(n):
            x = px + (r + 0.03) * math.cos(a) * (1 + 0.08 * k)
            y, z = PLY + (r + 0.03) * math.sin(a) - 0.02 * k, rz - 0.21 - 0.26 * k
            vines.append(b(f'Vine_{p}_{j}_{k}', (0.04, 0.04, 0.30), (x, y, z), leafA, 'S'))
            for s in (1, -1):
                leaves.append(box(f'Vine_Leaf_{p}_{j}_{k}_{len(leaves)}', (0.10, 0.02, 0.07), (x + 0.06 * s, y - 0.02, z + 0.07 * s),
                                  (0, math.radians(20 * s), 0), (leafA, leafB)[len(leaves) % 2], bevel=0.005, seg=S[1]))
parts += vines + leaves

# 合并前记录长椅最低点 / 藤蔓（含叶）最低点 / 吊盆
plant_check = None
try:
    bpy.context.view_layer.update()
    zmin = lambda os_: min((o.matrix_world @ Vector(c)).z for o in os_ for c in o.bound_box)
    plant_check = (zmin(bench), zmin(vines + leaves))
    print('[CHECK] planters=%d vines=%d leaves=%d nail_z=%.2f pot_z_min=%.2f'
          % (len(PLANTERS), len(vines), len(leaves), HZ, zmin(pots)))
except Exception as e:
    print('[CHECK] bench/plant bbox failed:', e)

# 顾客区右侧工作台：长边沿 Y 贴右墙内侧（x 2.23~2.88），y -2.87~-1.57 止于寄信箱（y≥-1.53）前；人坐 -X 侧面朝 +X
plastic = mat('PLASTIC_D', '#2E3136')            # 深灰塑料
screen = mat('SCREEN', '#1A2230', roughness=0.1)  # 深色屏幕 + 极淡蓝自发光
_sb = next(n for n in screen.node_tree.nodes if n.type == 'BSDF_PRINCIPLED').inputs
_sb['Emission Color'].default_value, _sb['Emission Strength'].default_value = (0.55, 0.72, 1.0, 1.0), 0.25
WX, WY, WL, WD, WT = 2.555, -2.22, 1.30, 0.65, 0.75  # 桌心 x/y、长(Y)、深(X)、桌面顶 z
LX, LY = WD / 2 - 0.06, WL / 2 - 0.06                 # 桌腿内缩
desk = [box('Desk_Top', (WD, WL, 0.04), (WX, WY, WT - 0.02), (0, 0, 0), wood2, bevel=0.03, seg=4)]  # z 0.71~0.75
for i, (sx, sy, dx, dy) in enumerate(((WD - 0.06, 0.02, 0, 1), (WD - 0.06, 0.02, 0, -1), (0.02, WL - 0.06, 1, 0), (0.02, WL - 0.06, -1, 0))):
    desk.append(b(f'Desk_Apron_{i}', (sx, sy, 0.06), (WX + dx * (WD / 2 - 0.04), WY + dy * (WL / 2 - 0.04), WT - 0.07), wood, 'S'))  # 收边 z 0.65~0.71
for i, (sx, sy) in enumerate(((-1, -1), (1, -1), (-1, 1), (1, 1))):  # 桌腿 z 0.12~0.71
    desk.append(b(f'Desk_Leg_{i}', (0.05, 0.05, WT - 0.16), (WX + sx * LX, WY + sy * LY, (0.12 + WT - 0.04) / 2), wood, 'S'))
desk.append(b('Desk_Brace_Y', (0.03, 2 * LY, 0.04), (WX + LX, WY, 0.22), wood, 'S'))  # 底部横撑（贴墙侧纵向 + 两端横向，留出腿部空间）
for i, sy in enumerate((-1, 1)):
    desk.append(b(f'Desk_Brace_X{i}', (2 * LX, 0.03, 0.04), (WX, WY + sy * LY, 0.22), wood, 'S'))
desk.append(b('Desk_Cabinet', (0.46, 0.39, 0.53), (2.56, -1.865, 0.385), wood, 'S'))  # 抽屉柜 z 0.12~0.65，靠寄信箱一端
for k in range(3):
    desk.append(b(f'Desk_Drawer_{k}', (0.02, 0.35, 0.155), (2.32, -1.865, 0.2275 + k * 0.17), wood2, 'S'))
    desk.append(b(f'Desk_Handle_{k}', (0.02, 0.10, 0.02), (2.30, -1.865, 0.2675 + k * 0.17), iron, 'S'))
# 电脑：显示器贴墙侧、屏幕朝 -X；键盘 / 鼠标 / 笔筒 / 纸叠都压在桌面 z=0.75 上
pc = [b('PC_Base', (0.20, 0.24, 0.02), (2.72, -2.40, WT + 0.01), plastic, 'S'),
      b('PC_Neck', (0.03, 0.06, 0.32), (2.735, -2.40, WT + 0.18), plastic, 'S'),  # z 0.77~1.09，插进边框背面
      b('PC_Bezel', (0.03, 0.58, 0.36), (2.71, -2.40, 1.06), plastic, 'S'),       # z 0.88~1.24
      box('PC_Screen', (0.004, 0.54, 0.32), (2.694, -2.40, 1.06), (0, 0, 0), screen, bevel=0.001, seg=1),
      b('PC_Keyboard', (0.16, 0.44, 0.02), (2.45, -2.40, WT + 0.01), plastic, 'S'),
      box('PC_Mouse', (0.10, 0.06, 0.03), (2.46, -2.07, WT + 0.015), (0, 0, 0), plastic, bevel=0.014, seg=4),
      cyl('PC_PenCup', radius=0.035, height=0.10, loc=(2.76, -1.76, WT + 0.05), material=iron, verts=16)]
pc += [box(f'PC_Key_{r}_{c}', (0.026, 0.028, 0.008), (2.45 + (r - 1.5) * 0.034, -2.40 + (c - 5.5) * 0.034, WT + 0.024),
           (0, 0, 0), shutter_rail, bevel=0.002, seg=1) for r in range(4) for c in range(12)]  # 4×12 键帽，顶 z 0.778
for i, (ry, m) in enumerate(((-0.15, tape), (0.0, wood_d), (0.12, ink))):  # 笔底 z≈0.76 落在筒底之上
    pc.append(cyl(f'PC_Pen_{i}', radius=0.004, height=0.15, loc=(2.76, -1.772 + i * 0.012, WT + 0.085), rot=(0, ry, 0), material=m, verts=8, bevel=0.001, seg=1))
pc += [box(f'PC_Paper_{i}', (0.21, 0.297, 0.004), (2.47, -1.80, WT + 0.002 + i * 0.004), (0, 0, math.radians((i - 1) * 4)), paper, bevel=0.001, seg=1) for i in range(3)]
KX, KY = 1.80, -2.40  # 办公椅心；靠背在 -X 侧 → 面朝 +X 对着桌子；五星脚 + 轮子落地 z=0.12
chair = [cyl('Chair_Hub', radius=0.05, height=0.05, loc=(KX, KY, 0.18), material=iron, verts=16),
         cyl('Chair_Column', radius=0.025, height=0.27, loc=(KX, KY, 0.335), material=iron, verts=12),  # z 0.20~0.47
         box('Chair_Seat', (0.46, 0.46, 0.07), (KX, KY, 0.495), (0, 0, 0), plastic, bevel=0.025, seg=4),  # z 0.46~0.53
         b('Chair_BackPost', (0.04, 0.06, 0.32), (KX - 0.21, KY, 0.60), iron, 'S'),                       # z 0.44~0.76
         box('Chair_Back', (0.05, 0.42, 0.40), (KX - 0.235, KY, 0.88), (0, 0, 0), plastic, bevel=0.02, seg=4)]  # z 0.68~1.08
for i in range(5):
    a = math.radians(90 + i * 72)
    chair.append(box(f'Chair_Leg_{i}', (0.26, 0.04, 0.03), (KX + 0.13 * math.cos(a), KY + 0.13 * math.sin(a), 0.185), (0, 0, a), iron, bevel=0.01, seg=2))
    chair.append(sphere(f'Chair_Wheel_{i}', 0.025, (KX + 0.25 * math.cos(a), KY + 0.25 * math.sin(a), 0.145), plastic))  # z 0.12~0.17
parts += desk + pc + chair
desk_check = None
try:
    bpy.context.view_layer.update()
    _dv = [o.matrix_world @ Vector(c) for o in desk for c in o.bound_box]
    desk_check = (min(v.x for v in _dv), max(v.x for v in _dv), min(v.y for v in _dv), max(v.y for v in _dv), WT, zmin(desk + pc + chair))
except Exception as e:
    print('[CHECK] desk bbox failed:', e)

# 右前方室外邮筒：台基 6.8 宽只到 x=3.4，x=3.85 已在台基外 → 落在草地 base_z=0，底座即一圈小基座
# 邮筒新位置：x=3.85（略外移），y=-2.45（往-Y移动，靠近正面大门，避开告示牌 y -1.85~+1.45）
post_red = mat('POST_RED', '#C0392B')    # 邮筒红
post_dark = mat('POST_DARK', '#8E2C20')  # 暗红（顶盖/底座）
post_white = mat('POST_WHITE', '#F2EFE6')  # 白色铭牌
MX, MYB, MZ = 3.85, -2.45, (0.12 if 3.85 <= 3.4 else 0.0)
mailbox = [cyl('Mailbox_Base', radius=0.32, height=0.10, loc=(MX, MYB, MZ + 0.05), material=post_dark,
               verts=32, bevel=S[0], seg=S[1]),
           cyl('Mailbox_Body', radius=0.28, height=1.02, loc=(MX, MYB, MZ + 0.61), material=post_red,
               verts=32, bevel=S[0], seg=S[1])]
cap = sphere('Mailbox_Cap', 0.30, (MX, MYB, MZ + 1.12), post_dark)
cap.scale.z = 0.55  # 压扁成顶盖，z 约 0.955 ~ 1.285
mailbox += [cap,
            b('Mailbox_Slot',  (0.34, 0.06, 0.05), (MX, MYB - 0.275, MZ + 0.92), post_dark, 'S'),
            b('Mailbox_Door',  (0.26, 0.04, 0.34), (MX, MYB - 0.272, MZ + 0.42), post_dark, 'S'),
            b('Mailbox_Plate', (0.20, 0.03, 0.09), (MX, MYB - 0.276, MZ + 0.72), post_white, 'S'),
            cyl('Mailbox_Handle', radius=0.03, height=0.10, loc=(MX, MYB, MZ + 1.30), material=post_dark, verts=32)]
for o in mailbox:  # 同长椅：室外邮筒从 z=0 下移到台基底 z=-0.18，避免被查看器整体抬高后悬空
    o.location.z -= 0.18
parts += mailbox

# 合并前记录邮筒整体世界包围盒
mailbox_check = None
try:
    bpy.context.view_layer.update()
    cs = [o.matrix_world @ Vector(c) for o in mailbox for c in o.bound_box]
    mailbox_check = (min(c.z for c in cs), max(c.z for c in cs),
                     (min(c.x for c in cs) + max(c.x for c in cs)) / 2, (min(c.y for c in cs) + max(c.y for c in cs)) / 2)
except Exception as e:
    print('[CHECK] mailbox bbox failed:', e)

# 两盏可开关灯：对象名 / 材质名均以 LGT_ 开头
lm = {k: light_mat(f'LGT_{k}', '#FFE2A8', v['on'], v['strength']) for k, v in LIGHTS.items()}
# 1. 室内大厅吊灯：吸顶座(顶面 3.72) + 细长吊杆 z 3.00~3.68 + 灯罩顶帽 + 宽平灯罩 z 2.90~3.00 + 灯泡
CX, CY = 0, 0.2
parts.append(cyl('LGT_post_ceiling_Canopy', radius=0.10, height=0.04, loc=(CX, CY, 3.70), material=iron, verts=24))
parts.append(cyl('LGT_post_ceiling_Rod', radius=0.015, height=0.68, loc=(CX, CY, 3.34), material=iron, verts=12))
parts.append(cyl('LGT_post_ceiling_Cap', radius=0.12, height=0.06, loc=(CX, CY, 3.03), material=iron, verts=24))
parts.append(cyl('LGT_post_ceiling_Shade', radius=0.34, height=0.10, loc=(CX, CY, 2.95),
                 material=lm['post_ceiling'], verts=48))
parts.append(sphere('LGT_post_ceiling_Bulb', 0.11, (CX, CY, 2.86), lm['post_ceiling']))
# 2. 招牌右侧挑臂灯：x=2.72 夹在右侧两盆吊篮之间（盆/藤 x≤2.66、≥2.81），招牌止于 x=2.10 不挡字
#    墙面底座(底 3.18 > 卷帘轴顶 3.12) → 横臂 z=3.55 外挑至 y=-3.97（越过吊盆前沿 -3.66）→ 斜撑 → 吊杆 → 灯罩朝下照门口右侧
SX, AZ, AY = 2.72, 3.55, -3.97
parts.append(b('LGT_post_sign_Mount', (0.12, 0.04, 0.44), (SX, -3.13, 3.40), iron, 'S'))
parts.append(cyl('LGT_post_sign_Arm', radius=0.02, height=-3.13 - AY, loc=(SX, (-3.13 + AY) / 2, AZ),
                 rot=(math.pi / 2, 0, 0), material=iron, verts=12))
parts.append(sphere('LGT_post_sign_Finial', 0.03, (SX, AY, AZ), iron))
d = Vector((0, -0.48, 0.31))  # 斜撑：底座下端 (y -3.14, z 3.22) → 横臂 (y -3.62, z 3.53)
parts.append(cyl('LGT_post_sign_Brace', radius=0.013, height=d.length, loc=(SX, -3.14 + d.y / 2, 3.22 + d.z / 2),
                 rot=(0, math.acos(d.z / d.length), math.atan2(d.y, d.x)), material=iron, verts=8))
parts.append(cyl('LGT_post_sign_Drop', radius=0.008, height=0.20, loc=(SX, AY + 0.05, AZ - 0.11), material=iron, verts=6))
parts.append(cyl('LGT_post_sign_Cap', radius=0.06, height=0.04, loc=(SX, AY + 0.05, 3.33), material=iron, verts=16))
parts.append(cyl('LGT_post_sign_Shade', radius=0.16, height=0.10, loc=(SX, AY + 0.05, 3.26),
                 material=lm['post_sign'], verts=32))
parts.append(sphere('LGT_post_sign_Bulb', 0.065, (SX, AY + 0.05, 3.20), lm['post_sign']))

# 檐沟：压扁圆柱 r0.07×竖向 0.6，顶贴屋面板底 z=3.72（高于檐口转角块顶 3.62），轴线外移到 ±3.28 伸出屋檐 ±3.30
gutter_m = mat('GUTTER', '#4A4F55')  # 深灰
GR, GS, GO = 0.07, 0.6, 3.28
GZ = 3.72 - GR * GS
for side, nx, ny in (('F', 0, -1), ('B', 0, 1), ('L', -1, 0), ('R', 1, 0)):
    g = cyl(f'Gutter_{side}', radius=GR, height=2 * GO, loc=(nx * GO, ny * GO, GZ),
            rot=(0, math.pi / 2, 0) if nx == 0 else (math.pi / 2, 0, 0), material=gutter_m, verts=24)
    g.scale = (GS, 1, 1) if nx == 0 else (1, GS, 1)  # 局部轴压扁 → 世界 Z 方向 0.6
    parts.append(g)
for sx, sy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):  # 四角短段补齐转角
    parts.append(cyl(f'Gutter_Corner_{sx:+d}{sy:+d}', radius=GR, height=2 * GR * GS,
                     loc=(sx * GO, sy * GO, GZ), material=gutter_m, verts=24))
# 落水管 ×2：背面(+Y)左右角，x=±2.80 让开檐口/墙裙转角块(到 2.91)；y=3.344 外侧让开所有线脚(≤3.31)
# 竖管 z 0.22~3.55 → 顶部 30° 弯头朝墙内斜接檐沟(y 3.28) → 底部 30° 斜排水口朝外；3 个卡箍(抱箍+连墙片)
PX, PY, PR, PZ0, PZ1 = 2.80, GO + 0.064, 0.055, 0.22, 3.55
for sx in (-1, 1):
    x = sx * PX
    parts.append(cyl(f'Downpipe_{sx:+d}', radius=PR, height=PZ1 - PZ0, loc=(x, PY, (PZ0 + PZ1) / 2), material=gutter_m, verts=20))
    parts.append(cyl(f'Downpipe_Elbow_{sx:+d}', radius=PR, height=0.16, loc=(x, (PY + GO) / 2, PZ1 + 0.055),
                     rot=(math.radians(30), 0, 0), material=gutter_m, verts=20))
    parts.append(cyl(f'Downpipe_Outlet_{sx:+d}', radius=PR, height=0.24, loc=(x, PY + 0.05, PZ0 - 0.087),
                     rot=(math.radians(30), 0, 0), material=gutter_m, verts=20))
    for k in range(3):  # z 0.89/1.78/2.66：均避开墙裙(≤0.72)、腰线(2.225~2.275)、檐口(≥3.37)
        cz = PZ1 * (k + 1) / 4
        parts.append(cyl(f'Downpipe_Clip_{sx:+d}_{k}', radius=PR + 0.012, height=0.04, loc=(x, PY, cz),
                         material=gutter_m, verts=20))
        parts.append(tb(f'Downpipe_ClipTab_{sx:+d}_{k}', (0.03, PY - WF, 0.03), (x, (WF + PY) / 2, cz), gutter_m))
try:
    print('[CHECK] downpipes=2 gutter_len=%.2f z=[%.2f,%.2f]' % (4 * 2 * GO, GZ - GR * GS, GZ + GR * GS))
except Exception as e:
    print('[CHECK] gutter/downpipe failed:', e)

# 背门 x=BD_X（见 BDOOR）：两侧后墙内侧堆满包裹，落水管在 ±2.80；墙裙 / 分格已按 BDOOR ±0.50 让开
# 洞 0.90×2.00（z 0.12~2.12）打穿后墙 → 三面内衬厚 0.06 → 门扇贴内衬外面、左铰链向外(+Y)开 60° → 合页 ×2 + 把手 → 雨篷 + 两斜撑
wd = []
back = [p for p in parts if p.name == 'Wall_Back'][0]
BD_CUT = 0.60  # 切割体 Y 深 0.60 > 墙厚 0.22 + 内衬 0.06，局部 y=0 即墙厚中心
bd_lx, bd_lz = BD_X - back.location.x, (0.10 + 2.12) / 2 - WZ  # 世界 → 墙局部（墙无旋转）
bd_f0 = len(back.data.polygons)
window_recess(back, w=0.90, h=2.02, depth=BD_CUT, loc=(bd_lx, 0, bd_lz))  # 底边多切 0.02
bd_f1 = len(back.data.polygons)
try:  # 打穿判据（墙局部坐标射线）：洞心沿 +Y 贯穿墙厚不命中，洞外 0.9 处对照射线命中，且布尔后面数增加
    bpy.context.view_layer.update()
    _ray = lambda x: back.ray_cast(Vector((x, -1.0, bd_lz)), Vector((0, 1, 0)), distance=2.0)[0]
    door_thru = (not _ray(bd_lx)) and _ray(bd_lx + 0.90) and bd_f1 > bd_f0
except Exception as e:
    door_thru = 'n/a (%s)' % e
wd += [tb(f'BackDoor_Lining_{sx:+d}', (0.06, 0.235, 1.94), (BD_X + sx * 0.42, 3.0025, 1.09), roof) for sx in (-1, 1)]  # x ±0.39~0.45，y 2.885~3.12
wd += [tb('BackDoor_Lining_Top', (0.90, 0.235, 0.06), (BD_X, 3.0025, 2.09), roof),   # z 2.06~2.12
       tb('BackDoor_Sill', (0.90, 0.235, 0.125), (BD_X, 3.0025, 0.0685), wood_d)]  # 补洞底 z 0.006~0.131（上移 0.006 避免底面与地板共面）
BA = math.radians(60)
BHX, BHY = BD_X - 0.43, 3.149  # 铰链轴：门扇左沿、内面（内衬外面 3.12 外移 0.029，避免与墙面共面）
dw = lambda u, v, z: (BHX + u * math.cos(BA) - v * math.sin(BA), BHY + u * math.sin(BA) + v * math.cos(BA), z)  # 扇局部(u 沿宽, v 沿厚朝外) → 世界
wd += [box('BackDoor_Leaf', (0.86, 0.05, 1.94), dw(0.43, 0.025, 1.10), (0, 0, BA), wood_d, bevel=BV['S'][0], seg=BV['S'][1]),  # z 0.13~2.07
       cyl('BackDoor_Knob', radius=0.03, height=0.03, loc=dw(0.78, 0.065, 1.00), rot=(math.pi / 2, 0, BA), material=iron, verts=16),
       box('BackDoor_Lever', (0.11, 0.02, 0.02), dw(0.735, 0.09, 1.00), (0, 0, BA), iron, bevel=0.004, seg=1)]
for i, z in enumerate((0.40, 1.80)):  # 合页：框侧页片（沿 +Y 外移 0.012）+ 轴筒
    wd += [tb(f'BackDoor_Hinge_{i}', (0.05, 0.015, 0.12), (BHX - 0.02, 3.1295, z), iron),
           cyl(f'BackDoor_HingePin_{i}', radius=0.012, height=0.14, loc=(BHX, BHY, z), material=iron, verts=12)]
wd.append(tb('BackDoor_Canopy', (1.10, 0.30, 0.10), (BD_X, 3.25, 2.35), roof))  # y 3.10~3.40（嵌墙 1cm），z 2.30~2.40 高过腰线 2.275
wd += [box(f'BackDoor_Brace_{sx:+d}', (0.03, 0.03, math.hypot(0.26, 0.30) + 0.02), (BD_X + sx * 0.52, 3.24, 2.15),
           (-math.atan2(0.26, 0.30), 0, 0), iron, bevel=0.004, seg=1) for sx in (-1, 1)]  # 墙面 (y 3.11, z 2.00) → 篷底 (y 3.37, z 2.30)
# 屋顶设备（屋面顶 z 3.96，靠后侧 y≈2.6，离女儿墙内面 3.14 留 0.3+）：百叶通风口 / 排气管
RT, VX, VY, EX, EY = 3.96, -1.20, 2.55, 1.30, 2.60
wd.append(tb('Vent_Body', (0.45, 0.45, 0.25), (VX, VY, RT + 0.125), roof))  # 外框 z 3.96~4.21，正面 y=2.325
wd += [box(f'Vent_Blade_{i}', (0.39, 0.05, 0.012), (VX, VY - 0.2475, RT + 0.035 + 0.036 * i), (math.radians(25), 0, 0),
           iron, bevel=0.003, seg=1) for i in range(6)]  # 外沿下倾 25°，内沿贴正面
wd += [cyl(f'Vent_Nut_{sx:+d}{sy:+d}', radius=0.018, height=0.016, loc=(VX + sx * 0.19, VY + sy * 0.19, RT + 0.258), material=iron, verts=6)
       for sx, sy in ((-1, -1), (1, -1), (-1, 1), (1, 1))]
wd += [cyl('Exhaust_Flange', radius=0.15, height=0.02, loc=(EX, EY, RT + 0.01), material=iron, verts=24),
       cyl('Exhaust_Pipe', radius=0.09, height=0.55, loc=(EX, EY, RT + 0.275), material=iron, verts=24),     # z 3.96~4.51
       sphere('Exhaust_Cap', 0.16, (EX, EY, RT + 0.58), roof)]
wd[-1].scale = (1, 1, 0.35)  # 压扁球作伞帽，z 4.48~4.60 罩住管口
parts += wd
n_wd = sum(p.name.startswith(('Trim_', 'Gutter_', 'Downpipe_', 'BackDoor_', 'Vent_', 'Exhaust_')) for p in parts)  # 合并前计数

# 右侧外墙告示牌：木框 + 浅色板面 + 顶部标题色带（以后在板面写待办）
board_mat = mat('BOARD', '#F2EFE6')       # 浅色板面
board_hdr = mat('BOARD_HDR', '#5E9C7A')   # 标题色带（深绿）
FW, FT, BH, BL = 0.10, 0.07, 2.05, 3.30   # 框宽、框厚、牌高、牌长(Y)
BX, BZ0 = 3.194, 0.65                     # 牌中心 x=3.194（整组外移 0.014 避免与墙裙共面）
BZ = BZ0 + BH / 2                          # 牌中心 z
BY = -0.20                                 # 牌中心 y（沿墙铺开，避开邮筒新位置 y≈-2.45）
HH = 0.18                                  # 标题色带高
# 四条框：上下沿 Y、左右沿 Y；框外表面 x≈3.194+0.035=3.229，内表面埋进墙 x≈3.154
board_parts = [
	tb('Board_Frame_Top',    (FW, BL, FT), (BX + 0.035, BY, BZ0 + BH - FT / 2), wood_d),
	tb('Board_Frame_Bottom', (FW, BL, FT), (BX + 0.035, BY, BZ0 + FT / 2), wood_d),
	tb('Board_Frame_Left',   (FW, FW, FT), (BX + 0.035, BY - BL / 2 + FW / 2, BZ), wood_d),
	tb('Board_Frame_Right',  (FW, FW, FT), (BX + 0.035, BY + BL / 2 - FW / 2, BZ), wood_d)]
# 板面：比框内缩，埋进墙内侧 0.024（内缩 0.004 避免与框共面）
board_parts.append(tb('Board_Face', (0.012, BL - 2 * FW, BH - 2 * FT), (BX - 0.024, BY, BZ), board_mat))
# 标题色带：顶部窄条，x 厚度比板面薄 0.012（两侧各缩 0.006），沿 x 外移 0.008（压在板面上，z 错开 0.004）
board_parts.append(tb('Board_Header', (0.008, BL - 2 * FW - 0.012, HH), (BX - 0.016, BY, BZ0 + BH - FT - HH / 2 - 0.004), board_hdr))
parts += board_parts
try:
	bpy.context.view_layer.update()
	_bc = [o.matrix_world @ Vector(c) for o in board_parts for c in o.bound_box]
	_bx = (min(v.x for v in _bc), max(v.x for v in _bc))
	_by = (min(v.y for v in _bc), max(v.y for v in _bc))
	_bz = (min(v.z for v in _bc), max(v.z for v in _bc))
	print('[CHECK] board x=[%.2f,%.2f] y=[%.2f,%.2f] z=[%.2f,%.2f]' % (_bx[0], _bx[1], _by[0], _by[1], _bz[0], _bz[1]))
except Exception as e:
	print('[CHECK] board bbox failed:', e)

# --- 临时诊断：找出窗户区域彼此过近(<0.006)的构件对，定位 z-fighting ---
try:
    _wins = [o for o in parts if o.type == 'MESH' and (o.name.startswith('Win_') or o.name.startswith('Wall_Front'))]
    print('[DIAG] win objs', len(_wins))
    _np = 0
    for _i in range(len(_wins)):
        for _j in range(_i + 1, len(_wins)):
            _a, _b = _wins[_i], _wins[_j]
            _pa = [_a.matrix_world @ Vector(c) for c in _a.bound_box]
            _pb = [_b.matrix_world @ Vector(c) for c in _b.bound_box]
            _amn = (min(p.x for p in _pa), min(p.y for p in _pa), min(p.z for p in _pa))
            _amx = (max(p.x for p in _pa), max(p.y for p in _pa), max(p.z for p in _pa))
            _bmn = (min(p.x for p in _pb), min(p.y for p in _pb), min(p.z for p in _pb))
            _bmx = (max(p.x for p in _pb), max(p.y for p in _pb), max(p.z for p in _pb))
            _dx = max(0.0, max(_amn[0] - _bmx[0], _bmn[0] - _amx[0]))
            _dy = max(0.0, max(_amn[1] - _bmx[1], _bmn[1] - _amx[1]))
            _dz = max(0.0, max(_amn[2] - _bmx[2], _bmn[2] - _amx[2]))
            _g = (_dx ** 2 + _dy ** 2 + _dz ** 2) ** 0.5
            if _g < 0.006:
                print('[DIAG] near %-22s %-22s gap=%.4f' % (_a.name, _b.name, _g))
                _np += 1
    print('[DIAG] near pairs', _np)
except Exception as _e:
    print('[DIAG] failed:', _e)

# --- 共面检测：找出两个对象在某一轴上的面坐标几乎相等(<0.004)且另两轴投影重叠的对，即 z-fighting 嫌疑 ---
try:
    _objs = [o for o in parts if o.type == 'MESH']
    def _bb(o):
        p = [o.matrix_world @ Vector(c) for c in o.bound_box]
        return (min(q.x for q in p), max(q.x for q in p), min(q.y for q in p), max(q.y for q in p), min(q.z for q in p), max(q.z for q in p))
    _B = {o.name: _bb(o) for o in _objs}
    _cop = 0
    _names = list(_B)
    for _i in range(len(_names)):
        for _j in range(_i + 1, len(_names)):
            a, b = _B[_names[_i]], _B[_names[_j]]
            # 只关心不同材质之间的共面：同材质会在 join_by_material 后合并成同一 mesh，内部不会 z-fight
            _oa = next((o for o in _objs if o.name == _names[_i]), None)
            _ob = next((o for o in _objs if o.name == _names[_j]), None)
            if _oa is not None and _ob is not None:
                _ma = _oa.active_material.name if _oa.active_material else 'none'
                _mb = _ob.active_material.name if _ob.active_material else 'none'
                if _ma == _mb:
                    continue
            ov = lambda p, q: min(p[1], q[1]) - max(p[0], q[0])   # 区间重叠长度
            for _ax, (i0, i1, i2, i3) in (('x', (0, 1, 2, 3)), ('y', (2, 3, 0, 1)), ('z', (4, 5, 0, 1))):
                for pa in (a[i0], a[i1]):
                    for pb in (b[i0], b[i1]):
                        if abs(pa - pb) < 0.004:
                            # 另两轴投影是否都重叠
                            if _ax == 'x':
                                o1, o2 = ov((a[2], a[3]), (b[2], b[3])), ov((a[4], a[5]), (b[4], b[5]))
                            elif _ax == 'y':
                                o1, o2 = ov((a[0], a[1]), (b[0], b[1])), ov((a[4], a[5]), (b[4], b[5]))
                            else:
                                o1, o2 = ov((a[0], a[1]), (b[0], b[1])), ov((a[2], a[3]), (b[2], b[3]))
                            if o1 > 0.01 and o2 > 0.01:
                                print('[COPLANAR] %-20s %-20s axis=%s at=%.4f (faces %.4f/%.4f) overlap=%.3f' % (_names[_i], _names[_j], _ax, pa, pa, pb, min(o1, o2)))
                                _cop += 1
    print('[COPLANAR] total', _cop)
except Exception as _e:
    print('[COPLANAR] failed:', _e)

# --- 室外家具真实世界坐标接地检查（bound_box 是局部坐标，必须乘 matrix_world）---
try:
    def _wz(o):
        return [(o.matrix_world @ Vector(c)).z for c in o.bound_box]
    for _tag, _pref in (('bench', 'Bench_'), ('mailbox', ('MailBox', 'Post_'))):
        _grp = [o for o in parts if o.name.startswith(_pref)]
        if not _grp:
            print('[WORLD] %s: no objects' % _tag); continue
        _all = [z for o in _grp for z in _wz(o)]
        _low = [o for o in _grp if min(_wz(o)) < -0.17]
        print('[WORLD] %s n=%d z=[%.3f,%.3f] grounded_objs=%d' % (_tag, len(_grp), min(_all), max(_all), len(_low)))
except Exception as _e:
    print('[WORLD] failed:', _e)

objs = join_by_material(parts)

# 自检（任何异常都不阻断导出）
try:
    print('[CHECK] objs=', len(objs))
    print('[CHECK] pilasters=%d corners=4 dado_z0=%.1f' % (n_pil, TRIMS[0][1]))
    print('[CHECK] front_faces=', len(front.data.polygons))
    for name, loc, deg in sash_check:
        print(f'[CHECK] {name} center=({loc[0]:.3f}, {loc[1]:.3f}, {loc[2]:.3f}) rot_z={deg:.1f}°')
    (_, lc, la), (_, rc, ra) = sash_check
    print('[CHECK] sash L=(%.2f,%.2f,%.2f) ang=%.0f | R=(%.2f,%.2f,%.2f) ang=%.0f' % (*lc, la, *rc, ra))
    for name, c in sign_check:
        print(f'[CHECK] {name} bbox_center=({c.x:.3f}, {c.y:.3f}, {c.z:.3f})')
    if counter_z is not None:
        print(f'[CHECK] Counter bbox z min={counter_z[0]:.3f} max={counter_z[1]:.3f} (expect 0.12 / {TOP:.2f})')
    print('[CHECK] divider x=[%.2f,%.2f] top_z=%.2f glass_area=%.2f' % (X0, X1, TOP, glass_area))
    for name, zmin in mail_zmin:
        print(f'[CHECK] {name} z_min={zmin:.3f} {"OK" if zmin >= 0.12 - 1e-4 else "BELOW FLOOR"}')
    if new_zmin is not None:
        print('[CHECK] parcels=%d letters=%d chairs=%d z_min=%.3f' % (len(mail), n_let, len(SVC), new_zmin))
    if plant_check is not None:
        print(f'[CHECK] Bench z_min={plant_check[0]:.3f} (expect ≈0.12) | Vine z_min={plant_check[1]:.3f} (expect 2.2~2.6)')
    print(f'[CHECK] leaves: vine={len(leaves)} bush={6 * len(PLANTERS)} total={len(leaves) + 6 * len(PLANTERS)}')
    if mailbox_check is not None:
        zlo, zhi, cx, cy = mailbox_check
        print(f'[CHECK] Mailbox z_min={zlo:.3f} z_max={zhi:.3f} center=({cx:.3f}, {cy:.3f}) '
              f'{"OK" if abs(zlo - MZ) < 1e-3 and cx > 3.11 else "CHECK POS"} (expect z {MZ:.2f}~{MZ + 1.35:.2f})')
    if desk_check is not None:
        print('[CHECK] desk x=[%.2f,%.2f] y=[%.2f,%.2f] top_z=%.2f z_min=%.3f' % desk_check)
    print('[CHECK] window w/h and glass alpha updated')
    print('[CHECK] lights:', list(LIGHTS), '| LGT mats:', [m.name for m in bpy.data.materials if m.name.startswith('LGT_')])
    print('[CHECK] wall_detail objs=%d gutter_z=%.2f pipe_z=[%.2f,%.2f]' % (n_wd, GZ, PZ0, PZ1))
    print('[CHECK] roof_vent=1 roof_pipe=1 door_open=60')
    print('[CHECK] BV=', BV)
    print('[CHECK] backdoor x=%.2f through=%s faces_before=%d faces_after=%d' % (BD_X, door_thru, bd_f0, bd_f1))
    print('[CHECK] backdoor through=%s cut_depth=%.2f > wall+lining=%.2f' % (door_thru, BD_CUT, 0.22 + 0.06))
    # 窗洞穿透：起点取左半格中心 x=-2.45（窗洞中心 -2.05 正对中竖梃 Win_Mullion），y=-3.05 在洞内、窗扇之后，沿 +Y 打；第一命中应落在室内（y > -2.9）
    deps = bpy.context.evaluated_depsgraph_get()
    _rx = -2.45
    hit, _hl, _hn, _hi, ho, _hm = bpy.context.scene.ray_cast(deps, (_rx, -3.05, 1.80), (0, 1, 0), distance=4.0)
    hit_y, hit_name = (_hl.y, ho.name) if hit else (float('nan'), 'none')
    print('[CHECK] ray x=%.2f hit_y=%.2f hit_obj=%s through=%s' % (_rx, hit_y, hit_name, (not hit) or hit_y > -2.9))
    _bzs = lambda pre: [c.z for o in bench if o.name.startswith(pre) for c in o.bound_box]
    _lz, _fz = _bzs('Bench_Leg_'), _bzs('Bench_Foot_')
    _out_z = [c.z for o in bench + mailbox for c in o.bound_box]
    print('[CHECK] outdoor z_min=%.3f (should = -0.180) bench=%.3f mailbox=%.3f' % (
        min(_out_z), min(c.z for o in bench for c in o.bound_box), min(c.z for o in mailbox for c in o.bound_box)))
    if _lz and _fz:
        print('[CHECK] bench low: legs=%.3f pads=%.3f (both should be ~0.000)' % (min(_lz), min(_fz)))
    else:
        print('[CHECK] bench names:', sorted(o.name for o in bench))
    os.makedirs('out/models', exist_ok=True)
except Exception as e:
    print('[CHECK] failed:', e)

export_glb('out/models/post.glb', objs)
