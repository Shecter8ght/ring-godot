"""Упакованная библиотека NPC, отдельные Blender Asset и фотографии для скачивания."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import argparse,addon_utils,bpy,hashlib,json,re,shutil,zipfile
from mathutils import Vector
import m02_custom_clothes as G
import m02_custom_clothes_deliver as D
import wardrobe_geometry as W
import wardrobe_balaclavas as B
import npc_wardrobe as N

ROOT=Path(__file__).resolve().parents[2]
MODEL_ROOT=Path('E:/Models Blender/RING_NPC_2026-10-20_v01')


def pack(out):
    directory=out/'textures';directory.mkdir(exist_ok=True);report=[]
    for im in bpy.data.images:
        if im.name in ['Render Result','Viewer Node'] or not im.packed_file: continue
        payload=bytes(im.packed_file.data);sha=hashlib.sha256(payload).hexdigest()
        stem=re.sub(r'[^\w.\-]+','_',im.name)
        if not stem.lower().endswith(('.png','.jpg','.jpeg','.exr','.hdr','.tif')): stem+='.png'
        filename=sha[:10]+'_'+stem
        target=directory/filename
        if not target.exists(): target.write_bytes(payload)
        im.filepath='//textures/'+filename
        report.append({'name':im.name,'file':'textures/'+filename,'sha256':sha,'bytes':len(payload)})
    bpy.ops.file.pack_all()
    return report


def native_item_file(master,out,record,render):
    bpy.ops.wm.open_mainfile(filepath=str(master))
    selected=bpy.data.collections[record['collection']];rig=bpy.data.objects['M02_New_Anatomical_Rig'];control=bpy.data.objects['RING | Wardrobe Controls']
    studio=bpy.data.collections['06_Review_Studio'];keep=set(selected.objects)|{rig,control}|set(studio.objects)
    for obj in list(bpy.data.objects):
        if obj not in keep: bpy.data.objects.remove(obj,do_unlink=True)
    for obj in [rig,control]:
        if obj.name not in selected.objects: selected.objects.link(obj)
    if selected.name not in bpy.context.scene.collection.children: bpy.context.scene.collection.children.link(selected)
    for col in list(bpy.data.collections):
        if col not in [selected,studio]: bpy.data.collections.remove(col)
    control['Предмет']=record['isolation_index'];control.update_tag();bpy.context.view_layer.update()
    rig.hide_set(True);control.hide_set(True)
    selected.asset_mark();selected.asset_data.description=record['id']+' | '+record['title']+' | M02 | editable UCUPaint'
    for tag in ['RING','M02','Original clothing','UCUPaint']: selected.asset_data.tags.new(tag)
    for group in [bpy.data.meshes,bpy.data.materials,bpy.data.node_groups,bpy.data.images,bpy.data.armatures]:
        for block in group: block.use_fake_user=False
    bpy.data.orphans_purge(do_local_ids=True,do_linked_ids=True,do_recursive=True)
    code=record['id']
    z,scale=(1.25,1.08) if code.startswith('T') else (.60,1.20) if code.startswith('P') else (.13,.57) if code.startswith('F') else (1.63,.43)
    camera=bpy.data.objects['Wardrobe_ThreeQuarter'];target=Vector((0,-.025,z))
    camera.location=target+Vector((2.2,-4,.65));camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.ortho_scale=scale
    scene=bpy.context.scene;scene.camera=camera;scene.cycles.samples=32;scene.render.resolution_x=1000;scene.render.resolution_y=1100
    png=out/'Previews'/(code+'_asset.png');scene.render.filepath=str(png)
    D.frame(tuple(target),scale*1.4)
    filename=out/'Separate_Assets'/(code+'_M02.blend')
    for im in bpy.data.images:
        if im.packed_file and im.filepath.startswith('//textures/'):
            im.filepath='//../textures/'+im.filepath.rsplit('/',1)[-1]
    bpy.ops.wm.save_as_mainfile(filepath=str(filename),check_existing=False,relative_remap=False)
    if render: bpy.ops.render.render(write_still=True)
    assert all(not o.hide_render for o in selected.objects if o.type=='MESH')
    return {'id':code,'file':str(filename.relative_to(out)).replace('\\','/'),'collection':selected.name,
            'self_contained_rig_and_controls':True,'mesh_objects':sum(o.type=='MESH' for o in selected.objects)}


def deliver(source,out,render):
    assert out.parent.resolve()==MODEL_ROOT.resolve(),out
    assert not out.exists(),'Новая выдача должна находиться в новой папке'
    verification=json.loads((source.parent/'verification/wardrobe_verification.json').read_text(encoding='utf-8'))
    assert verification['status']=='PASS'
    out.mkdir();(out/'Separate_Assets').mkdir();(out/'Previews').mkdir()
    bpy.ops.wm.open_mainfile(filepath=str(source));D.enable_layers()
    bpy.context.preferences.filepaths.save_version=0
    images=pack(out);control=bpy.data.objects['RING | Wardrobe Controls'];rig=bpy.data.objects['M02_New_Anatomical_Rig']
    control['Комплект']=1;control['Предмет']=0;control['Балаклава']=True;control['Вариант балаклавы']=0;control.update_tag();bpy.context.view_layer.update()
    rig.hide_set(True)
    G.activate(control);D.frame((0,-.02,.96),2.6)
    scene=bpy.context.scene;scene.camera=bpy.data.objects['Wardrobe_ThreeQuarter'];scene.render.filepath='//Previews/C01_threequarter.png'
    master=out/'RING_NPC_Wardrobe_M02_v01.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(master),check_existing=False,relative_remap=False)
    records=[]
    for item in verification['items']:
        code=item['id'];cfg=W.TOPS.get(code) or W.PANTS.get(code) or W.SHOES.get(code) or B.DESIGNS.get(code)
        title=cfg['title'] if cfg else 'Black leather work boot material variant'
        records.append(dict(item,title=title))
    assets=[]
    for record in records:
        assets.append(native_item_file(master,out,record,render));print('WARDROBE_DELIVER '+record['id'],flush=True)
    for png in source.parent.glob('*.png'): shutil.copy2(png,out/'Previews'/png.name)
    verification['file']=str(master)
    (out/'wardrobe_verification.json').write_text(json.dumps(verification,ensure_ascii=False,indent=2),encoding='utf-8')
    materials=ROOT/'_asset_src/npc_wardrobe/materials'
    shutil.copy2(materials/'sources.json',out/'phototexture_sources.json')
    licenses=out/'licenses';licenses.mkdir()
    shutil.copytree(G.SOURCE.parent/'licenses',licenses/'M02_character',dirs_exist_ok=True)
    shutil.copy2(G.SOURCE.parent/'sources_licenses.md',licenses/'M02_sources_licenses.md')
    shutil.copy2(materials/'license.txt',licenses/'Poly_Haven_CC0.txt')
    construction=out/'construction_scripts';construction.mkdir()
    for name in ['m02_custom_clothes.py','m02_custom_clothes_deliver.py','m02_custom_clothes_verify.py','wardrobe_geometry.py','wardrobe_sources.py','npc_wardrobe.py','wardrobe_materials.py','wardrobe_polish.py','wardrobe_balaclavas.py','wardrobe_finish.py','wardrobe_clearance.py','wardrobe_package_prepare.py','wardrobe_verify.py','wardrobe_deliver.py','wardrobe_delivery_verify.py']:
        shutil.copy2(ROOT/'tools/characters'/name,construction/name)
    manifest={'file':str(master),'source':str(G.SOURCE),'source_sha256':verification['source_sha256'],
              'base_clothes':14,'balaclavas':6,'boot_material_variants':1,'items':records,'separate_assets':assets,'images':images,
              'outfits':{str(k):list(v)+['B%02d'%k] for k,v in N.OUTFITS.items()},'blender':bpy.app.version_string,'ucupaint':'2.4.9'}
    (out/'wardrobe_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    (out/'00_НАЧНИ_ЗДЕСЬ.txt').write_text('''RING — одежда и балаклавы NPC, M02, v01

Открыть RING_NPC_Wardrobe_M02_v01.blend в Blender 5.2.2 LTS.
Это редактируемая библиотека исходников для художественной оценки.
14 базовых вещей + чёрный вариант рабочих ботинок + 6 балаклав.

В Outliner выбрать RING | Wardrobe Controls, Object Properties → Custom Properties:
Комплект: 1 повседневный; 2 рабочий; 3 ветровка; 4 спортивный;
         5 облегчённая форма ЧВК; 6 полевая форма ЧВК.
Балаклава: включить / снять, волосы возвращаются автоматически.
Вариант балаклавы: 0 следует комплекту; 1–6 — любой вариант с любой одеждой.
Предмет: 0 полный комплект; номера отдельных вещей — в wardrobe_manifest.json.

Все вещи, карманы, швы и фурнитура — отдельные редактируемые сетки.
Separate_Assets содержит 21 самостоятельный .blend с ригом и контроллером.
Для смены одежды на одном персонаже перенести меши нужной вещи и назначить
им существующий M02_New_Anatomical_Rig в Armature modifier и Parent.
Скелет из отдельного ассета можно использовать для самостоятельной примерки.
Не объединять автоматически несколько вложенных скелетов.

Геометрия ткани имеет сохранённый раскрой и отдельную форму драпировки;
Subdivision и Solidify редактируются. Веса — предварительные, общие для M02.
Материалы — настоящие слои UCUPaint 2.4.9: исходные цвета/рисунок, CC0-фото
волокон и кожи, микрорельеф, шероховатость и локальное истирание.
UV_Fabric_Metres хранит масштаб ткани в метрах. Это исходная развёртка
для материалов, не финальный игровой атлас.

Тело, его топология, UV и все формы исходного M02 сохранены. Анатомия под
вещами скрыта обратимой маской. Балаклавы не вырезают лицо из тела.
Previews — реальные рендеры Blender. Фотографии также собраны в ZIP.
Изображения упакованы в .blend, копии лежат в textures с относительными путями.
Лицензии и источники — в licenses и phototexture_sources.json.

Это новая библиотека по шести концептам, ещё ожидает художественной оценки.
Посадка рассчитана на M02; другие тела потребуют подгонки.
Полная проверка анимаций, игровые сетки, bake, LOD и импорт в Godot — отдельно.
''',encoding='utf-8-sig')
    (out/'asset-state.md').write_text('''# Состояние библиотеки

- Этап: редактируемые исходники формы и материалов по шести концептам; кандидат на оценку владельца.
- Состав: 14 предметов одежды, 1 материальный вариант обуви, 6 балаклав; шесть сочетаний.
- Проверено: повторное открытие, исходная анатомия и формы M02, UV, слои UCUPaint,
  упаковка изображений, переключатели, нормализованные веса, статичные сгибы и поворот головы.
- Не выполнены и не подразумеваются: посадка на другие тела, полный анимационный прогон,
  игровая оптимизация, финальные атласы, LOD, bake, экспорт и импорт в движок.
- Готовые сетки одежды из внешних наборов не использованы.
- Сканы материалов Poly Haven — CC0; происхождение анатомии M02 записано отдельно в licenses.
''',encoding='utf-8')
    archive=out/'RING_NPC_Wardrobe_Photos_v01.zip'
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for file in sorted((out/'Previews').glob('*.png')): z.write(file,'Previews/'+file.name)
    checks={str(p.relative_to(out)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in out.rglob('*') if p.is_file()}
    (out/'SHA256.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8')
    print('WARDROBE_DELIVERY_PASS '+str(master),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('source',type=Path);parser.add_argument('output',type=Path);parser.add_argument('--render-assets',action='store_true')
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:]);deliver(args.source.resolve(),args.output.resolve(),args.render_assets)
