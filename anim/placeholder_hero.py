"""placeholder_hero.py — Blender. A capsule with idle and walk, no Mixamo.

    blender -b -P anim/placeholder_hero.py -- --out assets/hero.glb
"""
import argparse
import math
import os
import sys

import bpy

argv = sys.argv
argv = argv[argv.index("--") + 1:] if "--" in argv else []
p = argparse.ArgumentParser()
p.add_argument("--out", required=True)
args = p.parse_args(argv)

bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)

bpy.ops.mesh.primitive_cylinder_add(radius=0.3, depth=1.2, location=(0, 0, 0.9))
body = bpy.context.object
body.name = "hero"

def add_action(name, period, amount):
    action = bpy.data.actions.new(name)
    body.animation_data_create()
    body.animation_data.action = action
    fcu = action.fcurves.new(data_path="location", index=2)
    fcu.keyframe_points.add(3)
    base = 0.9
    keys = [(0.0, base), (period / 2, base + amount), (period, base)]
    for i, (t, v) in enumerate(keys):
        fcu.keyframe_points[i].co = (t, v)
        fcu.keyframe_points[i].interpolation = "BEZIER"
    # keep the action on the object as a slot Godot can see
    track = body.animation_data.nla_tracks.new()
    track.name = name
    strip = track.strips.new(name, 0, action)
    strip.name = name
    return action

idle = add_action("idle", 1.2, 0.04)
walk = add_action("walk", 0.4, 0.12)
# last assignment sticks; push both into the NLA so export keeps them
body.animation_data.action = idle

os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
bpy.ops.export_scene.gltf(
    filepath=args.out,
    export_format="GLB",
    export_animations=True,
    export_nla_strips=True,
)
print(f"HERO {args.out}")
