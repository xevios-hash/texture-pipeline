"""
ai_texture_agent.py  --  the piece an LLM agent calls.

Full pipeline: alpha image -> mesh (alpha_to_geometry.py) -> textured GLB.

    texture_asset(image, prompt, out, **opts)

Steps:
  1. alpha_to_geometry.py  traces the alpha channel into a mesh
  2. texture_pipeline.py    renders orbiting views
  3. openrouter_texture.py  diffuses each view via OpenRouter
  4. texture_pipeline.py --bake  projects views onto UVs, exports GLB

Example:
    texture_asset("bush.png", "dense green foliage, soft studio light", "bush_textured.glb")
"""
import argparse, os, subprocess, sys

BLENDER = os.environ.get("BLENDER_BIN", "blender")
HERE = os.path.dirname(os.path.abspath(__file__))


def run(cmd):
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)


def texture_asset(image, prompt, out, workdir=None, views=6, res=1024,
                  model="bytedance-seed/seedream-4.5", blender=BLENDER,
                  mode="plane", subdiv=8, threshold=0.5, decimate=0.05,
                  min_area=50, size=2.0):
    """End-to-end: alpha image -> mesh -> textured GLB."""
    workdir = workdir or os.path.join(os.path.dirname(out) or ".",
                                      "_tex_" + os.path.splitext(os.path.basename(image))[0])
    os.makedirs(workdir, exist_ok=True)

    mesh_path = os.path.join(workdir, "mesh.glb")

    # pass 1: alpha -> geometry
    run([blender, "-b", "-P", os.path.join(HERE, "alpha_to_geometry.py"), "--",
         "--image", image, "--out", mesh_path, "--mode", mode,
         "--subdiv", str(subdiv), "--threshold", str(threshold),
         "--decimate", str(decimate), "--size", str(size),
         "--min-area", str(min_area)])

    # pass 2: render views
    run([blender, "-b", "-P", os.path.join(HERE, "texture_pipeline.py"), "--",
         "--mesh", mesh_path, "--out", out, "--views", str(views), "--res", str(res),
         "--workdir", workdir])

    # pass 3: OpenRouter diffusion per view
    run([sys.executable, os.path.join(HERE, "openrouter_texture.py"),
         "--workdir", workdir, "--model", model, "--prompt", prompt])

    # pass 4: bake projected views back onto UVs + export GLB
    run([blender, "-b", "-P", os.path.join(HERE, "texture_pipeline.py"), "--",
         "--mesh", mesh_path, "--out", out, "--views", str(views), "--res", str(res),
         "--workdir", workdir, "--bake"])
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="alpha image -> textured GLB pipeline")
    ap.add_argument("image", help="PNG with alpha channel")
    ap.add_argument("prompt", help="surface description for diffusion")
    ap.add_argument("out", help="output GLB path")
    ap.add_argument("--workdir", default=None)
    ap.add_argument("--views", type=int, default=6)
    ap.add_argument("--res", type=int, default=1024)
    ap.add_argument("--model", default="bytedance-seed/seedream-4.5")
    ap.add_argument("--mode", choices=["plane", "sprite"], default="plane")
    ap.add_argument("--subdiv", type=int, default=8)
    ap.add_argument("--threshold", type=float, default=0.5)
    ap.add_argument("--decimate", type=float, default=0.05)
    ap.add_argument("--min-area", type=int, default=50)
    ap.add_argument("--size", type=float, default=2.0)
    a = ap.parse_args()
    texture_asset(a.image, a.prompt, a.out, workdir=a.workdir, views=a.views,
                  res=a.res, model=a.model, mode=a.mode, subdiv=a.subdiv,
                  threshold=a.threshold, decimate=a.decimate,
                  min_area=a.min_area, size=a.size)
