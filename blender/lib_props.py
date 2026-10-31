"""第 4 轮：风格化道具（低模、圆润、哑光纯色）。所有函数返回创建的对象列表。"""
import bpy, bmesh, math


def lin(h):
    return [((int(h[i:i + 2], 16) / 255 + 0.055) / 1.055) ** 2.4 for i in (0, 2, 4)]


def mat(name, hexcol, rough=0.92, metal=0.0):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    b = next(x for x in m.node_tree.nodes if x.type == 'BSDF_PRINCIPLED')
    c = lin(hexcol)
    b.inputs['Base Color'].default_value = (*c, 1)
    b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metal
    b.inputs['Specular IOR Level'].default_value = 0.15 if metal else 0.0
    m.diffuse_color = (*c, 1)
    return m


def _obj(name, bm, material, smooth=True):
    old = bpy.data.objects.get(name)
    if old:
        bpy.data.objects.remove(old, do_unlink=True)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = smooth
    me.materials.append(material)
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    return o


def _bevel(o, w, seg=2):
    b = o.modifiers.new('Bevel', 'BEVEL')
    b.width = w
    b.segments = seg
    b.limit_method = 'ANGLE'
    b.angle_limit = math.radians(40)
    o.modifiers.new('WN', 'WEIGHTED_NORMAL').keep_sharp = True


def ball(name, loc, r, material, scale=(1, 1, 1), seg=20):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=seg // 2, radius=r)
    o = _obj(name, bm, material)
    o.location = loc
    o.scale = scale
    return o


def tube(name, loc, r1, r2, h, material, seg=20, bevel=0.04):
    """圆台/圆柱，底面落在 loc.z。"""
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r1, radius2=r2, depth=h)
    bmesh.ops.translate(bm, vec=(0, 0, h / 2), verts=bm.verts)
    o = _obj(name, bm, material)
    o.location = loc
    if bevel:
        _bevel(o, min(bevel, h * 0.3, min(r1, r2) * 0.4 if min(r1, r2) > 0 else bevel))
    return o


def rbox(name, loc, size, material, bevel=0.045):
    """圆角盒，底面落在 loc.z。"""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1)
    bmesh.ops.scale(bm, vec=size, verts=bm.verts)
    bmesh.ops.translate(bm, vec=(0, 0, size[2] / 2), verts=bm.verts)
    o = _obj(name, bm, material)
    o.location = loc
    _bevel(o, min(bevel, min(size) * 0.45), 3)
    return o


def tree(name, x, y, z, h=4.2, crown=1.5):
    trunk = mat('Tree_Trunk', '7A5236')
    g1, g2 = mat('Leaf_Dark', '6FA060', 0.95), mat('Leaf_Light', '8FBF7A', 0.95)
    out = [tube(name + '_trunk', (x, y, z), 0.28, 0.2, h * 0.62, trunk, 16, 0.06)]
    cz = z + h * 0.62
    for i, (dx, dy, dz, s, m) in enumerate([(0, 0, crown * 0.55, 1.0, g1), (crown * 0.55, 0.25, 0.1, 0.72, g2),
                                            (-crown * 0.5, -0.2, 0.25, 0.75, g2), (0.1, -crown * 0.45, crown * 0.95, 0.6, g2)]):
        out.append(ball(f'{name}_crown{i}', (x + dx, y + dy, cz + dz), crown * s, m, (1, 1, 0.9)))
    return out


def bamboo(name, x, y, z, n=5, h=4.8):
    stem, leaf = mat('Bamboo_Stem', '9CB86A'), mat('Bamboo_Leaf', '7FAF6A', 0.95)
    out, rng = [], [(0, 0), (0.45, 0.2), (-0.35, 0.35), (0.2, -0.45), (-0.4, -0.3)]
    for i in range(n):
        dx, dy = rng[i % 5]
        hh = h * (0.8 + 0.08 * i)
        out.append(tube(f'{name}_stem{i}', (x + dx, y + dy, z), 0.07, 0.06, hh, stem, 10, 0))
        out.append(ball(f'{name}_leaf{i}', (x + dx * 1.6, y + dy * 1.6, z + hh - 0.3), 0.55, leaf, (1, 1, 1.5), 14))
        out.append(ball(f'{name}_leafB{i}', (x + dx * 1.4 + 0.15, y + dy * 1.4, z + hh * 0.7), 0.42, leaf, (1, 1, 1.3), 12))
    return out


def flower_pot(name, x, y, z, flower_hex):
    pot, soil = mat('Pot_Clay', 'B5705A'), mat('Pot_Rim', 'D9D2C5')
    fl, lf = mat('Flower_' + flower_hex, flower_hex, 0.95), mat('Leaf_Light', '8FBF7A', 0.95)
    out = [tube(name, (x, y, z), 0.3, 0.42, 0.5, pot, 20, 0.05),
           tube(name + '_rim', (x, y, z + 0.46), 0.45, 0.45, 0.08, soil, 20, 0.03),
           ball(name + '_leaf', (x, y, z + 0.66), 0.38, lf, (1, 1, 0.7), 16)]
    for i, (dx, dy) in enumerate([(0.12, 0.05), (-0.13, 0.08), (0.0, -0.14)]):
        out.append(ball(f'{name}_fl{i}', (x + dx, y + dy, z + 0.82), 0.17, fl, (1, 1, 0.9), 12))
    return out


def water_vat(name, x, y, z):
    clay, lid = mat('Vat_Clay', 'B5705A'), mat('Wood_Pillar', '8A5A3B')
    body = ball(name, (x, y, z + 0.5), 0.62, clay, (1, 1, 0.82), 24)
    rim = tube(name + '_rim', (x, y, z + 0.92), 0.5, 0.5, 0.1, clay, 24, 0.03)
    cap = tube(name + '_lid', (x, y, z + 1.0), 0.54, 0.54, 0.07, lid, 24, 0.025)
    knob = ball(name + '_knob', (x, y, z + 1.1), 0.08, lid)
    foot = tube(name + '_foot', (x, y, z), 0.36, 0.36, 0.12, clay, 20, 0.03)
    return [body, rim, cap, knob, foot]


def text3d(name, body, loc, size, material, font_path, depth=0.012, vertical=False):
    """立体文字（朝 -Y），转成 mesh 以便 GLB 导出；字体失败返回 None。"""
    try:
        font = bpy.data.fonts.load(font_path, check_existing=True)
    except Exception as e:
        print('font fail', e)
        return None
    old = bpy.data.objects.get(name)
    if old:
        bpy.data.objects.remove(old, do_unlink=True)
    cu = bpy.data.curves.new(name, 'FONT')
    cu.body = '\n'.join(body) if vertical else body
    cu.font = font
    cu.size = size
    cu.extrude = depth
    cu.align_x = 'CENTER'
    cu.align_y = 'CENTER'
    cu.space_line = 0.95
    cu.resolution_u = 2  # 默认 12 会让每个汉字上千三角面
    o = bpy.data.objects.new(name, cu)
    bpy.context.scene.collection.objects.link(o)
    o.location = loc
    o.rotation_euler = (math.radians(90), 0, 0)
    cu.materials.append(material)
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(o.evaluated_get(dg))
    mw = o.matrix_world.copy()
    bpy.data.objects.remove(o, do_unlink=True)
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    ob.matrix_world = mw
    return ob


def framed_board(name, cx, y_face, cz, w, h, board_mat, frame_mat, margin=0.06, depth=0.04):
    """金边实体板：金色底框贴墙，深色/红色板面凸出在前。y_face 为墙面 y（板向 -Y 凸出）。"""
    f = rbox(name + '_frame', (cx, y_face - depth / 2, cz - h / 2 - margin), (w + 2 * margin, depth, h + 2 * margin), frame_mat, 0.02)
    b = rbox(name + '_board', (cx, y_face - depth - 0.012, cz - h / 2), (w, 0.03, h), board_mat, 0.012)
    return [f, b]


def islands(me):
    """返回每个顶点所属连通块编号（numpy）。"""
    import numpy as np
    ev = np.empty(len(me.edges) * 2, dtype=np.int64)
    me.edges.foreach_get('vertices', ev)
    ev = ev.reshape(-1, 2)
    lab = np.arange(len(me.vertices))
    for _ in range(500):
        old = lab.copy()
        m = np.minimum(lab[ev[:, 0]], lab[ev[:, 1]])
        np.minimum.at(lab, ev[:, 0], m)
        np.minimum.at(lab, ev[:, 1], m)
        lab = lab[lab]
        if (lab == old).all():
            break
    return np.unique(lab, return_inverse=True)[1]


def restyle(o, mats, two_tone=None, seed=1):
    """整体换成纯色哑光材质；two_tone=(matA, matB, ratioB) 时按连通块随机分两档。"""
    import numpy as np
    me = o.data
    me.materials.clear()
    for m in mats:
        me.materials.append(m)
    if two_tone:
        a, b, r = two_tone
        me.materials.clear()
        me.materials.append(a)
        me.materials.append(b)
        lab = islands(me)
        pick = np.random.default_rng(seed).random(lab.max() + 1) < r
        idx = np.zeros(len(me.polygons), dtype=np.int32)
        for p in me.polygons:
            idx[p.index] = 1 if pick[lab[p.vertices[0]]] else 0
        me.polygons.foreach_set('material_index', idx)
    else:
        me.polygons.foreach_set('material_index', [0] * len(me.polygons))
    me.polygons.foreach_set('use_smooth', [True] * len(me.polygons))
    if not any(m.type == 'NODES' and 'Smooth' in m.name for m in o.modifiers):
        try:
            for x in bpy.context.selected_objects:
                x.select_set(False)
            o.select_set(True)
            bpy.context.view_layer.objects.active = o
            bpy.ops.object.shade_smooth_by_angle(angle=math.radians(30))
        except Exception as e:
            print('smooth', e)


def _decimate(o, target_tris):
    tris = sum(len(p.vertices) - 2 for p in o.data.polygons)
    if tris <= target_tris:
        return
    for x in bpy.context.selected_objects:
        x.select_set(False)
    o.select_set(True)
    bpy.context.view_layer.objects.active = o
    d = o.modifiers.new('Dec', 'DECIMATE')
    d.decimate_type = 'COLLAPSE'
    d.ratio = target_tris / tris
    bpy.ops.object.modifier_apply(modifier=d.name)


def thin_leaves(o, keep=0.25, grow=1.6, target_tris=22000, seed=11):
    """Poly Haven 叶片：按连通块随机保留一部分并放大填满树冠，再 Collapse 减面。"""
    import numpy as np
    me = o.data
    lab = islands(me)
    n = lab.max() + 1
    alive = np.random.default_rng(seed).random(n) < keep
    co = np.empty(len(me.vertices) * 3, dtype=np.float64)
    me.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3)
    cen = np.zeros((n, 3))
    np.add.at(cen, lab, co)
    cen /= np.bincount(lab)[:, None]
    co = cen[lab] + (co - cen[lab]) * grow
    me.vertices.foreach_set('co', co.astype(np.float32).ravel())
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[bm.verts[i] for i in np.nonzero(~alive[lab])[0]], context='VERTS')
    bm.to_mesh(me)
    bm.free()
    _decimate(o, target_tris)


def split_by_material(o, prefix):
    """按材质拆分导入模型，返回 {材质名尾词: 对象}。"""
    for x in bpy.context.selected_objects:
        x.select_set(False)
    o.select_set(True)
    bpy.context.view_layer.objects.active = o
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='DESELECT')
    bpy.ops.mesh.separate(type='MATERIAL')
    bpy.ops.object.mode_set(mode='OBJECT')
    out = {}
    for x in list(bpy.context.selected_objects):
        key = x.data.materials[0].name.split('_')[-1] if x.data.materials else 'part'
        x.name = f'{prefix}_{key}'
        out[key] = x
    return out


def purge():
    for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.images):
        for d in list(coll):
            if d.users == 0:
                coll.remove(d)


def flower_bed(name, cx, cy, z, sx, sy, clumps, flower_mats, spacing=0.55, seed=0):
    """石砌矮花坛 + 土面 + 关联复制的草花团（clumps 为源对象列表）。"""
    import random
    rnd = random.Random(seed)
    kerb, soil = mat('Stone_Base', 'D9D2C5'), mat('Soil', '6B5446', 0.95)
    out = [rbox(name + '_kerb', (cx, cy, z), (sx, sy, 0.22), kerb, 0.05),
           rbox(name + '_soil', (cx, cy, z + 0.12), (sx - 0.14, sy - 0.14, 0.12), soil, 0.03)]
    top = z + 0.22
    long_x = sx >= sy
    L = sx if long_x else sy
    n = max(2, int((L - 0.2) / spacing))
    for i in range(n):
        t = -L / 2 + 0.25 + i * (L - 0.5) / max(n - 1, 1)
        jit = rnd.uniform(-0.06, 0.06)
        x, y = (cx + t, cy + jit) if long_x else (cx + jit, cy + t)
        src = rnd.choice(clumps)
        o = bpy.data.objects.new(f'{name}_c{i}', src.data)
        bpy.context.scene.collection.objects.link(o)
        o.location = (x, y, top - 0.02)
        o.rotation_euler = (0, 0, rnd.uniform(0, 6.283))
        s = rnd.uniform(1.5, 1.9)
        o.scale = (s, s, s)
        if len(o.material_slots) > 1:
            o.material_slots[1].link = 'OBJECT'
            o.material_slots[1].material = flower_mats[i % len(flower_mats)]
        out.append(o)
    return out


def bamboo_clump(name, x, y, z, n=6, h=3.6, seed=0, leaves_per_node=9):
    """精细程序化竹丛：带锥度的竹竿 + 5–7 节节环 + 上部节点的披针形叶扇（每片叶 4 三角带中脉折角）。"""
    import random
    from mathutils import Vector, Matrix
    rnd = random.Random(seed)
    stem = mat('Bamboo_Culm', '9DB27A', 0.9)
    node = mat('Bamboo_Node', '7F9A62', 0.9)
    la, lb = mat('Leaf_A', '7FA86A', 0.9), mat('Leaf_B', '5E8A55', 0.9)
    bm = bmesh.new()
    mi = {}

    def add(geom_verts, faces, m):
        vs = [bm.verts.new(v) for v in geom_verts]
        for f in faces:
            bm.faces.new([vs[i] for i in f]).material_index = m

    for c in range(n):
        ang = rnd.uniform(0, 6.283)
        rad = rnd.uniform(0.05, 0.38)
        base = Vector((x + rad * math.cos(ang), y + rad * math.sin(ang), z))
        hh = h * rnd.uniform(0.78, 1.05)
        lean = Vector((math.cos(ang), math.sin(ang), 0)) * rnd.uniform(0.04, 0.12)
        axis = (Vector((0, 0, 1)) + lean).normalized()
        r0 = rnd.uniform(0.045, 0.06)
        nodes = rnd.randint(5, 7)
        seg = 8
        # culm: one tapered tube per internode, with a slightly wider ring at each node
        for k in range(nodes):
            t0, t1 = k / nodes, (k + 1) / nodes
            p0, p1 = base + axis * hh * t0, base + axis * hh * t1
            ra, rb = r0 * (1 - 0.45 * t0), r0 * (1 - 0.45 * t1)
            q = axis.to_track_quat('Z', 'Y').to_matrix()
            ring = lambda p, r: [p + q @ Vector((r * math.cos(2 * math.pi * i / seg), r * math.sin(2 * math.pi * i / seg), 0)) for i in range(seg)]
            v = ring(p0, ra) + ring(p1, rb)
            add(v, [(i, (i + 1) % seg, seg + (i + 1) % seg, seg + i) for i in range(seg)], 0)
            pn = p1 - axis * 0.02
            v = ring(pn, rb * 1.18) + ring(pn + axis * 0.04, rb * 1.18)
            add(v, [(i, (i + 1) % seg, seg + (i + 1) % seg, seg + i) for i in range(seg)], 1)
            # leaf fans on the upper nodes
            if t1 > 0.4:
                for j in range(leaves_per_node + int(t1 * 4)):
                    yaw = rnd.uniform(0, 6.283)
                    L = rnd.uniform(0.22, 0.34)
                    W = L * 0.13
                    out = Vector((math.cos(yaw), math.sin(yaw), 0))
                    side = Vector((-out.y, out.x, 0))
                    tw = p1 + out * rnd.uniform(0.05, 0.35) + Vector((0, 0, rnd.uniform(-0.15, 0.1)))
                    droop = rnd.uniform(0.05, 0.18)
                    tip = tw + out * L + Vector((0, 0, -droop))
                    mid = tw + out * L * 0.4 + Vector((0, 0, 0.02))
                    add([tw, mid - side * W, mid + Vector((0, 0, 0.012)), mid + side * W, tip],
                        [(0, 1, 2), (0, 2, 3), (1, 4, 2), (2, 4, 3)], 2 if rnd.random() < 0.6 else 3)
    old = bpy.data.objects.get(name)
    if old:
        bpy.data.objects.remove(old, do_unlink=True)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for m in (stem, node, la, lb):
        me.materials.append(m)
    me.polygons.foreach_set('use_smooth', [True] * len(me.polygons))
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    return o


def drum_stool(name, x, y, z):
    st = mat('Stone_Base', 'D9D2C5')
    a = tube(name, (x, y, z), 0.24, 0.24, 0.42, st, 20, 0.05)
    b = ball(name + '_belly', (x, y, z + 0.21), 0.28, st, (1, 1, 0.7), 20)
    return [a, b]
