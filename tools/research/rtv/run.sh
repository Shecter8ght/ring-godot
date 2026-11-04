#!/usr/bin/env bash
# Road to Vostok для изучения (разработчик разрешил; владелец купил игру): оглавление пакета, настройки проекта,
# окружение и свет, шейдеры, скрипты из бинарных токенов, данные и ключевые сцены — текстом в папку ВНЕ репозитория.
# В RING из этого ничего не переносить (AGENTS.md, правило 6) — только идеи и числа; разбор — docs/research/road_to_vostok.md.
#   bash tools/research/rtv/run.sh <папка вывода>      (RTV_PCK — другой путь к RTV.pck)
set -euo pipefail
OUT="${1:?папка вывода вне репозитория}"
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../../.." && pwd)"
PCK="${RTV_PCK:-E:/SteamLibrary/steamapps/common/Road to Vostok/RTV.pck}"
# Путь к Godot записан только в tools/godot.cmd — берём оттуда.
GODOT="$(grep -o '"[^"]*\.exe"' "$ROOT/tools/godot.cmd" | head -1 | tr -d '"')"
case "$(cd "$(dirname "$OUT")" 2>/dev/null && pwd || true)/" in
	"$ROOT"/*) echo "папка вывода внутри репозитория — нельзя (чужой код не коммитится)" >&2; exit 1 ;;
esac
mkdir -p "$OUT"
# Godot получает пути без подмены MSYS — отдаём их в виде Windows (E:/…).
OUT="$(cd "$OUT" && pwd -W 2>/dev/null || pwd)"
HERE_W="$(cd "$HERE" && pwd -W 2>/dev/null || pwd)"

python -I -X utf8 "$HERE/pck_list.py" "$PCK" "$OUT/files.tsv"
cut -f3 "$OUT/files.tsv" | grep '\.tres\.remap$' | grep -v '/MT_' | grep -v '/Files/' | grep -v '^UI/Buttons' \
	| sed 's#\.remap$##' > "$OUT/reslist.txt"

export MSYS_NO_PATHCONV=1 RTV_PCK="$PCK"
# Их скрипты под нашим Godot не собираются (нет их автозагрузок) — эти ошибки загрузки сцен не важны, прячем.
run() { "$GODOT" --headless --path "$HERE_W" --script "res://$1" 2>&1 | grep -vE '^(Godot Engine|ERROR: Failed to load script|SCRIPT ERROR: Parse Error|   at: |   GDScript backtrace|       \[)' || true; }

RTV_OUT="$OUT/settings.txt" RTV_SHADERS="$OUT/shaders" \
	RTV_MAPS="res://Resources/World.tscn,res://Resources/Core.tscn,res://Scenes/Village.scn" run dump.gd
RTV_SRC="$OUT/src" run degdc.gd
RTV_DATA="$OUT/data" RTV_LIST="$OUT/reslist.txt" \
	RTV_SCENES="res://Resources/Core.tscn,res://AI/Bandit/AI_Bandit.tscn,res://Items/Weapons/AKM/AKM_Rig.tscn,res://Items/Weapons/AKM/AKM.tscn,res://Resources/Simulation.tscn,res://Resources/Spawners.tscn,res://Resources/AISpawner.tscn,res://Resources/Loader.tscn,res://Resources/Database.tscn,res://Resources/World.tscn,res://Resources/Spawn.tscn,res://Resources/Cache.tscn,res://Resources/Furniture.tscn" \
	run dumpres.gd
echo "готово: $OUT (settings.txt, shaders/, src/, data/)"
