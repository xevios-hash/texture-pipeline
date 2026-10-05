"""
alpha_to_geometry.py  --  pre-pass: turn an alpha-masked image into a mesh.

Two modes:
  --mode plane   Subdivide a plane heavily, delete faces where the alpha
                 channel reads below --threshold, then decimate.  Good for
                 flat cards (bushes, leaves, decals) where the silhouette
                 lives in the alpha.
  --mode sprite  Connected-component scan of the alpha channel: each
                 separate opaque blob becomes its own mesh, placed at its
                 centroid.  Good for sprite sheets with multiple props.

Usage:
    blender -b -P alpha_to_geometry.py -- --image bush.png --out bush.glb \
        --mode plane --subdiv 8 --threshold 0.5 --decimate 0.05

The output GLB is the input to texture_pipeline.py / ai_texture_agent.py.
"""
import argparse, os, sys

import bpy
import numpy as np
from mathutils import Vector

argv = sys.argv
argv = argv[argv.index("--") + 1:] if "--" in argv else []

p = argparse.ArgumentParser()
p.add_argument("--image", required=True, help="PNG with alpha channel")
p.add_argument("--out", required=True, help="output GLB path")
p.add_argument("--mode", choices=["plane", "sprite"], default="plane")
p.add_argument("--subdiv", type=int, default=8, help="subdivision levels for plane mode")
p.add_argument("--threshold", type=float, default=0.5, help="alpha cutoff 0-1")
p.add_argument("--decimate", type=float, default=0.05, help="decimate ratio (0.05 = keep 5%%)")
p.add_argument("--size", type=float, default=2.0, help="plane size in Blender units")
p.add_argument("--min-area", type=int, default=50, help="min blob area in px for sprite mode")


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for m in list(bpy.data.meshes):
        bpy.data.meshes.remove(m)


def load_alpha(path):
    img = bpy.data.images.load(path)
    w, h = img.size
    px = np.array(img.pixels[:]).reshape((h, w, 4))
    alpha = px[:, :, 3]
    # flip Y: Blender images are bottom-up
    alpha = np.flipud(alpha)
    return alpha, w, h


def plane_mode(alpha, w, h, subdiv, threshold, size):
    """Subdivide a plane, delete faces below alpha threshold."""
    bpy.ops.mesh.primitive_plane_add(size=size)
    obj = bpy.context.view_layer.objects.active
    # subdivide
    bpy.ops.object.mode_set(mode="EDIT")
    for _ in range(subdiv):
        bpy.ops.mesh.subdivide()
    bpy.ops.object.mode_set(mode="OBJECT")

    mesh = obj.data
    mesh.calc_loop_triangles()

    # map each triangle's centroid UV -> alpha sample
    uv_layer = mesh.uv_layers.active.data
    to_delete = set()
    for tri in mesh.loop_triangles:
        uvs = [uv_layer[li].uv for li in tri.loops]
        cu = sum(u.x for u in uvs) / 3
        cv = sum(u.y for u in uvs) / 3
        px = int(cu * (w - 1))
        py = int(cv * (h - 1))
        px = max(0, min(w - 1, px))
        py = max(0, min(h - 1, py))
        if alpha[py, px] < threshold:
            to_delete.add(tri.index)

    # delete triangles: select their verts in edit mode
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="DESELECT")
    bm_tris = mesh.loop_triangles
    # use bmesh for reliable deletion
    import bmesh
    bm = bmesh.from_edit_mesh(mesh)
    bm.faces.ensure_lookup_table()
    # map triangle index -> face via loops
    tri_to_face = {tri.index: tri.material_index for tri in bm_tris}  # placeholder
    # simpler: delete by selecting verts of low-alpha triangles
    bpy.ops.object.mode_set(mode="OBJECT")
    # rebuild via bmesh delete
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.faces.ensure_lookup_table()
    # map each face to its triangle index via loop triangles
    mesh.calc_loop_triangles()
    face_of_tri = []
    for tri in mesh.loop_triangles:
        # find face containing this triangle's first loop
        li = tri.loops[0]
        face_of_tri.append(li.face.index)
    to_del = set(face_of_tri[i] for i in to_delete)
    for fi in sorted(to_del, reverse=True):
        bm.faces.remove(bm.faces[fi])
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    return obj


def sprite_mode(alpha, w, h, min_area, size):
    """Connected components -> one mesh per blob."""
    mask = (alpha >= 0.5).astype(np.uint8)
    # flood fill
    visited = np.zeros_like(mask, dtype=bool)
    blobs = []
    dirs = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    for y in range(h):
        for x in range(w):
            if mask[y, x] and not visited[y, x]:
                stack = [(y, x)]
                visited[y, x] = True
                cells = []
                while stack:
                    cy, cx = stack.pop()
                    cells.append((cy, cx))
                    for dy, dx in dirs:
                        ny, nx = cy + dy, cx + dx
                        if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not visited[ny, nx]:
                            visited[ny, nx] = True
                            stack.append((ny, nx))
                if len(cells) >= min_area:
                    blobs.append(cells)
    print(f"found {len(blobs)} blobs (min area {min_area} px)")

    objects = []
    for i, cells in enumerate(blobs):
        ys = [c[0] for c in cells]; xs = [c[1] for c in cells]
        y0, y1 = min(ys), max(ys)
        x0, x1 = min(xs), max(xs)
        bw, bh = max(1, x1 - x0 + 1), max(1, y1 - y0 + 1)
        # build a plane scaled to the blob's bounding box, positioned at centroid
        cx = (x0 + x1) / 2 / w * size - size / 2
        cy = (y0 + y1) / 2 / h * size - size / 2
        sx = bw / w * size
        sy = bh / h * size
        bpy.ops.mesh.primitive_plane_add(size=1, location=(cx, cy, 0))
        obj = bpy.context.view_layer.objects.active
        obj.scale = (sx, sy, 1)
        # subdivide so the blob shape can be approximated
        bpy.ops.object.mode_set(mode="EDIT")
        for _ in range(4):
            bpy.ops.mesh.subdivide()
        bpy.ops.object.mode_set(mode="OBJECT")
        # delete faces outside the blob mask (sample UV)
        mesh = obj.data
        mesh.calc_loop_triangles()
        uv_layer = mesh.uv_layers.active.data
        to_delete = set()
        for tri in mesh.loop_triangles:
            uvs = [uv_layer[li].uv for li in tri.loops]
            cu = sum(u.x for u in uvs) / 3
            cv = sum(u.y for u in uvs) / 3
            # map UV back to blob-local pixel
            px = int(x0 + cu * bw)
            py = int(y0 + cv * bh)
            px = max(x0, min(x1, px)); py = max(y0, min(y1, py))
            if mask[py, px] < 1:
                to_delete.add(tri.index)
        import bmesh
        bm = bmesh.new()
        bm.from_mesh(mesh)
        bm.faces.ensure_lookup_table()
        mesh.calc_loop_triangles()
        face_of_tri = [tri.loops[0].face.index for tri in mesh.loop_triangles]
        for fi in sorted(set(face_of_tri[i] for i in to_delete), reverse=True):
            bm.faces.remove(bm.faces[fi])
        bm.to_mesh(mesh)
        bm.free()
        mesh.update()
        obj.name = f"blob_{i:03d}"
        objects.append(obj)
    return objects


def decimate(obj, ratio):
    mod = obj.modifiers.new(name="Decimate", type="DECIMATE")
    mod.ratio = ratio
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier="Decimate")


def export_glb(path):
    # select all mesh objects
    bpy.ops.object.select_all(action="DESELECT")
    for o in bpy.context.scene.objects:
        if o.type == "MESH":
            o.select_set(True)
    if not bpy.context.selected_objects:
        raise SystemExit("no mesh to export")
    bpy.context.view_layer.objects.active = bpy.context.selected_objects[0]
    bpy.ops.export_scene.gltf(filepath=path, use_selection=True, export_format="GLB")
    print(f"EXPORTED {path}")


clear_scene()

alpha, w, h = load_alpha(args.image)
print(f"loaded {args.image} ({w}x{h}), alpha range {alpha.min():.2f}-{alpha.max():.2f}")

if args.mode == "plane":
    obj = plane_mode(alpha, w, h, args.subdiv, args.threshold, args.size)
    decimate(obj, args.decimate)
    print(f"plane mode: {len(obj.data.polygons)} faces after decimate")
else:
    objects = sprite_mode(alpha, w, h, args.min_area, args.size)
    for o in objects:
        decimate(o, args.decimate)
    print(f"sprite mode: {len(objects)} objects")

export_glb(args.out)
