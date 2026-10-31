"""一次性诊断：找出窗户区域内彼此过近（<0.005）的对象对，即 z-fighting 嫌疑。"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
import bpy
from mathutils import Vector

# 直接跑 build_post 的建模部分：执行脚本到导出前
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'build_post.py'), encoding='utf-8').read()
src = src.replace("export_glb('out/models/post.glb'", "_SKIP_EXPORT = ('out/models/post.glb'")
exec(compile(src, 'build_post_skip.py', 'exec'), {'__name__': '__diag__', '__file__': os.path.abspath(__file__)})

bpy.context.view_layer.update()

def wbbox(o):
    pts = [o.matrix_world @ Vector(c) for c in o.bound_box]
    mn = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    mx = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return mn, mx

wins = [o for o in bpy.data.objects if o.type == 'MESH' and (o.name.startswith('Win_') or o.name.startswith('Wall_Front') or o.name.startswith('Sill'))]
print('[DIAG] window-area objects:', len(wins))
boxes = {o.name: wbbox(o) for o in wins}

def gap(a, b):
    (amn, amx), (bmn, bmx) = a, b
    # 每个轴上的分离距离（0 表示在该轴上重叠）
    dx = max(0.0, max(amn.x - bmx.x, bmn.x - amx.x))
    dy = max(0.0, max(amn.y - bmx.y, bmn.y - amx.y))
    dz = max(0.0, max(amn.z - bmz.z if False else 0, 0))
    dz = max(0.0, max(amn.z - bmx.z, bmn.z - amx.z))
    return (dx*dx + dy*dy + dz*dz) ** 0.5

near = []
names = list(boxes)
for i in range(len(names)):
    for j in range(i + 1, len(names)):
        g = gap(boxes[names[i]], boxes[names[j]])
        if g < 0.005:
            near.append((names[i], names[j], round(g, 4)))
print('[DIAG] pairs with gap < 0.005:', len(near))
for n in near[:30]:
    print('   ', n)
