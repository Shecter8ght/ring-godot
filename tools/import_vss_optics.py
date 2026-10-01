"""Проверенные отдельные GLB прицелов из сырья в assets; игровой код не меняется."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import shutil
import struct

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / '_asset_src' / 'vss_optics'
DESTINATION = ROOT / 'assets' / 'models' / 'attachments' / 'vss_optics'
IDENTIFIERS = ('PSO_VSS_4x24', 'Rail_4x32')
MARKERS = ('MountOrigin', 'OpticalAxis', 'Ocular', 'EyePoint', 'Objective')
CREDIT = '''<!-- VSS_OPTICS_START -->
## Отдельная оптика ВСС

- `assets/models/attachments/vss_optics/PSO_VSS_4x24.glb` — собственная наружная модель ПСО-1М2-1 для RING, с боковым кронштейном и удлинённым наглазником. Форма: фото владельца и [предметный референс](https://arteecool.com/catalog/izdelie-pso-1m2-1). Второстепенные размеры оценены; модель не является обмерной копией.
- `assets/models/attachments/vss_optics/Rail_4x32.glb` — собственный компактный прицел 4×32 на верхнюю планку, без копирования фирменного изделия.
- Обе модели и PBR-карты созданы для владельца проекта. Пиксели референсных фотографий в текстуры не переносились; цвет/ORM/normal запечены из собственных материалов. GLB содержат встроенные текстуры, отдельные меши корпуса и линз и метки крепления/оси/глаза. Исходники и происхождение — `_asset_src/vss_optics/`; сборка, экспорт и проверенный перенос — `tools/build_vss_optics.py`, `tools/export_vss_optic.py`, `tools/import_vss_optics.py`.
<!-- VSS_OPTICS_END -->'''


def read_glb(path: Path) -> dict:
    data = path.read_bytes()
    magic, version, length = struct.unpack_from('<4sII', data)
    if magic != b'glTF' or version != 2 or length != len(data):
        raise ValueError('Повреждённый GLB 2.0')
    count, kind = struct.unpack_from('<II', data, 12)
    if kind != 0x4E4F534A:
        raise ValueError('Нет JSON в GLB')
    return json.loads(data[20:20 + count])


def main() -> None:
    license_path = RAW / 'license.txt'
    if not license_path.is_file():
        raise ValueError('Не указано происхождение собственной модели')
    manifests = []
    for identifier in IDENTIFIERS:
        source = RAW / 'export' / identifier / (identifier + '.glb')
        report = json.loads((source.parent / 'export-report.json').read_text(encoding='utf-8'))
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        if report['status'] != 'PASS' or report['glb_sha256'] != digest or not report['source_unchanged']:
            raise ValueError('GLB не совпадает с проверенным экспортом ' + identifier)
        document = read_glb(source)
        nodes = document['nodes']
        names = {n.get('name') for n in nodes}
        if not {identifier, 'Body', 'Lenses', *MARKERS} <= names:
            raise ValueError('Не хватает владельца, мешей или меток ' + identifier)
        if document.get('animations') or len(document['meshes']) != 2:
            raise ValueError('В статический ассет попала лишняя сцена ' + identifier)
        if len(document.get('images', [])) != 3 or any('bufferView' not in i for i in document['images']):
            raise ValueError('Три PBR-карты должны быть встроены в GLB')
        count = sum(document['accessors'][p['indices']]['count'] // 3
            for mesh in document['meshes'] for p in mesh['primitives'])
        if count != report['triangles'] or count > 15000:
            raise ValueError('Не совпадает бюджет ' + identifier)
        if len(document.get('materials', [])) != 2:
            raise ValueError('Ожидаются два материала: атлас и стекло')
        if not any(m.get('alphaMode') == 'BLEND' for m in document['materials']):
            raise ValueError('Утрачена прозрачность линз')
        manifests.append({'id': identifier, 'source': str(source), 'sha256': digest,
            'triangles': count, 'dimensions_source_mm': report['source_bounds']['dimensions_mm'],
            'axes': '+Z forward, +Y up, -X right', 'root_origin': 'Mount contact',
            'markers': list(MARKERS), 'surfaces': 2, 'textures': '3 embedded 2048 PNG',
            'on_vss_source_mm': [361, 24.5, -3] if identifier.startswith('PSO') else [383, 0, 58.1]})
    DESTINATION.mkdir(parents=True, exist_ok=True)
    for item in manifests:
        shutil.copy2(item.pop('source'), DESTINATION / (item['id'] + '.glb'))
    (DESTINATION / 'manifest.json').write_text(json.dumps(manifests, indent=2), encoding='utf-8')
    credits_path = ROOT / 'assets' / 'CREDITS.md'
    credits = credits_path.read_text(encoding='utf-8')
    start, end = '<!-- VSS_OPTICS_START -->', '<!-- VSS_OPTICS_END -->'
    if start in credits:
        before, rest = credits.split(start, 1)
        _, after = rest.split(end, 1)
        credits = before.rstrip() + '\n\n' + CREDIT + after
    else:
        credits = credits.rstrip() + '\n\n' + CREDIT + '\n'
    credits_path.write_text(credits, encoding='utf-8')
    print(json.dumps({'status': 'PASS', 'destination': str(DESTINATION), 'assets': manifests}, ensure_ascii=False))


if __name__ == '__main__':
    main()
