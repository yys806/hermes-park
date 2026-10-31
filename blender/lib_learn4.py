"""学习科研地块 第4轮：细节密度零件库（分叉树、菜花树冠、窗、台阶、门、细节传送带）。Blender 4.5
依赖 lib_learn2 的 rbox/rcyl/ball/join/port 和 driver_namespace['L2P'] 材质表。"""
import bpy, bmesh, math, random
from mathutils import Vector, Matrix, noise
import lib_building as lb
import lib_learn2 as L

R, CY, BL = L.rbox, L.rcyl, L.ball
G = 0.06

def P():
    return bpy.app.driver_namespace['L2P']

def mat(name, hexcol, **kw):
    p = P()
    if name not in p:
        p[name] = L.C(name, hexcol, **kw)
    return p[name]

# ───────── 通用：沿折线扫掠的圆管（树干/树枝/弯头管） ─────────
def tube(name, pts, radii, m, segs=10, cap=True):
    pts = [Vector(p) for p in pts]
    bm = bmesh.new()
    rings = []
    for i, p in enumerate(pts):
        t = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
        a = Vector((0, 0, 1)) if abs(t.z) < 0.95 else Vector((1, 0, 0))
        u = t.cross(a).normalized(); v = t.cross(u).normalized()
        ring = [bm.verts.new(p + (u * math.cos(k / segs * math.tau) + v * math.sin(k / segs * math.tau)) * radii[i])
                for k in range(segs)]
        rings.append(ring)
    for a_, b_ in zip(rings, rings[1:]):
        for k in range(segs):
            bm.faces.new((a_[k], a_[(k + 1) % segs], b_[(k + 1) % segs], b_[k]))
    if cap:
        bm.faces.new(list(reversed(rings[0])))
        bm.faces.new(rings[-1])
    o = lb.new_obj(name)
    bm.normal_update(); bm.to_mesh(o.data); bm.free()
    o.data.polygons.foreach_set('use_smooth', [True] * len(o.data.polygons))
    o.data.materials.append(m)
    return o

def bez(p0, p1, p2, n=6):
    """二次贝塞尔采样点（树枝弯曲用）。"""
    p0, p1, p2 = Vector(p0), Vector(p1), Vector(p2)
    return [(1 - t) ** 2 * p0 + 2 * (1 - t) * t * p1 + t * t * p2 for t in (i / (n - 1) for i in range(n))]

# ───────── 菜花团块：一个凹凸大团 + 一圈咬合小鼓包 ─────────
def cauli(bm, c, r, rnd, bumps=9, squash=0.82):
    c = Vector(c)
    m = Matrix.Translation(c) @ Matrix.Diagonal((r, r, r * squash, 1))
    res = bmesh.ops.create_icosphere(bm, subdivisions=3, radius=1.0, matrix=m)
    off = Vector((rnd.random() * 50, rnd.random() * 50, rnd.random() * 50))
    for v in res['verts']:
        d = (v.co - c)
        n = noise.noise(d / r * 1.6 + off)
        v.co = c + d * (1 + 0.09 * n)
    for i in range(bumps):
        th = rnd.uniform(0, math.tau); ph = rnd.uniform(0.15, 1.25)
        dirv = Vector((math.cos(th) * math.sin(ph), math.sin(th) * math.sin(ph), math.cos(ph) * squash))
        br = r * rnd.uniform(0.32, 0.48)
        p = c + dirv * r * 0.78
        mm = Matrix.Translation(p) @ Matrix.Diagonal((br, br, br * 0.85, 1))
        bmesh.ops.create_icosphere(bm, subdivisions=2, radius=1.0, matrix=mm)

def blob_obj(name, clusters, m, seed):
    """clusters: [(center, r, bumps)] → 一个对象。"""
    rnd = random.Random(seed)
    bm = bmesh.new()
    for c, r, nb in clusters:
        cauli(bm, c, r, rnd, nb)
    o = lb.new_obj(name)
    bm.to_mesh(o.data); bm.free()
    o.data.polygons.foreach_set('use_smooth', [True] * len(o.data.polygons))
    o.data.materials.append(m)
    return o

def two_tone(o, m_dark, zcut=-0.25):
    """背阴面（法线朝下）换深色材质槽。"""
    o.data.materials.append(m_dark)
    for p in o.data.polygons:
        if p.normal.z < zcut:
            p.material_index = 1

def vc_material(name, hexcol, sss=0.2):
    """叶子材质：Base Color = 顶点色(Col) × 叶色；glTF 导出 COLOR_0，three.js 开 vertexColors 即可。"""
    nm = 'L2_' + name
    m = bpy.data.materials.get(nm)
    if m:
        return m
    m = L.C(name, hexcol, sss=sss)
    nt = m.node_tree
    b = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    at = nt.nodes.new('ShaderNodeVertexColor'); at.layer_name = 'Col'
    mx = nt.nodes.new('ShaderNodeMix'); mx.data_type = 'RGBA'; mx.blend_type = 'MULTIPLY'
    mx.inputs['Factor'].default_value = 1.0
    mx.inputs[6].default_value = b.inputs['Base Color'].default_value[:]
    nt.links.new(at.outputs['Color'], mx.inputs[7])
    nt.links.new(mx.outputs[2], b.inputs['Base Color'])
    return m

def shade_vc(o, cc, cr, lo=0.62, hi=1.12):
    """顶点色明暗：朝上/偏高的向阳面亮，朝下/偏低的背阴面暗，平滑过渡。"""
    me = o.data
    ca = me.color_attributes.get('Col') or me.color_attributes.new('Col', 'BYTE_COLOR', 'POINT')
    me.calc_loop_triangles()
    for v in me.vertices:
        hz = (v.co.z - cc.z) / (cr * 1.4)
        t = max(0.0, min(1.0, 0.5 + 0.35 * v.normal.z + 0.35 * hz + 0.1 * noise.noise(v.co * 2.0)))
        k = lo + (hi - lo) * t
        ca.data[v.index].color = (min(1, k), min(1, k * 1.0), min(1, k * (0.92 + 0.08 * t)), 1)
    o.data.materials.clear()
    o.data.materials.append(vc_material('leaf_vc', '#93C865'))

def tree4(nm, x, y, h=3.2, cr=0.9, seed=0, z0=0.12):
    """分叉树：Trunk_（主干+根部外扩+2~3主枝+细枝）、Foliage_（6~8菜花团+探出小叶团，双色）、Bare_（冬季细枝）。"""
    p = P(); rnd = random.Random(seed)
    tm = p['trunk']; lm = p['leaf']; ld = mat('leaf_shade', '#5E9E48', sss=0.2); ll = mat('leaf_sun', '#A3D46E', sss=0.2)
    base = Vector((x, y, z0)); parts = []
    lean = Vector((rnd.uniform(-0.08, 0.08), rnd.uniform(-0.08, 0.08), 0))
    top = base + Vector((0, 0, h * 0.4)) + lean
    parts.append(tube('tr_main', bez(base, base + Vector((0, 0, h * 0.25)), top, 7), [0.17, 0.15, 0.135, 0.125, 0.115, 0.11, 0.1], tm, 12))
    for i in range(5):   # 根部外扩
        a = i / 5 * math.tau + rnd.uniform(-0.3, 0.3)
        d = Vector((math.cos(a), math.sin(a), 0))
        parts.append(tube('tr_root', bez(base + Vector((0, 0, 0.32)), base + d * 0.12 + Vector((0, 0, 0.06)), base + d * rnd.uniform(0.32, 0.42) + Vector((0, 0, -0.02)), 5),
                          [0.08, 0.075, 0.06, 0.045, 0.03], tm, 8))
    cc = top + Vector((0, 0, cr * 0.75))          # 树冠中心
    nb = rnd.choice((2, 3)); tips = []
    cl = [(cc + Vector((0, 0, cr * 0.42)), cr * 0.58, 12)]   # 顶团
    ring = rnd.randint(5, 6)
    for i in range(ring):                           # 一圈高低错落的侧团
        a = i / ring * math.tau + rnd.uniform(-0.25, 0.25)
        d = Vector((math.cos(a), math.sin(a), 0))
        cl.append((cc + d * cr * rnd.uniform(0.5, 0.62) + Vector((0, 0, rnd.uniform(-0.25, 0.2) * cr)),
                   cr * rnd.uniform(0.42, 0.55), 9))
    cl.append((cc + Vector((rnd.uniform(-0.2, 0.2), rnd.uniform(-0.2, 0.2), -cr * 0.3)), cr * 0.5, 8))  # 底团
    for i in range(nb):   # 主枝伸向侧团中心
        c, r_, _ = cl[1 + i * (ring // nb)]
        tip = c.lerp(cc, 0.25)
        parts.append(tube('tr_br', bez(top - Vector((0, 0, 0.12)), top.lerp(tip, 0.4) + Vector((0, 0, 0.12)), tip, 6),
                          [0.105, 0.09, 0.075, 0.062, 0.05, 0.04], tm, 10))
        tips.append(tip)
        mid = top.lerp(tip, 0.5)
        for s in (-1, 1):   # 细枝
            a2 = math.atan2((tip - top).y, (tip - top).x) + s * 0.8
            t2 = mid + Vector((math.cos(a2), math.sin(a2), 0)) * cr * 0.45 + Vector((0, 0, cr * 0.35))
            parts.append(tube('tr_tw', bez(mid, mid + Vector((0, 0, 0.12)), t2, 4), [0.045, 0.036, 0.028, 0.02], tm, 8))
            tips.append(t2)
    trunk = L.join(parts, 'Trunk_' + nm)
    fol = blob_obj('Foliage_' + nm, cl, ll, seed)
    shade_vc(fol, cc, cr)
    # 探出的小叶团（贴在树冠外缘）
    tuft = []
    for i in range(4):
        a = rnd.uniform(0, math.tau)
        tuft.append((cc + Vector((math.cos(a) * cr * 1.02, math.sin(a) * cr * 1.02, rnd.uniform(-0.45, 0.1) * cr)), cr * 0.2, 5))
    tf = blob_obj('Foliage_tuft_' + nm, tuft, ll, seed + 5)
    shade_vc(tf, cc, cr)
    # 冬季细枝（Bare_）：从各枝端再长出 3 根小杈
    bp = []
    for t in tips:
        for k in range(3):
            a = rnd.uniform(0, math.tau)
            e = t + Vector((math.cos(a) * 0.35, math.sin(a) * 0.35, rnd.uniform(0.2, 0.45)))
            bp.append(tube('bt', [t, t.lerp(e, 0.5) + Vector((0, 0, 0.05)), e], [0.03, 0.02, 0.01], tm, 6))
    bare = L.join(bp, 'Bare_' + nm)
    return trunk, fol, tf, bare

def planter(nm, x, y, r, seed=0):
    """圆形树池：石砌收边环 + 草皮 + 草簇 + 小白花。返回 (Ground_ 部件, Foliage_ 草花部件)。"""
    p = P(); rnd = random.Random(seed)
    ring = [tube('pl_curb', [(x + math.cos(k / 48 * math.tau) * r, y + math.sin(k / 48 * math.tau) * r, 0.14) for k in range(49)],
                 [0.08] * 49, p['stone'], 10, cap=False)]
    ring.append(CY('pl_soil', r - 0.02, 0.12, (x, y, 0.1), p['grass'], r=0.03, verts=48))
    fl = []
    for i in range(int(r * 14)):
        a = rnd.uniform(0, math.tau); d = rnd.uniform(0.15, r - 0.15)
        px, py = x + math.cos(a) * d, y + math.sin(a) * d
        if i % 3 == 0:
            fl.append(BL('pl_fw', 0.035, (px, py, 0.2), p['white']))
            fl.append(BL('pl_fy', 0.015, (px, py, 0.225), p['book3']))
        else:
            for k in range(3):
                b = a + k * 2.1
                fl.append(L.rcyl('pl_gb', 0.025, 0.12, (px + math.cos(b) * 0.03, py + math.sin(b) * 0.03, 0.22), p['bush'], r=0.01, verts=6))
    return ring, fl

# ───────── 窗：窗套 + 窗框 + 窗棂分格 + 分格玻璃(两色) + 外挑窗台 + 窗楣 ─────────
def window(nm, c, w, h, facing, cols=2, rows=2, frame_m=None, glass=None, glass2=None, trim=None,
           sill=True, lintel=True, curtain=None, depth=0.1):
    """c=窗洞中心(墙面上)，facing 'S','N','E','W' 为窗朝向。返回零件列表（已在世界坐标）。"""
    rz = {'S': 0, 'N': math.pi, 'E': math.pi / 2, 'W': -math.pi / 2}[facing]
    parts = []
    fb = 0.06  # 框宽
    def add(o):
        parts.append(o); return o
    # 局部坐标：x 沿墙，-y 朝外，z 向上；墙面在 y=0
    for sx in (-1, 1):   # 窗套：四根外框条（不挡玻璃）
        add(R(nm + '_surv', (0.11, 0.05, h + 0.22), (sx * (w / 2 + 0.055), -0.015, 0), trim, r=0.02))
    for sz in (-1, 1):
        add(R(nm + '_surh', (w, 0.05, 0.11), (0, -0.015, sz * (h / 2 + 0.055)), trim, r=0.02))
    for sx in (-1, 1):
        add(R(nm + '_fv', (fb, depth, h), (sx * (w / 2 - fb / 2), 0.0, 0), frame_m, r=0.02))
    for sz in (-1, 1):
        add(R(nm + '_fh', (w, depth, fb), (0, 0.0, sz * (h / 2 - fb / 2)), frame_m, r=0.02))
    iw, ih = w - 2 * fb, h - 2 * fb
    for i in range(1, cols):
        add(R(nm + '_mv', (0.035, depth * 0.8, ih), (-iw / 2 + iw * i / cols, 0.0, 0), frame_m, r=0.012))
    for j in range(1, rows):
        add(R(nm + '_mh', (iw, depth * 0.8, 0.035), (0, 0.0, -ih / 2 + ih * j / rows), frame_m, r=0.012))
    k = 0
    for i in range(cols):
        for j in range(rows):
            gx = -iw / 2 + iw * (i + 0.5) / cols; gz = -ih / 2 + ih * (j + 0.5) / rows
            add(R(nm + '_pane', (iw / cols - 0.03, 0.02, ih / rows - 0.03), (gx, 0.03, gz),
                  glass if (i + j) % 2 == 0 or glass2 is None else glass2, r=0.008, seg=1))
            k += 1
    if curtain is not None:
        for sx in (-1, 1):
            add(R(nm + '_curt', (iw * 0.18, 0.03, ih * 0.9), (sx * (iw / 2 - iw * 0.09), 0.07, 0.0), curtain, r=0.02))
    if sill:
        add(R(nm + '_sill', (w + 0.26, 0.2, 0.07), (0, -0.08, -h / 2 - 0.06), trim, r=0.025))
        add(R(nm + '_sillb', (w + 0.1, 0.06, 0.05), (0, -0.03, -h / 2 - 0.115), trim, r=0.015))
    if lintel:
        add(R(nm + '_lintel', (w + 0.3, 0.1, 0.09), (0, -0.04, h / 2 + 0.14), trim, r=0.03))
    return place(parts, c, rz)

def place(parts, c, rz):
    """局部→世界：用 matrix_basis（matrix_world 在 view_layer.update 前是旧值）。"""
    M = Matrix.Translation(Vector(c)) @ Matrix.Rotation(rz, 4, 'Z')
    for o in parts:
        o.matrix_basis = M @ o.matrix_basis
    return parts

# ───────── 台阶：n 级 + 侧板 + 踏面前缘倒圆 + 可选扶手 ─────────
def steps(nm, c, w, n, rise, run, facing, m, cheek_m=None, rail_m=None):
    rz = {'S': 0, 'N': math.pi, 'E': math.pi / 2, 'W': -math.pi / 2}[facing]
    parts = []
    for k in range(1, n + 1):
        top = G + rise * k
        d = run * (n - k + 1)
        parts.append(R(nm + '_st', (w, d, rise * k), (0, -d / 2, G + rise * k / 2), m, r=0.035))
        parts.append(CY(nm + '_nose', 0.03, w - 0.06, (0, -d + 0.03, top - 0.025), m, r=0.0, verts=12, rot=(0, math.pi / 2, 0)))
    if cheek_m:
        for sx in (-1, 1):
            parts.append(R(nm + '_cheek', (0.12, run * n + 0.05, rise * n + 0.06), (sx * (w / 2 + 0.06), -run * n / 2, G + (rise * n + 0.06) / 2), cheek_m, r=0.04))
    if rail_m:
        for sx in (-1, 1):
            for k in (0.25, n * run - 0.12):
                parts.append(CY(nm + '_rp', 0.025, 0.85, (sx * (w / 2 + 0.06), -k, G + rise * n + 0.42), rail_m, r=0.01, verts=10))
            ln = n * run - 0.37 + 0.1
            parts.append(CY(nm + '_rr', 0.03, ln, (sx * (w / 2 + 0.06), -(0.25 + n * run - 0.12) / 2, G + rise * n + 0.86), rail_m, r=0.012, verts=10, rot=(math.pi / 2, 0, 0)))
    return place(parts, c, rz)

# ───────── 门：门框 + 分块门板 + 把手座 + 门槛 + 脚垫 ─────────
def door(nm, c, w, h, facing, leaf_m, frame_m, metal_m, mat_m=None, leaves=1, glass=None, panels=(2, 1)):
    rz = {'S': 0, 'N': math.pi, 'E': math.pi / 2, 'W': -math.pi / 2}[facing]
    parts = []
    lw = w / leaves
    for k in range(leaves):
        x0 = -w / 2 + lw * (k + 0.5)
        parts.append(R(nm + '_leaf', (lw - 0.03, 0.06, h - 0.03), (x0, 0.0, h / 2), leaf_m, r=0.025))
        pr, pc = panels
        for i in range(pr):
            pz = h * (0.3 + 0.42 * i) if pr == 2 else h * 0.5
            ph = h * 0.32
            if glass is not None and i == pr - 1:
                parts.append(R(nm + '_gl', (lw * 0.62, 0.03, ph), (x0, -0.03, pz), glass, r=0.015))
                parts.append(R(nm + '_glf', (lw * 0.7, 0.035, ph + 0.07), (x0, -0.02, pz), frame_m, r=0.02))
            else:
                parts.append(R(nm + '_pan', (lw * 0.62, 0.04, ph), (x0, -0.035, pz), leaf_m, r=0.03))
        hx = x0 + (lw / 2 - 0.12) * (-1 if (leaves == 2 and k == 1) else 1)
        parts.append(R(nm + '_rose', (0.06, 0.03, 0.2), (hx, -0.04, h * 0.47), metal_m, r=0.015))
        parts.append(CY(nm + '_knob', 0.022, 0.12, (hx, -0.08, h * 0.47 + 0.04), metal_m, r=0.008, verts=10, rot=(0, math.pi / 2, 0)))
        parts.append(BL(nm + '_lock', 0.018, (hx, -0.06, h * 0.42), metal_m))
        for hz in (0.15, 0.85):
            parts.append(CY(nm + '_hinge', 0.025, 0.12, (x0 - (lw / 2 - 0.03) * (-1 if (leaves == 2 and k == 1) else 1), -0.03, h * hz), metal_m, r=0.006, verts=10))
    for sx in (-1, 1):
        parts.append(R(nm + '_jamb', (0.1, 0.14, h + 0.1), (sx * (w / 2 + 0.05), -0.02, (h + 0.1) / 2), frame_m, r=0.03))
    parts.append(R(nm + '_head', (w + 0.3, 0.16, 0.12), (0, -0.03, h + 0.1), frame_m, r=0.04))
    parts.append(R(nm + '_sill', (w + 0.24, 0.2, 0.04), (0, -0.06, 0.02), frame_m, r=0.015))
    if mat_m is not None:
        parts.append(R(nm + '_mat', (w * 0.9, 0.55, 0.025), (0, -0.55, -0.0), mat_m, r=0.012))
    return place(parts, c, rz)
