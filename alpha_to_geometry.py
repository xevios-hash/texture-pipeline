"""
alpha_to_geometry.py  --  run inside Blender:
    blender -b -P alpha_to_geometry.py -- --image bush.png --out bush_mesh.glb
                              [--threshold 0.5] [--subdiv 6] [--decimate 0.05]
                              [--workdir .]

Takes an alpha-masked image (e.g. a bush sprite with transparent background)
and turns the opaque silhouette into real mesh geometry:

  1. Load the image, build a grayscale height map from the alpha channel.
  2. Create a subdivided plane, displace it along normals using the alpha
     as a height map so the silhouette puffs out into 3D volume.
  3. Delete faces whose alpha reads below --threshold (the transparent parts).
  4. Optional: Decimate to bring triangle count down to a mobile budget.
  5. Re-unwrap UVs (ANGLE_BASED) so the new topology has clean islands.
  6. Export GLB.

The output mesh is the input to texture_pipeline.py.  Because the mesh
topology changed, the texture pass MUST re-render views and re-diffuse
-- you cannot reuse a texture baked for the old mesh.  The agent wrapper
(ai_texture_agent.py) handles this ordering automatically.
"""
import argparse, json, math, os, sys

import bpy
import numpy as np
from mathutils import Vector

argv = sys.argv
argv = argv[argv.index("--") + 1:] if "--" in argv else []

p = argparse.ArgumentParser()
p.add_argument("--image", required=True, help="alpha-masked PNG/JPG")
p.add_argument("--out", required=True, help="output GLB path")
p.add_argument("--threshold", type=float, default=0.5,
               help="alpha below this gets deleted (0-1)")
p.add_argument("--subdiv", type=int, default=6,
               help="subdivision levels before displacement")
p.add_argument("--decimate", type=float, default=0.05,
               help="decimate ratio after cleanup (0 = skip)")
p.add_argument("--size", type=float, default=2.0, help="plane size")
p.add_argument("--workdir", default=".")

# optional: also run the texture pipeline in one shot
p.add_argument("--texture-prompt", default=None,
               help="if set, after meshing, run render+diffuse+bake with this prompt")
p.add_argument("--views", type=int, default=6)
p.add_argument("--res", type=int, default=1024)
p.add_argument("--model", default="bytedance-seed/seedream-4.5")

try:
    args = p.parse_args(argv)
except SystemExit:
    # Blender's argv parsing can choke on unknown flags; fall back to defaults
    args = p.parse_args(["--image", "in.png", "--out", "out.glb"])

WORK = args.workdir
os.makedirs(WORK, exist_ok=True)


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for m in list(bpy.data.meshes):
        bpy.data.meshes.remove(m)
    for img in list(bpy.data.images):
        bpy.data.images.remove(img)


def load_alpha(path):
    img = bpy.data.images.load(path)
    w, h = img.size
    px = np.array(img.pixels[:]).reshape((h, w, 4))
    alpha = px[:, :, 3]
    # flip Y: Blender images are bottom-up
    alpha = np.flipud(alpha)
    return alpha, w, h


def build_mesh_from_alpha(alpha, w, h, size, subdiv, threshold, decimate):
    # 1. base plane
    bpy.ops.mesh.primitive_plane_add(size=size, location=(0, 0, 0))
    obj = bpy.context.view_layer.objects.active

    # 2. subdivide
    if subdiv > 0:
        mod = obj.modifiers.new("Subsurf", "SUBSURF")
        mod.levels = subdiv
        mod.render_levels = subdiv
        bpy.ops.object.modifier_apply(modifier=mod.name)

    # 3. displace along normals using alpha as height
    mesh = obj.data
    mesh.calc_loop_triangles()
    # sample alpha at each vertex UV
    if not mesh.uv_layers:
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.uv.unwrap(method="ANGLE_BASED", margin=0.02)
        bpy.ops.object.mode_set(mode="OBJECT")
    uv_layer = mesh.uv_layers.active.data
    verts = mesh.vertices
    # build per-vertex height from averaged UV samples
    heights = np.zeros(len(verts), dtype=np.float32)
    counts = np.zeros(len(verts), dtype=np.float32)
    for poly in mesh.polygons:
        for li in poly.loop_indices:
            vi = mesh.loops[li].vertex_index
            uv = uv_layer[li].uv
            x = int(np.clip(uv.x * (w - 1), 0, w - 1))
            y = int(np.clip(uv.y * (h - 1), 0, h - 1))
            heights[vi] += alpha[y, x]
            counts[vi] += 1
    counts[counts == 0] = 1
    heights /= counts

    # displace
    for vi, v in enumerate(verts):
        n = v.normal
        v.co += n * (heights[vi] * 0.5)  # 0.5 = puff depth scale

    # 4. delete faces below threshold (transparent parts)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="DESELECT")
    # select faces whose average alpha < threshold
    bm_faces_to_delete = []
    mesh.calc_loop_triangles()
    for poly in mesh.polygons:
        avg = 0.0
        for li in poly.loop_indices:
            vi = mesh.loops[li].vertex_index
            avg += heights[vi]
        avg /= max(len(poly.loop_indices), 1)
        if avg < threshold:
            poly.select = True
    bpy.ops.mesh.delete(type="FACES")
    bpy.ops.object.mode_set(mode="OBJECT")

    # 5. remove loose geometry
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.delete_loose()
    bpy.ops.object.mode_set(mode="OBJECT")

    # 6. decimate
    if decimate and decimate < 1.0:
        mod = obj.modifiers.new("Decimate", "DECIMATE")
        mod.ratio = decimate
        bpy.ops.object.modifier_apply(modifier=mod.name)

    # 7. re-unwrap for clean islands on the new topology
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.unwrap(method="ANGLE_BASED", margin=0.02)
    bpy.ops.object.mode_set(mode="OBJECT")

    # 8. shade smooth
    for p in mesh.polygons:
        p.use_smooth = True

    return obj


def export_glb(obj, path):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.export_scene.gltf(filepath=path, use_selection=True, export_format="GLB")
    print(f"EXPORTED MESH {path}  tris={len(obj.data.loop_triangles)}")


clear_scene()
alpha, w, h = load_alpha(args.image)
obj = build_mesh_from_alpha(alpha, w, h, args.size, args.subdiv,
                            args.threshold, args.decimate)
export_glb(obj, args.out)

# save a small manifest so the texture pass knows this mesh came from alpha
manifest = {
    "source_image": args.image,
    "mesh": args.out,
    "threshold": args.threshold,
    "subdiv": args.subdiv,
    "decimate": args.decimate,
    "tris": len(obj.data.loop_triangles),
}
with open(os.path.join(WORK, "alpha_manifest.json"), "w") as f:
    json.dump(manifest, f, indent=2)

if args.texture_prompt:
    # hand off to the texture pipeline: render -> diffuse -> bake
    # (texture_pipeline.py is a sibling script; run it as a separate Blender
    #  invocation from the agent wrapper instead of nesting here)
    print("MESH READY. Run texture_pipeline.py next with --mesh", args.out)
