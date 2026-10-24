"""Новая текстурная версия всей библиотеки; исходники не перезаписываются."""
from pathlib import Path
import argparse
import json
import shutil
from PIL import Image

from plan import ROOT, DELIVERY, LIBRARY, REVISIONS, OWNER_REQUEST, prepare, sha

PREFERRED={'U11_02':'R01','U11_03':'R02','U16_01':'R03','U14_01':'R04','U05_02':'R05'}


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')


def preserve_building(rows):
    a=next(a for a in rows if a['id']=='R06')
    source=Path(a['source_pbr_root'])
    target=ROOT/'assets'/a['folder']
    shutil.copytree(source,target,dirs_exist_ok=True)
    assert sha(target/'model/R06_building_pbr_v01.blend')=='509bbd5876a8fa69fa21d4ac0a433081815854c1bff796a2da226814d19ace19'
    a['existing_native_report']=read(target/'checks/native_validation.json')
    a['existing_geometry_report']=read(target/'checks/accepted_geometry_audit.json')


def make_state(a,report,inventory):
    folder=ROOT/'assets'/a['folder']
    if a['id']=='R06':
        geometry='Форма явно принята владельцем: «Форма подходит — переходи к текстурам».'
        uv='MetricUV — метры, WeatherUV — маски фасадов, PartUV — локальные детали.'
        prior='Ранее выполненная отделка здания сохранена побайтово; исходный отчёт — checks/native_validation.json. '
        sources='sources.json и textures/'
    else:
        geometry='Сохранённая авторская форма; владелец прямо поручил текстурировать все сделанные модели. Это не отдельное утверждение формы каждого из 95 предметов.'
        uv='MetricUV — метры, PartUV — локальная плоскость детали, GrainUV — направленное волокно/плетение.'
        prior=''
        sources='../../sources.json и ../../textures/'
    dimensions=inventory.get(a['id'],{}).get('dimensions_m')
    state=f'''# {a['id']} — {a['name']}, PBR v01

Подготовлено к просмотру владельцем. Blender 5.2.2 LTS, нативный UCUPaint 2.4.9.
{geometry}
Поручение: «{OWNER_REQUEST}»

Источник: {a['source_blend']}
SHA-256 исходника: `{a['source_sha256']}`.
Открыть: [текстурный .blend](model/{a['folder']}_pbr_v01.blend).
{prior}Метры, Z вверх, лицевая сторона −Y; размеры исходника: {dimensions or 'см. исходный asset-state.md'} м.
Основание, окраска, износ и загрязнения разделены на редактируемые слои.
Художественное состояние одно: {a['finish_target']}.

{uv}
Развёртки перекрываются для тайлинга; это авторинг материалов, не уникальный игровой атлас.
Геометрия, локальные матрицы и иерархия сверены с источником. Изображения встроены в .blend,
их внешние относительные копии сверяются по SHA-256; mapping — checks/image_manifest.json.
{report['native_materials']} нативных материалов, {report['native_layers']} слоёв.

Для изменения отделки откройте соответствующий материал в UCUPaint:
основание/заводская отделка — первые слои, сколы и окисление — 20–35,
пыль/контакт/низ — 60–80. Имена описывают назначение. Пыль и ржавчина — диэлектрики,
покрытие не становится металлом; стекло использует физическое преломление.
Photo BaseColor — sRGB, Normal/Roughness и маски — Non-Color.

CC0-фототекстуры Poly Haven и их лицензии — {sources}.
Маски владельца подписаны отдельно; права CC0 для них не заявляются.
Надписи и рисунки экранов/плакатов вымышленные, созданы для проекта.
Референсы в ../../references/ служат для формы и отделки; они не объявлены игровыми текстурами.

Проверки после повторного открытия — checks/validation.json и checks/delivery_validation.json.
Просмотры спереди, сзади, крупно — previews/. Текстуры ещё не утверждены владельцем.
Игровая оптимизация, bake, LOD, коллизии и импорт в Godot не выполнялись.
'''
    (folder/'asset-state.md').write_text(state,encoding='utf-8')


def enrich_image_manifest(a):
    """Tie every packed image to its preserved source and licence record."""
    folder=ROOT/'assets'/a['folder']
    file=folder/'checks/image_manifest.json'
    images=read(file)
    if a['id']=='R06':
        return images  # Immutable earlier mapping already includes source hashes and licence manifest.
    sources={s['id']:s for s in read(ROOT/'sources.json')}
    for im in images:
        try:
            relative=Path(im['source']).relative_to(ROOT/'textures')
        except ValueError:
            assert a['id'].startswith('R') and 'references' in im['source'],im['source']
            im.update(source_id='geometry_reference',source_url=a['source_reference'],
                license='Visual reference only; not a licensed game texture',
                processing='Original packed reference inherited from geometry source',purpose='Reference EMPTY image; not a model material')
            continue
        name=relative.parts[0]
        key='sky' if name.endswith('.hdr') else name.removesuffix('.png')
        record=sources[key]
        im.update(source_id=key,source_url=record.get('url',record.get('source')),
            license=record['license'],processing=record['operation'])
        leaf=relative.name.lower()
        im['purpose']='Normal OpenGL' if 'normal' in leaf else 'Roughness' if 'roughness' in leaf else (
            'HDR environment' if leaf.endswith('.hdr') else 'Mask/data' if im['colorspace']=='Non-Color' else 'BaseColor / printed graphic')
    write(file,images)
    return images


def prepare_package():
    rows=prepare()
    preserve_building(rows)
    inventory={a['id']:a for a in read(ROOT/'source_inventory.json')}
    records=[]
    for a in rows:
        folder=ROOT/'assets'/a['folder']
        model=ROOT/a['output_model']
        assert model.is_file(),a['id']
        if a['id']=='R06':
            n=a['existing_native_report']
            assert not n['problems'] and a['existing_geometry_report']['pass']
            report=dict(id='R06',passed=True,native_materials=n['native_materials'],native_layers=n['native_layers'],
                native_masks=n['native_masks'],packed_images=n['image_datablocks_checked'],blend_sha256=sha(model),
                existing_pbr_preserved=True,original_validation='checks/native_validation.json')
            views=('front34_day','rear34_day','damage_day')
            write(folder/'checks/validation.json',report)
        else:
            report=read(folder/'checks/validation.json')
            assert report['passed'] and report['blend_sha256']==sha(model),a['id']
            views=('front34','rear34','detail')
        for view in views:
            with Image.open(folder/'previews'/(view+'.png')) as image:
                image.verify()
        enrich_image_manifest(a)
        make_state(a,report,inventory)
        rec=dict(a)
        rec.pop('existing_native_report',None)
        rec.pop('existing_geometry_report',None)
        rec.update(model=a['output_model'],blend_sha256=sha(model),
            native_materials=report['native_materials'],native_layers=report['native_layers'],
            packed_images=report['packed_images'],geometry_preserved=True,status='Подготовлено к просмотру',
            image_manifest=f'assets/{a["folder"]}/checks/image_manifest.json',
            state=f'assets/{a["folder"]}/asset-state.md',
            previews=[f'assets/{a["folder"]}/previews/{v}.png' for v in views])
        rec.update(stage='native_pbr_candidate',production_uv=True,production_textures=True,
            authoring_uv_not_game_atlas=True,pbr_model=a['output_model'],pbr_manifest='manifest.json',
            pbr_sha256=sha(model),visual_review='Individual PBR PNG views reviewed; checks/visual_review.json')
        if a['id'] in PREFERRED:
            rec['preferred_revision']=PREFERRED[a['id']]
        records.append(rec)
    references=[]
    for source in sorted({Path(a['source_reference']) for a in rows}):
        assert source.is_file(),str(source)
        digest=sha(source)
        file=ROOT/'references'/('screens' if source.suffix.lower()=='.png' else 'photos')/(digest[:12]+source.suffix.lower())
        file.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,file)
        references.append(dict(source=str(source),file=file.relative_to(ROOT).as_posix(),sha256=digest,
            purpose='Visual reference only; not a licensed texture or downloaded 3D model'))
    # Preserve all three owner photos, not only the wide elevation used by the matrix.
    for source in sorted((REVISIONS/'references/building_user').glob('ref_*')):
        file=ROOT/'references/building_user'/source.name
        file.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,file)
        references.append(dict(source=str(source),file=file.relative_to(ROOT).as_posix(),sha256=sha(source),purpose='Owner photo reference'))
    write(ROOT/'references/manifest.json',references)
    reference_map={r['source']:r['file'] for r in references}
    for a in records:
        a['reference']=reference_map[a['source_reference']]
        if 'source' in a:
            a['source_reference_in_geometry_library']=a['source']
            a['source']=a['reference']
    manifest=dict(date='2026-10-24',version='textured_v01',owner_request=OWNER_REQUEST,
        blender='5.2.2 LTS',ucupaint='2.4.9',models=len(records),newly_textured=100,preserved_textured=1,
        texture_approved=False,game_export=False,assets=records)
    write(ROOT/'manifest.json',manifest)
    text='# Городская библиотека — 101 модель с текстурами\n\n'
    text+='95 исходных предметов, 5 переделанных предметов и здание по фотографиям. '
    text+='Нативный UCUPaint 2.4.9 / Blender 5.2.2 LTS; текстуры подготовлены к просмотру владельцем. '
    text+='Все карты встроены, внешние копии и лицензии сохранены рядом.\n\n'
    text+='Для забора, бункера, банкомата, машины и ларька предпочтительны версии R01–R05. '
    text+='Исходная геометрия и прежняя отделка здания сохранены отдельно. Игровой экспорт — следующий самостоятельный этап.\n\n'
    text+='[Источники текстур](sources.json) · [Проверка выдачи](checks/delivery_summary.json) · [Технический манифест](manifest.json)\n\n'
    text+='| ID | Модель | Файл | Снимок | Материалы |\n|---|---|---|---|---|\n'
    for a in records:
        note='; предпочтительна '+a['preferred_revision'] if 'preferred_revision' in a else ''
        text+=f'| {a["id"]} | {a["name"]}{note} | [Blender]({a["model"]}) | [Спереди]({a["previews"][0]}) | [Слои и проверки]({a["state"]}) |\n'
    (ROOT/'README.md').write_text(text,encoding='utf-8')
    return manifest


def deliver(ids=None):
    manifest=prepare_package()
    if DELIVERY.exists():
        existing=DELIVERY/'manifest.json'
        assert existing.is_file() and read(existing).get('owner_request')==OWNER_REQUEST,'Destination belongs to a different version'
    DELIVERY.mkdir(parents=True,exist_ok=True)
    for name in ('textures','dependencies','references') if not ids else ('dependencies',):
        shutil.copytree(ROOT/name,DELIVERY/name,dirs_exist_ok=True)
    for a in manifest['assets']:
        if not ids or a['id'] in ids:
            shutil.copytree(ROOT/'assets'/a['folder'],DELIVERY/'assets'/a['folder'],dirs_exist_ok=True)
    for name in ('manifest.json','sources.json','README.md','plan.json','source_inventory.json'):
        shutil.copy2(ROOT/name,DELIVERY/name)
    target=DELIVERY/'source'
    target.mkdir(exist_ok=True)
    for script in Path(__file__).parent.glob('*.py'):
        shutil.copy2(script,target/script.name)
    for a in manifest['assets']:
        assert sha(DELIVERY/a['model'])==a['blend_sha256']
    print('URBAN_PBR_COPIED',len(manifest['assets']),str(DELIVERY),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--deliver',action='store_true')
    parser.add_argument('--ids',default='')
    args=parser.parse_args()
    if args.deliver:
        deliver(set(args.ids.split(',')) if args.ids else None)
    else:
        print('URBAN_PACKAGE_PREPARED',prepare_package()['models'])
