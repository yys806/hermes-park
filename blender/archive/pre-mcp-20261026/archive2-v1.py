"""Rainbow's Castle - 完整场景建模
基于 02-鸟瞰庭院.jpg 主参考图，还原粉色童话城堡全景。
Blender 4.5+ / Python 3.11
"""
import sys, os, math
sys.path.insert(0, os.path.dirname(__file__))
from lib_building import *

reset_scene()   # 必须先清场景再建材质：reset 会清空 bpy.data，材质引用会失效

# ========== 材质定义 ==========
M_PINK_WALL = mat('pink_wall', '#FFB8D1', roughness=0.7)      # 粉色墙面
M_CREAM_STONE = mat('cream_stone', '#F5E6D3', roughness=0.8)  # 米色石砌
M_RED_ROOF = mat('red_roof', '#A63446', roughness=0.6)        # 暗红屋顶
M_WOOD = mat('wood', '#8B6F47', roughness=0.9)                # 木质门板
M_METAL = mat('metal', '#4A4A4A', roughness=0.3, metallic=0.8) # 金属铁艺
M_GOLD = mat('gold', '#D4AF37', roughness=0.2, metallic=0.9)  # 金色装饰
M_WINDOW = mat('window', '#FFE4A0', roughness=0.1, alpha=0.6) # 金色窗户（半透明）
M_POOL = mat('pool', '#5DADE2', roughness=0.05)               # 蓝色泳池
M_GRASS = mat('grass', '#7CB342', roughness=0.9)              # 草地
M_GROUND = mat('ground', '#E8DCC8', roughness=0.85)           # 地砖
M_FLOWER_PINK = mat('flower_pink', '#F8BBD0', roughness=0.6)  # 粉花
M_FLOWER_WHITE = mat('flower_white', '#FFFFFF', roughness=0.5) # 白花
M_GREEN_LEAF = mat('green_leaf', '#66BB6A', roughness=0.7)    # 绿叶
M_SLIDE = mat('slide', '#E91E63', roughness=0.3)              # 滑梯（彩虹色，这里用粉红代表）

all_objs = []

# ========== 主建筑结构 ==========

# --- 1. 中央主塔（三层锥台 + 圆锥顶）---
# 第一层（最底层，最大）
main_base1 = box('main_tower_base1', (6, 6, 4), loc=(0, 0, 2), material=M_PINK_WALL, bevel=0.05)
all_objs.append(main_base1)

# 米色石砌边角（四角装饰柱）
for x, y in [(-3, -3), (3, -3), (-3, 3), (3, 3)]:
    corner = box(f'corner1_{x}_{y}', (0.6, 0.6, 4), loc=(x, y, 2), material=M_CREAM_STONE, bevel=0.02)
    all_objs.append(corner)

# 第二层
main_base2 = box('main_tower_base2', (5, 5, 3.5), loc=(0, 0, 5.75), material=M_PINK_WALL, bevel=0.05)
all_objs.append(main_base2)
for x, y in [(-2.5, -2.5), (2.5, -2.5), (-2.5, 2.5), (2.5, 2.5)]:
    corner = box(f'corner2_{x}_{y}', (0.5, 0.5, 3.5), loc=(x, y, 5.75), material=M_CREAM_STONE, bevel=0.02)
    all_objs.append(corner)

# 暗红屋顶平台（第二层顶部）
roof2 = box('roof2_platform', (5.5, 5.5, 0.3), loc=(0, 0, 7.7), material=M_RED_ROOF, bevel=0.03)
all_objs.append(roof2)

# 第三层（顶层圆柱塔身）
main_top = cyl('main_tower_top', radius=1.8, height=3, loc=(0, 0, 9.5), material=M_PINK_WALL, verts=16, bevel=0.03)
all_objs.append(main_top)

# 顶层四周拱窗（4个金色拱窗）
for i, angle in enumerate([0, 90, 180, 270]):
    rad = math.radians(angle)
    wx, wy = 1.6 * math.cos(rad), 1.6 * math.sin(rad)
    window = box(f'main_window_{i}', (0.6, 0.15, 1.2), loc=(wx, wy, 9.5),
                 rot=(0, 0, rad), material=M_WINDOW, bevel=0.01)
    all_objs.append(window)

# 圆锥屋顶（暗红色鳞片瓦）
cone_roof = cyl('main_cone_roof', radius=2.2, height=3, loc=(0, 0, 12.5),
                material=M_RED_ROOF, verts=16, bevel=0.02)
# 锥形顶：手动缩放顶部顶点（简化处理，用圆台模拟）
bpy.context.view_layer.update()
select_only([cone_roof])
apply_all_modifiers(cone_roof)
bm = bmesh.new()
bm.from_mesh(cone_roof.data)
for v in bm.verts:
    if v.co.z > 13.5:  # 顶部顶点
        v.co.x *= 0.1
        v.co.y *= 0.1
bm.to_mesh(cone_roof.data)
bm.free()
all_objs.append(cone_roof)

# 金色顶球 + 旗杆
top_sphere = sphere('top_finial', radius=0.25, loc=(0, 0, 14.2), material=M_GOLD, segs=12, rings=8)
all_objs.append(top_sphere)
flag_pole = cyl('flag_pole', radius=0.05, height=1.5, loc=(0, 0, 15.1), material=M_GOLD, verts=8, bevel=0)
all_objs.append(flag_pole)

# --- 2. 前方城门建筑（两侧圆塔 + 中央拱门）---
# 前方门楼主体（粉色墙面，连接两侧塔）
gate_building = box('gate_building', (10, 3, 5), loc=(0, -9, 2.5), material=M_PINK_WALL, bevel=0.05)
all_objs.append(gate_building)

# 中央拱门洞（布尔切割）
gate_arch = cyl('gate_arch_cutter', radius=1.8, height=3.5, loc=(0, -9, 2), rot=(math.pi/2, 0, 0),
                material=None, verts=20, bevel=0)
boolean_cut(gate_building, gate_arch)

# 拱门内侧石砌装饰（米色）
arch_frame = cyl('arch_frame', radius=2, height=0.3, loc=(0, -10.5, 2), rot=(math.pi/2, 0, 0),
                 material=M_CREAM_STONE, verts=20, bevel=0.02)
all_objs.append(arch_frame)

# 木质大门（两扇对开门，略微打开）
left_door = box('gate_door_left', (1.5, 0.2, 3.2), loc=(-0.8, -10.3, 1.8),
                rot=(0, 0, math.radians(15)), material=M_WOOD, bevel=0.02)
right_door = box('gate_door_right', (1.5, 0.2, 3.2), loc=(0.8, -10.3, 1.8),
                 rot=(0, 0, math.radians(-15)), material=M_WOOD, bevel=0.02)
all_objs.extend([left_door, right_door])

# 门上铁艺装饰（金属铰链）
for x in [-0.9, 0.9]:
    hinge = box(f'door_hinge_{x}', (0.15, 0.1, 1), loc=(x, -10.2, 2.5), material=M_METAL, bevel=0.005)
    all_objs.append(hinge)

# 门环（金色圆环）
for x in [-0.5, 0.5]:
    ring = cyl(f'door_ring_{x}', radius=0.15, height=0.05, loc=(x, -10.15, 2.2),
               rot=(math.pi/2, 0, 0), material=M_GOLD, verts=12, bevel=0.01)
    all_objs.append(ring)

# 门楼上方 "Rainbow's Castle" 标牌（米色石板）
sign_board = box('castle_sign', (4, 0.3, 0.8), loc=(0, -7.5, 5.2), material=M_CREAM_STONE, bevel=0.03)
all_objs.append(sign_board)

# 垛口城墙（门楼顶部）
for i in range(5):
    battlement = box(f'gate_battlement_{i}', (1.5, 2.5, 0.6),
                    loc=(-4 + i*2, -9, 5.2), material=M_CREAM_STONE, bevel=0.02)
    all_objs.append(battlement)

# 左侧圆塔
left_gate_tower = cyl('left_gate_tower', radius=1.2, height=6, loc=(-5.5, -9, 3),
                      material=M_PINK_WALL, verts=16, bevel=0.03)
all_objs.append(left_gate_tower)
# 塔顶锥形屋顶
left_tower_roof = cyl('left_gate_tower_roof', radius=1.5, height=2, loc=(-5.5, -9, 7),
                      material=M_RED_ROOF, verts=16, bevel=0.02)
# 锥化
select_only([left_tower_roof])
apply_all_modifiers(left_tower_roof)
bm = bmesh.new()
bm.from_mesh(left_tower_roof.data)
for v in bm.verts:
    if v.co.z > 7.8:
        v.co.x *= 0.05
        v.co.y *= 0.05
bm.to_mesh(left_tower_roof.data)
bm.free()
all_objs.append(left_tower_roof)
# 顶部金球
left_tower_finial = sphere('left_gate_finial', radius=0.2, loc=(-5.5, -9, 8.2), material=M_GOLD)
all_objs.append(left_tower_finial)

# 右侧圆塔（镜像）
right_gate_tower = dupe(left_gate_tower, loc=(5.5, -9, 3))
right_gate_tower.name = 'right_gate_tower'
all_objs.append(right_gate_tower)
right_tower_roof = dupe(left_tower_roof, loc=(5.5, -9, 7))
right_tower_roof.name = 'right_gate_tower_roof'
all_objs.append(right_tower_roof)
right_tower_finial = sphere('right_gate_finial', radius=0.2, loc=(5.5, -9, 8.2), material=M_GOLD)
all_objs.append(right_tower_finial)

# --- 3. 四角塔楼（前后各两座，圆柱 + 锥顶）---
tower_positions = [
    (-7, -6, 'front_left'),
    (7, -6, 'front_right'),
    (-7, 6, 'back_left'),
    (7, 6, 'back_right')
]

for tx, ty, name in tower_positions:
    # 圆柱塔身
    tower = cyl(f'corner_tower_{name}', radius=1.5, height=7, loc=(tx, ty, 3.5),
                material=M_PINK_WALL, verts=16, bevel=0.03)
    all_objs.append(tower)

    # 米色石砌底座
    tower_base = cyl(f'tower_base_{name}', radius=1.7, height=0.8, loc=(tx, ty, 0.4),
                     material=M_CREAM_STONE, verts=16, bevel=0.02)
    all_objs.append(tower_base)

    # 锥形屋顶
    tower_roof = cyl(f'tower_roof_{name}', radius=1.8, height=2.5, loc=(tx, ty, 8.25),
                     material=M_RED_ROOF, verts=16, bevel=0.02)
    select_only([tower_roof])
    apply_all_modifiers(tower_roof)
    bm = bmesh.new()
    bm.from_mesh(tower_roof.data)
    for v in bm.verts:
        if v.co.z > 9.5:
            v.co.x *= 0.05
            v.co.y *= 0.05
    bm.to_mesh(tower_roof.data)
    bm.free()
    all_objs.append(tower_roof)

    # 金球顶饰
    finial = sphere(f'tower_finial_{name}', radius=0.2, loc=(tx, ty, 10.6), material=M_GOLD)
    all_objs.append(finial)

    # 塔楼拱窗（正面一个）
    angle_to_center = math.atan2(-ty, -tx)
    wx = tx + 1.3 * math.cos(angle_to_center)
    wy = ty + 1.3 * math.sin(angle_to_center)
    tower_window = box(f'tower_window_{name}', (0.5, 0.15, 1), loc=(wx, wy, 4.5),
                       rot=(0, 0, angle_to_center), material=M_WINDOW, bevel=0.01)
    all_objs.append(tower_window)

# --- 4. 城墙连接（带垛口）---
# 前墙左段（连接左前塔和左门塔）
front_wall_left = box('front_wall_left', (1.5, 3, 4), loc=(-6.25, -7.5, 2), material=M_PINK_WALL, bevel=0.03)
all_objs.append(front_wall_left)
for i in range(2):
    btl = box(f'front_wall_left_btl_{i}', (0.6, 2.5, 0.5),
             loc=(-6.25 - 0.4 + i*0.8, -7.5, 4.3), material=M_CREAM_STONE, bevel=0.01)
    all_objs.append(btl)

# 前墙右段（镜像）
front_wall_right = box('front_wall_right', (1.5, 3, 4), loc=(6.25, -7.5, 2), material=M_PINK_WALL, bevel=0.03)
all_objs.append(front_wall_right)
for i in range(2):
    btr = box(f'front_wall_right_btl_{i}', (0.6, 2.5, 0.5),
             loc=(6.25 - 0.4 + i*0.8, -7.5, 4.3), material=M_CREAM_STONE, bevel=0.01)
    all_objs.append(btr)

# 后墙（连接后方两塔）
back_wall = box('back_wall', (14, 3, 4.5), loc=(0, 8, 2.25), material=M_PINK_WALL, bevel=0.03)
all_objs.append(back_wall)
for i in range(7):
    btl = box(f'back_wall_btl_{i}', (1.5, 2.5, 0.6),
             loc=(-9 + i*3, 8, 4.8), material=M_CREAM_STONE, bevel=0.01)
    all_objs.append(btl)

# 侧墙（左右连接前后塔）
left_wall = box('left_wall', (3, 12, 4), loc=(-8, 0, 2), material=M_PINK_WALL, bevel=0.03)
all_objs.append(left_wall)
right_wall = box('right_wall', (3, 12, 4), loc=(8, 0, 2), material=M_PINK_WALL, bevel=0.03)
all_objs.append(right_wall)

# ========== 庭院设施（鸟瞰图布局）==========

# --- 5. 地面（前方砖石 + 后方草地）---
courtyard_floor = box('courtyard_floor', (18, 20, 0.3), loc=(0, 0, 0.15), material=M_GROUND, bevel=0.02)
all_objs.append(courtyard_floor)

# 后方草地区域
grass_area = box('grass_area', (14, 10, 0.35), loc=(0, 3, 0.18), material=M_GRASS, bevel=0.02)
all_objs.append(grass_area)

# --- 6. 中央喷泉 ---
fountain_base = cyl('fountain_base', radius=1.2, height=0.6, loc=(0, -3, 0.6),
                   material=M_CREAM_STONE, verts=16, bevel=0.02)
all_objs.append(fountain_base)
fountain_pillar = cyl('fountain_pillar', radius=0.25, height=1.5, loc=(0, -3, 1.65),
                     material=M_CREAM_STONE, verts=12, bevel=0.01)
all_objs.append(fountain_pillar)
fountain_bowl = cyl('fountain_bowl', radius=0.8, height=0.4, loc=(0, -3, 2.6),
                   material=M_CREAM_STONE, verts=16, bevel=0.02)
all_objs.append(fountain_bowl)

# --- 7. 左侧泳池区（蓝色泳池 + 木桥 + 秋千）---
pool = box('pool', (6, 4, 1), loc=(-5, 2, 0.5), material=M_POOL, bevel=0.03)
all_objs.append(pool)

# 泳池边缘石砌
pool_edge = cyl('pool_edge', radius=3.5, height=0.3, loc=(-5, 2, 1.15),
               material=M_CREAM_STONE, verts=20, bevel=0.02, cap=False)
all_objs.append(pool_edge)

# 木桥（横跨泳池）
bridge = box('pool_bridge', (6.5, 0.8, 0.2), loc=(-5, 2, 1.3), material=M_WOOD, bevel=0.02)
all_objs.append(bridge)
for i in range(5):
    plank = box(f'bridge_plank_{i}', (0.15, 0.8, 0.15),
               loc=(-7 + i*1, 2, 1.35), material=M_WOOD, bevel=0.005)
    all_objs.append(plank)

# 秋千架（后方）
swing_frame_left = cyl('swing_frame_left', radius=0.08, height=2.5, loc=(-6.5, 5.5, 1.25),
                      material=M_WOOD, verts=8, bevel=0)
swing_frame_right = cyl('swing_frame_right', radius=0.08, height=2.5, loc=(-3.5, 5.5, 1.25),
                       material=M_WOOD, verts=8, bevel=0)
swing_bar = cyl('swing_bar', radius=0.06, height=3.2, loc=(-5, 5.5, 2.5),
               rot=(0, math.pi/2, 0), material=M_WOOD, verts=8, bevel=0)
all_objs.extend([swing_frame_left, swing_frame_right, swing_bar])

# 秋千座椅（两个）
for i, sx in enumerate([-5.8, -4.2]):
    seat = box(f'swing_seat_{i}', (0.6, 0.4, 0.1), loc=(sx, 5.5, 1.2), material=M_WOOD, bevel=0.01)
    all_objs.append(seat)

# --- 8. 右侧游乐区（彩虹滑梯 + 小塔屋）---
# 小塔屋（攀爬塔）
playhouse_tower = cyl('playhouse_tower', radius=1, height=3, loc=(6, 3, 1.5),
                     material=M_PINK_WALL, verts=12, bevel=0.02)
all_objs.append(playhouse_tower)
playhouse_roof = cyl('playhouse_roof', radius=1.2, height=1.5, loc=(6, 3, 3.75),
                    material=M_RED_ROOF, verts=12, bevel=0.02)
# 锥化屋顶
select_only([playhouse_roof])
apply_all_modifiers(playhouse_roof)
bm = bmesh.new()
bm.from_mesh(playhouse_roof.data)
for v in bm.verts:
    if v.co.z > 4.2:
        v.co.x *= 0.05
        v.co.y *= 0.05
bm.to_mesh(playhouse_roof.data)
bm.free()
all_objs.append(playhouse_roof)

# 彩虹滑梯（简化为一个倾斜色板）
slide = box('rainbow_slide', (1.2, 3, 0.3), loc=(5, 1.5, 2),
           rot=(0, math.radians(-30), 0), material=M_SLIDE, bevel=0.02)
all_objs.append(slide)

# 滑梯扶手（两侧）
for sy in [-0.5, 0.5]:
    rail = cyl(f'slide_rail_{sy}', radius=0.05, height=3.2, loc=(5, 1.5 + sy*0.6, 2),
              rot=(0, math.radians(-30), 0), material=M_WOOD, verts=8, bevel=0)
    all_objs.append(rail)

# --- 9. 装饰物（花盆、灯笼）---
# 门前两侧花盆
for fx in [-2, 2]:
    pot = cyl(f'flower_pot_front_{fx}', radius=0.3, height=0.5, loc=(fx, -5.5, 0.25),
             material=M_CREAM_STONE, verts=12, bevel=0.01)
    all_objs.append(pot)
    # 花丛（粉白球体簇）
    for i in range(3):
        flower = sphere(f'flower_{fx}_{i}', radius=0.15,
                       loc=(fx + (i-1)*0.2, -5.5, 0.6 + i*0.1),
                       material=M_FLOWER_PINK if i % 2 == 0 else M_FLOWER_WHITE)
        all_objs.append(flower)

# 窗台花盆（主塔二层窗下）
for i, angle in enumerate([45, 135, 225, 315]):
    rad = math.radians(angle)
    px, py = 2.3 * math.cos(rad), 2.3 * math.sin(rad)
    pot = box(f'window_pot_{i}', (0.6, 0.3, 0.2), loc=(px, py, 5),
             material=M_CREAM_STONE, bevel=0.01)
    all_objs.append(pot)
    # 绿叶 + 粉花
    leaf = sphere(f'leaf_{i}', radius=0.2, loc=(px, py, 5.2), material=M_GREEN_LEAF, segs=8)
    all_objs.append(leaf)
    flower_cluster = sphere(f'flower_cluster_{i}', radius=0.12, loc=(px, py, 5.35), material=M_FLOWER_PINK)
    all_objs.append(flower_cluster)

# 门楼拱门上方吊灯
gate_lantern = box('gate_lantern', (0.25, 0.25, 0.4), loc=(0, -9, 3.5), material=M_METAL, bevel=0.01)
all_objs.append(gate_lantern)
lantern_chain = cyl('lantern_chain', radius=0.02, height=0.6, loc=(0, -9, 4.1),
                   material=M_METAL, verts=6, bevel=0)
all_objs.append(lantern_chain)

# ========== 合并导出 ==========
print(f"[build_castle] 创建了 {len(all_objs)} 个对象")

# 按材质合并（提升性能）
merged = join_by_material(all_objs, tol=0.001)
print(f"[build_castle] 按材质合并后剩余 {len(merged)} 个网格")

# 导出 GLB
out_path = 'D:/hermes/home/out/models/castle.glb'
export_glb(out_path, merged)
print(f"[build_castle] ✓ 导出完成: {out_path}")
