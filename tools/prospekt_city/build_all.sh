#!/usr/bin/env bash
# «Проспект», ограждения и город: собрать формы в библиотеку владельца, проверить и снять виды.
#   bash tools/prospekt_city/build_all.sh [модуль …]   (по умолчанию — все)
# Выход — E:/Models Blender/ENVIRONMENT/Проспект_город_партия1/<папка из META>/{models,checks,previews}.
set -euo pipefail
cd "$(dirname "$0")/../.."
BL="/d/ПРОГРАММЫ/Blender 5/blender.exe"
ROOT="E:/Models Blender/ENVIRONMENT/Проспект_город_партия1"
MODS=("$@")
[ ${#MODS[@]} -eq 0 ] && MODS=(po2_fence garages containers poles catenary bus_stop ktp)
for m in "${MODS[@]}"; do
  [ -f "tools/prospekt_city/$m.py" ] || { echo "нет генератора: $m"; continue; }
  folder=$(python -X utf8 tools/prospekt_city/meta.py "$m" folder | tr -d '\r')
  name=$(python -X utf8 tools/prospekt_city/meta.py "$m" name | tr -d '\r')
  out="$ROOT/$folder/models/${name}_geometry_v01.blend"
  "$BL" --background --factory-startup --python-exit-code 1 --python tools/prospekt_city/build.py -- "$m" "$out" | grep -E "собрано|Error" || true
  [ -f "$out" ] || { echo "не собрано: $m"; exit 1; }
  "$BL" --background --factory-startup --python-exit-code 1 --python tools/prospekt_city/audit.py -- "$out" "$ROOT/$folder/checks/geometry.json" \
    | grep -vE "^(Blender|Read blend|Info|$)" || true
  python -X utf8 tools/prospekt_city/previews.py "$m" "$out"
done
