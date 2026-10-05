# texture-pipeline

Full text-to-3D and image-to-3D pipeline, plus alpha-to-geometry and an
optional voxel remesh. An LLM agent drives it with one call.

```
prompt  ──> OpenRouter reference image ──> Hunyuan3D shape ──┐
image   ──> Hunyuan3D shape ─────────────────────────────────┤
alpha   ──> alpha_to_geometry ───────────────────────────────┤
mesh    ─────────────────────────────────────────────────────┤
                                                             ▼
                                              optional voxel remesh
                                                             ▼
                                         render views -> OpenRouter diffuse -> bake GLB
                                                             ▼
                                              optional UniRig (Mixamo FBX)
```

Voxel remesh and alpha meshing both change topology, so the texture pass
always re-runs on the mesh that actually comes out. Rigging is last.

## Usage

```bash
export OPENROUTER_API_KEY=sk-or-v1-...
export HY3D_ROOT=~/Hunyuan3D-2.1          # text/image-to-3D
export UNIRIG_ROOT=~/UniRig               # optional rig
export BLENDER_BIN=blender

# text to textured GLB, with a watertight voxel remesh
python ai_texture_agent.py fern.glb "dense green fern, soft studio light" \
  --source-prompt "a single fern frond, game asset" --voxel 0.03

# image to 3D + rig
python ai_texture_agent.py fern.glb "dense green fern" --image photo.png --rig biped

# alpha sprite to mesh (no Hunyuan needed)
python ai_texture_agent.py bush.glb "dense foliage" --alpha bush.png --voxel 0.02
```

## Shape generation

`shape_gen.py` writes a reference image (OpenRouter, transparent background)
then runs Hunyuan3D-2.1's shape DiT if `HY3D_ROOT` is set. Without Hunyuan
it exits 3 after saving the reference image — texture-only mode on an
existing `--mesh` still works.

Hunyuan3D-2.1: https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1
Shape stage is about 10 GB VRAM; their paint stage is ~21 GB. This repo
does not use their paint stage — texturing stays on the OpenRouter view bake
so you can swap models.

## Voxel remesh

`voxel_remesh.py` applies Blender's voxel Remesh modifier, smooths, and
re-unwraps. This is the path that turns a flat alpha puff into a closed
volume. Smaller `--voxel` means more detail and more triangles.

## Cost

- Reference image: ~$0.04 (Seedream 4.5)
- Six texture views: ~$0.24
- Hunyuan shape: local GPU, not an API charge
- UniRig: local GPU
- Hosted Meshy/Tripo full asset: about $0.30–$0.60, geometry included

## Limits

- Bake is naive per-triangle projection. Seams on complex meshes.
- Hunyuan and UniRig CLIs drift; the wrappers try the documented entry points.
- Rigging after remesh is required — remesh deletes bones.
