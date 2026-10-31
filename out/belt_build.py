exec(open('D:/hermes/home/out/belt_lib.py', encoding='utf-8').read())

def segs(pts):
    out = []
    for i in range(len(pts) - 1):
        a, b = Vector((*pts[i], 0)), Vector((*pts[i+1], 0))
        d = (b - a).normalized()
        ts = te = 0  # turn sign at start / end (+1 left turn)
        if i > 0:
            dp = (a - Vector((*pts[i-1], 0))).normalized(); ts = 1 if dp.cross(d).z > 0 else -1
        if i < len(pts) - 2:
            dn = (Vector((*pts[i+2], 0)) - b).normalized(); te = 1 if d.cross(dn).z > 0 else -1
        out.append((a, b, d, (b - a).length, ts, te))
    return out

def side_ext(t, side, w):
    # side +1 = left. inner side of a left turn is left
    if t == 0: return 0.0
    return -w if t == side else w

def build_long(pre, pts):
    S = segs(pts)
    for side, rn, gn in ((1, 'railA', 'guardL'), (-1, 'railB', 'guardR')):
        bmr, bmg = bmesh.new(), bmesh.new()
        for a, b, d, L, ts, te in S:
            M = frame(a, d)
            x0 = -side_ext(ts, side, 0.51); x1 = L + side_ext(te, side, 0.51)
            def Y(u0, u1): return (u0, u1) if side > 0 else (-u1, -u0)
            box(bmr, M, x0, x1, *Y(0.45, 0.475), 0.33, 0.55, 0.008)   # web
            box(bmr, M, x0, x1, *Y(0.45, 0.51), 0.525, 0.55, 0.008)   # top flange
            box(bmr, M, x0, x1, *Y(0.45, 0.51), 0.33, 0.355, 0.008)   # bottom flange
            box(bmr, M, x0, x1, *Y(0.49, 0.51), 0.33, 0.37, 0.006)    # bottom lip
            box(bmr, M, x0, x1, *Y(0.49, 0.51), 0.51, 0.55, 0.006)    # top lip
            box(bmg, M, x0, x1, *Y(0.45, 0.49), 0.55, 0.67, 0.015)    # guard
        obj(pre + rn, bmr, 'VB_leg'); obj(pre + gn, bmg, 'VB_guard')
    bm = bmesh.new()
    for a, b, d, L, ts, te in S:
        M = frame(a, d)
        x0 = HW if ts else 0.0
        x1 = L + (HW if te else 0.0)
        box(bm, M, x0, x1, -0.45, 0.45, 0.40, 0.47, 0.012)  # bed plate
    obj(pre + 'bed', bm, 'VB_belt')
    return S

def build_slats(pre, S):
    k = 0
    for a, b, d, L, ts, te in S:
        M0 = frame(a, d)
        x0 = HW if ts else 0.0; x1 = L + (HW if te else 0.0)
        n = int((x1 - x0 - 0.06) / 0.12)
        for j in range(n):
            x = x0 + 0.06 + 0.12 * j
            k += 1; bm = bmesh.new()
            M = M0 @ Matrix.Translation((x, 0, 0.505))
            cyl(bm, M, 0.045, 0.84, 14, 0.01)
            cyl(bm, M, 0.016, 0.90, 8)        # axle stub
            obj('%sslat_%02d' % (pre, k), bm, 'VB_belt')
    return k

def build_legs(pre, S, step=1.5, first=0.5):
    k = 0; s0 = 0.0; nxt = first
    for a, b, d, L, ts, te in S:
        M0 = frame(a, d)
        while nxt <= s0 + L - 0.2:
            x = nxt - s0
            k += 1; bm = bmesh.new(); M = M0 @ Matrix.Translation((x, 0, 0))
            for u in (-0.41, 0.41):
                box(bm, M, -0.04, 0.04, u - 0.04, u + 0.04, 0.06, 0.40, 0.01)   # post 0.08
                box(bm, M, -0.11, 0.11, u - 0.11, u + 0.11, 0.02, 0.06, 0.012)  # pad
                for sx in (-0.07, 0.07):
                    for sy in (-0.07, 0.07):
                        cyl(bm, M @ Matrix.Translation((sx, u + sy, 0.065)) @ Matrix.Rotation(math.pi/2, 4, 'X'), 0.012, 0.014, 6)
            box(bm, M, -0.025, 0.025, -0.37, 0.37, 0.17, 0.22, 0.008)   # cross brace
            box(bm, M, -0.06, 0.06, -0.47, 0.47, 0.37, 0.40, 0.008)     # head plate
            obj('%sleg%02d' % (pre, k), bm, 'VB_leg')
            nxt += step
        s0 += L
    return k

def build_flange(name, p, d, z=0.52):
    bm = bmesh.new(); M = frame(p, d)
    box(bm, M, -0.03, 0.03, -0.5, 0.5, z + 0.40, z + 0.50, 0.012)
    box(bm, M, -0.03, 0.03, -0.5, 0.5, z - 0.50, z - 0.40, 0.012)
    box(bm, M, -0.03, 0.03, -0.5, -0.40, z - 0.40, z + 0.40, 0.012)
    box(bm, M, -0.03, 0.03, 0.40, 0.5, z - 0.40, z + 0.40, 0.012)
    for u in (-0.45, 0.45):
        for w in (-0.45, 0.45):
            R = M @ Matrix.Translation((0, u, z + w)) @ Matrix.Rotation(-math.pi/2, 4, 'Z')
            cyl(bm, R, 0.018, 0.12, 8)
            for sx in (-0.045, 0.045):
                cyl(bm, R @ Matrix.Translation((0, sx, 0)), 0.035, 0.024, 6, 0.004)  # hex head / nut
    obj(name, bm, 'VB_flange')

def build_all(pre, pts):
    S = build_long(pre, pts)
    ns = build_slats(pre, S); nl = build_legs(pre, S)
    a = S[0]; z = S[-1]
    build_flange(pre + 'flange_src', a[0] + a[2] * 0.03, a[2])
    build_flange(pre + 'flange', z[1] - z[2] * 0.03, z[2])
    print(pre, 'segs', len(S), 'slats', ns, 'legs', nl, 'objs', len(NEW))
