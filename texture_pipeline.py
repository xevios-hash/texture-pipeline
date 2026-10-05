"""
texture_pipeline.py  --  run inside Blender:
    blender -b -P texture_pipeline.py -- --mesh in.glb --out out.glb --views 6 --res 1024

Renders the mesh from N orbiting cameras, saves PNGs + manifest.json.
The companion script openrouter_texture.py reads the manifest, calls the
OpenRouter Image API per view, and writes view_N.png back.  Then re-run
this script with --bake to project those views onto the mesh UVs and
export a textured GLB.
"""
import argparse, json, math, os, sys

import bpy
from mathutils import Vector

argv = sys.argv
argv = argv[argv.index("--") + 1:] if "--" in argv else []

p = argparse.ArgumentParser()
p.add_argument("--mesh", required=True)
p.add_argument("--out", required=True)
p.add_argument("--views", type=int, default=6)
p.add_argument("--res", type=int, default=1024)
p.add_argument("--fov", type=float, default=45.0)
p.add_argument("--bake", action="store_true")
p.add_argument("--workdir", default=".")
args = p.parse_args(argv)

WORK = args.workdir
os.makedirs(WORK, exist_ok=True)

def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for m in list(bpy.data.meshes):
        bpy.data.meshes.remove(m)
    for img in list(bpy.data.images):
        bpy.data.images.remove(img)

def import_mesh(path):
    ext = os.path.splitext(path)[1].lower()
    if ext in (".glb", ".gltf"):
        bpy.ops.import_scene.gltf(filepath=path)
    elif ext == ".obj":
        bpy.ops.import_scene.obj(filepath=path)
    elif ext == ".fbx":
        bpy.ops.import_scene.fbx(filepath=path)
    else:
        raise SystemExit(f"unsupported mesh format: {ext}")
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    if not meshes:
        raise SystemExit("no mesh found in file")
    bpy.ops.object.select_all(action="DESELECT")
    for o in meshes:
        o.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    if len(meshes) > 1:
        bpy.ops.object.join()
    obj = bpy.context.view_layer.objects.active
    if not obj.data.uv_layers:
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.uv.unwrap(method="ANGLE_BASED", margin=0.02)
        bpy.ops.object.mode_set(mode="OBJECT")
    return obj

def setup_render(res, fov):
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE_NEXT" if hasattr(bpy.types.Scene, "eevee") else "BLENDER_EEVEE"
    scene.render.resolution_x = res
    scene.render.resolution_y = res
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    cam_data = bpy.data.cameras.new("Cam")
    cam_data.angle = math.radians(fov)
    cam_data.clip_start = 0.01
    cam_data.clip_end = 1000.0
    cam = bpy.data.objects.new("Cam", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    for name, loc, energy in [("Key", (4, -4, 6), 800), ("Fill", (-5, 2, 3), 300), ("Rim", (0, 6, 2), 400)]:
        ldata = bpy.data.lights.new(name, type="AREA")
        ldata.energy = energy
        ldata.size = 4
        l = bpy.data.objects.new(name, ldata)
        l.location = loc
        scene.collection.objects.link(l)
    return cam

def orbit_cameras(obj, n, cam):
    bb = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    center = sum(bb, Vector()) / 8
    radius = max((c - center).length for c in bb) * 2.5
    elev = math.radians(20)
    views = []
    for i in range(n):
        az = 2 * math.pi * i / n
        x = center.x + radius * math.cos(elev) * math.cos(az)
        y = center.y + radius * math.cos(elev) * math.sin(az)
        z = center.z + radius * math.sin(elev)
        cam.location = (x, y, z)
        direction = center - cam.location
        cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
        views.append({
            "index": i,
            "azimuth_deg": math.degrees(az),
            "elevation_deg": math.degrees(elev),
            "camera_location": list(cam.location),
            "target": list(center),
            "fov_deg": math.degrees(cam.data.angle),
            "resolution": [bpy.context.scene.render.resolution_x, bpy.context.scene.render.resolution_y],
        })
    return views, center, radius

def render_views(obj, cam, views, work):
    scene = bpy.context.scene
    for v in views:
        cam.location = v["camera_location"]
        direction = Vector(v["target"]) - cam.location
        cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
        path = os.path.join(work, f"view_{v['index']:02d}.png")
        scene.render.filepath = path
        bpy.ops.render.render(write_still=True)
        v["image"] = os.path.basename(path)

def bake_views(obj, views, work, out_path):
    import numpy as np
    res = views[0]["resolution"][0]
    atlas = bpy.data.images.new("BakedAtlas", width=res, height=res, alpha=True)
    atlas.colorspace_settings.name = "sRGB"
    pixels = np.zeros((res, res, 4), dtype=np.float32)

    view_imgs = []
    for v in views:
        img = bpy.data.images.load(os.path.join(work, v["image"]))
        arr = np.array(img.pixels[:]).reshape((img.size[1], img.size[0], 4))
        view_imgs.append(arr)
        bpy.data.images.remove(img)

    mesh = obj.data
    mesh.calc_loop_triangles()
    tri_view = {}
    for tri in mesh.loop_triangles:
        n = obj.matrix_world.to_3x3() @ tri.normal
        n.normalize()
        best, best_dot = 0, -1
        for i, v in enumerate(views):
            d = Vector(v["target"]) - Vector(v["camera_location"])
            d.normalize()
            dot = n.dot(d)
            if dot > best_dot:
                best_dot, best = dot, i
        tri_view[tri.index] = best

    uv_layer = mesh.uv_layers.active.data
    for tri in mesh.loop_triangles:
        vi = tri_view[tri.index]
        arr = view_imgs[vi]
        h, w = arr.shape[:2]
        uvs = [uv_layer[li].uv for li in tri.loops]
        us = [u.x for u in uvs]; vs = [u.y for u in uvs]
        u0, u1 = max(0, min(us)), min(1, max(us))
        v0, v1 = max(0, min(vs)), min(1, max(vs))
        px0, px1 = int(u0 * w), int(u1 * w)
        py0, py1 = int(v0 * h), int(v1 * h)
        for py in range(py0, py1 + 1):
            for px in range(px0, px1 + 1):
                u = (px + 0.5) / w
                vv = (py + 0.5) / h
                def bary(p, a, b, c):
                    v0_ = b - a; v1_ = c - a; v2_ = p - a
                    dot00 = v0_.dot(v0_); dot01 = v0_.dot(v1__); dot02 = v0_.dot(v2_)
                    dot11 = v1_.dot(v1__); dot12 = v1_.dot(v2_)
                    inv = 1 / (dot00 * dot11 - dot01 * dot01)
                    u_ = (dot11 * dot02 - dot01 * dot12) * inv
                    v_ = (dot00 * dot12 - dot01 * dot02) * inv
                    return (u_ >= -1e-6) and (v_ >= -1e-6) and (u_ + v_ <= 1 + 1e-6)
                a = Vector((uvs[0].x, uvs[0].y)); b = Vector((uvs[1].x, uvs[1].y)); c = Vector((uvs[2].x, uvs[2].y))
                if bary(Vector((u, vv)), a, b, c):
                    sx = int(u * (w - 1)); sy = int(vv * (h - 1))
                    col = arr[sy, sx]
                    if col[3] > pixels[py, px, 3]:
                        pixels[py, px] = col

    pixels = np.flipud(pixels)
    atlas.scale(res, res)
    atlas.pixels = pixels.flatten().tolist()
    atlas.pack()

    if obj.data.materials:
        mat = obj.data.materials[0]
    else:
        mat = bpy.data.materials.new("BakedMat")
        obj.data.materials.append(mat)
    mat.use_nodes = True
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = atlas
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    outn = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    nt.links.new(bsdf.outputs["BSDF"], outn.inputs["Surface"])

    ext = os.path.splitext(out_path)[1].lower()
    if ext == ".glb":
        bpy.ops.export_scene.gltf(filepath=out_path, use_selection=True, export_format="GLB")
    elif ext == ".fbx":
        bpy.ops.export_scene.fbx(filepath=out_path, use_selection=True)
    else:
        bpy.ops.export_scene.obj(filepath=out_path)
    print(f"EXPORTED {out_path}")

clear_scene()
obj = import_mesh(args.mesh)
cam = setup_render(args.res, args.fov)
views, center, radius = orbit_cameras(obj, args.views, cam)

manifest = {"mesh": args.mesh, "out": args.out, "workdir": WORK, "views": views,
            "center": list(center), "radius": radius}
with open(os.path.join(WORK, "manifest.json"), "w") as f:
    json.dump(manifest, f, indent=2)

if args.bake:
    bake_views(obj, views, WORK, args.out)
else:
    render_views(obj, cam, views, WORK)
    print(f"RENDERED {len(views)} views -> {WORK}/view_XX.png + manifest.json")
    print("Next: run openrouter_texture.py, then re-run with --bake")
