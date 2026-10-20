"""Deliver the original clothing candidate and three editable native assets."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

import addon_utils
import bpy
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[2]
MODEL_ROOT=Path('E:/Models Blender/RING_NPC_2026-10-20_v01')
PARTS=[
    ('T00_TShirt','01_Original_TShirt_M02','shirt',1.22,.98),
    ('P02_Work_Trousers','02_Original_Work_Trousers_M02','trousers',.62,1.25),
    ('F02_Work_Boots','03_Original_Work_Boots_M02','boots',.105,.52),
]


def enable_layers():
    module='bl_ext.blender_org.ucupaint'
    bpy.context.preferences.use_preferences_save=False
    if module not in bpy.context.preferences.addons:
        bpy.context.preferences.addons.new().module=module
    addon_utils.enable(module,default_set=False,persistent=False)


def frame(target=(0,0,.96),distance=2.55):
    direction=Vector((2.7,-4,1.3))
    rotation=direction.to_track_quat('Z','Y')
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type=='VIEW_3D':
                space=area.spaces.active
                space.shading.type='MATERIAL'
                space.region_3d.view_location=target
                space.region_3d.view_distance=distance
                space.region_3d.view_rotation=rotation
                space.clip_start=.001
                space.clip_end=100


def pack_images(out):
    textures=out/'textures'
    textures.mkdir(exist_ok=True)
    images=[]
    for image in bpy.data.images:
        if image.source!='FILE' or not image.filepath: continue
        assert image.packed_file and image.packed_file.size>0,image.name
        payload=bytes(image.packed_file.data)
        filename=Path(image.name).name
        target=textures/filename
        if target.exists(): assert target.read_bytes()==payload,target
        else: target.write_bytes(payload)
        image.filepath='//textures/'+filename
        images.append({'image':image.name,'path':'textures/'+filename,
            'sha256':hashlib.sha256(payload).hexdigest()})
    bpy.ops.file.pack_all()
    return images


def deliver(source,out):
    source=source.resolve()
    out=out.resolve()
    assert out.parent==MODEL_ROOT.resolve()
    assert not out.exists(),out
    report=json.loads((source.parent/'clothes_report.json').read_text(encoding='utf-8'))
    assert hashlib.sha256(Path(report['source']).read_bytes()).hexdigest()==report['source_sha256']
    verification=json.loads((source.parent/'verification/clothes_verification.json').read_text(encoding='utf-8'))
    assert verification['status']=='PASS'
    out.mkdir()
    bpy.ops.wm.open_mainfile(filepath=str(source))
    enable_layers()
    report['images']=pack_images(out)
    rig=bpy.data.objects['M02_New_Anatomical_Rig']
    rig.hide_set(True)
    controls=bpy.data.objects['M02_Clothing_Controls']
    controls.hide_set(True)
    frame()
    bpy.context.scene.camera=bpy.data.objects['Custom_Clothes_ThreeQuarter']
    bpy.context.scene.render.filepath='//threequarter.png'
    bpy.context.preferences.filepaths.save_version=0
    main=out/source.name
    bpy.ops.wm.save_as_mainfile(filepath=str(main),check_existing=False,relative_remap=False)
    report['file']=str(main)
    assets=out/'Separate_Assets'
    assets.mkdir()
    asset_report=[]
    for stem,name,key,z,scale in PARTS:
        bpy.ops.wm.open_mainfile(filepath=str(main))
        selected=bpy.data.collections[name]
        rig=bpy.data.objects['M02_New_Anatomical_Rig']
        controls=bpy.data.objects['M02_Clothing_Controls']
        keep=set(selected.all_objects)|{rig,controls}
        keep|={obj for obj in bpy.context.scene.objects if obj.type in ['CAMERA','LIGHT']}
        for obj in list(bpy.data.objects):
            if obj not in keep: bpy.data.objects.remove(obj,do_unlink=True)
        # Each native collection includes its own fitting skeleton and controls,
        # so appending this asset never leaves dangling parent/driver targets.
        for obj in [rig,controls]:
            if obj.name not in selected.objects: selected.objects.link(obj)
        for candidate in ['shirt','trousers','boots']: controls[candidate]=candidate==key
        controls.update_tag()
        bpy.context.view_layer.update()
        selected.asset_mark()
        selected.asset_data.description='Original RING '+stem+'; editable M02 size with preliminary rig. Geometry review candidate.'
        selected.asset_data.tags.new('RING')
        selected.asset_data.tags.new('M02')
        selected.asset_data.tags.new('Geometry review')
        for col in list(bpy.data.collections):
            if col!=selected and not col.objects and not col.children:
                bpy.data.collections.remove(col)
        bpy.data.orphans_purge(do_local_ids=True,do_linked_ids=True,do_recursive=True)
        camera=bpy.data.objects['Custom_Clothes_ThreeQuarter']
        target=Vector((0,-.025,z))
        camera.location=target+Vector((2.7,-4,.75))
        camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler()
        camera.data.ortho_scale=scale
        bpy.context.scene.camera=camera
        bpy.context.scene.render.filepath='//'+stem+'.png'
        frame(tuple(target),scale*1.3)
        path=assets/(stem+'_M02_v09.blend')
        bpy.ops.wm.save_as_mainfile(filepath=str(path),check_existing=False,relative_remap=False)
        asset_report.append({'id':stem,'file':str(path.relative_to(out)).replace('\\','/'),
            'mesh_objects':sum(obj.type=='MESH' for obj in selected.objects),
            'native_collection_asset':name,'independent_rig_and_controls':True})
    for view in ['front','back','threequarter','boots']:
        shutil.copy2(source.parent/(view+'.png'),out/(view+'.png'))
    report['separate_assets']=asset_report
    (out/'clothes_report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    verification['file']=str(main)
    (out/'clothes_verification.json').write_text(json.dumps(verification,indent=2,ensure_ascii=False),encoding='utf-8')
    source_folder=Path(report['source']).parent
    shutil.copytree(source_folder/'licenses',out/'licenses')
    shutil.copy2(source_folder/'sources_licenses.md',out/'character_sources_licenses.md')
    for script in ['m02_custom_clothes.py','m02_custom_clothes_verify.py','m02_custom_clothes_deliver.py']:
        (out/'construction_scripts').mkdir(exist_ok=True)
        shutil.copy2(ROOT/'tools/characters'/script,out/'construction_scripts'/script)
    (out/'00_НАЧНИ_ЗДЕСЬ.txt').write_text('''М02 — своя одежда, геометрия v09 на просмотр.

Открыть M02_Custom_Clothes_v09.blend в Blender 5.2.2 LTS.
Рядом — виды спереди, сзади, в три четверти и обувь вблизи.
Это первая собственная конструкция: футболка, рабочие брюки и кожаные ботинки.
Материалы нейтральные для проверки формы; финальные ткань, кожа, UV и износ ещё впереди.

В Separate_Assets/ лежат три отдельных .blend. Их можно открыть отдельно или добавить через File → Append → Collection.
В каждом есть одежда, свой экземпляр примерочного скелета М02 и контроллер.
В общей сцене одежда уже сидит на одном общем скелете М02.

В Outliner выбрать M02_Clothing_Controls. Object Properties → Custom Properties:
shirt / trousers / boots — независимые выключатели. Скрытые участки тела восстанавливаются сами.
Карманы и пояс брюк под футболкой временно скрыты; при выключении футболки появляются.
Исходная анатомия и UV тела не удалены. Старые примерочные шорты сохранены скрытыми.

Основные поверхности редактируются до сглаживания и толщины; швы, карманы, язычки,
шнурки и подошвы — отдельные объекты. Это подробные исходники Blender, не игровые модели.
Посадка сделана для М02. Другие тела требуют подгонки. Анимационные коррекции и игровой экспорт отдельно.
''',encoding='utf-8')
    (out/'asset-state.md').write_text('''# М02 — самостоятельные ассеты одежды, v09

Дата: 2026-10-20. Стадия: **первая геометрия на художественную оценку**.

Владелец отверг вид одежды из наборов и поручил изготовить собственные вещи.
Собраны три исходника: T00 футболка с нагрудным карманом, P02 рабочие брюки с
дублирующими коленными панелями, F02 кожаные рабочие ботинки со шнуровкой.
Это самостоятельный базовый комплект, а не точное воспроизведение всех деталей листа C02.
Куртка и остальные вещи из концептов в этот выпуск не входят.

## Устройство

Главный файл — `M02_Custom_Clothes_v09.blend`, примерка на М02 в T-позе.
Три `Separate_Assets/*.blend` содержат отдельные редактируемые вещи и собственный
экземпляр примерочного рига; коллекции помечены как нативные Blender Asset.
При объединении отдельных файлов под один скелет нужно переназначить Armature
на скелет целевого персонажа. В главном файле это уже сделано.

Основы футболки и брюк — сшитые поверхности, сглаживание и толщина не применены.
У футболки четыре открытых контура (ворот, подол, два рукава), у брюк три
(пояс, две штанины), посторонних неманифолдных рёбер и нулевых граней нет.
Детали вынесены в объекты. Вещи имеют первичные нормализованные веса общего рига.

Переключатели shirt / trousers / boots на `M02_Clothing_Controls` управляют вещами
и обратимыми масками тела. Верхние детали брюк скрываются под футболкой.
Маски не удаляют базовую анатомию; исходные координаты, топология, UV и все
shape keys тела совпадают с M02_Appearance_v05. Изображения персонажа упакованы.

## Проверено и что дальше

Повторное открытие, веса всех вершин, независимое переключение трёх вещей,
топология основных полотен и исходное тело проверены скриптом.
Опущенные руки и сгибы конечностей проверяются внутренними статичными кадрами.
Полная проверка игровых анимаций и коррекция складок по позам ещё не выполнены.

Текущие материалы — нейтральная заливка для оценки формы. Финальные UV, PBR,
микрорельеф ткани/кожи, износ, LOD, запекание и Godot-экспорт — последующие этапы.
Форма ещё не принята владельцем. Образцы размеров S/L не изготовлены.

Программное построение собственных полотен и деталей — `construction_scripts/`.
Одежда из MPFB/других наборов не использовалась.
''',encoding='utf-8')
    (out/'sources_licenses.md').write_text('''# Источники одежды М02

Все сетки футболки, брюк и обуви построены заново для RING; ни готовые сетки
одежды, ни fitting data, ни текстуры пакетов не использовались.
М02 и изображения кожи/глаз унаследованы из соседнего M02_Appearance_v05;
их CC0-происхождение сохранено в character_sources_licenses.md и licenses/.

Конструктивные ориентиры, фотографии и схемы просмотрены без копирования текстур и брендов:
- хлопковая футболка с круглым воротом и карманом: официальный Carhartt K87,
  https://s7d9.scene7.com/is/content/Carhartt/ECOM/CCG_Product_SellSheet/K87.pdf
- усиленные рабочие брюки: официальный Dickies Double Knee,
  https://www.dickies.com/en-us/products/relaxed-fit-double-knee-duck-pants-dk0dur02sbk
- устройство кожаного рабочего ботинка: лист производителя Red Wing 2233,
  https://www.nasa-comercial.com/wp-content/uploads/2012/05/REDWING-2233-Data-Sheet.pdf
- собственные сгенерированные концепты RING Clothing_Concepts_v01 использованы
  как дополнительный ориентир. Внешность с этих листов не переносилась на тело М02.

Это собственная вариация базового рабочего комплекта, не копия изделия или логотипа.
''',encoding='utf-8')
    manifest={str(path.relative_to(out)).replace('\\','/'):hashlib.sha256(path.read_bytes()).hexdigest()
        for path in out.rglob('*') if path.is_file()}
    (out/'sha256_manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding='utf-8')
    print('M02_CLOTHES_DELIVERED '+json.dumps({'file':str(main),'assets':asset_report,'files':len(manifest)},ensure_ascii=False),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('file',type=Path)
    parser.add_argument('--out',type=Path,default=MODEL_ROOT/'M02_Custom_Clothes_v09')
    argv=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    args=parser.parse_args(argv)
    deliver(args.file,args.out)
