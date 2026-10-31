"""从 all_plots.blend 里单独导出某个场景为 glb（独立进程，不占 MCP，不改模型）。
用法：blender -b <blend> --python export_scene_glb.py -- <scene> <out_glb>
"""
import bpy, os, sys, json, struct

argv = sys.argv[sys.argv.index("--") + 1:]
scene_name, out_path = argv[0], argv[1]

sc = bpy.data.scenes.get(scene_name)
if not sc:
    print("NO_SCENE", scene_name)
    sys.exit(1)

# 后台模式下切 window.scene 经常静默失败，导致导出成"当前活动场景"（混进别的地块）。
# 最稳的做法：把其它场景直接从文件里删掉，只留目标场景再导出。
for other in list(bpy.data.scenes):
    if other.name != scene_name:
        bpy.data.scenes.remove(other)
try:
    for w in bpy.context.window_manager.windows:
        w.scene = sc
except Exception:
    pass

# 只导出可见对象，确保顶点色 AO 带上
bpy.ops.object.select_all(action="DESELECT")
# 全部对象都选上（包括隐藏的季节孪生件），否则四季切换会缺件
for o in sc.objects:
    try:
        o.hide_set(False)
        o.hide_viewport = False
        o.hide_render = False
        o.select_set(True)
    except Exception:
        pass

kw = dict(
    filepath=out_path,
    export_format="GLB",
    use_selection=True,
    use_visible=False,
    export_extras=True,
    export_apply=True,
    export_yup=True,
)
try:
    kw["export_vertex_color"] = "ACTIVE"
    kw["export_all_vertex_colors"] = True
except Exception:
    pass
try:
    kw["export_image_format"] = "AUTO"
    kw["export_materials"] = "EXPORT"
except Exception:
    pass

bpy.ops.export_scene.gltf(**kw)

if not os.path.exists(out_path):
    print("EXPORT_FAILED")
    sys.exit(2)

d = open(out_path, "rb").read()
n = struct.unpack("<I", d[12:16])[0]
js = json.loads(d[20:20 + n])
names = [x.get("name", "") for x in js["nodes"]]
print("EXPORTED", out_path)
print("MB", round(len(d) / 1048576, 1),
      "| 节点", len(js["nodes"]),
      "| 网格", len([x for x in js["nodes"] if "mesh" in x]),
      "| 材质", len(js.get("materials", [])),
      "| 贴图", len(js.get("images", [])),
      "| Loop", len([x for x in names if x.startswith("Loop_")]),
      "| Geng", len([x for x in names if x.startswith("Geng")]),
      "| Glass", len([m.get("name", "") for m in js.get("materials", [])
                      if m.get("name", "").lower().startswith("glass")]))
