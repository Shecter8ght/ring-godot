#!/usr/bin/env bash
# Транспорт «Проспекта», партия 2: отделка — ливреи и маска мест в развёртку (livery.py), затем семьи в Substance Painter
# с нуля (sp_family.sh: проект, запекание, стек «Краска v2» с ливреей, карты, Blender, снимки). Игровая сетка уже есть
# (game_kit.py → <машина>/game/<Имя>_lod0_v01.blend), Painter с мостом запущен (задания _asset_src/prospekt_vehicles/sp_jobs).
#   bash tools/prospekt_vehicles/batch2_finish.sh [taxi police van ambulance bus12_over]
set -euo pipefail
cd "$(dirname "$0")/../.."
BL="/d/ПРОГРАММЫ/Blender 5/blender.exe"
export BATCH=Город_партия2
ROOT="E:/Models Blender/VEHICLES/$BATCH"
declare -A DIR=([taxi]=Такси [police]=Полиция [van]=Фургон [ambulance]=Скорая [bus12_over]=Автобус_перевёрнутый)
declare -A NAME=([taxi]=Taxi [police]=Police [van]=Van [ambulance]=Ambulance [bus12_over]=Bus12Over)
# основной цвет ливреи (для выгорания и мелкого тона краски); у перевёрнутого — краска принятого автобуса 12 м
declare -A COLOR=([taxi]=0.93,0.74,0.12 [police]=0.88,0.88,0.86 [van]=0.84,0.84,0.80 [ambulance]=0.90,0.90,0.88
                  [bus12_over]=0.82,0.60,0.12)
KEYS=("$@")
[ ${#KEYS[@]} -eq 0 ] && KEYS=(taxi police van ambulance bus12_over)
for k in "${KEYS[@]}"; do
  SP="E:/Games/RING-godot/_asset_src/prospekt_vehicles/$k/sp"
  "$BL" --background --factory-startup --python-exit-code 1 --python tools/prospekt_vehicles/livery.py -- \
    "$k" "$ROOT/${DIR[$k]}/game/${NAME[$k]}_lod0_v01.blend" "$SP" 2>&1 | grep -E "ливрея|маска мест|Error|Traceback" || true
  case $k in
    taxi|police) FAMS="clean wreck" ;;
    bus12_over) FAMS="over" ;;
    *) FAMS="clean" ;;
  esac
  for fam in $FAMS; do
    JOB=sp/stack_car.py
    [ "$fam" = wreck ] && JOB=sp/stack_wreck.py
    if [ "$k" = bus12_over ]; then PIC="where=$SP/livery/where_$fam"; else PIC="livery=$SP/livery/livery_$fam"; fi
    EXTRA=()
    [ "$k" = ambulance ] && EXTRA=("seat_plastic=0.10,0.24,0.55")     # кислородные баллоны — синие
    bash tools/prospekt_vehicles/sp_family.sh "${DIR[$k]}" "${NAME[$k]}" "$k" "$fam" "$JOB" "color=${COLOR[$k]}" "$PIC"       ${EXTRA[@]+"${EXTRA[@]}"}
    echo "готово: $k $fam"
  done
done
