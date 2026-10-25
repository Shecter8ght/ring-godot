"""Portable saved-file delivery, image hashes, reopen and full UV verification."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import sys

import bpy

sys.path.insert(0,str(Path(__file__).resolve().parent))
from config import WORK,SOURCE,DELIVERY,MODEL,rows,write,sha
from uv_check import audit


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def signature():
    return {o.name:dict(parent=o.parent.name if o.parent else None,matrix=[list(r) for r in o.matrix_local])
        for o in bpy.data.collections[MODEL].objects}


def one(a):
    src=WORK/a['retopo_model']; out=DELIVERY/a['retopo_model']
    folder=out.parent.parent; source_folder=src.parent.parent
    report=read(source_folder/'checks/retopology.json')
    bake=read(source_folder/'checks/bake.json')
    assert report['passed'] and bake['passed'] and bake['coverage']['passed']
    assert sha(src)==report['model_sha256']==bake['model_sha256']
    previews=read(source_folder/'checks/previews.json')
    assert previews['model_sha256']==bake['model_sha256']
    assert all(sha(source_folder/'previews'/name)==digest for name,digest in previews['images'].items())
    assert sha(a['source_pbr'])==report['source_sha256']
    folder.mkdir(parents=True,exist_ok=True)
    for name in ('checks','previews','textures'):
        shutil.copytree(source_folder/name,folder/name,dirs_exist_ok=True)
    for name in ('sources.json','CREDITS.md'):
        path=SOURCE/'assets'/a['folder']/name
        if path.exists():shutil.copyfile(path,folder/name)
    bpy.ops.wm.open_mainfile(filepath=str(src))
    before=signature(); records=[]
    tex=folder/'textures'
    for im in bpy.data.images:
        if im.type in ('RENDER_RESULT','COMPOSITING'):
            continue
        if not im.packed_file:
            im.pack()
        data=bytes(im.packed_file.data); digest=hashlib.sha256(data).hexdigest()
        name=Path(im.filepath.replace('\\','/')).name
        if not name or '.' not in name:
            name='dependency_'+digest[:16]+('.hdr' if im.is_float else '.png')
        path=tex/name
        if path.exists() and sha(path)!=digest:
            path=tex/(path.stem+'_'+digest[:12]+path.suffix)
        path.write_bytes(data)
        im.filepath='//../textures/'+path.name
        records.append(dict(name=im.name,file='textures/'+path.name,sha256=digest,
            size=list(im.size),colorspace=im.colorspace_settings.name))
    out.parent.mkdir(exist_ok=True)
    bpy.context.preferences.use_preferences_save=False
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(out),compress=True,relative_remap=False)
    bpy.ops.wm.open_mainfile(filepath=str(out))
    errors=[]
    if signature()!=before:
        errors.append('Saved hierarchy or local matrices differ')
    objects=[o for o in bpy.data.collections[MODEL].objects if o.type=='MESH']
    count=sum(len(t.vertices)-2 for o in objects for t in o.data.polygons)
    if count!=report['after']:
        errors.append('Triangle count differs')
    if any(len(o.modifiers) for o in objects):
        errors.append('Uncommitted modifiers')
    for r in records:
        im=bpy.data.images.get(r['name']); path=folder/r['file']
        if not im or not im.packed_file or hashlib.sha256(bytes(im.packed_file.data)).hexdigest()!=r['sha256']:
            errors.append('Packed image mismatch: '+r['name'])
        if sha(path)!=r['sha256'] or im.colorspace_settings.name!=r['colorspace']:
            errors.append('External image or colorspace mismatch: '+r['name'])
        if Path(bpy.path.abspath(im.filepath)).resolve()!=path.resolve():
            errors.append('Image path is not portable: '+r['name'])
    for mat in {m for o in objects for m in o.data.materials}:
        nodes=mat.node_tree.nodes
        imgs=[n for n in nodes if n.type=='TEX_IMAGE']
        normals=[n for n in nodes if n.type=='NORMAL_MAP']
        if len(imgs)!=4 or len(normals)!=1 or normals[0].uv_map!='BakeUV':
            errors.append('Baked PBR material differs: '+mat.name)
        for n in imgs:
            wanted='sRGB' if '_BaseColor' in n.image.name else 'Non-Color'
            if n.image.colorspace_settings.name!=wanted:
                errors.append('PBR image colorspace differs: '+n.image.name)
    uv=audit(objects)
    if not uv['passed']:
        errors.append('Final UV validation failed')
    if sha(a['source_pbr'])!=report['source_sha256']:
        errors.append('Source changed')
    validation=dict(id=a['id'],passed=not errors,errors=errors,triangles=count,mesh_parts=len(objects),
        model_sha256=sha(out),source_unchanged=True,saved_file_reopened=True,
        work_model_sha256=sha(src),
        hierarchy_and_pivots_preserved=True,uv=uv,images=len(records),game_import=False)
    write(folder/'checks/images_delivery.json',records)
    write(folder/'checks/delivery_validation.json',validation)
    for filename in ('retopology.json','bake.json'):
        path=folder/'checks'/filename
        result=read(path)
        result['work_model_sha256']=result['model_sha256']
        result['model_sha256']=validation['model_sha256']
        result['delivered_model']=str(out)
        write(path,result)
    state=f'''# {a['id']} — {a['name']}: ретопология v01

Поручение владельца: «нужно выполнить ретопологию»; вся текстурированная партия 101 модели.
Источник: `{a['source_pbr']}`.
SHA-256 неизменённого PBR-мастера: `{report['source_sha256']}`.
Форма R06 принята отдельно; остальные индивидуальные утверждения формы и текстур этим поручением не подменяются.

Открыть [ретопологию](model/{out.name}).
Сетка: {report['before']:,} → {count:,} треугольников; {len(objects)} отдельных деталей.
Силуэт, отверстия, иерархия, исходный масштаб в метрах и локальные матрицы сохранены.
Z вверх, лицевая сторона −Y. Методы и измеренные допуски каждой детали: checks/retopology.json.
Статичная игровая триангуляция: плоские участки очищены, регулярные участки разрежены,
криволинейные упрощены с ограничением отклонения; тонкие критичные контуры сохранены.
Это производная игровая сетка, не новая subdivision-модель с исключительно четырёхугольными петлями.

BakeUV — отдельный уникальный атлас {report['atlas_resolution']} × {report['atlas_resolution']}, проверен на пересечения и вырожденные треугольники.
Старые UV сохранены как справочные. BaseColor без света — sRGB; Metallic, Roughness, Normal — Non-Color.
Нормали OpenGL в касательном пространстве (+X +Y +Z), NormalMap использует BakeUV.
Сплошные цвета объёмных букв сохранены из точных исходных значений BSDF без выборки из атласа.
Запекание Cycles выбранного полного источника на облегчённый при разнесении пар деталей;
контроль покрытия — checks/bake_coverage.json, исходные каналы — checks/bake.json.
MaterialData.png (R металл / G шероховатость / B покрытие лучами) — диагностический результат, не ORM.
Встроенные карты и относительные внешние копии сверены по SHA-256 после повторного открытия.
Нативная послойная отделка UCUPaint остаётся в неизменённом PBR-мастере по пути выше.

Просмотр: previews/front34.png; фактическая сетка: previews/topology_front.png и topology_rear.png.
Оценка формы и художественное утверждение текстур остаются за владельцем.
Источники и лицензии фотографических материалов: ../../sources.json и исходный PBR-мастер.
Референсы владельца не объявлены CC0. Новые фотографии или купленные материалы не использованы.
LOD, коллизии, объединение draw calls, экспорт GLB и импорт/размещение в Godot не выполнялись.
'''
    (folder/'asset-state.md').write_text(state,encoding='utf-8')
    if errors:
        raise RuntimeError(a['id']+': '+str(errors))
    print('DELIVERY_OK',a['id'],count,flush=True)
    return dict(id=a['id'],folder=a['folder'],name=a['name'],model=a['retopo_model'],
        model_sha256=sha(out),source_pbr=a['source_pbr'],source_sha256=report['source_sha256'],
        before=report['before'],after=count,atlas_resolution=report['atlas_resolution'],mesh_parts=len(objects))


def catalog(results):
    before=sum(x['before'] for x in results); after=sum(x['after'] for x in results)
    data=dict(stage='Retopology and PBR transfer; no engine import',assets=results,
        assets_count=len(results),source_triangles=before,retopology_triangles=after,
        reduction_percent=100*(1-after/before),source_library=str(SOURCE))
    write(DELIVERY/'manifest.json',data)
    shutil.copyfile(SOURCE/'sources.json',DELIVERY/'sources.json')
    text=f'''# RING — ретопология городской библиотеки v01

{len(results)} моделей. {before:,} → {after:,} треугольников (−{100*(1-after/before):.1f}%).
Исходные модели и редактируемая отделка UCUPaint сохранены в `{SOURCE}` без изменений.

В каждой папке: отдельный `.blend`, PBR-карты, asset-state.md и отчёты проверок.
Все сохранённые файлы повторно открыты: иерархия, масштаб, число треугольников, уникальный BakeUV,
встроенные/внешние изображения и цветовые пространства проверены. Текстуры перенесены с полных источников.
Нормали OpenGL. BaseColor без света, sRGB; Metallic/Roughness/Normal — Non-Color.
Части оставлены раздельными. Это ретопология в Blender; LOD, коллизии и импорт в Godot — отдельный этап.
Изменение отделки: в исходном PBR-мастере, затем повторное запекание.
Старая машина U14_01 и прочие первые версии оставлены для полноты; рекомендуемые переработки:
R01 забор, R02 контейнер, R03 банкомат, R04 автомобиль, R05 киоск. R06 — здание по трём фотографиям владельца.

| ID | Модель | Треугольники: было → стало | Атлас | Файл / просмотр / сетка |
|---|---|---:|---:|---|
'''
    for r in results:
        root='assets/'+r['folder']
        text+=f"| {r['id']} | {r['name']} | {r['before']:,} → {r['after']:,} | {r['atlas_resolution']} | [Blend]({r['model']}) · [Вид]({root}/previews/front34.png) · [Сетка]({root}/previews/topology_front.png) |\n"
    (DELIVERY/'README.md').write_text(text,encoding='utf-8')
    write(WORK/'delivery_summary.json',data)


def main():
    p=argparse.ArgumentParser(); p.add_argument('--ids',default=''); p.add_argument('--resume',action='store_true')
    args=p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    selected=set(args.ids.split(',')) if args.ids else None
    results=[]
    for a in rows():
        if selected and a['id'] not in selected: continue
        path=DELIVERY/'assets'/a['folder']/'checks/delivery_validation.json'
        if args.resume and path.exists():
            v=read(path); r=read(path.parent/'retopology.json')
            if v['passed'] and v.get('work_model_sha256')==sha(WORK/a['retopo_model']) and sha(DELIVERY/a['retopo_model'])==v['model_sha256']:
                results.append(dict(id=a['id'],folder=a['folder'],name=a['name'],model=a['retopo_model'],
                    model_sha256=v['model_sha256'],source_pbr=a['source_pbr'],source_sha256=r['source_sha256'],
                    before=r['before'],after=r['after'],atlas_resolution=r['atlas_resolution'],mesh_parts=v['mesh_parts']))
                continue
        results.append(one(a))
    catalog(results)
    print('DELIVERY_COMPLETE',len(results),flush=True)


if __name__=='__main__': main()
