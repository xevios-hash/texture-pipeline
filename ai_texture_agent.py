#!/usr/bin/env python3
"""ai_texture_agent.py — One-function agent entry point for the full pipeline.

texture_mesh(mesh, prompt, out) drives: alpha-to-geometry -> render -> diffuse
-> bake, and optionally rigs the result with self-hosted UniRig.

The LLM (MiMo-V2.6, Claude, whatever) is the orchestrator: it picks prompts,
models, and retry policy. This module never touches pixels directly — it
shells out to Blender for geometry/render/bake and calls OpenRouter for
diffusion. Rigging is a separate optional pass because any mesh-changing step
destroys rig data, so it must come last.

Usage:
    from ai_texture_agent import texture_mesh, rig_textured_mesh

    glb = texture_mesh("bush_alpha.png", "dense forest bush, PBR", "bush.glb")
    rigged = rig_textured_mesh(glb, body_plan="biped")   # optional
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Optional

from alpha_to_geometry import alpha_to_mesh
from openrouter_texture import diffuse_views
from texture_pipeline import bake_textures, render_views


# ---------------------------------------------------------------------------
# Pipeline stages
# ---------------------------------------------------------------------------

def texture_mesh(
    mesh: str | Path,
    prompt: str,
    out: str | Path = "textured.glb",
    *,
    alpha_mask: Optional[str | Path] = None,
    views: int = 6,
    model: str = "bytedance-seed/seedream-4.5",
    api_key: Optional[str] = None,
    blender: str = "blender",
    work_dir: Optional[str | Path] = None,
) -> Path:
    """Full texture pipeline for one asset.

    1. If alpha_mask is given, run alpha-to-geometry first — the mesh gets
       created/defined from the masked image before anything else.
    2. Render orbiting views (transparent BG).
    3. Diffuse each view via OpenRouter (Seedream default, swappable).
    4. Bake projected views back onto the UV atlas.

    Because alpha meshing changes topology, any texture baked against old UVs
    won't line up — so the render/diffuse/bake sequence always runs fresh on
    whatever mesh it receives. Never reuse a prior bake.

    Parameters
    ----------
    mesh : input mesh, or ignored if alpha_mask is provided
    prompt : text prompt for the diffusion pass
    out : final GLB path
    alpha_mask : optional masked image -> alpha-to-geometry pre-pass
    views : number of orbiting cameras
    model : OpenRouter image model id
    api_key : OpenRouter key (falls back to OPENROUTER_API_KEY env)
    blender : Blender executable
    work_dir : scratch directory for intermediates

    Returns
    -------
    Path to the textured GLB.
    """
    out = Path(out)
    work = Path(work_dir) if work_dir else out.parent / f".{out.stem}_work"
    work.mkdir(parents=True, exist_ok=True)

    # Stage 0: alpha-to-geometry (mesh gets created and defined here)
    current_mesh = Path(mesh)
    if alpha_mask is not None:
        current_mesh = alpha_to_mesh(
            alpha_mask,
            out=work / f"{out.stem}_alpha.glb",
            blender=blender,
        )
        print(f"[agent] alpha mesh: {current_mesh}")

    # Stage 1: render views
    manifest = render_views(current_mesh, work / "views", n_views=views, blender=blender)
    print(f"[agent] rendered {views} views -> {manifest}")

    # Stage 2: diffuse
    diffused = diffuse_views(manifest, prompt, work / "diffused", model=model, api_key=api_key)
    print(f"[agent] diffused {len(diffused)} views")

    # Stage 3: bake
    bake_textures(current_mesh, diffused, manifest, out, blender=blender)
    print(f"[agent] baked -> {out}")
    return out


def rig_textured_mesh(
    mesh: str | Path,
    *,
    body_plan: str = "biped",
    out: Optional[str | Path] = None,
    max_attempts: int = 3,
    unirig_root: Optional[str | Path] = None,
):
    """Optional post-texture rigging pass via self-hosted UniRig.

    Must run AFTER texturing: any mesh-changing step destroys bones, skin
    weights, and animation bindings. This is why rigging is a separate
    function the agent calls explicitly rather than being baked into
    texture_mesh().

    Lazy-imports unirig_rig so the texture pipeline works without UniRig
    installed — rigging is opt-in.
    """
    from unirig_rig import rig_mesh

    mesh = Path(mesh)
    out = Path(out) if out else mesh.with_name(f"{mesh.stem}_rigged.fbx")
    result = rig_mesh(
        mesh,
        body_plan=body_plan,
        out=out,
        max_attempts=max_attempts,
        unirig_root=unirig_root,
    )
    tag = "DEGENERATE" if result.degenerate else "OK"
    print(
        f"[agent] rig [{tag}] {result.fbx_path} | {result.skeleton_joints} joints | "
        f"{result.body_plan} | attempt {result.attempt}/{max_attempts}"
    )
    return result


# ---------------------------------------------------------------------------
# CLI: agent-style one-shot
    #   python ai_texture_agent.py bush_alpha.png "dense forest bush" bush.glb
    #   python ai_texture_agent.py bush.glb "dense forest bush" bush.glb --rig biped
# ---------------------------------------------------------------------------

def main() -> None:
    p = argparse.ArgumentParser(description="Agent entry point: texture (+ optional rig)")
    p.add_argument("mesh", help="Input mesh, or alpha-masked image if --alpha given")
    p.add_argument("prompt", help="Diffusion prompt")
    p.add_argument("out", help="Output GLB path")
    p.add_argument("--alpha", help="Alpha mask image -> alpha-to-geometry pre-pass")
    p.add_argument("--views", type=int, default=6)
    p.add_argument("--model", default="bytedance-seed/seedream-4.5")
    p.add_argument("--rig", choices=["biped", "quadruped", "hexapod", "octopod", "avian", "serpentine", "aquatic"],
                   help="Optional UniRig pass after texturing")
    p.add_argument("--rig-attempts", type=int, default=3)
    p.add_argument("--unirig-root", default=None)
    p.add_argument("--blender", default="blender")
    p.add_argument("--work-dir", default=None)
    args = p.parse_args()

    glb = texture_mesh(
        args.mesh,
        args.prompt,
        args.out,
        alpha_mask=args.alpha,
        views=args.views,
        model=args.model,
        blender=args.blender,
        work_dir=args.work_dir,
    )

    if args.rig:
        rig_textured_mesh(
            glb,
            body_plan=args.rig,
            max_attempts=args.rig_attempts,
            unirig_root=args.unirig_root,
        )


if __name__ == "__main__":
    main()
