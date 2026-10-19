#!/usr/bin/env bash
# ВЕРАС-54 v13: клипы переводчика огня большим пальцем (fire_mode_clip.py) — АВ→2, 2→ОД, ОД→АВ, без рукоятки и под ВАРН V1 / V2.
# bash tools/veras54_v13/clips/build_fire_modes.sh → «Игровая версия/Клипы v13/VERAS54_FireMode_<откуда>_<куда>[_<рукоятка>]_v13.blend»;
# затем tools/export_veras54.py.
set -u
B="D:/ПРОГРАММЫ/Blender 5/blender.exe"
LIB="E:/Models Blender/WEAPONS/ВЕРАС-54 — модель и обвесы/ВЕРАС-54/Игровая версия"
RIG="$LIB/Риг v13/VERAS54_Rig_v13.blend"
OUT="$LIB/Клипы v13"
HERE="$(cd "$(dirname "$0")" && pwd)"
LOG="$HERE/../../../_asset_src/veras54_game_v13/logs"
mkdir -p "$OUT" "$LOG"
fail=0
for pair in "auto burst" "burst semi" "semi auto"; do
  set -- $pair
  for g in "" varn_v1 varn_v2; do
    name="VERAS54_FireMode_${1}_${2}${g:+_$g}_v13"
    "$B" --background --factory-startup "$RIG" --python-exit-code 1 --python "$HERE/fire_mode_clip.py" -- "$1" "$2" "$OUT/$name.blend" $g > "$LOG/clip_$name.log" 2>&1
    code=$?
    echo "CLIP $name exit $code $(grep -o 'thumb pad miss mm.*' "$LOG/clip_$name.log" | head -1)"
    [ $code -ne 0 ] && fail=1
  done
done
exit $fail
