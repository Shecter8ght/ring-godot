#!/usr/bin/env bash
# «Проспект», ограждения и город: семейство с нуля — игровая сетка и FBX (game.py), проект Painter на игровой сетке,
# запекание с подробной формы, затем круг отделки (sp_cycle.sh). Painter с мостом уже запущен (своя папка заданий
# _asset_src/prospekt_city/sp_jobs). Один проект Painter на всех: перед запуском взять замок (sp_lock.py).
#   bash tools/prospekt_city/sp_family.sh <модуль> <задание стека> [ключ=значение …]
# Из GAME модуля: res — разрешение наборов («11» — 2048, «11x10» — 2048 × 1024), ray — дальность луча запекания
# (доля размера сцены, по умолчанию 0,006; у тонкой решётки меньше).
set -euo pipefail
cd "$(dirname "$0")/../.."
BL="/d/ПРОГРАММЫ/Blender 5/blender.exe"
MOD="$1"; JOB="$2"; shift 2
name=$(python -X utf8 tools/prospekt_city/meta.py "$MOD" name | tr -d '\r')
W="E:/Games/RING-godot/_asset_src/prospekt_city/$name/sp"
GAMEPY="import ast,sys;t=ast.parse(open('tools/prospekt_city/$MOD.py',encoding='utf-8').read());g=[ast.literal_eval(n.value) for n in t.body if isinstance(n,ast.Assign) and getattr(n.targets[0],'id','')=='GAME'][0]"
RES=$(python -X utf8 -c "$GAMEPY;sys.stdout.write(','.join(f'{k}:{v}' for k,v in g['res'].items()))" | tr -d '\r')
RAY=$(python -X utf8 -c "$GAMEPY;sys.stdout.write(str(g.get('ray',0.006)))" | tr -d '\r')
"$BL" --background --factory-startup --python-exit-code 1 --python tools/prospekt_city/game.py -- "$MOD" "$W" 2>&1 \
  | grep -E "LOD0|UV |наборы|Error|Traceback" || true
[ -f "$W/${name}_low.fbx" ] || { echo "нет игровой сетки"; exit 1; }
python -X utf8 tools/prospekt_city/sp_run.py tools/prospekt_city/sp/create.py 120 -- "low=$W/${name}_low.fbx" "tag=$MOD" | head -2
python -X utf8 tools/prospekt_city/sp_run.py --wait "_proj_$MOD.txt" 300 >/dev/null
python -X utf8 tools/prospekt_city/sp_run.py tools/prospekt_city/sp/bake.py 120 -- "high=$W/${name}_high.fbx" "res=$RES" \
  "rel=$RAY" "tag=$MOD" | head -2
echo "запечено: $(python -X utf8 tools/prospekt_city/sp_run.py --wait "_bake_$MOD.txt" 2400)"
bash tools/prospekt_city/sp_cycle.sh "$MOD" "$JOB" "$@"
