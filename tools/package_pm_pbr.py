"""Pack editable PM texture states with exact external dependency copies.

Creates only a workspace delivery directory. Library publication is a separate
bounded copy after fresh-file validation. No renders, gallery, video or export.
"""
from pathlib import Path
import sys,json,hashlib,shutil,os
import bpy,addon_utils
PROJECT=Path(__file__).resolve().parents[1];ROOT=PROJECT/'_asset_src/pm_texturing'
OUT=ROOT/'delivery';LIB=Path('E:/Models Blender/WEAPONS/ПМ — модели и текстуры/14_Текстуры_v1_на_проверку')
bpy.context.preferences.use_preferences_save=False
addon_utils.enable('bl_ext.blender_org.ucupaint',default_set=True)
for folder in ('01_ПМ','02_Текстуры','03_Источники','04_Проверки','05_Скрипты'):(OUT/folder).mkdir(parents=True,exist_ok=True)
state=json.loads((ROOT/'texture_state.json').read_text(encoding='utf-8'))
image_records=[];font_records=[];file_records=[]
digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

for condition in (100,60,20):
 source=ROOT/'candidate'/str(condition)/f'PM_Textures_{condition}_v01.blend'
 bpy.ops.wm.open_mainfile(filepath=str(source))
 target=OUT/'01_ПМ'/source.name
 for im in bpy.data.images:
  if im.type in {'RENDER_RESULT','COMPOSITING'}:continue
  if not im.packed_file:raise RuntimeError('Unpacked image: '+im.name)
  content=bytes(im.packed_file.data);sha=hashlib.sha256(content).hexdigest()
  orig=Path(im.filepath.replace('\\','/')).name
  suffix=Path(orig).suffix.lower() or '.png'
  stem=(im.name if im.name.startswith('PM_') else Path(orig).stem)[:90]
  folder=OUT/('02_Текстуры' if im.name.startswith('PM_') else '03_Источники/Встроенные_ресурсы')
  folder.mkdir(parents=True,exist_ok=True);external=folder/f'{stem}__{sha[:10]}{suffix}'
  if not external.exists():external.write_bytes(content)
  assert digest(external)==sha
  relative=os.path.relpath(external,target.parent).replace('\\','/')
  old_space=im.colorspace_settings.name
  # REMOVE unpacks only in memory and writes no historical/temp paths. Reload
  # the exact exported bytes, then pack from a valid task-local source. This
  # replaces stale internal packed-file names inherited from old geometry.
  im.unpack(method='REMOVE');im.filepath=str(external);im.reload()
  im.colorspace_settings.name=old_space;im.pack()
  assert hashlib.sha256(bytes(im.packed_file.data)).hexdigest()==sha
  im.filepath='//'+relative
  for packed in im.packed_files:
   prop=packed.bl_rna.properties.get('filepath')
   if prop and not prop.is_readonly:packed.filepath=im.filepath
  assert im.colorspace_settings.name==old_space
  origin='Authored physical-scale mask; placements/alpha/CC0 origins in source manifests' if im.name.startswith('PM_') else ('Poly Haven Story Studio 02, CC0 1.0' if orig=='story_studio_02_4k.hdr' else 'Preserved visual reference from accepted geometry; not a PBR texture')
  image_records.append(dict(condition=condition,datablock=im.name,file=external.relative_to(OUT).as_posix(),shader_path=im.filepath,
                            sha256=sha,size=list(im.size),color_space=old_space,packed=True,origin=origin))
 for font in bpy.data.fonts:
  if not font.packed_file:continue
  content=bytes(font.packed_file.data);sha=hashlib.sha256(content).hexdigest()
  orig=Path(font.filepath.replace('\\','/')).name;external=OUT/'03_Источники/Шрифты'/f'{Path(orig).stem}__{sha[:10]}{Path(orig).suffix}'
  external.parent.mkdir(parents=True,exist_ok=True)
  if not external.exists():external.write_bytes(content)
  assert digest(external)==sha
  font.filepath='//'+os.path.relpath(external,target.parent).replace('\\','/')
  font_records.append(dict(condition=condition,datablock=font.name,file=external.relative_to(OUT).as_posix(),sha256=sha,origin='Packed font preserved from accepted geometry; original license applies'))
 for name in ('PM_CONTROLS • select me','PM_OpticMount • asset root','PM_ReflexSight • asset root','Magazine • extraction'):
  if name in bpy.data.objects:bpy.data.objects[name]['condition_percent']=condition
 glass=bpy.data.objects['Reflex | K1 curved aspheric lens'].data.materials[0]
 # Feature-gated settings of this installed Blender, never global preferences.
 # Cycles remains the saved renderer; these also allow EEVEE preview refraction.
 if hasattr(glass,'use_raytrace_refraction'):glass.use_raytrace_refraction=True
 if hasattr(bpy.context.scene,'eevee') and hasattr(bpy.context.scene.eevee,'use_raytracing'):bpy.context.scene.eevee.use_raytracing=True
 # Source resources are already packed. Repacking attempts stale historical
 # paths. Relative paths were authored for the destination, so disable Blender's
 # automatic remapping from the previous candidate directory.
 assert all(im.packed_file for im in bpy.data.images if im.type not in {'RENDER_RESULT','COMPOSITING'})
 bpy.ops.wm.save_as_mainfile(filepath=str(target),relative_remap=False)
 file_records.append(dict(condition=condition,file=target.relative_to(OUT).as_posix(),sha256=digest(target),geometry='accepted v11',texture_approved=False))
 print('PM_PACKAGED_NATIVE',condition,target,flush=True)

for sub,dest in (('sources/alphas','03_Источники/Альфы_владельца'),('sources/cc0','03_Источники/CC0')):
 shutil.copytree(ROOT/sub,OUT/dest,dirs_exist_ok=True)
for name in ('alpha_manifest.json','cc0_manifest.json'):
 shutil.copy2(ROOT/'sources'/name,OUT/'03_Источники'/name)
used=json.loads((ROOT/'sources/used_alphas.json').read_text(encoding='utf-8'))
for row in used:row['copied_file']='03_Источники/Альфы_владельца/'+row['relative']
(OUT/'03_Источники/used_alphas.json').write_text(json.dumps(used,ensure_ascii=False,indent=2),encoding='utf-8')
placements=json.loads((ROOT/'textures/mask_manifest.json').read_text(encoding='utf-8'))
for row in placements['images']:
 row['authored_file']=row['file']
 name=f"PM_{row['condition']}_{row['projection']}_{row['purpose']}"
 delivered=next((r for r in image_records if r['datablock']==name),None)
 row['file']=delivered['file'] if delivered else None
(OUT/'03_Источники/mask_placements.json').write_text(json.dumps(placements,ensure_ascii=False,indent=2),encoding='utf-8')
for name in ('cleanup_candidates_report.json','cleanup_report.json'):
 shutil.copy2(ROOT/'checks'/name,OUT/'04_Проверки'/name)
for src in (PROJECT/'_asset_src/pm_refinement/surface_sources').glob('*/license_page.html'):
 shutil.copy2(src,OUT/'03_Источники/CC0'/f'{src.parent.name}_license.html')
for name in ('author_pm_pbr.py','pm_texture_masks.py','check_pm_pbr.py','package_pm_pbr.py','render_pm_materials.py'):
 shutil.copy2(PROJECT/'tools'/name,OUT/'05_Скрипты'/name)
state.update(stage='Native UCUPaint PBR v01, prepared for owner review',delivery=str(LIB),texture_approved=False,
             deferred_geometry='Owner observed a housing geometry/shading kink near both lower lens corners; explicitly postponed repair until after texture acceptance.',
             glass=dict(metallic=0,transmission=1,ior=1.48,diagnosis='Two-sided checker transmission confirmed; Solid viewport hides shader glass.'),
             source_types='Procedural factory microsurface + placed owner alphas + CC0 ambientCG scratch/smear detail; not presented as a measured scan of this PM.')
(ROOT/'texture_state.json').write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'04_Проверки/texture_state.json').write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'texture_manifest.json').write_text(json.dumps(dict(states=file_records,images=image_records,fonts=font_records),ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'variants.json').write_text(json.dumps([dict(condition_percent=c,file=f'01_ПМ/PM_Textures_{c}_v01.blend',geometry='accepted v11',gameplay_mapping=None,price=None) for c in (100,60,20)],ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'00_ОТКРЫТЬ_В_BLENDER.txt').write_text('ПМ / КОРС-9 — текстуры v01\n\nОсновной вариант для просмотра:\n01_ПМ/PM_Textures_60_v01.blend\n\n100% — заводское состояние без эксплуатации.\n60% — лёгкий износ.\n20% — тяжёлый износ, самостоятельный рисунок следов.\nЭто один пистолет с разными состояниями материалов.\n\nМатериалы редактируются в UCUPaint 2.4.9 (Blender 5.2.2).\nВсе изображения и шрифты встроены; рядом лежат относительные внешние копии.\nСтекло смотреть в Material Preview или Rendered: Solid не показывает прозрачность.\nРучные контролы — на объекте PM_CONTROLS • select me.\n\nТекстуры подготовлены к вашему просмотру, пока не приняты.\nДефект корпуса у левого и правого нижнего угла стекла сохранён по вашему\nуказанию; его правка будет после принятия текстур.\n\nГеометрия, подвижные детали и глубины клейм сохранены по принятой v11.\nИгровые bake/LOD/экспорт/материал линзы Godot — следующий отдельный этап.\nНезависимые глушитель, патрон и оба магазина в прежних актуальных папках сохранены.\n',encoding='utf-8')
(OUT/'asset-state.md').write_text(f'''# ПМ / КОРС-9 — нативное PBR v01

Источник формы: `{state['source']}`. Владелец принял v11 словами «всё просто прекрасно» и поручил текстурирование 2026-10-13.
SHA-256: `{state['sha256']}`. Контрольная копия: `{state['frozen_source']}`.
Стадия: подготовлено к просмотру; принятие текстур ещё ожидается.

Blender 5.2.2 LTS, UCUPaint 2.4.9. Использован обновлённый skill `weapon-asset-texturing`.
Одна оружейная сборка: ПМ, установленное крепление, ЗОРИН К-1 и магазин. Состояния 100/60/20 лежат отдельными `.blend`, каждый со своими независимыми материалами. Отдельные компоненты библиотеки не заменялись.

Форма всех состояний — принятая v11. +X — затыльник, −X — дульная часть, −Y — сторона органов управления, +Z — вверх; размеры в метрах. Пистолет без обвесов занимает около 160 × 32 × 123 мм. Ручные свойства Slide/Hammer/Trigger/Safety/Magazine/MagCatch/SlideStop сохранены, демонстрационный Action не назначен.

13 нативных материалов: воронёная сталь, обработанная сталь ствола, крепёж, чёрный анодированный алюминий, красно-коричневый бакелит, резина, диэлектрическая линза, латунь, томпак, капсюль, красная эмаль предохранителя, светлая точка мушки и сохранённая двухслойная эмаль клейм. Окраска дна существующих клейм не меняет глубины или формы вырезов.

Заводское зерно/обработка — процедурные, в физическом масштабе, не объявляются фотосканом. Для износа использованы 13 масок владельца из 43 доступных (RGB, сигнал яркости, без alpha) и вторичные CC0-паттерны ambientCG. У отпечатков основное изменение — roughness; пыль и окислы диэлектрические, снятое воронение открывает металлическую сталь. Бакелит при износе остаётся полимером. Никаких придуманных трещин линзы или изменений силуэта.

Исходные UV сохранены. `PMWearUV`: две независимые стороны, каждый участок 166 × 175 мм, 4096 × 4096 пикселей, около 43 мкм/пиксель. `PMTopUV`: 166 × 50 мм. `LensUV`: 32 × 24 мм. Цветовые атрибуты ограничивают проекции по ориентации, хвату и защищённости. Маски порогов находятся внутри отдельных Noise; границы штампов плавно уходят в ноль. Подвижные детали уносят UV вместе с собой.

100% сохраняет заводскую обработку без эксплуатационных масок; эмаль клейм целая. 60/20 имеют отдельные рисунки, не являются одним рисунком с изменённой общей прозрачностью. Износ редактируется по слоям UCUPaint; названия слоёв называют его причину.

Линза Metallic=0, Transmission=1, IOR=1.48. Оттенок и тонкая плёнка — художественное приближение по присланным референсам, не расчёт оптической системы конкретного производителя. Пропускание проверено с контрастной подложкой с обеих сторон. Для просмотра нужен Material Preview/Rendered. Godot требует своего этапа материалов и проверки импорта.

Все изображения и используемые внешние шрифты встроены и имеют относительные копии. `texture_manifest.json` сопоставляет datablock, файл, SHA-256, размер, color space и источник; `03_Источники/mask_placements.json` содержит физические размеры и размещения штампов. Проверки сравнивают базовую форму, текст/кривые, родителей, локальные матрицы, модификаторы, драйверы, Actions и shape keys с контрольной v11. Подтверждение окончательных проверок — в `04_Проверки`.

Источники: фото и снимки владельца — только визуальные референсы; [{ 'ambientCG Scratches004' }](https://ambientcg.com/view?id=Scratches004) и [Smear002](https://ambientcg.com/view?id=Smear002), [CC0](https://docs.ambientcg.com/license/); окружение [Story Studio 02](https://polyhaven.com/a/story_studio_02), Grzegorz Wronkowski, [CC0](https://polyhaven.com/license). Шрифты и прежние изображения унаследованы из принятой геометрии со своими исходными условиями использования.

По явному поручению удалены 19 старых папок кандидатов и резервов, 9 963 159 655 байт. Актуальные ПМ v11, глушитель, пустой и снаряжённый магазины, патрон и исходные скрипты сохранены; контрольный файл формы не изменён.

Отложенный дефект: излом корпуса у обоих нижних углов линзы. Владелец прямо указал исправлять его после принятия текстур; в этом комплекте он сохранён. Игровая сетка, запекание, LOD, коллизии, экспорт и внедрение в Godot не выполнялись.

Скрипты в `05_Скрипты` — копии инструментов проекта для истории и повторного авторинга. Запускать их из `E:/Games/RING-godot/tools`, где находятся принятая контрольная копия и исходные маски. Для обычного редактирования достаточно `.blend` и установленного UCUPaint.
''',encoding='utf-8')
print('PM_PBR_PACKAGE_READY',OUT,flush=True)
