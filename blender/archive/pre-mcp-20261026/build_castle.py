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

# ========== 地面基础（bmesh 一次生成，不要 900 个对象）==========
print("[地面] 开始铺设石板...")
ground_obj = new_obj('ground_tiles')
bm = bmesh.new()
for ix in range(-15, 15):
    for iy in range(-14, 10):
        cx, cy = ix * 1.0, iy * 1.0
        # 每块 0.92×0.92，间隙 0.08
        verts = [
            bm.verts.new((cx - 0.46, cy - 0.46, 0.0)),
            bm.verts.new((cx + 0.46, cy - 0.46, 0.0)),
            bm.verts.new((cx + 0.46, cy + 0.46, 0.0)),
            bm.verts.new((cx - 0.46, cy + 0.46, 0.0)),
            bm.verts.new((cx - 0.46, cy - 0.46, 0.2)),
            bm.verts.new((cx + 0.46, cy - 0.46, 0.2)),
            bm.verts.new((cx + 0.46, cy + 0.46, 0.2)),
            bm.verts.new((cx - 0.46, cy + 0.46, 0.2)),
        ]
        # 六面体
        faces = [
            [verts[0], verts[1], verts[2], verts[3]],  # bottom
            [verts[4], verts[5], verts[6], verts[7]],  # top
            [verts[0], verts[1], verts[5], verts[4]],
            [verts[1], verts[2], verts[6], verts[5]],
            [verts[2], verts[3], verts[7], verts[6]],
            [verts[3], verts[0], verts[4], verts[7]],
        ]
        for f in faces:
            bm.faces.new(f)
bm.to_mesh(ground_obj.data)
bm.free()
ground_obj.data.materials.append(M_GROUND_STONE)
bv = ground_obj.modifiers.new('Bevel', 'BEVEL')
bv.width, bv.segments, bv.limit_method = 0.006, 2, 'ANGLE'
bv.angle_limit, bv.harden_normals = ANGLE, True
all_objs.append(ground_obj)

# 后方草地
grass_area = box('grass', (24, 18, 0.25), loc=(0, 6, 0.125), material=M_GRASS, bevel=0.012)
all_objs.append(grass_area)

# ========== 城门建筑（高精度拱门 + 砖缝）==========
print("[城门] 构建主墙...")
gate_wall = box('gate_wall', (18, 4.5, 8), loc=(0, -14, 4), material=M_PINK_WALL, bevel=0.04)
all_objs.append(gate_wall)

# 砖缝（bmesh 一次生成，不要 153 个对象）
brick_joints_obj = new_obj('gate_brick_joints')
bm = bmesh.new()

def _joint_quad(x0, x1, z0, z1, y=-11.815):
    """在墙正面生成一条砖缝面片（直接持有顶点引用，不用下标索引）"""
    v0 = bm.verts.new((x0, y, z0))
    v1 = bm.verts.new((x1, y, z0))
    v2 = bm.verts.new((x1, y, z1))
    v3 = bm.verts.new((x0, y, z1))
    bm.faces.new((v0, v1, v2, v3))

JH = 0.07
# 横向砖缝：门洞区域（|x|<3.15 且 z<5.9）断开，分左右两段
for iz in range(16):
    z = 0.3 + iz * 0.5
    if z < 5.9:
        _joint_quad(-8.75, -3.15, z, z + JH)
        _joint_quad(3.15, 8.75, z, z + JH)
    else:
        _joint_quad(-8.75, 8.75, z, z + JH)
# 竖向砖缝：门洞两侧到底，门洞上方从拱顶开始
for ix in range(-16, 17):
    x = ix * 0.5 + 0.25
    if abs(x) > 3.15:
        _joint_quad(x, x + JH, 0.3, 7.9)
    else:
        _joint_quad(x, x + JH, 6.2, 7.9)
bm.normal_update()
bm.to_mesh(brick_joints_obj.data)
bm.free()
brick_joints_obj.data.materials.append(M_CREAM_STONE)
all_objs.append(brick_joints_obj)

# 拱门洞（改为真正的拱形门洞，保留墙体厚度）
gate_arch_cutter = box('arch_cut', (5.8, 5.0, 5.8), loc=(0, -14, 2.9),
                       material=None, bevel=0)
# 做成拱形：上半圆形切割
arch_top = cyl('arch_top_cut', radius=2.9, height=5.5, loc=(0, -14, 2.9),
               rot=(math.pi/2, 0, 0), verts=64, bevel=0)
boolean_cut(gate_arch_cutter, arch_top)
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

# 铁艺横带（3 条 × 2 门）+ 铆钉（用 bmesh 一次生成每侧）
for side, x_base, rot_sign in [('L', -1.3, 22), ('R', 1.3, -22)]:
    band_obj = new_obj(f'bands_{side}')
    bm = bmesh.new()
    for i, z in enumerate([1.5, 2.8, 4.1]):
        # 横带主体（简化为单层面片）
        w, h = 1.9, 0.14
        cos_r, sin_r = math.cos(math.radians(rot_sign)), math.sin(math.radians(rot_sign))
        cx, cy = x_base, -15.7
        for dx in [-w/2, w/2]:
            for dz in [z - h/2, z + h/2]:
                rx = cx + dx * cos_r
                ry = cy - 0.05
                bm.verts.new((rx, ry, dz))
        # 8 个铆钉（小球体，简化为 8 边）
        for j in range(8):
            rx_rivet = x_base + (j - 3.5) * 0.24
            ry_rivet = -15.6
            rivet_r = 0.032
            rivet_base = len(bm.verts)
            for seg_i in range(8):
                angle_seg = math.pi * 2 * seg_i / 8
                bm.verts.new((rx_rivet + rivet_r * math.cos(angle_seg), ry_rivet + rivet_r * math.sin(angle_seg), z))
    bm.to_mesh(band_obj.data)
    bm.free()
    band_obj.data.materials.append(M_METAL_IRON)
    all_objs.append(band_obj)

# 黄铜门环（每扇门，圆环 + 底座）
for x in [-1.3, 1.3]:
    base = cyl(f'ring_base_{x}', radius=0.22, height=0.08, loc=(x, -15.5, 2.8),
              rot=(math.pi/2, 0, 0), material=M_BRASS, verts=24, bevel=0.012)
    all_objs.append(base)
    ring = cyl(f'ring_{x}', radius=0.18, height=0.1, loc=(x, -15.4, 2.8),
              rot=(math.pi/2, 0, 0), material=M_BRASS, verts=24, bevel=0.008, cap=False)
    all_objs.append(ring)

# 门匾（位置上移，避开拱顶，文字清晰可见）
sign = box('sign', (5.5, 0.45, 1.1), loc=(0, -11.2, 7.2), material=M_CREAM_STONE, bevel=0.025)
all_objs.append(sign)
# 门匾上的文字凸起（"Rainbow's Castle"，用简单几何体示意）
for i, letter_x in enumerate([-2.2, -1.5, -0.8, -0.1, 0.6, 1.3, 2.0]):
    letter = box(f'sign_letter_{i}', (0.3, 0.15, 0.7),
                loc=(letter_x, -11.0, 7.2), material=M_BRASS, bevel=0.01)
    all_objs.append(letter)

# 门前灯笼（移到门楣两侧，不挂在拱门中央）
for lx in [-3.5, 3.5]:
    lantern = cyl(f'lantern_{lx}', radius=0.28, height=0.75, loc=(lx, -11.5, 6.8),
                 verts=6, material=M_METAL_IRON, bevel=0.012)
    all_objs.append(lantern)
    lantern_top = cyl(f'lantern_top_{lx}', radius=0.35, height=0.2, loc=(lx, -11.5, 7.6),
                     verts=6, material=M_BRASS, bevel=0.01)
    all_objs.append(lantern_top)
    # 链条（向上连接到墙体）
    for i in range(4):
        chain_link = cyl(f'chain_{lx}_{i}', radius=0.025, height=0.18, loc=(lx, -11.5, 7.9 + i * 0.15),
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

    # 锥形屋顶（深红瓦，清晰的锥形，顶部收尖）
    roof_base = cyl(f'tower_roof_{side}', radius=2.15, height=3.8, loc=(x, -14, 10.5),
                   verts=56, material=M_RED_ROOF, bevel=0.022)
    select_only([roof_base])
    apply_all_modifiers(roof_base)
    bm = bmesh.new()
    bm.from_mesh(roof_base.data)
    for v in bm.verts:
        # 让顶部收成尖锥
        local_z = v.co.z - 10.5
        if local_z > 0:
            ratio = 1.0 - (local_z / 3.8) * 0.96  # 顶部收到 4% 半径
            v.co.x *= ratio
            v.co.y *= ratio
    bm.to_mesh(roof_base.data)
    bm.free()
    all_objs.append(roof_base)

    # 瓦片（bmesh 一次生成，6 圈 × 16 片 = 96 片/塔）
    tiles_obj = new_obj(f'tower_tiles_{side}')
    bm = bmesh.new()
    for ring in range(6):
        r = 2.0 - ring * 0.3
        z_base = 9.3 + ring * 0.6
        for i in range(16):
            angle_tile = math.pi * 2 * i / 16
            tx = x + r * math.cos(angle_tile)
            ty = -14 + r * math.sin(angle_tile)
            # 每片瓦 0.28 × 0.18 × 0.38
            cos_a, sin_a = math.cos(angle_tile), math.sin(angle_tile)
            for dx in [-0.14, 0.14]:
                for dy in [-0.09, 0.09]:
                    for dz in [0, 0.38]:
                        bm.verts.new((tx + dx * cos_a - dy * sin_a, ty + dx * sin_a + dy * cos_a, z_base + dz))
    bm.to_mesh(tiles_obj.data)
    bm.free()
    tiles_obj.data.materials.append(M_RED_ROOF)
    all_objs.append(tiles_obj)

    # 金球顶饰（清晰可见）
    finial = sphere(f'tower_finial_{side}', radius=0.35, loc=(x, -14, 14.5),
                   material=M_BRASS, segs=32, rings=24)
    all_objs.append(finial)

# 门楼垛口（bmesh 一次生成 8 个）
gate_btl_obj = new_obj('gate_battlements')
bm = bmesh.new()
for i in range(8):
    x = -7 + i * 2
    for dx in [-0.9, 0.9]:
        for dy in [-2.0, 2.0]:
            for dz in [7.2, 8.0]:
                bm.verts.new((x + dx, -14 + dy, dz))
bm.to_mesh(gate_btl_obj.data)
bm.free()
gate_btl_obj.data.materials.append(M_CREAM_STONE)
all_objs.append(gate_btl_obj)

print("[主塔] 开始构建...")
# ========== 主塔（三层明显退台 + 高密度窗框）==========
# 第一层（方形，比例调整让退台明显）
L1 = box('main_L1', (9, 9, 5.0), loc=(0, 0, 2.5), material=M_PINK_WALL, bevel=0.045)
all_objs.append(L1)

# 一层砖缝（横向主要，减少对象数）
bricks_L1 = new_obj('L1_bricks')
bm = bmesh.new()
for iz in range(10):
    z = 0.3 + iz * 0.5
    for dy in [-0.015, 0.015]:
        for dx in [-4.4, 4.4]:
            bm.verts.new((dx, dy, z))
bm.to_mesh(bricks_L1.data)
bm.free()
bricks_L1.data.materials.append(M_CREAM_STONE)
all_objs.append(bricks_L1)

# 一层四角隅石柱（bmesh 一次生成）
quoins_L1_obj = new_obj('L1_quoins')
bm = bmesh.new()
for cx, cy in [(-4.5, -4.5), (4.5, -4.5), (-4.5, 4.5), (4.5, 4.5)]:
    for iz in range(8):
        z = 0.35 + iz * 0.68
        for dx in [-0.4, 0.4]:
            for dy in [-0.4, 0.4]:
                for dz in [0, 0.65]:
                    bm.verts.new((cx + dx, cy + dy, z + dz))
bm.to_mesh(quoins_L1_obj.data)
bm.free()
quoins_L1_obj.data.materials.append(M_CREAM_STONE)
all_objs.append(quoins_L1_obj)

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

# 第二层（明显退台，尺寸从 9→6.5，视觉上清晰）
L2 = box('main_L2', (6.5, 6.5, 4.2), loc=(0, 0, 7.6), material=M_PINK_WALL, bevel=0.04)
all_objs.append(L2)

# 二层砖缝（简化）
bricks_L2 = new_obj('L2_bricks')
bm = bmesh.new()
for iz in range(7):
    z = 5.6 + iz * 0.6
    for dy in [-0.015, 0.015]:
        for dx in [-3.2, 3.2]:
            bm.verts.new((dx, dy, z))
bm.to_mesh(bricks_L2.data)
bm.free()
bricks_L2.data.materials.append(M_CREAM_STONE)
all_objs.append(bricks_L2)

# 二层隅石（bmesh 一次生成）
quoins_L2_obj = new_obj('L2_quoins')
bm = bmesh.new()
for cx, cy in [(-3.5, -3.5), (3.5, -3.5), (-3.5, 3.5), (3.5, 3.5)]:
    for iz in range(6):
        z = 5.9 + iz * 0.73
        for dx in [-0.35, 0.35]:
            for dy in [-0.35, 0.35]:
                for dz in [0, 0.7]:
                    bm.verts.new((cx + dx, cy + dy, z + dz))
bm.to_mesh(quoins_L2_obj.data)
bm.free()
quoins_L2_obj.data.materials.append(M_CREAM_STONE)
all_objs.append(quoins_L2_obj)

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
    # 绿叶丛（保留手工球体，视觉基础）
    for j in range(3):
        leaf = sphere(f'L2_leaf_{i}_{j}', radius=0.18,
                     loc=(px + (j - 1) * 0.15, py, 5.95 + j * 0.05),
                     material=M_GREEN_LEAF, segs=16, rings=12)
        all_objs.append(leaf)
    # 花朵（复用现成模型，3 朵粉 + 2 朵白）
    for j in range(3):
        flowers_p = import_glb('D:/hermes/home/assets-src/nature/Models/GLTF format/flower_purpleB.glb',
                              name_prefix=f'L2_flower_p_{i}_{j}', scale=0.22,
                              loc=(px + (j - 1) * 0.15, py, 6.15 + j * 0.05),
                              recolor=M_FLOWER_PINK)
        all_objs.extend(flowers_p)
    for j in range(2):
        flowers_w = import_glb('D:/hermes/home/assets-src/nature/Models/GLTF format/flower_yellowC.glb',
                              name_prefix=f'L2_flower_w_{i}_{j}', scale=0.18,
                              loc=(px - (j - 0.5) * 0.18, py, 6.2 + j * 0.04),
                              recolor=M_FLOWER_WHITE)
        all_objs.extend(flowers_w)

# 二层檐口
for i, (w, z_off) in enumerate([(7.5, 10.25), (7.7, 10.40)]):
    cornice = box(f'L2_cornice_{i}', (w, w, 0.12), loc=(0, 0, z_off),
                 material=M_CREAM_STONE, bevel=0.018)
    all_objs.append(cornice)

# 第三层（圆柱塔身，再次明显收窄）
L3 = cyl('main_L3', radius=2.2, height=4.2, loc=(0, 0, 14.0),
        verts=64, material=M_PINK_WALL, bevel=0.035)
all_objs.append(L3)

# 三层环箍（三道）
for i, z in enumerate([12.2, 14.0, 15.8]):
    ring = cyl(f'L3_ring_{i}', radius=2.28, height=0.32, loc=(0, 0, z),
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

# 主塔锥形屋顶（深红色，明显的锥形）
roof_cone = cyl('main_roof', radius=2.8, height=4.8, loc=(0, 0, 19.0),
               verts=64, material=M_RED_ROOF, bevel=0.025)
select_only([roof_cone])
apply_all_modifiers(roof_cone)
bm = bmesh.new()
bm.from_mesh(roof_cone.data)
for v in bm.verts:
    local_z = v.co.z - 19.0
    if local_z > 0:
        ratio = 1.0 - (local_z / 4.8) * 0.97  # 顶部收到 3%
        v.co.x *= ratio
        v.co.y *= ratio
bm.to_mesh(roof_cone.data)
bm.free()
all_objs.append(roof_cone)

# 主塔瓦片（bmesh 一次生成，12 圈，总约 400 片）
print("[主塔] 铺设屋顶瓦片...")
main_tiles_obj = new_obj('main_tiles')
bm = bmesh.new()
for ring in range(12):
    r = 2.6 - ring * 0.2
    z_base = 17.0 + ring * 0.38
    num_tiles = max(24, int(48 - ring * 2))
    for i in range(num_tiles):
        angle_tile = math.pi * 2 * i / num_tiles
        tx, ty = r * math.cos(angle_tile), r * math.sin(angle_tile)
        # 每片 0.22 × 0.15 × 0.32
        cos_a, sin_a = math.cos(angle_tile), math.sin(angle_tile)
        for dx in [-0.11, 0.11]:
            for dy in [-0.075, 0.075]:
                for dz in [0, 0.32]:
                    bm.verts.new((tx + dx * cos_a, ty + dx * sin_a, z_base + dz))
bm.to_mesh(main_tiles_obj.data)
bm.free()
main_tiles_obj.data.materials.append(M_RED_ROOF)
all_objs.append(main_tiles_obj)

# 金球 + 旗杆
finial = sphere('main_finial', radius=0.42, loc=(0, 0, 24.2),
               material=M_BRASS, segs=32, rings=24)
all_objs.append(finial)
pole = cyl('flag_pole', radius=0.09, height=2.5, loc=(0, 0, 25.7),
          verts=16, material=M_BRASS, bevel=0)
all_objs.append(pole)
flag = panel('flag', [(0, 0), (1.2, 0.6), (0, 1.2)], thickness=0.05,
            loc=(0.15, 0, 26.5), material=M_PINK_WALL, bevel=0.01)
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

    # 锥形屋顶（深红色，清晰锥形）
    roof = cyl(f'corner_roof_{name}', radius=2.5, height=3.8, loc=(tx, ty, 12.0),
              verts=56, material=M_RED_ROOF, bevel=0.022)
    select_only([roof])
    apply_all_modifiers(roof)
    bm = bmesh.new()
    bm.from_mesh(roof.data)
    for v in bm.verts:
        local_z = v.co.z - 12.0
        if local_z > 0:
            ratio = 1.0 - (local_z / 3.8) * 0.96
            v.co.x *= ratio
            v.co.y *= ratio
    bm.to_mesh(roof.data)
    bm.free()
    all_objs.append(roof)

    # 瓦片（bmesh 一次生成，5 圈 × 20 = 100 片/塔）
    corner_tiles = new_obj(f'corner_tiles_{name}')
    bm = bmesh.new()
    for ring in range(5):
        r = 2.3 - ring * 0.42
        z_base = 10.5 + ring * 0.65
        for i in range(20):
            angle_tile = math.pi * 2 * i / 20
            tile_x = tx + r * math.cos(angle_tile)
            tile_y = ty + r * math.sin(angle_tile)
            cos_a, sin_a = math.cos(angle_tile), math.sin(angle_tile)
            for dx in [-0.125, 0.125]:
                for dy in [-0.08, 0.08]:
                    for dz in [0, 0.35]:
                        bm.verts.new((tile_x + dx * cos_a, tile_y + dx * sin_a, z_base + dz))
    bm.to_mesh(corner_tiles.data)
    bm.free()
    corner_tiles.data.materials.append(M_RED_ROOF)
    all_objs.append(corner_tiles)

    # 金球顶饰
    finial = sphere(f'corner_finial_{name}', radius=0.35, loc=(tx, ty, 16.0),
                   material=M_BRASS, segs=32, rings=24)
    all_objs.append(finial)

print("[城墙] 开始构建...")
# ========== 城墙（连接各塔，带垛口、射孔）==========
# 前墙左段
wall_FL = box('wall_FL', (2.2, 4, 6.5), loc=(-9.5, -12, 3.25),
             material=M_PINK_WALL, bevel=0.035)
all_objs.append(wall_FL)

wall_FR = box('wall_FR', (2.2, 4, 6.5), loc=(9.5, -12, 3.25),
             material=M_PINK_WALL, bevel=0.035)
all_objs.append(wall_FR)

# 左墙
wall_L = box('wall_L', (4, 18, 6.8), loc=(-11, 0, 3.4),
            material=M_PINK_WALL, bevel=0.035)
all_objs.append(wall_L)

# 右墙
wall_R = box('wall_R', (4, 18, 6.8), loc=(11, 0, 3.4),
            material=M_PINK_WALL, bevel=0.035)
all_objs.append(wall_R)

# 后墙
wall_B = box('wall_B', (20, 4, 6.8), loc=(0, 11, 3.4),
            material=M_PINK_WALL, bevel=0.035)
all_objs.append(wall_B)

# 所有城墙垛口（bmesh 一次生成）
wall_btl_obj = new_obj('wall_battlements')
bm = bmesh.new()
# 前墙左段 4 个
for i in range(4):
    x = -9.5 - 0.8 + i * 0.55
    for dx in [-0.35, 0.35]:
        for dy in [-1.75, 1.75]:
            for dz in [6.0, 6.8]:
                bm.verts.new((x + dx, -12 + dy, dz))
# 前墙右段 4 个
for i in range(4):
    x = 9.5 - 0.8 + i * 0.55
    for dx in [-0.35, 0.35]:
        for dy in [-1.75, 1.75]:
            for dz in [6.0, 6.8]:
                bm.verts.new((x + dx, -12 + dy, dz))
# 左墙 9 个
for i in range(9):
    y = -8.5 + i * 2.1
    for dx in [-1.75, 1.75]:
        for dy in [-0.9, 0.9]:
            for dz in [6.4, 7.2]:
                bm.verts.new((-11 + dx, y + dy, dz))
# 右墙 9 个
for i in range(9):
    y = -8.5 + i * 2.1
    for dx in [-1.75, 1.75]:
        for dy in [-0.9, 0.9]:
            for dz in [6.4, 7.2]:
                bm.verts.new((11 + dx, y + dy, dz))
# 后墙 10 个
for i in range(10):
    x = -9.5 + i * 2.1
    for dx in [-0.9, 0.9]:
        for dy in [-1.75, 1.75]:
            for dz in [6.4, 7.2]:
                bm.verts.new((x + dx, 11 + dy, dz))
bm.to_mesh(wall_btl_obj.data)
bm.free()
wall_btl_obj.data.materials.append(M_CREAM_STONE)
all_objs.append(wall_btl_obj)

print("[院子] 开始构建设施...")
# ========== 院子设施（对照 02-鸟瞰庭院.jpg，放大可见性）==========
# 中央喷泉（三层叠水，放大）
fountain_base = cyl('fountain_base', radius=2.2, height=1.1, loc=(0, -5, 0.55),
                   verts=48, material=M_CREAM_STONE, bevel=0.025)
all_objs.append(fountain_base)
fountain_pool1 = cyl('fountain_pool1', radius=2.0, height=0.55, loc=(0, -5, 1.4),
                    verts=48, material=M_WATER, bevel=0.018)
all_objs.append(fountain_pool1)
fountain_pillar = cyl('fountain_pillar', radius=0.42, height=2.5, loc=(0, -5, 2.95),
                     verts=32, material=M_CREAM_STONE, bevel=0.015)
all_objs.append(fountain_pillar)
fountain_bowl2 = cyl('fountain_bowl2', radius=1.2, height=0.65, loc=(0, -5, 4.5),
                    verts=32, material=M_CREAM_STONE, bevel=0.02)
all_objs.append(fountain_bowl2)
fountain_water2 = cyl('fountain_water2', radius=1.05, height=0.25, loc=(0, -5, 4.75),
                     verts=32, material=M_WATER, bevel=0.012)
all_objs.append(fountain_water2)

# 左侧豆形池塘（放大 + 池岸石，bmesh 一次生成）
pool = cyl('pool', radius=5.0, height=1.8, loc=(-7, 3, 0.9),
          verts=48, material=M_WATER, bevel=0.035)
all_objs.append(pool)

# 池岸石（复用现成岩石模型，环绕池塘）
rock_models = ['rock_smallA.glb', 'rock_smallB.glb', 'rock_smallC.glb', 'rock_smallD.glb']
for i in range(18):
    angle = math.pi * 2 * i / 18
    r = 5.3
    px = -7 + r * math.cos(angle)
    py = 3 + r * math.sin(angle)
    rock_model = rock_models[i % 4]
    rocks = import_glb(f'D:/hermes/home/assets-src/nature/Models/GLTF format/{rock_model}',
                      name_prefix=f'pool_rock_{i}', scale=0.6,
                      loc=(px, py, 1.6), rot=(0, 0, angle),
                      recolor=M_CREAM_STONE)
    all_objs.extend(rocks)

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

# 木桥（复用现成模型，横跨池塘）
bridge_parts = import_glb('D:/hermes/home/assets-src/nature/Models/GLTF format/bridge_wood.glb',
                          name_prefix='bridge', scale=2.8, loc=(-7, 3, 2.0), rot=(0, 0, math.pi/2),
                          recolor=M_WOOD_DARK)
all_objs.extend(bridge_parts)

# 秋千架（池后，放大增强可见性）
swing_L = cyl('swing_L', radius=0.14, height=3.8, loc=(-9.5, 8, 1.9),
             verts=12, material=M_WOOD_DARK, bevel=0)
all_objs.append(swing_L)
swing_R = cyl('swing_R', radius=0.14, height=3.8, loc=(-4.5, 8, 1.9),
             verts=12, material=M_WOOD_DARK, bevel=0)
all_objs.append(swing_R)
swing_bar = cyl('swing_bar', radius=0.12, height=5.2, loc=(-7, 8, 3.8),
               rot=(0, math.pi/2, 0), verts=12, material=M_WOOD_DARK, bevel=0)
all_objs.append(swing_bar)

# 双秋千座椅（放大）
for i, sx in enumerate([-8.2, -5.8]):
    seat = box(f'swing_seat_{i}', (1.0, 0.65, 0.2), loc=(sx, 8, 1.8),
              material=M_WOOD_DARK, bevel=0.012)
    all_objs.append(seat)
    for ry in [-0.25, 0.25]:
        rope = cyl(f'swing_rope_{i}_{ry}', radius=0.025, height=1.9,
                  loc=(sx, 8 + ry, 2.85), verts=8, material=M_METAL_IRON, bevel=0)
        all_objs.append(rope)

# 右侧游戏屋 + 彩虹滑梯（放大，增强可见性）
playhouse = cyl('playhouse', radius=1.8, height=4.5, loc=(8, 4.5, 2.25),
               verts=32, material=M_PINK_WALL, bevel=0.025)
all_objs.append(playhouse)
play_win = box('play_win', (0.75, 0.15, 1.1), loc=(8, 2.7, 3.0),
              material=M_WINDOW_GLOW, bevel=0.01)
all_objs.append(play_win)

play_roof = cyl('play_roof', radius=2.1, height=2.4, loc=(8, 4.5, 5.7),
               verts=32, material=M_RED_ROOF, bevel=0.02)
select_only([play_roof])
apply_all_modifiers(play_roof)
bm = bmesh.new()
bm.from_mesh(play_roof.data)
for v in bm.verts:
    local_z = v.co.z - 5.7
    if local_z > 0:
        ratio = 1.0 - (local_z / 2.4) * 0.95
        v.co.x *= ratio
        v.co.y *= ratio
bm.to_mesh(play_roof.data)
bm.free()
all_objs.append(play_roof)

play_finial = sphere('play_finial', radius=0.25, loc=(8, 4.5, 7.8),
                    material=M_BRASS, segs=24, rings=16)
all_objs.append(play_finial)

# 彩虹滑梯（七色，逐条台阶，放大）
slide_mats = [M_SLIDE_R, M_SLIDE_O, M_SLIDE_Y, M_SLIDE_G, M_SLIDE_C, M_SLIDE_B, M_SLIDE_P]
for step in range(14):
    mat_idx = step % 7
    slide_step = box(f'slide_step_{step}', (2.2, 0.45, 0.24),
                    loc=(6.5 + step * 0.32, 2.8 + step * 0.25, 3.8 - step * 0.26),
                    rot=(0, math.radians(-38), 0), material=slide_mats[mat_idx], bevel=0.012)
    all_objs.append(slide_step)

# 滑梯扶手（两侧）
for side, sy in [('L', 1.6), ('R', 4.0)]:
    rail = cyl(f'slide_rail_{side}', radius=0.08, height=5.5,
              loc=(7.0, sy, 3.5), rot=(0, math.radians(-38), 0),
              verts=10, material=M_WOOD_DARK, bevel=0)
    all_objs.append(rail)

# 门前花盆（两侧，复用现成花朵模型）
for fx in [-3, 3]:
    pot = cyl(f'gate_pot_{fx}', radius=0.45, height=0.65, loc=(fx, -8.5, 0.325),
             verts=20, material=M_CREAM_STONE, bevel=0.018)
    all_objs.append(pot)
    # 粉色花朵
    for i in range(4):
        flowers_pink = import_glb('D:/hermes/home/assets-src/nature/Models/GLTF format/flower_purpleA.glb',
                                  name_prefix=f'gate_flower_p_{fx}_{i}', scale=0.35,
                                  loc=(fx + (i - 1.5) * 0.18, -8.5, 0.75 + i * 0.06),
                                  recolor=M_FLOWER_PINK)
        all_objs.extend(flowers_pink)
    # 白色花朵
    for i in range(4):
        flowers_white = import_glb('D:/hermes/home/assets-src/nature/Models/GLTF format/flower_yellowA.glb',
                                   name_prefix=f'gate_flower_w_{fx}_{i}', scale=0.32,
                                   loc=(fx - (i - 1.5) * 0.16, -8.5, 0.8 + i * 0.05),
                                   recolor=M_FLOWER_WHITE)
        all_objs.extend(flowers_white)

# 花坛（四角，复用现成花朵模型）
for fx, fy in [(-5, -3), (5, -3), (-5, -7), (5, -7)]:
    bed = box(f'flowerbed_{fx}_{fy}', (1.5, 1.5, 0.4), loc=(fx, fy, 0.2),
             material=M_CREAM_STONE, bevel=0.015)
    all_objs.append(bed)
    # 红色/粉色花朵
    for i in range(6):
        px = fx + (i % 3 - 1) * 0.35
        py = fy + (i // 3 - 0.5) * 0.35
        flowers_red = import_glb('D:/hermes/home/assets-src/nature/Models/GLTF format/flower_redA.glb',
                                 name_prefix=f'bed_flower_r_{fx}_{fy}_{i}', scale=0.28,
                                 loc=(px, py, 0.5 + i * 0.02), recolor=M_FLOWER_PINK)
        all_objs.extend(flowers_red)
    # 黄色花朵
    for i in range(6):
        px = fx + (i % 3 - 1) * 0.3
        py = fy - (i // 3 - 0.5) * 0.3
        flowers_yellow = import_glb('D:/hermes/home/assets-src/nature/Models/GLTF format/flower_yellowB.glb',
                                    name_prefix=f'bed_flower_y_{fx}_{fy}_{i}', scale=0.25,
                                    loc=(px, py, 0.55 + i * 0.03), recolor=M_FLOWER_WHITE)
        all_objs.extend(flowers_yellow)

# 庭院装饰灌木（四角 + 中央）
bush_locs = [(-9, 7, 0), (9, 7, 0), (-9, -1, 0), (9, -1, 0), (0, 3, 0)]
for idx, (bx, by, bz) in enumerate(bush_locs):
    bush = import_glb('D:/hermes/home/assets-src/nature/Models/GLTF format/plant_bushLarge.glb',
                     name_prefix=f'yard_bush_{idx}', scale=1.2,
                     loc=(bx, by, bz), recolor=M_GREEN_LEAF)
    all_objs.extend(bush)

# ========== 合并导出 ==========
print(f"[完成] 创建了 {len(all_objs)} 个对象")

merged = join_by_material(all_objs, tol=0.001)
print(f"[合并] 按材质合并后剩余 {len(merged)} 个网格")

out_path = 'D:/hermes/home/out/models/castle.glb'
stats = export_glb(out_path, merged)
print(f"[导出] ✓ {out_path}")
print(f"  网格数: {stats['meshes']}, 三角面: {stats['tris']:,}, 材质数: {stats['materials']}, 文件大小: {stats['bytes'] / (1024*1024):.2f} MB")
