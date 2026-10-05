# texture-pipeline

Higgsfield-style texturing. No text-to-3D shape model.

An LLM writes a GLB. That GLB can be a plane or a cube — `primitive_mesh.py`
emits one with no dependencies. A diffusion model paints it. Alpha and
displacement turn the paint into actual mesh detail.

```
LLM  -->  plane or cube GLB
              |
              v
        render orbiting views (Blender)
              |
              v
        OpenRouter image model paints each view   <-- the Higgsfield step
              |
              v
        bake views onto UVs
              |
              v
        alpha cut + displace the card into a silhouette
              |
              v
        optional voxel remesh (closes it into a volume; texture re-bakes)
```

## Usage

```bash
export OPENROUTER_API_KEY=sk-or-v1-...

# bush: plane, painted, cut to the alpha
python ai_texture_agent.py bush.glb "dense green bush, cutout foliage, no background" \
  --primitive plane

# crate: cube, paint only, do not cut the silhouette
python ai_texture_agent.py crate.glb "weathered wood crate" \
  --primitive cube --no-displace

# LLM already wrote the GLB
python ai_texture_agent.py prop.glb "rusty metal panel" --mesh prop.glb
```

## What each file does

| File | Role |
|------|------|
| `primitive_mesh.py` | Cube or plane GLB. This is what the LLM calls instead of a 3D generator. |
| `texture_pipeline.py` | Render views, bake them back. |
| `openrouter_texture.py` | Stable-diffusion-class paint via OpenRouter (`seedream-4.5` default). |
| `alpha_to_geometry.py` | Texture alpha becomes the mesh. |
| `voxel_remesh.py` | Optional close-the-volume pass. |
| `unirig_rig.py` | Optional, last. |

`shape_gen.py` is leftover from a Hunyuan front end. Do not use it for this path.

## Cost

Six painted views at Seedream 4.5 is about $0.24. The mesh is free.
A second bake after voxel remesh doubles the image spend.
