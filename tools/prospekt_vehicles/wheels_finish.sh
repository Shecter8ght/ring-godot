#!/usr/bin/env bash
# Транспорт «Проспекта»: колёса v2 с отделкой на просмотр — игровая сетка и FBX (wheels_kit.py kit), проект Painter,
# запекание с подробной формы (протектор, надписи боковины), стеки колеса (sp/stack_wheels.py → vstacks.wheel), карты,
# сборка с картами (wheels_kit.py textured). Painter с мостом запущен (задания _asset_src/prospekt_vehicles/sp_jobs).
#   bash tools/prospekt_vehicles/wheels_finish.sh [stack]      — stack: только стек, карты и сборка (проект уже запечён)
set -euo pipefail
cd "$(dirname "$0")/../.."
BL="/d/ПРОГРАММЫ/Blender 5/blender.exe"
R="E:/Models Blender/VEHICLES/Колёса"
SP="E:/Games/RING-godot/_asset_src/prospekt_vehicles/wheels/sp"
J=_asset_src/prospekt_vehicles/sp_jobs
TAG=wheels

wait_mark() {
  for _ in $(seq 1 "$2"); do [ -f "$J/$1" ] && return 0; sleep 1; done
  echo "нет метки $1 за $2 с"; return 1
}

if [ "${1:-}" != stack ]; then
  "$BL" --background --factory-startup --python-exit-code 1 --python tools/prospekt_vehicles/wheels_kit.py -- kit "$SP" \
    "$R/game/Wheels_lod0_v01.blend" 2>&1 | grep -E "UV |игровая|сохранено|Error|Traceback" || true
  python -X utf8 tools/prospekt_vehicles/sp_run.py tools/prospekt_vehicles/sp/create.py 120 -- "low=$SP/wheels_low.fbx" \
    "tag=$TAG" | head -2
  wait_mark "_proj_$TAG.txt" 300
  sleep 20                                        # полки и сетка дочитываются после входа в проект
  python -X utf8 tools/prospekt_vehicles/sp_run.py tools/prospekt_vehicles/sp/bake.py 120 -- "high=$SP/wheels_high.fbx" \
    "res=WheelCap:10,WheelSteel:10,WheelAlloy:10" "tag=$TAG" | head -2
  wait_mark "_bake_$TAG.txt" 2400
  echo "запечено: $(cat "$J/_bake_$TAG.txt")"
fi
python -X utf8 tools/prospekt_vehicles/sp_run.py tools/prospekt_vehicles/sp/stack_wheels.py 600 -- \
  "styles=WheelCap=cap,WheelSteel=steel,WheelAlloy=alloy" | head -8
MARK="_export_$TAG.txt"
python -X utf8 tools/prospekt_vehicles/sp_run.py tools/prospekt_vehicles/sp/export.py 900 -- "out=$R/textures" \
  "spp=$R/textures/painter/Wheels_v01.spp" "mark=$MARK" | head -3
wait_mark "$MARK" 1200
cat "$J/$MARK"; echo
rm -f "$R/textures/Untitled.bin" "$R/textures/Untitled.glb" "$R/textures/Untitled.gltf"
"$BL" --background --factory-startup --python-exit-code 1 --python tools/prospekt_vehicles/wheels_kit.py -- textured \
  "$R/game/Wheels_lod0_v01.blend" "$R/textures" "$R/game/Wheels_textured_v01.blend" 2>&1 | grep -E "сохранено|Error" || true
