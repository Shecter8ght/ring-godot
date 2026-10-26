#!/usr/bin/env bash
# Транспорт «Проспекта»: семья машины в Substance Painter с нуля — проект на игровой сетке, запекание с подробной формы,
# затем круг отделки (sp_cycle.sh: стек → карты → Blender → снимки). Painter с мостом уже запущен (sp_run.py).
#   bash tools/prospekt_vehicles/sp_family.sh <папка машины> <Имя> <класс> <семья> <задание стека> [ключ=значение …]
# Пример: bash tools/prospekt_vehicles/sp_family.sh Хэтчбек Hatchback hatch clean sp/stack_car.py color=0.42,0.07,0.08
set -euo pipefail
cd "$(dirname "$0")/../.."
FOLDER="$1"; NAME="$2"; CLS="$3"; FAM="$4"; JOB="$5"; shift 5
SP="E:/Games/RING-godot/_asset_src/prospekt_vehicles/$CLS/sp"
J=_asset_src/prospekt_vehicles/sp_jobs
TAG="${CLS}_${FAM}"
case $CLS in
  bus12) RES="BodyA:11,BodyB:11,Interior:11,Wheel:10,Under:10" ;;
  paz) RES="BodyA:11,BodyB:11,Interior:10,Wheel:10,Under:10" ;;
  gazel) RES="Body:11,Interior:10,Wheel:10,Under:10" ;;
  *) RES="Body:11,BodyA:11,BodyB:11,Interior:10,Wheel:10,Under:9" ;;
esac

wait_mark() {                                    # ждать файл-метку моста (секунд не больше $2)
  for _ in $(seq 1 "$2"); do [ -f "$J/$1" ] && return 0; sleep 1; done
  echo "нет метки $1 за $2 с"; return 1
}

python -X utf8 tools/prospekt_vehicles/sp_run.py tools/prospekt_vehicles/sp/create.py 120 -- "low=$SP/${FAM}_low.fbx" \
  "tag=$TAG" | head -2
wait_mark "_proj_$TAG.txt" 300
sleep 5                                          # полки и сетка дочитываются после входа в проект
python -X utf8 tools/prospekt_vehicles/sp_run.py tools/prospekt_vehicles/sp/bake.py 120 -- "high=$SP/${FAM}_high.fbx" \
  "res=$RES" "tag=$TAG" | head -2
wait_mark "_bake_$TAG.txt" 2400
echo "запечено: $(cat "$J/_bake_$TAG.txt")"
bash tools/prospekt_vehicles/sp_cycle.sh "$FOLDER" "$NAME" "$FAM" "$JOB" "$@"
