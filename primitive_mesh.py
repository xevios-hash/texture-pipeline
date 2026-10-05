#!/usr/bin/env python3
"""primitive_mesh.py — write a dumb GLB an LLM can emit without a 3D model.

No Hunyuan, no Tripo, no Meshy. A cube, plane, or card is enough.
Detail comes later from the diffusion texture (alpha cut + displacement),
which is the Higgsfield-style path.

    python primitive_mesh.py --kind plane --out card.glb --size 2
    python primitive_mesh.py --kind cube --out box.glb
"""
from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path


def _plane(size: float):
    h = size / 2
    # two triangles, +Z facing, UV 0-1
    pos = [(-h, -h, 0), (h, -h, 0), (h, h, 0), (-h, h, 0)]
    nrm = [(0, 0, 1)] * 4
    uv = [(0, 0), (1, 0), (1, 1), (0, 1)]
    idx = [0, 1, 2, 0, 2, 3]
    return pos, nrm, uv, idx


def _cube(size: float):
    h = size / 2
    # 24 verts so each face has its own UV
    faces = [
        # +Z front
        ((-h, -h, h), (h, -h, h), (h, h, h), (-h, h, h), (0, 0, 1)),
        # -Z back
        ((h, -h, -h), (-h, -h, -h), (-h, h, -h), (h, h, -h), (0, 0, -1)),
        # +X
        ((h, -h, h), (h, -h, -h), (h, h, -h), (h, h, h), (1, 0, 0)),
        # -X
        ((-h, -h, -h), (-h, -h, h), (-h, h, h), (-h, h, -h), (-1, 0, 0)),
        # +Y
        ((-h, h, h), (h, h, h), (h, h, -h), (-h, h, -h), (0, 1, 0)),
        # -Y
        ((-h, -h, -h), (h, -h, -h), (h, -h, h), (-h, -h, h), (0, -1, 0)),
    ]
    pos, nrm, uv, idx = [], [], [], []
    for i, (a, b, c, d, n) in enumerate(faces):
        base = i * 4
        pos.extend([a, b, c, d])
        nrm.extend([n, n, n, n])
        uv.extend([(0, 0), (1, 0), (1, 1), (0, 1)])
        idx.extend([base, base + 1, base + 2, base, base + 2, base + 3])
    return pos, nrm, uv, idx


def write_glb(path: Path, pos, nrm, uv, idx) -> None:
    def pad(b: bytes) -> bytes:
        return b + b"\x00" * ((4 - len(b) % 4) % 4)

    vp = b"".join(struct.pack("<3f", *p) for p in pos)
    vn = b"".join(struct.pack("<3f", *n) for n in nrm)
    vt = b"".join(struct.pack("<2f", *t) for t in uv)
    vi = b"".join(struct.pack("<H", i) for i in idx)
    bin_blob = pad(vp + vn + vt + vi)
    off_n, off_t, off_i = len(vp), len(vp) + len(vn), len(vp) + len(vn) + len(vt)

    gltf = {
        "asset": {"version": "2.0", "generator": "primitive_mesh.py"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0}],
        "meshes": [{"primitives": [{
            "attributes": {"POSITION": 0, "NORMAL": 1, "TEXCOORD_0": 2},
            "indices": 3,
        }]}],
        "buffers": [{"byteLength": len(bin_blob)}],
        "bufferViews": [
            {"buffer": 0, "byteOffset": 0, "byteLength": len(vp), "target": 34962},
            {"buffer": 0, "byteOffset": off_n, "byteLength": len(vn), "target": 34962},
            {"buffer": 0, "byteOffset": off_t, "byteLength": len(vt), "target": 34962},
            {"buffer": 0, "byteOffset": off_i, "byteLength": len(vi), "target": 34963},
        ],
        "accessors": [
            {"bufferView": 0, "componentType": 5126, "count": len(pos), "type": "VEC3",
             "min": [min(p[0] for p in pos), min(p[1] for p in pos), min(p[2] for p in pos)],
             "max": [max(p[0] for p in pos), max(p[1] for p in pos), max(p[2] for p in pos)]},
            {"bufferView": 1, "componentType": 5126, "count": len(nrm), "type": "VEC3"},
            {"bufferView": 2, "componentType": 5126, "count": len(uv), "type": "VEC2"},
            {"bufferView": 3, "componentType": 5123, "count": len(idx), "type": "SCALAR"},
        ],
    }
    j = json.dumps(gltf, separators=(",", ":")).encode()
    j = pad(j)
    chunk = struct.pack("<I4s", len(j), b"JSON") + j + struct.pack("<I4s", len(bin_blob), b"BIN\x00") + bin_blob
    glb = struct.pack("<4sII", b"glTF", 2, 12 + len(chunk)) + chunk
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(glb)
    print(f"PRIMITIVE {path} verts={len(pos)} tris={len(idx)//3}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--kind", choices=("plane", "cube"), default="plane")
    p.add_argument("--out", required=True)
    p.add_argument("--size", type=float, default=2.0)
    a = p.parse_args()
    pos, nrm, uv, idx = _cube(a.size) if a.kind == "cube" else _plane(a.size)
    write_glb(Path(a.out), pos, nrm, uv, idx)


if __name__ == "__main__":
    main()
