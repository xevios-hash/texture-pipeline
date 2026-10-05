# Layers

A game is not one generator. Each layer only reads the layer under it.

1. Mesh. LLM emits a plane or cube (`primitive_mesh.py`). Diffusion paints it. Alpha and displacement turn paint into silhouette. Output: `assets/<name>.glb`.
2. Parts. A prop that should move is not a new mesh. It is a named object in `parts.json` (door, wheel, leaf card). Characters get a Mixamo-spec skeleton from UniRig, last, after the mesh has stopped changing.
3. Clips. Animation is data, not a prompt. Props get curves from `clips.json` (`anim/prop_actions.py`). Characters get Mixamo FBX dropped in `clips/` and copied on by bone name (`anim/retarget_mixamo.py`). Nothing here invents a walk cycle from text.
4. World. `worlds/<name>.json` is the only editable scene. Each iteration adds, moves, or deletes instances. `env/build_world.py` rebuilds `worlds/<name>.glb` from that file. Do not regenerate assets to move a bush.
5. Game. Godot 4 reads the world GLB, the clip library, and `game/game.json`. Gameplay scripts live in `game/`. iOS is a Godot export target later, not a second pipeline.

OpenCode edits JSON and calls the launchers. It does not reimplement a layer.
