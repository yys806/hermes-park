import bpy, bmesh, math
from mathutils import Vector

SC = bpy.data.scenes['clock']


def MAT(name, c):
    m = bpy.data.materials.get(name)
    if not m:
        m = bpy.data.materials.new(name)
        m.use_nodes = True
    b = next(x for x in m.node_tree.nodes if x.type == 'BSDF_PRINCIPLED')
    b.inputs['Base Color'].default_value = (*c, 1)
    b.inputs['Roughness'].default_value = 0.85
    b.inputs['Metallic'].default_value = 0
    b.inputs['Emission Strength'].default_value = 0
    m.diffuse_color = (*c, 1)
    return m


def _obj(name, bm, mat, loc, rot):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    o = bpy.data.objects.new(name, me)
    o.data.materials.append(mat)
    SC.collection.objects.link(o)
    o.location = loc
    o.rotation_euler = rot
    return o


def BOX(name, loc, size, mat, r=0.02, seg=3, rot=(0, 0, 0)):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1)
    bmesh.ops.scale(bm, vec=size, verts=bm.verts)
    r = min(r, min(size) * 0.45)
    if r > 0.001:
        bmesh.ops.bevel(bm, geom=bm.edges[:] + bm.verts[:], offset=r, segments=seg,
                        profile=0.5, affect='EDGES', clamp_overlap=True)
    return _obj(name, bm, mat, loc, rot)


def CYL(name, loc, rad, h, mat, n=24, r=0.015, seg=2, rot=(0, 0, 0), rad2=None):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=n, radius1=rad,
                          radius2=rad if rad2 is None else rad2, depth=h)
    if r > 0.001:
        ed = [e for e in bm.edges if abs(e.verts[0].co.z - e.verts[1].co.z) < 1e-5
              and abs(abs(e.verts[0].co.z) - h / 2) < 1e-5]
        bmesh.ops.bevel(bm, geom=ed, offset=min(r, h * 0.4), segments=seg, profile=0.5,
                        affect='EDGES', clamp_overlap=True)
    return _obj(name, bm, mat, loc, rot)


def PRISM(name, pts2d, z0, h, mat, loc=(0, 0, 0), rot=(0, 0, 0), r=0.01, seg=2):
    bm = bmesh.new()
    vs = [bm.verts.new((x, y, z0)) for x, y in pts2d]
    f = bm.faces.new(vs)
    res = bmesh.ops.extrude_face_region(bm, geom=[f])
    nv = [g for g in res['geom'] if isinstance(g, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, vec=(0, 0, h), verts=nv)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    if r > 0.001:
        bmesh.ops.bevel(bm, geom=bm.edges[:], offset=r, segments=seg, profile=0.5,
                        affect='EDGES', clamp_overlap=True)
    return _obj(name, bm, mat, loc, rot)


def SAVE():
    bpy.ops.wm.save_mainfile(filepath='D:/hermes/home/out/models/all_plots.blend')
