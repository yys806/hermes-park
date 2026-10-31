"""日常事务地块 · 冬季积雪（Snow_*，默认隐藏，只在冬季显示）。只新增物件，不改已有几何。
做法：俯视射线高度场 —— 网格点向下打射线命中目标面得到 hz，遮挡物（灯具/灯泡串/传送带等）先被命中则该点不铺雪；
雪皮 z = hz + 厚度 × 离边距离的渐变，边界点下沉 droop（边缘圆润、檐口微垂），再做两遍平滑。"""
import bpy, bmesh, math
from mathutils import Vector, noise
from mathutils.bvhtree import BVHTree
import lib_daily as D
import lib_learn2 as L2
import lib_learn4 as L4

def objs(*prefixes):
    return [o for o in bpy.data.collections[D.COLL].all_objects
            if o.type == 'MESH' and D.base_name(o).startswith(prefixes)]

def bvh(obs):
    vs, ps = [], []
    for o in obs:
        mw = o.matrix_world; k = len(vs)
        vs += [mw @ v.co for v in o.data.vertices]
        ps += [[k + i for i in p.vertices] for p in o.data.polygons]
    return BVHTree.FromPolygons(vs, ps) if ps else None

def snowfield(name, rect, cell, targets, blockers=(), thick=lambda x, y, z: 0.04, hole=None,
              zmin=-1.0, droop=0.02, ramp=2, smooth=2, minnz=0.3, spread=0.0):
    """spread>0：每点再在 ±spread 十字上补打 4 根射线取最高命中（雪跨过木板缝/砖缝，不掉进缝里）。"""
    tb, bb = bvh(targets), bvh(blockers)
    offs = [(0, 0)] + ([(spread, 0), (-spread, 0), (0, spread), (0, -spread)] if spread else [])
    def top(x, y):
        hs = [h for h in (tb.ray_cast(Vector((x + a, y + b, 30.0)), Vector((0, 0, -1))) for a, b in offs) if h[0] is not None]
        return max(hs, key=lambda h: h[0].z) if hs else (None, None)
    x0, x1, y0, y1 = rect
    nx, ny = max(1, round((x1 - x0) / cell)), max(1, round((y1 - y0) / cell))
    X = lambda i: x0 + (x1 - x0) * i / nx; Y = lambda j: y0 + (y1 - y0) * j / ny
    dn = Vector((0, 0, -1)); H = {}
    for i in range(nx + 1):
        for j in range(ny + 1):
            x, y = X(i), Y(j); p = Vector((x, y, 30.0))
            h = top(x, y)
            if h[0] is None or h[0].z < zmin or h[1].z < minnz: continue
            if bb:
                b = bb.ray_cast(p, dn)
                if b[0] is not None and b[0].z > h[0].z - 0.01: continue
            if hole and hole(x, y): continue
            H[i, j] = h[0].z
    nb = lambda i, j: ((i + 1, j), (i - 1, j), (i, j + 1), (i, j - 1))
    dist = {k: 0 for k in H if any(n not in H for n in nb(*k))}   # 离边界的格数（BFS）
    front = list(dist)
    while front:
        nxt = []
        for k in front:
            for n in nb(*k):
                if n in H and n not in dist: dist[n] = dist[k] + 1; nxt.append(n)
        front = nxt
    Z = {}
    for k, hz in H.items():
        d = dist.get(k, ramp)
        Z[k] = hz - droop if d == 0 else hz + thick(X(k[0]), Y(k[1]), hz) * math.sqrt(min(1.0, d / ramp))
    for _ in range(smooth):
        Z = {k: (z if dist.get(k, 9) == 0 else
                 0.5 * z + 0.5 * sum(Z.get(n, z) for n in nb(*k)) / 4) for k, z in Z.items()}
    bm = bmesh.new(); V = {}
    def vert(k):
        if k not in V: V[k] = bm.verts.new((X(k[0]), Y(k[1]), Z[k]))
        return V[k]
    for i in range(nx):
        for j in range(ny):
            q = ((i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1))
            if all(k in Z for k in q): bm.faces.new([vert(k) for k in q])
    return to_obj(name, bm)

def to_obj(name, bm):
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    me.polygons.foreach_set('use_smooth', [True] * len(me.polygons))
    me.materials.append(D.M('snow'))
    o = bpy.data.objects.new(name, me); bpy.data.collections[D.SEASON].objects.link(o)
    return o

def finalize(o):
    """季节物件约定：Daily_Seasonal 集合、extras.default_visible=False、默认隐藏，带 AO 层。"""
    o['default_visible'] = False
    import lib_learn5 as L5; L5.ensure_ao(o)
    o.hide_render = True; o.hide_set(True)
    return o

def join(parts, name):
    o = L2.join(parts, name)
    for c in o.users_collection: c.objects.unlink(o)
    bpy.data.collections[D.SEASON].objects.link(o)
    return o

# ───────── 地面：铺装 / 草地 / 橡胶垫 / 木地板，留出踩出来的小路 ─────────
TRAILS = [
    [(-1.05, -7.95), (-1.0, -5.5), (-1.1, -3.4), (-1.05, -2.2)],          # 主路两侧（中线是 Belt_Main）
    [(1.05, -7.95), (1.1, -5.6), (1.0, -3.5), (1.05, -2.2)],
    [(-1.05, -2.2), (-2.6, -1.4), (-3.7, 0.2), (-5.6, 1.5), (-6.65, 2.45)],  # → 书店门
    [(1.05, -2.2), (2.6, -1.4), (3.8, 0.3), (5.0, 1.5), (5.1, 2.45)],        # → 影院门
    [(1.05, -4.7), (2.6, -4.75), (4.3, -4.7)],                               # → 超市门
    [(-1.05, -4.95), (-2.6, -4.9), (-3.7, -4.6)],                            # → 健身角
]

def trail_dist(x, y):
    p = Vector((x, y)); best = 9.0
    for line in TRAILS:
        for a, b in zip(line, line[1:]):
            a, b = Vector(a), Vector(b); ab = b - a
            t = max(0.0, min(1.0, (p - a).dot(ab) / ab.length_squared))
            best = min(best, (a + ab * t - p).length)
    return best

def trail_hw(x, y):
    return 0.2 + 0.05 * noise.noise(Vector((x * 2.3, y * 2.3, 0.7)))

def build_ground_snow(cell=0.1):
    tg = objs('Ground_grass', 'Ground_paving', 'Ground_mat', 'Ground_woodpath')
    bl = [o for o in bpy.data.collections[D.COLL].all_objects if o.type == 'MESH'
          and not D.base_name(o).startswith(('Ground_', 'Foliage_', 'Bare_', 'Snow_', 'CommonTree', 'Bush'))
          and D.SEASON not in [c.name for c in o.users_collection]]
    def th(x, y, z):
        d = trail_dist(x, y); hw = trail_hw(x, y)
        return 0.035 + 0.012 * noise.noise(Vector((x * 0.8, y * 0.8, 1.3))) + 0.03 * math.exp(-((d - hw) / 0.14) ** 2)
    o = snowfield('Snow_ground', (-7.85, 7.85, -7.85, 7.85), cell, tg, bl, th,
                  hole=lambda x, y: trail_dist(x, y) < trail_hw(x, y), droop=0.015, ramp=2, spread=0.04)
    return finalize(o)

# ───────── 屋顶 ─────────
def build_roof_snow():
    blk = objs('LGT_daily_', 'Cinema_bulbs', 'Cinema_dark')
    out = []
    bk = lambda x, y, z: 0.05 + 0.09 * max(0.0, 1 - abs(y - 4.6) / 2.4) + 0.01 * noise.noise(Vector((x * 1.5, y * 1.5, 0)))
    out.append(snowfield('Snow_roof_bookstore', (-7.85, -2.15, 2.15, 7.05), 0.07,
                         objs('Bookstore_roof', 'Bookstore_roof2', 'Bookstore_cream'), blk, bk, zmin=2.9, droop=0.04))
    blanket = lambda x, y, z: (0.08 + 0.035 * noise.noise(Vector((x * 0.9, y * 0.9, 2.1)))
                               + 0.015 * noise.noise(Vector((x * 3.1, y * 3.1, 4.2))))
    out.append(snowfield('Snow_roof_cinema', (2.35, 7.65, 2.35, 7.05), 0.08,
                         objs('Cinema_cinema', 'Cinema_cinema_dark', 'Cinema_stone', 'Cinema_trim', 'Cinema_metal', 'Cinema_brass'),
                         blk, blanket, zmin=3.7, droop=0.035))
    sm = lambda x, y, z: 0.045 if z < 3.5 else blanket(x, y, z) * 0.9      # 遮阳篷薄一点
    out.append(snowfield('Snow_roof_supermarket', (3.25, 7.7, -6.65, -2.8), 0.07,
                         objs('Supermarket_white', 'Supermarket_stone', 'Supermarket_tile_grout', 'Supermarket_cream',
                              'Supermarket_awning', 'Supermarket_awning2'), blk, sm, zmin=2.55, droop=0.03))
    return [finalize(o) for o in out]

# ───────── 朝上的小件：石凳、货箱、购物车、跑步机扶手 ─────────
def build_props_snow():
    blk = objs('LGT_daily_')
    parts = []
    for n, x in (('Stool_1', -1.9), ('Stool_2', 1.9)):
        dome = lambda px, py, z, x=x: 0.03 + 0.045 * max(0.0, 1 - math.hypot(px - x, py - 0.95) / 0.26)
        parts.append(snowfield('sp', (x - 0.3, x + 0.3, 0.65, 1.25), 0.02, objs(n), blk, dome, zmin=0.4, droop=0.012, ramp=3))
    parts.append(snowfield('sp', (2.94, 4.54, -3.93, -3.06), 0.025, objs('Props_crate_'), blk,
                           lambda x, y, z: 0.035, zmin=0.3, droop=0.01))
    parts.append(snowfield('sp', (3.5, 4.22, -6.32, -5.38), 0.015, objs('Supermarket_metal'), blk,
                           lambda x, y, z: 0.03, zmin=0.45, droop=0.008, ramp=1, smooth=1))
    parts.append(snowfield('sp', (-7.05, -4.05, -6.45, -4.25), 0.015, objs('Treadmill_'), blk,
                           lambda x, y, z: 0.025, zmin=0.95, droop=0.008, ramp=1, smooth=1))
    parts = [p for p in parts if len(p.data.polygons)]
    return finalize(join(parts, 'Snow_props'))

# ───────── 南篱笆：上横档一条雪 + 竖板/方柱球头小雪帽 ─────────
def build_fence_snow():
    m = D.M('snow'); P = []; y = -7.72
    for xa, xb in ((-7.85, -1.85), (1.85, 7.85)):
        n = int((xb - xa) / 0.08); zc = 0.615 + 0.004
        pts = [(xa + 0.02 + (xb - xa - 0.04) * k / n, y + 0.035, zc) for k in range(n + 1)]
        rr = [0.026 + 0.006 * noise.noise(Vector((p[0] * 3.0, 0.5, 0.5))) for p in pts]
        rr[0] = rr[-1] = 0.012
        t = L4.tube('sf', pts, rr, m, segs=10)
        for v in t.data.vertices:
            v.co.z = zc + (v.co.z - zc) * (0.55 if v.co.z > zc else 0.25)
        P.append(t)
        L_ = xb - xa; k_n = int(L_ / 0.16)
        for k in range(k_n + 1):
            x = xa + k * L_ / k_n
            if k % 8 == 0 or k == k_n: P.append(cap((x, y, 0.91), (0.052, 0.052, 0.022), m))
            else: P.append(cap((x, y - 0.01, 0.68), (0.034, 0.022, 0.013), m))
    return finalize(join(P, 'Snow_fence'))

def cap(c, s, m):
    """低面数小雪帽（10×5 UV 球压扁），控制面数。"""
    from mathutils import Matrix
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=10, v_segments=5, radius=1.0,
                              matrix=Matrix.Translation(c) @ Matrix.Diagonal((*s, 1)))
    o = to_obj('sf', bm); o.data.materials[0] = m
    return o
