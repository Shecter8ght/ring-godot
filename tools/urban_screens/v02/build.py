"""Сохранение новых кандидатов отдельно от отклонённой партии v01."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import argparse
import hashlib
import json
import math
import time
import bpy
from mathutils import Vector
from common import k,ROOT,DELIVERY,start,studio
from generate import bounds,audit,camera_fit
import stationary


def fit(cam,low,high,direction):
    camera_fit(cam,low,high,direction)
    sc=bpy.context.scene
    # Blender задаёт ortho_scale по ширине; учесть отношение сторон кадра.
    cam.data.ortho_scale*=sc.render.resolution_x/sc.render.resolution_y

META={
 'building':dict(id='R06',name='Двухэтажный корпус с повреждённой штукатуркой',dimensions=[34.8,10.5,6.65],
   prototype='Три фотографии двухэтажного здания, предоставленные владельцем 2026-10-24',
   reference='building_user/ref_03.jpg',previous='новое дополнительное задание владельца',
   sources=['Фотографии владельца: references/building_user/ref_01.jpg, ref_02.jpg, ref_03.jpg'],
   confirmed='Два этажа, два входа с пониженными окнами лестничных клеток, белые оконные рамы, козырьки, наплывы, трещины и отслоения штукатурки под карнизом',
   estimated='34,8 × 10,5 м и высота, число крайних окон за обрезом кадра, задний/боковые фасады и объёмы внутри; дверные проёмы 1,82 × 2,42 м под масштаб E',
   resolution=[1800,1000],directions=[('front34',(1.3,-6,1.25)),('rear34',(-2.0,6,1.6)),('front',(0,-1,.001)),('right',(1,0,.001))]),
 'fence':dict(id='R01',name='Высокий секционный бетонный забор',dimensions=[2.5,.16,3.0],
   prototype='ПО-2М с фартуком, Гирейское ЗАО ЖБ; два стакана ФО-2',
   reference='fence/ref_01.jpg',previous='U11_02_site_fence',
   sources=['https://zaogbi.ru/catalog/po-2/plity-zabora-po-2/','https://gbifactory.ru/montazh-demontazh-panelej/','https://gbifactory.ru/product/stakan-opornyj-fo-2/'],
   confirmed='Высокий тип выбран владельцем; панель 2500 × 3000 × 160 мм, рельеф 5 × 4, фартук, задняя рама; стакан 950 × 750 × 550 мм',
   estimated='Глубина рельефа, внутренний размер стакана, размеры монтажных петель и высота установки над грунтом'),
 'atm':dict(id='R03',name='Банкомат с защищённой клавиатурой',dimensions=[.45,.784,1.412],
   prototype='NCR SelfServ 22e, CEN I front access, 2019 brochure',
   reference='atm/ref_01.jpg',previous='U16_01_atm',
   sources=['https://ncr.co.il/ncr-selfserv_22e/','https://ncr.co.il/wp-content/uploads/2020/11/NCR_Banking_22e_ds.pdf'],
   confirmed='Фронтальная форма, компоновка дисплея и органов управления; габарит из заводского PDF',
   estimated='Невидимые задняя крышка, глубина внутренних ниш и мелкие монтажные размеры'),
 'dumpster':dict(id='R02',name='Большой мусорный бункер 8 м³',dimensions=[3.3,1.9,1.42],
   prototype='РостМеталл 1408, открытый бункер БН 8 м³',
   reference='dumpster/ref_02.jpeg',previous='U11_03_dump_bed',
   sources=['https://rostmetall.ru/blagoustrojstvo-goroda/bunkery-nakopiteli/bn-8-m3.html'],
   confirmed='Габарит, наклонные нижние стенки, открытый верх, обвязка и видимые усиления',
   estimated='Точное расположение скрытых швов и сечение захватов; выбран вариант листа 3 мм из карточки'),
 'kiosk':dict(id='R05',name='Ларёк с фастфудом и маркизой',dimensions=[3.02,2.9,3.3],
   prototype='Стальной киоск Mobifood, фотография «Хот-Дог»',
   reference='kiosk/ref_08.jpg',previous='U05_02_coffee_kiosk',
   sources=['https://mobifood.com.ua/p1641339994-kiosk-zakaz-pavilon.html'],
   confirmed='Видимые пропорции, панельные стены, окно с фрамугой, маркиза, карниз и поднятый центр фриза',
   estimated='Габарит, задняя сторона и внутреннее оснащение; дверной проём 1,17 × 2,42 м по правилу E'),
 'car':dict(id='R04',name='Городской трёхдверный хэтчбек',dimensions=[1.759,4.204,1.485],
   prototype='Volkswagen Golf V 3-door standard, blue car, no GTI body parts',
   reference='car_official/ref_01.jpg',previous='U14_01_hatchback',
   sources=['https://www.volkswagen-newsroom.com/en/golf-5-20032008-19480','https://www.volkswagen-newsroom.com/en/vehicle-data-golf-5-profile-19481'],
   confirmed='Видимые детали синего трёхдверного автомобиля: front ref_01, rear ref_04; длина, ширина и база из таблицы семейства',
   estimated='Высота кузова 1,485 м выбрана внутри диапазона семейства, скрытое днище, внутренние крепления и второстепенные размеры; внешняя маркировка собственная'),
}


def reference_empty(a):
    path=ROOT/'references'/a['reference']
    if not path.exists(): return
    collection=bpy.data.collections.new('REFERENCES | photo, not export')
    bpy.context.scene.collection.children.link(collection)
    collection.hide_render=True; collection.hide_viewport=True
    im=bpy.data.images.load(str(path),check_existing=True)
    im.pack()
    ob=bpy.data.objects.new('Source photo | '+a['prototype'],None)
    collection.objects.link(ob)
    ob.empty_display_type='IMAGE'; ob.data=im
    ob.empty_display_size=2
    ob['source_url']=a['sources'][0]
    ob['usage']='Visual reference only, excluded from game export'


def run(key,fn,quick=False):
    a=META[key]
    folder=ROOT/'assets'/f"{a['id']}_{key}"
    for sub in ('model','previews','checks'): (folder/sub).mkdir(parents=True,exist_ok=True)
    path=folder/'model'/f"{a['id']}_{key}_geometry_v02.blend"
    start(); fn()
    parts=list(k.PARTS)
    low,high=bounds(parts)
    shift=Vector((-(low.x+high.x)/2,-(low.y+high.y)/2,-low.z))
    root=bpy.data.objects.new(a['id']+' | '+a['name'],None)
    k.COLLECTION.objects.link(root)
    # Сборки с собственными pivot перемещаются целиком, дочерние детали сохраняют локальную позу.
    for ob in list(k.COLLECTION.objects):
        if ob!=root and ob.parent is None:
            ob.location+=shift; ob.parent=root
    for field in ('id','name','prototype','confirmed','estimated','previous'):
        root[field]=a[field]
    root['geometry_approved']=False
    root['production_uv']=False; root['production_textures']=False
    root['units']='metres; front -Y; ground Z=0'
    reference_empty(a)
    low,high=bounds(parts)
    cam=studio(parts,low,high)
    if 'resolution' in a:
        bpy.context.scene.render.resolution_x,bpy.context.scene.render.resolution_y=a['resolution']
    fit(cam,low,high,(3.6,-6,2.9))
    bpy.context.scene['asset_version']='v02_real_reference_candidate'
    bpy.context.scene['stage']='Unapproved geometry, neutral diagnostic materials only'
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(path),compress=True)
    bpy.ops.wm.open_mainfile(filepath=str(path))
    parts=[o for o in bpy.data.collections['MODEL | editable components'].objects if o.type in ('MESH','CURVE','FONT')]
    report=audit(parts)
    report.update(id=a['id'],key=key,prototype=a['prototype'],
       saved_file_reopened=True,blend_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
       source_urls=a['sources'],confirmed=a['confirmed'],estimated=a['estimated'],
       nominal_dimensions_m=a['dimensions'],geometry_approved=False)
    (folder/'checks/geometry.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    low,high=bounds(parts)
    sc=bpy.context.scene
    main_engine=sc.render.engine
    for view,direction in a.get('directions',[('front34',(3.6,-6,2.9)),('rear34',(-3.6,6,2.8)),('front',(0,-1,.001)),('right',(1,0,.001))]):
        fit(sc.camera,low,high,direction)
        if quick or view in ('front','right'):
            sc.render.engine='BLENDER_WORKBENCH'
            sh=sc.display.shading; sh.light='STUDIO'; sh.color_type='MATERIAL'
            sh.show_cavity=True; sh.cavity_type='BOTH'; sh.show_shadows=True
            sc.world.color=(.22,.22,.22)
            sc.render.resolution_percentage=75
        else:
            sc.render.engine=main_engine
            sc.render.resolution_percentage=100
        sc.render.filepath=str(folder/'previews'/(view+'.png'))
        bpy.ops.render.render(write_still=True)
    note=f"""# {a['id']} — {a['name']}, v02

Новая геометрия по сохранённым интернет-фотографиям. Форма ещё не принята.
Файл для открытия в Blender: `model/{path.name}`.
Прежний кандидат `{a['previous']}` сохранён в партии v01.

Прототип: {a['prototype']}.
Фото в комплекте: `../../references/{a['reference']}`; первичный снимок также упакован в `.blend`
в скрытой коллекции `REFERENCES`, не предназначенной для игрового экспорта.

Подтверждено: {a['confirmed']}.
Оценка/реконструкция: {a['estimated']}.
Проектный габарит: {a['dimensions']} м. Измеренный evaluated-габарит: {report['dimensions_m']} м.
Origin в центре основания; метры, Z вверх, лицевой вид -Y.

Все детали редактируются в коллекции `MODEL | editable components`; студия — отдельно.
Материалы `REVIEW_*` только для проверки геометрии: нейтральные поверхности, прозрачное стекло,
разделение металла, резины и пластика. Производственные UV и текстурные слои не начинались.
Low-poly/LOD, коллизии и игровой экспорт не выполнялись.

Файл сохранён и повторно открыт; размеры и топология — `checks/geometry.json`.
Виды: `previews/front34.png`, `rear34.png`, `front.png`, `right.png`.
Нейтральные виды не являются подтверждением окончательного качества или принятия владельца.
SHA-256 `.blend`: `{report['blend_sha256']}`.

Источники:
"""
    note+='\n'.join('- '+url for url in a['sources'])+'\n'
    (folder/'asset-state.md').write_text(note,encoding='utf-8')
    print('REBUILD_OK',key,report['triangles'],report['zero_area_faces'],report['nonmanifold_edges'],report['dimensions_m'],flush=True)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--only',default='atm,dumpster,kiosk')
    parser.add_argument('--quick',action='store_true')
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    for key in args.only.split(','):
        if key=='car':
            from car import car
            fn=car
        elif key=='fence':
            from fence import fence
            fn=fence
        elif key=='building':
            from building import building
            fn=building
        else: fn=getattr(stationary,key)
        run(key,fn,args.quick)


if __name__=='__main__': main()
