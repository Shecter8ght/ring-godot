#!/usr/bin/env bash
# VERAS-54 v14 geometry: build fields -> assemble .blend -> shots with the reference cameras -> comparison sheets.
#   [VERAS_TAG=name] bash tools/veras54_v14/geo/go.sh <k> "<parts or modules to rebuild, empty = all>" "<views, comma separated>"
# k = voxel multiplier (2 = draft, 1 = full). Output under _asset_src/veras54_v14_geo/work: v14_k<k>[_tag].blend,
# shots_k<k>[_tag], cmp_k<k>[_tag]. VERAS_JOBS = worker processes (default 3). VERAS_ADAPT = mesh coarsening multiplier.
# VERAS_TAG gives a private set of folders for parallel work. VERAS_BASE= (empty) skips appending the parts kept from v13.
set -e
cd "$(dirname "$0")/../../.."
K="${1:-2}"; PARTS="$2"; VIEWS="${3:-R02_receiver_right,L02_receiver_left}"
A="_asset_src/veras54_v14_geo"
S="k$K${VERAS_TAG:+_$VERAS_TAG}"
F="$A/fields_$S"
BL="/d/ПРОГРАММЫ/Blender 5/blender.exe"
BASE="${VERAS_BASE-E:/Models Blender/WEAPONS/ВЕРАС-54 — модель и обвесы/ВЕРАС-54/Актуальное/VERAS54_Only_State100_v13.blend}"
python -X utf8 tools/veras54_v14/geo/build.py "$F" $PARTS --k "$K" --jobs "${VERAS_JOBS:-3}" | tail -40
"$BL" --background --factory-startup --python-exit-code 1 --python tools/veras54_v14/geo/assemble.py -- "E:/Games/RING-godot/$F" "E:/Games/RING-godot/$A/work/v14_$S.blend" --adapt-scale "${VERAS_ADAPT:-1}" ${BASE:+--base "$BASE"} 2>&1 | grep -E "TOTAL|SAVED|NO_|BASE|Error|Traceback|error" || true
"$BL" --background "E:/Games/RING-godot/$A/work/v14_$S.blend" --python tools/veras54_v14/geo/shots.py -- "E:/Games/RING-godot/$A/work/shots_$S" "$VIEWS" 2>&1 | grep -E "SHOT|Error|Traceback" || true
python -X utf8 tools/veras54_v14/geo/compare.py "$A/work/shots_$S" "$A/work/cmp_$S" | tr '\n' ' '
