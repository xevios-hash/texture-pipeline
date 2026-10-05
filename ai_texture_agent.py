"""
ai_texture_agent.py  --  the piece an LLM agent calls.

One function: texture_mesh(mesh_path, prompt, out_path, **opts)

Full pipeline (alpha image in -> textured GLB out):
  1. alpha_to_geometry.py  --image in.png --out mesh.glb   (if --image given)
  2. texture_pipeline.py   render pass  (orbiting views + manifest.json)
  3. openrouter_texture.py diffusion pass (per-view OpenRouter Image API)
  4. texture_pipeline.py   --bake       (project views onto UVs, export GLB)

Because step 1 changes mesh topology, steps 2-4 ALWAYS re-run from scratch
on the new mesh.  Never reuse a texture baked for a previous mesh version.

Example agent call:
    texture_mesh(image="bush.png", prompt="dense green foliage, soft studio light",
                 out="bush_textured.glb")
    # or skip alpha meshing if you already have a mesh:
    texture_mesh(mesh="bush.glb", prompt="...", out="bush_textured.glb")
"""
import argparse, os, subprocess, sys

BLENDER = os.environ.get("BLENDER_BIN", "blender")
HERE = os.path.dirname(os.path.abspath(__file__))


def run(cmd):
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)


def texture_mesh(mesh=None, image=None, prompt=None, out=None,
                 workdir=None, views=6, res=1024,
                 model="bytedance-seed/seedream-4.5", blender=BLENDER,
                 alpha_threshold=0.5, alpha_subdiv=6, alpha_decimate=0.05):
    """Alpha image (or existing mesh) -> textured GLB.

    If `image` is given, step 1 meshes it via alpha_to_geometry.py and the
    resulting mesh becomes the input to steps 2-4.  `mesh` is ignored then.
    """
    if out is None:
        raise ValueError("out path required")
    if prompt is None:
        raise ValueError("prompt required")

    workdir = workdir or os.path.join(os.path.dirname(os.path.abspath(out)),
                                      "_tex_" + os.path.splitext(os.path.basename(out))[0])
    os.makedirs(workdir, exist_ok=True)

    # ---- step 1: alpha -> mesh (optional) ----
    if image:
        mesh_path = os.path.join(workdir, "alpha_mesh.glb")
        run([blender, "-b", "-P", os.path.join(HERE, "alpha_to_geometry.py"), "--",
             "--image", image, "--out", mesh_path,
             "--threshold", str(alpha_threshold),
             "--subdiv", str(alpha_subdiv),
             "--decimate", str(alpha_decimate),
             "--workdir", workdir])
        mesh = mesh_path
    elif mesh is None:
        raise ValueError("either mesh or image required")

    # ---- step 2: render orbiting views ----
    # IMPORTANT: always re-render.  If step 1 changed the topology, any
    # previously baked texture is invalid for this mesh.
    run([blender, "-b", "-P", os.path.join(HERE, "texture_pipeline.py"), "--",
         "--mesh", mesh, "--out", out, "--views", str(views), "--res", str(res),
         "--workdir", workdir])

    # ---- step 3: OpenRouter diffusion per view ----
    run([sys.executable, os.path.join(HERE, "openrouter_texture.py"),
         "--workdir", workdir, "--model", model, "--prompt", prompt])

    # ---- step 4: bake projected views onto UVs + export GLB ----
    run([blender, "-b", "-P", os.path.join(HERE, "texture_pipeline.py"), "--",
         "--mesh", mesh, "--out", out, "--views", str(views), "--res", str(res),
         "--workdir", workdir, "--bake"])
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mesh", default=None, help="existing mesh (skip alpha step)")
    ap.add_argument("--image", default=None, help="alpha-masked image to mesh first")
    ap.add_argument("prompt", help="surface description for the diffusion pass")
    ap.add_argument("out", help="output textured GLB")
    ap.add_argument("--views", type=int, default=6)
    ap.add_argument("--res", type=int, default=1024)
    ap.add_argument("--model", default="bytedance-seed/seedream-4.5")
    ap.add_argument("--workdir", default=None)
    ap.add_argument("--alpha-threshold", type=float, default=0.5)
    ap.add_argument("--alpha-subdiv", type=int, default=6)
    ap.add_argument("--alpha-decimate", type=float, default=0.05)
    a = ap.parse_args()
    texture_mesh(mesh=a.mesh, image=a.image, prompt=a.prompt, out=a.out,
                 workdir=a.workdir, views=a.views, res=a.res, model=a.model,
                 alpha_threshold=a.alpha_threshold, alpha_subdiv=a.alpha_subdiv,
                 alpha_decimate=a.alpha_decimate)
