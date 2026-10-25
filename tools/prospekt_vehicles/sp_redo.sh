#!/usr/bin/env bash
# Транспорт «Проспекта»: заново стек и карты уже запечённой семьи — открыть сохранённый проект Painter и пройти круг
# отделки (sp_cycle.sh). Для правок стеков vstacks.py без нового запекания.
#   bash tools/prospekt_vehicles/sp_redo.sh <папка машины> <Имя> <семья> <задание стека> [ключ=значение …]
set -euo pipefail
cd "$(dirname "$0")/../.."
R="E:/Models Blender/VEHICLES/Город_партия1/$1"
J=_asset_src/prospekt_vehicles/sp_jobs
TAG="redo_$2_$3"
python -X utf8 tools/prospekt_vehicles/sp_run.py tools/prospekt_vehicles/sp/open.py 120 -- \
  "spp=$R/textures/painter/$2_$3_v01.spp" "tag=$TAG" | head -1
for _ in $(seq 1 180); do [ -f "$J/_proj_$TAG.txt" ] && break; sleep 1; done
[ -f "$J/_proj_$TAG.txt" ] || { echo "проект не открылся: $TAG"; exit 1; }
sleep 3
bash tools/prospekt_vehicles/sp_cycle.sh "$@"
