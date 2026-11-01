"""AR-15 «ГРАНЬ-15»: настройки импорта карт Godot после первого `tools/godot.cmd --headless --import` — как у ВСС-М
(tools/vss_m_v8/game_imports.py).

python -X utf8 tools/ar15/game_imports.py, затем ещё раз `tools/godot.cmd --headless --import`.
Папки: assets/models/weapons/ar15 (винтовка, магазин), assets/models/attachments/supp_gran (глушитель, supp_game.py).
Как у Мосина, ПМ и ВСС-М: сжатие VRAM, mip-уровни; у нормалей — флаг карты нормалей и сглаживание шероховатости по ним
(ORM винтовки — по своей карте нормалей; у прицелов шероховатость — отдельная карта _roughness).
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DIRS = ['assets/models/weapons/ar15', 'assets/models/attachments/supp_gran']


def setp(text: str, key: str, val: str) -> str:
    pat = re.compile(r'^' + re.escape(key) + r'=.*$', re.M)
    assert pat.search(text), key
    return pat.sub(f'{key}={val}', text)


for d in DIRS:
    res = f'res://{d}/'
    for f in sorted((ROOT / d).glob('*.png.import')):
        base = f.name[:-len('.import')]
        t = f.read_text(encoding='utf-8')
        if base.endswith('_reticle.png'):
            # сетка окуляра (reticles.py): тонкие нити — без сжатия, с mip-уровнями (сглаживание в маленьком окне)
            t = setp(t, 'compress/mode', '0')
            t = setp(t, 'mipmaps/generate', 'true')
            f.write_text(t, encoding='utf-8', newline='\n')
            print('AR15_IMPORTS', d, f.name)
            continue
        t = setp(t, 'compress/mode', '2')
        t = setp(t, 'mipmaps/generate', 'true')
        t = setp(t, 'detect_3d/compress_to', '0')
        if base.endswith('_normal.png') and base.startswith('supp_'):
            # обвес-модель: шероховатость — своя карта (канал R), сглаживание по нормалям — у неё
            t = setp(t, 'compress/normal_map', '1')
        elif base.endswith('_roughness.png'):
            t = setp(t, 'roughness/mode', '2')
            t = setp(t, 'roughness/src_normal', f'"{res}{base.replace("_roughness.png", "_normal.png")}"')
        elif base.endswith('_normal.png'):
            t = setp(t, 'compress/normal_map', '1')
            t = setp(t, 'roughness/mode', '1')
            t = setp(t, 'roughness/src_normal', f'"{res}{base}"')
        elif base.endswith('_orm.png'):
            t = setp(t, 'roughness/mode', '3')  # G — шероховатость ORM; 8 от редактора Godot фильтр выключает
            t = setp(t, 'roughness/src_normal', f'"{res}{base.replace("_orm.png", "_normal.png")}"')
        f.write_text(t, encoding='utf-8', newline='\n')
        print('AR15_IMPORTS', d, f.name)
