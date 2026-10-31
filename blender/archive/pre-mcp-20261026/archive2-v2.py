"""Rainbow's Castle - 完整重建版
严格对照 02-鸟瞰庭院.jpg，做到：
1. 真拱门（门洞+木门+铁艺+门环+门匾+台阶）
2. 主塔三层退台（檐口+窗+锥形瓦顶+金球旗杆）
3. 四角塔收分+环箍+拱窗+锥形顶
4. 院子设施（豆形池+木桥、秋千、游戏屋+彩虹滑梯、喷泉、石板路）
5. 工艺细节（砖纹、隅石、石基座、窗台花箱、灯笼）
6. 材质分明（粉墙、米石、酒红瓦、木、铁、铜、发光玻璃、水、草）
Blender 4.5+ / Python 3.11
"""
import sys, os, math
sys.path.insert(0, os.path.dirname(__file__))
from lib_building import *

reset_scene()

# ========== 材质定义（扩充到可辨认） ==========
M_PINK_WALL = mat('pink_wall', '#FFB8D1', roughness=0.75)         # 粉墙（哑光）
M_CREAM_STONE = mat('cream_stone', '#F5E6D3', roughness=0.82)     # 米色石材
M_RED_ROOF = mat('red_roof', '#A63446', roughness=0.65)           # 酒红瓦顶
M_WOOD_DARK = mat('wood_dark', '#6B4423', roughness=0.92)         # 中棕木
M_METAL_IRON = mat('metal_iron', '#3C3C3C', roughness=0.35, metallic=0.85)  # 暗灰铁
M_BRASS = mat('brass', '#D4AF37', roughness=0.22, metallic=0.92)  # 亮黄铜
M_WINDOW_GLOW = mat('window_glow', '#FFE4A0', roughness=0.08)     # 暖黄玻璃（后续加自发光）
M_WATER = mat('water', '#5DADE2', roughness=0.03)                 # 青蓝水面
M_GRASS = mat('grass', '#7CB342', roughness=0.93)                 # 鲜绿草地
M_GROUND_STONE = mat('ground_stone', '#E8DCC8', roughness=0.88)   # 浅色石板
M_FLOWER_PINK = mat('flower_pink', '#F8BBD0', roughness=0.62)
M_FLOWER_WHITE = mat('flower_white', '#FFFFFF', roughness=0.52)
M_GREEN_LEAF = mat('green_leaf', '#66BB6A', roughness=0.72)
# 彩虹滑梯七色
M_SLIDE_R = mat('slide_red', '#FF0000', roughness=0.28)
M_SLIDE_O = mat('slide_orange', '#FF7F00', roughness=0.28)
M_SLIDE_Y = mat('slide_yellow', '#FFFF00', roughness=0.28)
M_SLIDE_G = mat('slide_green', '#00FF00', roughness=0.28)
M_SLIDE_C = mat('slide_cyan', '#00FFFF', roughness=0.28)
M_SLIDE_B = mat('slide_blue', '#0000FF', roughness=0.28)
M_SLIDE_P = mat('slide_purple', '#8B00FF', roughness=0.28)

all_objs = []

# ========== 地面基础 ==========
# 院子地面（浅色石板，前方）
courtyard_floor = box('courtyard_floor', (20, 18, 0.25), loc=(0, -1, 0.125), material=M_GROUND_STONE, bevel=0.015)
all_objs.append(courtyard_floor)

# 后方草地区域
grass_area = box('grass_area', (16, 12, 0.28), loc=(0, 3.5, 0.14), material=M_GRASS, bevel=0.015)
all_objs.append(grass_area)

# 主路径（中轴线石板，从门到主塔）
main_path = box('main_path', (2.5, 14, 0.3), loc=(0, -3, 0.15), material=M_CREAM_STONE, bevel=0.01)
all_objs.append(main_path)

# ========== 城门建筑（最重要：做出真正的拱门）==========

# 门楼主体墙（粉色，左右门塔之间）
gate_wall = box('gate_wall', (12, 3.5, 6), loc=(0, -10, 3), material=M_PINK_WALL, bevel=0.04)
all_objs.append(gate_wall)

# **真正的拱形门洞**：用半圆柱切割出能看进院子的洞
gate_arch_cutter = cyl('gate_arch_cutter', radius=2.2, height=4, loc=(0, -10, 2.2),
                       rot=(math.pi/2, 0, 0), verts=24, bevel=0)
boolean_cut(gate_wall, gate_arch_cutter)

# 拱门厚度（门洞内侧石砌边框，米色）
arch_inner_ring = cyl('arch_inner_ring', radius=2.3, height=0.25, loc=(0, -11.75, 2.2),
                     rot=(math.pi/2, 0, 0), material=M_CREAM_STONE, verts=24, bevel=0.015, cap=False)
all_objs.append(arch_inner_ring)
arch_outer_ring = cyl('arch_outer_ring', radius=2.3, height=0.25, loc=(0, -8.25, 2.2),
                     rot=(math.pi/2, 0, 0), material=M_CREAM_STONE, verts=24, bevel=0.015, cap=False)
all_objs.append(arch_outer_ring)

# 门前台阶（三级石阶）
for i in range(3):
    step_w = 5 - i * 0.3
    step = box(f'gate_step_{i}', (step_w, 1.2, 0.3), loc=(0, -12.5 - i*0.6, 0.15 + i*0.3),
              material=M_CREAM_STONE, bevel=0.015)
    all_objs.append(step)

# **木质双开门**（向外打开15度，有板缝和铁艺）
# 左门扇
left_door = box('gate_door_left', (1.8, 0.18, 3.8), loc=(-1.0, -11.5, 2.0),
               rot=(0, 0, math.radians(18)), material=M_WOOD_DARK, bevel=0.015)
all_objs.append(left_door)
# 门板竖缝（5条）
for i in range(5):
    plank = box(f'left_door_plank_{i}', (0.35, 0.05, 3.6),
               loc=(-1.65 + i*0.36, -11.4, 2.0), rot=(0, 0, math.radians(18)),
               material=M_WOOD_DARK, bevel=0.005)
    all_objs.append(plank)

# 右门扇（镜像）
right_door = box('gate_door_right', (1.8, 0.18, 3.8), loc=(1.0, -11.5, 2.0),
                rot=(0, 0, math.radians(-18)), material=M_WOOD_DARK, bevel=0.015)
all_objs.append(right_door)
for i in range(5):
    plank = box(f'right_door_plank_{i}', (0.35, 0.05, 3.6),
               loc=(0.85 + i*0.36, -11.4, 2.0), rot=(0, 0, math.radians(-18)),
               material=M_WOOD_DARK, bevel=0.005)
    all_objs.append(plank)

# **铁艺横带**（3条暗灰铁条横跨门板）
for i, z in enumerate([1.2, 2.0, 2.8]):
    # 左门
    band_l = box(f'left_door_band_{i}', (1.7, 0.08, 0.12), loc=(-1.0, -11.42, z),
                rot=(0, 0, math.radians(18)), material=M_METAL_IRON, bevel=0.005)
    all_objs.append(band_l)
    # 右门
    band_r = box(f'right_door_band_{i}', (1.7, 0.08, 0.12), loc=(1.0, -11.42, z),
                rot=(0, 0, math.radians(-18)), material=M_METAL_IRON, bevel=0.005)
    all_objs.append(band_r)

# **铆钉**（每条铁带两端，共6对/门）
for i, z in enumerate([1.2, 2.0, 2.8]):
    for j, offset in enumerate([-0.75, 0.75]):
        # 左门铆钉
        rivet_l = sphere(f'left_rivet_{i}_{j}', radius=0.035,
                        loc=(-1.0 + offset, -11.35, z), material=M_METAL_IRON)
        all_objs.append(rivet_l)
        # 右门铆钉
        rivet_r = sphere(f'right_rivet_{i}_{j}', radius=0.035,
                        loc=(1.0 + offset, -11.35, z), material=M_METAL_IRON)
        all_objs.append(rivet_r)

# **黄铜门环**（每扇门中部，圆环+底座）
for x in [-1.0, 1.0]:
    # 门环底座（圆形铜盘）
    base = cyl(f'door_ring_base_{x}', radius=0.18, height=0.05, loc=(x, -11.3, 2.0),
              rot=(math.pi/2, 0, 0), material=M_BRASS, verts=16, bevel=0.01)
    all_objs.append(base)
    # 圆环（略微向前）
    ring = cyl(f'door_ring_{x}', radius=0.15, height=0.08, loc=(x, -11.25, 2.0),
              rot=(math.pi/2, 0, 0), material=M_BRASS, verts=16, bevel=0.008, cap=False)
    all_objs.append(ring)

# **门匾**（米色石牌匾，刻 "Rainbow's Castle"，门楣上方）
sign_board = box('castle_sign', (4.5, 0.35, 0.9), loc=(0, -8.5, 5.8),
                material=M_CREAM_STONE, bevel=0.025)
all_objs.append(sign_board)
# 文字浮雕（简化为凹槽条）
sign_text = box('sign_text_relief', (3.8, 0.05, 0.5), loc=(0, -8.35, 5.8),
               material=M_PINK_WALL, bevel=0.005)
all_objs.append(sign_text)

# **门前悬挂灯笼**（六角金属灯笼，门洞上方）
lantern_body = cyl('gate_lantern', radius=0.22, height=0.55, loc=(0, -10, 4.2),
                  verts=6, material=M_METAL_IRON, bevel=0.01)
all_objs.append(lantern_body)
lantern_top = cyl('lantern_top', radius=0.28, height=0.15, loc=(0, -10, 4.9),
                 verts=6, material=M_BRASS, bevel=0.008)
all_objs.append(lantern_top)
lantern_chain = cyl('lantern_chain', radius=0.02, height=0.5, loc=(0, -10, 5.35),
                   verts=6, material=M_METAL_IRON, bevel=0)
all_objs.append(lantern_chain)

# **门塔（左右各一，圆柱+收分+环箍+拱窗+锥形顶）**
for side, x in [('left', -6.5), ('right', 6.5)]:
    # 塔身（圆柱，有收分：底部半径大，顶部略小）
    tower = cyl(f'{side}_gate_tower', radius=1.5, height=7, loc=(x, -10, 3.5),
               verts=20, material=M_PINK_WALL, bevel=0.035)
    all_objs.append(tower)
    # 手动收分（顶部缩小到0.92倍）
    select_only([tower])
    apply_all_modifiers(tower)
    bm = bmesh.new()
    bm.from_mesh(tower.data)
    for v in bm.verts:
        if v.co.z > 6.5:  # 顶部
            v.co.x *= 0.92
            v.co.y *= 0.92
    bm.to_mesh(tower.data)
    bm.free()

    # 米色石基座
    base = cyl(f'{side}_gate_tower_base', radius=1.7, height=0.6, loc=(x, -10, 0.3),
              verts=20, material=M_CREAM_STONE, bevel=0.02)
    all_objs.append(base)

    # 环箍（两道米色石腰线）
    for i, z in enumerate([2.5, 5.0]):
        ring = cyl(f'{side}_gate_tower_ring_{i}', radius=1.58, height=0.25, loc=(x, -10, z),
                  verts=20, material=M_CREAM_STONE, bevel=0.015)
        all_objs.append(ring)

    # 拱窗（朝向中轴，暖黄玻璃）
    angle_to_center = math.atan2(10, -x)
    wx = x + 1.35 * math.cos(angle_to_center)
    wy = -10 + 1.35 * math.sin(angle_to_center)
    window = box(f'{side}_gate_tower_window', (0.6, 0.12, 1.3), loc=(wx, wy, 4.5),
                rot=(0, 0, angle_to_center), material=M_WINDOW_GLOW, bevel=0.01)
    all_objs.append(window)

    # 锥形屋顶（酒红瓦）
    roof = cyl(f'{side}_gate_tower_roof', radius=1.8, height=2.5, loc=(x, -10, 8.25),
              verts=20, material=M_RED_ROOF, bevel=0.02)
    select_only([roof])
    apply_all_modifiers(roof)
    bm = bmesh.new()
    bm.from_mesh(roof.data)
    for v in bm.verts:
        if v.co.z > 9.5:
            v.co.x *= 0.06
            v.co.y *= 0.06
    bm.to_mesh(roof.data)
    bm.free()
    all_objs.append(roof)

    # 金球顶饰
    finial = sphere(f'{side}_gate_tower_finial', radius=0.25, loc=(x, -10, 10.6),
                   material=M_BRASS, segs=14, rings=10)
    all_objs.append(finial)

# 门楼垛口（门塔之间的墙顶，米色石）
for i in range(6):
    battlement = box(f'gate_battlement_{i}', (1.6, 3, 0.7),
                    loc=(-5 + i*2, -10, 6.4), material=M_CREAM_STONE, bevel=0.02)
    all_objs.append(battlement)

# ========== 主塔（三层退台+檐口+窗+锥形瓦顶）==========

# **第一层**（最底层，最宽，方形）
main_L1 = box('main_tower_L1', (7, 7, 4.5), loc=(0, 0, 2.25), material=M_PINK_WALL, bevel=0.045)
all_objs.append(main_L1)

# 一层四角米色隅石柱
for x, y in [(-3.5, -3.5), (3.5, -3.5), (-3.5, 3.5), (3.5, 3.5)]:
    corner = box(f'main_L1_corner_{x}_{y}', (0.7, 0.7, 4.5), loc=(x, y, 2.25),
                material=M_CREAM_STONE, bevel=0.02)
    all_objs.append(corner)

# 一层四面各2扇窗（共8扇）
for side, (wx, wy, angle) in enumerate([
    (0, -3.5, 0), (3.5, 0, math.pi/2), (0, 3.5, math.pi), (-3.5, 0, -math.pi/2)
]):
    for i, offset in enumerate([-1.2, 1.2]):
        if side % 2 == 0:  # 前后
            wloc = (offset, wy, 2.5)
        else:  # 左右
            wloc = (wx, offset, 2.5)
        window = box(f'main_L1_window_{side}_{i}', (0.55, 0.12, 1.1),
                    loc=wloc, rot=(0, 0, angle), material=M_WINDOW_GLOW, bevel=0.01)
        all_objs.append(window)

# 一层檐口（米色石腰线）
L1_cornice = box('main_L1_cornice', (7.5, 7.5, 0.3), loc=(0, 0, 4.65),
                material=M_CREAM_STONE, bevel=0.025)
all_objs.append(L1_cornice)

# **第二层**（退台，稍小）
main_L2 = box('main_tower_L2', (5.5, 5.5, 3.8), loc=(0, 0, 6.8), material=M_PINK_WALL, bevel=0.04)
all_objs.append(main_L2)

# 二层四角隅石
for x, y in [(-2.75, -2.75), (2.75, -2.75), (-2.75, 2.75), (2.75, 2.75)]:
    corner = box(f'main_L2_corner_{x}_{y}', (0.6, 0.6, 3.8), loc=(x, y, 6.8),
                material=M_CREAM_STONE, bevel=0.018)
    all_objs.append(corner)

# 二层窗（四面各1扇，共4扇）
for side, (wx, wy, angle) in enumerate([
    (0, -2.75, 0), (2.75, 0, math.pi/2), (0, 2.75, math.pi), (-2.75, 0, -math.pi/2)
]):
    window = box(f'main_L2_window_{side}', (0.6, 0.12, 1.2),
                loc=(wx, wy, 7.0), rot=(0, 0, angle), material=M_WINDOW_GLOW, bevel=0.01)
    all_objs.append(window)

# 二层窗台花箱（4个）
for i, angle in enumerate([45, 135, 225, 315]):
    rad = math.radians(angle)
    px, py = 2.5 * math.cos(rad), 2.5 * math.sin(rad)
    pot = box(f'main_L2_planter_{i}', (0.7, 0.35, 0.22), loc=(px, py, 6.0),
             material=M_CREAM_STONE, bevel=0.012)
    all_objs.append(pot)
    # 绿叶+粉花
    leaf = sphere(f'main_L2_leaf_{i}', radius=0.22, loc=(px, py, 6.25),
                 material=M_GREEN_LEAF, segs=10, rings=8)
    all_objs.append(leaf)
    flower = sphere(f'main_L2_flower_{i}', radius=0.14, loc=(px, py, 6.42),
                   material=M_FLOWER_PINK, segs=10, rings=8)
    all_objs.append(flower)

# 二层檐口
L2_cornice = box('main_L2_cornice', (6, 6, 0.28), loc=(0, 0, 8.84),
                material=M_CREAM_STONE, bevel=0.022)
all_objs.append(L2_cornice)

# **第三层**（圆柱塔身）
main_L3 = cyl('main_tower_L3', radius=2.0, height=3.5, loc=(0, 0, 10.75),
             verts=24, material=M_PINK_WALL, bevel=0.035)
all_objs.append(main_L3)

# 三层环箍（米色石腰线）
L3_ring = cyl('main_L3_ring', radius=2.08, height=0.25, loc=(0, 0, 9.5),
             verts=24, material=M_CREAM_STONE, bevel=0.015)
all_objs.append(L3_ring)

# 三层拱窗（四个方向，暖黄玻璃）
for i, angle in enumerate([0, 90, 180, 270]):
    rad = math.radians(angle)
    wx, wy = 1.75 * math.cos(rad), 1.75 * math.sin(rad)
    window = box(f'main_L3_window_{i}', (0.65, 0.12, 1.35), loc=(wx, wy, 10.75),
                rot=(0, 0, rad), material=M_WINDOW_GLOW, bevel=0.012)
    all_objs.append(window)

# **锥形瓦顶**（酒红色，真正的锥形）
main_roof = cyl('main_roof_cone', radius=2.5, height=3.5, loc=(0, 0, 13.75),
               verts=24, material=M_RED_ROOF, bevel=0.025)
select_only([main_roof])
apply_all_modifiers(main_roof)
bm = bmesh.new()
bm.from_mesh(main_roof.data)
for v in bm.verts:
    if v.co.z > 15.8:
        v.co.x *= 0.04
        v.co.y *= 0.04
bm.to_mesh(main_roof.data)
bm.free()
all_objs.append(main_roof)

# 金球顶饰
main_finial = sphere('main_finial', radius=0.32, loc=(0, 0, 17.1),
                    material=M_BRASS, segs=16, rings=12)
all_objs.append(main_finial)

# 旗杆（黄铜）
flag_pole = cyl('flag_pole', radius=0.06, height=1.8, loc=(0, 0, 18.1),
               verts=10, material=M_BRASS, bevel=0)
all_objs.append(flag_pole)

# 粉色旗（三角旗）
flag_verts = [(0, 0), (0.8, 0.4), (0, 0.8)]
flag = panel('castle_flag', flag_verts, thickness=0.03, loc=(0.05, 0, 18.5),
            rot=(0, 0, 0), material=M_PINK_WALL, bevel=0.008)
all_objs.append(flag)

# ========== 四角塔（前后左右各一，收分+环箍+拱窗+锥形顶）==========
corner_positions = [
    (-8, -7, 'front_left'),
    (8, -7, 'front_right'),
    (-8, 7, 'back_left'),
    (8, 7, 'back_right')
]

for tx, ty, name in corner_positions:
    # 塔身（圆柱，有收分）
    tower = cyl(f'corner_tower_{name}', radius=1.6, height=8, loc=(tx, ty, 4),
               verts=20, material=M_PINK_WALL, bevel=0.035)
    select_only([tower])
    apply_all_modifiers(tower)
    bm = bmesh.new()
    bm.from_mesh(tower.data)
    for v in bm.verts:
        if v.co.z > 7.5:
            v.co.x *= 0.9
            v.co.y *= 0.9
    bm.to_mesh(tower.data)
    bm.free()
    all_objs.append(tower)

    # 米色石基座
    base = cyl(f'corner_tower_base_{name}', radius=1.8, height=0.7, loc=(tx, ty, 0.35),
              verts=20, material=M_CREAM_STONE, bevel=0.02)
    all_objs.append(base)

    # 环箍（两道）
    for i, z in enumerate([2.8, 5.8]):
        ring = cyl(f'corner_tower_ring_{name}_{i}', radius=1.68, height=0.28,
                  loc=(tx, ty, z), verts=20, material=M_CREAM_STONE, bevel=0.015)
        all_objs.append(ring)

    # 拱窗（朝向中心）
    angle_to_center = math.atan2(-ty, -tx)
    wx = tx + 1.45 * math.cos(angle_to_center)
    wy = ty + 1.45 * math.sin(angle_to_center)
    window = box(f'corner_tower_window_{name}', (0.65, 0.12, 1.4), loc=(wx, wy, 5.0),
                rot=(0, 0, angle_to_center), material=M_WINDOW_GLOW, bevel=0.012)
    all_objs.append(window)

    # 锥形屋顶（酒红瓦）
    roof = cyl(f'corner_tower_roof_{name}', radius=1.95, height=2.8, loc=(tx, ty, 9.4),
              verts=20, material=M_RED_ROOF, bevel=0.022)
    select_only([roof])
    apply_all_modifiers(roof)
    bm = bmesh.new()
    bm.from_mesh(roof.data)
    for v in bm.verts:
        if v.co.z > 11.0:
            v.co.x *= 0.05
            v.co.y *= 0.05
    bm.to_mesh(roof.data)
    bm.free()
    all_objs.append(roof)

    # 金球顶饰
    finial = sphere(f'corner_tower_finial_{name}', radius=0.26, loc=(tx, ty, 12.1),
                   material=M_BRASS, segs=14, rings=10)
    all_objs.append(finial)

# ========== 城墙（连接各塔，带垛口）==========

# 前墙左段（左前塔到左门塔）
front_wall_L = box('front_wall_left', (1.8, 3.2, 5), loc=(-7.25, -8.5, 2.5),
                  material=M_PINK_WALL, bevel=0.035)
all_objs.append(front_wall_L)
for i in range(3):
    btl = box(f'front_wall_L_btl_{i}', (0.65, 2.8, 0.65),
             loc=(-7.25 - 0.6 + i*0.6, -8.5, 5.35), material=M_CREAM_STONE, bevel=0.015)
    all_objs.append(btl)

# 前墙右段（右门塔到右前塔）
front_wall_R = box('front_wall_right', (1.8, 3.2, 5), loc=(7.25, -8.5, 2.5),
                  material=M_PINK_WALL, bevel=0.035)
all_objs.append(front_wall_R)
for i in range(3):
    btr = box(f'front_wall_R_btl_{i}', (0.65, 2.8, 0.65),
             loc=(7.25 - 0.6 + i*0.6, -8.5, 5.35), material=M_CREAM_STONE, bevel=0.015)
    all_objs.append(btr)

# 左墙（左前塔到左后塔）
left_wall = box('left_wall', (3.2, 14, 5.5), loc=(-9, 0, 2.75),
               material=M_PINK_WALL, bevel=0.035)
all_objs.append(left_wall)
for i in range(7):
    btl = box(f'left_wall_btl_{i}', (2.8, 1.6, 0.7),
             loc=(-9, -6.5 + i*2.2, 5.6), material=M_CREAM_STONE, bevel=0.015)
    all_objs.append(btl)

# 右墙（右前塔到右后塔）
right_wall = box('right_wall', (3.2, 14, 5.5), loc=(9, 0, 2.75),
                material=M_PINK_WALL, bevel=0.035)
all_objs.append(right_wall)
for i in range(7):
    btr = box(f'right_wall_btl_{i}', (2.8, 1.6, 0.7),
             loc=(9, -6.5 + i*2.2, 5.6), material=M_CREAM_STONE, bevel=0.015)
    all_objs.append(btr)

# 后墙（左后塔到右后塔）
back_wall = box('back_wall', (16, 3.2, 5.5), loc=(0, 9, 2.75),
               material=M_PINK_WALL, bevel=0.035)
all_objs.append(back_wall)
for i in range(8):
    btl = box(f'back_wall_btl_{i}', (1.6, 2.8, 0.7),
             loc=(-7.5 + i*2.2, 9, 5.6), material=M_CREAM_STONE, bevel=0.015)
    all_objs.append(btl)

# ========== 院子设施（对照02-鸟瞰庭院.jpg布局）==========

# **中央喷泉**（圆形，两层叠水盘）
fountain_base = cyl('fountain_base', radius=1.4, height=0.7, loc=(0, -3.5, 0.35),
                   verts=20, material=M_CREAM_STONE, bevel=0.025)
all_objs.append(fountain_base)
# 底层水盘（蓝水）
fountain_bowl1 = cyl('fountain_bowl1', radius=1.25, height=0.35, loc=(0, -3.5, 0.9),
                    verts=20, material=M_WATER, bevel=0.015)
all_objs.append(fountain_bowl1)
# 中央柱
fountain_pillar = cyl('fountain_pillar', radius=0.28, height=1.6, loc=(0, -3.5, 1.8),
                     verts=16, material=M_CREAM_STONE, bevel=0.015)
all_objs.append(fountain_pillar)
# 上层水盘
fountain_bowl2 = cyl('fountain_bowl2', radius=0.85, height=0.45, loc=(0, -3.5, 2.9),
                    verts=18, material=M_CREAM_STONE, bevel=0.018)
all_objs.append(fountain_bowl2)
# 上层水面
fountain_water2 = cyl('fountain_water2', radius=0.75, height=0.15, loc=(0, -3.5, 3.05),
                     verts=18, material=M_WATER, bevel=0.01)
all_objs.append(fountain_water2)

# **左侧豆形池塘+木桥**
# 池塘主体（用椭球近似）
pool = cyl('pool_main', radius=3.5, height=1.2, loc=(-5.5, 2, 0.6),
          verts=28, material=M_WATER, bevel=0.035)
all_objs.append(pool)
# 池岸（米色石）
pool_edge = cyl('pool_edge', radius=3.7, height=0.35, loc=(-5.5, 2, 1.35),
               verts=28, material=M_CREAM_STONE, bevel=0.02, cap=False)
all_objs.append(pool_edge)
# 睡莲（3朵粉白花）
for i, (px, py) in enumerate([(-5, 1.5), (-6, 2.5), (-5.5, 3)]):
    lily_pad = cyl(f'lily_pad_{i}', radius=0.25, height=0.05, loc=(px, py, 1.22),
                  verts=12, material=M_GREEN_LEAF, bevel=0.008)
    all_objs.append(lily_pad)
    lily_flower = sphere(f'lily_flower_{i}', radius=0.12, loc=(px, py, 1.28),
                        material=M_FLOWER_WHITE if i % 2 else M_FLOWER_PINK, segs=10, rings=8)
    all_objs.append(lily_flower)

# **横跨池塘的木桥**
bridge_deck = box('bridge_deck', (7, 1.0, 0.18), loc=(-5.5, 2, 1.55),
                 material=M_WOOD_DARK, bevel=0.018)
all_objs.append(bridge_deck)
# 桥面木板（10条）
for i in range(10):
    plank = box(f'bridge_plank_{i}', (0.15, 1.0, 0.12),
               loc=(-8.5 + i*0.7, 2, 1.6), material=M_WOOD_DARK, bevel=0.008)
    all_objs.append(plank)
# 桥栏杆（两侧）
for side in [-0.5, 0.5]:
    rail = cyl(f'bridge_rail_{side}', radius=0.05, height=7.2, loc=(-5.5, 2 + side, 1.85),
              rot=(0, math.pi/2, 0), verts=8, material=M_WOOD_DARK, bevel=0)
    all_objs.append(rail)

# **池后秋千架**（木架+双座）
# 左右支柱
swing_L = cyl('swing_post_L', radius=0.09, height=2.8, loc=(-7, 5.8, 1.4),
             verts=10, material=M_WOOD_DARK, bevel=0)
all_objs.append(swing_L)
swing_R = cyl('swing_post_R', radius=0.09, height=2.8, loc=(-4, 5.8, 1.4),
             verts=10, material=M_WOOD_DARK, bevel=0)
all_objs.append(swing_R)
# 顶部横杆
swing_bar = cyl('swing_bar', radius=0.07, height=3.2, loc=(-5.5, 5.8, 2.8),
               rot=(0, math.pi/2, 0), verts=10, material=M_WOOD_DARK, bevel=0)
all_objs.append(swing_bar)
# 秋千座椅（两个）
for i, sx in enumerate([-6.2, -4.8]):
    seat = box(f'swing_seat_{i}', (0.65, 0.45, 0.12), loc=(sx, 5.8, 1.3),
              material=M_WOOD_DARK, bevel=0.012)
    all_objs.append(seat)
    # 绳子（简化为细杆）
    for ry in [-0.18, 0.18]:
        rope = cyl(f'swing_rope_{i}_{ry}', radius=0.015, height=1.4, loc=(sx, 5.8 + ry, 2.05),
                  verts=6, material=M_METAL_IRON, bevel=0)
        all_objs.append(rope)

# **右侧游戏屋+彩虹滑梯**
# 游戏屋塔身（小圆塔）
playhouse = cyl('playhouse_tower', radius=1.15, height=3.2, loc=(6, 3.5, 1.6),
               verts=16, material=M_PINK_WALL, bevel=0.025)
all_objs.append(playhouse)
# 小窗
play_window = box('playhouse_window', (0.45, 0.1, 0.65), loc=(6, 2.35, 2.2),
                 material=M_WINDOW_GLOW, bevel=0.01)
all_objs.append(play_window)
# 锥形屋顶
play_roof = cyl('playhouse_roof', radius=1.35, height=1.6, loc=(6, 3.5, 4.0),
               verts=16, material=M_RED_ROOF, bevel=0.02)
select_only([play_roof])
apply_all_modifiers(play_roof)
bm = bmesh.new()
bm.from_mesh(play_roof.data)
for v in bm.verts:
    if v.co.z > 4.9:
        v.co.x *= 0.06
        v.co.y *= 0.06
bm.to_mesh(play_roof.data)
bm.free()
all_objs.append(play_roof)
# 小金球
play_finial = sphere('playhouse_finial', radius=0.15, loc=(6, 3.5, 5.5),
                    material=M_BRASS, segs=12, rings=8)
all_objs.append(play_finial)

# **彩虹七色滑梯**（从塔台到地面，七条色带）
slide_materials = [M_SLIDE_R, M_SLIDE_O, M_SLIDE_Y, M_SLIDE_G, M_SLIDE_C, M_SLIDE_B, M_SLIDE_P]
for i, mat in enumerate(slide_materials):
    slide_strip = box(f'slide_strip_{i}', (0.25, 3.5, 0.15),
                     loc=(5.2 + i*0.26, 1.8, 2.2), rot=(0, math.radians(-32), 0),
                     material=mat, bevel=0.012)
    all_objs.append(slide_strip)

# 滑梯扶手（两侧木栏杆）
for side, sy in [('L', 0.6), ('R', 3.0)]:
    rail = cyl(f'slide_rail_{side}', radius=0.05, height=3.8, loc=(5.2, sy, 2.4),
              rot=(0, math.radians(-32), 0), verts=8, material=M_WOOD_DARK, bevel=0)
    all_objs.append(rail)

# ========== 装饰物 ==========

# **门前花盆**（两侧）
for fx in [-2.5, 2.5]:
    pot = cyl(f'gate_planter_{fx}', radius=0.35, height=0.55, loc=(fx, -6.5, 0.275),
             verts=14, material=M_CREAM_STONE, bevel=0.015)
    all_objs.append(pot)
    # 花丛（粉白花+绿叶）
    for i in range(4):
        flower = sphere(f'gate_flower_{fx}_{i}', radius=0.16,
                       loc=(fx + (i-1.5)*0.15, -6.5, 0.65 + i*0.08),
                       material=M_FLOWER_PINK if i % 2 else M_FLOWER_WHITE, segs=10, rings=8)
        all_objs.append(flower)
    leaf = sphere(f'gate_leaf_{fx}', radius=0.25, loc=(fx, -6.5, 0.55),
                 material=M_GREEN_LEAF, segs=10, rings=8)
    all_objs.append(leaf)

# **墙面砖纹理提示**（在粉墙上添加细微凹陷，暗示砖缝）
# （这里简化为几个示意性浅槽，真实砖纹需要纹理贴图）
brick_accent = box('brick_accent_sample', (0.4, 0.02, 0.25), loc=(3, -9.8, 3),
                  material=M_CREAM_STONE, bevel=0.005)
all_objs.append(brick_accent)

# **隅石示意**（主塔第一层四角已有，这里额外在门楼角落加一个）
gate_quoin = box('gate_quoin_sample', (0.45, 3.3, 1.2), loc=(-6, -10, 1.5),
                material=M_CREAM_STONE, bevel=0.018)
all_objs.append(gate_quoin)

# ========== 合并导出 ==========
print(f"[build_castle] 创建了 {len(all_objs)} 个对象")

# 按材质合并（提升性能）
merged = join_by_material(all_objs, tol=0.001)
print(f"[build_castle] 按材质合并后剩余 {len(merged)} 个网格")

# 导出 GLB
out_path = 'D:/hermes/home/out/models/castle.glb'
export_glb(out_path, merged)
print(f"[build_castle] ✓ 导出完成: {out_path}")
