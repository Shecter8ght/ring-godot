#!/usr/bin/env bash
# Транспорт «Проспекта»: круг отделки в открытом проекте Painter — стек слоёв → выгрузка карт → карты на игровую
# сетку в Blender → проверочные снимки. Проект семьи уже создан и запечён (sp/create.py, sp/bake.py; с нуля — sp_family.sh).
#   bash tools/prospekt_vehicles/sp_cycle.sh <папка машины> <Имя> <семья> <задание стека> [ключ=значение …]
# Пример: bash tools/prospekt_vehicles/sp_cycle.sh Седан Sedan clean sp/stack_car.py color=0.86,0.86,0.84
set -euo pipefail
cd "$(dirname "$0")/../.."
BL="/d/ПРОГРАММЫ/Blender 5/blender.exe"
R="E:/Models Blender/VEHICLES/${BATCH:-Город_партия1}/$1"           # партия 2 — BATCH=Город_партия2
NAME="$2"; FAM="$3"; JOB="$4"; shift 4
SC="${REVIEW_DIR:-$PWD/_asset_src/prospekt_vehicles/review}"     # проверочные снимки (не в git)
python -X utf8 tools/prospekt_vehicles/sp_run.py "tools/prospekt_vehicles/$JOB" 600 -- "$@" | head -3
J=_asset_src/prospekt_vehicles/sp_jobs
MARK="_export_${NAME}_${FAM}.txt"
python -X utf8 tools/prospekt_vehicles/sp_run.py tools/prospekt_vehicles/sp/export.py 900 -- "out=$R/textures/$FAM" \
  "spp=$R/textures/painter/${NAME}_${FAM}_v01.spp" "mark=$MARK" | head -3
for _ in $(seq 1 1200); do [ -f "$J/$MARK" ] && break; sleep 1; done      # Painter досчитывает стек и выгружает
cat "$J/$MARK" 2>/dev/null || echo "нет метки выгрузки $MARK"; echo
rm -f "$R/textures/$FAM/Untitled.bin" "$R/textures/$FAM/Untitled.glb" "$R/textures/$FAM/Untitled.gltf"
"$BL" --background --factory-startup --python-exit-code 1 --python tools/prospekt_vehicles/apply_maps.py -- \
  "$R/game/${NAME}_lod0_v01.blend" "$R/textures" "$R/game/${NAME}_textured_v01.blend" 2>&1 | grep -i "error\|сохранено" || true
case $FAM in
  clean) HIDE="hide:Открыт hide:Битый hide:Сгоревший"; X=0.0 ;;
  wreck) HIDE="hide:Целый hide:Открыт hide:Сгоревший"; X=6.4 ;;
  burnt) HIDE="hide:Целый hide:Открыт hide:Битый"; X=9.6 ;;
  over) HIDE=""; X=0.0 ;;
esac
# виды — от габарита машины: у легковой как были, у автобуса, ПАЗ и ГАЗели — дальше в длину и выше
VIEWS=$(python -X utf8 tools/prospekt_vehicles/review_views.py "$NAME" "$X")
"$BL" --background --factory-startup --python-exit-code 1 --python tools/prospekt_vehicles/review.py -- \
  "$R/game/${NAME}_textured_v01.blend" "$SC" "${NAME}_${FAM}" eevee $HIDE $VIEWS 2>&1 | grep -i "error" || true
python -X utf8 tools/prospekt_vehicles/sheet.py "$SC/${NAME}_${FAM}.jpg" 900 "$SC/${NAME}_${FAM}_f34.png" \
  "$SC/${NAME}_${FAM}_r34.png" "$SC/${NAME}_${FAM}_low.png" "$SC/${NAME}_${FAM}_top.png"
