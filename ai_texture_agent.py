#!/usr/bin/env python3
"""ai_texture_agent.py — Higgsfield-style path, no 3D generator.

The LLM's job is the mesh, and the mesh is dumb on purpose:
  a plane or a cube it can emit itself (primitive_mesh.py), or any GLB it wrote.

Stable Diffusion does the look:
  render the primitive, paint each view through OpenRouter, bake to UVs.

Geometry detail comes FROM that texture, not from a shape model:
  1. ask the image model for a transparent-background paint
  2. alpha-cut + displace the primitive using the baked texture
  3. optional voxel remesh to close it into a volume

Rigging, if any, is last.

    python ai_texture_agent.py bush.glb "dense green bush, cutout foliage" --primitive plane
    python ai_texture_agent.py crate.glb "weathered wood crate" --primitive cube --no-displace
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

BLENDER = os.environ.get("BLENDER_BIN", "blender")
HERE = Path(__file__).resolve().parent


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)


def texture_asset(
    out: str | Path,
    prompt: str,
    *,
    mesh: str | None = None,
    primitive: str | None = "plane",
    views: int = 6,
    res: int = 1024,
    model: str = "bytedance-seed/seedream-4.5",
    displace: bool = True,
    voxel: float | None = None,
    rig: str | None = None,
    workdir: str | None = None,
    blender: str = BLENDER,
) -> Path:
    out = Path(out)
    work = Path(workdir) if workdir else out.parent / f"_work_{out.stem}"
    work.mkdir(parents=True, exist_ok=True)

    current = Path(mesh) if mesh else work / "primitive.glb"
    if not mesh:
        run([
            sys.executable, str(HERE / "primitive_mesh.py"),
            "--kind", primitive or "plane", "--out", str(current),
        ])

    # Paint the primitive. Views go back into work/ as view_XX.png.
    run([
        blender, "-b", "-P", str(HERE / "texture_pipeline.py"), "--",
        "--mesh", str(current), "--out", str(out),
        "--views", str(views), "--res", str(res), "--workdir", str(work),
    ])
    run([
        sys.executable, str(HERE / "openrouter_texture.py"),
        "--workdir", str(work), "--model", model, "--prompt", prompt,
    ])
    run([
        blender, "-b", "-P", str(HERE / "texture_pipeline.py"), "--",
        "--mesh", str(current), "--out", str(work / "painted.glb"),
        "--views", str(views), "--res", str(res), "--workdir", str(work), "--bake",
    ])
    current = work / "painted.glb"

    # Detail from the texture: front view is the alpha source for a card/plane.
    if displace:
        alpha_src = work / "view_00.png"
        cut = work / "cut.glb"
        run([
            blender, "-b", "-P", str(HERE / "alpha_to_geometry.py"), "--",
            "--image", str(alpha_src), "--out", str(cut), "--workdir", str(work),
        ])
        current = cut

    if voxel is not None:
        solid = work / "voxel.glb"
        run([
            blender, "-b", "-P", str(HERE / "voxel_remesh.py"), "--",
            "--mesh", str(current), "--out", str(solid), "--voxel", str(voxel),
        ])
        current = solid
        # topology changed, paint again so the texture matches the new mesh
        run([
            blender, "-b", "-P", str(HERE / "texture_pipeline.py"), "--",
            "--mesh", str(current), "--out", str(out),
            "--views", str(views), "--res", str(res), "--workdir", str(work),
        ])
        run([
            sys.executable, str(HERE / "openrouter_texture.py"),
            "--workdir", str(work), "--model", model, "--prompt", prompt,
        ])
        run([
            blender, "-b", "-P", str(HERE / "texture_pipeline.py"), "--",
            "--mesh", str(current), "--out", str(out),
            "--views", str(views), "--res", str(res), "--workdir", str(work), "--bake",
        ])
    else:
        # no second topology change; copy the detailed mesh to out if we cut it
        if current != out:
            run([
                blender, "-b", "-P", str(HERE / "texture_pipeline.py"), "--",
                "--mesh", str(current), "--out", str(out),
                "--views", str(views), "--res", str(res), "--workdir", str(work), "--bake",
            ])

    if rig:
        run([
            sys.executable, str(HERE / "unirig_rig.py"),
            str(out), "-p", rig, "-o", str(out.with_suffix(".fbx")),
        ])
    print(f"DONE {out}")
    return out


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("out")
    p.add_argument("prompt")
    p.add_argument("--mesh", default=None, help="GLB the LLM already wrote")
    p.add_argument("--primitive", choices=("plane", "cube"), default="plane")
    p.add_argument("--no-displace", action="store_true")
    p.add_argument("--voxel", type=float, default=None)
    p.add_argument("--views", type=int, default=6)
    p.add_argument("--res", type=int, default=1024)
    p.add_argument("--model", default="bytedance-seed/seedream-4.5")
    p.add_argument("--rig", default=None)
    p.add_argument("--workdir", default=None)
    a = p.parse_args()
    texture_asset(
        a.out, a.prompt,
        mesh=a.mesh, primitive=a.primitive, views=a.views, res=a.res,
        model=a.model, displace=not a.no_displace, voxel=a.voxel, rig=a.rig,
        workdir=a.workdir,
    )


if __name__ == "__main__":
    main()
