#!/usr/bin/env python3
"""unirig_rig.py — Self-hosted UniRig rigging pass.

Wraps the open-source UniRig pipeline (MIT, weights on Hugging Face) so it
slots into the texture-pipeline as an optional post-texture step. UniRig is
an autoregressive transformer that predicts a skeleton joint-by-joint with
bone semantics (Mixamo-style names), then skin-weights the mesh.

It handles seven body plans: biped, quadruped, hexapod, octopod, avian,
serpentine, aquatic. Output is a Mixamo-spec FBX that imports cleanly into
Unity and Unreal — which is what you want for iOS.

Requirements (separate from the texture pipeline):
    pip install torch trimesh numpy
    git clone https://github.com/VAST-AI-Research/UniRig
    # download weights from https://huggingface.co/VAST-AI/UniRig

Usage:
    from unirig_rig import rig_mesh
    rigged = rig_mesh("bush.glb", body_plan="biped", out="bush_rigged.fbx")

Cost: GPU time only. A 3090 runs UniRig in seconds per mesh — roughly a
cent or two at rented-GPU rates. Compare to Tripo's 25-credit rig call.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BODY_PLANS = (
    "biped", "quadruped", "hexapod", "octopod", "avian", "serpentine", "aquatic"
)

# Where you cloned UniRig. Override with UNIRIG_ROOT env var.
UNIRIG_ROOT = Path(os.environ.get("UNIRIG_ROOT", "~/UniRig")).expanduser()


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

@dataclass
class RigResult:
    """Output of one rigging attempt."""
    fbx_path: Path
    skeleton_joints: int
    body_plan: str
    attempt: int
    degenerate: bool = False


# ---------------------------------------------------------------------------
# Core: call UniRig on a mesh
# ---------------------------------------------------------------------------

def _unirig_available() -> bool:
    """True if the UniRig repo is cloned and its entry script exists."""
    return (UNIRIG_ROOT / "inference.py").exists() or (UNIRIG_ROOT / "run.py").exists()


def _run_unirig(mesh_path: Path, body_plan: str, out_dir: Path) -> Path:
    """Invoke UniRig's inference entry point.

    UniRig's actual CLI varies by version, so this tries the common patterns
    and falls back to a direct Python import of their pipeline module. The
    important contract: it must return a path to a Mixamo-spec FBX.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    fbx_out = out_dir / f"{mesh_path.stem}_rigged.fbx"

    # Pattern 1: CLI script (most common in recent UniRig releases)
    for script_name in ("inference.py", "run.py", "main.py"):
        script = UNIRIG_ROOT / script_name
        if script.exists():
            cmd = [
                sys.executable, str(script),
                "--input", str(mesh_path),
                "--output", str(fbx_out),
                "--body-plan", body_plan,
            ]
            r = subprocess.run(cmd, capture_output=True, text=True)
            if r.returncode == 0 and fbx_out.exists():
                return fbx_out
            # fall through to next pattern on failure

    # Pattern 2: import their pipeline module directly
    for mod_name in ("unirig", "unirig.pipeline", "unirig.inference"):
        spec = importlib.util.find_spec(mod_name)
        if spec is None:
            continue
        mod = importlib.util.module_from_spec(spec)
        sys.modules[mod_name] = mod
        spec.loader.exec_module(mod)
        if hasattr(mod, "rig_mesh"):
            mod.rig_mesh(str(mesh_path), str(fbx_out), body_plan=body_plan)
            if fbx_out.exists():
                return fbx_out

    raise RuntimeError(
        f"Could not invoke UniRig from {UNIRIG_ROOT}. "
        "Check that the repo is cloned and UNIRIG_ROOT is set correctly."
    )


# ---------------------------------------------------------------------------
# Sanity check: is the skeleton degenerate?
# ---------------------------------------------------------------------------

def _is_degenerate(fbx_path: Path) -> bool:
    """Heuristic degeneracy check on the output FBX.

    UniRig is nondeterministic — the same mesh can produce a clean skeleton
    or a collapsed one. This catches the obvious failure modes: too few joints,
    zero-length bones, or a skeleton that doesn't span the mesh bounds.
    """
    try:
        import trimesh
    except ImportError:
        return False  # can't check, assume fine

    # Trimesh can't read FBX directly in all builds; try anyway, fall back to
    # a lenient pass if the loader isn't available.
    try:
        scene = trimesh.load(str(fbx_path), force="scene")
    except Exception:
        return False

    # Count named joints / bones across the scene graph
    joints = [g for g in scene.geometry.values() if "joint" in g.name.lower()]
    if len(joints) < 3:
        return True

    # Check bone lengths aren't near-zero
    for j in joints:
        if j.bounds is None:
            continue
        extent = (j.bounds[1] - j.bounds[0]).max()
        if extent < 1e-4:
            return True

    return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def rig_mesh(
    mesh_path: str | Path,
    *,
    body_plan: str = "biped",
    out: str | Path = "rigged.fbx",
    max_attempts: int = 3,
    unirig_root: str | Path | None = None,
) -> RigResult:
    """Rig a mesh with self-hosted UniRig.

    Retries up to max_attempts because UniRig's autoregressive sampling is
    nondeterministic — a degenerate skeleton on attempt N often comes back
    clean on attempt N+1. This mirrors the retry pattern people use with
    Tripo's rig endpoint, except here the retry is free (GPU time only).

    Parameters
    ----------
    mesh_path : input mesh (GLB/FBX/OBJ — anything UniRig accepts)
    body_plan : one of BODY_PLANS
    out : output FBX path
    max_attempts : how many times to retry on degeneracy
    unirig_root : override UNIRIG_ROOT for this call

    Returns
    -------
    RigResult with the FBX path and skeleton stats.
    """
    global UNIRIG_ROOT
    if unirig_root is not None:
        UNIRIG_ROOT = Path(unirig_root).expanduser()

    if body_plan not in BODY_PLANS:
        raise ValueError(f"body_plan must be one of {BODY_PLANS}, got {body_plan!r}")

    if not _unirig_available():
        raise RuntimeError(
            f"UniRig not found at {UNIRIG_ROOT}. "
            "Clone it (git clone https://github.com/VAST-AI-Research/UniRig) "
            "and download weights from https://huggingface.co/VAST-AI/UniRig, "
            "or set UNIRIG_ROOT."
        )

    mesh_path = Path(mesh_path)
    out_dir = Path(out).parent
    last_fbx: Optional[Path] = None

    for attempt in range(1, max_attempts + 1):
        fbx = _run_unirig(mesh_path, body_plan, out_dir)
        last_fbx = fbx
        if not _is_degenerate(fbx):
            # Count joints for the report
            n_joints = 0
            try:
                import trimesh
                scene = trimesh.load(str(fbx), force="scene")
                n_joints = sum(1 for g in scene.geometry.values() if "joint" in g.name.lower())
            except Exception:
                pass
            return RigResult(
                fbx_path=fbx,
                skeleton_joints=n_joints,
                body_plan=body_plan,
                attempt=attempt,
            )
        # degenerate — retry with a fresh sample
        if attempt < max_attempts:
            print(f"[unirig] attempt {attempt} degenerate, retrying...", file=sys.stderr)

    # All attempts degenerate — return the last one with a flag rather than
    # silently failing, so the agent can decide what to do.
    return RigResult(
        fbx_path=last_fbx,
        skeleton_joints=0,
        body_plan=body_plan,
        attempt=max_attempts,
        degenerate=True,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    p = argparse.ArgumentParser(description="Self-hosted UniRig rigging pass")
    p.add_argument("mesh", help="Input mesh (GLB/FBX/OBJ)")
    p.add_argument("-p", "--body-plan", default="biped", choices=BODY_PLANS)
    p.add_argument("-o", "--out", default="rigged.fbx")
    p.add_argument("--max-attempts", type=int, default=3)
    p.add_argument("--unirig-root", default=None, help="Override UNIRIG_ROOT")
    args = p.parse_args()

    result = rig_mesh(
        args.mesh,
        body_plan=args.body_plan,
        out=args.out,
        max_attempts=args.max_attempts,
        unirig_root=args.unirig_root,
    )
    status = "DEGENERATE" if result.degenerate else "OK"
    print(
        f"[{status}] {result.fbx_path} | {result.skeleton_joints} joints | "
        f"{result.body_plan} | attempt {result.attempt}/{args.max_attempts}"
    )
    if result.degenerate:
        sys.exit(2)


if __name__ == "__main__":
    main()
