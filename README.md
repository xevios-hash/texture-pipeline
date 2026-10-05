# texture-pipeline

AI-driven 3D asset pipeline: alpha-to-geometry, multi-view diffusion texturing,
and optional self-hosted UniRig rigging. Designed so an LLM agent (MiMo-V2.6,
Claude, etc.) can drive the whole thing through one function call.

## Pipeline

```
alpha mask ──> alpha_to_geometry ──> mesh (GLB)
                                        │
                                        ▼
                              render_views (Blender, N orbiting cams)
                                        │
                                        ▼
                              diffuse_views (OpenRouter: Seedream / Flux / ...)
                                        │
                                        ▼
                              bake_textures (project views onto UV atlas)
                                        │
                                        ▼
                              textured GLB ──> [optional] rig_textured_mesh (UniRig)
                                                              │
                                                              ▼
                                                    Mixamo-spec FBX (Unity/Unreal/iOS ready)
```

## Why this order

Any mesh-changing step destroys rig data — bones, skin weights, animation
bindings. So rigging is always last, and it's a separate explicit call the
agent makes after texturing. The agent wrapper enforces this by running
render → diffuse → bake as a fresh sequence on whatever mesh it receives.

## Files

| File | Role |
|------|------|
| `alpha_to_geometry.py` | Alpha-masked image → subdivided, displaced, decimated mesh |
| `texture_pipeline.py` | Blender render + bake passes |
| `openrouter_texture.py` | OpenRouter image API (Seedream 4.5 default, swappable) |
| `unirig_rig.py` | **Self-hosted UniRig rigging** (new) |
| `ai_texture_agent.py` | One-function agent entry: `texture_mesh()` + `rig_textured_mesh()` |

## Quick start

```bash
# Texture only
python ai_texture_agent.py bush_alpha.png "dense forest bush, PBR" bush.glb

# Texture + rig (UniRig must be cloned + weights downloaded)
python ai_texture_agent.py bush.glb "dense forest bush" bush.glb --rig biped
```

## UniRig setup (optional rigging pass)

```bash
git clone https://github.com/VAST-AI-Research/UniRig
# download weights from https://huggingface.co/VAST-AI/UniRig
export UNIRIG_ROOT=~/UniRig
```

UniRig is MIT-licensed, runs on a single consumer GPU (a 3090 is plenty),
and outputs Mixamo-spec FBX. It handles seven body plans: biped, quadruped,
hexapod, octopod, avian, serpentine, aquatic. It's nondeterministic, so
`unirig_rig.py` retries up to 3 times on degenerate skeletons — same pattern
people use with Tripo's rig endpoint, except retries here cost GPU-seconds,
not cents.

## Cost per asset (textured, 6 views)

- OpenRouter Seedream 4.5: ~$0.04/image → ~$0.24
- Blender render/bake: free on owned hardware
- UniRig rig pass: ~$0.01–0.02 GPU time
- **Total: roughly 25–30 cents**, vs 60+ cents on Meshy/Tripo for equivalent output

## Honest limits

- Bake pass is naive per-triangle rasterization — expect seams on complex
  meshes. Swap for xatlas + proper projection for production.
- Alpha displacement only pushes along normals: puffy silhouette, no true
  volume or overhangs. For real 3D volume, a voxel remesh / marching-cubes
  pass is the next step (not yet wired in).
- UniRig's research-grade CLI means `unirig_rig.py` tries several invocation
  patterns; if your UniRig version differs, point it at the right script or
  set up the import path.
