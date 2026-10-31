"""学习科研地块专用小工具：L_ 前缀材质、蓬松树冠、双套树（有叶/枯枝）、季节默认隐藏。Blender 4.5"""
import bpy, bmesh, math, random
from mathutils import Vector, Matrix
import lib_building as lb

COLL = 'Learn'

def coll():
    sc = bpy.context.scene
    c = bpy.data.collections.get(COLL)
    if c is None:
        c = bpy.data.collections.new(COLL)
        sc.collection.children.link(c)
    lc = bpy.context.view_layer.layer_collection.children[COLL]
    bpy.context.view_layer.active_layer_collection = lc
    return c

def M(name, hexcol, rough=0.75, metal=0.0, emit=None, strength=3.0, alpha=1.0):
    """L_ 前缀材质；emit 给 hex 时加自发光。"""
    m = lb.mat('L_' + name, hexcol, rough, metal, alpha)
    if emit:
        b = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
        r, g, bl = (lb.srgb_to_linear(int(emit.lstrip('#')[i:i + 2], 16) / 255) for i in (0, 2, 4))
        b.inputs['Emission Color'].default_value = (r, g, bl, 1)
        b.inputs['Emission Strength'].default_value = strength
    return m

def seasonal_hide(o, hidden=True):
    """默认隐藏（冬季件）：视口/渲染关闭 + 自定义属性，导出到 glTF extras。"""
    o['default_visible'] = not hidden
    o.hide_render = hidden
    o.hide_set(hidden)
    return o

def blob(name, parts, material, subdiv=2, smooth=True, loc=(0, 0, 0)):
    """多个 icosphere 拼成一个蓬松对象。parts: [(x,y,z,r,(sx,sy,sz))]，坐标相对 loc。"""
    bm = bmesh.new()
    for p in parts:
        x, y, z, r = p[:4]
        sc = p[4] if len(p) > 4 else (1, 1, 1)
        mtx = Matrix.Translation((x, y, z)) @ Matrix.Diagonal((r * sc[0], r * sc[1], r * sc[2], 1))
        bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=1.0, matrix=mtx)
    o = lb.new_obj(name)
    bm.to_mesh(o.data); bm.free()
    o.data.polygons.foreach_set('use_smooth', [smooth] * len(o.data.polygons))
    o.data.materials.append(material)
    o.location = loc
    return o

def crown_parts(h, r, seed):
    """伞状树冠：中心大团 + 一圈小团 + 顶部团。"""
    rnd = random.Random(seed)
    ps = [(0, 0, 0, r * 0.78, (1, 1, 0.8))]
    n = 7
    for i in range(n):
        a = i / n * math.tau + rnd.uniform(-0.2, 0.2)
        ps.append((math.cos(a) * r * 0.62, math.sin(a) * r * 0.62, rnd.uniform(-0.15, 0.1) * r,
                   r * rnd.uniform(0.42, 0.52), (1, 1, 0.85)))
    for i in range(4):
        a = i / 4 * math.tau + 0.4
        ps.append((math.cos(a) * r * 0.3, math.sin(a) * r * 0.3, r * 0.42, r * rnd.uniform(0.4, 0.48)))
    return ps

def tree(nm, x, y, z0, h=3.0, r=1.0, seed=0, M_=None):
    """双套树：Trunk_ 常显，Foliage_ 树冠（换季变色），Bare_ 枯枝（默认隐藏）。"""
    trunk = lb.cyl('Trunk_' + nm, 0.13 * r + 0.05, h * 0.62, (x, y, z0 + h * 0.31), material=M_['trunk'],
                   verts=12, bevel=0.03)
    zc = z0 + h - r * 0.75
    fol = blob('Foliage_' + nm, crown_parts(h, r, seed), M_['leaf'], loc=(x, y, zc))
    # 枯枝：从树干顶向外斜伸的几根细枝 + 二级小杈
    rnd = random.Random(seed + 7)
    bm = bmesh.new()
    top = Vector((0, 0, h * 0.55))
    def limb(p0, d, L, rad):
        q = d.to_track_quat('Z', 'Y').to_matrix().to_4x4()
        mtx = Matrix.Translation(p0 + d * L / 2) @ q
        bmesh.ops.create_cone(bm, cap_ends=True, segments=6, radius1=rad, radius2=rad * 0.45, depth=L, matrix=mtx)
        return p0 + d * L
    for i in range(5):
        a = i / 5 * math.tau + rnd.uniform(-0.3, 0.3)
        d = Vector((math.cos(a), math.sin(a), rnd.uniform(1.0, 1.6))).normalized()
        tip = limb(top - Vector((0, 0, 0.1)), d, r * 0.85, 0.05)
        for s in (-0.6, 0.6):
            d2 = Vector((math.cos(a + s), math.sin(a + s), 1.4)).normalized()
            limb(tip - d * 0.15, d2, r * 0.4, 0.025)
    bare = lb.new_obj('Bare_' + nm)
    bm.to_mesh(bare.data); bm.free()
    bare.data.materials.append(M_['trunk'])
    bare.location = (x, y, z0)
    seasonal_hide(bare)
    return trunk, fol, bare

def bush(nm, x, y, z0, r=0.35, seed=0, M_=None):
    rnd = random.Random(seed)
    ps = [(0, 0, r * 0.7, r)]
    for i in range(3):
        a = i / 3 * math.tau + rnd.uniform(0, 1)
        ps.append((math.cos(a) * r * 0.8, math.sin(a) * r * 0.8, r * 0.5, r * rnd.uniform(0.6, 0.8)))
    return blob('Foliage_bush_' + nm, ps, M_['bush'], subdiv=2, loc=(x, y, z0))
