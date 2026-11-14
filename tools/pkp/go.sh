#!/usr/bin/env bash
# PKP: build fields -> assemble .blend -> shots -> overlays on the owner's reference renders, in one go.
#   [PKP_TAG=name] bash tools/pkp/go.sh <k> "<parts or modules to rebuild, empty = all>" "<views, comma separated>"
# k = voxel multiplier (2 = draft, 1 = full). Output: <asset>/work/pkp_k<k>.blend, work/shots_k<k>, work/cmp_k<k>.
# PKP_JOBS = worker processes (default 4: other sessions on this PC leave little free memory).
# PKP_ADAPT = multiplier of mesh coarsening (1 = draft default; 0.4 for the delivery build: cleaner thin ribs, more triangles).
# PKP_TAG gives a private set of folders (fields_k<k>_<tag>, pkp_k<k>_<tag>.blend, shots_k<k>_<tag>) for parallel work.
set -e
cd "$(dirname "$0")/../.."
K="${1:-2}"; PARTS="$2"; VIEWS="${3:-ref13,ref14}"
A="E:/Models Blender/WEAPONS/Печенег — модель"
S="k$K${PKP_TAG:+_$PKP_TAG}"
F="_asset_src/pkp/fields_$S"
BL="/d/ПРОГРАММЫ/Blender 5/blender.exe"
python -X utf8 tools/pkp/build.py "$F" $PARTS --k "$K" --jobs "${PKP_JOBS:-4}" | tail -60
"$BL" --background --factory-startup --python-exit-code 1 --python tools/pkp/assemble.py -- "E:/Games/RING-godot/$F" "$A/work/pkp_$S.blend" --adapt-scale "${PKP_ADAPT:-1}" 2>&1 | grep -E "TOTAL|SAVED|NO_|Error|Traceback|error" || true
"$BL" --background "$A/work/pkp_$S.blend" --python tools/pkp/shots.py -- "$A/work/shots_$S" "$VIEWS" 2>&1 | grep -E "SHOT|Error|Traceback" || true
case "$VIEWS" in *ref13*|*ref14*) python -X utf8 tools/pkp/compare.py "$A/work/shots_$S" "$A/refs/owner" "$A/work/cmp_$S" ;; esac
