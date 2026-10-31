"""共享建模工具库：圆角体素、材质、布尔、按材质合并、GLB 导出。Blender 4.5 / Python 3.11"""
import bpy, bmesh, os, math
from mathutils import Vector, Matrix, Quaternion

ANGLE = math.radians(30)

def reset_scene():
    """清空场景（安全版）。

    🔴 绝不能用 bpy.ops.wm.read_factory_settings()：它会把所有插件重置，
    连带把 Blender MCP 的 addon 一起禁用，MCP 连接立刻断掉、Blender 可能直接退出。
    （2026-10-27 实测踩过，一轮建模白跑）
    这里只删数据块，不碰插件和用户偏好。
    """
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.cameras,
                 bpy.data.lights, bpy.data.curves, bpy.data.images):
        for item in list(coll):
            try:
                coll.remove(item)
            except Exception:
                pass

def srgb_to_linear(c):
    """单通道 sRGB(0~1) 转线性。"""
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

def mat(name, hexcolor, roughness=0.8, metallic=0.0, alpha=1.0):
    """按名字取/建 Principled 材质；hex 转线性写入 Base Color，alpha<1 时启用混合。"""
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    m = bpy.data.materials.new(name)
    m.use_nodes = True  # 4.x 新建材质默认 use_nodes=False、node_tree=None
    nt = m.node_tree
    bsdf = nt.nodes.get('Principled BSDF')
    if bsdf is None:  # 兜底：节点名可能被本地化/改版，按类型找
        bsdf = next((n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if bsdf is None:  # 仍没有则新建并接到输出
        bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
        out = next((n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL'), None) or nt.nodes.new('ShaderNodeOutputMaterial')
        nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    r, g, b = (srgb_to_linear(int(hexcolor.lstrip('#')[i:i + 2], 16) / 255) for i in (0, 2, 4))
    bsdf.inputs['Base Color'].default_value = (r, g, b, alpha)
    for k, v in (('Roughness', roughness), ('Metallic', metallic), ('Alpha', alpha)):
        bsdf.inputs[k].default_value = v
    m.diffuse_color = (r, g, b, alpha)
    if alpha < 1.0:
        m.surface_render_method = 'BLENDED'  # 4.2+ 新属性
        if hasattr(m, 'blend_method'):
            m.blend_method = 'BLEND'  # 旧属性，4.x 仍保留（已弃用）
    return m

def new_obj(name, mesh_or_none=None):
    """新建网格对象并链接到当前集合；不给 mesh 时建空网格。"""
    obj = bpy.data.objects.new(name, mesh_or_none or bpy.data.meshes.new(name))
    bpy.context.collection.objects.link(obj)
    return obj

def _finish(obj, name, material, bevel, seg):
    """内部：命名、挂 Bevel（bevel>0）+ WeightedNormal、指定材质。"""
    obj.name = obj.data.name = name
    if bevel > 0:
        bv = obj.modifiers.new('Bevel', 'BEVEL')
        bv.width, bv.segments, bv.limit_method = bevel, seg, 'ANGLE'
        bv.angle_limit, bv.harden_normals = ANGLE, True
    wn = obj.modifiers.new('WeightedNormal', 'WEIGHTED_NORMAL')
    wn.keep_sharp, wn.weight = True, 50
    if material is not None:
        obj.data.materials.append(material)
    return obj

def box(name, size, loc=(0, 0, 0), rot=(0, 0, 0), material=None,
        bevel=0.03, seg=2, smooth=False):
    """圆角立方体：尺寸烘焙进网格（scale 保持 1，倒角不变形）。"""
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc, rotation=rot)
    obj = bpy.context.active_object
    obj.data.transform(Matrix.Diagonal((size[0], size[1], size[2], 1.0)))
    _finish(obj, name, material, bevel, seg)
    if smooth:
        select_only([obj])
        try:
            bpy.ops.object.shade_auto_smooth(angle=ANGLE)
        except Exception:
            bpy.ops.object.shade_smooth()
    return obj

def cyl(name, radius, height, loc=(0, 0, 0), rot=(0, 0, 0), material=None,
        verts=24, bevel=0.01, seg=2, cap=True):
    """圆柱（沿 Z 轴），带 Bevel + WeightedNormal；cap=False 时不封口。"""
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=radius, depth=height, location=loc,
                                        rotation=rot, end_fill_type='NGON' if cap else 'NOTHING')
    return _finish(bpy.context.active_object, name, material, bevel, seg)

def sphere(name, radius, loc, material, segs=16, rings=12):
    """UV 球，平滑着色 + WeightedNormal，无倒角。"""
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segs, ring_count=rings, radius=radius, location=loc)
    obj = bpy.context.active_object
    obj.data.polygons.foreach_set('use_smooth', [True] * len(obj.data.polygons))
    return _finish(obj, name, material, 0, 0)

def panel(name, verts2d, thickness, loc=(0, 0, 0), rot=(0, 0, 0), material=None, bevel=0.02):
    """XY 平面 2D 轮廓 → Solidify 沿 +Z 加厚 → Bevel → WeightedNormal。"""
    obj = new_obj(name)
    bm = bmesh.new()
    f = bm.faces.new([bm.verts.new((x, y, 0.0)) for x, y in verts2d])
    f.normal_update()
    if f.normal.z < 0:
        f.normal_flip()  # 保证法线朝 +Z，配合 offset=1 向上挤出
    bm.to_mesh(obj.data)
    bm.free()
    obj.location, obj.rotation_euler = loc, rot
    so = obj.modifiers.new('Solidify', 'SOLIDIFY')
    so.thickness, so.offset = thickness, 1.0
    return _finish(obj, name, material, bevel, 2)

def select_only(objs):
    """只选中 objs，并把第一个设为 active。"""
    vl = bpy.context.view_layer
    for o in vl.objects:
        o.select_set(o in objs)
    if objs:
        vl.objects.active = objs[0]

def boolean_cut(target, cutter):
    """target 减去 cutter（布尔差集，移到栈首后应用），然后删除 cutter。"""
    mod = target.modifiers.new('BoolCut', 'BOOLEAN')
    mod.operation, mod.solver, mod.object = 'DIFFERENCE', 'EXACT', cutter
    select_only([target])
    bpy.ops.object.modifier_move_to_index(modifier=mod.name, index=0)
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(cutter, do_unlink=True)
    return target

def window_recess(wall, w, h, depth, loc, rot_z=0.0):
    """在墙上挖窗洞：切割体 X=w、Y=depth、Z=h，loc 为墙局部坐标的洞中心。"""
    bpy.context.view_layer.update()
    _, rq, _ = wall.matrix_world.decompose()
    cutter = box(wall.name + '_cut', (w, depth, h), bevel=0)
    cutter.matrix_world = Matrix.LocRotScale(wall.matrix_world @ Vector(loc),
                                             rq @ Quaternion((0, 0, 1), rot_z), None)
    return boolean_cut(wall, cutter)

def array_offset(obj, count, offset_vec, axis='X'):
    """Array 修改器（固定偏移 count 份）；offset_vec 给标量时沿 axis 方向。"""
    if isinstance(offset_vec, (int, float)):
        offset_vec = [float(offset_vec) if a == axis.upper() else 0.0 for a in 'XYZ']
    mod = obj.modifiers.new('Array', 'ARRAY')
    mod.count, mod.use_relative_offset, mod.use_constant_offset = count, False, True
    mod.constant_offset_displace = offset_vec
    return mod

def dupe(obj, loc, rot=(0, 0, 0), scale=None):
    """深复制对象（含网格数据和修改器），设位置/旋转/缩放。"""
    new = obj.copy()
    if obj.data is not None:
        new.data = obj.data.copy()
    (obj.users_collection[0] if obj.users_collection else bpy.context.collection).objects.link(new)
    new.location, new.rotation_euler = loc, rot
    new.scale = scale if scale is not None else obj.scale
    return new

def shift(obj, delta):
    """平移对象。"""
    obj.location += Vector(delta)
    return obj

def clear_all_modifiers(obj):
    """删除对象的全部修改器（不应用）。"""
    obj.modifiers.clear()

def apply_all_modifiers(obj):
    """按栈顺序应用对象的全部修改器（遍历副本，apply 会改动集合）。"""
    select_only([obj])
    for m in list(obj.modifiers):
        bpy.ops.object.modifier_apply(modifier=m.name)

def join_by_material(objs, tol=0.0):
    """按 active_material 名分组（无材质归 'none'），每组先应用修改器再 Join；tol>0 时按距离合并顶点。"""
    groups = {}
    for o in objs:
        if o.type == 'MESH':
            groups.setdefault(o.active_material.name if o.active_material else 'none', []).append(o)
    result = []
    for key, grp in groups.items():
        for o in grp:
            apply_all_modifiers(o)
        select_only(grp)
        if len(grp) > 1:
            bpy.ops.object.join()
        merged = bpy.context.view_layer.objects.active
        merged.name = merged.data.name = 'M_' + key
        if tol > 0:
            bm = bmesh.new()
            bm.from_mesh(merged.data)
            bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=tol)
            bm.to_mesh(merged.data)
            bm.free()
        result.append(merged)
    return result

def import_glb(path, name_prefix='imported', scale=1.0, loc=(0, 0, 0), rot=(0, 0, 0), recolor=None):
    """导入 GLB/GLTF 文件，返回导入的对象列表。
    recolor: 若给定材质字典 {old_mat_name: new_mat}，替换材质；或给单个材质对象统一替换所有材质。
    """
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    imported = [o for o in bpy.data.objects if o not in before]

    for obj in imported:
        obj.name = f'{name_prefix}_{obj.name}'
        obj.location = Vector(loc)
        obj.rotation_euler = rot
        obj.scale = (scale, scale, scale)

        # 材质替换
        if recolor and obj.type == 'MESH':
            if isinstance(recolor, dict):
                for slot in obj.material_slots:
                    if slot.material and slot.material.name in recolor:
                        slot.material = recolor[slot.material.name]
            else:  # 单个材质，统一替换
                for slot in obj.material_slots:
                    slot.material = recolor

    return imported

def export_glb(path, objs):
    """导出选中对象为 GLB（Y-up、应用修改器），打印 mesh/三角面/材质/文件大小。"""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    select_only(objs)
    bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', use_selection=True,
                              export_apply=True, export_yup=True, export_materials='EXPORT')
    dg = bpy.context.evaluated_depsgraph_get()
    meshes = [o for o in objs if o.type == 'MESH']
    tris, mats = 0, set()
    for o in meshes:
        eo = o.evaluated_get(dg)  # 用求值后网格计数，与 export_apply 一致
        me = eo.to_mesh()
        me.calc_loop_triangles()
        tris += len(me.loop_triangles)
        eo.to_mesh_clear()
        mats.update(s.material.name for s in o.material_slots if s.material)
    size = os.path.getsize(path)
    print(f'[export_glb] {path}: meshes={len(meshes)} tris={tris} materials={len(mats)} size={size / 1024:.1f} KB')
    return {'meshes': len(meshes), 'tris': tris, 'materials': len(mats), 'bytes': size}
