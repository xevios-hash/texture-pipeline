# texture-pipeline

End-to-end asset pipeline: **alpha image -> mesh -> textured GLB**.

Four passes, driven by one agent-facing function:

1. **alpha_to_geometry.py** — traces the alpha channel of an image into a mesh (plane mode: subdivide + delete low-alpha faces; sprite mode: connected components, one mesh per blob). Decimates to a target triangle budget.
2. **texture_pipeline.py** — Blender renders N orbiting views with transparent backgrounds, writes `manifest.json`.
3. **openrouter_texture.py** — calls `POST https://openrouter.ai/api/v1/images` per view, sending each rendered view as an `input_reference` so the diffusion model edits in place. Default: `bytedance-seed/seedream-4.5` (~$0.01/image). Swappable to Flux 2 Pro or Nano Banana 2.
4. **texture_pipeline.py --bake** — projects each diffused view onto the UV atlas (per-triangle, most face-on camera wins), assigns to a Principled BSDF, exports GLB.

## Usage

```bash
export OPENROUTER_API_KEY=sk-or-v1-...
export BLENDER_BIN=blender   # optional

# full pipeline: alpha image -> textured GLB
python ai_texture_agent.py bush.png "dense green foliage, soft studio light" bush_textured.glb

# or just the alpha->mesh pre-pass
blender -b -P alpha_to_geometry.py -- --image bush.png --out bush.glb --mode plane --subdiv 8 --decimate 0.05
```

## Agent wrapper

```python
from ai_texture_agent import texture_asset
texture_asset("bush.png", "dense green foliage, soft studio light", "bush_textured.glb")
```

## Cost

~6 views x ~$0.01-0.05 = a few cents per asset. The LLM orchestrator (MiMo-V2.6, Claude, etc.) never touches pixels directly.

## Known limits

- The bake pass is naive per-triangle rasterization. Seams and aliasing will show on complex meshes; for production swap for xatlas + a proper projection step.
- Plane mode produces flat cards — displacement or a later remesh pass is needed for true 3D volume (leaves, bark).
- Sprite mode needs clean separation between blobs; overlapping alpha will merge them.
- Output is a standard GLB with a PBR albedo map — RealityKit / SceneKit on iOS load it directly.

## License

MIT
