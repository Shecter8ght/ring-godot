"""Магазины ВЕРАС-54: настройки импорта карт Godot после первого `tools/godot.cmd --headless --import` (как game_imports.py
автомата): сжатие VRAM, mip-уровни; у нормалей — флаг карты нормалей, у ORM — сглаживание шероховатости по нормали;
маски _wear и _coat — сжатие высокого качества (BPTC).

python -X utf8 tools/veras54_mags/mags_game_imports.py, затем ещё раз `tools/godot.cmd --headless --import`.
"""
import re
from pathlib import Path

D = Path(__file__).resolve().parents[2] / 'assets/models/weapons/veras54_mags'
RES = 'res://assets/models/weapons/veras54_mags/'


def setp(text: str, key: str, val: str) -> str:
    pat = re.compile(r'^' + re.escape(key) + r'=.*$', re.M)
    assert pat.search(text), key
    return pat.sub(f'{key}={val}', text)


for f in sorted(D.glob('veras54_*.png.import')):
    base = f.name[:-len('.import')]
    t = f.read_text(encoding='utf-8')
    t = setp(t, 'compress/mode', '2')
    t = setp(t, 'mipmaps/generate', 'true')
    t = setp(t, 'detect_3d/compress_to', '0')
    if base.endswith(('_wear.png', '_coat.png')):
        t = setp(t, 'compress/high_quality', 'true')
    elif base.endswith('_normal.png'):
        t = setp(t, 'compress/normal_map', '1')
        t = setp(t, 'roughness/mode', '1')
        t = setp(t, 'roughness/src_normal', f'"{RES}{base}"')
    elif base.endswith('_orm.png'):
        t = setp(t, 'roughness/mode', '8')
        t = setp(t, 'roughness/src_normal', f'"{RES}{base.replace("_orm.png", "_normal.png")}"')
    f.write_text(t, encoding='utf-8', newline='\n')
    print('MAGS_IMPORTS', f.name)
