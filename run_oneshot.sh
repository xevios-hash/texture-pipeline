#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [[ -z "${BLENDER_BIN:-}" && -x "/Applications/Blender.app/Contents/MacOS/Blender" ]]; then
  export BLENDER_BIN="/Applications/Blender.app/Contents/MacOS/Blender"
fi
exec python3 oneshot.py "$@"
