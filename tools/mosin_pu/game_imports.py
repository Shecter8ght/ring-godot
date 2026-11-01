"""Мосин ПУ: настройки импорта карт Godot после первого `tools/godot.cmd --headless --import`.

python -X utf8 tools/mosin_pu/game_imports.py, затем ещё раз `tools/godot.cmd --headless --import`.
Godot извлекает карты из mosin_pu.glb, mosin_pu_round.glb и mosin_pu_clip.glb без сжатия (4K RGBA — ~85 МБ видеопамяти каждая).
Ставятся настройки, как у ПМ (assets/models/weapons/pm): сжатие VRAM, mip-уровни; у нормалей — флаг карты нормалей, у ORM —
сглаживание шероховатости по нормали.
"""
import re
from pathlib import Path

D = Path(__file__).resolve().parents[2] / 'assets/models/weapons/mosin_pu'
RES = 'res://assets/models/weapons/mosin_pu/'


def setp(text: str, key: str, val: str) -> str:
    pat = re.compile(r'^' + re.escape(key) + r'=.*$', re.M)
    assert pat.search(text), key
    return pat.sub(f'{key}={val}', text)


for f in sorted(D.glob('*.png.import')):
    base = f.name[:-len('.import')]
    t = f.read_text(encoding='utf-8')
    t = setp(t, 'compress/mode', '2')
    t = setp(t, 'mipmaps/generate', 'true')
    t = setp(t, 'detect_3d/compress_to', '0')
    if base.endswith('_normal.png'):
        t = setp(t, 'compress/normal_map', '1')
        t = setp(t, 'roughness/mode', '1')
        t = setp(t, 'roughness/src_normal', f'"{RES}{base}"')
    elif base.endswith('_orm.png'):
        t = setp(t, 'roughness/mode', '3')  # G — шероховатость ORM; 8 от редактора Godot фильтр выключает
        t = setp(t, 'roughness/src_normal', f'"{RES}{base.replace("_orm.png", "_normal.png")}"')
    f.write_text(t, encoding='utf-8')
    print('MOSIN_IMPORTS', f.name)
