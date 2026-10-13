"""Portable native 20% PM v02 only; no export, game bake or presentation."""
from pathlib import Path
import sys,os,json,hashlib,shutil
import bpy,addon_utils
PROJECT=Path(__file__).resolve().parents[1];ROOT=PROJECT/'_asset_src/pm_texturing';REV=ROOT/'revision_20_v02'
OUT=REV/'delivery';SOURCE=REV/'candidate/PM_Textures_20_v02.blend'
LIB=Path('E:/Models Blender/WEAPONS/ПМ — модели и текстуры/15_Текстуры_v2_20_на_проверку')
digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
bpy.context.preferences.use_preferences_save=False;addon_utils.enable('bl_ext.blender_org.ucupaint',default_set=True)
validation=json.loads((REV/'checks/candidate_validation.json').read_text(encoding='utf-8'))
assert validation['pass_checks'] and not validation['geometry_changes']
for name in ('01_ПМ','02_Текстуры','03_Источники','04_Проверки','05_Скрипты'):(OUT/name).mkdir(parents=True,exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
target=OUT/'01_ПМ'/SOURCE.name;images=[];fonts=[]
for im in bpy.data.images:
    if im.type in {'RENDER_RESULT','COMPOSITING'}:continue
    assert im.packed_file,im.name
    content=bytes(im.packed_file.data);sha=hashlib.sha256(content).hexdigest()
    original=Path(im.filepath.replace('\\','/')).name;suffix=Path(original).suffix.lower() or '.png'
    stem=(im.name if im.name.startswith('PM_') else Path(original).stem)[:90]
    folder=OUT/('02_Текстуры' if im.name.startswith('PM_') else '03_Источники/Встроенные_ресурсы')
    folder.mkdir(parents=True,exist_ok=True);external=folder/f'{stem}__{sha[:10]}{suffix}'
    external.write_bytes(content);assert digest(external)==sha
    space=im.colorspace_settings.name
    im.unpack(method='REMOVE');im.filepath=str(external);im.reload();im.colorspace_settings.name=space;im.pack()
    assert hashlib.sha256(bytes(im.packed_file.data)).hexdigest()==sha
    im.filepath='//'+os.path.relpath(external,target.parent).replace('\\','/')
    for packed in im.packed_files:
        prop=packed.bl_rna.properties.get('filepath')
        if prop and not prop.is_readonly:packed.filepath=im.filepath
    images.append(dict(condition=20,datablock=im.name,file=external.relative_to(OUT).as_posix(),shader_path=im.filepath,sha256=sha,size=list(im.size),color_space=space,packed=True,
                       origin='Authored artistic PBR/contact mask; see placements and source manifests' if im.name.startswith('PM_') else ('Poly Haven Story Studio 02, CC0' if original.endswith('.hdr') else 'Preserved owner reference; visual reference only')))
for font in bpy.data.fonts:
    if not font.packed_file:continue
    content=bytes(font.packed_file.data);sha=hashlib.sha256(content).hexdigest();original=Path(font.filepath.replace('\\','/')).name
    external=OUT/'03_Источники/Шрифты'/f'{Path(original).stem}__{sha[:10]}{Path(original).suffix}'
    external.parent.mkdir(parents=True,exist_ok=True);external.write_bytes(content)
    font.filepath='//'+os.path.relpath(external,target.parent).replace('\\','/')
    fonts.append(dict(condition=20,datablock=font.name,file=external.relative_to(OUT).as_posix(),sha256=sha,origin='Packed original font from accepted geometry; original license applies'))
glass=bpy.data.objects['Reflex | K1 curved aspheric lens'].data.materials[0]
if hasattr(glass,'use_raytrace_refraction'):glass.use_raytrace_refraction=True
if hasattr(bpy.context.scene,'eevee') and hasattr(bpy.context.scene.eevee,'use_raytracing'):bpy.context.scene.eevee.use_raytracing=True
rig=bpy.data.objects['PM_CONTROLS • select me'];rig['Texture stage']='20% v02, dark factory bluing and skin oil; prepared for owner review'
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':
            area.spaces.active.shading.type='MATERIAL';area.spaces.active.overlay.show_extras=False;area.spaces.active.overlay.show_relationship_lines=False
for name in ('PM_CONTROLS • select me','PM_OpticMount • asset root','PM_ReflexSight • asset root','Magazine • extraction'):
    bpy.data.objects[name]['condition_percent']=20
bpy.context.scene.render.engine='CYCLES'
bpy.ops.wm.save_as_mainfile(filepath=str(target),relative_remap=False)
(OUT/'texture_manifest.json').write_text(json.dumps(dict(revision='20-v02',conditions=[20],images=images,fonts=fonts),ensure_ascii=False,indent=2),encoding='utf-8')

def copy(src,rel):
    dst=OUT/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst);assert digest(src)==digest(dst);return dst

contacts=json.loads((REV/'masks/manifest.json').read_text(encoding='utf-8'))
for row in contacts['source_alphas']:
    src=REV/row['copied_file'];copy(src,'03_Источники/Альфы_владельца/'+row['relative'])
    row['copied_file']='03_Источники/Альфы_владельца/'+row['relative']
for row in contacts['images']:
    im=next(r for r in images if r['sha256']==row['sha256']);row['authored_file']=row['file'];row['file']=im['file']
(OUT/'03_Источники/Контактные_маски_v02.json').write_text(json.dumps(contacts,ensure_ascii=False,indent=2),encoding='utf-8')
# Existing optic/fastener/lens layers retain their licensed and owner sources.
legacy=json.loads((ROOT/'sources/used_alphas.json').read_text(encoding='utf-8'))
for row in legacy:
    src=ROOT/row['copied_file'];copy(src,'03_Источники/Альфы_владельца/'+row['relative']);row['copied_file']='03_Источники/Альфы_владельца/'+row['relative']
(OUT/'03_Источники/Альфы_предыдущих_полезных_слоёв.json').write_text(json.dumps(legacy,ensure_ascii=False,indent=2),encoding='utf-8')
for src in (ROOT/'sources/cc0').glob('*'):
    if src.is_file():copy(src,'03_Источники/CC0/'+src.name)
copy(ROOT/'sources/cc0_manifest.json','03_Источники/CC0_manifest.json')
for src in (REV/'references').glob('*.png'):copy(src,'03_Источники/Референсы_владельца/'+src.name)
copy(REV/'references/manifest.json','03_Источники/Референсы_владельца/manifest.json')
copy(REV/'checks/authoring.json','04_Проверки/authoring.json');copy(REV/'checks/candidate_validation.json','04_Проверки/candidate_validation.json')
for name in ('refine_pm_20_pbr.py','pm_20_contact_masks.py','render_pm_20_review.py','check_pm_pbr.py','package_pm_20_pbr.py','author_pm_pbr.py'):
    copy(PROJECT/'tools'/name,'05_Скрипты/'+name)
state=dict(asset='ПМ / КОРС-9',revision='20-v02',stage='prepared_for_owner_review',owner_accepted=False,condition=20,
           approved_geometry=str(ROOT/'approved/PM_Geometry_v11_APPROVED.blend'),approved_geometry_sha256=digest(ROOT/'approved/PM_Geometry_v11_APPROVED.blend'),
           previous_texture_source=str(ROOT/'candidate/20/PM_Textures_20_v01.blend'),candidate=str(SOURCE),candidate_sha256=digest(SOURCE),delivery=str(LIB/'01_ПМ'/target.name),geometry_changed=False,
           other_conditions='100/60 v01 not modified; current owner focus is 20 only',
           user_correction='Dark factory bluing, no bleached/cloudy camouflage; oily fading and skin traces. Five palm alphas, trigger, extended right index included.',
           alpha_library='E:/Models Blender/Маски_АЛЬФА',blender=bpy.app.version_string,ucupaint='2.4.9',
           deferred_geometry=rig['Deferred geometry'],game_export=False,video_or_presentation=False,
           axes='metres; -X muzzle, +X backstrap, -Y left controls, +Z up; rest-pose maps move with parts')
(OUT/'asset-state.json').write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
(REV/'texture_state.json').write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'asset-state.md').write_text('''# ПМ / КОРС-9 — 20%, текстуры v02

Кандидат для проверки владельцем. Текстуры ещё не приняты.
Открыть `01_ПМ/PM_Textures_20_v02.blend` в Blender, Material Preview / Rendered.

Затвор сохраняет тёмное заводское воронение. Светлая облачная пятнистость
убрана; выцветание и следы хвата передаются слабыми переходами оттенка,
масляными разводами и изменением шероховатости. Неуместный штрихованный
участок царапин слева удалён. Рамка тёмная серо-коричневая, скоба светлее,
ствол гладкий сатиновый. Рукоять — полуглянцевый бордовый фенопласт.

На передней половине затвора, рукояти и курке — многочисленные отпечатки.
На рукояти использованы все пять масок ладоней, широкими частичными
контактами. На спуске — следы пальца. Справа под окном выброса гильз и
на рамке — следы вытянутого указательного пальца. Впадины защищены от
чрезмерных отпечатков, нанесение следует доступной геометрии.

Настоящие нативные слои UCUPaint 2.4.9, Blender 5.2.2 LTS.
Принятая форма v11, модификаторы, родители, драйверы и ручные контролы
сохранены. Прежние полезные стеки и заполнение утопленных клейм оставлены;
конфликтующие эффекты прежнего материала отключены. Изображения встроены
и имеют проверяемые относительные копии; источники и преобразования рядом.
Это художественные PBR-маски, не измеренные сканы пистолета.

Состояния 100/60 не дорабатывались. Правка корпуса прицела у нижних углов
линзы отложена владельцем до принятия текстур. Роликов, галерей, игрового
bake/LOD, экспорта и импорта в Godot нет.
''',encoding='utf-8')
(OUT/'03_Источники/LICENSES.md').write_text('''Owner alpha library: supplied for this asset; original ownership applies.
Owner screenshots: visual references only, not extracted as PBR textures.
ambientCG Scratches004 / Smear002: https://ambientcg.com/view?id=Scratches004 ;
https://ambientcg.com/view?id=Smear002 ; CC0 1.0: https://docs.ambientcg.com/license/ .
Preserved studio HDRI: https://polyhaven.com/a/story_studio_02 ;
Poly Haven CC0: https://polyhaven.com/license .
Original packed font is preserved, with its original license.
Native procedural layers/contact atlases are authored artistic materials;
no measured or photogrammetric scan claim is made.
''',encoding='utf-8')
print('PM_20_PACKAGE_READY',target,len(images),'packed/external images',len(fonts),'fonts',flush=True)
