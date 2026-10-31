import bpy, bmesh, math
from mathutils import Matrix, Vector


def gear_ring(name, R, ri, nt, th, mat):
    """Toothed ring: trapezoid teeth on the outside, round bore inside."""
    bm = bmesh.new()
    ro, rr = R, R - 0.075
    outer = []
    for i in range(nt):
        a0 = 2 * math.pi * i / nt
        da = 2 * math.pi / nt
        for f, r in [(0.0, rr), (0.18, ro), (0.42, ro), (0.6, rr)]:
            outer.append((a0 + f * da, r))
    n = len(outer)
    inner = [(2 * math.pi * k / n, ri) for k in range(n)]
    loops = []
    for pts in (outer, inner):
        for z in (-th / 2, th / 2):
            loops.append([bm.verts.new((r * math.cos(a), r * math.sin(a), z)) for a, r in pts])
    ob, ot, ib, it = loops
    for k in range(n):
        j = (k + 1) % n
        bm.faces.new((ot[k], ot[j], it[j], it[k]))
        bm.faces.new((ob[k], ib[k], ib[j], ob[j]))
        bm.faces.new((ob[k], ob[j], ot[j], ot[k]))
        bm.faces.new((ib[k], it[k], it[j], ib[j]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bmesh.ops.bevel(bm, geom=bm.edges[:], offset=0.006, segments=2, profile=0.5,
                    affect='EDGES', clamp_overlap=True)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    o = bpy.data.objects.new(name, me)
    o.data.materials.append(mat)
    SC.collection.objects.link(o)
    return o


def build_gear(tag, cx, cy, ang, z, R, nt, d, mats, nsp=6, spin=0.0):
    mR, mH, mS, mA, mB = mats
    n = Vector((math.cos(ang), math.sin(ang), 0))
    c = Vector((cx, cy, z)) + n * d
    G = Matrix.Translation(c) @ Matrix.Rotation(ang + math.pi / 2, 4, 'Z') \
        @ Matrix.Rotation(math.pi / 2, 4, 'X') @ Matrix.Rotation(spin, 4, 'Z')
    th = 0.07
    ri = R - 0.16
    o = gear_ring(f'Gear_ring_{tag}', R, ri, nt, th, mR)
    o.matrix_world = G
    hub = CYL(f'Gear_hub_{tag}', (0, 0, 0), R * 0.22, th + 0.04, mH, n=24, r=0.015)
    hub.matrix_world = G
    for s in range(nsp):
        a = 2 * math.pi * s / nsp
        rm = (R * 0.2 + ri + 0.02) / 2
        sp = BOX(f'Gear_spoke_{tag}_{s}', (0, 0, 0), (0.05, ri + 0.02 - R * 0.2, th * 0.7), mS, r=0.012)
        sp.matrix_world = G @ Matrix.Rotation(a, 4, 'Z') @ Matrix.Translation((0, rm, 0))
    ax = CYL(f'Gear_axle_{tag}', (0, 0, 0), 0.045, d + 0.2, mA, n=16, r=0.01)
    ax.matrix_world = G @ Matrix.Translation((0, 0, -(d + 0.2) / 2 + 0.07))
    cap = CYL(f'Gear_cap_{tag}', (0, 0, 0), 0.07, 0.04, mB, n=20, r=0.015)
    cap.matrix_world = G @ Matrix.Translation((0, 0, th / 2 + 0.035))
    for b in range(4):
        a = math.pi / 4 + b * math.pi / 2
        bo = CYL(f'Gear_bolt_{tag}_{b}', (0, 0, 0), 0.018, 0.03, mB, n=12, r=0.006)
        bo.matrix_world = G @ Matrix.Translation((R * 0.15 * math.cos(a), R * 0.15 * math.sin(a), th / 2 + 0.02))
    br = BOX(f'Bracket_gear_{tag}', (0, 0, 0), (R * 0.5, R * 0.5, 0.12), mA, r=0.025)
    br.matrix_world = G @ Matrix.Translation((0, 0, -0.095))
    return 9 + nsp
