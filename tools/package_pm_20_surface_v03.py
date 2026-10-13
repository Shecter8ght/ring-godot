"""Portable native PM 20-v03 and exact relative texture dependencies."""
from pathlib import Path
import os,json,hashlib,shutil
import bpy,addon_utils
PROJECT=Path(__file__).resolve().parents[1];ROOT=PROJECT/'_asset_src/pm_texturing';REV=ROOT/'revision_20_v03';OUT=REV/'delivery'
BASE=Path('E:/Models Blender/WEAPONS/ПМ — модели и текстуры/15_Текстуры_v2_20_на_проверку')
DEST=BASE.parent/'16_Текстуры_v3_20_на_проверку';SOURCE=REV/'candidate/PM_Textures_20_v03.blend'
digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
check=json.loads((REV/'checks/candidate_validation.json').read_text(encoding='utf-8'));assert check['pass_checks']
for folder in ('01_ПМ','02_Текстуры','03_Источники','04_Проверки','05_Скрипты'):(OUT/folder).mkdir(parents=True,exist_ok=True)
shutil.copytree(BASE/'03_Источники',OUT/'03_Источники',dirs_exist_ok=True)
bpy.context.preferences.use_preferences_save=False;addon_utils.enable('bl_ext.blender_org.ucupaint',default_set=True);bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
target=OUT/'01_ПМ'/SOURCE.name;images=[];fonts=[]
for im in bpy.data.images:
    if im.type in {'RENDER_RESULT','COMPOSITING'}:continue
    assert im.packed_file,im.name
    content=bytes(im.packed_file.data);sha=hashlib.sha256(content).hexdigest();original=Path(im.filepath.replace('\\','/')).name
    stem=(im.name if im.name.startswith('PM_') else Path(original).stem)[:90];suffix=Path(original).suffix or '.png'
    folder=OUT/('02_Текстуры' if im.name.startswith('PM_') else '03_Источники/Встроенные_ресурсы');folder.mkdir(parents=True,exist_ok=True)
    external=folder/f'{stem}__{sha[:10]}{suffix}';external.write_bytes(content);space=im.colorspace_settings.name
    im.unpack(method='REMOVE');im.filepath=str(external);im.reload();im.colorspace_settings.name=space;im.pack()
    assert hashlib.sha256(bytes(im.packed_file.data)).hexdigest()==sha
    im.filepath='//'+os.path.relpath(external,target.parent).replace('\\','/')
    for packed in im.packed_files:
        prop=packed.bl_rna.properties.get('filepath')
        if prop and not prop.is_readonly:packed.filepath=im.filepath
    images.append(dict(condition=20,datablock=im.name,file=external.relative_to(OUT).as_posix(),shader_path=im.filepath,sha256=sha,size=list(im.size),color_space=space,packed=True))
for font in bpy.data.fonts:
    if not font.packed_file:continue
    content=bytes(font.packed_file.data);sha=hashlib.sha256(content).hexdigest();original=Path(font.filepath.replace('\\','/')).name
    external=OUT/'03_Источники/Шрифты'/f'{Path(original).stem}__{sha[:10]}{Path(original).suffix}';external.parent.mkdir(parents=True,exist_ok=True);external.write_bytes(content)
    font.filepath='//'+os.path.relpath(external,target.parent).replace('\\','/');fonts.append(dict(condition=20,datablock=font.name,file=external.relative_to(OUT).as_posix(),sha256=sha))
bpy.ops.wm.save_as_mainfile(filepath=str(target),relative_remap=False)
(OUT/'texture_manifest.json').write_text(json.dumps(dict(revision='20-v03',conditions=[20],images=images,fonts=fonts),ensure_ascii=False,indent=2),encoding='utf-8')
details=json.loads((REV/'maps/manifest.json').read_text(encoding='utf-8'))
for row in details['images']:
    match=next(i for i in images if i['sha256']==row['sha256']);row['authored_file']=row['file'];row['file']=match['file']
for row in details['alpha_sources']:
    dst=OUT/'03_Источники/Альфы_владельца'/row['relative'];dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(REV/row['copied_file'],dst);row['copied_file']=dst.relative_to(OUT).as_posix()
(OUT/'03_Источники/Поверхности_и_частицы_v03.json').write_text(json.dumps(details,ensure_ascii=False,indent=2),encoding='utf-8')
for name in ('candidate_validation.json','authoring.json'):shutil.copy2(REV/'checks'/name,OUT/'04_Проверки'/name)
for name in ('refine_pm_20_surface_v03.py','pm_20_surface_detail_maps.py','package_pm_20_surface_v03.py','render_pm_20_review.py','check_pm_pbr.py','author_pm_pbr.py','publish_pm_20_surface_v03.ps1'):
    shutil.copy2(PROJECT/'tools'/name,OUT/'05_Скрипты'/name)
state=dict(asset='ПМ / КОРС-9',revision='20-v03',condition=20,owner_accepted=False,stage='prepared_for_owner_review',source=str(BASE/'01_ПМ/PM_Textures_20_v02.blend'),source_sha256=digest(REV/'approved/PM_20_v02_SOURCE.blend'),delivery=str(DEST/'01_ПМ'/target.name),geometry_source_sha256=check['source_sha256'],geometry_changed=False,other_conditions='100/60 unchanged',deferred_geometry='Lower lens housing corner defect postponed by owner until texture acceptance',game_export=False,presentation=False,blender=bpy.app.version_string,ucupaint='2.4.9')
(OUT/'asset-state.json').write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'asset-state.md').write_text('''# ПМ / КОРС-9 — состояние 20%, текстуры v03

Кандидат для визуальной проверки владельцем. Открыть
`01_ПМ/PM_Textures_20_v03.blend` в Blender, Material Preview / Rendered.

Тёмное заводское воронение и отпечатки пальцев/ладоней v02 сохранены.
На рукояти добавлены неодинаковые неровности формовки, положительные
наплывы и мелкая фактура прессованного фенопласта. Глянец чётче;
его Normal связан с рельефом материала. Полимер остаётся диэлектриком.

Металл имеет мелкую шероховатость и редкие небольшие раковины.
На открытых острых кромках — прерывистый износ до металлической основы,
отдельные сколы и выцветание защитного слоя. Плоскости остаются тёмными.
Тонкая прозрачная масляная реакция использует IOR 1.46 и следует
редактируемой шероховатости следов хвата; сухие отложения остаются матовыми.

В насечках затвора и радиальных вырезах курка — тёмное уплотнённое
отложение, пыль и отдельные светлые частицы кожи/грязи. Размещение
ограничено глубиной и координатами реальных принятых вырезов.
Частицы имеют положительный Height, раковины — отрицательный.
PNG16 — кодирующий span 140 мкм, midpoint 0.5, физический тайл 20 мм;
маски и интенсивности уменьшают итоговый рельеф относительно полного span.
Процедурные и seeded-карты художественные, не измеренные сканы.

Настоящие слои UCUPaint 2.4.9 / Blender 5.2.2 LTS. Принятая геометрия
v11, её модификаторы, иерархия, драйверы, Actions и ручные контролы
сохранены. Текстуры встроены, точные относительные копии и происхождение
прилагаются. Микрофактура проверена крупно, без DOF/denoise, под
нейтральным и противоположными скользящими светами.

100/60 не изменены. Правка нижних углов корпуса прицела остаётся
отложенной. Игровой bake/LOD, экспорт, импорт, видео и галереи не выполнялись.
''',encoding='utf-8')
print('PM_20_V03_PACKAGE_READY',target,len(images),'packed images',flush=True)
