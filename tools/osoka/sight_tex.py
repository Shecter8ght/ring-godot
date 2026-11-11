"""«Осока», тепловизор ПН-36Т «ПОЛЫНЬ», текстуры этап 1 на игровой сетке — заготовки для Painter тем же кодом, что
у «Осоки» (tools/osoka/game_tex.py без изменений: исходник читается и в нём подменяются пути и наборы).

"D:/ПРОГРАММЫ/Blender 5/blender.exe" -b -y --factory-startup --python-exit-code 1 --python tools/osoka/sight_tex.py -- [fbx] [maps] [normals]
→ _asset_src/osoka_polyn/tex/ (не в git): Polyn_low.fbx, Polyn_high.fbx (слоты «Polyn__<слот>_low/_high»), meshes.json,
  parts.json, scene.json, px_mm.json, Polyn_maps.npz (положение, нормаль, номер детали в пикселях развёртки),
  normals/Polyn_normal.png (запекание в Blender с принятой формы v03).
"""
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = (HERE / "game_tex.py").read_text(encoding="utf-8")
SUBS = [
    ("MODEL = Path('E:/Models Blender/WEAPONS/Верба — модель')",
     "MODEL = Path('E:/Models Blender/WEAPONS/Верба — модель/Тепловизор')"),
    ("HP = MODEL / 'work/osoka_v07.blend'", "HP = MODEL / 'Тепловизор_геометрия_v03.blend'"),
    ("LP = MODEL / 'work/osoka_game_uv_v01.blend'", "LP = MODEL / 'work/thermal_game_uv_v01.blend'"),
    ("OUT = ROOT / '_asset_src/osoka/tex'", "OUT = ROOT / '_asset_src/osoka_polyn/tex'"),
    ("RES = {'Tube': 4096, 'Launcher': 4096, 'Missile': 2048}", "RES = {'Polyn': 4096}"),
    ("MAP_SETS = ('Tube', 'Missile', 'Launcher')", "MAP_SETS = ('Polyn',)"),
    (".replace('Osoka_', '') if o.data.materials else 'Launcher'", ".replace('Polyn_', '') if o.data.materials else 'Polyn'"),
    ("'work/osoka_game_uv_v01_uv.json'", "'work/thermal_game_uv_v01_uv.json'"),
    ("OUT / 'Osoka_low.fbx'", "OUT / 'Polyn_low.fbx'"),
    ("OUT / 'Osoka_high.fbx'", "OUT / 'Polyn_high.fbx'"),
    ("print('OSOKA_TEX'", "print('POLYN_TEX'"),
]
for a, b in SUBS:
    if a not in SRC:
        raise SystemExit(f"game_tex.py изменился — нет строки: {a}")
    SRC = SRC.replace(a, b)
G = {"__name__": "__main__", "__file__": str(HERE / "game_tex.py")}
sys.path.insert(0, str(HERE))
exec(compile(SRC, "game_tex.py (ПОЛЫНЬ)", "exec"), G)
