"""家人小屋（四合院）专用构件：青瓦双坡顶、硬山山墙、材质表。依赖 lib_building。"""
import math
from mathutils import Vector
from lib_building import box, cyl, panel, mat, array_offset

def mats():
    """项目统一命名的材质表。"""
    return dict(
        brick=mat('Wall_RedBrick', '#b4553b', 0.9),
        stone=mat('Stone_Base', '#bdb7aa', 0.85),
        pave=mat('Stone_Paving', '#a8a49b', 0.9),
        tile=mat('Roof_BlueTile', '#55606b', 0.7),
        ridge=mat('Roof_Ridge', '#3b424b', 0.7),
        door=mat('Wood_Door', '#5a3520', 0.6),
        wood=mat('Wood_Pillar', '#7b4a2a', 0.6),
        win=mat('Wood_Window', '#4a2c18', 0.6),
        lantern=mat('Lantern_Red', '#d8381f', 0.5),
        couplet=mat('Couplet_Red', '#c21d16', 0.6),
        plaque=mat('Plaque_Dark', '#2b1d13', 0.5),
        gold=mat('Brass_Gold', '#c08a2a', 0.35, 0.8),
        iron=mat('Iron_Dark', '#1d1d20', 0.5, 0.6),
    )

def _place(objs, cx, cy, axis):
    """局部构件（屋脊沿 X、中心在原点）→ 平移到 (cx,cy)；axis='Y' 时先绕 Z 转 90°。"""
    for o in objs:
        if axis == 'Y':
            x, y, z = o.location
            o.location = Vector((-y, x, z))
            o.rotation_euler.z += math.pi / 2
        o.location.x += cx
        o.location.y += cy
    return objs

def gable_roof(name, cx, cy, z_eave, length, depth, rise, M, axis='X',
               over=0.5, eave_over=0.4, t=0.14, rib_step=0.32):
    """双坡顶：两块坡面 + 瓦垄阵列 + 屋脊 + 脊端。length 沿屋脊，depth 为墙体进深，
    z_eave 为墙顶（坡面下皮在墙外皮处正好落在墙顶）。"""
    a = math.atan2(rise, depth / 2)
    L = (depth / 2 + over) / math.cos(a)   # 坡面斜长
    zr = z_eave + rise
    Lx = length + 2 * eave_over
    nrm = lambda s: Vector((0, s * math.sin(a), math.cos(a)))   # 坡面 s 侧朝上法线
    out = []
    for s in (1, -1):
        c = Vector((0, s * (L / 2) * math.cos(a), zr - (L / 2) * math.sin(a))) + nrm(s) * (t / 2)
        k = 'AB'[s < 0]
        out.append(box(f'{name}_slope{k}', (Lx, L, t), c, (-s * a, 0, 0), M['tile'], bevel=0.02))
        n = max(2, int((Lx - 0.2) / rib_step))
        rc = c + nrm(s) * (t / 2 + 0.01) + Vector((-(n - 1) * rib_step / 2, 0, 0))
        r = cyl(f'{name}_rib{k}', 0.065, L * 0.98, rc, (-math.pi / 2 - s * a, 0, 0), M['ridge'], verts=6, bevel=0)
        array_offset(r, n, (rib_step, 0, 0))
        r.modifiers['Array'].relative_offset_displace = (0, 0, 0)
        out.append(r)
        out.append(box(f'{name}_eave{k}', (Lx, 0.12, 0.12),   # 檐口封边（勾头滴水简化）
                       c + Vector((0, s * (L / 2) * math.cos(a), -(L / 2) * math.sin(a))), material=M['ridge'], bevel=0.02))
    out.append(box(f'{name}_ridge', (Lx + 0.1, 0.34, 0.32), (0, 0, zr + t + 0.12), material=M['ridge'], bevel=0.04))
    for s in (1, -1):
        out.append(box(f'{name}_ridgeEnd{"AB"[s < 0]}', (0.34, 0.4, 0.55), (s * (Lx / 2 - 0.12), 0, zr + t + 0.4),
                       material=M['ridge'], bevel=0.06))
    return _place(out, cx, cy, axis)

def lantern(nm, x, y, z_top, M, wall_y, drop=0.25):
    """红灯笼：挂点 (x,y,z_top)，铁吊杆从墙面 wall_y 伸出（沿 Y），下接吊绳/金帽/灯体/金底/穗。"""
    from lib_building import sphere
    box(nm + '_hook', (0.06, abs(y - wall_y) + 0.02, 0.06), (x, (y + wall_y) / 2, z_top), material=M['iron'], bevel=0)
    cyl(nm + '_cord', 0.015, drop, (x, y, z_top - drop / 2), material=M['iron'], verts=6, bevel=0)
    zc = z_top - drop - 0.33
    cyl(nm + '_capT', 0.14, 0.08, (x, y, zc + 0.31), material=M['gold'], verts=12, bevel=0.01)
    s = sphere(nm, 0.34, (x, y, zc), M['lantern'], segs=16, rings=10)
    s.scale.z = 0.8
    cyl(nm + '_capB', 0.14, 0.08, (x, y, zc - 0.31), material=M['gold'], verts=12, bevel=0.01)
    cyl(nm + '_tassel', 0.04, 0.4, (x, y, zc - 0.55), material=M['couplet'], verts=8, bevel=0)
    return s

def lattice_window(nm, cx, y, cz, w, h, M, n=4, axis='X', bar=0.06, depth=0.05):
    """木格窗：外框 + n×n 方格棂条，立在 XZ 平面（axis='Y' 时立在 YZ 平面）。"""
    import bpy
    parts = [(w, bar * 1.6, 0, h / 2 - bar * 0.8), (w, bar * 1.6, 0, -h / 2 + bar * 0.8),
             (bar * 1.6, h, w / 2 - bar * 0.8, 0), (bar * 1.6, h, -w / 2 + bar * 0.8, 0)]
    parts += [(bar, h, -w / 2 + w * i / n, 0) for i in range(1, n)]
    parts += [(w, bar, 0, -h / 2 + h * i / n) for i in range(1, n)]
    out = []
    for k, (sw, sh, du, dz) in enumerate(parts):
        size = (sw, depth, sh) if axis == 'X' else (depth, sw, sh)
        loc = (cx + du, y, cz + dz) if axis == 'X' else (cx, y + du, cz + dz)
        out.append(box(f'{nm}_bar{k}', size, loc, material=M['win'], bevel=0.008))
    return out

def wing(s, M, F=0.5):
    """两层厢房（s=+1 东厢、-1 西厢）：台基、主体、端墙墀头、廊柱、二层廊台栏杆、屋顶山墙、门窗。"""
    from lib_building import window_recess
    tag = 'E' if s > 0 else 'W'
    nm = f'Wing{tag}'
    y0, y1, xi, xo, xp = 5.0, 16.6, 8.6, 11.75, 7.0     # 主体南北端 / 内外墙面 / 廊外沿
    zb, FH = F + 0.35, 2.6                               # 台基顶 / 层高
    zt = zb + 2 * FH
    cy, ly = (y0 + y1) / 2, y1 - y0
    X = lambda x: s * x
    box(nm + '_Podium', (xo - 6.8, ly + 0.4, 0.35), (X((xo + 6.8) / 2), cy, F + 0.175), material=M['stone'], bevel=0.03)
    body = box(nm + '_Body', (xo - xi, ly, 2 * FH), (X((xo + xi) / 2), cy, zb + FH), material=M['brick'], bevel=0.02)
    for k, yy in (('S', y0 + 0.2), ('N', y1 - 0.2)):     # 廊两端墀头墙
        box(f'{nm}_EndWall{k}', (xi - xp, 0.4, 2 * FH), (X((xi + xp) / 2), yy, zb + FH), material=M['brick'], bevel=0.02)
    cols = [5.65 + i * 2.6 for i in range(5)]
    for i, yy in enumerate(cols):
        cyl(f'{nm}_Col{i}', 0.13, 2 * FH - 0.2, (X(7.25), yy, zb + FH - 0.1), material=M['wood'], verts=12, bevel=0.01)
        cyl(f'{nm}_ColBase{i}', 0.2, 0.18, (X(7.25), yy, zb + 0.09), material=M['stone'], verts=12, bevel=0.02)
    box(nm + '_EaveBeam', (0.26, ly - 0.8, 0.22), (X(7.25), cy, zt - 0.11), material=M['wood'], bevel=0.02)
    box(nm + '_Fascia', (0.06, ly - 0.8, 0.35), (X(7.09), cy, zt - 0.42), material=M['win'], bevel=0.01)
    # 二层廊台：楼板 + 栏杆扶手 + 栏杆立条
    box(nm + '_Gallery', (xi - 7.12, ly - 0.8, 0.14), (X((xi + 7.12) / 2), cy, zb + FH - 0.07), material=M['wood'], bevel=0.01)
    box(nm + '_RailTop', (0.08, ly - 0.8, 0.08), (X(7.25), cy, zb + FH + 0.86), material=M['wood'], bevel=0.01)
    box(nm + '_RailBot', (0.08, ly - 0.8, 0.08), (X(7.25), cy, zb + FH + 0.1), material=M['wood'], bevel=0.01)
    b = box(nm + '_Baluster', (0.05, 0.05, 0.7), (X(7.25), y0 + 0.55, zb + FH + 0.48), material=M['win'], bevel=0)
    array_offset(b, int((ly - 1.1) / 0.3) + 1, (0, 0.3, 0))
    gable_roof(nm + '_Roof', X((xp + xo) / 2), cy, zt, ly, xo - xp, 1.0, M, 'Y', over=0.5, eave_over=0.35, t=0.14, rib_step=0.32)
    gable_wall(nm, X((xp + xo) / 2), cy, zt, ly, xo - xp, 1.0, M, 'Y', thick=0.4)
    # 门窗：三开间，底层中门两窗，二层三窗（墙体局部坐标，切割体绕 Z 转 90°）
    bays = [y0 + ly * (i + 0.5) / 3 for i in range(3)]
    hx = -s * (xo - xi) / 2
    for i, yy in enumerate(bays):
        if i == 1:
            window_recess(body, 1.3, 2.4, 0.5, (hx, yy - cy, -FH + 1.2), 1.5708)
            for j in (1, -1):
                box(f'{nm}_Door{j}', (0.06, 0.64, 2.38), (X(xi + 0.2), yy + j * 0.325, zb + 1.19), material=M['door'], bevel=0.01)
        else:
            window_recess(body, 1.4, 1.2, 0.4, (hx, yy - cy, -FH + 1.6), 1.5708)
            box(f'{nm}_WinBack{i}', (0.02, 1.4, 1.2), (X(xi + 0.18), yy, zb + 1.6), material=M['plaque'], bevel=0)
            lattice_window(f'{nm}_Win{i}', X(xi + 0.1), yy, zb + 1.6, 1.4, 1.2, M, n=4, axis='Y')
        window_recess(body, 1.4, 1.1, 0.4, (hx, yy - cy, 1.3), 1.5708)
        box(f'{nm}_WinBack2F{i}', (0.02, 1.4, 1.1), (X(xi + 0.18), yy, zb + FH + 1.3), material=M['plaque'], bevel=0)
        lattice_window(f'{nm}_Win2F{i}', X(xi + 0.1), yy, zb + FH + 1.3, 1.4, 1.1, M, n=4, axis='Y')
    return body

def gable_wall(name, cx, cy, z_eave, length, depth, rise, M, axis='X', thick=0.4):
    """硬山山墙：屋顶两端的三角砖墙，外皮与墙体外皮平齐。"""
    out = []
    for s in (1, -1):
        pts = [(-depth / 2, 0), (depth / 2, 0), (0, rise)]
        x = s * length / 2 - (thick if s > 0 else 0)   # 挤出方向 +X
        out.append(panel(f'{name}_gable{"AB"[s < 0]}', pts, thick, (x, 0, z_eave),
                         (math.pi / 2, 0, math.pi / 2), M['brick'], bevel=0))
    return _place(out, cx, cy, axis)
