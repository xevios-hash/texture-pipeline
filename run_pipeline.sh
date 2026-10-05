#!/usr/bin/env bash
# macOS / Linux launcher. OpenCode should call this, not invent steps.
#
#   export OPENROUTER_API_KEY=sk-or-v1-...
#   export BLENDER_BIN="/Applications/Blender.app/Contents/MacOS/Blender"
#   ./run_pipeline.sh bush.glb "dense green bush, cutout foliage" --primitive plane
set -euo pipefail
cd "$(dirname "$0")"

if [[ -z "${OPENROUTER_API_KEY:-}" ]]; then
  echo "OPENROUTER_API_KEY is not set" >&2
  exit 1
fi

if [[ -z "${BLENDER_BIN:-}" ]]; then
  if [[ -x "/Applications/Blender.app/Contents/MacOS/Blender" ]]; then
    export BLENDER_BIN="/Applications/Blender.app/Contents/MacOS/Blender"
  else
    export BLENDER_BIN="blender"
  fi
fi

PY="${PYTHON_BIN:-python3}"
exec "$PY" ai_texture_agent.py "$@"
