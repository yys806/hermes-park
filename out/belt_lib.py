import bpy, bmesh, math
from mathutils import Matrix, Vector
COL = bpy.data.collections['Belt_parts_vault']
HW = 0.45      # half belt width
TOP = 0.55     # belt top
NEW = []

def frame(p, d, z=0.0):
    d = Vector((d[0], d[1], 0)).normalized(); n = Vector((-d.y, d.x, 0))
    return Matrix(((d.x, n.x, 0, p[0]), (d.y, n.y, 0, p[1]), (0, 0, 1, z), (0, 0, 0, 1)))

def _bev(bm, verts, w, seg=2):
    if w <= 0: return
    es = list({e for v in verts for e in v.link_edges})
    bmesh.ops.bevel(bm, geom=list(verts) + es, offset=w, segments=seg, affect='EDGES', profile=0.5)

def box(bm, M, x0, x1, y0, y1, z0, z1, bev=0.0):
    tmp = bmesh.new()
    r = bmesh.ops.create_cube(tmp, size=1.0)
    for v in tmp.verts:
        v.co = Vector(((v.co.x + .5) * (x1 - x0) + x0, (v.co.y + .5) * (y1 - y0) + y0, (v.co.z + .5) * (z1 - z0) + z0))
    _bev(tmp, tmp.verts[:], min(bev, (x1-x0)/2.1, (y1-y0)/2.1, (z1-z0)/2.1))
    bmesh.ops.transform(tmp, matrix=M, verts=tmp.verts[:])
    _merge(bm, tmp)

def cyl(bm, M, r, L, seg=16, bev=0.0):
    """cylinder along local Y, centered at M origin"""
    tmp = bmesh.new()
    bmesh.ops.create_cone(tmp, cap_ends=True, segments=seg, radius1=r, radius2=r, depth=L)
    _bev(tmp, tmp.verts[:], min(bev, r * 0.4), 1)
    bmesh.ops.rotate(tmp, verts=tmp.verts[:], cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 4, 'X'))
    bmesh.ops.transform(tmp, matrix=M, verts=tmp.verts[:])
    _merge(bm, tmp)

def _merge(bm, tmp):
    me = bpy.data.meshes.new('_t'); tmp.to_mesh(me); tmp.free()
    bm.from_mesh(me); bpy.data.meshes.remove(me)

def obj(name, bm, mat):
    if name in bpy.data.objects:
        print('NAME CLASH', name); return None
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    for p in me.polygons: p.use_smooth = True
    try: me.set_sharp_from_angle(angle=math.radians(40))
    except Exception: pass
    me.materials.append(bpy.data.materials[mat])
    ca = me.color_attributes.new('AO', 'BYTE_COLOR', 'CORNER')
    for li, l in enumerate(me.loops):
        z = me.vertices[l.vertex_index].co.z
        a = 0.62 + 0.38 * min(1.0, max(0.0, z / 0.6))
        ca.data[li].color = (a, a, a, 1.0)
    me.color_attributes.active_color = ca
    o = bpy.data.objects.new(name, me); COL.objects.link(o); NEW.append(o)
    return o
