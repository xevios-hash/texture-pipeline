---
name: texture-pipeline
description: "Build a playable Godot level from this repo in one command. Use when the user wants a one-shot game, a painted mesh, a cloud UniRig, a state machine, or a world JSON. Not for Meshy, Tripo, Hunyuan, or AAA production."
type: workflow
lifecycle: active
---

# Texture pipeline — one command, then edit JSON

Do not reimplement stages. Do not call Meshy, Tripo, Hunyuan, or `shape_gen.py`.

## Run

```bash
./run_oneshot.sh
```

Windows: `run_oneshot.bat`. Blender must be on PATH, or set `BLENDER_BIN`.

Then tell the user to open `game/` in Godot 4 and press Play. WASD, Shift sprint, J attack, marker wins.

## Optional stages, same command

| Need | Do |
|------|----|
| Painted bush | `OPENROUTER_API_KEY` set, then `./run_oneshot.sh --paint` |
| Rigged hero | `REPLICATE_API_TOKEN` set. The one shot calls `anim/cloud_rig.py`. |
| Real clips | User drops Mixamo FBX in `clips/`. Do not scrape Mixamo. Rerun the one shot. |

A missing token prints SKIP and still writes the level. Do not fail the task for that.

## After the first play

Edit data, rerun the one shot. Do not regenerate a mesh to move a prop.

- `worlds/clearing.json` — instances, scatter, terrain
- `game/state_machine.json` — states. Allowed `when`: `speed > 0.1`, `speed <= 0.1`, `attack_pressed`, `sprint_pressed`, `not sprint_pressed`, `clip_finished`, `player_at_goal`
- `game/loop.json` — health, goal, win, fail

`game/brain.gd` reads those files. Do not rewrite it to change a transition.

## Order, if a single stage breaks

1. `primitive_mesh.py` writes the GLB.
2. `texture_pipeline.py` renders, `openrouter_texture.py` paints, bake again.
3. `alpha_to_geometry.py` only if the user asked for a silhouette cut.
4. `anim/cloud_rig.py` last among mesh changes. Remesh deletes bones.
5. `anim/retarget_mixamo.py` only if bone names match the clip.
6. `env/build_world.py` rebuilds the level GLB.
