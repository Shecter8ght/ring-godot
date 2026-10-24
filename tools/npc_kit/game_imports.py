"""NPC «мародёр»: настройки импорта Godot для карт игровой модели (после первого --import).

python -X utf8 tools/npc_kit/game_imports.py
Карты assets/models/characters/npc_marauder: сжатие видеопамяти, mip-уровни, карты нормалей — как у ПМ
(tools/pm_worn/imports.py). Затем --import ещё раз.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DIRS = (ROOT / "assets/models/characters/npc_marauder", ROOT / "assets/models/characters/npc_gear")
n = 0
for folder in DIRS:
    for path in folder.rglob("*.png.import"):
        text = path.read_text(encoding="utf-8")
        new = text.replace("compress/mode=0", "compress/mode=2").replace("mipmaps/generate=false", "mipmaps/generate=true")
        new = new.replace("detect_3d/compress_to=1", "detect_3d/compress_to=0")
        if "_normal.png.import" in path.name:
            new = new.replace("compress/normal_map=0", "compress/normal_map=1")
        if new != text:
            path.write_text(new, encoding="utf-8", newline="\n")
            n += 1
print("NPC_IMPORTS_OK", n, "files updated")
