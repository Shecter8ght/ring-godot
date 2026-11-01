"""Фильтр шероховатости в настройках импорта карт Godot: найти и исправить значения за перечнем.

`roughness/mode` — Detect 0, Disabled 1, Red 2, Green 3, Blue 4, Alpha 5, Gray 6 (канал = mode − 2). При «Detect»
редактор Godot 4.7.2 сам вписывает канал, когда видит карту в материале, но у карты, которую шейдер берёт с подсказкой
`hint_default_white`, пишет 8 (в `material_storage.cpp` условие «или» вместо «и») — и фильтр по карте нормалей молча
не работает (`Image::generate_mipmap_roughness` с каналом 6 ничего не делает). Навык godot-asset-preparation, godot-checks.md.

Канал — по имени карты: ORM / ARM / occlusionRoughnessMetallic / metallicRoughness / specularGlossiness (её glTF-импорт
Godot переводит в шероховатость G) — 3; отдельная серая шероховатость — 6; остальное только в списке, руками.
Ещё в списке: фильтр включён, а карты нормалей `roughness/src_normal` нет или выключены mip-уровни (фильтр их правит).

python -X utf8 tools/asset_kit/roughness_imports.py          список
python -X utf8 tools/asset_kit/roughness_imports.py --fix    исправить, затем tools/godot.cmd --headless --import
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKIP = ('.godot', '.git', '_asset_src', 'export')
MODE_MAX = 6
GREEN = 3
GRAY = 6
PACKED = re.compile(r'(^|[_\-.])(orm|arm)([_\-.]|$)|occlusionroughness|metallicroughness|specularglossiness')
MODE_LINE = re.compile(r'^roughness/mode=(\d+)(\r?)$', re.M)


def channel_for(name: str) -> int:
    """Канал шероховатости по имени карты; 0 — не понять, оставить человеку."""
    low = name.lower()
    if PACKED.search(low):
        return GREEN
    if 'rough' in low:
        return GRAY
    return 0


def param(text: str, key: str) -> str:
    m = re.search(rf'^{re.escape(key)}=(.*?)\r?$', text, re.M)
    return m.group(1) if m else ''


def main() -> int:
    fix = '--fix' in sys.argv[1:]
    bad: list[str] = []
    fixed = 0
    for imp in sorted(ROOT.rglob('*.import')):
        rel = imp.relative_to(ROOT).as_posix()
        if rel.split('/', 1)[0] in SKIP:
            continue
        text = imp.read_bytes().decode('utf-8')
        m = MODE_LINE.search(text)
        if m is None or param(text, 'importer') != '"texture"':
            continue
        mode = int(m.group(1))
        if mode > MODE_MAX:
            ch = channel_for(imp.name[:-len('.import')])
            if fix and ch:
                text = text[:m.start()] + f'roughness/mode={ch}{m.group(2)}' + text[m.end():]
                imp.write_bytes(text.encode('utf-8'))
                fixed += 1
                print(f'ROUGHNESS_FIX {rel}: {mode} -> {ch}')
            else:
                bad.append(f'{rel}: mode={mode}' + (f' (надо {ch})' if ch else ' (канал не понять по имени)'))
            continue
        if mode >= 2:
            src = param(text, 'roughness/src_normal').strip('"')
            if not src or not (ROOT / src.removeprefix('res://')).exists():
                bad.append(f'{rel}: mode={mode}, нет карты нормалей «{src}»')
            elif param(text, 'mipmaps/generate') != 'true':
                bad.append(f'{rel}: mode={mode}, mip-уровни выключены — фильтру нечего править')
    for line in bad:
        print('ROUGHNESS_BAD', line)
    print(f'ROUGHNESS исправлено {fixed}, осталось {len(bad)}')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
