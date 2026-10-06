#!/usr/bin/env python3
"""oneshot.py — build a playable graybox in one command.

Does not need OpenRouter or Mixamo. If OPENROUTER_API_KEY is set and --paint
is passed, bushes go through the texture pipeline. Otherwise primitives.

    python oneshot.py
    python oneshot.py --paint

Then open game/ in Godot 4 and press Play.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BLENDER = os.environ.get("BLENDER_BIN", "blender")


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--paint", action="store_true", help="texture bushes if OPENROUTER_API_KEY is set")
    a = p.parse_args()

    assets = ROOT / "assets"
    worlds = ROOT / "worlds"
    game = ROOT / "game"
    assets.mkdir(exist_ok=True)
    worlds.mkdir(exist_ok=True)

    run([sys.executable, str(ROOT / "primitive_mesh.py"), "--kind", "cube", "--out", str(assets / "crate.glb"), "--size", "1"])
    run([sys.executable, str(ROOT / "primitive_mesh.py"), "--kind", "plane", "--out", str(assets / "bush.glb"), "--size", "1.4"])

    if a.paint and os.environ.get("OPENROUTER_API_KEY"):
        run([sys.executable, str(ROOT / "ai_texture_agent.py"), str(assets / "bush.glb"),
             "dense green bush, cutout foliage", "--mesh", str(assets / "bush.glb")])
    elif a.paint:
        print("SKIP paint: OPENROUTER_API_KEY not set")

    run([BLENDER, "-b", "-P", str(ROOT / "anim" / "placeholder_hero.py"), "--",
         "--out", str(assets / "hero.glb")])

    spec = {
        "name": "clearing",
        "terrain": {"size": 32, "step": 1.0, "amplitude": 0.6, "seed": 3},
        "instances": [
            {"asset": "assets/crate.glb", "name": "crate_a", "at": [4, 0, 2], "rot_y": 20, "scale": 1},
            {"asset": "assets/bush.glb", "name": "bush_hero", "at": [-2, 0, 5], "rot_y": 0, "scale": 1.4},
        ],
        "scatter": [{
            "asset": "assets/bush.glb",
            "region": [-12, -12, 12, 12],
            "count": 18,
            "seed": 7,
            "scale": [0.7, 1.3],
            "avoid": [[0, 0, 3], [10, 10, 2]],
        }],
        "player_spawn": [0, 0, 0],
    }
    world_spec = worlds / "clearing.json"
    world_spec.write_text(json.dumps(spec, indent=2), encoding="utf-8")
    run([BLENDER, "-b", "-P", str(ROOT / "env" / "build_world.py"), "--",
         "--spec", str(world_spec), "--out", str(worlds / "clearing.glb")])

    shutil.copyfile(worlds / "clearing.glb", game / "world.glb")
    shutil.copyfile(assets / "hero.glb", game / "hero.glb")
    shutil.copyfile(ROOT / "game" / "state_machine.example.json", game / "state_machine.json")
    loop = json.loads((ROOT / "game" / "loop.example.json").read_text(encoding="utf-8"))
    (game / "loop.json").write_text(json.dumps(loop, indent=2), encoding="utf-8")
    (game / "game.json").write_text(json.dumps({
        "world": "res://world.glb",
        "player": "res://hero.glb",
        "spawn": [0, 0, 0],
        "move_speed": 4.0,
    }, indent=2), encoding="utf-8")
    print("DONE open game/ in Godot 4 and press Play. WASD move, Shift sprint, J attack.")


if __name__ == "__main__":
    main()
