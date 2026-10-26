#!/usr/bin/env bash
# «Проспект», ограждения и город: круг отделки в открытом проекте Painter — стек слоёв → выгрузка карт → карты на
# игровую сетку в Blender → проверочные снимки игровой версии. Проект уже создан и запечён (sp_family.sh).
#   bash tools/prospekt_city/sp_cycle.sh <модуль> <задание стека> [ключ=значение …]
# Снимки — META["game_shots"] модуля (как shots: подпись, камера, цель, фокус — от начала варианта; варианты — по
# порядку game.py: VARIANTS, затем GAME["extra"]); лист → <папка выдачи>/previews/<name>_game_v01_sheet.jpg.
set -euo pipefail
cd "$(dirname "$0")/../.."
BL="/d/ПРОГРАММЫ/Blender 5/blender.exe"
MOD="$1"; JOB="$2"; shift 2
folder=$(python -X utf8 tools/prospekt_city/meta.py "$MOD" folder | tr -d '\r')
name=$(python -X utf8 tools/prospekt_city/meta.py "$MOD" name | tr -d '\r')
R="E:/Models Blender/ENVIRONMENT/Проспект_город_партия1/$folder"
W="E:/Games/RING-godot/_asset_src/prospekt_city/$name/sp"
python -X utf8 tools/prospekt_city/sp_run.py "tools/prospekt_city/$JOB" 900 -- "$@" | head -5
python -X utf8 tools/prospekt_city/sp_run.py tools/prospekt_city/sp/export.py 900 -- "out=$R/textures" \
  "spp=$R/textures/painter/${name}_v01.spp" | head -12
# пресет glTF выгружает и сетку (Untitled.* до сохранения проекта, потом — по имени проекта): в выдаче только карты
rm -f "$R/textures/"{Untitled,"${name}_v01"}.{bin,glb,gltf}
python -X utf8 tools/prospekt_city/sharpen_maps.py "$R/textures" | grep "ПУСТАЯ" || true
# плиточные карты проволоки и прутка — только тем семействам, у которых есть такие детали
wires=$(grep -o '"\(Razor\|Barbed\|Rebar\)"' "tools/prospekt_city/$MOD.py" | tr -d '"' | sort -u | tr '\n' ' ' || true)
[ -z "$wires" ] || python -X utf8 tools/prospekt_city/wire_textures.py "$R/textures" $wires >/dev/null
"$BL" --background --factory-startup --python-exit-code 1 --python tools/prospekt_city/game_apply.py -- \
  "$MOD" "$W/${name}_lod0.blend" "$R/textures" "$R/game/${name}_game_v01.blend" 2>&1 | grep -iE "error|сохранено" || true
python -X utf8 tools/prospekt_city/game_previews.py "$MOD" "$R/game/${name}_game_v01.blend"
