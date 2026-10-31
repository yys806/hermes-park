"""日常事务地块（第 8 栋）：独立场景 Daily，16×16 m，南入口。Blender 4.5
复用 lib_learn2（圆角体块/传送带/接口）、lib_learn5（黏土材质/资产导入/AO 烘焙）、lib_learn6（灯具网格工具）。
坐标：地块 x,y ∈ [-8, 8]，-Y 为南（正入口）。"""
import bpy, bmesh, math, random
from mathutils import Vector, Matrix
import lib_building as lb
import lib_learn2 as L2
import lib_learn5 as L5
import lib_learn6 as L6

SCENE = COLL = 'Daily'
SEASON = 'Daily_Seasonal'
G = 0.08          # 铺装面高度（草面 0.04）
TOP = 0.42        # 传送带面高度

# ───────── 场景 / 集合 ─────────
def scene():
    sc = bpy.data.scenes.get(SCENE) or bpy.data.scenes.new(SCENE)
    bpy.context.window.scene = sc
    return sc

def coll(name=COLL):
    sc = scene()
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
        (sc.collection if name == COLL else bpy.data.collections[COLL]).children.link(c)
    def find(lc):
        if lc.collection == c: return lc
        for ch in lc.children:
            r = find(ch)
            if r: return r
    bpy.context.view_layer.active_layer_collection = find(bpy.context.view_layer.layer_collection)
    return c

def base_name(o):
    """其它场景已占用同名对象时 Blender 会加 .001 后缀；导出时再换回干净名字。"""
    import re
    return re.sub(r'\.\d{3}$', '', o.name)

def get(name):
    return next((o for o in bpy.data.collections[COLL].all_objects if base_name(o) == name), None)

def ao_all():
    """所有 Daily 网格都要有 AO 层（材质里乘了 AO 顶点色，缺层会发黑）。"""
    n = 0
    for o in bpy.data.collections[COLL].all_objects:
        if o.type == 'MESH' and 'AO' not in o.data.color_attributes:
            L5.ensure_ao(o); n += 1
    return n

SEASON_PRE = ('Foliage_Autumn_', 'Bare_', 'Snow_')

def show_season(pre=None):
    """pre=None：绿（默认）；否则只显示该前缀的季节变体并隐藏 Foliage_ 绿植。"""
    for o in list(bpy.data.collections[COLL].all_objects):
        n = o.name
        if n.startswith(SEASON_PRE): vis = pre is not None and n.startswith(pre)
        elif n.startswith('Foliage_'): vis = pre is None
        else: continue
        o.hide_render = not vis; o.hide_set(not vis)

def bake_ao(objs, samples=48):
    """Cycles AO → 顶点色 AO 层（柔化 + 平滑 + 乘导入件的 TEX 贴图色）。objs 必须当前可见。"""
    sc = bpy.context.scene; old = sc.cycles.samples; sc.cycles.samples = samples
    objs = [o for o in objs if o.type == 'MESH' and o.visible_get()]
    try:
        L5.finish_ao(objs)
    finally:
        sc.cycles.samples = old
    for o in objs: o['ao_baked'] = True
    return len(objs)

def wipe(prefixes):
    """删掉 Daily 集合里指定前缀的对象（重建用），只动 Daily。"""
    for o in list(bpy.data.collections[COLL].all_objects):
        if o.name.startswith(prefixes):
            d = o.data; bpy.data.objects.remove(o, do_unlink=True)
            if d is not None and d.users == 0:
                (bpy.data.lights if isinstance(d, bpy.types.Light) else bpy.data.meshes).remove(d)

def setup_render():
    """照搬 Learn2 的灯光/世界/渲染设定（各自独立的数据块，不改 Learn2）。"""
    sc = scene(); src = bpy.data.scenes['Learn2']
    try: sc.render.engine = 'CYCLES'
    except TypeError as e: print(e)
    sc.cycles.samples = 96; sc.cycles.use_denoising = True
    sc.render.resolution_x, sc.render.resolution_y = 1400, 1000
    sc.view_settings.view_transform = src.view_settings.view_transform
    sc.view_settings.exposure = src.view_settings.exposure
    w = bpy.data.worlds.get('D_world') or src.world.copy(); w.name = 'D_world'; sc.world = w
    c = coll('Daily_Rig')
    for n in ('Key_soft', 'Fill_area', 'Top_area'):
        s = bpy.data.objects[n]; nm = 'Rig_' + n
        o = bpy.data.objects.get(nm)
        if o is None:
            o = bpy.data.objects.new(nm, s.data.copy()); c.objects.link(o)
        o.matrix_world = s.matrix_world.copy()
    coll()
    return sc

def cam(name, loc, rot_deg, ortho=None, lens=35):
    c = coll('Daily_Rig')
    o = bpy.data.objects.get(name)
    if o is None:
        o = bpy.data.objects.new(name, bpy.data.cameras.new(name)); c.objects.link(o)
    o.location = loc; o.rotation_euler = [math.radians(a) for a in rot_deg]
    if ortho: o.data.type = 'ORTHO'; o.data.ortho_scale = ortho
    else: o.data.type = 'PERSP'; o.data.lens = lens
    o.data.clip_end = 200
    coll()
    return o

# ───────── 材质 ─────────
PAL = {
    'base': '#B9AF9F', 'soil': '#9C8468', 'grass': '#8EC266', 'grass2': '#7DB159',
    'plaza': '#DAD7D1', 'grout': '#A9A49C', 'slate': '#5E636B', 'slate2': '#6E737B',
    'rubber': '#4F5B6C', 'rubber_line': '#7C8899', 'deck': '#CB9461', 'deck2': '#BC8654', 'wood_dark': '#8C5E40',
    'white': '#F3EFE7', 'cream': '#ECE2CC', 'roof': '#A8683F', 'roof2': '#93592F', 'trim': '#E4D8C2',
    'glass': '#BFDDE6', 'door_green': '#3F6B4E', 'sign': '#D8B27A',
    'cinema': '#4B5B72', 'cinema_dark': '#38424F', 'screen': '#F1ECDD', 'curtain': '#8E2E34',
    'board': '#2F3433', 'chalk': '#F2F1EA', 'tile': '#D2D6D8', 'tile_grout': '#AEB3B6',
    'awning': '#9CC9E4', 'awning2': '#F6F8F9', 'metal': '#B8BDC2', 'dark': '#4A4E55',
    'tm_body': '#4A4F58', 'tm_band': '#C7CACD', 'tm_line': '#A3A7AB', 'orange': '#EE8A3C', 'screen_dk': '#26303A',
    'red': '#D9604E', 'blue': '#5B8FD0', 'yellow': '#F0C95A', 'green': '#6DB27A', 'purple': '#9A7BC4', 'pink': '#E89AA8',
    'frame': '#CFC7BA', 'belt': '#5E6168', 'slit': '#3E4045', 'rail': '#ECE6DA', 'leg': '#8E9096',
    'port': '#D9D2C5', 'port_in': '#2F3236', 'bolt': '#B89A5C', 'hub': '#E4C69C', 'hub2': '#D2AF80',
    'lamp_post': '#474B52', 'stone': '#C9C4BB', 'fence': '#F4F2EE', 'snow': '#F1F5F9',
    'glass_side': '#A9CBD6', 'interior': '#6E5A4A', 'shelf': '#A87348', 'paper': '#F4EBD6', 'brass': '#C9A15A',
}
GLASSY = {'glass'}

def M(key):
    nm = 'D_' + key
    m = bpy.data.materials.get(nm)
    if m is None:
        m = L5.clay_nodes(bpy.data.materials.new(nm), L5.srgb(PAL[key]))
        b = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
        b.inputs['Roughness'].default_value = 0.92
        if key in GLASSY:
            b.inputs['Roughness'].default_value = 0.3; b.inputs['Subsurface Weight'].default_value = 0.0
            b.inputs['Alpha'].default_value = 0.3; m.surface_render_method = 'BLENDED'
            m.diffuse_color = (*m.diffuse_color[:3], 0.3)
    return m

def belt_mats():
    return {k: M(k) for k in ('frame', 'belt', 'slit', 'rail', 'leg', 'port', 'port_in', 'bolt')}

def lamp_mat(lid, hexcol='#FFE2A8', strength=6.0):
    nm = 'LGT_daily_' + lid
    m = bpy.data.materials.get(nm) or L5.clay_nodes(bpy.data.materials.new(nm), L5.srgb(hexcol))
    b = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    b.inputs['Emission Color'].default_value = L5.srgb(hexcol)
    b.inputs['Emission Strength'].default_value = strength
    b.inputs['Subsurface Weight'].default_value = 0.0
    m['lgt'] = True
    return m

# ───────── 小工具 ─────────
B = L2.rbox
def C(name, r, h, loc, m, verts=32, rr=0.03, rot=(0, 0, 0)):
    return L2.rcyl(name, r, h, loc, m, r=rr, verts=verts, rot=rot)

def tiles(nm, x0, x1, y0, y1, t, m, gap=0.03, h=0.05, z=G, r=0.012, jitter=0.0, seed=1, stagger=False):
    """一片独立圆角铺砖（顶面在 z）。返回对象列表。"""
    rnd = random.Random(seed); out = []
    nx, ny = max(1, round((x1 - x0) / t[0])), max(1, round((y1 - y0) / t[1]))
    sx, sy = (x1 - x0) / nx, (y1 - y0) / ny
    for j in range(ny):
        off = (sx / 2 if stagger and j % 2 else 0)
        for i in range(nx + (1 if stagger and j % 2 else 0)):
            a = x0 + i * sx - off; b = a + sx
            a, b = max(a, x0), min(b, x1)
            if b - a < 0.08: continue
            dz = rnd.uniform(-jitter, jitter)
            out.append(B(nm, (b - a - gap, sy - gap, h), ((a + b) / 2, y0 + (j + 0.5) * sy, z - h / 2 + dz), m, r=r, seg=2))
    return out

def recolor_some(objs, every, start, m):
    for k, o in enumerate(objs):
        if k % every == start: o.data.materials[0] = m

# ───────── 地基 ─────────
PLAZA = (-3.6, 3.6, -2.2, 1.4)       # 中央广场
DECK = (-7.4, 7.4, 1.4, 2.6)         # 书店/影院门前共用木地板
PATH = (-1.6, 1.6, -7.9, -2.2)       # 南入口石板路
MAT = (-7.3, -2.7, -7.0, -3.1)       # 健身角橡胶垫
SHOP_T = (1.6, 4.4, -6.6, -2.2)      # 超市门前瓷砖
APRONS = ((-7.4, -3.6, 0.55, 1.4), (3.6, 7.4, 0.55, 1.4))

def _bed(r, m, z=0.04):
    return B('g', (r[1] - r[0], r[3] - r[2], 0.04), ((r[0] + r[1]) / 2, (r[2] + r[3]) / 2, z), m, r=0.01)

def build_ground():
    coll(); wipe(('Ground_',))
    out = [L2.join([B('g', (16, 16, 0.36), (0, 0, -0.18), M('base'), r=0.08),
                    B('g', (15.96, 15.96, 0.05), (0, 0, -0.005), M('soil'), r=0.02)], 'Ground_base')]
    out.append(L2.join([B('g', (15.8, 15.8, 0.06), (0, 0, 0.01), M('grass'), r=0.03)], 'Ground_grass'))
    pv = [_bed(PLAZA, M('grout'))] + tiles('g', *PLAZA, (0.6, 0.6), M('plaza'), z=G)
    st = tiles('g', *PATH, (0.55, 0.42), M('slate'), gap=0.05, z=G, jitter=0.006, seed=3, stagger=True)
    recolor_some(st, 3, 1, M('slate2')); pv += st
    st = tiles('g', -2.7, -1.6, -5.4, -4.5, (0.5, 0.45), M('slate'), gap=0.05, z=G, seed=5)   # 主路 → 健身垫
    recolor_some(st, 2, 1, M('slate2')); pv += st
    pv += [_bed(SHOP_T, M('tile_grout'))] + tiles('g', *SHOP_T, (0.4, 0.4), M('tile'), gap=0.02, z=G, r=0.008)
    out.append(L2.join(pv, 'Ground_paving'))
    wd = tiles('g', *DECK, (1.85, 0.2), M('deck'), gap=0.025, h=0.06, z=G + 0.01, r=0.012, stagger=True, seed=7)
    for ap in APRONS:   # 书摊 / 影院门前再往南伸一块
        wd += tiles('g', *ap, (1.9, 0.2), M('deck'), gap=0.025, h=0.06, z=G + 0.01, r=0.012, stagger=True, seed=8)
    recolor_some(wd, 4, 2, M('deck2'))
    for ap in APRONS:
        wd.append(B('g', (ap[1] - ap[0], 0.08, 0.07), ((ap[0] + ap[1]) / 2, ap[2] - 0.04, G - 0.02), M('wood_dark'), r=0.02))
    wd += [B('g', (PLAZA[1] - PLAZA[0], 0.08, 0.07), (0, DECK[2] - 0.04, G - 0.02), M('wood_dark'), r=0.02)]
    out.append(L2.join(wd, 'Ground_woodpath'))
    mt = [B('g', (MAT[1] - MAT[0] + 0.12, MAT[3] - MAT[2] + 0.12, 0.05), ((MAT[0] + MAT[1]) / 2, (MAT[2] + MAT[3]) / 2, 0.045), M('rubber_line'), r=0.03)]
    mt += tiles('g', *MAT, (0.98, 0.98), M('rubber'), gap=0.025, h=0.05, z=G + 0.015, r=0.02)
    out.append(L2.join(mt, 'Ground_mat'))
    return out

# ───────── 实体通用 ─────────
import lib_learn4 as L4
FACE = {'S': 0, 'N': math.pi, 'E': math.pi / 2, 'W': -math.pi / 2}

def finish(parts, obj_name, prefix, loc=(0, 0, 0)):
    """零件按材质合并 → <prefix>_<材质>，挂到空物体 Obj_<元素> 下。"""
    coll()
    e = get(obj_name)
    if e is None:
        e = bpy.data.objects.new(obj_name, None); bpy.data.collections[COLL].objects.link(e)
    e.empty_display_type, e.empty_display_size = 'CUBE', 0.4
    e.location = loc
    for c in list(e.children):
        if c.name.startswith(('Port_', 'Foliage_')): continue
        d = c.data; bpy.data.objects.remove(c, do_unlink=True)
        if d is not None and d.users == 0: bpy.data.meshes.remove(d)
    keep = [o for o in parts if o.name.startswith(('Foliage_', 'Port_'))]
    merged = lb.join_by_material([o for o in parts if o not in keep])
    for m in merged:
        m.name = m.data.name = prefix + '_' + m.name[2:].replace('D_', '')
    L2.parent(merged + keep, e)
    return e, merged

def text(nm, s, size, loc, m, rz=0.0, depth=0.02, align='CENTER'):
    """立体字 → 网格（面朝 -Y，再绕 Z 旋转）。"""
    cu = bpy.data.curves.new(nm, 'FONT'); cu.body = s; cu.size = size
    cu.extrude = depth; cu.bevel_depth = depth * 0.4; cu.bevel_resolution = 1
    cu.align_x = align; cu.align_y = 'CENTER'; cu.resolution_u = 4
    o = bpy.data.objects.new(nm, cu); bpy.context.collection.objects.link(o)
    o.rotation_euler = (math.pi / 2, 0, rz); o.location = loc
    o.data.materials.append(m)
    lb.select_only([o]); bpy.ops.object.convert(target='MESH')
    o = bpy.context.view_layer.objects.active
    return o

def prism(nm, pts_yz, x0, x1, m, r=0.03):
    """YZ 平面多边形沿 X 拉伸（山墙三角等）。"""
    bm = bmesh.new()
    a = [bm.verts.new((x0, y, z)) for y, z in pts_yz]; b = [bm.verts.new((x1, y, z)) for y, z in pts_yz]
    bm.faces.new(a); bm.faces.new(b[::-1]); n = len(a)
    for k in range(n):
        bm.faces.new((a[k], a[(k + 1) % n], b[(k + 1) % n], b[k]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    o = lb.new_obj(nm); bm.to_mesh(o.data); bm.free(); o.data.materials.append(m)
    return L2._soft(o, r, 2)

def gable(nm, x0, x1, y0, y1, z_eave, z_ridge, over, t, m_roof, m_board, m_gable, n_boards=0):
    """沿 X 的双坡屋顶：两片圆角坡面 + 顺坡木条 + 屋脊圆木 + 封檐板 + 两端山墙三角。"""
    out = []
    cy = (y0 + y1) / 2; half = (y1 - y0) / 2; rise = z_ridge - z_eave
    ang = math.atan2(rise, half)
    L_ = math.hypot(half, rise) + over / math.cos(ang)
    W = x1 - x0 + 2 * over
    for s in (-1, 1):
        # 坡面中心：从屋脊沿坡向外 L_/2；rot.x 正值让 +Y 侧抬高，所以 s=-1(南坡) 取 +ang
        d = L_ / 2
        mid_y = cy + s * d * math.cos(ang); mid_z = z_ridge - d * math.sin(ang) + t / 2
        rx = -s * ang
        out.append(B(nm + '_slab', (W, L_, t), ((x0 + x1) / 2, mid_y, mid_z), m_roof, r=0.05, rot=(rx, 0, 0)))
        nz = t / 2 + 0.015
        for k in range(n_boards):
            bx = x0 - over + 0.15 + k * (W - 0.3) / (n_boards - 1)
            out.append(B(nm + '_bat', (0.06, L_ - 0.08, 0.035), (bx, mid_y + s * nz * math.sin(ang), mid_z + nz * math.cos(ang)), m_board, r=0.014, rot=(rx, 0, 0)))
        ey = cy + s * (half + over * 0.98); ez = z_eave - over * math.tan(ang) + 0.02
        out.append(B(nm + '_fascia', (W + 0.04, 0.07, 0.17), ((x0 + x1) / 2, ey, ez), m_board, r=0.025))
    out.append(C(nm + '_ridge', 0.09, W + 0.08, ((x0 + x1) / 2, cy, z_ridge + t + 0.03), m_board, verts=16, rr=0.02, rot=(0, math.pi / 2, 0)))
    for xa, xb in ((x0, x0 + 0.2), (x1 - 0.2, x1)):
        out.append(prism(nm + '_gab', [(y0, z_eave), (y1, z_eave), (cy, z_ridge)], xa, xb, m_gable, r=0.02))
    return out
