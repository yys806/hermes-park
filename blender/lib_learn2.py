"""学习科研地块 v2：独立场景 Learn2、L2_ 黏土材质（SSS+噪声凹凸+无高光）、大圆角体块、传送带/接口部件。Blender 4.5"""
import bpy, bmesh, math, random
from mathutils import Vector, Matrix
import lib_building as lb

SCENE = 'Learn2'
COLL = 'Learn2'
SEASON = 'Learn2_Seasonal'
G = 0.06  # 铺装面高度

def scene():
    sc = bpy.data.scenes.get(SCENE) or bpy.data.scenes.new(SCENE)
    bpy.context.window.scene = sc
    return sc

def coll(name=COLL, parent=None):
    sc = scene()
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
        (parent or sc.collection).children.link(c)
    def find(lc):
        if lc.collection == c:
            return lc
        for ch in lc.children:
            r = find(ch)
            if r:
                return r
    bpy.context.view_layer.active_layer_collection = find(bpy.context.view_layer.layer_collection)
    return c

def _lin(h):
    return tuple(lb.srgb_to_linear(int(h.lstrip('#')[i:i + 2], 16) / 255) for i in (0, 2, 4))

def C(name, hexcol, sss=0.12, rough=0.88, emit=None, strength=0.0, bump=0.06, spec=0.0, alpha=1.0):
    """黏土材质：高粗糙、Specular=0、少量 SSS、极浅噪声凹凸。emit 给出时设发光色（strength 默认 0=关灯）。"""
    nm = 'L2_' + name
    if nm in bpy.data.materials:
        return bpy.data.materials[nm]
    m = bpy.data.materials.new(nm)
    m.use_nodes = True
    nt = m.node_tree
    b = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    c = _lin(hexcol)
    b.inputs['Base Color'].default_value = (*c, 1)
    b.inputs['Roughness'].default_value = rough
    b.inputs['Specular IOR Level'].default_value = spec
    b.inputs['Subsurface Weight'].default_value = sss
    b.inputs['Subsurface Radius'].default_value = (1.0, 0.7, 0.5)
    b.inputs['Subsurface Scale'].default_value = 0.04
    if alpha < 1:
        b.inputs['Alpha'].default_value = alpha
        m.surface_render_method = 'BLENDED'
    if emit:
        b.inputs['Emission Color'].default_value = (*_lin(emit), 1)
        b.inputs['Emission Strength'].default_value = strength
    if bump > 0:
        tc = nt.nodes.new('ShaderNodeTexCoord')
        nz = nt.nodes.new('ShaderNodeTexNoise')
        nz.inputs['Scale'].default_value = 3.5
        nz.inputs['Detail'].default_value = 2.0
        bp = nt.nodes.new('ShaderNodeBump')
        bp.inputs['Strength'].default_value = bump
        bp.inputs['Distance'].default_value = 0.02
        nt.links.new(tc.outputs['Object'], nz.inputs['Vector'])
        nt.links.new(nz.outputs['Fac'], bp.inputs['Height'])
        nt.links.new(bp.outputs['Normal'], b.inputs['Normal'])
    m.diffuse_color = (*c, alpha)
    return m

def _soft(o, r, seg):
    if r > 0:
        bv = o.modifiers.new('Bevel', 'BEVEL')
        bv.width, bv.segments, bv.limit_method, bv.angle_limit = r, seg, 'ANGLE', math.radians(30)
        bv.harden_normals = False
    o.data.polygons.foreach_set('use_smooth', [True] * len(o.data.polygons))
    wn = o.modifiers.new('WeightedNormal', 'WEIGHTED_NORMAL')
    wn.keep_sharp, wn.weight = False, 50
    return o

def rbox(name, size, loc, m, r=0.06, seg=3, rot=(0, 0, 0)):
    """大圆角盒子：尺寸烘进网格，倒角宽 r（自动不超过最短边 45%）。"""
    o = lb.new_obj(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bm.to_mesh(o.data); bm.free()
    o.data.transform(Matrix.Diagonal((*size, 1)))
    o.location, o.rotation_euler = loc, rot
    o.data.materials.append(m)
    return _soft(o, min(r, min(size) * 0.45), seg)

def rcyl(name, radius, h, loc, m, r=0.03, verts=32, rot=(0, 0, 0)):
    o = lb.new_obj(name)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=verts, radius1=radius, radius2=radius, depth=h)
    bm.to_mesh(o.data); bm.free()
    o.location, o.rotation_euler = loc, rot
    o.data.materials.append(m)
    return _soft(o, min(r, radius * 0.45, h * 0.45), 3)

def ball(name, radius, loc, m, scale=(1, 1, 1)):
    o = lb.new_obj(name)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=14, radius=radius)
    bm.to_mesh(o.data); bm.free()
    o.data.transform(Matrix.Diagonal((*scale, 1)))
    o.location = loc
    o.data.materials.append(m)
    o.data.polygons.foreach_set('use_smooth', [True] * len(o.data.polygons))
    return o

def join(objs, name, parent=None):
    """应用修改器后合并为一个对象（保留多材质），可挂到父级空物体。"""
    objs = [o for o in objs if o and o.type == 'MESH']
    for o in objs:
        lb.apply_all_modifiers(o)
    lb.select_only(objs)
    if len(objs) > 1:
        bpy.ops.object.join()
    j = bpy.context.view_layer.objects.active
    j.name = j.data.name = name
    if parent:
        mw = j.matrix_world.copy()
        j.parent = parent
        j.matrix_world = mw
    return j

def empty(name, loc=(0, 0, 0)):
    e = bpy.data.objects.get(name)
    if e is None:
        e = bpy.data.objects.new(name, None)
        bpy.context.collection.objects.link(e)
    e.location = loc
    e.empty_display_type, e.empty_display_size = 'CUBE', 0.5
    return e

def parent(objs, p):
    for o in objs:
        mw = o.matrix_world.copy()
        o.parent = p
        o.matrix_world = mw

def seasonal_hide(o, hidden=True):
    o['default_visible'] = not hidden
    o.hide_render = hidden
    o.hide_set(hidden)
    return o

# ───────── 传送带 ─────────
def belt_seg(nm, p0, p1, w, M, top=0.42, leg_gap=1.4):
    """直线带段（沿 X 或 Y）：带床 + 深色带面 + 细缝 + 两侧矮挡边 + 矮支腿。返回对象列表。"""
    p0, p1 = Vector((*p0, 0)), Vector((*p1, 0))
    d = p1 - p0
    L = d.length
    ax = 'X' if abs(d.x) > abs(d.y) else 'Y'
    c = (p0 + p1) / 2
    def sz(a, b):  # a=沿带长度，b=横向
        return (a, b) if ax == 'X' else (b, a)
    out = []
    sx, sy = sz(L, w)
    out.append(rbox(nm + '_bed', (sx, sy, 0.14), (c.x, c.y, top - 0.09), M['frame'], r=0.05))
    sx, sy = sz(L - 0.04, w - 0.12)
    out.append(rbox(nm + '_top', (sx, sy, 0.04), (c.x, c.y, top), M['belt'], r=0.015, seg=2))
    n = max(2, int(L / 0.28))
    for i in range(n):
        t = (i + 0.5) / n
        q = p0 + d * t
        sx, sy = sz(0.025, w - 0.14)
        out.append(rbox(nm + '_slit%d' % i, (sx, sy, 0.012), (q.x, q.y, top + 0.02), M['slit'], r=0))
    for s in (-1, 1):
        off = Vector(sz(0, s * (w / 2 - 0.03)) + (0,))
        sx, sy = sz(L, 0.07)
        out.append(rbox(nm + '_rail%d' % s, (sx, sy, 0.1), (c.x + off.x, c.y + off.y, top + 0.06), M['rail'], r=0.03))
    nl = max(2, int(L / leg_gap) + 1)
    for i in range(nl):
        t = 0.08 + 0.84 * i / (nl - 1)
        q = p0 + d * t
        for s in (-1, 1):
            off = Vector(sz(0, s * (w / 2 - 0.1)) + (0,))
            out.append(rcyl(nm + '_leg', 0.05, top - 0.16 - G, (q.x + off.x, q.y + off.y, G + (top - 0.16 - G) / 2), M['leg'], r=0.015, verts=12))
            out.append(rcyl(nm + '_foot', 0.09, 0.04, (q.x + off.x, q.y + off.y, G + 0.02), M['leg'], r=0.015, verts=16))
    return out

def belt_corner(nm, p, w, M, top=0.42):
    """L 形转角：圆角方形转盘。"""
    return [rbox(nm + '_cbed', (w + 0.08, w + 0.08, 0.14), (p[0], p[1], top - 0.09), M['frame'], r=0.12),
            rcyl(nm + '_cdisc', w / 2 - 0.06, 0.04, (p[0], p[1], top), M['belt'], r=0.015),
            rcyl(nm + '_cleg', 0.07, top - 0.16 - G, (p[0], p[1], G + (top - 0.16 - G) / 2), M['leg'], verts=12)]

def port(nm, loc, facing, M, w=0.8, h=0.35, depth=0.18):
    """接驳口：深色口腔 + 一圈圆角法兰 + 4 颗小螺栓。facing: 'N','S','E','W'（口朝向）。"""
    rotz = {'S': 0, 'N': math.pi, 'E': math.pi / 2, 'W': -math.pi / 2}[facing]
    parts = [rbox(nm + '_mouth', (w, depth, h), (0, 0, 0), M['port_in'], r=0.04),
             rbox(nm + '_ft', (w + 0.2, depth - 0.02, 0.09), (0, -0.01, h / 2 + 0.045), M['port'], r=0.035),
             rbox(nm + '_fb', (w + 0.2, depth - 0.02, 0.09), (0, -0.01, -h / 2 - 0.045), M['port'], r=0.035),
             rbox(nm + '_fl', (0.09, depth - 0.02, h), (-w / 2 - 0.055, -0.01, 0), M['port'], r=0.035),
             rbox(nm + '_fr', (0.09, depth - 0.02, h), (w / 2 + 0.055, -0.01, 0), M['port'], r=0.035),
             rbox(nm + '_fl2', (w + 0.36, 0.05, h + 0.32), (0, depth / 2 - 0.02, 0), M['port'], r=0.02)]
    for sx in (-1, 1):
        for sz_ in (-1, 1):
            parts.append(ball(nm + '_bolt', 0.025, (sx * (w / 2 + 0.07), -depth / 2 - 0.01, sz_ * (h / 2 + 0.05)), M['bolt']))
    o = join(parts, nm)
    o.rotation_euler = (0, 0, rotz)
    o.location = loc
    return o
