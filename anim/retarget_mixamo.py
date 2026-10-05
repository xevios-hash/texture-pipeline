"""retarget_mixamo.py — Blender. Copy a Mixamo clip onto a Mixamo-spec rig.

    blender -b -P anim/retarget_mixamo.py -- --mesh hero.fbx --clip clips/walk.fbx --out hero_walk.glb --name walk

UniRig's Mixamo spec and a Mixamo download share bone names (mixamorig:Hips).
This copies F-curves by name. It does not solve a different skeleton.
Drop clips in clips/. Do not generate them.
"""
import argparse
import os
import sys

import bpy

argv = sys.argv
argv = argv[argv.index("--") + 1:] if "--" in argv else []
p = argparse.ArgumentParser()
p.add_argument("--mesh", required=True)
p.add_argument("--clip", required=True)
p.add_argument("--out", required=True)
p.add_argument("--name", default="clip")
args = p.parse_args(argv)


def import_any(path):
    ext = os.path.splitext(path)[1].lower()
    before = set(bpy.data.objects)
    if ext == ".fbx":
        bpy.ops.import_scene.fbx(filepath=path)
    elif ext in (".glb", ".gltf"):
        bpy.ops.import_scene.gltf(filepath=path)
    else:
        raise SystemExit(ext)
    return [o for o in bpy.data.objects if o not in before]


def armature_of(objs):
    for o in objs:
        if o.type == "ARMATURE":
            return o
    return None


bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)

target_objs = import_any(args.mesh)
target = armature_of(target_objs)
if target is None:
    raise SystemExit("target has no armature — rig it before retarget")

clip_objs = import_any(args.clip)
source = armature_of(clip_objs)
if source is None or not source.animation_data or not source.animation_data.action:
    raise SystemExit("clip has no armature action")

src_action = source.animation_data.action
dst = bpy.data.actions.new(args.name)
target_bones = {b.name for b in target.data.bones}
copied = 0
for fcu in src_action.fcurves:
    # pose.bones["mixamorig:Hips"].rotation_quaternion
    if not fcu.data_path.startswith("pose.bones["):
        continue
    bone = fcu.data_path.split('"')[1]
    if bone not in target_bones:
        continue
    nf = dst.fcurves.new(data_path=fcu.data_path, index=fcu.array_index)
    nf.keyframe_points.add(len(fcu.keyframe_points))
    for i, kp in enumerate(fcu.keyframe_points):
        nf.keyframe_points[i].co = kp.co
        nf.keyframe_points[i].interpolation = kp.interpolation
    copied += 1

target.animation_data_create()
target.animation_data.action = dst
print(f"COPIED {copied} curves as {args.name}")

for o in clip_objs:
    bpy.data.objects.remove(o, do_unlink=True)

bpy.ops.export_scene.gltf(filepath=args.out, export_format="GLB", export_animations=True)
print(f"WROTE {args.out}")
