# OpenCode instructions

This repo is a texture pipeline, not a 3D generator. Do not call Meshy, Tripo, Hunyuan, or shape_gen.py.

## What to run

One command. Do not reimplement the steps.

macOS:

```bash
./run_pipeline.sh <out.glb> "<surface prompt>" --primitive plane
```

Windows:

```bat
run_pipeline.bat <out.glb> "<surface prompt>" --primitive plane
```

Flags:

- `--primitive plane` for foliage, sprites, cards. Default.
- `--primitive cube` for boxes. Add `--no-displace` if the silhouette should stay a cube.
- `--mesh path.glb` if you already wrote a GLB. Skip `--primitive` in that case.
- `--voxel 0.03` only if the user asked for a closed volume. It spends the image budget twice.
- `--model` only if the user names an OpenRouter image model. Default is `bytedance-seed/seedream-4.5`.

## Required environment

- `OPENROUTER_API_KEY` must already be set. Do not ask the user to paste it into a file. Do not echo it.
- `BLENDER_BIN` if `blender` is not on PATH. macOS default is `/Applications/Blender.app/Contents/MacOS/Blender`.

## Order, if you have to debug a single stage

1. `primitive_mesh.py` writes the GLB.
2. `texture_pipeline.py` renders views.
3. `openrouter_texture.py` paints them.
4. `texture_pipeline.py --bake` writes the GLB.
5. `alpha_to_geometry.py` cuts the silhouette from the paint.
6. `voxel_remesh.py` only if requested, then bake again.

Rigging is out of scope unless the user asks.
