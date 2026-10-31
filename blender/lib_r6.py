"""第 6 轮：后院与外围建筑构件（院墙段、篱笆、单坡顶、攒尖顶、廊桥、栏杆）。依赖 lib_building / lib_house。"""
import bpy, bmesh, math
from mathutils import Vector
from lib_building import box, cyl, panel, mat, array_offset, new_obj
from lib_house import mats as _house_mats

def mats():
    """项目材质表 + 本轮新增（全部哑光）。"""
    M = _house_mats()
    M.update(soil=mat('Soil', '#6b4a33', 0.95), path=mat('Path_Stone', '#9d978c', 0.93),
             joint=mat('Paving_Joint', '#7d786f', 0.93), grass=mat('Grass', '#7aa35a', 0.95),
             fence=mat('Wood_Fence', '#9a6a42', 0.92), water=mat('Water_Pond', '#7fb7b5', 0.88),
             pondbed=mat('Pond_Bed', '#4f7d7c', 0.92), thatch=mat('Roof_Thatch', '#b89462', 0.95))
    return M

def use_coll(name):
    """新建/切换到场景下的集合，后续 box/cyl 都建在这里。"""
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(c)
    lc = bpy.context.view_layer.layer_collection.children[name]
    bpy.context.view_layer.active_layer_collection = lc
    return c

def wall_run(nm, a, b, M, z0=0.5, h=4.5, t=0.5):
    """与现有院墙同规格的一段墙：石勒脚 + 红墙身 + 压顶 + 青瓦墙帽。a,b 为墙中线两端 (x,y)，须沿 X 或 Y。"""
    a, b = Vector((*a, 0)), Vector((*b, 0))
    L = (b - a).length
    c = (a + b) / 2
    rz = 0 if abs(b.x - a.x) > abs(b.y - a.y) else math.pi / 2
    out = [box(nm + '_plinth', (L, t + 0.08, 0.45), (c.x, c.y, z0 + 0.225), (0, 0, rz), M['stone'], bevel=0.03),
           box(nm, (L, t, h), (c.x, c.y, z0 + h / 2), (0, 0, rz), M['brick'], bevel=0.02),
           box(nm + '_coping', (L, t + 0.12, 0.12), (c.x, c.y, z0 + h + 0.06), (0, 0, rz), M['ridge'], bevel=0.02)]
    zt = z0 + h + 0.12
    for s in (1, -1):   # 两坡墙帽
        off = Vector((-math.sin(rz), math.cos(rz), 0)) * s
        p, e = c + off * 0.25, c + off * 0.47
        out.append(box(f'{nm}_cap_slope{"AB"[s < 0]}', (L + 0.1, 0.58, 0.07), (p.x, p.y, zt + 0.11),
                       (-s * 0.67, 0, rz), M['tile'], bevel=0.015))
        out.append(box(f'{nm}_cap_eave{"AB"[s < 0]}', (L + 0.1, 0.12, 0.12), (e.x, e.y, zt - 0.01), (0, 0, rz), M['ridge'], bevel=0.02))
    out.append(box(nm + '_cap_ridge', (L + 0.2, 0.19, 0.14), (c.x, c.y, zt + 0.3), (0, 0, rz), M['ridge'], bevel=0.03))
    return out

def fence_run(nm, a, b, M, h=1.2, step=0.22, mat_key='fence', post_step=2.0):
    """木篱笆：立柱 + 上下横档 + 尖头竖板阵列。a,b 为 (x,y)。"""
    a, b = Vector((*a, 0)), Vector((*b, 0))
    d = b - a
    L = d.length
    rz = math.atan2(d.y, d.x)
    c = (a + b) / 2
    m = M[mat_key]
    out = []
    np_ = max(1, round(L / post_step))
    for i in range(np_ + 1):
        p = a + d * (i / np_)
        out.append(box(f'{nm}_post{i}', (0.14, 0.14, h + 0.2), (p.x, p.y, (h + 0.2) / 2), (0, 0, rz), M['wood'], bevel=0.02))
    for k, z in (('T', h * 0.78), ('B', h * 0.28)):
        out.append(box(f'{nm}_rail{k}', (L, 0.06, 0.09), (c.x, c.y, z), (0, 0, rz), m, bevel=0.01))
    n = max(1, int((L - 0.2) / step))
    u = d.normalized()
    p0 = a + u * ((L - (n - 1) * step) / 2)
    pk = box(nm + '_pickets', (0.12, 0.04, h), (p0.x, p0.y, h / 2), (0, 0, rz), m, bevel=0.015)
    array_offset(pk, n, (step, 0, 0))   # 局部 X = 篱笆方向
    out.append(pk)
    return out

def shed_roof(nm, cx, cy, lx, ly, z_lo, z_hi, M, down='-Y', t=0.12, rib_step=0.3, mat_key='tile'):
    """单坡顶：坡面 + 瓦垄 + 檐口封边。lx/ly 为水平投影尺寸，down 为低檐方向（'-Y','+Y','-X','+X'）。"""
    along_y = down in ('-Y', '+Y')
    run, span = (ly, lx) if along_y else (lx, ly)
    s = -1 if down[0] == '-' else 1
    a = math.atan2(z_hi - z_lo, run)
    L = math.hypot(run, z_hi - z_lo)
    zc = (z_lo + z_hi) / 2 + t / 2
    rot = (-s * a, 0, 0) if along_y else (0, s * a, 0)
    sz = (span, L, t) if along_y else (L, span, t)
    out = [box(nm + '_slope', sz, (cx, cy, zc), rot, M[mat_key], bevel=0.02)]
    if mat_key == 'tile':
        n = max(2, int((span - 0.2) / rib_step))
        off = (-(n - 1) * rib_step / 2, 0) if along_y else (0, -(n - 1) * rib_step / 2)
        nrm = Vector((0, -s * math.sin(a), math.cos(a))) if along_y else Vector((s * math.sin(a), 0, math.cos(a)))
        p = Vector((cx + off[0], cy + off[1], zc)) + nrm * (t / 2 + 0.03)
        rr = (math.pi / 2 - s * a, 0, 0) if along_y else (0, math.pi / 2 + s * a, 0)
        r = cyl(nm + '_rib', 0.055, L * 0.98, p, rr, M['ridge'], verts=6, bevel=0)
        array_offset(r, n, (0, 0, 0))
        _world_array(r, (rib_step, 0, 0) if along_y else (0, rib_step, 0))
        out.append(r)
    lo = (cx, cy + s * run / 2, z_lo + 0.02) if along_y else (cx + s * run / 2, cy, z_lo + 0.02)
    hi = (cx, cy - s * run / 2, z_hi + t) if along_y else (cx - s * run / 2, cy, z_hi + t)
    es = (span + 0.05, 0.14, 0.14) if along_y else (0.14, span + 0.05, 0.14)
    out.append(box(nm + '_eave', es, lo, material=M['ridge'], bevel=0.02))
    out.append(box(nm + '_top', es, hi, material=M['ridge'], bevel=0.02))
    return out

def _world_array(obj, vec):
    """Array 的常量偏移是局部坐标：把世界方向 vec 换算到对象局部。"""
    bpy.context.view_layer.update()
    loc = obj.matrix_world.to_3x3().inverted() @ Vector(vec)
    obj.modifiers['Array'].constant_offset_displace = loc

def tent_roof(nm, cx, cy, z_eave, r, h, M, sides=6, rot0=0.0):
    """攒尖顶：带出檐的多边锥面 + 檐口环 + 垂脊 + 宝顶。r 为檐口外接圆半径。"""
    bpy.ops.mesh.primitive_cone_add(vertices=sides, radius1=r, radius2=0.12, depth=h,
                                    location=(cx, cy, z_eave + h / 2), rotation=(0, 0, rot0))
    o = bpy.context.active_object
    o.name = o.data.name = nm + '_cone'
    o.data.materials.append(M['tile'])
    bv = o.modifiers.new('Bevel', 'BEVEL'); bv.width, bv.segments, bv.limit_method = 0.04, 2, 'ANGLE'
    out = [o]
    ring = cyl(nm + '_eaveRing', r * 1.0, 0.16, (cx, cy, z_eave + 0.02), (0, 0, rot0), M['ridge'], verts=sides, bevel=0.03)
    out.append(ring)
    bpy.context.view_layer.update()
    base = [o.matrix_world @ v.co for v in o.data.vertices if v.co.z < 0]
    for i, q in enumerate(base):   # 垂脊沿锥棱（取锥体底面实际顶点）
        ang = math.atan2(q.y - cy, q.x - cx)
        p = Vector((cx + math.cos(ang) * r / 2, cy + math.sin(ang) * r / 2, z_eave + h / 2 + 0.08))
        L = math.hypot(r, h)
        out.append(box(f'{nm}_hip{i}', (L, 0.16, 0.16), p, (0, math.atan2(h, r), ang), M['ridge'], bevel=0.04))
        out.append(box(f'{nm}_hipEnd{i}', (0.4, 0.2, 0.3), (cx + math.cos(ang) * (r - 0.05), cy + math.sin(ang) * (r - 0.05), z_eave + 0.28),
                       (0, -0.6, ang), M['ridge'], bevel=0.05))
    out.append(cyl(nm + '_finialBase', 0.28, 0.25, (cx, cy, z_eave + h + 0.05), material=M['ridge'], verts=12, bevel=0.04))
    from lib_building import sphere
    out.append(sphere(nm + '_finial', 0.26, (cx, cy, z_eave + h + 0.42), M['ridge'], 14, 10))
    return out

def _tube(nm, pts, r, m):
    """沿折线点的圆管（曲线倒角转网格），用于弧形垂脊、檐口。"""
    cu = bpy.data.curves.new(nm, 'CURVE'); cu.dimensions = '3D'
    cu.bevel_depth, cu.bevel_resolution, cu.use_fill_caps = r, 2, True
    sp = cu.splines.new('POLY'); sp.points.add(len(pts) - 1)
    for p, q in zip(sp.points, pts):
        p.co = (*q, 1)
    o = bpy.data.objects.new(nm, cu); bpy.context.collection.objects.link(o)
    o.data.materials.append(m)
    from lib_building import select_only
    select_only([o]); bpy.ops.object.convert(target='MESH')
    o = bpy.context.view_layer.objects.active
    o.data.polygons.foreach_set('use_smooth', [True] * len(o.data.polygons))
    return o

def tent_roof2(nm, cx, cy, z_eave, r, h, M, sides=6, rot0=0.0, step=0.3, amp=0.06,
               flare=0.38, push=0.3, rt=0.14, nu_per=6, nv=18, t=0.1):
    """攒尖顶（瓦垄版）：内凹坡面上直接起平行瓦垄，檐角起翘外伸，弧形垂脊、檐口圆管、宝顶。
    角点在 rot0 + 2πi/sides；r 为檐角外接圆半径（起翘前）。"""
    C = Vector((cx, cy, 0))
    cor = [Vector((cx + r * math.cos(rot0 + 2 * math.pi * i / sides), cy + r * math.sin(rot0 + 2 * math.pi * i / sides), 0)) for i in range(sides)]
    side = (cor[1] - cor[0]).length
    nu = max(8, int(side / step * nu_per))
    apex = Vector((cx, cy, z_eave + h))

    def surf(i, u, v, bump=True):
        E = cor[i].lerp(cor[(i + 1) % sides], u)
        d = E - C
        f = abs(2 * u - 1) ** 4 * (1 - v) ** 2.5
        H = C + d * (1 - v * (1 - rt / r)) + d.normalized() * push * f
        p = Vector((H.x, H.y, z_eave + h * v ** 1.5 + flare * f))
        if bump:
            x = (u - 0.5) * side * (1 - v)
            k = (0.5 + 0.5 * math.cos(2 * math.pi * x / step)) ** 1.5 * (1 - abs(2 * u - 1) ** 8)
            a, b = cor[i], cor[(i + 1) % sides]
            n = (b - a).cross(apex - a).normalized()
            p += n * amp * k
        return p

    bm = bmesh.new()
    for i in range(sides):
        g = [[bm.verts.new(surf(i, iu / nu, iv / nv)) for iu in range(nu + 1)] for iv in range(nv + 1)]
        for iv in range(nv):
            for iu in range(nu):
                bm.faces.new((g[iv][iu], g[iv][iu + 1], g[iv + 1][iu + 1], g[iv + 1][iu]))
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.004)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    o = new_obj(nm + '_tiles'); bm.to_mesh(o.data); bm.free()
    if o.data.polygons[0].normal.z < 0:
        for p in o.data.polygons: p.flip()
    o.data.polygons.foreach_set('use_smooth', [True] * len(o.data.polygons))
    o.data.materials.append(M['tile'])
    so = o.modifiers.new('Solidify', 'SOLIDIFY'); so.thickness, so.offset = t, -1
    out = [o]
    for i in range(sides):   # 垂脊：沿坡面角线，末端再翘出一截
        pts = [surf(i, 0, iv / nv, False) + Vector((0, 0, 0.1)) for iv in range(nv, -1, -1)]
        tip = pts[-1] + (pts[-1] - pts[-2]).normalized() * 0.3 + Vector((0, 0, 0.18))
        out.append(_tube(f'{nm}_hip{i}', pts + [tip], 0.09, M['ridge']))
    ev = [surf(i, iu / nu, 0, False) + Vector((0, 0, -0.02)) for i in range(sides) for iu in range(0, nu, 3)]
    out.append(_tube(nm + '_eave', ev + [ev[0]], 0.075, M['ridge']))
    out.append(cyl(nm + '_finialBase', 0.3, 0.22, (cx, cy, z_eave + h + 0.06), material=M['ridge'], verts=16, bevel=0.04))
    from lib_building import sphere
    out.append(sphere(nm + '_finialA', 0.24, (cx, cy, z_eave + h + 0.36), M['ridge'], 16, 10))
    s2 = sphere(nm + '_finialB', 0.15, (cx, cy, z_eave + h + 0.68), M['ridge'], 14, 8); out.append(s2)
    return out

def rail_run(nm, a, b, z, M, h=0.75, step=0.3, seat=False):
    """木栏杆：扶手 + 下枋 + 立条阵列；seat=True 时加一条坐凳板（美人靠简化）。"""
    a, b = Vector((*a, 0)), Vector((*b, 0))
    d = b - a; L = d.length; c = (a + b) / 2
    rz = math.atan2(d.y, d.x)
    out = [box(nm + '_top', (L, 0.1, 0.08), (c.x, c.y, z + h), (0, 0, rz), M['wood'], bevel=0.015),
           box(nm + '_bot', (L, 0.1, 0.08), (c.x, c.y, z + 0.08), (0, 0, rz), M['wood'], bevel=0.015)]
    n = max(1, int((L - 0.2) / step))
    u = d.normalized(); p0 = a + u * ((L - (n - 1) * step) / 2)
    bl = box(nm + '_bal', (0.05, 0.05, h - 0.1), (p0.x, p0.y, z + h / 2 + 0.04), (0, 0, rz), M['win'], bevel=0)
    array_offset(bl, n, (step, 0, 0)); out.append(bl)
    if seat:
        out.append(box(nm + '_seat', (L, 0.36, 0.08), (c.x, c.y, z + 0.45), (0, 0, rz), M['wood'], bevel=0.02))
    return out
