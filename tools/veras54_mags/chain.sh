#!/bin/sh
# Магазины ВЕРАС-54 в игру целиком: игровая сетка → запекание → упаковка → экспорт (по магазину; без аргументов — оба).
# sh tools/veras54_mags/chain.sh [m45] [d60]; логи — _asset_src/veras54_game_mags/<этап>_<магазин>.log
set -e
cd "$(dirname "$0")/../.."
B="D:/ПРОГРАММЫ/Blender 5/blender.exe"
LOG=_asset_src/veras54_game_mags
mkdir -p "$LOG"
for m in ${*:-m45 d60}; do
  for stage in lp bake pack export; do
    "$B" --background --factory-startup --python-exit-code 1 --python "tools/veras54_mags/mags_game_$stage.py" -- "$m" > "$LOG/${stage}_$m.log" 2>&1
    echo "MAGS_CHAIN $m $stage ok"
  done
done
