"""ВСС-М v8: настройки импорта карт Godot после первого `tools/godot.cmd --headless --import`.

python -X utf8 tools/vss_m_v8/game_imports.py, затем ещё раз `tools/godot.cmd --headless --import`.
Папки: assets/models/weapons/vss_m (винтовка, магазины), assets/models/attachments/pso_vss и scope_4x32 (прицелы).
Как у Мосина и ПМ: сжатие VRAM, mip-уровни; у нормалей — флаг карты нормалей и сглаживание шероховатости по ним
(ORM винтовки — по своей карте нормалей; у прицелов шероховатость — отдельная карта _roughness).
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DIRS = ['assets/models/weapons/vss_m', 'assets/models/attachments/pso_vss', 'assets/models/attachments/scope_4x32']


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
            print('VSS_IMPORTS', d, f.name)
            continue
        t = setp(t, 'compress/mode', '2')
        t = setp(t, 'mipmaps/generate', 'true')
        t = setp(t, 'detect_3d/compress_to', '0')
        if base.endswith('_normal.png'):
            t = setp(t, 'compress/normal_map', '1')
            t = setp(t, 'roughness/mode', '1')
            t = setp(t, 'roughness/src_normal', f'"{res}{base}"')
        elif base.endswith('_orm.png'):
            t = setp(t, 'roughness/mode', '8')
            t = setp(t, 'roughness/src_normal', f'"{res}{base.replace("_orm.png", "_normal.png")}"')
        f.write_text(t, encoding='utf-8', newline='\n')
        print('VSS_IMPORTS', d, f.name)
