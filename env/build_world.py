"""build_world.py — Blender. Rebuild a world from JSON. Idempotent.

    blender -b -P env/build_world.py -- --spec env/world.example.json --out worlds/clearing.glb

Edit the JSON to iterate. Do not regenerate meshes to move a prop.
Terrain is a displaced grid. Instances snap to the terrain height.
Scatter is deterministic from seed.
"""
import argparse
import json
import math
import os
import random
import sys

import bpy

argv = sys.argv
argv = argv[argv.index("--") + 1:] if "--" in argv else []
p = argparse.ArgumentParser()
p.add_argument("--spec", required=True)
p.add_argument("--out", required=True)
args = p.parse_args(argv)

spec = json.loads(open(args.spec, encoding="utf-8").read())
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)

terrain = spec.get("terrain", {"size": 32, "step": 1.0, "amplitude": 0.4, "seed": 1})
size = float(terrain["size"])
step = float(terrain.get("step", 1.0))
amp = float(terrain.get("amplitude", 0.4))
n = max(2, int(size / step))


def height(x, z):
    return amp * (
        math.sin(x * 0.35 + terrain.get("seed", 1)) * 0.5
        + math.cos(z * 0.27) * 0.5
    )


mesh = bpy.data.meshes.new("terrain")
obj = bpy.data.objects.new("terrain", mesh)
bpy.context.collection.objects.link(obj)
verts, faces = [], []
for iz in range(n):
    for ix in range(n):
        x = -size / 2 + ix * step
        z = -size / 2 + iz * step
        verts.append((x, z, height(x, z)))
for iz in range(n - 1):
    for ix in range(n - 1):
        a = iz * n + ix
        faces.append((a, a + 1, a + n + 1, a + n))
mesh.from_pydata(verts, [], faces)
mesh.update()


def place(asset, name, at, rot_y, scale):
    if not os.path.exists(asset):
        print(f"SKIP missing {asset}")
        return
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=asset)
    new = [o for o in bpy.data.objects if o not in before]
    if not new:
        return
    parent = new[0]
    parent.name = name
    x, y, z = at
    parent.location = (x, z, height(x, z) + y)
    parent.rotation_euler[2] = math.radians(rot_y)
    parent.scale = (scale, scale, scale)


for inst in spec.get("instances", []):
    place(inst["asset"], inst.get("name", "inst"), inst["at"], inst.get("rot_y", 0), inst.get("scale", 1))

for sc in spec.get("scatter", []):
    rng = random.Random(sc.get("seed", 1))
    x0, z0, x1, z1 = sc["region"]
    lo, hi = sc.get("scale", [1, 1])
    avoid = sc.get("avoid", [])
    for i in range(int(sc.get("count", 0))):
        for _ in range(8):
            x = rng.uniform(x0, x1)
            z = rng.uniform(z0, z1)
            if any((x - a[0]) ** 2 + (z - a[1]) ** 2 < a[2] ** 2 for a in avoid):
                continue
            place(sc["asset"], f"scatter_{i}", [x, 0, z], rng.uniform(0, 360), rng.uniform(lo, hi))
            break

os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
bpy.ops.export_scene.gltf(filepath=args.out, export_format="GLB")
print(f"WORLD {args.out}")
