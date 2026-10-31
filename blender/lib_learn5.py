"""学习科研地块 第5轮：Quaternius 真资产替换 + 原生黏土材质（SSS + AO 顶点色，无噪波凹凸）。Blender 4.5"""
import bpy, re
from mathutils import Vector, Matrix

CL = 'D:/hermes/home/assets/lib/clay/'
UN = CL + 'quaternius-ultimate-nature/Ultimate Nature Pack - Jun 2019/Blends/'
PACK = {'mega': CL + 'quaternius-stylized-nature-megakit/glTF/',
        'props': CL + 'quaternius-fantasy-props/Exports/glTF/',
        'village': CL + 'quaternius-medieval-village/glTF/'}
COLL, SEASON = 'Learn2', 'Learn2_Seasonal'
USED = bpy.app.driver_namespace.setdefault('L5_used', set())

# Quaternius 原色名 → 黏土色（sRGB hex，比原包亮、偏暖、略降饱和）
QMAP = {'wood': '#8C5E40', 'green': '#86BF5E', 'darkgreen': '#5E9A48', 'orange': '#E8984E', 'snow': '#F3F4F7',
        'white': '#EEE7DA', 'black': '#4E4544', 'berry': '#D9566E', 'red': '#D9604E', 'yellow': '#F0C95A',
        'brown': '#9A6A48', 'lightgreen': '#A6D27A', 'grey': '#A7A9AE', 'gray': '#A7A9AE', 'darkgrey': '#7C7F86'}

def srgb(h):
    h = h.lstrip('#'); c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple((x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4) for x in c) + (1.0,)

def clay_nodes(m, rgba):
    """黏土 BSDF：Rough 0.9 / Spec 0 / SSS 0.2，Radius (0.02,0.015,0.01)，Scale 0.05；Base = 颜色 × AO 顶点色；无 bump。"""
    m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial'); b = nt.nodes.new('ShaderNodeBsdfPrincipled')
    b.inputs['Roughness'].default_value = 0.9
    b.inputs['Specular IOR Level'].default_value = 0.0
    b.inputs['Subsurface Weight'].default_value = 0.2
    b.inputs['Subsurface Radius'].default_value = (0.02, 0.015, 0.01)
    b.inputs['Subsurface Scale'].default_value = 0.05
    ao = nt.nodes.new('ShaderNodeVertexColor'); ao.layer_name = 'AO'
    mx = nt.nodes.new('ShaderNodeMix'); mx.data_type = 'RGBA'; mx.blend_type = 'MULTIPLY'
    mx.inputs['Factor'].default_value = 1.0; mx.inputs[6].default_value = rgba
    nt.links.new(ao.outputs['Color'], mx.inputs[7]); nt.links.new(mx.outputs[2], b.inputs['Base Color'])
    nt.links.new(b.outputs[0], out.inputs[0])
    m.diffuse_color = rgba; m['clay5'] = True
    return m

def clay(name, hexcol):
    nm = 'K5_' + name
    return bpy.data.materials.get(nm) or clay_nodes(bpy.data.materials.new(nm), srgb(hexcol))

def base_key(m):
    return re.sub(r'\.\d+$', '', m.name).lower().replace('_', '').replace(' ', '')

def recolor(o):
    """导入件的平涂/贴图材质 → 黏土材质（按原色名映射，未知名用原色提亮）。"""
    ensure_ao(o)
    for s in o.material_slots:
        m = s.material
        if m is None or m.get('clay5'): continue
        k = base_key(m)
        if k in QMAP: s.material = clay('q_' + k, QMAP[k]); continue
        c = list(m.diffuse_color)
        if m.use_nodes:
            b = next((n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
            if b and not b.inputs['Base Color'].is_linked: c = list(b.inputs['Base Color'].default_value)
        c = [min(1.0, x * 1.25 + 0.02) for x in c[:3]]
        nm = 'K5_q_' + k
        s.material = bpy.data.materials.get(nm) or clay_nodes(bpy.data.materials.new(nm), tuple(c) + (1.0,))

def ensure_ao(o, val=1.0):
    """AO 顶点色层（缺失时 Color Attribute 节点输出黑色），默认白，烘焙后覆盖。"""
    me = o.data
    a = me.color_attributes.get('AO')
    if a is None:
        a = me.color_attributes.new('AO', 'BYTE_COLOR', 'CORNER')
        a.data.foreach_set('color', [val, val, val, 1.0] * len(a.data))
    me.color_attributes.active_color = a; me.color_attributes.render_color_index = me.color_attributes.find('AO')
    return a

def to_clay(m, glassy=False):
    """原地把 L2_ 材质改成黏土节点：保留底色/自发光/透明度，删掉噪波 bump。"""
    nt = m.node_tree; b = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    bc = b.inputs['Base Color']
    col = tuple(bc.links[0].from_node.inputs[6].default_value) if bc.is_linked and bc.links[0].from_node.type == 'MIX' else tuple(bc.default_value)
    ec = tuple(b.inputs['Emission Color'].default_value); es = b.inputs['Emission Strength'].default_value
    al = b.inputs['Alpha'].default_value
    clay_nodes(m, col)
    b = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    b.inputs['Emission Color'].default_value = ec; b.inputs['Emission Strength'].default_value = es
    b.inputs['Alpha'].default_value = al
    if glassy:
        b.inputs['Roughness'].default_value = 0.25; b.inputs['Subsurface Weight'].default_value = 0.0
        b.inputs['Specular IOR Level'].default_value = 0.4
    return m

def densify(o, maxlen=0.35, loops=6):
    """顶点色 AO 只在顶点采样：大平面三角化后反复对半切长边，让墙面内部也有采样点。"""
    import bmesh
    me = o.data; bm = bmesh.new(); bm.from_mesh(me)
    sx = max(o.scale)
    long = [f for f in bm.faces if any(e.calc_length() * sx > maxlen for e in f.edges)]
    if not long: bm.free(); return 0
    bmesh.ops.triangulate(bm, faces=long)
    for _ in range(loops):
        es = [e for e in bm.edges if e.calc_length() * sx > maxlen]
        if not es: break
        bmesh.ops.subdivide_edges(bm, edges=es, cuts=1, use_grid_fill=True)
        bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4])
    bm.to_mesh(me); bm.free(); me.update()
    return len(me.polygons)

def remap_ao(o, lo=0.5, gamma=0.7, warm=(1.0, 0.95, 0.9)):
    """烘焙值 → 柔和黏土 AO：抬黑位、提 gamma，暗部略偏暖。"""
    a = o.data.color_attributes['AO']
    buf = [0.0] * (len(a.data) * 4); a.data.foreach_get('color', buf)
    for i in range(0, len(buf), 4):
        v = lo + (1 - lo) * (max(0.0, buf[i]) ** gamma)
        buf[i:i + 3] = [1 - (1 - v) * (2 - w) for w in warm]
    a.data.foreach_set('color', buf)

def smooth_ao(o, iters=2):
    """AO 按顶点平均后沿边做邻域平滑，消掉三角化带来的条纹，写回各 corner。"""
    me = o.data; a = me.color_attributes['AO']; nv = len(me.vertices)
    lv = [0] * len(me.loops); me.loops.foreach_get('vertex_index', lv)
    buf = [0.0] * (len(lv) * 4); a.data.foreach_get('color', buf)
    s = [[0.0, 0.0, 0.0, 0] for _ in range(nv)]
    for i, v in enumerate(lv):
        t = s[v]; t[0] += buf[i * 4]; t[1] += buf[i * 4 + 1]; t[2] += buf[i * 4 + 2]; t[3] += 1
    c = [(t[0] / t[3], t[1] / t[3], t[2] / t[3]) if t[3] else (1, 1, 1) for t in s]
    ev = [0] * (len(me.edges) * 2); me.edges.foreach_get('vertices', ev)
    for _ in range(iters):
        acc = [list(x) + [1] for x in c]
        for k in range(0, len(ev), 2):
            p, q = ev[k], ev[k + 1]
            for j in range(3): acc[p][j] += c[q][j]; acc[q][j] += c[p][j]
            acc[p][3] += 1; acc[q][3] += 1
        c = [(x[0] / x[3], x[1] / x[3], x[2] / x[3]) for x in acc]
    for i, v in enumerate(lv): buf[i * 4:i * 4 + 3] = c[v]
    a.data.foreach_set('color', buf)

_IMG = {}

def _pixels(img):
    if img.name not in _IMG:
        import array
        if img.size[0] == 0:   # fantasy-props 的 glTF 引用 ../Textures 下的贴图，路径解析失败时改指过去
            import os
            fn = os.path.basename(img.filepath.replace('\\', '/')) or re.sub(r'\.\d+$', '', img.name) + '.png'
            for d in (CL + 'quaternius-fantasy-props/Textures/', PACK['village'], PACK['mega']):
                if os.path.exists(d + fn): img.filepath = d + fn; img.reload(); break
        if img.size[0] == 0: return None
        buf = array.array('f', [0.0]) * (img.size[0] * img.size[1] * 4); img.pixels.foreach_get(buf)
        _IMG[img.name] = (img.size[0], img.size[1], buf)
    return _IMG[img.name]

def bake_tex(o):
    """贴图（trim sheet）→ 每面取 UV 中心的颜色写入 TEX 层（线性），之后乘进 AO；材质换成白底黏土。"""
    me = o.data; uv = me.uv_layers.active
    if uv is None: return False
    imgs = []
    for s in o.material_slots:
        m = s.material; t = None
        if m and m.use_nodes:
            t = next((n.image for n in m.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image), None)
        imgs.append(t)
    if not any(imgs): return False
    a = me.color_attributes.get('TEX') or me.color_attributes.new('TEX', 'FLOAT_COLOR', 'CORNER')
    buf = [1.0] * (len(me.loops) * 4)
    for p in me.polygons:
        img = imgs[p.material_index] if p.material_index < len(imgs) else None
        if img is None:
            c = list(o.material_slots[p.material_index].material.diffuse_color[:3])
        elif _pixels(img) is None:
            c = [0.8, 0.8, 0.8]
        else:
            w, h, px = _pixels(img)
            u = sum(uv.data[i].uv.x for i in p.loop_indices) / p.loop_total
            v = sum(uv.data[i].uv.y for i in p.loop_indices) / p.loop_total
            x = int((u % 1.0) * (w - 1)); y = int((v % 1.0) * (h - 1)); k = (y * w + x) * 4
            c = [px[k], px[k + 1], px[k + 2]]
            if img.colorspace_settings.name == 'sRGB':
                c = [(q / 12.92 if q <= 0.04045 else ((q + 0.055) / 1.055) ** 2.4) for q in c]
        c = [min(1.0, q * 1.15 + 0.015) for q in c]
        for i in p.loop_indices: buf[i * 4:i * 4 + 3] = c
    a.data.foreach_set('color', buf)
    me.materials.clear(); me.materials.append(clay('vc_white', '#FFFFFF'))
    return True

def finish_ao(objs):
    """新物件：Cycles AO 烘焙到顶点色 → 柔化 → 平滑 → 乘 TEX。"""
    for o in bpy.context.selected_objects: o.select_set(False)
    for o in objs: densify(o); ensure_ao(o); o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.bake(type='AO', target='VERTEX_COLORS')
    for o in objs:
        remap_ao(o); smooth_ao(o, 2)
        t = o.data.color_attributes.get('TEX')
        if t:
            a = o.data.color_attributes['AO']; n = len(a.data) * 4
            b1 = [0.0] * n; b2 = [0.0] * n; a.data.foreach_get('color', b1); t.data.foreach_get('color', b2)
            a.data.foreach_set('color', [x * y for x, y in zip(b1, b2)])
            o.data.color_attributes.remove(t); ensure_ao(o)

def _link(o, coll):
    for c in list(o.users_collection): c.objects.unlink(o)
    bpy.data.collections[coll].objects.link(o)

def append_nature(name, newname, coll=COLL):
    with bpy.data.libraries.load(UN + name + '.blend', link=False) as (df, dt):
        dt.objects = [n for n in df.objects]
    obs = [o for o in dt.objects if o and o.type == 'MESH']
    o = obs[0]; o.name = newname; o.data.name = newname
    _link(o, coll); USED.add('UltimateNature/' + name)
    recolor(o)
    return o

def import_gltf(pack, name, newname, coll=COLL):
    """导入 glTF → 合并为单网格（去空物体），返回对象。"""
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=PACK[pack] + name + '.gltf')
    new = [o for o in bpy.data.objects if o not in before]
    meshes = [o for o in new if o.type == 'MESH']
    dg = bpy.context.evaluated_depsgraph_get()
    for o in meshes:
        o.data = o.data.copy() if o.data.users > 1 else o.data
        o.data.transform(o.matrix_world); o.parent = None; o.matrix_world = o.matrix_world.Identity(4)
    for o in new:
        if o.type != 'MESH': bpy.data.objects.remove(o, do_unlink=True)
    if len(meshes) > 1:
        with bpy.context.temp_override(active_object=meshes[0], selected_editable_objects=meshes):
            bpy.ops.object.join()
    o = meshes[0]; o.name = newname; o.data.name = newname
    _link(o, coll); USED.add(pack + '/' + name)
    if not bake_tex(o): recolor(o)
    ensure_ao(o)
    return o

def normalize(o, height=None, scale=None, loc=(0, 0), z=0.0, rz=0.0, smooth=True, center=False):
    """按高度或倍率缩放，原点(树根)放到 loc，最低点落在 z。"""
    zs = [v.co.z for v in o.data.vertices]; h = max(zs) - min(zs)
    k = scale if scale else height / h
    o.rotation_mode = 'XYZ'   # glTF 导入默认是四元数，不切换的话 rotation_euler 无效
    o.scale = (k, k, k); o.rotation_euler = (0, 0, rz)
    o.location = (loc[0], loc[1], z - min(zs) * k)
    if center:   # 道具：按包围盒中心落位（原点常在一端）
        xs = [v.co.x for v in o.data.vertices]; ys = [v.co.y for v in o.data.vertices]
        c = Vector(((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, 0)) * k
        c.rotate(Matrix.Rotation(rz, 3, 'Z')); o.location.x -= c.x; o.location.y -= c.y
    if smooth: o.data.polygons.foreach_set('use_smooth', [True] * len(o.data.polygons)); o.data.update()
    return k

def seasonal(o, hidden=True):
    _link(o, SEASON)
    o['default_visible'] = not hidden; o.hide_render = hidden; o.hide_set(hidden)

def season(name):
    """spring/summer: Foliage_；autumn: Foliage_Autumn_ 替换夏叶；winter: Snow_；bare: Bare_（枯树）。"""
    objs = [o for o in bpy.data.collections[COLL].all_objects]
    for o in objs:
        n = o.name
        if n.startswith('Foliage_Autumn_'): vis = name == 'autumn'
        elif n.startswith(('Foliage_', 'Trunk_')): vis = name in ('spring', 'summer') or (name == 'autumn' and not o.get('has_autumn'))
        elif n.startswith('Snow_'): vis = name == 'winter'
        elif n.startswith('Bare_'): vis = name == 'bare'
        else: continue
        o.hide_render = not vis; o.hide_set(not vis)
