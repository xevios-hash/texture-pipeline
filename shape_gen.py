#!/usr/bin/env python3
"""shape_gen.py — text-to-3D or image-to-3D front end.

Two stages, deliberately split so you can swap either half:

  1. Reference image
     - image path given: use it
     - text prompt only: render a clean product-shot via OpenRouter Image API
       (Seedream 4.5 default). Transparent background requested.

  2. Shape
     - If Hunyuan3D-2.1 is installed (HY3D_ROOT or importable hy3dshape),
       run the shape DiT and export an untextured GLB.
     - Otherwise write the reference image and exit 3 with a clear message.
       Texture-only mode still works on a mesh you already have.

This does NOT texture. Texturing is the existing render -> diffuse -> bake
pass, which always re-runs on the mesh this script emits.

Usage:
    python shape_gen.py --prompt "a low poly fern" --out fern.glb
    python shape_gen.py --image photo.png --out fern.glb
"""
from __future__ import annotations

import argparse
import base64
import os
import sys
from pathlib import Path

API = "https://openrouter.ai/api/v1/images"


def reference_image(prompt: str, out: Path, model: str, api_key: str | None) -> Path:
    import requests

    key = api_key or os.environ.get("OPENROUTER_API_KEY")
    if not key:
        sys.exit("OPENROUTER_API_KEY not set")
    payload = {
        "model": model,
        "prompt": (
            f"{prompt}, single object centered, studio lighting, "
            "plain background, product photo, no text"
        ),
        "resolution": "1K",
        "aspect_ratio": "1:1",
        "output_format": "png",
        "background": "transparent",
    }
    r = requests.post(
        API,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json=payload,
        timeout=180,
    )
    if r.status_code != 200:
        sys.exit(f"reference image failed {r.status_code}: {r.text[:400]}")
    b64 = r.json()["data"][0]["b64_json"]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(base64.b64decode(b64))
    print(f"REFERENCE {out}")
    return out


def hunyuan_shape(image: Path, out: Path) -> Path:
    """Run Hunyuan3D shape DiT if the local install is present."""
    root = os.environ.get("HY3D_ROOT")
    if root:
        sys.path.insert(0, root)
        sys.path.insert(0, str(Path(root) / "hy3dshape"))
    try:
        from hy3dshape.pipelines import Hunyuan3DDiTFlowMatchingPipeline
    except ImportError:
        print(
            "Hunyuan3D not installed. Clone https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1 "
            "and set HY3D_ROOT. Reference image was still written.",
            file=sys.stderr,
        )
        sys.exit(3)

    pipe = Hunyuan3DDiTFlowMatchingPipeline.from_pretrained("tencent/Hunyuan3D-2.1")
    mesh = pipe(image=str(image))[0]
    out.parent.mkdir(parents=True, exist_ok=True)
    mesh.export(str(out))
    print(f"SHAPE {out}")
    return out


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--prompt", default=None)
    p.add_argument("--image", default=None)
    p.add_argument("--out", required=True)
    p.add_argument("--ref-out", default=None, help="where to save the reference image")
    p.add_argument("--model", default="bytedance-seed/seedream-4.5")
    args = p.parse_args()
    if not args.prompt and not args.image:
        sys.exit("need --prompt or --image")

    out = Path(args.out)
    if args.image:
        ref = Path(args.image)
    else:
        ref = Path(args.ref_out) if args.ref_out else out.with_suffix(".ref.png")
        reference_image(args.prompt, ref, args.model, None)
    hunyuan_shape(ref, out)


if __name__ == "__main__":
    main()
