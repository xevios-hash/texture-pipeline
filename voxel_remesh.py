"""voxel_remesh.py — run inside Blender.

    blender -b -P voxel_remesh.py -- --mesh in.glb --out out.glb --voxel 0.02

Voxel remesh turns a puffy alpha displacement (or a messy generated mesh)
into a watertight volume. Unlike Displace, this can close gaps and give
real thickness. It destroys UVs, so we re-unwrap after. Any texture baked
before this step is invalid — the agent always re-renders after remesh.
"""
import argparse
import os
import sys

import bpy

argv = sys.argv
argv = argv[argv.index("--") + 1:] if "--" in argv else []
p = argparse.ArgumentParser()
p.add_argument("--mesh", required=True)
p.add_argument("--out", required=True)
p.add_argument("--voxel", type=float, default=0.02, help="voxel size in object units")
p.add_argument("--smooth", type=int, default=2)
args = p.parse_args(argv)

bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)

ext = os.path.splitext(args.mesh)[1].lower()
if ext in (".glb", ".gltf"):
    bpy.ops.import_scene.gltf(filepath=args.mesh)
elif ext == ".obj":
    bpy.ops.wm.obj_import(filepath=args.mesh)
elif ext == ".fbx":
    bpy.ops.import_scene.fbx(filepath=args.mesh)
else:
    raise SystemExit(f"unsupported: {ext}")

meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
if not meshes:
    raise SystemExit("no mesh")
bpy.ops.object.select_all(action="DESELECT")
for o in meshes:
    o.select_set(True)
bpy.context.view_layer.objects.active = meshes[0]
if len(meshes) > 1:
    bpy.ops.object.join()
obj = bpy.context.view_layer.objects.active

# voxel remesh modifier (watertight)
mod = obj.modifiers.new("Voxel", "REMESH")
mod.mode = "VOXEL"
mod.voxel_size = args.voxel
mod.use_smooth_shade = True
bpy.ops.object.modifier_apply(modifier=mod.name)

if args.smooth > 0:
    sm = obj.modifiers.new("Smooth", "SMOOTH")
    sm.iterations = args.smooth
    bpy.ops.object.modifier_apply(modifier=sm.name)

# UVs are gone after remesh — rebuild
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="SELECT")
bpy.ops.uv.smart_project(angle_limit=1.15, island_margin=0.02)
bpy.ops.object.mode_set(mode="OBJECT")

bpy.ops.object.select_all(action="DESELECT")
obj.select_set(True)
bpy.context.view_layer.objects.active = obj
bpy.ops.export_scene.gltf(filepath=args.out, use_selection=True, export_format="GLB")
print(f"VOXEL {args.out} voxel={args.voxel} tris={len(obj.data.polygons)}")
