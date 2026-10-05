# OpenCode instructions

Read LAYERS.md. Do not collapse the layers. Do not call Meshy, Tripo, or Hunyuan.

## Mesh

macOS: `./run_pipeline.sh bush.glb "dense green bush, cutout foliage" --primitive plane`
Windows: `run_pipeline.bat bush.glb "dense green bush, cutout foliage" --primitive plane`

`--no-displace` keeps a cube a cube. `--voxel` only if asked.

## Parts and clips

Prop motion is `anim/clips.json` then:

```bash
blender -b -P anim/prop_actions.py -- --spec anim/clips.json
```

Character motion is a Mixamo FBX you already downloaded, retargeted by bone name:

```bash
blender -b -P anim/retarget_mixamo.py -- --mesh hero.fbx --clip clips/walk.fbx --out assets/hero_walk.glb --name walk
```

Do not invent a walk cycle. If clips/ is empty, say so.

## World

Edit `worlds/<name>.json` (copy `env/world.example.json`). Then rebuild. Never move props by regenerating meshes.

```bash
blender -b -P env/build_world.py -- --spec worlds/clearing.json --out worlds/clearing.glb
```

## Game

Copy the world GLB and `game/game.example.json` into `game/` as `game.json`. Open `game/` in Godot 4. Gameplay changes go in `game/main.gd`, not in the mesh scripts.

`OPENROUTER_API_KEY` must already be set. Do not print it.
