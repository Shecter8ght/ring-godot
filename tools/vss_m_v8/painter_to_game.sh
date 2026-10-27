#!/usr/bin/env bash
# ВСС-М v8: карты, выгруженные из Substance Painter (владелец рисовал износ сам, docs/assets/vss_m_painter_manual_wear.md),
# → игра и сцены для осмотра. Наборы Painter → атласы игры:
#   receiver, steel_parts, suppressor, bare_steel → Steel (задний прицел из steel_parts — в Cerakote); sleeve → Cerakote;
#   handguard, rubber → Polymer; wood → Wood; magazine, magazine_30, rounds → Mags.
# bash tools/vss_m_v8/painter_to_game.sh [набор …] [--scenes] [--shots]
#   без наборов — все атласы; --scenes — пересобрать студию, стол и сочетания в папке сдачи; --shots — снимки в игре
#   (tools/vss_shots.tscn, VSS_ONLY=iron → docs/screens/vss_iron_*.png).
# Painter закрыть: он держит видеопамять, и запекание Cycles уходит на процессор (в разы дольше).
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT" || exit 1
B="D:/ПРОГРАММЫ/Blender 5/blender.exe"
T=tools/vss_m_v8
DELIVERY="E:/Models Blender/WEAPONS/ВСС Винторез — полный комплект/01_ВСС-М_v8"
LOG="$ROOT/_asset_src/vss_m_v8_game/painter_to_game.log"

declare -A ATLAS=([receiver]=Steel [steel_parts]="Steel Cerakote" [suppressor]=Steel [bare_steel]=Steel [sleeve]=Cerakote
                  [handguard]=Polymer [rubber]=Polymer [wood]=Wood [magazine]=Mags [magazine_30]=Mags [rounds]=Mags)
atlases="" scenes=0 shots=0
for a in "$@"; do
    case "$a" in
        --scenes) scenes=1 ;;
        --shots) shots=1 ;;
        *) [ -n "${ATLAS[$a]:-}" ] || { echo "нет такого набора: $a (есть: ${!ATLAS[*]})"; exit 1; }
           atlases="$atlases ${ATLAS[$a]}" ;;
    esac
done
atlases=$(echo $atlases | tr ' ' '\n' | sort -u | tr '\n' ' ')
[ -n "$atlases" ] || atlases="Steel Wood Polymer Cerakote Mags"

if tasklist //FI "IMAGENAME eq Adobe Substance 3D Painter.exe" 2>/dev/null | grep -qi "Painter"; then
    echo "Painter открыт — закройте его (видеопамять), затем запустите снова."
    exit 1
fi
echo "атласы: $atlases (подробно — $LOG)"
: > "$LOG"
step() { echo "== $1"; shift; "$@" >> "$LOG" 2>&1 || { echo "ОШИБКА, хвост журнала:"; tail -25 "$LOG"; exit 1; }; }
# карты Painter (_asset_src/vss_m_v8/sp_*/export) → материалы исходника → игровые карты с high-poly
step "запекание (минут 5–15)" "$B" --background --factory-startup --python-exit-code 1 --python $T/game_bake.py -- $atlases --channels color,rough,metal,normal
step "упаковка карт" python -X utf8 $T/game_pack.py $atlases
step "экспорт в assets/models/weapons/vss_m" "$B" --background --factory-startup --python-exit-code 1 --python $T/game_export.py
step "импорт Godot" env MSYS_NO_PATHCONV=1 cmd /c "tools\\godot.cmd --headless --import"
if [ "$scenes" = 1 ]; then
    SRC=_asset_src/vss_m_v8/VSS_M_v8_sp.blend
    step "студия" "$B" --background --factory-startup "$SRC" --python-exit-code 1 --python $T/scene_v8.py -- "$DELIVERY/ВСС-М_v8_студия.blend" studio painter
    step "стол" "$B" --background --factory-startup "$SRC" --python-exit-code 1 --python $T/scene_v8.py -- "$DELIVERY/ВСС-М_v8_на_столе.blend" table painter
    step "сочетания" "$B" --background --factory-startup "$DELIVERY/ВСС-М_v8_студия.blend" --python-exit-code 1 --python $T/combos_v8.py -- "$DELIVERY/ВСС-М_v8_сочетания.blend"
fi
if [ "$shots" = 1 ]; then
    step "снимки в игре" env VSS_ONLY=iron MSYS_NO_PATHCONV=1 cmd /c "tools\\godot.cmd --windowed --resolution 1920x1080 res://tools/vss_shots.tscn"
fi
git status --short assets/models/weapons/vss_m
echo "готово"
