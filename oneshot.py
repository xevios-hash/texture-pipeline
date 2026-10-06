#!/usr/bin/env python3
"""oneshot.py — one command from nothing to a Godot level.

Always produces a playable graybox. Extra stages run only if their
credential or file is already present. A missing token skips that stage.
It does not fail the level.

    python oneshot.py
    python oneshot.py --paint          # needs OPENROUTER_API_KEY

Rigging runs when REPLICATE_API_TOKEN is set (cloud UniRig).
Clips in clips/<name>.fbx are retargeted onto the rigged hero.
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


def try_run(cmd: list[str], label: str) -> bool:
    print("+", " ".join(cmd), flush=True)
    r = subprocess.run(cmd)
    if r.returncode != 0:
        print(f"SKIP {label}: exit {r.returncode}")
        return False
    return True


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--paint", action="store_true")
    a = p.parse_args()

    assets = ROOT / "assets"
    worlds = ROOT / "worlds"
    game = ROOT / "game"
    clips = ROOT / "clips"
    assets.mkdir(exist_ok=True)
    worlds.mkdir(exist_ok=True)

    run([sys.executable, str(ROOT / "primitive_mesh.py"), "--kind", "cube", "--out", str(assets / "crate.glb"), "--size", "1"])
    run([sys.executable, str(ROOT / "primitive_mesh.py"), "--kind", "plane", "--out", str(assets / "bush.glb"), "--size", "1.4"])

    if a.paint and os.environ.get("OPENROUTER_API_KEY"):
        try_run([
            sys.executable, str(ROOT / "ai_texture_agent.py"), str(assets / "bush.glb"),
            "dense green bush, cutout foliage", "--mesh", str(assets / "bush.glb"), "--no-displace",
        ], "paint")
    elif a.paint:
        print("SKIP paint: OPENROUTER_API_KEY not set")

    hero = assets / "hero.glb"
    run([BLENDER, "-b", "-P", str(ROOT / "anim" / "placeholder_hero.py"), "--", "--out", str(hero)])

    player = hero
    if os.environ.get("REPLICATE_API_TOKEN"):
        rigged = assets / "hero_rigged.glb"
        if try_run([
            sys.executable, str(ROOT / "anim" / "cloud_rig.py"),
            "--mesh", str(hero), "--out", str(rigged),
        ], "cloud rig"):
            player = rigged
            for clip in sorted(clips.glob("*.fbx")) if clips.exists() else []:
                out = assets / f"hero_{clip.stem}.glb"
                if try_run([
                    BLENDER, "-b", "-P", str(ROOT / "anim" / "retarget_mixamo.py"), "--",
                    "--mesh", str(player), "--clip", str(clip),
                    "--out", str(out), "--name", clip.stem,
                ], f"retarget {clip.name}"):
                    player = out
    else:
        print("SKIP rig: REPLICATE_API_TOKEN not set")

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
    shutil.copyfile(player, game / "hero.glb")
    shutil.copyfile(game / "state_machine.example.json", game / "state_machine.json")
    loop = json.loads((game / "loop.example.json").read_text(encoding="utf-8"))
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
