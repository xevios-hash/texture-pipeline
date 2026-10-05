# Agent contract for animation, state, and loop

You are a local model. Call these. Do not rewrite Godot scripts. Do not scrape Mixamo.

## Add an animation

```bash
python anim/fetch_clip.py --intent walk --mesh assets/hero.fbx
```

Exit 0: clip was already on disk or downloaded from a catalog url, and retargeted.
Exit 2: `clips/<name>.needed.json` was written. Tell the user the search name and the save path. When they drop the FBX there, run the same command again.

Intents in the catalog: idle, walk, run, attack, death. Add a row to `anim/catalog.json` for a new one. A url field must be a direct file, not a login page.

## State machine

Edit `game/state_machine.json` (copy `game/state_machine.example.json`).
Allowed `when` values: `speed > 0.1`, `speed <= 0.1`, `attack_pressed`, `sprint_pressed`, `not sprint_pressed`, `clip_finished`, `player_at_goal`.
`game/brain.gd` reads the file. Jev can emit the same JSON; the schema is the interface.

## Loop

Edit `game/loop.json` (copy `game/loop.example.json`). `health`, `goal`, `win_when`, `fail_when`.
`on_win` and `on_fail` are `restart` only for now.
