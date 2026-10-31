"""独立进程渲染一块地（不改动主 Blender，崩了也不影响建模会话）。
用法：blender -b all_plots.blend --python render_plot.py -- <scene> <outname>
"""
import bpy, sys, os

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
scene_name, out_name = argv[0], argv[1]
winter = len(argv) > 2 and argv[2] == "winter"

sc = bpy.data.scenes.get(scene_name)
if not sc:
    print("NO_SCENE", scene_name); sys.exit(1)

bpy.context.window.scene = sc if bpy.context.window else None
for o in bpy.context.view_layer.objects:
    pass

# 相机：优先 CAM_iso.<scene>
cam = None
for o in sc.objects:
    if o.type == "CAMERA" and o.name.startswith("CAM_iso"):
        cam = o
if cam:
    sc.camera = cam

# 冬季：切到雪季可见性
if winter:
    for o in sc.objects:
        n = o.name
        if n.startswith("Snow_") or n.startswith("Bare_"):
            o.hide_render = False
        elif n.startswith("Foliage_"):
            o.hide_render = True

r = sc.render
r.resolution_x, r.resolution_y, r.resolution_percentage = 960, 720, 100
r.film_transparent = False
try:
    r.engine = "BLENDER_EEVEE_NEXT"
    r.image_settings.file_format = "PNG"
except Exception:
    pass
r.filepath = os.path.join(r"D:/hermes/home/out/renders", out_name)
bpy.ops.render.render(write_still=True)
print("RENDERED", r.filepath)
