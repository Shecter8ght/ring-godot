#!/usr/bin/env bash
# ВЕРАС-54 v13: все клипы рук от рига v13 (tools/veras54_v13/game_rig.py) — без рукоятки и под ВАРН V1 / V2.
# bash tools/veras54_v13/clips/build_all.sh [клип …]   (клип: tactical check full jam fast fastfull; без аргументов — все)
# → «Игровая версия/Клипы v13/VERAS54_<Клип>[_<рукоятка>]_v13.blend»; затем tools/export_veras54.py.
set -u
B="D:/ПРОГРАММЫ/Blender 5/blender.exe"
LIB="E:/Models Blender/WEAPONS/ВЕРАС-54 — модель и обвесы/ВЕРАС-54/Игровая версия"
RIG="$LIB/Риг v13/VERAS54_Rig_v13.blend"
OUT="$LIB/Клипы v13"
HERE="$(cd "$(dirname "$0")" && pwd)"
LOG="$HERE/../../../_asset_src/veras54_game_v13/logs"
mkdir -p "$OUT" "$LOG"
declare -A FILE=([tactical]=Reload_Tactical [check]=Mag_Check [full]=Reload_Full [jam]=Jam_Clear [fast]=Reload_Fast [fastfull]=Reload_FastFull)
CLIPS=("$@")
[ ${#CLIPS[@]} -eq 0 ] && CLIPS=(tactical check full jam fast fastfull)
fail=0
for clip in "${CLIPS[@]}"; do
  for g in "" varn_v1 varn_v2; do
    name="VERAS54_${FILE[$clip]}${g:+_$g}_v13"
    "$B" --background --factory-startup --python-exit-code 1 "$RIG" --python "$HERE/build_clips.py" -- "$clip" "$OUT/$name.blend" $g > "$LOG/clip_$name.log" 2>&1
    code=$?
    echo "CLIP $name exit $code $(grep -o 'IK не дотянулась.*' "$LOG/clip_$name.log" | head -1)"
    [ $code -ne 0 ] && fail=1
  done
done
exit $fail
