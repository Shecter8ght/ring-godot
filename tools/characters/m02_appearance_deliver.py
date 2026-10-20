"""Pack the reviewed appearance candidate into a new, portable Models Blender folder."""
import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import shutil
import sys

import addon_utils
import bpy

MODEL_ROOT=Path('E:/Models Blender/RING_NPC_2026-10-20_v01')
ROOT=Path(__file__).resolve().parents[2]


def deliver(source,out):
    source=source.resolve()
    out=out.resolve()
    assert out.parent==MODEL_ROOT.resolve(),out
    assert source.is_file()
    assert not out.exists(),f'Destination already exists: {out}'
    report=json.loads((source.parent/'appearance_report.json').read_text(encoding='utf-8'))
    assert hashlib.sha256(Path(report['source']).read_bytes()).hexdigest()==report['source_sha256']
    bpy.ops.wm.open_mainfile(filepath=str(source))
    bpy.context.preferences.use_preferences_save=False
    module='bl_ext.blender_org.ucupaint'
    if module not in bpy.context.preferences.addons:
        bpy.context.preferences.addons.new().module=module
    addon_utils.enable(module,default_set=False,persistent=False)
    U=importlib.import_module(module)
    assert U.common.get_current_version_str()=='2.4.9'
    out.mkdir()
    textures=out/'textures'
    textures.mkdir()
    image_manifest=[]
    for image in bpy.data.images:
        if image.source!='FILE' or not image.filepath:
            continue
        assert image.packed_file and image.packed_file.size>0,image.name
        target=textures/Path(image.name).name
        payload=bytes(image.packed_file.data)
        if target.exists():
            assert target.read_bytes()==payload,target
        else:
            target.write_bytes(payload)
        image.filepath='//textures/'+target.name
        image_manifest.append({'name':image.name,'path':'textures/'+target.name,
            'size':list(image.size),'colorspace':image.colorspace_settings.name,
            'sha256':hashlib.sha256(payload).hexdigest()})
    bpy.context.scene.render.filepath='//head_three_quarter.png'
    target=out/source.name
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(target),check_existing=False,relative_remap=False)
    report['file']=str(target)
    report['images']=image_manifest
    (out/'appearance_report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    for view in ['head_three_quarter','head_front','head_profile','body_front','body_back']:
        source_image=source.parent/(view+'.png')
        assert source_image.is_file(),source_image
        shutil.copy2(source_image,out/source_image.name)
    data=Path(os.environ['APPDATA'])/'Blender Foundation/Blender/5.2/extensions/.user/blender_org/mpfb/data'
    licenses=out/'licenses'
    licenses.mkdir()
    for relative in ['skins/young_caucasian_male2/young_caucasian_male2.mhmat',
                     'skins/middleage_caucasian_male/middleage_caucasian_male.mhmat']:
        shutil.copy2(data/relative,licenses/Path(relative).name)
    (out/'00_НАЧНИ_ЗДЕСЬ.txt').write_text(
        'М02 — кожа, волосы и лицо, кандидат v05.\n\n'
        'Открыть M02_Appearance_v05.blend в Blender. Для полного вида кожи и волос: Z → Rendered (Cycles), либо F12.\n'
        'В сцене сохранена камера крупного плана. Общий вид и остальные ракурсы — PNG рядом.\n'
        'Кожа редактируется в настоящем UCUPaint 2.4.9; волосы, брови и щетина — отдельные объекты Curves.\n'
        'Для отката небольшой правки лица уменьшить shape key «M02 — adult face refinement» до 0.\n'
        'Все изображения упакованы и также лежат рядом в textures/.\n'
        'Геометрия v06 сохранена в соседней папке M02_Geometry_v06.\n',encoding='utf-8')
    (out/'asset-state.md').write_text('''# М02 — внешность, кандидат v05

Дата: 2026-10-20. Стадия: кожа, лицо и волосы на просмотр владельцу.

Владелец принял v06 как рабочую основу и поручил довести лицо, волосы и кожу.
Текущий образ ещё не проходил художественного принятия. Основной файл — `M02_Appearance_v05.blend`.

## Что изменено

- Сохранена базовая сетка v06: рост 1,78 м, непрерывные тело и голова, 13 380 вершин / 13 378 quad-граней, те же UV.
- Отдельный обратимый shape key лица: небольшие правки щёк, уголков губ, верхних век, подбородка и носа; максимум около 1,38 мм.
- Настоящий стек UCUPaint 2.4.9, 11 слоёв: исходные карты кожи, возрастной цвет лица, баланс оттенка ног,
  тёплые зоны, нижние веки, тон щетины, блеск лба/носа, губы, поры, мелкая вариация шероховатости и корни волос.
- Карие глаза получили более гладкую влажную поверхность; посадка ресниц уточнена.
- Короткие каштановые волосы (64 000 кривых), щетина (11 500), брови (2 200) — отдельные нативные объекты Curves.
  Они следуют за костью головы; исходные карточки волос и бровей v06 сохранены скрытыми.
- Примерочные серые шорты сохранены. Студия и камеры находятся в файле.

## Просмотр и правки

Blender 5.2.2 LTS. Полный вид материалов — Cycles, `Z → Rendered` или `F12`.
Камера по умолчанию — три четверти. В Material Preview вид волос может отличаться от Cycles.
Для редактирования стека нужен установленный UCUPaint; сам файл и нативные узлы материалов открываются без него.
Небольшую правку формы можно отключить shape key. Цветовые области кожи — редактируемые цветовые атрибуты сетки.
Волосы можно редактировать как кривые; текущая привязка — к голове, полноценный риг мимики ещё не разрабатывался.

Все 10 изображений упакованы в .blend и продублированы относительными файлами `textures/`.
Контрольные виды — пять PNG рядом. Отчёт сборки — `appearance_report.json`, повторного открытия — `appearance_verification.json`.

## Следующие этапы

Художественная оценка текущего образа; первый комплект одежды и проверка его посадки.
Игровые волосы, оптимизация, запекание и импорт Godot — отдельный производственный этап.
Текущие детальные кривые предназначены для редактируемого исходника Blender.

Сборщик: `tools/characters/m02_appearance.py`; проверка: `m02_appearance_verify.py`;
выдача: `m02_appearance_deliver.py`. Происхождение — `sources_licenses.md`.
''',encoding='utf-8')
    (out/'sources_licenses.md').write_text('''# Источники М02, внешность v05

- Тело, UV, предварительный новый скелет и части головы унаследованы от M02_Geometry_v06.
  Основа MakeHuman/MPFB core hm08, core-ассеты CC0. Исходник v06 не перезаписывался.
- Цвет кожи: MakeHuman core `young_caucasian_male2/young_lightskinned_male_diffuse2.png`
  и `middleage_caucasian_male/middleage_lightskinned_male_diffuse.png`, 2048 × 2048.
  В `licenses/` сохранены соответствующие неизменённые .mhmat с явным объявлением выпуска в CC0 в сентябре 2020.
  Указанные правообладатели: Data Collection AB, Joel Palmius, Jonas Hauquier.
- Остальные упакованные изображения глаз, зубов, языка и исходных карточек — тот же локальный CC0 core-набор MPFB;
  происхождение перечислено также в соседней выдаче геометрии v06.
- Референсы М02 созданы imagegen для RING; не использованы как карты кожи.
- Новые цветовые маски, мелкий процедурный рельеф кожи, поправка формы и генерация/укладка кривых волос —
  собственная работа для RING, `tools/characters/m02_appearance.py`.
- Программа MPFB и UCUPaint имеют собственные лицензии кода; их код не включён в выдаваемые графические исходники.

Официальные источники:

- https://static.makehumancommunity.org/about/license.html
- https://github.com/makehumancommunity/mpfb2/blob/master/LICENSE.md

Пути, размеры и SHA-256 изображений записаны в `appearance_report.json`.
''',encoding='utf-8')
    manifest={str(path.relative_to(out)).replace('\\','/'):hashlib.sha256(path.read_bytes()).hexdigest()
        for path in out.rglob('*') if path.is_file()}
    (out/'sha256_manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding='utf-8')
    print('M02_APPEARANCE_DELIVERED '+json.dumps({'folder':str(out),'file':str(target),'files':len(manifest)},ensure_ascii=False),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('file',type=Path)
    parser.add_argument('--out',type=Path,default=MODEL_ROOT/'M02_Appearance_v05')
    argv=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    args=parser.parse_args(argv)
    deliver(args.file,args.out)
