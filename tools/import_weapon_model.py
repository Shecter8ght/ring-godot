"""Импорт собственной модели ПМ в assets/models/weapons через проверенный glb.

    python tools/import_weapon_model.py pm_highpoly_v5

Исходники и license.txt остаются в _asset_src; модель и встроенные PBR-текстуры
копируются в assets только после проверки дерева, масштаба и бюджета.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import shutil
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PARTS = ('Frame','Slide','Barrel','Trigger','Hammer','SlideStop','Safety','MagCatch','Magazine','Suppressor')
MARKERS = ('Muzzle','MuzzleSuppressed','SightFront','SightRear')


def read_glb(path: Path) -> dict:
    data = path.read_bytes()
    magic, version, length = struct.unpack_from('<4sII', data)
    if magic != b'glTF' or version != 2 or length != len(data):
        raise ValueError('Неверный GLB 2.0')
    chunk_length, chunk_type = struct.unpack_from('<II', data, 12)
    if chunk_type != 0x4E4F534A:
        raise ValueError('В GLB отсутствует JSON')
    return json.loads(data[20:20 + chunk_length].decode('utf-8'))


def inspect(doc: dict) -> dict:
    nodes = doc.get('nodes', [])
    names = {n.get('name'): i for i, n in enumerate(nodes)}
    required = ('PM','PM_LOD1','Rounds') + PARTS + MARKERS + tuple(p + '_LOD1' for p in PARTS)
    missing = [name for name in required if name not in names]
    if missing:
        raise ValueError('Не найдены детали/метки: ' + ', '.join(missing))
    if doc.get('animations'):
        raise ValueError('Игровая модель должна иметь покой без демонстрационных actions')
    for image in doc.get('images', []):
        if 'bufferView' not in image:
            raise ValueError('Текстура не встроена в GLB')
    def descendants(index: int) -> list[int]:
        return [index] + [i for c in nodes[index].get('children', []) for i in descendants(c)]
    branch = set(descendants(names['PM_LOD1']))
    counts = {'first_person': 0, 'third_person': 0}
    for index, node in enumerate(nodes):
        if 'mesh' not in node:
            continue
        for primitive in doc['meshes'][node['mesh']]['primitives']:
            if primitive.get('mode', 4) != 4:
                raise ValueError('Поддерживаются только треугольные сетки')
            accessor = primitive.get('indices', primitive['attributes']['POSITION'])
            counts['third_person' if index in branch else 'first_person'] += doc['accessors'][accessor]['count'] // 3
    if counts['first_person'] > 40000 or counts['third_person'] > 5000:
        raise ValueError('Превышен бюджет треугольников: ' + str(counts))
    parents = {c: i for i, n in enumerate(nodes) for c in n.get('children', [])}
    identity = [[float(i == j) for j in range(4)] for i in range(4)]
    def multiply(a: list, b: list) -> list:
        return [[sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]
    def local_matrix(node: dict) -> list:
        if 'matrix' in node:
            return [[node['matrix'][j * 4 + i] for j in range(4)] for i in range(4)]
        x, y, z, w = node.get('rotation', [0,0,0,1])
        scale = node.get('scale', [1,1,1]);translation = node.get('translation', [0,0,0])
        rotation = [[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],
                    [2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],
                    [2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]]
        return [[rotation[i][j] * scale[j] for j in range(3)] + [translation[i]] for i in range(3)] + [[0,0,0,1]]
    world_cache: dict = {}
    def world_matrix(index: int) -> list:
        if index not in world_cache:
            parent_matrix = world_matrix(parents[index]) if index in parents else identity
            world_cache[index] = multiply(parent_matrix, local_matrix(nodes[index]))
        return world_cache[index]
    def position(name: str) -> list:
        matrix = world_matrix(names[name]);return [matrix[i][3] for i in range(3)]
    # Позиции независимо взяты из защищённого исходника v5 и заданной точки хвата.
    # Проверка только совпадения manifest и GLB пропустила бы две одинаковые нулевые ошибки.
    sx = 161.0 / 161.5
    def source_point(x: float, y: float, z: float) -> list:
        return [-y, z-.0495, -(x-.0495)*sx]
    expected_positions = {
        'Muzzle': source_point(-.08172864,0,.11253256),
        'MuzzleSuppressed': source_point(-.2402039,0,.11253256),
        'SightFront': source_point(-.0727,0,.12675),
        'SightRear': source_point(.0614,0,.12675),
        'Trigger': source_point(-.004919486586004496,0,.08879262953996658),
        'Hammer': source_point(.06812824308872223,0,.09929654747247696),
        'Magazine': source_point(.042,0,.081),
        'Suppressor': source_point(-.08065,0,.11253256),
    }
    for name, expected in expected_positions.items():
        measured = position(name)
        if not all(math.isfinite(v) for v in measured) or any(abs(a-b)>.0005 for a,b in zip(measured,expected)):
            raise ValueError(f'Неверная мировая позиция {name}: {measured}, ожидается {expected}')
    if position('Muzzle')[2] <= .1 or position('MuzzleSuppressed')[2] <= position('Muzzle')[2]+.1:
        raise ValueError('Дульные метки должны находиться на реальных срезах, а не в корне')
    if position('SightRear')[2] >= position('SightFront')[2]:
        raise ValueError('Целик должен быть позади мушки')
    if parents.get(names['Rounds']) != names['Magazine']:
        raise ValueError('Патроны должны следовать за магазином')
    round_nodes = nodes[names['Rounds']].get('children', [])
    if [nodes[index].get('name') for index in round_nodes] != [f'Round_{i:02}' for i in range(1, 9)]:
        raise ValueError('Rounds должен содержать восемь отдельных патронов снизу вверх')
    if parents.get(names['Safety']) != names['Slide']:
        raise ValueError('Предохранитель должен следовать за затвором')
    return {'triangles': counts, 'embedded_images': len(doc.get('images', [])), 'nodes': len(nodes),
            'verified_world_positions_m': {name:position(name) for name in expected_positions}}


def embedded_pngs(model: Path, doc: dict) -> dict[str, bytes]:
    """Извлечённые Godot PNG обновляются теми же байтами, что встроены в новый GLB."""
    data = model.read_bytes();json_length = struct.unpack_from('<I', data, 12)[0]
    offset = 20 + json_length
    binary_length, kind = struct.unpack_from('<II', data, offset)
    if kind != 0x004E4942:
        raise ValueError('Нет встроенного BIN блока GLB')
    binary = data[offset+8:offset+8+binary_length]
    images: dict[str, bytes] = {}
    for image in doc.get('images', []):
        name = image.get('name', '')
        if name not in ('pm_base_color','pm_normal','pm_orm'):
            raise ValueError(f'Неизвестная PBR-карта: {name}')
        view = doc['bufferViews'][image['bufferView']]
        if view.get('buffer', 0) != 0:
            raise ValueError('Карта не входит в главный BIN блок')
        start = view.get('byteOffset', 0);payload = binary[start:start+view['byteLength']]
        if not payload.startswith(b'\x89PNG\r\n\x1a\n'):
            raise ValueError('Ожидается встроенная PNG-карта')
        images[name] = payload
    if set(images) != {'pm_base_color','pm_normal','pm_orm'}:
        raise ValueError('Нужны все три PBR-карты')
    return images


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source_id', choices=['pm_highpoly_v5'])
    args = parser.parse_args()
    src = ROOT / '_asset_src' / args.source_id
    license_path = src / 'license.txt'
    license_text = license_path.read_text(encoding='utf-8')
    if 'собственная модель' not in license_text.lower() or 'владелец' not in license_text.lower():
        raise SystemExit('Нет явного разрешения владельца для собственной модели')
    model = src / 'pm.glb'
    doc = read_glb(model);facts = inspect(doc);images = embedded_pngs(model, doc)
    for name, payload in images.items():
        if hashlib.sha256(payload).digest() != hashlib.sha256((src / (name+'.png')).read_bytes()).digest():
            raise SystemExit(f'Встроенная {name} устарела относительно запечённой PNG: перепакуйте изображение')
    manifest = json.loads((src / 'export_manifest.json').read_text(encoding='utf-8'))
    if manifest['source_sha256_before'] != manifest['source_sha256_after']:
        raise SystemExit('Исходник изменился во время экспорта')
    expected = [30.5,126.75,161.0]
    measured = manifest['bounds']['base']['size_gltf_mm']
    if any(abs(a-b) > .4 for a,b in zip(measured, expected)):
        raise SystemExit(f'Габариты вне допуска: {measured}, ожидается {expected}')
    dst = ROOT / 'assets' / 'models' / 'weapons' / 'pm'
    dst.mkdir(parents=True, exist_ok=True)
    temp = dst / 'pm.glb.tmp'
    shutil.copy2(model, temp)
    temp.replace(dst / 'pm.glb')
    # Godot может сохранить уже извлечённый файл при повторном импорте GLB.
    # Публикуем карты через этот же tools importer и исключаем старый normal atlas.
    for name, payload in images.items():
        image_path = dst / ('pm_'+name+'.png')
        image_temp = image_path.with_suffix('.png.tmp');image_temp.write_bytes(payload);image_temp.replace(image_path)
    credits = ROOT / 'assets' / 'CREDITS.md'
    old = credits.read_text(encoding='utf-8') if credits.exists() else ''
    start, end = '<!-- PM_MODEL_START -->', '<!-- PM_MODEL_END -->'
    section = f'''{start}
## Пистолет ПМ

- `assets/models/weapons/pm/pm.glb` — собственная модель, сделана для RING; владелец — автор проекта. Предоставленный владельцем `PM_Highpoly_v5.blend` сохранён отдельной неизменённой копией в `_asset_src/pm_highpoly_v5/`.
- Игровая копия, PBR-атласы цвета/ORM/normal и два уровня детализации подготовлены `tools/export_pm_game.py`; импорт — `tools/import_weapon_model.py`. Фото служили референсами формы; их пиксели в игровых текстурах не использованы. Текстуры запечены из собственных процедурных материалов и highpoly-геометрии.
{end}'''
    if start in old:
        before, rest = old.split(start, 1)
        _, after = rest.split(end, 1)
        updated = before + section + after
    else:
        updated = old.rstrip() + '\n\n' + section + '\n'
    credits.write_text(updated, encoding='utf-8', newline='\n')
    facts['sha256'] = hashlib.sha256(model.read_bytes()).hexdigest()
    print('готово: res://assets/models/weapons/pm/pm.glb')
    print(json.dumps(facts, ensure_ascii=False))


if __name__ == '__main__':
    main()
