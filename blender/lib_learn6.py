"""学习科研地块 第6轮：灯具实体（路灯 / 吊灯 / 壁灯）。Blender 4.5
每盏灯 = 空物体组 LGT_learn_<id>（custom prop castShadow）
       ├ LGT_learn_<id>_body   普通材质（杆/底座/托架/吸顶盘），不发光
       ├ LGT_learn_<id>_shade  材质 LGT_learn_<id>（唯一发光材质；对阴影不可见，光才透得出来）
       └ LGT_learn_<id>_light  点光源，use_shadow=True"""
import bpy, bmesh, math
from mathutils import Vector, Matrix
import lib_building as lb
import lib_learn5 as L5

COLL = 'Learn2'

def P():
    return bpy.app.driver_namespace['L2P']

def cone(bm, r1, r2, h, z0, verts=16, cap=True, xy=(0, 0)):
    """底面在 z0 的圆台（verts=8 即八角）。"""
    m = Matrix.Translation((xy[0], xy[1], z0 + h / 2))
    bmesh.ops.create_cone(bm, cap_ends=cap, segments=verts, radius1=r1, radius2=r2, depth=h, matrix=m)

def shell(bm, r1, r2, h, z0, t, verts=24):
    """有厚度、上下开口的灯罩：内外两层圆台 + 上下环面。"""
    def ring(r, z):
        return [bm.verts.new((r * math.cos(k / verts * math.tau), r * math.sin(k / verts * math.tau), z)) for k in range(verts)]
    ob, ot, ib, it = ring(r1, z0), ring(r2, z0 + h), ring(r1 - t, z0), ring(r2 - t, z0 + h)
    for a, b, flip in ((ob, ot, False), (it, ib, False), (ib, ob, False), (ot, it, False)):
        for k in range(verts):
            q = (a[k], a[(k + 1) % verts], b[(k + 1) % verts], b[k])
            bm.faces.new(q[::-1] if flip else q)

def ball(bm, r, c):
    bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=10, radius=r, matrix=Matrix.Translation(c))

def mesh(name, bm, mats):
    """bm 的面按 material_index 已设好；返回对象（光滑着色 + AO 层）。"""
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    o = lb.new_obj(name)
    bm.to_mesh(o.data); bm.free()
    o.data.polygons.foreach_set('use_smooth', [True] * len(o.data.polygons))
    for m in mats: o.data.materials.append(m)
    L5.ensure_ao(o)
    return o

def cleanup(lid):
    """删掉同名旧灯组（含网格数据），以便重建。"""
    nm = 'LGT_learn_' + lid
    for suf in ('_body', '_shade', '_light', ''):
        o = bpy.data.objects.get(nm + suf)
        if o:
            d = o.data; bpy.data.objects.remove(o, do_unlink=True)
            if d is not None and d.users == 0:
                (bpy.data.lights if isinstance(d, bpy.types.Light) else bpy.data.meshes).remove(d)

def tag(bm, i, before):
    for f in bm.faces[before:]:
        f.material_index = i

def lamp_mat(lid, hexcol, strength):
    nm = 'LGT_learn_' + lid
    m = bpy.data.materials.get(nm) or L5.clay_nodes(bpy.data.materials.new(nm), L5.srgb(hexcol))
    b = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    b.inputs['Emission Color'].default_value = L5.srgb(hexcol)
    b.inputs['Emission Strength'].default_value = strength
    b.inputs['Subsurface Weight'].default_value = 0.0
    m['lgt'] = True
    return m

def group(lid, loc, body, shade, light_z, energy, color=(1.0, 0.82, 0.58), radius=0.06):
    """组装：空物体 + body + shade + 点光源。loc 为世界坐标（x,y,z0）；部件按局部坐标建在原点。"""
    nm = 'LGT_learn_' + lid
    e = bpy.data.objects.new(nm, None); e.empty_display_size = 0.3
    bpy.data.collections[COLL].objects.link(e)
    e.location = loc; e['castShadow'] = True; e['lgt_kind'] = lid.split('_')[0]
    ld = bpy.data.lights.get(nm + '_light') or bpy.data.lights.new(nm + '_light', 'POINT')
    ld.energy = energy; ld.color = color; ld.shadow_soft_size = radius; ld.use_shadow = True
    lo = bpy.data.objects.new(nm + '_light', ld); bpy.data.collections[COLL].objects.link(lo)
    lo.location = (0, 0, light_z); lo['castShadow'] = True
    for o in (body, shade, lo):
        if o is None: continue
        o.parent = e
        if o.name in bpy.context.scene.collection.objects: pass
        for c in list(o.users_collection):
            if c.name != COLL: c.objects.unlink(o)
        if COLL not in [c.name for c in o.users_collection]: bpy.data.collections[COLL].objects.link(o)
    if shade is not None:
        shade.visible_shadow = False   # Cycles：灯罩不挡自己的点光源
    return e

# ───────── 路灯：底座 + 锥度灯杆 + 八角灯笼头 + 挑檐顶帽 ─────────
def clashes(lid, margin=0.05, skip=('Ground_', 'Snow_ground', 'LGT_learn_')):
    """灯组 body/shade 与 Learn2 其它网格（含隐藏的季节变体）做 BVH 相交 + 包围盒间隙检测。"""
    from mathutils.bvhtree import BVHTree
    dg = bpy.context.evaluated_depsgraph_get(); bpy.context.view_layer.update()
    def bvh(o):
        return BVHTree.FromPolygons([o.matrix_world @ v.co for v in o.data.vertices], [p.vertices[:] for p in o.data.polygons])
    def box(o, m=0.0):
        b = [o.matrix_world @ Vector(c) for c in o.bound_box]
        return [min(v[k] for v in b) - m for k in range(3)], [max(v[k] for v in b) + m for k in range(3)]
    mine = [bpy.data.objects[n] for n in ('LGT_learn_%s_body' % lid, 'LGT_learn_%s_shade' % lid) if n in bpy.data.objects]
    hits = []
    for a in mine:
        amn, amx = box(a, margin); ta = bvh(a)
        for o in bpy.data.collections[COLL].all_objects:
            if o.type != 'MESH' or o.name.startswith(skip): continue
            bmn, bmx = box(o)
            if any(amx[k] < bmn[k] or bmx[k] < amn[k] for k in range(3)): continue
            if ta.overlap(bvh(o)): hits.append(o.name)
            else:
                # 未相交但很近：用最近点测间隙
                tb = bvh(o); gap = min((tb.find_nearest(a.matrix_world @ v.co)[3] or 9) for v in list(a.data.vertices)[::3])
                if gap < margin: hits.append('%s(gap %.3f)' % (o.name, gap))
    return sorted(set(hits))

def street(lid, x, y, z0=0.12, H=2.75, energy=60):
    cleanup(lid); p = P(); post, gold = p['lamppost'], p['bolt']
    bm = bmesh.new()
    cone(bm, 0.24, 0.24, 0.06, 0.0, 8)              # 底盘
    cone(bm, 0.19, 0.13, 0.26, 0.06, 8)             # 八角底座（略粗）
    cone(bm, 0.095, 0.085, 0.07, 0.32, 16)          # 底座收口环
    cone(bm, 0.062, 0.042, H - 0.95, 0.39, 16)      # 锥度灯杆
    zc = H - 0.56                                    # 杆顶
    cone(bm, 0.07, 0.09, 0.05, zc - 0.08, 16)       # 颈环
    cone(bm, 0.05, 0.17, 0.09, zc - 0.03, 8)        # 托盘（向外撇）
    cone(bm, 0.19, 0.19, 0.035, zc + 0.06, 8)       # 灯头底板
    for k in range(8):                               # 八根框条
        a = (k + 0.5) / 8 * math.tau
        cone(bm, 0.013, 0.013, 0.34, zc + 0.095, 6, xy=(0.168 * math.cos(a), 0.168 * math.sin(a)))
    cone(bm, 0.2, 0.2, 0.03, zc + 0.435, 8)         # 上框
    cone(bm, 0.27, 0.07, 0.16, zc + 0.465, 8)       # 挑檐顶帽
    cone(bm, 0.05, 0.03, 0.06, zc + 0.625, 8)       # 帽颈
    ball(bm, 0.045, (0, 0, zc + 0.72))               # 顶珠
    n0 = len(bm.faces)
    for k in range(2):                               # 两个挂钩装饰
        a = k * math.pi
        cone(bm, 0.025, 0.012, 0.12, zc - 0.25, 6, xy=(0.07 * math.cos(a), 0.07 * math.sin(a)))
    tag(bm, 1, n0)
    body = mesh('LGT_learn_%s_body' % lid, bm, [post, gold])
    bs = bmesh.new()
    cone(bs, 0.15, 0.15, 0.34, zc + 0.095, 8)        # 八角灯罩（发光）
    shade = mesh('LGT_learn_%s_shade' % lid, bs, [lamp_mat(lid, '#FFE2A8', 6.0)])
    return group(lid, (x, y, z0), body, shade, zc + 0.27, energy)

# ───────── 吊灯：吸顶盘 + 吊杆 + 有厚度的圆台灯罩 + 灯泡 ─────────
def pendant(lid, x, y, z_ceil, drop=0.75, r_bot=0.24, r_top=0.08, h=0.2, hexcol='#FFE9C2', energy=35):
    cleanup(lid); p = P()
    bm = bmesh.new()
    cone(bm, 0.11, 0.09, 0.035, -0.035, 24)          # 吸顶盘
    cone(bm, 0.012, 0.012, drop, -0.035 - drop, 8)   # 吊杆
    cone(bm, 0.035, 0.035, 0.05, -0.035 - drop - 0.03, 12)   # 灯头座
    body = mesh('LGT_learn_%s_body' % lid, bm, [p['lamppost']])
    zt = -0.035 - drop
    bs = bmesh.new()
    shell(bs, r_bot, r_top, h, zt - h + 0.02, 0.018, 28)   # 有厚度的开口灯罩
    cone(bs, r_top, 0.03, 0.03, zt + 0.02, 28, cap=True)    # 罩顶封口（留中孔视觉由座盖住）
    ball(bs, 0.055, (0, 0, zt - h * 0.55))                  # 灯泡
    shade = mesh('LGT_learn_%s_shade' % lid, bs, [lamp_mat(lid, hexcol, 5.0)])
    return group(lid, (x, y, z_ceil), body, shade, zt - h * 0.55, energy, radius=0.05)

# ───────── 壁灯：墙板 + 铁艺弯臂（挑出 ~0.3 m）+ 吊挂小灯笼 ─────────
def wall(lid, x, y, z, facing='S', reach=0.3, energy=25):
    import lib_learn4 as L4
    cleanup(lid); p = P(); post = p['lamppost']
    rz = {'S': 0, 'N': math.pi, 'E': math.pi / 2, 'W': -math.pi / 2}[facing]
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation((0, -0.015, 0)) @ Matrix.Diagonal((0.1, 0.03, 0.2, 1)))  # 墙板
    arm = L4.tube('tmp_arm', L4.bez((0, -0.02, 0.0), (0, -reach * 0.55, 0.12), (0, -reach, 0.02), 8), [0.016] * 8, post, 8)
    curl = L4.tube('tmp_curl', L4.bez((0, -0.02, -0.08), (0, -reach * 0.35, -0.1), (0, -reach * 0.6, 0.06), 6), [0.01] * 6, post, 6)
    for t in (arm, curl):
        bm.from_mesh(t.data); me = t.data; bpy.data.objects.remove(t, do_unlink=True); bpy.data.meshes.remove(me)
    cone(bm, 0.008, 0.008, 0.08, -0.06, 6, xy=(0, -reach))          # 吊杆
    cone(bm, 0.11, 0.03, 0.08, -0.1, 8, xy=(0, -reach))              # 顶帽
    cone(bm, 0.085, 0.085, 0.025, -0.36, 8, xy=(0, -reach))          # 底板
    for k in range(4):
        a = (k + 0.5) / 4 * math.tau
        cone(bm, 0.009, 0.009, 0.24, -0.34, 6, xy=(0.075 * math.cos(a), -reach + 0.075 * math.sin(a)))
    ball(bm, 0.025, (0, -reach, -0.39))
    body = mesh('LGT_learn_%s_body' % lid, bm, [post])
    bs = bmesh.new()
    cone(bs, 0.07, 0.07, 0.24, -0.34, 8, xy=(0, -reach))             # 玻璃罩（发光）
    shade = mesh('LGT_learn_%s_shade' % lid, bs, [lamp_mat(lid, '#FFE2A8', 5.0)])
    e = group(lid, (x, y, z), body, shade, -0.22, energy)
    e.rotation_euler = (0, 0, rz)
    bpy.data.objects['LGT_learn_%s_light' % lid].location = (0, -reach, -0.22)
    return e
