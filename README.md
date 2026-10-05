# texture-pipeline

Multi-view texture generation pipeline for 3D meshes. Renders orbiting views of a mesh in Blender, textures each view through the OpenRouter Image API, then bakes the results back onto the mesh UVs and exports a GLB.

Designed so an LLM agent (e.g. MiMo-V2.6 via OpenCode) can drive the whole thing with one function call.

## Pipeline

1. **Render pass** (`texture_pipeline.py`) — Blender renders N orbiting views with transparent backgrounds, writes `manifest.json` describing each camera.
2. **Diffusion pass** (`openrouter_texture.py`) — calls `POST https://openrouter.ai/api/v1/images` per view, sending the rendered view as an `input_reference` so the model edits in place. Default model: `bytedance-seed/seedream-4.5` (~$0.01/image). Swappable to `black-forest-labs/flux.2-pro` or `google/gemini-3.1-flash-image`.
3. **Bake pass** (`texture_pipeline.py --bake`) — projects each view onto the UV atlas (per-triangle, most face-on camera wins), assigns the atlas to a Principled BSDF, exports GLB.

## Usage

```bash
export OPENROUTER_API_KEY=sk-or-v1-...
export BLENDER_BIN=blender   # optional, defaults to 'blender' on PATH

python ai_texture_agent.py bush.glb "dense green foliage, soft studio light" bush_textured.glb
```

Or step by step:

```bash
# 1. render views
blender -b -P texture_pipeline.py -- --mesh bush.glb --out bush_textured.glb --views 6 --res 1024 --workdir ./work

# 2. diffuse each view
python openrouter_texture.py --workdir ./work --prompt "dense green foliage, soft studio light, no background"

# 3. bake + export
blender -b -P texture_pipeline.py -- --mesh bush.glb --out bush_textured.glb --workdir ./work --bake
```

## Agent wrapper

`ai_texture_agent.py` exposes one function:

```python
from ai_texture_agent import texture_mesh
texture_mesh("bush.glb", "dense green foliage, soft studio light", "bush_textured.glb")
```

The agent never sees Blender internals — just mesh in, textured GLB out.

## Cost

~6 views × ~$0.01–0.05 = a few cents per asset. MiMo-V2.6 (or any model) stays the orchestrator; it never touches pixels directly.

## Notes / known limits

- The bake pass is naive per-triangle rasterization, not a GPU rasterizer. Seams and aliasing will show on complex meshes. For production, swap for xatlas + a proper projection step.
- Requires Blender 4.x with EEVEE (or EEVEE_NEXT) and Python 3.10+ with `requests`.
- Output is a standard GLB with a PBR albedo map — RealityKit / SceneKit on iOS can load it directly.

## License

MIT
