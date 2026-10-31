"""Rainbow's Castle - 超高密度版（目标 45 万三角面 / 20 MB+）
对照 02-鸟瞰庭院.jpg，全面提升密度：
- 尺寸放大到 30×30 米
- 所有圆柱 48~64 边
- 球体 32 段 24 环
- 墙面砖缝横竖逐条
- 瓦片逐片叠加
- 窗框多层（套、楣、棂、台）
- 门板分格、铆钉逐个
- 院子石板逐块、花朵逐个、池岸石逐块
Blender 4.5+ / Python 3.11
"""
import sys, os, math
sys.path.insert(0, os.path.dirname(__file__))
from lib_building import *

reset_scene()

# ========== 材质定义 ==========
M_PINK_WALL = mat('pink_wall', '#FFB8D1', roughness=0.75)
M_CREAM_STONE = mat('cream_stone', '#F5E6D3', roughness=0.82)
M_RED_ROOF = mat('red_roof', '#A63446', roughness=0.65)
M_WOOD_DARK = mat('wood_dark', '#6B4423', roughness=0.92)
M_METAL_IRON = mat('metal_iron', '#3C3C3C', roughness=0.35, metallic=0.85)
M_BRASS = mat('brass', '#D4AF37', roughness=0.22, metallic=0.92)
M_WINDOW_GLOW = mat('window_glow', '#FFE4A0', roughness=0.08)
M_WATER = mat('water', '#5DADE2', roughness=0.03)
M_GRASS = mat('grass', '#7CB342', roughness=0.93)
M_GROUND_STONE = mat('ground_stone', '#E8DCC8', roughness=0.88)
M_FLOWER_PINK = mat('flower_pink', '#F8BBD0', roughness=0.62)
M_FLOWER_WHITE = mat('flower_white', '#FFFFFF', roughness=0.52)
M_GREEN_LEAF = mat('green_leaf', '#66BB6A', roughness=0.72)
M_SLIDE_R = mat('slide_red', '#FF0000', roughness=0.28)
M_SLIDE_O = mat('slide_orange', '#FF7F00', roughness=0.28)
M_SLIDE_Y = mat('slide_yellow', '#FFFF00', roughness=0.28)
M_SLIDE_G = mat('slide_green', '#00FF00', roughness=0.28)
M_SLIDE_C = mat('slide_cyan', '#00FFFF', roughness=0.28)
M_SLIDE_B = mat('slide_blue', '#0000FF', roughness=0.28)
M_SLIDE_P = mat('slide_purple', '#8B00FF', roughness=0.28)

all_objs = []

# ========== 地面基础（石板逐块铺）==========
print("[地面] 开始铺设石板...")
for ix in range(-15, 15):
    for iy in range(-14, 10):
        tile = box(f'tile_{ix}_{iy}', (0.92, 0.92, 0.2),
                  loc=(ix, iy, 0.1), material=M_GROUND_STONE, bevel=0.006)
        all_objs.append(tile)

# 后方草地
grass_area = box('grass', (24, 18, 0.25), loc=(0, 6, 0.125), material=M_GRASS, bevel=0.012)
all_objs.append(grass_area)

# ========== 城门建筑（高精度拱门 + 砖缝）==========
print("[城门] 构建主墙...")
gate_wall = box('gate_wall', (18, 4.5, 8), loc=(0, -14, 4), material=M_PINK_WALL, bevel=0.04)
all_objs.append(gate_wall)

# 砖缝横向（每 0.5 米一条）
for iz in range(16):
    brick_h = box(f'gw_brick_h_{iz}', (17.5, 0.03, 0.06),
                 loc=(0, -11.8, 0.3 + iz * 0.5), material=M_CREAM_STONE, bevel=0.001)
    all_objs.append(brick_h)

# 砖缝竖向（错缝排列）
for ix in range(-8, 9):
    for iz in range(8):
        shift_x = 0.25 if iz % 2 == 0 else 0
        brick_v = box(f'gw_brick_v_{ix}_{iz}', (0.06, 0.03, 0.48),
                     loc=(ix * 1.05 + shift_x, -11.8, 0.55 + iz * 1.0), material=M_CREAM_STONE, bevel=0.001)
        all_objs.append(brick_v)

# 拱门洞（高精度半圆）
gate_arch_cutter = cyl('arch_cut', radius=2.8, height=5.5, loc=(0, -14, 2.8),
                       rot=(math.pi/2, 0, 0), verts=64, bevel=0)
boolean_cut(gate_wall, gate_arch_cutter)

# 拱门石砌边框（逐块拱券石）
for i in range(18):
    angle = math.pi * i / 17
    r = 2.9
    x, z = r * math.sin(angle) - 0.0, r * math.cos(angle) + 2.8
    voussoir = box(f'voussoir_{i}', (0.48, 0.3, 0.35), loc=(x, -15.8, z),
                  rot=(0, 0, -angle), material=M_CREAM_STONE, bevel=0.01)
    all_objs.append(voussoir)
    voussoir2 = box(f'voussoir_b_{i}', (0.48, 0.3, 0.35), loc=(x, -12.2, z),
                   rot=(0, 0, -angle), material=M_CREAM_STONE, bevel=0.01)
    all_objs.append(voussoir2)

# 拱心石（顶部）
keystone = box('keystone', (0.55, 4.5, 0.5), loc=(0, -14, 5.6),
              material=M_BRASS, bevel=0.015)
all_objs.append(keystone)

# 门前台阶（五级，逐级递减）
for i in range(5):
    step = box(f'step_{i}', (6 - i * 0.4, 1.4, 0.32), loc=(0, -17 - i * 0.7, 0.16 + i * 0.32),
              material=M_CREAM_STONE, bevel=0.012)
    all_objs.append(step)

print("[城门] 构建木门...")
# 左门扇（分 6 块木板）
for i in range(6):
    plank = box(f'door_L_plank_{i}', (0.32, 0.2, 4.2),
               loc=(-1.8 + i * 0.33, -15.8, 2.8), rot=(0, 0, math.radians(22)),
               material=M_WOOD_DARK, bevel=0.008)
    all_objs.append(plank)

# 右门扇
for i in range(6):
    plank = box(f'door_R_plank_{i}', (0.32, 0.2, 4.2),
               loc=(0.85 + i * 0.33, -15.8, 2.8), rot=(0, 0, math.radians(-22)),
               material=M_WOOD_DARK, bevel=0.008)
    all_objs.append(plank)

# 铁艺横带（3 条 × 2 门）
for side, x_base, rot_sign in [('L', -1.3, 22), ('R', 1.3, -22)]:
    for i, z in enumerate([1.5, 2.8, 4.1]):
        band = box(f'band_{side}_{i}', (1.9, 0.1, 0.14), loc=(x_base, -15.7, z),
                  rot=(0, 0, math.radians(rot_sign)), material=M_METAL_IRON, bevel=0.006)
        all_objs.append(band)
        # 每条铁带上 8 个铆钉
        for j in range(8):
            rivet = sphere(f'rivet_{side}_{i}_{j}', radius=0.032,
                          loc=(x_base + (j - 3.5) * 0.24, -15.6, z),
                          material=M_METAL_IRON, segs=12, rings=8)
            all_objs.append(rivet)

# 黄铜门环（每扇门，圆环 + 底座）
for x in [-1.3, 1.3]:
    base = cyl(f'ring_base_{x}', radius=0.22, height=0.08, loc=(x, -15.5, 2.8),
              rot=(math.pi/2, 0, 0), material=M_BRASS, verts=24, bevel=0.012)
    all_objs.append(base)
    ring = cyl(f'ring_{x}', radius=0.18, height=0.1, loc=(x, -15.4, 2.8),
              rot=(math.pi/2, 0, 0), material=M_BRASS, verts=24, bevel=0.008, cap=False)
    all_objs.append(ring)

# 门匾
sign = box('sign', (5, 0.4, 1.0), loc=(0, -9.5, 6.5), material=M_CREAM_STONE, bevel=0.025)
all_objs.append(sign)

# 门前灯笼（六角，带链条）
lantern = cyl('lantern', radius=0.25, height=0.65, loc=(0, -14, 5.8),
             verts=6, material=M_METAL_IRON, bevel=0.012)
all_objs.append(lantern)
lantern_top = cyl('lantern_top', radius=0.32, height=0.18, loc=(0, -14, 6.5),
                 verts=6, material=M_BRASS, bevel=0.01)
all_objs.append(lantern_top)
for i in range(8):
    chain_link = cyl(f'chain_{i}', radius=0.022, height=0.15, loc=(0, -14, 6.8 + i * 0.12),
                    verts=8, material=M_METAL_IRON, bevel=0)
    all_objs.append(chain_link)

print("[城门] 构建门塔...")
# 左右门塔（圆柱 + 收分 + 环箍 + 拱窗 + 锥顶瓦片）
for side, x in [('L', -9), ('R', 9)]:
    # 塔身（高精度圆柱）
    tower = cyl(f'gate_tower_{side}', radius=1.8, height=8.5, loc=(x, -14, 4.25),
               verts=56, material=M_PINK_WALL, bevel=0.035)
    all_objs.append(tower)
    # 收分（顶部缩小）
    select_only([tower])
    apply_all_modifiers(tower)
    bm = bmesh.new()
    bm.from_mesh(tower.data)
    for v in bm.verts:
        if v.co.z > 7.8:
            v.co.x *= 0.88
            v.co.y *= 0.88
    bm.to_mesh(tower.data)
    bm.free()

    # 石基座
    base = cyl(f'tower_base_{side}', radius=2.0, height=0.8, loc=(x, -14, 0.4),
              verts=56, material=M_CREAM_STONE, bevel=0.02)
    all_objs.append(base)

    # 环箍（三道）
    for i, z in enumerate([2.8, 5.2, 7.5]):
        ring = cyl(f'tower_ring_{side}_{i}', radius=1.88, height=0.3, loc=(x, -14, z),
                  verts=56, material=M_CREAM_STONE, bevel=0.015)
        all_objs.append(ring)

    # 拱窗（朝向中心）
    angle = math.atan2(14, -x)
    wx = x + 1.6 * math.cos(angle)
    wy = -14 + 1.6 * math.sin(angle)
    window = box(f'tower_win_{side}', (0.75, 0.15, 1.6), loc=(wx, wy, 5.5),
                rot=(0, 0, angle), material=M_WINDOW_GLOW, bevel=0.012)
    all_objs.append(window)
    # 窗套
    win_frame = box(f'tower_win_frame_{side}', (0.95, 0.2, 1.8), loc=(wx, wy, 5.5),
                   rot=(0, 0, angle), material=M_CREAM_STONE, bevel=0.015)
    all_objs.append(win_frame)

    # 锥形屋顶（逐圈瓦片叠加）
    roof_base = cyl(f'tower_roof_{side}', radius=2.1, height=3.2, loc=(x, -14, 10),
                   verts=56, material=M_RED_ROOF, bevel=0.022)
    select_only([roof_base])
    apply_all_modifiers(roof_base)
    bm = bmesh.new()
    bm.from_mesh(roof_base.data)
    for v in bm.verts:
        if v.co.z > 11.8:
            v.co.x *= 0.04
            v.co.y *= 0.04
    bm.to_mesh(roof_base.data)
    bm.free()
    all_objs.append(roof_base)

    # 瓦片（环形叠加，每圈 16 片）
    for ring in range(6):
        r = 2.0 - ring * 0.3
        z_base = 8.8 + ring * 0.45
        for i in range(16):
            angle_tile = math.pi * 2 * i / 16
            tx = x + r * math.cos(angle_tile)
            ty = -14 + r * math.sin(angle_tile)
            tile = box(f'tower_tile_{side}_{ring}_{i}', (0.28, 0.18, 0.38),
                      loc=(tx, ty, z_base), rot=(0, 0, angle_tile),
                      material=M_RED_ROOF, bevel=0.008)
            all_objs.append(tile)

    # 金球顶饰
    finial = sphere(f'tower_finial_{side}', radius=0.3, loc=(x, -14, 12.5),
                   material=M_BRASS, segs=32, rings=24)
    all_objs.append(finial)

# 门楼垛口（逐个）
for i in range(8):
    btl = box(f'gate_btl_{i}', (1.8, 4, 0.8),
             loc=(-7 + i * 2, -14, 7.6), material=M_CREAM_STONE, bevel=0.018)
    all_objs.append(btl)

print("[主塔] 开始构建...")
# ========== 主塔（三层退台 + 高密度窗框）==========
# 第一层（方形，7 面砖缝）
L1 = box('main_L1', (9, 9, 5.5), loc=(0, 0, 2.75), material=M_PINK_WALL, bevel=0.045)
all_objs.append(L1)

# 一层砖缝（横竖）
for iz in range(10):
    brick = box(f'L1_brick_h_{iz}', (8.8, 0.03, 0.06),
               loc=(0, 0, 0.3 + iz * 0.55), material=M_CREAM_STONE, bevel=0.001)
    all_objs.append(brick)
for ix in range(-4, 5):
    for iz in range(5):
        brick = box(f'L1_brick_v_{ix}_{iz}', (0.06, 0.03, 0.52),
                   loc=(ix * 1.0, 0, 0.6 + iz * 1.1), material=M_CREAM_STONE, bevel=0.001)
        all_objs.append(brick)

# 一层四角隅石柱（逐排）
for cx, cy in [(-4.5, -4.5), (4.5, -4.5), (-4.5, 4.5), (4.5, 4.5)]:
    for iz in range(8):
        quoin = box(f'L1_quoin_{cx}_{cy}_{iz}', (0.8, 0.8, 0.65),
                   loc=(cx, cy, 0.35 + iz * 0.68), material=M_CREAM_STONE, bevel=0.015)
        all_objs.append(quoin)

# 一层窗（四面各 3 扇，共 12 扇，每扇带窗套、窗楣、窗棂）
for side, (base_x, base_y, rot_angle) in enumerate([
    (0, -4.5, 0), (4.5, 0, math.pi/2), (0, 4.5, math.pi), (-4.5, 0, -math.pi/2)
]):
    for i, offset in enumerate([-2.2, 0, 2.2]):
        if side % 2 == 0:
            wx, wy = offset, base_y
        else:
            wx, wy = base_x, offset
        # 窗玻璃
        win = box(f'L1_win_{side}_{i}', (0.7, 0.15, 1.4), loc=(wx, wy, 3.0),
                 rot=(0, 0, rot_angle), material=M_WINDOW_GLOW, bevel=0.01)
        all_objs.append(win)
        # 窗套（米色石框）
        frame = box(f'L1_frame_{side}_{i}', (0.9, 0.2, 1.6), loc=(wx, wy, 3.0),
                   rot=(0, 0, rot_angle), material=M_CREAM_STONE, bevel=0.015)
        all_objs.append(frame)
        # 窗楣（上方装饰）
        lintel = box(f'L1_lintel_{side}_{i}', (1.0, 0.22, 0.22), loc=(wx, wy, 3.85),
                    rot=(0, 0, rot_angle), material=M_CREAM_STONE, bevel=0.012)
        all_objs.append(lintel)
        # 窗棂（横竖分格，3×3 格）
        for gx in range(-1, 2):
            mullion_v = box(f'L1_mullion_v_{side}_{i}_{gx}', (0.05, 0.08, 1.3),
                           loc=(wx + gx * 0.22, wy, 3.0), rot=(0, 0, rot_angle),
                           material=M_WOOD_DARK, bevel=0.003)
            all_objs.append(mullion_v)
        for gz in range(-1, 2):
            mullion_h = box(f'L1_mullion_h_{side}_{i}_{gz}', (0.65, 0.08, 0.05),
                           loc=(wx, wy, 3.0 + gz * 0.45), rot=(0, 0, rot_angle),
                           material=M_WOOD_DARK, bevel=0.003)
            all_objs.append(mullion_h)

# 一层檐口（多层线脚）
for i, (w, z_off) in enumerate([(9.5, 5.35), (9.7, 5.50), (9.9, 5.65)]):
    cornice = box(f'L1_cornice_{i}', (w, w, 0.12), loc=(0, 0, z_off),
                 material=M_CREAM_STONE, bevel=0.018)
    all_objs.append(cornice)

# 第二层（退台）
L2 = box('main_L2', (7, 7, 4.5), loc=(0, 0, 8), material=M_PINK_WALL, bevel=0.04)
all_objs.append(L2)

# 二层砖缝
for iz in range(8):
    brick = box(f'L2_brick_h_{iz}', (6.8, 0.03, 0.06),
               loc=(0, 0, 5.9 + iz * 0.55), material=M_CREAM_STONE, bevel=0.001)
    all_objs.append(brick)

# 二层隅石
for cx, cy in [(-3.5, -3.5), (3.5, -3.5), (-3.5, 3.5), (3.5, 3.5)]:
    for iz in range(6):
        quoin = box(f'L2_quoin_{cx}_{cy}_{iz}', (0.7, 0.7, 0.7),
                   loc=(cx, cy, 5.9 + iz * 0.73), material=M_CREAM_STONE, bevel=0.015)
        all_objs.append(quoin)

# 二层窗（四面各 2 扇）
for side, (base_x, base_y, rot_angle) in enumerate([
    (0, -3.5, 0), (3.5, 0, math.pi/2), (0, 3.5, math.pi), (-3.5, 0, -math.pi/2)
]):
    for i, offset in enumerate([-1.5, 1.5]):
        if side % 2 == 0:
            wx, wy = offset, base_y
        else:
            wx, wy = base_x, offset
        win = box(f'L2_win_{side}_{i}', (0.65, 0.15, 1.3), loc=(wx, wy, 8.2),
                 rot=(0, 0, rot_angle), material=M_WINDOW_GLOW, bevel=0.01)
        all_objs.append(win)
        frame = box(f'L2_frame_{side}_{i}', (0.85, 0.2, 1.5), loc=(wx, wy, 8.2),
                   rot=(0, 0, rot_angle), material=M_CREAM_STONE, bevel=0.015)
        all_objs.append(frame)

# 二层窗台花箱（8 个，每个 5 朵花）
for i, angle in enumerate([0, 45, 90, 135, 180, 225, 270, 315]):
    rad = math.radians(angle)
    px, py = 3.2 * math.cos(rad), 3.2 * math.sin(rad)
    pot = box(f'L2_pot_{i}', (0.8, 0.4, 0.25), loc=(px, py, 5.7),
             material=M_CREAM_STONE, bevel=0.012)
    all_objs.append(pot)
    # 绿叶丛
    for j in range(3):
        leaf = sphere(f'L2_leaf_{i}_{j}', radius=0.18,
                     loc=(px + (j - 1) * 0.15, py, 5.95 + j * 0.05),
                     material=M_GREEN_LEAF, segs=16, rings=12)
        all_objs.append(leaf)
    # 花朵（5 朵）
    for j in range(5):
        flower = sphere(f'L2_flower_{i}_{j}', radius=0.12,
                       loc=(px + (j - 2) * 0.12, py, 6.1 + j * 0.06),
                       material=M_FLOWER_PINK if j % 2 else M_FLOWER_WHITE,
                       segs=16, rings=12)
        all_objs.append(flower)

# 二层檐口
for i, (w, z_off) in enumerate([(7.5, 10.25), (7.7, 10.40)]):
    cornice = box(f'L2_cornice_{i}', (w, w, 0.12), loc=(0, 0, z_off),
                 material=M_CREAM_STONE, bevel=0.018)
    all_objs.append(cornice)

# 第三层（圆柱塔身）
L3 = cyl('main_L3', radius=2.5, height=4.5, loc=(0, 0, 13),
        verts=64, material=M_PINK_WALL, bevel=0.035)
all_objs.append(L3)

# 三层环箍（三道）
for i, z in enumerate([11.0, 13.0, 15.0]):
    ring = cyl(f'L3_ring_{i}', radius=2.58, height=0.32, loc=(0, 0, z),
              verts=64, material=M_CREAM_STONE, bevel=0.015)
    all_objs.append(ring)

# 三层拱窗（八个方向）
for i, angle in enumerate([0, 45, 90, 135, 180, 225, 270, 315]):
    rad = math.radians(angle)
    wx, wy = 2.2 * math.cos(rad), 2.2 * math.sin(rad)
    win = box(f'L3_win_{i}', (0.75, 0.15, 1.5), loc=(wx, wy, 13.0),
             rot=(0, 0, rad), material=M_WINDOW_GLOW, bevel=0.012)
    all_objs.append(win)
    frame = box(f'L3_frame_{i}', (0.95, 0.22, 1.7), loc=(wx, wy, 13.0),
               rot=(0, 0, rad), material=M_CREAM_STONE, bevel=0.015)
    all_objs.append(frame)

# 主塔锥形屋顶（瓦片逐片）
roof_cone = cyl('main_roof', radius=3.0, height=4.5, loc=(0, 0, 17.5),
               verts=64, material=M_RED_ROOF, bevel=0.025)
select_only([roof_cone])
apply_all_modifiers(roof_cone)
bm = bmesh.new()
bm.from_mesh(roof_cone.data)
for v in bm.verts:
    if v.co.z > 19.2:
        v.co.x *= 0.03
        v.co.y *= 0.03
bm.to_mesh(roof_cone.data)
bm.free()
all_objs.append(roof_cone)

# 主塔瓦片（逐圈叠加，12 圈）
print("[主塔] 铺设屋顶瓦片...")
for ring in range(12):
    r = 2.8 - ring * 0.22
    z_base = 15.8 + ring * 0.35
    num_tiles = max(24, int(48 - ring * 3))
    for i in range(num_tiles):
        angle_tile = math.pi * 2 * i / num_tiles
        tx, ty = r * math.cos(angle_tile), r * math.sin(angle_tile)
        tile = box(f'main_tile_{ring}_{i}', (0.22, 0.15, 0.32),
                  loc=(tx, ty, z_base), rot=(0, 0, angle_tile),
                  material=M_RED_ROOF, bevel=0.006)
        all_objs.append(tile)

# 金球 + 旗杆
finial = sphere('main_finial', radius=0.38, loc=(0, 0, 20.5),
               material=M_BRASS, segs=32, rings=24)
all_objs.append(finial)
pole = cyl('flag_pole', radius=0.08, height=2.2, loc=(0, 0, 21.8),
          verts=16, material=M_BRASS, bevel=0)
all_objs.append(pole)
flag = panel('flag', [(0, 0), (1.0, 0.5), (0, 1.0)], thickness=0.04,
            loc=(0.1, 0, 22.5), material=M_PINK_WALL, bevel=0.01)
all_objs.append(flag)

print("[四角塔] 开始构建...")
# ========== 四角塔（四座，高密度）==========
corners = [(-10, -10, 'FL'), (10, -10, 'FR'), (-10, 10, 'BL'), (10, 10, 'BR')]
for tx, ty, name in corners:
    tower = cyl(f'corner_{name}', radius=2.0, height=9.5, loc=(tx, ty, 4.75),
               verts=56, material=M_PINK_WALL, bevel=0.035)
    all_objs.append(tower)
    select_only([tower])
    apply_all_modifiers(tower)
    bm = bmesh.new()
    bm.from_mesh(tower.data)
    for v in bm.verts:
        if v.co.z > 8.8:
            v.co.x *= 0.86
            v.co.y *= 0.86
    bm.to_mesh(tower.data)
    bm.free()

    base = cyl(f'corner_base_{name}', radius=2.2, height=0.9, loc=(tx, ty, 0.45),
              verts=56, material=M_CREAM_STONE, bevel=0.02)
    all_objs.append(base)

    for i, z in enumerate([3.2, 6.5, 9.0]):
        ring = cyl(f'corner_ring_{name}_{i}', radius=2.08, height=0.35, loc=(tx, ty, z),
                  verts=56, material=M_CREAM_STONE, bevel=0.015)
        all_objs.append(ring)

    angle_cen = math.atan2(-ty, -tx)
    wx = tx + 1.75 * math.cos(angle_cen)
    wy = ty + 1.75 * math.sin(angle_cen)
    win = box(f'corner_win_{name}', (0.8, 0.15, 1.7), loc=(wx, wy, 6.0),
             rot=(0, 0, angle_cen), material=M_WINDOW_GLOW, bevel=0.012)
    all_objs.append(win)
    frame = box(f'corner_frame_{name}', (1.0, 0.22, 1.9), loc=(wx, wy, 6.0),
               rot=(0, 0, angle_cen), material=M_CREAM_STONE, bevel=0.015)
    all_objs.append(frame)

    roof = cyl(f'corner_roof_{name}', radius=2.4, height=3.5, loc=(tx, ty, 11.25),
              verts=56, material=M_RED_ROOF, bevel=0.022)
    select_only([roof])
    apply_all_modifiers(roof)
    bm = bmesh.new()
    bm.from_mesh(roof.data)
    for v in bm.verts:
        if v.co.z > 12.8:
            v.co.x *= 0.04
            v.co.y *= 0.04
    bm.to_mesh(roof.data)
    bm.free()
    all_objs.append(roof)

    # 瓦片（5 圈）
    for ring in range(5):
        r = 2.2 - ring * 0.4
        z_base = 10.0 + ring * 0.55
        for i in range(20):
            angle_tile = math.pi * 2 * i / 20
            tile_x = tx + r * math.cos(angle_tile)
            tile_y = ty + r * math.sin(angle_tile)
            tile = box(f'corner_tile_{name}_{ring}_{i}', (0.25, 0.16, 0.35),
                      loc=(tile_x, tile_y, z_base), rot=(0, 0, angle_tile),
                      material=M_RED_ROOF, bevel=0.007)
            all_objs.append(tile)

    finial = sphere(f'corner_finial_{name}', radius=0.32, loc=(tx, ty, 14.5),
                   material=M_BRASS, segs=32, rings=24)
    all_objs.append(finial)

print("[城墙] 开始构建...")
# ========== 城墙（连接各塔，带垛口、射孔）==========
# 前墙左段
wall_FL = box('wall_FL', (2.2, 4, 6.5), loc=(-9.5, -12, 3.25),
             material=M_PINK_WALL, bevel=0.035)
all_objs.append(wall_FL)
for i in range(4):
    btl = box(f'wall_FL_btl_{i}', (0.7, 3.5, 0.8),
             loc=(-9.5 - 0.8 + i * 0.55, -12, 6.4), material=M_CREAM_STONE, bevel=0.015)
    all_objs.append(btl)

wall_FR = box('wall_FR', (2.2, 4, 6.5), loc=(9.5, -12, 3.25),
             material=M_PINK_WALL, bevel=0.035)
all_objs.append(wall_FR)
for i in range(4):
    btl = box(f'wall_FR_btl_{i}', (0.7, 3.5, 0.8),
             loc=(9.5 - 0.8 + i * 0.55, -12, 6.4), material=M_CREAM_STONE, bevel=0.015)
    all_objs.append(btl)

# 左墙
wall_L = box('wall_L', (4, 18, 6.8), loc=(-11, 0, 3.4),
            material=M_PINK_WALL, bevel=0.035)
all_objs.append(wall_L)
for i in range(9):
    btl = box(f'wall_L_btl_{i}', (3.5, 1.8, 0.8),
             loc=(-11, -8.5 + i * 2.1, 6.8), material=M_CREAM_STONE, bevel=0.015)
    all_objs.append(btl)

# 右墙
wall_R = box('wall_R', (4, 18, 6.8), loc=(11, 0, 3.4),
            material=M_PINK_WALL, bevel=0.035)
all_objs.append(wall_R)
for i in range(9):
    btl = box(f'wall_R_btl_{i}', (3.5, 1.8, 0.8),
             loc=(11, -8.5 + i * 2.1, 6.8), material=M_CREAM_STONE, bevel=0.015)
    all_objs.append(btl)

# 后墙
wall_B = box('wall_B', (20, 4, 6.8), loc=(0, 11, 3.4),
            material=M_PINK_WALL, bevel=0.035)
all_objs.append(wall_B)
for i in range(10):
    btl = box(f'wall_B_btl_{i}', (1.8, 3.5, 0.8),
             loc=(-9.5 + i * 2.1, 11, 6.8), material=M_CREAM_STONE, bevel=0.015)
    all_objs.append(btl)

print("[院子] 开始构建设施...")
# ========== 院子设施（对照 02-鸟瞰庭院.jpg）==========
# 中央喷泉（三层叠水）
fountain_base = cyl('fountain_base', radius=1.8, height=0.9, loc=(0, -5, 0.45),
                   verts=48, material=M_CREAM_STONE, bevel=0.025)
all_objs.append(fountain_base)
fountain_pool1 = cyl('fountain_pool1', radius=1.6, height=0.45, loc=(0, -5, 1.15),
                    verts=48, material=M_WATER, bevel=0.018)
all_objs.append(fountain_pool1)
fountain_pillar = cyl('fountain_pillar', radius=0.35, height=2.0, loc=(0, -5, 2.4),
                     verts=32, material=M_CREAM_STONE, bevel=0.015)
all_objs.append(fountain_pillar)
fountain_bowl2 = cyl('fountain_bowl2', radius=1.0, height=0.55, loc=(0, -5, 3.7),
                    verts=32, material=M_CREAM_STONE, bevel=0.02)
all_objs.append(fountain_bowl2)
fountain_water2 = cyl('fountain_water2', radius=0.88, height=0.2, loc=(0, -5, 3.9),
                     verts=32, material=M_WATER, bevel=0.012)
all_objs.append(fountain_water2)

# 左侧豆形池塘（放大 + 池岸石逐块）
pool = cyl('pool', radius=4.5, height=1.5, loc=(-7, 3, 0.75),
          verts=48, material=M_WATER, bevel=0.035)
all_objs.append(pool)

# 池岸石（逐块，环形）
for i in range(36):
    angle = math.pi * 2 * i / 36
    r = 4.7
    px = -7 + r * math.cos(angle)
    py = 3 + r * math.sin(angle)
    edge_stone = box(f'pool_edge_{i}', (0.45, 0.35, 0.4),
                    loc=(px, py, 1.65), rot=(0, 0, angle),
                    material=M_CREAM_STONE, bevel=0.012)
    all_objs.append(edge_stone)

# 睡莲（8 朵，逐朵）
lily_pos = [(-6.5, 2), (-7.5, 3.5), (-6, 4), (-8, 2.5), (-7, 4.5), (-6.5, 1.5), (-8.5, 3), (-7.5, 1.8)]
for i, (px, py) in enumerate(lily_pos):
    pad = cyl(f'lily_pad_{i}', radius=0.32, height=0.06, loc=(px, py, 1.53),
             verts=16, material=M_GREEN_LEAF, bevel=0.01)
    all_objs.append(pad)
    flower = sphere(f'lily_flower_{i}', radius=0.15, loc=(px, py, 1.62),
                   material=M_FLOWER_WHITE if i % 2 else M_FLOWER_PINK,
                   segs=16, rings=12)
    all_objs.append(flower)

# 木桥（横跨池塘，桥板逐条）
for i in range(16):
    plank = box(f'bridge_plank_{i}', (0.22, 1.3, 0.15),
               loc=(-10.5 + i * 0.55, 3, 2.0), material=M_WOOD_DARK, bevel=0.01)
    all_objs.append(plank)

# 桥栏杆（两侧，支柱 + 横杆）
for side in [-0.65, 0.65]:
    for i in range(8):
        post = cyl(f'bridge_post_{side}_{i}', radius=0.04, height=0.65,
                  loc=(-10 + i * 1.2, 3 + side, 2.3), verts=8,
                  material=M_WOOD_DARK, bevel=0)
        all_objs.append(post)
    rail = cyl(f'bridge_rail_{side}', radius=0.05, height=9, loc=(-7, 3 + side, 2.55),
              rot=(0, math.pi/2, 0), verts=8, material=M_WOOD_DARK, bevel=0)
    all_objs.append(rail)

# 秋千架（池后）
swing_L = cyl('swing_L', radius=0.11, height=3.2, loc=(-9, 8, 1.6),
             verts=12, material=M_WOOD_DARK, bevel=0)
all_objs.append(swing_L)
swing_R = cyl('swing_R', radius=0.11, height=3.2, loc=(-5, 8, 1.6),
             verts=12, material=M_WOOD_DARK, bevel=0)
all_objs.append(swing_R)
swing_bar = cyl('swing_bar', radius=0.09, height=4.2, loc=(-7, 8, 3.2),
               rot=(0, math.pi/2, 0), verts=12, material=M_WOOD_DARK, bevel=0)
all_objs.append(swing_bar)

# 双秋千座椅
for i, sx in enumerate([-7.8, -6.2]):
    seat = box(f'swing_seat_{i}', (0.75, 0.5, 0.15), loc=(sx, 8, 1.5),
              material=M_WOOD_DARK, bevel=0.012)
    all_objs.append(seat)
    for ry in [-0.2, 0.2]:
        rope = cyl(f'swing_rope_{i}_{ry}', radius=0.018, height=1.6,
                  loc=(sx, 8 + ry, 2.35), verts=8, material=M_METAL_IRON, bevel=0)
        all_objs.append(rope)

# 右侧游戏屋 + 彩虹滑梯
playhouse = cyl('playhouse', radius=1.4, height=3.8, loc=(7.5, 4.5, 1.9),
               verts=32, material=M_PINK_WALL, bevel=0.025)
all_objs.append(playhouse)
play_win = box('play_win', (0.55, 0.12, 0.8), loc=(7.5, 3.1, 2.5),
              material=M_WINDOW_GLOW, bevel=0.01)
all_objs.append(play_win)

play_roof = cyl('play_roof', radius=1.65, height=2.0, loc=(7.5, 4.5, 4.8),
               verts=32, material=M_RED_ROOF, bevel=0.02)
select_only([play_roof])
apply_all_modifiers(play_roof)
bm = bmesh.new()
bm.from_mesh(play_roof.data)
for v in bm.verts:
    if v.co.z > 5.9:
        v.co.x *= 0.05
        v.co.y *= 0.05
bm.to_mesh(play_roof.data)
bm.free()
all_objs.append(play_roof)

play_finial = sphere('play_finial', radius=0.18, loc=(7.5, 4.5, 6.7),
                    material=M_BRASS, segs=24, rings=16)
all_objs.append(play_finial)

# 彩虹滑梯（七色，逐条台阶）
slide_mats = [M_SLIDE_R, M_SLIDE_O, M_SLIDE_Y, M_SLIDE_G, M_SLIDE_C, M_SLIDE_B, M_SLIDE_P]
for step in range(14):
    mat_idx = step % 7
    slide_step = box(f'slide_step_{step}', (1.8, 0.35, 0.18),
                    loc=(6.2 + step * 0.25, 2.5 + step * 0.2, 3.2 - step * 0.22),
                    rot=(0, math.radians(-35), 0), material=slide_mats[mat_idx], bevel=0.01)
    all_objs.append(slide_step)

# 滑梯扶手（两侧）
for side, sy in [('L', 1.5), ('R', 3.5)]:
    rail = cyl(f'slide_rail_{side}', radius=0.06, height=4.5,
              loc=(6.5, sy, 2.8), rot=(0, math.radians(-35), 0),
              verts=10, material=M_WOOD_DARK, bevel=0)
    all_objs.append(rail)

# 门前花盆（两侧，每侧 8 朵花）
for fx in [-3, 3]:
    pot = cyl(f'gate_pot_{fx}', radius=0.45, height=0.65, loc=(fx, -8.5, 0.325),
             verts=20, material=M_CREAM_STONE, bevel=0.018)
    all_objs.append(pot)
    for i in range(8):
        flower = sphere(f'gate_flower_{fx}_{i}', radius=0.18,
                       loc=(fx + (i - 3.5) * 0.12, -8.5, 0.75 + i * 0.06),
                       material=M_FLOWER_PINK if i % 2 else M_FLOWER_WHITE,
                       segs=16, rings=12)
        all_objs.append(flower)
    for i in range(5):
        leaf = sphere(f'gate_leaf_{fx}_{i}', radius=0.22,
                     loc=(fx + (i - 2) * 0.15, -8.5, 0.65),
                     material=M_GREEN_LEAF, segs=14, rings=10)
        all_objs.append(leaf)

# 花坛（四角）
for fx, fy in [(-5, -3), (5, -3), (-5, -7), (5, -7)]:
    bed = box(f'flowerbed_{fx}_{fy}', (1.5, 1.5, 0.4), loc=(fx, fy, 0.2),
             material=M_CREAM_STONE, bevel=0.015)
    all_objs.append(bed)
    # 每个花坛 12 朵花
    for i in range(12):
        px = fx + (i % 4 - 1.5) * 0.3
        py = fy + (i // 4 - 1) * 0.3
        flower = sphere(f'bed_flower_{fx}_{fy}_{i}', radius=0.14,
                       loc=(px, py, 0.5 + i * 0.03),
                       material=M_FLOWER_PINK if i % 2 else M_FLOWER_WHITE,
                       segs=14, rings=10)
        all_objs.append(flower)

# ========== 合并导出 ==========
print(f"[完成] 创建了 {len(all_objs)} 个对象")

merged = join_by_material(all_objs, tol=0.001)
print(f"[合并] 按材质合并后剩余 {len(merged)} 个网格")

out_path = 'D:/hermes/home/out/models/castle.glb'
stats = export_glb(out_path, merged)
print(f"[导出] ✓ {out_path}")
print(f"  网格数: {stats['meshes']}, 三角面: {stats['tris']:,}, 材质数: {stats['materials']}, 文件大小: {stats['bytes'] / (1024*1024):.2f} MB")
