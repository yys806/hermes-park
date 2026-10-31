"""第 10 轮：分区可开关灯具。发光部件只用 LGT_<zone> 材质，骨架/挂件/底座全用普通材质。
查看器约定：材质名以 LGT_ 开头 = 一路开关。依赖 lib_building / lib_r9。"""
import bpy, math
from mathutils import Vector, Matrix
from lib_building import box, cyl, sphere, srgb_to_linear
from lib_r9 import oct_prism

ZONES = ('gate', 'courtyard', 'backyard', 'farm', 'wall')
# 关灯底色（哑光实体） / 发光色（暖色温）
LOOK = dict(red=('#c2412b', (1.0, 0.46, 0.22)), paper=('#e6d6b2', (1.0, 0.74, 0.44)),
            amber=('#d9a65a', (1.0, 0.66, 0.32)))
ZONE_LOOK = dict(gate='red', courtyard='red', backyard='red', farm='amber', wall='paper')
STRENGTH = 3.0


def lgt(zone):
    """取/建 LGT_<zone>：Principled 底色为关灯实体色，Emission 暖光（开灯）。"""
    nm = 'LGT_' + zone
    m = bpy.data.materials.get(nm)
    if m is None:
        m = bpy.data.materials.new(nm); m.use_nodes = True
    base, emi = LOOK[ZONE_LOOK[zone]]
    b = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    rgb = [srgb_to_linear(int(base[i:i + 2], 16) / 255) for i in (1, 3, 5)]
    b.inputs['Base Color'].default_value = (*rgb, 1)
    b.inputs['Roughness'].default_value = 0.75
    b.inputs['Emission Color'].default_value = (*emi, 1)
    b.inputs['Emission Strength'].default_value = STRENGTH
    m.diffuse_color = (*rgb, 1)
    return m


def M_():
    g = bpy.data.materials.get
    return dict(iron=g('Iron_Dark'), gold=g('Brass_Gold'), wood=g('Wood_Pillar'), win=g('Wood_Window'),
                tassel=g('Couplet_Red'), stone=g('Stone_Base'), tile=g('Roof_BlueTile'), ridge=g('Roof_Ridge'))


def _point(nm, zone, loc, energy, color):
    """渲染用点光源（只导 mesh，不进 GLB），按区域放进 R10_Lights_<zone>。"""
    cn = 'R10_Lights_' + zone
    c = bpy.data.collections.get(cn)
    if c is None:
        c = bpy.data.collections.new(cn); bpy.context.scene.collection.children.link(c)
    d = bpy.data.lights.new(nm, 'POINT'); d.energy, d.color, d.shadow_soft_size = energy, color, 0.15
    o = bpy.data.objects.new(nm, d); o.location = loc; c.objects.link(o)
    return o


def lantern(nm, zone, x, y, z_hang, r=0.3, cord=0.25, light=25):
    """圆灯笼：挂钩 + 吊绳 + 金色上下盖 + 灯皮(LGT) + 八道竹骨 + 腰箍 + 流苏。z_hang 为吊点高度。"""
    M, G = M_(), lgt(zone)
    hz = 0.8 * r                       # 灯皮半高
    zc = z_hang - cord - 0.06 - hz      # 灯皮中心
    out = [box(nm + '_hook', (0.05, 0.05, 0.06), (x, y, z_hang - 0.03), material=M['iron'], bevel=0),
           cyl(nm + '_cord', 0.012, cord, (x, y, z_hang - 0.06 - cord / 2), material=M['iron'], verts=6, bevel=0)]
    body = sphere(nm + '_shade', r, (x, y, zc), G, 16, 10); body.scale = (1, 1, 0.8); out.append(body)
    for s, z in (('T', zc + hz - 0.01), ('B', zc - hz + 0.01)):
        out.append(cyl(f'{nm}_cap{s}', r * 0.42, 0.07, (x, y, z), material=M['gold'], verts=12, bevel=0.01))
    for k in range(4):                 # 竹骨：4 个竖向椭圆环 = 8 道经线
        bpy.ops.mesh.primitive_torus_add(major_radius=r * 1.01, minor_radius=0.011, major_segments=20, minor_segments=4,
                                         location=(0, 0, 0))
        t = bpy.context.active_object; t.name = t.data.name = f'{nm}_rib{k}'
        t.data.transform(Matrix.Diagonal((1, 1, 0.8, 1)) @ Matrix.Rotation(k * math.pi / 4, 4, 'Z') @ Matrix.Rotation(math.pi / 2, 4, 'X'))
        t.location = (x, y, zc)
        t.data.materials.append(M['win'])
        out.append(t)
    out.append(cyl(nm + '_waist', r * 1.012, 0.025, (x, y, zc), material=M['win'], verts=20, bevel=0))
    zb = zc - hz - 0.035
    out.append(cyl(nm + '_knot', 0.035, 0.08, (x, y, zb - 0.04), material=M['gold'], verts=8, bevel=0))
    tl = r * 1.1
    bpy.ops.mesh.primitive_cone_add(vertices=8, radius1=r * 0.22, radius2=0.03, depth=tl, location=(x, y, zb - 0.08 - tl / 2))
    ts = bpy.context.active_object; ts.name = ts.data.name = nm + '_tassel'; ts.data.materials.append(M['tassel'])
    out.append(ts)
    _point(nm + '_L', zone, (x, y, zc), light, LOOK[ZONE_LOOK[zone]][1])
    return out


def _cone(nm, r1, r2, h, loc, m, n=8, rz=0.0):
    bpy.ops.mesh.primitive_cone_add(vertices=n, radius1=r1, radius2=r2, depth=h, location=loc, rotation=(0, 0, rz))
    o = bpy.context.active_object; o.name = o.data.name = nm; o.data.materials.append(m)
    return o


def wall_lamp(nm, zone, x, y, z, nx, ny, reach=0.42, light=18):
    """宫灯式壁灯：铁背板 + 挑臂 + 斜撑 + 吊钩，下挂六角纸灯（木框上下沿、小顶盖、短流苏）。
    (x,y) 为墙面上的点，(nx,ny) 为墙面外法线，z 为挑臂高度。"""
    M, G = M_(), lgt(zone)
    rz = math.atan2(ny, nx)
    p = lambda d: (x + nx * d, y + ny * d)
    out = [box(nm + '_plate', (0.04, 0.14, 0.34), (*p(0.02), z - 0.08), (0, 0, rz), M['iron'], bevel=0.01),
           box(nm + '_arm', (reach + 0.04, 0.035, 0.035), (*p(reach / 2 + 0.02), z), (0, 0, rz), M['iron'], bevel=0)]
    br = math.hypot(reach * 0.6, 0.22)
    out.append(box(nm + '_brace', (br, 0.025, 0.025), (*p(reach * 0.32), z - 0.11), (0, math.atan2(0.22, reach * 0.6), rz), M['iron'], bevel=0))
    hx, hy = p(reach)
    out.append(cyl(nm + '_cord', 0.01, 0.1, (hx, hy, z - 0.07), material=M['iron'], verts=6, bevel=0))
    zt = z - 0.12
    out.append(_cone(nm + '_roof', 0.2, 0.03, 0.11, (hx, hy, zt - 0.055), M['ridge'], 6))
    out.append(oct_prism(nm + '_rimT', hx, hy, 0.16, zt - 0.14, 0.03, M['win'], 0.005, n=6))
    out.append(oct_prism(nm + '_shade', hx, hy, 0.145, zt - 0.44, 0.3, G, 0.0, n=6))
    out.append(oct_prism(nm + '_rimB', hx, hy, 0.16, zt - 0.47, 0.03, M['win'], 0.005, n=6))
    out.append(_cone(nm + '_tassel', 0.04, 0.015, 0.16, (hx, hy, zt - 0.55), M['tassel'], 6))
    _point(nm + '_L', zone, (hx, hy, zt - 0.3), light, LOOK[ZONE_LOOK[zone]][1])
    return out


def post_lamp(nm, zone, x, y, z0, h=1.0, light=14):
    """矮灯/庭院灯：石基座 + 木灯柱 + 托板 + 方纸灯罩(LGT，四角木条) + 青瓦攒尖小顶 + 宝珠。"""
    M, G = M_(), lgt(zone)
    out = [box(nm + '_base', (0.34, 0.34, 0.16), (x, y, z0 + 0.08), material=M['stone'], bevel=0.03),
           cyl(nm + '_post', 0.05, h, (x, y, z0 + 0.16 + h / 2), material=M['wood'], verts=8, bevel=0)]
    zt = z0 + 0.16 + h
    out.append(box(nm + '_tray', (0.3, 0.3, 0.04), (x, y, zt + 0.02), material=M['wood'], bevel=0.01))
    out.append(box(nm + '_shade', (0.21, 0.21, 0.26), (x, y, zt + 0.17), material=G, bevel=0.01))
    for i, (sx, sy) in enumerate(((1, 1), (1, -1), (-1, 1), (-1, -1))):
        out.append(box(f'{nm}_stick{i}', (0.03, 0.03, 0.28), (x + sx * 0.105, y + sy * 0.105, zt + 0.17), material=M['win'], bevel=0))
    out.append(_cone(nm + '_roof', 0.25, 0.02, 0.15, (x, y, zt + 0.375), M['tile'], 4, math.pi / 4))
    out.append(sphere(nm + '_finial', 0.035, (x, y, zt + 0.47), M['ridge'], 8, 6))
    _point(nm + '_L', zone, (x, y, zt + 0.17), light, LOOK[ZONE_LOOK[zone]][1])
    return out


def bulb_lamp(nm, zone, x, y, z_hang, drop=0.35, light=12):
    """农家吊灯：铁钩 + 电线 + 灯座 + 铁皮伞罩（普通材质）+ 外露灯泡(LGT)。"""
    M, G = M_(), lgt(zone)
    out = [box(nm + '_hook', (0.04, 0.04, 0.05), (x, y, z_hang - 0.025), material=M['iron'], bevel=0),
           cyl(nm + '_wire', 0.008, drop, (x, y, z_hang - 0.05 - drop / 2), material=M['iron'], verts=6, bevel=0)]
    zs = z_hang - 0.05 - drop
    out.append(cyl(nm + '_socket', 0.025, 0.06, (x, y, zs - 0.03), material=M['iron'], verts=8, bevel=0))
    out.append(_cone(nm + '_shadeTin', 0.17, 0.035, 0.09, (x, y, zs - 0.075), M['iron'], 12))
    out.append(sphere(nm + '_bulb', 0.055, (x, y, zs - 0.13), G, 12, 8))
    _point(nm + '_L', zone, (x, y, zs - 0.14), light, LOOK[ZONE_LOOK[zone]][1])
    return out
