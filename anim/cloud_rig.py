#!/usr/bin/env python3
"""cloud_rig.py — rig a mesh on Replicate. No local UniRig install.

Hugging Face does not serve VAST-AI/UniRig on its inference API.
This calls the community model aaronjmars/unirig-ai, which runs skeleton
and skin prediction on their GPU and returns a file.

    export REPLICATE_API_TOKEN=r8_...
    python anim/cloud_rig.py --mesh assets/hero.glb --out assets/hero_rigged.glb

Billing is Replicate GPU seconds, not an OpenRouter credit.
The official HF checkpoint is skeleton-only; this hosted model claims skin
weights too. Check the output armature before retargeting.
"""
from __future__ import annotations

import argparse
import os
import sys
import urllib.request
from pathlib import Path

MODEL = "aaronjmars/unirig-ai:9ee496eafcc6ab9789a110a6357e43e5ee8b93cee9ab653bdc6f06a29341ee86"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--mesh", required=True)
    p.add_argument("--out", required=True)
    a = p.parse_args()
    if not os.environ.get("REPLICATE_API_TOKEN"):
        sys.exit("REPLICATE_API_TOKEN is not set")
    try:
        import replicate
    except ImportError:
        sys.exit("pip install replicate")

    mesh = Path(a.mesh)
    print(f"RIG {mesh} via {MODEL.split(':')[0]}")
    with mesh.open("rb") as fh:
        out = replicate.run(MODEL, input={"input_mesh": fh})
    url = out[0] if isinstance(out, (list, tuple)) else out
    if hasattr(url, "url"):
        url = url.url
    url = str(url)
    dest = Path(a.out)
    dest.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(url, dest)
    print(f"WROTE {dest}")


if __name__ == "__main__":
    main()
