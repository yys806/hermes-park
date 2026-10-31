"""rainbow 地块（彩虹事务）建模辅助：黏土材质 + 圆角基本体。物件名统一带 .rb 后缀，cl_name 存导出名。"""
import bpy, bmesh, math
from mathutils import Vector, Matrix

SUF = '.rb'


def scn():
    return bpy.data.scenes['rainbow']


def lin(h):
    return [((int(h[i:i + 2], 16) / 255 + 0.055) / 1.055) ** 2.4 for i in (0, 2, 4)]


def mat(name, hexcol, emit=0.0):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        if n.type not in ('BSDF_PRINCIPLED', 'OUTPUT_MATERIAL'):
            nt.nodes.remove(n)
    b = next(x for x in nt.nodes if x.type == 'BSDF_PRINCIPLED')
    c = (*lin(hexcol), 1)
    b.inputs['Base Color'].default_value = c
    b.inputs['Roughness'].default_value = 0.92
    b.inputs['Metallic'].default_value = 0.0
    b.inputs['Specular IOR Level'].default_value = 0.0
    b.inputs['Subsurface Weight'].default_value = 0.2
    b.inputs['Subsurface Radius'].default_value = (0.02, 0.015, 0.01)
    b.inputs['Subsurface Scale'].default_value = 0.05
    if emit:
        b.inputs['Emission Color'].default_value = c
        b.inputs['Emission Strength'].default_value = emit
    m.diffuse_color = c
    return m


def clayify(m):
    """把导入资产的材质改成黏土参数，清空贴图只留纯色。"""
    if not m.use_nodes:
        col = tuple(m.diffuse_color)
        m.use_nodes = True
        b = next(x for x in m.node_tree.nodes if x.type == 'BSDF_PRINCIPLED')
        b.inputs['Base Color'].default_value = col
    nt = m.node_tree
    b = next((x for x in nt.nodes if x.type == 'BSDF_PRINCIPLED'), None)
    if b is None:
        return
    for n in list(nt.nodes):
        if n.type not in ('BSDF_PRINCIPLED', 'OUTPUT_MATERIAL'):
            nt.nodes.remove(n)
    b.inputs['Roughness'].default_value = 0.92
    b.inputs['Metallic'].default_value = 0.0
    b.inputs['Specular IOR Level'].default_value = 0.0
    b.inputs['Subsurface Weight'].default_value = 0.2
    b.inputs['Subsurface Radius'].default_value = (0.02, 0.015, 0.01)
    b.inputs['Subsurface Scale'].default_value = 0.05


def link(o, name, parent=None, **props):
    o.name = name + SUF
    if o.data is not None and hasattr(o.data, 'name'):
        o.data.name = name + SUF
    if o.name not in scn().collection.objects:
        scn().collection.objects.link(o)
    o['cl_name'] = name
    for k, v in props.items():
        o[k] = v
    if parent is not None:
        par(o, parent)
    return o


def par(o, parent):
    """挂到父物体下且保持世界位置。"""
    bpy.context.view_layer.update()
    mw = o.matrix_world.copy()
    o.parent = parent
    o.matrix_parent_inverse = parent.matrix_world.inverted()
    return o


def remove(name):
    o = bpy.data.objects.get(name + SUF)
    if o:
        bpy.data.objects.remove(o, do_unlink=True)


def obj_from_bm(name, bm, material, smooth=True, parent=None):
    remove(name)
    me = bpy.data.meshes.new(name + SUF)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = smooth
    if material is not None:
        me.materials.append(material)
    o = bpy.data.objects.new(name + SUF, me)
    return link(o, name, parent)


def bevel(o, w, seg=3, angle=40):
    b = o.modifiers.new('Bevel', 'BEVEL')
    b.width = w
    b.segments = seg
    b.limit_method = 'ANGLE'
    b.angle_limit = math.radians(angle)
    o.modifiers.new('WN', 'WEIGHTED_NORMAL').keep_sharp = True
    return o


def rbox(name, loc, size, material, bv=0.05, rot=(0, 0, 0), parent=None):
    """圆角盒，loc 为底面中心。"""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1)
    bmesh.ops.scale(bm, vec=size, verts=bm.verts)
    bmesh.ops.translate(bm, vec=(0, 0, size[2] / 2), verts=bm.verts)
    o = obj_from_bm(name, bm, material, parent=parent)
    o.location = loc
    o.rotation_euler = rot
    return bevel(o, min(bv, min(size) * 0.45))


def cyl(name, loc, r1, r2, h, material, seg=32, bv=0.03, rot=(0, 0, 0), parent=None):
    """圆台，loc 为底面中心。"""
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r1, radius2=r2, depth=h)
    bmesh.ops.translate(bm, vec=(0, 0, h / 2), verts=bm.verts)
    o = obj_from_bm(name, bm, material, parent=parent)
    o.location = loc
    o.rotation_euler = rot
    if bv:
        bevel(o, min(bv, h * 0.3, max(min(r1, r2), 0.01) * 0.4))
    return o


def ball(name, loc, r, material, scale=(1, 1, 1), seg=24, parent=None):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=seg // 2, radius=r)
    o = obj_from_bm(name, bm, material, parent=parent)
    o.location = loc
    o.scale = scale
    return o


def heart_bm(size=1.0, depth=0.4, n=64):
    """竖立的心形（XZ 平面，沿 Y 挤出），返回 bmesh，底尖在原点。"""
    bm = bmesh.new()
    pts = []
    for i in range(n):
        t = 2 * math.pi * i / n
        x = 16 * math.sin(t) ** 3
        z = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        pts.append((x / 32 * size, z / 32 * size))
    zmin = min(p[1] for p in pts)
    vs = [bm.verts.new((x, -depth / 2, z - zmin)) for x, z in pts]
    f = bm.faces.new(vs)
    r = bmesh.ops.extrude_face_region(bm, geom=[f])
    nv = [g for g in r['geom'] if isinstance(g, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, vec=(0, depth, 0), verts=nv)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def join(objs, name):
    """合并对象（先应用修改器），返回合并后的对象，名字为 name。"""
    dg = bpy.context.evaluated_depsgraph_get()
    bm = bmesh.new()
    mats = []
    for o in objs:
        ev = o.evaluated_get(dg)
        me = bpy.data.meshes.new_from_object(ev)
        me.transform(o.matrix_world)
        idx = []
        for m in me.materials:
            if m not in mats:
                mats.append(m)
            idx.append(mats.index(m))
        for p in me.polygons:
            p.material_index = idx[p.material_index] if idx else 0
        bm.from_mesh(me)
        bpy.data.meshes.remove(me)
    for o in objs:
        bpy.data.objects.remove(o, do_unlink=True)
    remove(name)
    me = bpy.data.meshes.new(name + SUF)
    bm.to_mesh(me)
    bm.free()
    for m in mats:
        me.materials.append(m)
    o = bpy.data.objects.new(name + SUF, me)
    return link(o, name)


def empty(name, loc=(0, 0, 0), parent=None, **props):
    remove(name)
    e = bpy.data.objects.new(name + SUF, None)
    e.location = loc
    e.empty_display_size = 0.5
    return link(e, name, parent, **props)


def append_asset(path, name_hint=None):
    """从 .blend append 所有网格对象并合并成一个，返回对象（未链接到场景以外的地方）。"""
    with bpy.data.libraries.load(path, link=False) as (src, dst):
        dst.objects = list(src.objects)
    objs = [o for o in dst.objects if o is not None and o.type == 'MESH']
    for o in dst.objects:
        if o is not None and o.type != 'MESH':
            bpy.data.objects.remove(o, do_unlink=True)
    for o in objs:
        scn().collection.objects.link(o)
        for m in o.data.materials:
            if m:
                clayify(m)
    return objs


def belt(name, pts, w, M, z=0.34, leg_step=1.3):
    """抬高的传送带：pts 折线 (x,y)，宽 w。M: frame/belt/slit/rail/leg/bolt 材质。返回合并对象。"""
    parts = []
    k = [0]

    def nm():
        k[0] += 1
        return '_b%d' % k[0]
    P = [Vector((x, y)) for x, y in pts]
    for i in range(len(P) - 1):
        a, b = P[i], P[i + 1]
        d = b - a
        n = d.length
        horiz = abs(d.x) > abs(d.y)
        c = (a + b) / 2
        ext = w / 2 + 0.05 if 0 < i else 0.0      # 拐角处延伸，避免缺口
        ext2 = w / 2 + 0.05 if i + 1 < len(P) - 1 else 0.0
        L = n + ext + ext2
        sh = (ext2 - ext) / 2
        dn = d.normalized()
        c = c + dn * sh
        sz = (lambda t, h: (L, t, h)) if horiz else (lambda t, h: (t, L, h))
        parts.append(rbox(nm(), (c.x, c.y, z), sz(w + 0.12, 0.12), M['frame'], bv=0.035))
        parts.append(rbox(nm(), (c.x, c.y, z + 0.11), sz(w - 0.06, 0.03), M['belt'], bv=0.012))
        ns = int(L / 0.28)
        for j in range(1, ns):
            q = c + dn * (-L / 2 + j * L / ns)
            s2 = (0.025, w - 0.08, 0.012) if horiz else (w - 0.08, 0.025, 0.012)
            parts.append(rbox(nm(), (q.x, q.y, z + 0.135), s2, M['slit'], bv=0.004))
        pv = Vector((-dn.y, dn.x))
        for sgn in (-1, 1):
            q = c + pv * sgn * (w / 2 + 0.03)
            parts.append(rbox(nm(), (q.x, q.y, z + 0.12), sz(0.05, 0.1), M['rail'], bv=0.02))
        nl = max(1, int(n / leg_step))
        for j in range(nl + 1):
            q0 = a + d * (j / nl)
            for sgn in (-1, 1):
                q = q0 + pv * sgn * (w / 2 - 0.02)
                parts.append(cyl(nm(), (q.x, q.y, 0.0), 0.045, 0.04, z + 0.01, M['leg'], seg=12, bv=0.015))
                parts.append(cyl(nm(), (q.x, q.y, 0.0), 0.08, 0.075, 0.07, M['leg'], seg=14, bv=0.02))
                qb = q0 + pv * sgn * (w / 2 + 0.065)
                parts.append(ball(nm(), (qb.x, qb.y, z + 0.06), 0.022, M['bolt'], seg=10))
    return join(parts, name)


def port(name, loc, rz, w, dpt, M, h=0.42):
    """功能出口：带宽法兰的方口 + 螺栓。loc 为底面中心，开口朝局部 -Y（rz 旋转）。"""
    parts = [rbox(name + '_body', (0, 0, 0.0), (w, dpt, h), M['port'], bv=0.05),
             rbox(name + '_in', (0, -dpt / 2 + 0.03, 0.24), (w - 0.24, 0.08, h - 0.33), M['port_in'], bv=0.02),
             ]
    fy = -dpt / 2 - 0.02
    fw = 0.11   # 宽法兰：四条框组成
    for sx in (-1, 1):
        parts.append(rbox(name + '_fl_s%d' % sx, (sx * (w / 2 + 0.08 - fw / 2), fy, -0.0), (fw, 0.05, h + 0.06), M['frame'], bv=0.02))
    parts.append(rbox(name + '_fl_t', (0, fy, h + 0.06 - fw), (w + 0.16, 0.05, fw), M['frame'], bv=0.02))
    parts.append(rbox(name + '_fl_b', (0, fy, 0.0), (w + 0.16, 0.05, fw), M['frame'], bv=0.02))
    for sx in (-1, 1):
        for sz_ in (0, 1):
            parts.append(ball(name + '_bolt%d%d' % (sx, sz_), (sx * (w / 2 + 0.03), -dpt / 2 - 0.05, 0.09 + sz_ * (h - 0.06)), 0.028, M['bolt'], seg=10))
    parts.append(rbox(name + '_lip', (0, -dpt / 2 - 0.05, 0.2), (w - 0.2, 0.06, 0.04), M['port_in'], bv=0.015))
    o = join(parts, name)
    o.location = loc
    o.rotation_euler = (0, 0, rz)
    return o


def import_fbx(path):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=path)
    new = [o for o in bpy.data.objects if o not in before]
    for o in new:
        for m in getattr(o.data, 'materials', []) or []:
            if m:
                clayify(m)
    return new
