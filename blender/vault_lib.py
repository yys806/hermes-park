# vault 地块（资产管理）建模工具库：每次 execute 前 exec 载入
import bpy, bmesh, math
from mathutils import Vector, Matrix, Euler

SC = bpy.data.scenes['vault']


def M(name, rgb=(0.8, 0.8, 0.8), rough=0.85, emit=None, strength=4.0, metal=0.0):
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials['VA_wall'].copy()
    m.name = name
    nt = m.node_tree
    mix = next(n for n in nt.nodes if n.type == 'MIX')
    mix.inputs['A_Color'].default_value = (*rgb, 1)
    p = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    p.inputs['Roughness'].default_value = rough
    p.inputs['Metallic'].default_value = metal
    if emit:
        p.inputs['Emission Color'].default_value = (*emit, 1)
        p.inputs['Emission Strength'].default_value = strength
    else:
        p.inputs['Emission Strength'].default_value = 0.0
    m.diffuse_color = (*rgb, 1)
    return m


def finish(name, bm, mats, loc=(0, 0, 0), rot=(0, 0, 0), props=None, sharp=35):
    if isinstance(mats, bpy.types.Material) or mats is None:
        mats = [mats]
    mw = Matrix.Translation(loc) @ Euler(rot).to_matrix().to_4x4()
    for f in bm.faces:
        f.smooth = True
    th = math.radians(sharp)
    for e in bm.edges:
        if len(e.link_faces) == 2 and e.calc_face_angle(0) > th:
            e.smooth = False
    old = bpy.data.objects.get(name)
    if old:
        om = old.data
        bpy.data.objects.remove(old)
        if om and om.users == 0:
            bpy.data.meshes.remove(om)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for m in mats:
        me.materials.append(m)
    ao = me.color_attributes.new('AO', 'BYTE_COLOR', 'CORNER')
    vs = me.vertices
    r3 = mw.to_3x3()
    cols = []
    for poly in me.polygons:
        nz = (r3 @ poly.normal).z
        k = 0.82 if nz < -0.5 else 1.0
        for li in poly.loop_indices:
            z = (mw @ vs[me.loops[li].vertex_index].co).z
            a = (0.62 + 0.38 * min(1.0, max(0.0, z / 0.7))) * k
            cols.append((li, a))
    flat = [0.0] * (len(me.loops) * 4)
    for li, a in cols:
        flat[li * 4:li * 4 + 4] = (a, a, a, 1.0)
    ao.data.foreach_set('color', flat)
    me.color_attributes.active_color_name = 'AO'
    o = bpy.data.objects.new(name, me)
    o.location = loc
    o.rotation_euler = rot
    SC.collection.objects.link(o)
    o['export_name'] = name
    for k_, v in (props or {}).items():
        o[k_] = v
    return o


def bev(bm, r, seg, ang=30):
    if r <= 0:
        return
    th = math.radians(ang)
    es = [e for e in bm.edges if len(e.link_faces) == 2 and e.calc_face_angle(0) > th]
    if es:
        bmesh.ops.bevel(bm, geom=es, offset=r, segments=seg, profile=0.5,
                        affect='EDGES', clamp_overlap=True)


def _merge(bm, t):
    me = bpy.data.meshes.new('_t')
    t.to_mesh(me)
    t.free()
    bm.from_mesh(me)
    bpy.data.meshes.remove(me)


def boxbm(bm, s, c, rot=0.0, r=0.0, seg=2):
    t = bmesh.new()
    bmesh.ops.create_cube(t, size=1)
    bmesh.ops.scale(t, vec=s, verts=t.verts)
    if r > 0:
        bev(t, min(r, min(s) * 0.45), seg)
    bmesh.ops.rotate(t, verts=t.verts, matrix=Matrix.Rotation(rot, 3, 'Z'))
    bmesh.ops.translate(t, vec=c, verts=t.verts)
    _merge(bm, t)


def cylbm(bm, r, h, c, n=24, b=0.0, seg=2, rot=(0, 0, 0), r2=None):
    t = bmesh.new()
    bmesh.ops.create_cone(t, cap_ends=True, segments=n, radius1=r,
                          radius2=(r if r2 is None else r2), depth=h)
    if b > 0:
        bev(t, min(b, h * 0.45, r * 0.45), seg, ang=50)
    bmesh.ops.rotate(t, verts=t.verts, matrix=Euler(rot).to_matrix())
    bmesh.ops.translate(t, vec=c, verts=t.verts)
    _merge(bm, t)


def rbox(name, s, loc, mat, r=0.02, seg=3, rot=(0, 0, 0), props=None):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=s, verts=bm.verts)
    bev(bm, min(r, min(s) * 0.45), seg)
    return finish(name, bm, mat, loc, rot, props)


def cyl(name, r, h, loc, mat, n=32, b=0.01, seg=2, rot=(0, 0, 0), r2=None, props=None):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=n, radius1=r,
                          radius2=(r if r2 is None else r2), depth=h)
    bev(bm, min(b, h * 0.45, r * 0.45), seg, ang=50 if n >= 12 else 30)
    return finish(name, bm, mat, loc, rot, props)


def sph(name, r, loc, mat, u=24, v=12, s=(1, 1, 1), rot=(0, 0, 0), props=None):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=u, v_segments=v, radius=r)
    bmesh.ops.scale(bm, vec=s, verts=bm.verts)
    return finish(name, bm, mat, loc, rot, props, sharp=80)


def torbm(bm, R, r, n=48, m=12, c=(0, 0, 0), rot=(0, 0, 0)):
    t = bmesh.new()
    vs = []
    for i in range(n):
        a = 2 * math.pi * i / n
        row = []
        for j in range(m):
            b = 2 * math.pi * j / m
            row.append(t.verts.new(((R + r * math.cos(b)) * math.cos(a),
                                    (R + r * math.cos(b)) * math.sin(a), r * math.sin(b))))
        vs.append(row)
    for i in range(n):
        for j in range(m):
            t.faces.new((vs[i][j], vs[(i + 1) % n][j], vs[(i + 1) % n][(j + 1) % m], vs[i][(j + 1) % m]))
    bmesh.ops.rotate(t, verts=t.verts, matrix=Euler(rot).to_matrix())
    bmesh.ops.translate(t, vec=Vector(c), verts=t.verts)
    _merge(bm, t)


def tor(name, R, r, loc, mat, n=48, m=12, rot=(0, 0, 0), props=None):
    bm = bmesh.new()
    torbm(bm, R, r, n, m)
    return finish(name, bm, mat, loc, rot, props, sharp=80)


def tubebm(bm, pts, r, n=10):
    """折线管：沿点列扫掠圆截面（点列先做 Catmull-Rom 平滑）"""
    P = [Vector(p) for p in pts]
    sm = []
    for i in range(len(P) - 1):
        p0 = P[max(i - 1, 0)]; p1 = P[i]; p2 = P[i + 1]; p3 = P[min(i + 2, len(P) - 1)]
        for k in range(6):
            t = k / 6
            sm.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                             + (-p0 + 3 * p1 - 3 * p2 + p3) * t * t * t))
    sm.append(P[-1])
    rings = []
    up = Vector((0, 0, 1))
    for i, p in enumerate(sm):
        d = (sm[min(i + 1, len(sm) - 1)] - sm[max(i - 1, 0)]).normalized()
        ref = up if abs(d.dot(up)) < 0.9 else Vector((1, 0, 0))
        u = d.cross(ref).normalized()
        v = d.cross(u).normalized()
        rings.append([bm.verts.new(p + (u * math.cos(2 * math.pi * j / n) + v * math.sin(2 * math.pi * j / n)) * r)
                      for j in range(n)])
    for a, b in zip(rings, rings[1:]):
        for j in range(n):
            bm.faces.new((a[j], b[j], b[(j + 1) % n], a[(j + 1) % n]))
    bm.faces.new(rings[0][::-1])
    bm.faces.new(rings[-1])


def tube(name, pts, r, mat, n=10, props=None):
    bm = bmesh.new()
    tubebm(bm, pts, r, n)
    return finish(name, bm, mat, (0, 0, 0), (0, 0, 0), props, sharp=80)


def kill(prefixes):
    dead = [o for o in SC.objects if o.name.startswith(prefixes)
            and not any(s != SC and o.name in s.objects for s in bpy.data.scenes)]
    mes = [o.data for o in dead if o.type == 'MESH']
    bpy.data.batch_remove(dead)
    bpy.data.batch_remove([m for m in mes if m.users == 0])
    return len(dead)


# ---------------- 传送带 ----------------
W = 0.46
Z0 = 0.02


def seg_parts(tag, i, A, B, c0, c1, in0, in1):
    MF = M('VA_frame'); MB = M('VA_belt'); MR = M('VA_rail'); ML = M('VA_leg'); MBo = M('VA_bolt')
    A = Vector((*A, 0)); B = Vector((*B, 0))
    d = (B - A).normalized(); n = Vector((-d.y, d.x, 0))
    e0 = -W / 2 if c0 else 0; e1 = W / 2 if c1 else 0
    a = A - d * e0; b = B + d * e1
    L = (b - a).length; c = (a + b) / 2; ang = math.atan2(d.y, d.x)
    bm = bmesh.new()
    boxbm(bm, (L, W - 0.06, 0.03), c + Vector((0, 0, 0.255)), ang, 0.01, 2)
    k = max(1, int(L / 0.28))
    for j in range(k):
        p = a + d * ((j + 0.5) * L / k)
        boxbm(bm, (0.035, W - 0.12, 0.018), p + Vector((0, 0, 0.276)), ang, 0.007, 2)
    for j in range(max(2, int(L / 0.3))):   # 托辊（侧面可见）
        p = a + d * ((j + 0.5) * L / max(2, int(L / 0.3)))
        cylbm(bm, 0.03, W - 0.1, p + Vector((0, 0, 0.215)), 16, 0.006, 1, rot=(math.pi / 2, 0, ang))
    nm = f'Belt_Sub_{tag}_{i}' if tag != 'Main' else f'Belt_Main_vault_{i}'
    VA_last = finish(nm, bm, MB)
    # 框架：两侧槽钢，中间透出托辊
    for side in (1, -1):
        VA_c = c + n * side * (W / 2 - 0.025) + Vector((0, 0, 0.2))
        rbox(f'Frame_belt_{tag}_{i}_{"L" if side > 0 else "R"}', (L, 0.05, 0.1), VA_c, MF, 0.015, 3, (0, 0, ang))
    for side in (1, -1):
        s0 = (-W / 2 if in0 == side else W / 2) if c0 else 0
        s1 = (-W / 2 if in1 == side else W / 2) if c1 else 0
        aa = A - d * s0; bb = B + d * s1; LL = (bb - aa).dot(d)
        if LL < 0.05:
            continue
        cc = (aa + bb) / 2 + n * side * (W / 2 - 0.02)
        rbox(f'Rail_belt_{tag}_{i}_{"L" if side > 0 else "R"}', (LL, 0.04, 0.1),
             cc + Vector((0, 0, 0.3)), MR, 0.018, 3, (0, 0, ang))
    nl = max(1, int(L / 0.9))
    for j in range(nl + 1):
        p = a + d * (0.12 + (L - 0.24) * j / nl)
        for side in (1, -1):
            q = p + n * side * (W / 2 - 0.05)
            sfx = f'{tag}_{i}_{j}{"L" if side > 0 else "R"}'
            rbox(f'Bracket_leg_{sfx}', (0.05, 0.05, 0.15), q + Vector((0, 0, Z0 + 0.075)), ML, 0.012, 2, (0, 0, ang))
            rbox(f'Bracket_foot_{sfx}', (0.11, 0.11, 0.02), q + Vector((0, 0, Z0 + 0.01)), ML, 0.006, 2, (0, 0, ang))
            cyl(f'Bolt_foot_{sfx}', 0.014, 0.016, q + d * 0.035 + Vector((0, 0, Z0 + 0.026)), MBo, 6, 0.003, 1)
    return L


def flange(tag, P, d, label):
    MFl = M('VA_flange'); MBo = M('VA_bolt')
    P = Vector((*P, 0)); d = Vector((*d, 0)).normalized(); n = Vector((-d.y, d.x, 0)); ang = math.atan2(d.y, d.x)
    rbox(f'Trim_flange_{tag}_{label}', (0.05, W + 0.14, 0.26), P + Vector((0, 0, 0.23)), MFl, 0.015, 3, (0, 0, ang))
    for k, (u, v) in enumerate(((1, 1), (1, -1), (-1, 1), (-1, -1))):
        for s in (1, -1):
            q = P + d * 0.03 * s + n * u * (W / 2 + 0.035) + Vector((0, 0, 0.23 + v * 0.085))
            cyl(f'Bolt_flange_{tag}_{label}_{k}{"f" if s > 0 else "b"}', 0.016, 0.02, q, MBo, 6, 0.003, 1,
                rot=(0, math.pi / 2, ang))


def lane(tag, pts):
    def turn(P, Q, R):
        d1 = (Q[0] - P[0], Q[1] - P[1]); d2 = (R[0] - Q[0], R[1] - Q[1])
        return 1 if d1[0] * d2[1] - d1[1] * d2[0] > 0 else -1
    Ls = 0
    for i in range(len(pts) - 1):
        A, B = pts[i], pts[i + 1]
        c0 = i > 0; c1 = i < len(pts) - 2
        in0 = turn(pts[i - 1], A, B) if c0 else 0
        in1 = turn(A, B, pts[i + 2]) if c1 else 0
        Ls += seg_parts(tag, i, A, B, c0, c1, in0, in1)
    d0 = (pts[1][0] - pts[0][0], pts[1][1] - pts[0][1])
    d1 = (pts[-1][0] - pts[-2][0], pts[-1][1] - pts[-2][1])
    flange(tag, pts[0], d0, 'a')
    flange(tag, pts[-1], d1, 'b')
    return Ls
