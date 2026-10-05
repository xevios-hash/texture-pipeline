#!/usr/bin/env python3
"""fetch_clip.py — what a local model calls to add an animation.

    python anim/fetch_clip.py --intent walk --mesh assets/hero.fbx

Looks up anim/catalog.json. If the row has a url, downloads the FBX into clips/.
If the row is Mixamo (url null), writes clips/<name>.needed.json and exits 2.
The model should show that file to the user, not scrape Mixamo.

When a file already exists at clips/<name>.fbx, skips download and retargets.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "anim" / "catalog.json"
CLIPS = ROOT / "clips"


def find(intent: str) -> dict:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    key = intent.lower().strip()
    for row in data["clips"]:
        names = [row["name"]] + row.get("intent", [])
        if key in [n.lower() for n in names]:
            return row
    raise SystemExit(f"no catalog row for {intent!r}. Add one to anim/catalog.json")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--intent", required=True)
    p.add_argument("--mesh", default=None, help="rigged FBX/GLB to retarget onto")
    p.add_argument("--catalog", default=str(CATALOG))
    a = p.parse_args()

    row = find(a.intent)
    CLIPS.mkdir(exist_ok=True)
    dest = CLIPS / f"{row['name']}.fbx"

    if not dest.exists():
        if row.get("url"):
            print(f"GET {row['url']}")
            urllib.request.urlretrieve(row["url"], dest)
        else:
            need = CLIPS / f"{row['name']}.needed.json"
            need.write_text(json.dumps({
                "name": row["name"],
                "source": row.get("source", "mixamo"),
                "search": row.get("search", row["name"]),
                "save_as": str(dest),
                "then": f"python anim/fetch_clip.py --intent {row['name']}" + (f" --mesh {a.mesh}" if a.mesh else ""),
            }, indent=2), encoding="utf-8")
            print(f"NEED_LOGIN {need}")
            print(f"Download {row.get('search')!r} from {row.get('source')} and save as {dest}")
            sys.exit(2)
    else:
        print(f"HAVE {dest}")

    if not a.mesh:
        print(f"CLIP {dest}")
        return

    out = ROOT / "assets" / f"hero_{row['name']}.glb"
    out.parent.mkdir(exist_ok=True)
    blender = os.environ.get("BLENDER_BIN", "blender")
    subprocess.run([
        blender, "-b", "-P", str(ROOT / "anim" / "retarget_mixamo.py"), "--",
        "--mesh", a.mesh, "--clip", str(dest), "--out", str(out), "--name", row["name"],
    ], check=True)
    print(f"RETARGET {out}")


if __name__ == "__main__":
    main()
