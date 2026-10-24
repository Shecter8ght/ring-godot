"""Состав всей созданной городской библиотеки и отдельные текстурные версии."""
from pathlib import Path
import hashlib
import json

PROJECT = Path(__file__).resolve().parents[3]
LIBRARY = Path('E:/Models Blender/ENVIRONMENT/RING_Urban_95')
ROOT = PROJECT / '_asset_src/urban_pbr_all_v01'
DELIVERY = LIBRARY / 'textured_v01'
REVISIONS = LIBRARY / 'revisions/v02_real_references'
OWNER_REQUEST = 'Текстурируй не только это здание, но и все остальные модели, которые ты делал.'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def records():
    out = []
    original = json.loads((LIBRARY / 'manifest.json').read_text(encoding='utf-8'))
    for a in original:
        a = dict(a)
        a['folder'] = a['id'] + '_' + a['key']
        a['source_blend'] = str(LIBRARY / 'assets' / a['folder'] / 'model' / (a['folder'] + '_geometry_v01.blend'))
        a['source_reference'] = str(LIBRARY / a['source'])
        a['variant'] = 'original_95'
        a['existing_pbr'] = False
        out.append(a)
    revision = json.loads((REVISIONS / 'manifest.json').read_text(encoding='utf-8'))
    for source in revision['assets']:
        a = dict(source)
        a['folder'] = a['id'] + '_' + a['key']
        a['source_blend'] = str(REVISIONS / source['model'])
        a['variant'] = 'rebuilt_v02'
        a['existing_pbr'] = a['id'] == 'R06'
        a['finish_target'] = {
            'R01': 'cast grey concrete; exposed mineral aggregate; damp low edge; rusty lifting loops',
            'R02': 'weathered dark green steel skip; scratched loading rim; rust in floor and welds',
            'R03': 'graphite moulded fascia and enamel safe; polished keypad; cloudy screen; contact grime',
            'R04': 'dark blue automotive paint; dusty glazing; road grime low body; rubber; aluminium wheels',
            'R05': 'cream fastfood kiosk; burgundy fascia; stainless counter; burgundy-cream striped awning; timber trim',
            'R06': 'Owner-photo old plaster PBR already delivered; preserved without retexturing',
        }[a['id']]
        a['source_reference'] = str(REVISIONS / 'references' / {
            'R01': 'fence/ref_01.jpg', 'R02': 'dumpster/ref_02.jpeg', 'R03': 'atm/ref_01.jpg',
            'R04': 'car_official/ref_01.jpg', 'R05': 'kiosk/ref_08.jpg', 'R06': 'building_user/ref_03.jpg',
        }[a['id']])
        if a['existing_pbr']:
            a['source_pbr_root'] = str(REVISIONS / 'assets/R06_building/pbr_v01')
        out.append(a)
    for a in out:
        a['source_sha256'] = sha(a['source_blend'])
        a['output_model'] = 'assets/' + a['folder'] + '/model/' + a['folder'] + '_pbr_v01.blend'
        a['texture_authorization'] = OWNER_REQUEST
        a['texture_approved'] = False
    assert len(out) == 101 and len({a['id'] for a in out}) == 101
    return out


def prepare():
    ROOT.mkdir(parents=True, exist_ok=True)
    a = records()
    (ROOT / 'plan.json').write_text(json.dumps(a, ensure_ascii=False, indent=2), encoding='utf-8')
    return a


if __name__ == '__main__':
    a = prepare()
    print('URBAN_PBR_PLAN', len(a), 'total;', sum(not r['existing_pbr'] for r in a), 'to texture; R06 preserved')
