"""
ai_texture_agent.py  --  the piece an LLM agent calls.

One function: texture_mesh(mesh_path, prompt, out_path, **opts)
It shells out to Blender for render + bake, and to openrouter_texture.py
for the diffusion pass.  The agent never sees Blender internals.

Example agent call:
    texture_mesh("bush.glb", "dense green foliage, soft studio light", "bush_textured.glb")
"""
import argparse, os, subprocess, sys

BLENDER = os.environ.get("BLENDER_BIN", "blender")
HERE = os.path.dirname(os.path.abspath(__file__))

def run(cmd):
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)

def texture_mesh(mesh, prompt, out, workdir=None, views=6, res=1024,
                 model="bytedance-seed/seedream-4.5", blender=BLENDER):
    workdir = workdir or os.path.join(os.path.dirname(out),
                                      "_tex_" + os.path.splitext(os.path.basename(mesh))[0])
    os.makedirs(workdir, exist_ok=True)

    # pass 1: render views
    run([blender, "-b", "-P", os.path.join(HERE, "texture_pipeline.py"), "--",
         "--mesh", mesh, "--out", out, "--views", str(views), "--res", str(res),
         "--workdir", workdir])

    # pass 2: OpenRouter diffusion per view
    run([sys.executable, os.path.join(HERE, "openrouter_texture.py"),
         "--workdir", workdir, "--model", model, "--prompt", prompt])

    # pass 3: bake projected views back onto UVs + export GLB
    run([blender, "-b", "-P", os.path.join(HERE, "texture_pipeline.py"), "--",
         "--mesh", mesh, "--out", out, "--views", str(views), "--res", str(res),
         "--workdir", workdir, "--bake"])
    return out

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("mesh")
    ap.add_argument("prompt")
    ap.add_argument("out")
    ap.add_argument("--views", type=int, default=6)
    ap.add_argument("--res", type=int, default=1024)
    ap.add_argument("--model", default="bytedance-seed/seedream-4.5")
    ap.add_argument("--workdir", default=None)
    a = ap.parse_args()
    texture_mesh(a.mesh, a.prompt, a.out, workdir=a.workdir,
                 views=a.views, res=a.res, model=a.model)
