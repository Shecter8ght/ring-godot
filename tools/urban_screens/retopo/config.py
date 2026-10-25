"""Отдельная производная версия текущей текстурированной библиотеки."""
from pathlib import Path
import hashlib
import json

PROJECT=Path(__file__).resolve().parents[3]
SOURCE=Path('E:/Models Blender/ENVIRONMENT/RING_Urban_95/textured_v01')
WORK=PROJECT/'_asset_src/urban_retopology_v01'
DELIVERY=SOURCE.parent/'retopology_v01'
MODEL='MODEL | editable components'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path,value):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')


def rows():
    data=json.loads((SOURCE/'manifest.json').read_text(encoding='utf-8'))['assets']
    for a in data:
        a['source_pbr']=str(SOURCE/a['model'])
        a['retopo_model']=f'assets/{a["folder"]}/model/{a["folder"]}_retopology_v01.blend'
    return data
