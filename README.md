# texture-pipeline

Multi-view texture generation pipeline for 3D meshes. Two entry modes:

- **Mesh in** -> orbiting views -> OpenRouter diffusion -> bake -> textured GLB
- **Alpha image in** -> alpha-to-geometry mesh -> (same texture pipeline)

Designed so an LLM agent (e.g. MiMo-V2.6 via OpenCode) drives everything
with one function call.

## Pipeline

```
alpha image ──> [alpha_to_geometry] ──> mesh ──> [render views] ──> [OpenRouter diffuse] ──> [bake UVs] ──> textured GLB
```

1. **Alpha-to-geometry** (`alpha_to_geometry.py`) — trace the alpha channel into a subdivided, displaced mesh. Transparent parts get deleted, topology gets re-unwrapped. Optional decimate for mobile budgets.
2. **Render pass** (`texture_pipeline.py`) — Blender renders N orbiting views, writes `manifest.json`.
3. **Diffusion pass** (`openrouter_texture.py`) — `POST /api/v1/images` per view with the render as `input_reference`. Default: `bytedance-seed/seedream-4.5`.
4. **Bake pass** (`texture_pipeline.py --bake`) — project views onto UVs, export GLB.

## Usage

```bash
export OPENROUTER_API_KEY=sk-or-v1-...
export BLENDER_BIN=blender

# alpha image -> textured GLB (full pipeline)
python ai_texture_agent.py --image bush.png "dense green foliage, soft studio light" bush_textured.glb

# existing mesh -> textured GLB
python ai_texture_agent.py --mesh bush.glb "dense green foliage, soft studio light" bush_textured.glb
```

## Why the texture must re-run after alpha meshing

Alpha-to-geometry **changes the mesh topology** — new faces, new UVs, different
triangle layout. A texture baked against the old mesh's UVs will not line up
with the new ones. So the rule is strict: after any mesh-changing step,
re-render and re-diffuse from scratch. The agent wrapper enforces this by
always running render -> diffuse -> bake as a fresh sequence on whatever mesh
it receives.

## Cost

~6 views x ~$0.01-0.05 = a few cents per asset. The LLM orchestrator never
touches pixels directly.

## Known limits

- Bake pass is naive per-triangle rasterization. Seams on complex meshes;
  swap for xatlas + proper projection in production.
- Alpha meshing displaces along normals only — no overhangs or true volume.
  For real 3D volume you'd need voxel remesh / marching cubes (different pass).
- Requires Blender 4.x and Python 3.10+ with `requests`.

## License

MIT
