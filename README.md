# texture-pipeline

One command builds a playable Godot level. Painting and rigging run in that
same command when their tokens are set. They are not separate steps you have
to remember.

```bash
# macOS
./run_oneshot.sh

# Windows
run_oneshot.bat

# painted bushes, if OPENROUTER_API_KEY is set
./run_oneshot.sh --paint
```

Then open `game/` in Godot 4 and press Play. WASD moves, Shift sprints, J attacks.
Walk to the marker to win. The scene reloads.

Requires Blender on PATH, or `BLENDER_BIN`. On a Mac the launcher uses
`/Applications/Blender.app/Contents/MacOS/Blender` if that exists.

## What the one shot always does

1. Writes a crate and a bush GLB. No shape model.
2. Writes a capsule hero with idle and walk bobs, so the level plays with no Mixamo.
3. Builds `worlds/clearing.json` and a terrain GLB with scattered bushes.
4. Copies the world, the hero, the state machine, and the loop into `game/`.
5. Godot adds collision to every mesh, follows the camera, and reads the brain.

## What it adds when credentials exist

| Env | Stage |
|-----|--------|
| `OPENROUTER_API_KEY` and `--paint` | Paints the bush through the view-bake path. |
| `REPLICATE_API_TOKEN` | Rigs the hero on Replicate (`anim/cloud_rig.py`). |
| `clips/*.fbx` plus the token above | Retargets each clip onto that rig by bone name. |

A missing token skips that stage and still writes the level. Mixamo is not
scraped. Drop FBX files in `clips/` yourself.

## After the first play

Edit JSON, then rerun the one shot. Do not regenerate a mesh to move a bush.

- `worlds/clearing.json` — instances, scatter, terrain seed
- `game/state_machine.json` — states and transitions
- `game/loop.json` — health, goal, win and fail

`game/brain.gd` reads those files. Gameplay code in `game/main.gd` should not
be rewritten to change a transition.

## What this is not

Not a 3D generator. Not Tripo, Meshy, or Hunyuan. `shape_gen.py` is leftover;
do not use it. Not an AAA pipeline. The cloud rig is a community Replicate
model, and its bone names may not match Mixamo until you check the armature.
