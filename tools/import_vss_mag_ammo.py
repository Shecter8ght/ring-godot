"""Проверенный перенос собственных игровых магазинов/патрона из сырья в assets."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import shutil
import struct

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / '_asset_src/vss_mag_ammo'
DESTINATION = ROOT / 'assets/models/weapons/vss_mag_ammo'
IDENTIFIERS = ('Magazine_939_10_Empty', 'Magazine_939_10_Loaded', 'Cartridge_939_SP5')
CREDIT = '''<!-- VSS_MAG_AMMO_START -->
## Отдельные магазин и патрон ВСС

- `assets/models/weapons/vss_mag_ammo/Magazine_939_10_Empty.glb` и `Magazine_939_10_Loaded.glb` — собственный короткий магазин ВСС на 10 мест: пустое состояние с подавателем и снаряжённое с двумя видимыми верхними патронами. Наружные рёбра/пятка взяты из собственной ВСС по фотографиям владельца; открытый верх доработан для самостоятельного ассета. Скрытая механика и остальные патроны не моделировались.
- `assets/models/weapons/vss_mag_ammo/Cartridge_939_SP5.glb` — собственный многоразовый художественный prop 9×39 СП-5: лакированная гильза, медная оболочка пули, капсюль и красный лак. Внешний вид: [предметные фото Mechanik / Munición](https://municion.org/ficha-09-039-bgc-010-0004/). Размеры дизайна и вторичные детали — визуальное приближение, не обмерная копия.
- Модели и PBR-карты созданы для владельца RING. Пиксели референсных фотографий в текстуры не переносились. Каждая игровая модель содержит один статический меш, встроенные basecolor/ORM/normal 2048² и три метки. Происхождение и редактируемые `.blend` — `_asset_src/vss_mag_ammo/`; сборка и проверенный перенос — `tools/build_vss_mag_ammo.py`, `tools/export_vss_mag_ammo.py`, `tools/import_vss_mag_ammo.py`.
<!-- VSS_MAG_AMMO_END -->'''


def read_glb(path: Path) -> dict:
    data = path.read_bytes()
    magic, version, length = struct.unpack_from('<4sII', data)
    if magic != b'glTF' or version != 2 or length != len(data):
        raise ValueError('Повреждённый GLB')
    count, kind = struct.unpack_from('<II', data, 12)
    if kind != 0x4E4F534A:
        raise ValueError('Отсутствует JSON GLB')
    return json.loads(data[20:20+count])


def main() -> None:
    if not (RAW / 'license.txt').is_file():
        raise ValueError('Нет происхождения модели')
    results = []
    for identifier in IDENTIFIERS:
        source = RAW / 'export' / identifier / (identifier + '.glb')
        report = json.loads((source.parent / 'export-report.json').read_text(encoding='utf-8'))
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        if report['status'] != 'PASS' or report['glb_sha256'] != digest or not report['source_unchanged']:
            raise ValueError('Не подтверждён экспорт ' + identifier)
        doc = read_glb(source)
        markers = report['markers']
        names = {n.get('name') for n in doc['nodes']}
        if not {identifier, 'Body', *markers} <= names or doc.get('animations'):
            raise ValueError('Неверная иерархия статического ассета ' + identifier)
        if len(doc['meshes']) != 1 or len(doc['materials']) != 1:
            raise ValueError('Ожидается одна игровая поверхность')
        if len(doc['images']) != 3 or any('bufferView' not in i for i in doc['images']):
            raise ValueError('PBR-карты должны быть встроены')
        triangles = sum(doc['accessors'][p['indices']]['count'] // 3
            for m in doc['meshes'] for p in m['primitives'])
        if triangles != report['triangles'] or triangles > 9000:
            raise ValueError('Неверный бюджет ' + identifier)
        results.append({'id': identifier, 'sha256': digest, 'triangles': triangles,
            'game_item_id': 'ammo_939_sp5' if identifier.startswith('Cartridge') else 'mag_939_10',
            'rounds_loaded': None if identifier.startswith('Cartridge') else (10 if identifier.endswith('Loaded') else 0),
            'visible_round_props': 2 if identifier.endswith('Loaded') else 0,
            'dimensions_source_mm': report['source_bounds']['dimensions_mm'],
            'axes': '+Z forward, +Y up, -X right', 'surfaces': 1,
            'root_origin': 'Case base center' if identifier.startswith('Cartridge') else 'Original VSS magazine socket',
            'on_vss_source_mm': None if identifier.startswith('Cartridge') else [455, 0, -37],
            'markers': markers, 'textures': '3 embedded 2048 PNG', 'source': str(source)})
    DESTINATION.mkdir(parents=True, exist_ok=True)
    for item in results:
        shutil.copy2(item.pop('source'), DESTINATION / (item['id'] + '.glb'))
    (DESTINATION / 'manifest.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
    path = ROOT / 'assets/CREDITS.md'
    credits = path.read_text(encoding='utf-8')
    start, end = '<!-- VSS_MAG_AMMO_START -->', '<!-- VSS_MAG_AMMO_END -->'
    if start in credits:
        before, rest = credits.split(start, 1)
        _, after = rest.split(end, 1)
        credits = before.rstrip() + '\n\n' + CREDIT + after
    else:
        credits = credits.rstrip() + '\n\n' + CREDIT + '\n'
    path.write_text(credits, encoding='utf-8')
    print(json.dumps({'status': 'PASS', 'destination': str(DESTINATION), 'assets': results}, ensure_ascii=False))


if __name__ == '__main__':
    main()
