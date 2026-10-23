"""ПМ «пошарпанный» v01: настройки импорта Godot для карт (после первого --import).

python -X utf8 tools/pm_worn/imports.py
Карты ПМ, глушителя-обвеса и ЗОРИН К-1: сжатие видеопамяти, mip-уровни, карты нормалей — как у ВЕРАС-54 и обвесов
(tools/prepare_veras_attachments.py configure_imports). Затем --import ещё раз.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DIRS = (ROOT / 'assets/models/weapons/pm', ROOT / 'assets/models/attachments/supp_pm', ROOT / 'assets/models/attachments/zorin_k1')
n = 0
for folder in DIRS:
    for path in folder.glob('*.png.import'):
        text = path.read_text(encoding='utf-8')
        new = text.replace('compress/mode=0', 'compress/mode=2').replace('mipmaps/generate=false', 'mipmaps/generate=true')
        new = new.replace('detect_3d/compress_to=1', 'detect_3d/compress_to=0')
        if '_normal.png.import' in path.name:
            new = new.replace('compress/normal_map=0', 'compress/normal_map=1')
        if new != text:
            path.write_text(new, encoding='utf-8', newline='\n')
            n += 1
print('PM_IMPORTS_OK', n, 'files updated')
