#!/usr/bin/env bash
# Клипы рук под магазины 45 / 60 от файлов хватов владельца («Хваты магазинов 45 и 60»): перезарядки — построителем
# автомата (tools/veras54_v13/clips/build_clips.py, без правок), действия переименовываются в набор магазина;
# проверка — поворотом автомата к окнам остатка (mags_check_clip.py). Без рукоятки и под ВАРН V1 / V2.
# bash tools/veras54_mags/mags_clips.sh [m45|d60 …]  → «Клипы v13/VERAS54_<Клип>[_<рукоятка>]_<mag45|drum60>_v13.blend»
set -u
cd "$(dirname "$0")/../.."
B="D:/ПРОГРАММЫ/Blender 5/blender.exe"
LIB="E:/Models Blender/WEAPONS/ВЕРАС-54 — модель и обвесы/ВЕРАС-54/Игровая версия"
OUT="$LIB/Клипы v13"
LOG="$PWD/_asset_src/veras54_game_mags/logs"
mkdir -p "$LOG"
declare -A ATLAS=([m45]=Mag45 [d60]=Drum60)
declare -A SET=([m45]=mag45 [d60]=drum60)
declare -A FILE=([tactical]=Reload_Tactical [full]=Reload_Full [fast]=Reload_Fast [fastfull]=Reload_FastFull)
declare -A TAG=([tactical]=Tactical [full]=Full [fast]=Fast [fastfull]=Fastfull)
MAGS=("$@")
[ ${#MAGS[@]} -eq 0 ] && MAGS=(m45 d60)
fail=0
for m in "${MAGS[@]}"; do
  GRIP="$LIB/Хваты магазинов 45 и 60/VERAS54_Grip_${ATLAS[$m]}_v01.blend"
  for g in "" varn_v1 varn_v2; do
    for clip in tactical full fast fastfull; do
      name="VERAS54_${FILE[$clip]}${g:+_$g}_${SET[$m]}_v13"
      "$B" --background --factory-startup --python-exit-code 1 "$GRIP" --python tools/veras54_v13/clips/build_clips.py -- "$clip" "$OUT/$name.blend" $g > "$LOG/clip_$name.log" 2>&1 \
        && "$B" --background --factory-startup --python-exit-code 1 "$OUT/$name.blend" --python tools/veras54_mags/mags_rename_actions.py -- "${TAG[$clip]}${g:+_$g}" "${SET[$m]}" >> "$LOG/clip_$name.log" 2>&1
      code=$?
      echo "CLIP $name exit $code $(grep -o 'IK не дотянулась.*' "$LOG/clip_$name.log" | head -1)"
      [ $code -ne 0 ] && fail=1
    done
    name="VERAS54_Mag_Check${g:+_$g}_${SET[$m]}_v13"
    "$B" --background --factory-startup --python-exit-code 1 "$GRIP" --python tools/veras54_mags/mags_check_clip.py -- "$m" "$OUT/$name.blend" $g > "$LOG/clip_$name.log" 2>&1
    code=$?
    echo "CLIP $name exit $code"
    [ $code -ne 0 ] && fail=1
  done
done
exit $fail
