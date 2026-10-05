#!/usr/bin/env python3
"""ai_texture_agent.py — one entry point for the full pipeline.

Modes (pick one source):
  --prompt "a fern"          text -> reference image -> Hunyuan3D mesh
  --image photo.png          image -> Hunyuan3D mesh
  --alpha bush.png           alpha mask -> displaced silhouette mesh
  --mesh bush.glb            existing mesh

Then always:
  optional --voxel 0.02      watertight remesh (kills UVs, so texture re-runs)
  render orbiting views
  OpenRouter diffuse each view
  bake onto UVs, export GLB
  optional --rig biped       UniRig, last, because remesh destroys bones

Example:
  python ai_texture_agent.py --prompt "low poly fern" fern.glb --voxel 0.03
  python ai_texture_agent.py --image photo.png fern.glb --rig biped
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


def make_shape(prompt, image, alpha, mesh, work: Path, model: str, blender: str) -> Path:
    """Return a GLB path. Exactly one of prompt/image/alpha/mesh should be set."""
    if mesh:
        return Path(mesh)
    if alpha:
        out = work / "alpha_mesh.glb"
        run([
            blender, "-b", "-P", str(HERE / "alpha_to_geometry.py"), "--",
            "--image", str(alpha), "--out", str(out), "--workdir", str(work),
        ])
        return out
    if prompt or image:
        out = work / "shape.glb"
        cmd = [sys.executable, str(HERE / "shape_gen.py"), "--out", str(out), "--model", model]
        if image:
            cmd += ["--image", str(image)]
        else:
            cmd += ["--prompt", prompt, "--ref-out", str(work / "reference.png")]
        run(cmd)
        return out
    raise SystemExit("need --prompt, --image, --alpha, or --mesh")


def texture_asset(
    out: str | Path,
    *,
    prompt: str,
    source_prompt: str | None = None,
    image: str | None = None,
    alpha: str | None = None,
    mesh: str | None = None,
    voxel: float | None = None,
    views: int = 6,
    res: int = 1024,
    model: str = "bytedance-seed/seedream-4.5",
    rig: str | None = None,
    workdir: str | None = None,
    blender: str = BLENDER,
) -> Path:
    out = Path(out)
    work = Path(workdir) if workdir else out.parent / f"_work_{out.stem}"
    work.mkdir(parents=True, exist_ok=True)

    current = make_shape(source_prompt, image, alpha, mesh, work, model, blender)

    if voxel is not None:
        remeshed = work / "voxel.glb"
        run([
            blender, "-b", "-P", str(HERE / "voxel_remesh.py"), "--",
            "--mesh", str(current), "--out", str(remeshed), "--voxel", str(voxel),
        ])
        current = remeshed

    # texture always re-runs on the mesh we actually have
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

    if rig:
        run([
            sys.executable, str(HERE / "unirig_rig.py"),
            str(out), "-p", rig, "-o", str(out.with_suffix(".fbx")),
        ])
    return out


def main() -> None:
    p = argparse.ArgumentParser(description="text/image/alpha/mesh -> textured GLB")
    p.add_argument("out")
    p.add_argument("prompt", help="surface description used for the texture pass")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--source-prompt", help="text-to-3D: generate shape from this prompt")
    src.add_argument("--image", help="image-to-3D")
    src.add_argument("--alpha", help="alpha mask to silhouette mesh")
    src.add_argument("--mesh", help="existing mesh, skip shape gen")
    p.add_argument("--voxel", type=float, default=None, help="voxel size; omit to skip remesh")
    p.add_argument("--views", type=int, default=6)
    p.add_argument("--res", type=int, default=1024)
    p.add_argument("--model", default="bytedance-seed/seedream-4.5")
    p.add_argument("--rig", default=None)
    p.add_argument("--workdir", default=None)
    a = p.parse_args()
    texture_asset(
        a.out,
        prompt=a.prompt,
        source_prompt=a.source_prompt,
        image=a.image,
        alpha=a.alpha,
        mesh=a.mesh,
        voxel=a.voxel,
        views=a.views,
        res=a.res,
        model=a.model,
        rig=a.rig,
        workdir=a.workdir,
    )


if __name__ == "__main__":
    main()
