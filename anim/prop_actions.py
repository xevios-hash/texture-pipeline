"""prop_actions.py — Blender. Animate named parts. No skeleton.

    blender -b -P anim/prop_actions.py -- --spec anim/clips.example.json

The mesh must already contain an object whose name matches action.object
(the LLM names the parts when it builds the GLB, or you split in Blender).
Keys are seconds and radians. Exports a GLB with actions.
"""
import argparse
import json
import os
import sys

import bpy

argv = sys.argv
argv = argv[argv.index("--") + 1:] if "--" in argv else []
p = argparse.ArgumentParser()
p.add_argument("--spec", required=True)
args = p.parse_args(argv)

spec = json.loads(open(args.spec, encoding="utf-8").read())
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)

src = spec["asset"]
ext = os.path.splitext(src)[1].lower()
if ext in (".glb", ".gltf"):
    bpy.ops.import_scene.gltf(filepath=src)
elif ext == ".fbx":
    bpy.ops.import_scene.fbx(filepath=src)
else:
    raise SystemExit(f"unsupported {ext}")

by_name = {o.name: o for o in bpy.context.scene.objects}
for action_spec in spec.get("actions", []):
    obj = by_name.get(action_spec["object"])
    if obj is None:
        print(f"MISSING {action_spec['object']}")
        continue
    action = bpy.data.actions.new(action_spec["name"])
    obj.animation_data_create()
    obj.animation_data.action = action
    axis = int(action_spec.get("axis", 0))
    data_path = action_spec.get("channel", "rotation_euler")
    fcu = action.fcurves.new(data_path=data_path, index=axis)
    fcu.keyframe_points.add(len(action_spec["keys"]))
    for i, (t, v) in enumerate(action_spec["keys"]):
        fcu.keyframe_points[i].co = (float(t), float(v))
        fcu.keyframe_points[i].interpolation = "BEZIER"
    print(f"ACTION {action_spec['name']} on {obj.name}")

out = spec["out"]
os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
bpy.ops.export_scene.gltf(filepath=out, export_format="GLB", export_animations=True)
print(f"WROTE {out}")
