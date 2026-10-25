#!/usr/bin/env bash
# Транспорт «Проспекта», партия 1: собрать формы всех машин в библиотеку владельца и снять проверочные виды.
#   bash tools/prospekt_vehicles/build_all.sh [ключ …]   (по умолчанию — все семь)
# Ключи: sedan hatch wagon suv bus12 paz gazel. Выход — E:/Models Blender/VEHICLES/Город_партия1/<папка>/.
set -euo pipefail
cd "$(dirname "$0")/../.."
BL="/d/ПРОГРАММЫ/Blender 5/blender.exe"
ROOT="E:/Models Blender/VEHICLES/Город_партия1"
declare -A DIR=([sedan]="Седан" [hatch]="Хэтчбек" [wagon]="Универсал" [suv]="Внедорожник" [bus12]="Автобус_12м"
                [paz]="ПАЗ" [gazel]="ГАЗель_маршрутка")
declare -A FILE=([sedan]="Sedan" [hatch]="Hatchback" [wagon]="Wagon" [suv]="SUV" [bus12]="CityBus12" [paz]="PAZ"
                 [gazel]="Gazel_Minibus")
KEYS=("$@")
[ ${#KEYS[@]} -eq 0 ] && KEYS=(sedan hatch wagon suv bus12 paz gazel)
for k in "${KEYS[@]}"; do
  out="$ROOT/${DIR[$k]}/models/${FILE[$k]}_geometry_v01.blend"
  case $k in
    bus12|paz|gazel) "$BL" --background --factory-startup --python-exit-code 1 --python tools/prospekt_vehicles/build_bus.py -- "$k" "$out" intact,open ;;
    *) "$BL" --background --factory-startup --python-exit-code 1 --python tools/prospekt_vehicles/build_car.py -- "$k" "$out" intact,open,wreck,burnt ;;
  esac
  echo "собрано: $out"
done
