#!/usr/bin/env bash
# Транспорт «Проспекта»: колёса v2 на машины обеих партий (владелец 2026-10-29: «да, ставь на машины»). По классу:
# игровая сетка заново (game_kit.py — колёса по wheel_looks.CAR_WHEELS: стиль и вариант на класс и семью), у партии 2 —
# ливреи в новую развёртку (livery.py), затем семьи в Painter с прежним стеком кузова и цветом (sp_family.sh) и колесом
# своей семьи («wheel=стиль:вариант»). Painter с мостом запущен (задания _asset_src/prospekt_vehicles/sp_jobs).
#   bash tools/prospekt_vehicles/wheels_cars.sh [класс …]       SKIP_KIT=1 — игровая сетка уже собрана
set -euo pipefail
cd "$(dirname "$0")/../.."
BL="/d/ПРОГРАММЫ/Blender 5/blender.exe"
declare -A DIR=([sedan]=Седан [hatch]=Хэтчбек [wagon]=Универсал [suv]=Внедорожник [bus12]=Автобус_12м [paz]=ПАЗ
                [gazel]=ГАЗель_маршрутка [taxi]=Такси [police]=Полиция [van]=Фургон [ambulance]=Скорая
                [bus12_over]=Автобус_перевёрнутый)
declare -A NAME=([sedan]=Sedan [hatch]=Hatchback [wagon]=Wagon [suv]=SUV [bus12]=Bus12 [paz]=PAZ [gazel]=Gazel
                 [taxi]=Taxi [police]=Police [van]=Van [ambulance]=Ambulance [bus12_over]=Bus12Over)
# цвета краски — те же, с которыми отделка принята (партия 1 — 2026-10-26, партия 2 — 2026-10-29)
declare -A COLOR=([sedan]=0.86,0.86,0.84 [hatch]=0.42,0.06,0.07 [wagon]=0.45,0.52,0.56 [suv]=0.20,0.24,0.18
                  [bus12]=0.82,0.60,0.12 [paz]=0.85,0.84,0.78 [gazel]=0.88,0.74,0.20 [taxi]=0.93,0.74,0.12
                  [police]=0.88,0.88,0.86 [van]=0.84,0.84,0.80 [ambulance]=0.90,0.90,0.88 [bus12_over]=0.82,0.60,0.12)
KEYS=("$@")
[ ${#KEYS[@]} -eq 0 ] && KEYS=(sedan hatch wagon suv taxi police bus12 paz gazel van ambulance bus12_over)
for k in "${KEYS[@]}"; do
  case $k in taxi|police|van|ambulance|bus12_over) B=Город_партия2 ;; *) B=Город_партия1 ;; esac
  SP="E:/Games/RING-godot/_asset_src/prospekt_vehicles/$k/sp"
  GAME="E:/Models Blender/VEHICLES/$B/${DIR[$k]}/game/${NAME[$k]}_lod0_v01.blend"
  if [ -z "${SKIP_KIT:-}" ]; then
    "$BL" --background --factory-startup --python-exit-code 1 --python tools/prospekt_vehicles/game_kit.py -- \
      "$k" "$SP" "$GAME" 2>&1 | grep -E "UV .*Wheel|LOD0|сохранено|Error|Traceback" || true
  fi
  rm -f "${SP:?}"/*.assbin                            # кэш подробной формы Painter — от прежней сетки
  case $k in
    bus12|paz|gazel|van|ambulance) FAMS="clean" ;;
    bus12_over) FAMS="over" ;;
    taxi|police) FAMS="clean wreck" ;;
    *) FAMS="clean wreck burnt" ;;
  esac
  if [ "$B" = Город_партия2 ]; then                 # ливреи и маска мест — в развёртку новой сетки
    "$BL" --background --factory-startup --python-exit-code 1 --python tools/prospekt_vehicles/livery.py -- \
      "$k" "$GAME" "$SP" 2>&1 | grep -E "ливрея|маска мест|Error|Traceback" || true
  fi
  for fam in $FAMS; do
    case $fam in wreck) JOB=sp/stack_wreck.py ;; burnt) JOB=sp/stack_burnt.py ;; *) JOB=sp/stack_car.py ;; esac
    EXTRA=("color=${COLOR[$k]}" "$(python -X utf8 tools/prospekt_vehicles/wheel_looks.py arg "$k" "$fam" | tr -d '\r')")
    case $k in
      taxi|police|van|ambulance) EXTRA+=("livery=$SP/livery/livery_$fam") ;;
      bus12_over) EXTRA+=("where=$SP/livery/where_$fam") ;;
    esac
    [ "$k" = ambulance ] && EXTRA+=("seat_plastic=0.10,0.24,0.55")     # кислородные баллоны — синие
    BATCH=$B bash tools/prospekt_vehicles/sp_family.sh "${DIR[$k]}" "${NAME[$k]}" "$k" "$fam" "$JOB" "${EXTRA[@]}"
    echo "готово: $k $fam (${EXTRA[1]})"
  done
done
