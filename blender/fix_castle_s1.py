"""Claude 版城堡 · 修 1：删底板/前院地砖 · 城垛落地 · 窗户统一光源材质"""
import bpy, bmesh, sys, os
sys.path.insert(0, r'D:\hermes\home\blender')
import lib_building as L
from mathutils import Vector

# ---------- 1) 删底板与城堡前地砖 ----------
for n in ('Ground_Plaza', 'Forecourt_paving'):
    o = bpy.data.objects.get(n)
    if o:
        bpy.data.objects.remove(o, do_unlink=True)
        print('[DEL]', n)

# ---------- 2) 城垛落地：把悬空的墩往下平移 ----------
WALL_TOP = 4.40
moved = 0
for on in ('WallB_stone', 'WallL_stone', 'WallFL_stone', 'WallFR_stone'):
    o = bpy.data.objects.get(on)
    if not o:
        print('[MISS]', on); continue
    bm = bmesh.new(); bm.from_mesh(o.data)
    seen = set(); groups = []
    for v in bm.verts:
        if v.index in seen: continue
        st = [v]; seen.add(v.index); g = []
        while st:
            c = st.pop(); g.append(c)
            for e in c.link_edges:
                w = e.other_vert(c)
                if w.index not in seen:
                    seen.add(w.index); st.append(w)
        zs = [(o.matrix_world @ x.co).z for x in g]
        groups.append((g, min(zs), max(zs)))
    dz = {}
    for g, zmin, zmax in groups:
        if 4.45 <= zmin <= 4.60 and zmax < 5.2:
            d = WALL_TOP - zmin
            dz[round(d, 3)] = dz.get(round(d, 3), 0) + 1
            for v in g:
                v.co.z -= d
            moved += 1
    bm.to_mesh(o.data); bm.free()
    print(f'[MERLON] {on} moved={sum(dz.values())} dz={dz}')

# ---------- 3) 窗户统一成一个光源材质 ----------
m = bpy.data.materials.get('Window_Glow')
if not m:
    print('[ERR] Window_Glow 不存在'); raise SystemExit(1)
bsdf = next((n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
for k in ('Base Color', 'Emission Color', 'Emission Strength'):
    if bsdf and k in bsdf.inputs:
        print('[BEFORE]', k, list(bsdf.inputs[k].default_value) if hasattr(bsdf.inputs[k].default_value, '__len__') else bsdf.inputs[k].default_value)
m.name = 'LGT_castle_window'
WARM = (1.0, 0.70, 0.32, 1.0)
if bsdf:
    if 'Base Color' in bsdf.inputs:
        bsdf.inputs['Base Color'].default_value = (0.42, 0.28, 0.10, 1.0)
    if 'Emission Color' in bsdf.inputs:
        bsdf.inputs['Emission Color'].default_value = WARM
    if 'Emission Strength' in bsdf.inputs:
        bsdf.inputs['Emission Strength'].default_value = 2.2
m.diffuse_color = WARM
print('[MAT] renamed ->', m.name, 'emission set')

# ---------- 4) 统计 + 保存 + 导出 ----------
meshes = [o for o in bpy.data.objects if o.type == 'MESH']
bpy.ops.wm.save_mainfile()
print('[SAVED] blend objects=%d' % len(meshes))
L.export_glb(r'D:\hermes\home\out\models\castle_claude.glb', meshes)
