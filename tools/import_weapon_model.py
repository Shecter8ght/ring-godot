"""Импорт собственных моделей оружия в assets/models/weapons через проверенный glb.

    python tools/import_weapon_model.py pm_highpoly_v5
    python tools/import_weapon_model.py glock17_gen5
    python tools/import_weapon_model.py glock17_gen5 --check   # только проверки, без записи

Исходники и license.txt остаются в _asset_src; модель и встроенные PBR-текстуры
копируются в assets только после проверки дерева, масштаба и бюджета. Что проверять у
каждой модели — таблица SPECS внизу файла.
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
# Glock: ударниковый, без курка и флажка предохранителя; глушитель только процедурный обвес.
GLOCK_PARTS = ('Frame','Slide','Barrel','Trigger','SlideStop','MagCatch','Magazine')
GLOCK_ABSENT = ('Hammer','Safety','Suppressor')
GLOCK_IMAGES = ('glock_metal_base_color','glock_metal_normal','glock_metal_orm',
                'glock_polymer_base_color','glock_polymer_normal','glock_polymer_orm')
GLOCK_ROUNDS = 17
# Санитарное окно габаритов Glock 17 Gen5 с магазином, мм [ширина, высота, длина]
# (заводские около 34 × 139 × 202): вне окна — сломан масштаб или оси экспорта.
GLOCK_BOUNDS_MIN_MM = (28.0, 125.0, 190.0)
GLOCK_BOUNDS_MAX_MM = (37.0, 150.0, 210.0)
BOUNDS_TOLERANCE_MM = .4
TRIS_LOD0_MAX = 40000
TRIS_LOD1_MAX = 5000


def read_glb(path: Path) -> dict:
    data = path.read_bytes()
    magic, version, length = struct.unpack_from('<4sII', data)
    if magic != b'glTF' or version != 2 or length != len(data):
        raise ValueError('Неверный GLB 2.0')
    chunk_length, chunk_type = struct.unpack_from('<II', data, 12)
    if chunk_type != 0x4E4F534A:
        raise ValueError('В GLB отсутствует JSON')
    return json.loads(data[20:20 + chunk_length].decode('utf-8'))


def inspect_pm(doc: dict) -> dict:
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


class Scene:
    """Мировые матрицы и вершины glb: одна арифметика для всех проверок дерева Glock."""

    def __init__(self, doc: dict, binary: bytes) -> None:
        self.doc = doc;self.binary = binary
        self.nodes = doc.get('nodes', [])
        self.names = {n.get('name'): i for i, n in enumerate(self.nodes)}
        self.parents = {c: i for i, n in enumerate(self.nodes) for c in n.get('children', [])}
        self._world: dict[int, list] = {}

    @staticmethod
    def _multiply(a: list, b: list) -> list:
        return [[sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]

    @staticmethod
    def _local(node: dict) -> list:
        if 'matrix' in node:
            return [[node['matrix'][j * 4 + i] for j in range(4)] for i in range(4)]
        x, y, z, w = node.get('rotation', [0,0,0,1])
        scale = node.get('scale', [1,1,1]);translation = node.get('translation', [0,0,0])
        rotation = [[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],
                    [2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],
                    [2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]]
        return [[rotation[i][j] * scale[j] for j in range(3)] + [translation[i]] for i in range(3)] + [[0,0,0,1]]

    def world(self, index: int) -> list:
        if index not in self._world:
            parent = self.world(self.parents[index]) if index in self.parents else [[float(i == j) for j in range(4)] for i in range(4)]
            self._world[index] = self._multiply(parent, self._local(self.nodes[index]))
        return self._world[index]

    def relative(self, name: str, ancestor: str) -> list:
        """Позиция узла в осях корня модели (начало корня — точка хвата)."""
        a = self.world(self.names[ancestor]);p = self.world(self.names[name])
        # Корень без поворота и масштаба: игра считает его осями модели.
        if any(abs(a[i][j] - float(i == j)) > 1e-6 for i in range(3) for j in range(3)):
            raise ValueError(f'Корень {ancestor} повёрнут или масштабирован при экспорте')
        return [p[i][3] - a[i][3] for i in range(3)]

    def descendants(self, index: int) -> list[int]:
        return [index] + [i for c in self.nodes[index].get('children', []) for i in self.descendants(c)]

    def parent_name(self, name: str) -> str:
        index = self.parents.get(self.names[name])
        return self.nodes[index].get('name', '') if index is not None else ''

    def triangles(self, root: str) -> int:
        total = 0
        for index in self.descendants(self.names[root]):
            node = self.nodes[index]
            if 'mesh' not in node:
                continue
            for primitive in self.doc['meshes'][node['mesh']]['primitives']:
                if primitive.get('mode', 4) != 4:
                    raise ValueError('Поддерживаются только треугольные сетки')
                accessor = primitive.get('indices', primitive['attributes']['POSITION'])
                total += self.doc['accessors'][accessor]['count'] // 3
        return total

    def bounds_mm(self, root: str) -> list[float]:
        """Точные габариты по вершинам: AABB наклонённых деталей раздул бы размер."""
        lo = [math.inf] * 3;hi = [-math.inf] * 3
        for index in self.descendants(self.names[root]):
            node = self.nodes[index]
            if 'mesh' not in node:
                continue
            m = self.world(index)
            for primitive in self.doc['meshes'][node['mesh']]['primitives']:
                accessor = self.doc['accessors'][primitive['attributes']['POSITION']]
                if accessor.get('componentType') != 5126 or accessor.get('type') != 'VEC3' or 'sparse' in accessor:
                    raise ValueError('Ожидаются вершины float VEC3 без sparse и квантования')
                view = self.doc['bufferViews'][accessor['bufferView']]
                stride = view.get('byteStride', 12)
                start = view.get('byteOffset', 0) + accessor.get('byteOffset', 0)
                for k in range(accessor['count']):
                    x, y, z = struct.unpack_from('<3f', self.binary, start + k * stride)
                    for i in range(3):
                        v = m[i][0]*x + m[i][1]*y + m[i][2]*z + m[i][3]
                        if v < lo[i]: lo[i] = v
                        if v > hi[i]: hi[i] = v
        return [(hi[i] - lo[i]) * 1000.0 for i in range(3)]


def glb_binary(model: Path) -> bytes:
    data = model.read_bytes();json_length = struct.unpack_from('<I', data, 12)[0]
    offset = 20 + json_length
    binary_length, kind = struct.unpack_from('<II', data, offset)
    if kind != 0x004E4942:
        raise ValueError('Нет встроенного BIN блока GLB')
    return data[offset+8:offset+8+binary_length]


def inspect_glock(doc: dict, model: Path) -> dict:
    """Дерево по контракту экспорта Glock 17 Gen5: детали на своих осях, метки на затворе, 17 патронов."""
    scene = Scene(doc, glb_binary(model))
    names = scene.names
    required = (('Glock','Glock_LOD1','Rounds','Rounds_LOD1','Round_01_LOD1') + GLOCK_PARTS + MARKERS
                + tuple(p + '_LOD1' for p in GLOCK_PARTS))
    missing = [name for name in required if name not in names]
    if missing:
        raise ValueError('Не найдены детали/метки: ' + ', '.join(missing))
    extra = [name for base in GLOCK_ABSENT for name in (base, base + '_LOD1') if name in names]
    if extra:
        raise ValueError('У Glock нет курка, предохранителя и своего глушителя: ' + ', '.join(extra))
    if doc.get('animations'):
        raise ValueError('Игровая модель должна иметь покой без демонстрационных actions')
    for image in doc.get('images', []):
        if 'bufferView' not in image:
            raise ValueError('Текстура не встроена в GLB')
    # Ветки — соседи: вложенный LOD1 рисовался бы вместе с LOD0.
    if names['Glock_LOD1'] in scene.descendants(names['Glock']) or names['Glock'] in scene.descendants(names['Glock_LOD1']):
        raise ValueError('Glock и Glock_LOD1 должны быть отдельными ветками')
    for suffix, root in (('', 'Glock'), ('_LOD1', 'Glock_LOD1')):
        expected_parents = {'Frame': root, 'Slide': root, 'Barrel': root, 'Magazine': root,
                            'Trigger': 'Frame' + suffix, 'SlideStop': 'Frame' + suffix,
                            'MagCatch': 'Frame' + suffix, 'Rounds': 'Magazine' + suffix}
        for part, parent in expected_parents.items():
            if scene.parent_name(part + suffix) != parent:
                raise ValueError(f'{part + suffix} должен быть дочерним {parent}, а не {scene.parent_name(part + suffix)}')
    slide_branch = set(scene.descendants(names['Slide']))
    for marker in MARKERS:
        if names[marker] not in slide_branch:
            raise ValueError(f'Метка {marker} должна ехать с затвором (внутри Slide)')
    round_nodes = scene.nodes[names['Rounds']].get('children', [])
    if [scene.nodes[i].get('name') for i in round_nodes] != [f'Round_{i:02}' for i in range(1, GLOCK_ROUNDS + 1)]:
        raise ValueError(f'Rounds должен содержать {GLOCK_ROUNDS} отдельных патронов Round_01..Round_{GLOCK_ROUNDS}')
    low_rounds = [scene.nodes[i].get('name') for i in scene.nodes[names['Rounds_LOD1']].get('children', [])]
    if not low_rounds or low_rounds != [f'Round_{i:02}_LOD1' for i in range(1, len(low_rounds) + 1)]:
        raise ValueError('Rounds_LOD1 должен начинаться с Round_01_LOD1 и идти по порядку')
    # WeaponRig показывает первые N патронов: Round_01 — верхний, последним остаётся в магазине.
    heights = [scene.world(names[f'Round_{i:02}'])[1][3] for i in range(1, GLOCK_ROUNDS + 1)]
    if any(a <= b for a, b in zip(heights, heights[1:])):
        raise ValueError('Патроны должны идти сверху вниз: Round_01 — верхний')
    position = {name: scene.relative(name, 'Glock') for name in MARKERS + GLOCK_PARTS}
    if position['Muzzle'][2] <= .1:
        raise ValueError('Дульная метка должна находиться на срезе ствола, а не в корне')
    if any(abs(a - b) > .0005 for a, b in zip(position['Muzzle'], position['MuzzleSuppressed'])):
        raise ValueError('Без своего глушителя MuzzleSuppressed совпадает с Muzzle')
    if position['SightRear'][2] >= position['SightFront'][2]:
        raise ValueError('Целик должен быть позади мушки')
    if min(position['SightFront'][1], position['SightRear'][1]) <= position['Muzzle'][1]:
        raise ValueError('Линия прицеливания должна быть выше оси канала ствола')
    if position['Magazine'][1] >= 0:
        raise ValueError('Магазин должен стоять в рукояти ниже точки хвата')
    for part in GLOCK_PARTS:
        low = scene.relative(part + '_LOD1', 'Glock_LOD1')
        if any(abs(a - b) > .0005 for a, b in zip(low, position[part])):
            raise ValueError(f'{part}_LOD1 должен стоять на той же оси, что и {part}: {low} ≠ {position[part]}')
    counts = {'first_person': scene.triangles('Glock'), 'third_person': scene.triangles('Glock_LOD1')}
    if counts['first_person'] > TRIS_LOD0_MAX or counts['third_person'] > TRIS_LOD1_MAX:
        raise ValueError('Превышен бюджет треугольников: ' + str(counts))
    return {'triangles': counts, 'embedded_images': len(doc.get('images', [])), 'nodes': len(scene.nodes),
            'bounds_mm': [round(v, 3) for v in scene.bounds_mm('Glock')],
            'positions_m': {name: [round(v, 5) for v in position[name]]
                            for name in ('Muzzle','SightFront','SightRear','Magazine','Trigger','SlideStop')}}


def png_size(payload: bytes) -> tuple[int, int]:
    return struct.unpack_from('>II', payload, 16)


def embedded_pngs(model: Path, doc: dict, expected: tuple = ('pm_base_color','pm_normal','pm_orm'),
                  size: int = 0) -> dict[str, bytes]:
    """Извлечённые Godot PNG обновляются теми же байтами, что встроены в новый GLB."""
    binary = glb_binary(model)
    images: dict[str, bytes] = {}
    for image in doc.get('images', []):
        name = image.get('name', '')
        if name not in expected:
            raise ValueError(f'Неизвестная PBR-карта: {name}')
        view = doc['bufferViews'][image['bufferView']]
        if view.get('buffer', 0) != 0:
            raise ValueError('Карта не входит в главный BIN блок')
        start = view.get('byteOffset', 0);payload = binary[start:start+view['byteLength']]
        if not payload.startswith(b'\x89PNG\r\n\x1a\n'):
            raise ValueError('Ожидается встроенная PNG-карта')
        if size and png_size(payload) != (size, size):
            raise ValueError(f'Карта {name} {png_size(payload)}, ожидается {size}×{size}')
        images[name] = payload
    if set(images) != set(expected):
        raise ValueError(f'Нужны все PBR-карты {sorted(expected)}, есть {sorted(images)}')
    return images


def check_pm(src: Path, model: Path, doc: dict, images: dict[str, bytes]) -> dict:
    facts = inspect_pm(doc)
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
    return facts


def check_glock(src: Path, model: Path, doc: dict, images: dict[str, bytes]) -> dict:
    facts = inspect_glock(doc, model)
    manifest = json.loads((src / 'export_manifest.json').read_text(encoding='utf-8'))
    if manifest.get('id') != 'glock17_gen5' or manifest.get('glb') != model.name:
        raise SystemExit('export_manifest.json описывает другой экспорт')
    if manifest.get('root', 'Glock') != 'Glock' or manifest.get('lod_root', 'Glock_LOD1') != 'Glock_LOD1':
        raise SystemExit('Корни в manifest не совпадают с контрактом Glock / Glock_LOD1')
    # Покраску владельца после экспорта не меняли: иначе glb устарел относительно .blend.
    # Копия в _asset_src упакована (текстуры внутри .blend) — её хеш другой по построению,
    # поэтому сверяется только оригинал из папки владельца, когда он есть на этой машине.
    digest = str(manifest.get('source_sha256', ''))
    original = Path(str(manifest.get('source_blend', '')))
    copy = src / str(manifest.get('source_copy', ''))
    if str(original) not in ('', '.') and original.is_file():
        actual = hashlib.sha256(original.read_bytes()).hexdigest()
        if actual != digest:
            raise SystemExit(f'{original} изменился после экспорта ({actual} ≠ {digest}): переэкспортируйте glb')
        facts['source_verified'] = str(original)
    elif manifest.get('source_copy') and copy.is_file():
        print(f'предупреждение: оригинала {original} нет на этой машине, хеш не сверен; копия — {copy.name}')
        facts['source_verified'] = ''
    else:
        raise SystemExit('Нет ни исходника из manifest, ни его копии в _asset_src')
    measured = facts['bounds_mm'];declared = [float(v) for v in manifest['bounds_mm']]
    if any(abs(a-b) > BOUNDS_TOLERANCE_MM for a,b in zip(measured, declared)):
        raise SystemExit(f'Габариты glb {measured} расходятся с manifest {declared} больше чем на {BOUNDS_TOLERANCE_MM} мм')
    if any(not lo <= v <= hi for v, lo, hi in zip(measured, GLOCK_BOUNDS_MIN_MM, GLOCK_BOUNDS_MAX_MM)):
        raise SystemExit(f'Габариты {measured} не похожи на Glock 17: окно {GLOCK_BOUNDS_MIN_MM}–{GLOCK_BOUNDS_MAX_MM}')
    counts = facts['triangles']
    if [counts['first_person'], counts['third_person']] != [int(manifest['tris_lod0']), int(manifest['tris_lod1'])]:
        raise SystemExit(f'Треугольники {counts} не совпадают с manifest {manifest["tris_lod0"]}/{manifest["tris_lod1"]}')
    # Запечённые PNG рядом необязательны; если лежат — во встроенных те же байты.
    for name, payload in images.items():
        baked = src / (name + '.png')
        if baked.is_file() and hashlib.sha256(payload).digest() != hashlib.sha256(baked.read_bytes()).digest():
            raise SystemExit(f'Встроенная {name} устарела относительно {baked.name}: перепакуйте изображение')
    return facts


def update_credits(start: str, end: str, body: str) -> None:
    """Меняется только своя секция между метками; остальной файл и его переводы строк — как были."""
    credits = ROOT / 'assets' / 'CREDITS.md'
    raw = credits.read_bytes().decode('utf-8') if credits.exists() else ''
    newline = '\r\n' if '\r\n' in raw else '\n'
    section = newline.join(f'{start}\n{body}\n{end}'.split('\n'))
    if start in raw:
        before, rest = raw.split(start, 1)
        _, after = rest.split(end, 1)
        updated = before + section + after
    else:
        updated = raw.rstrip() + newline + newline + section + newline
    with credits.open('w', encoding='utf-8', newline='') as f:
        f.write(updated)


PM_CREDITS = '''## Пистолет ПМ

- `assets/models/weapons/pm/pm.glb` — собственная модель, сделана для RING; владелец — автор проекта. Предоставленный владельцем `PM_Highpoly_v5.blend` сохранён отдельной неизменённой копией в `_asset_src/pm_highpoly_v5/`.
- Игровая копия, PBR-атласы цвета/ORM/normal и два уровня детализации подготовлены `tools/export_pm_game.py`; импорт — `tools/import_weapon_model.py`. Фото служили референсами формы; их пиксели в игровых текстурах не использованы. Текстуры запечены из собственных процедурных материалов и highpoly-геометрии.'''

GLOCK_CREDITS = '''## Пистолет Glock 17 Gen5

- `assets/models/weapons/glock17/glock17.glb` — собственная модель владельца проекта, сделана для RING; лицензия — собственная работа. Glock 17 Gen5: рамка, затвор, ствол, спуск, затворная задержка, защёлка, магазин на 17 патронов; покраска владельца (PBR металл/полимер 2048², встроена в glb); два уровня детализации.
- Источник — `_asset_src/glock17_gen5/` (glb, неизменённая копия .blend, `license.txt`, `export_manifest.json`); проверка и импорт — `tools/import_weapon_model.py glock17_gen5`.
- Маркировка GLOCK — товарный знак Glock Ges.m.b.H.; оставлена по решению владельца, до выпуска игры решить отдельно (см. `license.txt`).'''

# Что проверять и куда класть у каждой модели. ПМ — те же проверки, что при первом импорте.
SPECS: dict[str, dict] = {
    'pm_highpoly_v5': {
        'glb': 'pm.glb', 'dest': ('pm', 'pm.glb'),
        'images': ('pm_base_color','pm_normal','pm_orm'), 'image_size': 0,
        'check': check_pm, 'credits': ('<!-- PM_MODEL_START -->', '<!-- PM_MODEL_END -->', PM_CREDITS),
    },
    'glock17_gen5': {
        'glb': 'glock17.glb', 'dest': ('glock17', 'glock17.glb'),
        'images': GLOCK_IMAGES, 'image_size': 2048,
        'check': check_glock, 'credits': ('<!-- GLOCK17_MODEL_START -->', '<!-- GLOCK17_MODEL_END -->', GLOCK_CREDITS),
    },
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source_id', choices=sorted(SPECS))
    parser.add_argument('--check', action='store_true', help='только проверить исходник, ничего не записывать')
    args = parser.parse_args()
    spec = SPECS[args.source_id]
    src = ROOT / '_asset_src' / args.source_id
    license_path = src / 'license.txt'
    license_text = license_path.read_text(encoding='utf-8')
    if 'собственная модель' not in license_text.lower() or 'владелец' not in license_text.lower():
        raise SystemExit('Нет явного разрешения владельца для собственной модели')
    model = src / spec['glb']
    doc = read_glb(model)
    images = embedded_pngs(model, doc, spec['images'], spec['image_size'])
    facts = spec['check'](src, model, doc, images)
    facts['sha256'] = hashlib.sha256(model.read_bytes()).hexdigest()
    folder, filename = spec['dest']
    if args.check:
        print('проверено, ничего не записано: ' + args.source_id)
        print(json.dumps(facts, ensure_ascii=False))
        return
    dst = ROOT / 'assets' / 'models' / 'weapons' / folder
    dst.mkdir(parents=True, exist_ok=True)
    target = dst / filename
    temp = dst / (filename + '.tmp')
    shutil.copy2(model, temp)
    temp.replace(target)
    # Godot может сохранить уже извлечённый файл при повторном импорте GLB.
    # Публикуем карты через этот же tools importer под именем извлечения Godot: <glb>_<карта>.png.
    for name, payload in images.items():
        image_path = dst / (target.stem + '_' + name + '.png')
        image_temp = image_path.with_suffix('.png.tmp');image_temp.write_bytes(payload);image_temp.replace(image_path)
    update_credits(*spec['credits'])
    print(f'готово: res://assets/models/weapons/{folder}/{filename}')
    print(json.dumps(facts, ensure_ascii=False))


if __name__ == '__main__':
    main()
