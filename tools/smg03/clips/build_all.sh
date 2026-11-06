#!/usr/bin/env bash
# ИЗЛОМ-45: риг и все клипы рук заново (tools/smg03/clips): риг → tactical, full, check, inspect, jam → выгрузка в игру.
# bash tools/smg03/clips/build_all.sh [rig] [clips] [export]   (без аргументов — всё)
set -e
cd "$(dirname "$0")/../../.."
B="D:/ПРОГРАММЫ/Blender 5/blender.exe"
D="E:/Models Blender/WEAPONS/Vector — модель/Анимации"
want() { [ $# -eq 0 ] && return 0; for a in "${ARGS[@]}"; do [ "$a" = "$1" ] && return 0; done; return 1; }
ARGS=("$@")
if [ ${#ARGS[@]} -eq 0 ] || want rig; then
  "$B" -b --factory-startup --python-exit-code 1 --python tools/smg03/clips/rig.py 2>&1 | grep -E "SMG03_RIG|Error|Traceback" || true
fi
if [ ${#ARGS[@]} -eq 0 ] || want clips; then
  for c in tactical full check inspect jam; do
    "$B" -b "$D/ИЗЛОМ45_Rig_v01.blend" --python-exit-code 1 --python tools/smg03/clips/build_clips.py -- $c "$D/ИЗЛОМ45_Clip_${c}_v01.blend" 2>&1 | grep -E "^CLIP [a-z]|Error|Traceback" || true
  done
fi
if [ ${#ARGS[@]} -eq 0 ] || want export; then
  "$B" -b --factory-startup --python-exit-code 1 --python tools/smg03/clips/export_viewmodel.py 2>&1 | grep -E "SMG03_VM|Error|Traceback" || true
fi
