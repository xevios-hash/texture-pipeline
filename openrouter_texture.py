"""
openrouter_texture.py  --  reads manifest.json from the Blender render pass,
calls the OpenRouter Image API for each view, saves view_N.png back.

Usage:
    export OPENROUTER_API_KEY=sk-or-v1-...
    python openrouter_texture.py [--workdir .] [--model bytedance-seed/seedream-4.5]
                                 [--prompt "bush, dense green foliage, studio light"]

Each call sends the rendered view as an input_reference so the model edits
in place (preserves geometry/lighting cues) rather than hallucinating a
new object.  Switch --model to flux.2-pro or nano-banana anytime.
"""
import argparse, base64, json, os, sys, time
import requests

API = "https://openrouter.ai/api/v1/images"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workdir", default=".")
    ap.add_argument("--model", default="bytedance-seed/seedream-4.5")
    ap.add_argument("--prompt", required=True,
                    help="surface description, e.g. 'dense green bush foliage, soft studio light, no background'")
    ap.add_argument("--resolution", default="1K")
    ap.add_argument("--sleep", type=float, default=0.5, help="pause between calls")
    args = ap.parse_args()

    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        sys.exit("OPENROUTER_API_KEY not set")

    with open(os.path.join(args.workdir, "manifest.json")) as f:
        manifest = json.load(f)

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://local.dev/texture-pipeline",
        "X-Title": "texture-pipeline",
    }

    for v in manifest["views"]:
        src = os.path.join(args.workdir, v["image"])
        with open(src, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        payload = {
            "model": args.model,
            "prompt": args.prompt,
            "resolution": args.resolution,
            "aspect_ratio": "1:1",
            "output_format": "png",
            "input_references": [
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}
            ],
        }
        print(f"view {v['index']:02d} -> {args.model} ...", end=" ", flush=True)
        r = requests.post(API, headers=headers, json=payload, timeout=180)
        if r.status_code != 200:
            print(f"FAIL {r.status_code}: {r.text[:300]}")
            continue
        data = r.json()
        b64_out = data["data"][0]["b64_json"]
        out = os.path.join(args.workdir, f"view_{v['index']:02d}.png")
        with open(out, "wb") as f:
            f.write(base64.b64decode(b64_out))
        print(f"ok ({len(b64_out)//1024} KB)")
        time.sleep(args.sleep)

    print("done. re-run Blender with --bake to project views onto UVs.")

if __name__ == "__main__":
    main()
