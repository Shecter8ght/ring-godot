"""Редактируемый маркировщик по фото OMTech Galvo: сначала превью, затем экспорт в игру.
Blender --background --factory-startup --python tools/build_engraver.py
Сырые GLB в _asset_src/engraver; этот инструмент сам не внедряет модель в уровень.
"""
from pathlib import Path
import math
import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '_asset_src/engraver'
OUT.mkdir(parents=True, exist_ok=True)
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

def material(name, color, metal, rough):
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*color, 1)
    m.use_nodes = True
    bs = m.node_tree.nodes.get('Principled BSDF')
    bs.inputs['Base Color'].default_value = (*color, 1)
    bs.inputs['Metallic'].default_value = metal
    bs.inputs['Roughness'].default_value = rough
    return m

paint = material('LP03 — серо-зелёная порошковая краска', (.15,.20,.18), 0, .65)
alum = material('Матовый обработанный алюминий', (.47,.49,.50), 1, .48)
steel = material('Винты, хромированные направляющие', (.3,.32,.34), 1, .28)
black = material('Чёрный анодированный алюминий', (.023,.026,.027), 1, .55)
rubber = material('Резина и изоляция', (.016,.019,.016), 0, .88)
green = material('Кнопка пуска', (.025,.26,.13), 0, .35)
red = material('Аварийная кнопка', (.40,.035,.015), 0, .4)
brass = material('Латунь разъёмов', (.4,.25,.06), 1, .4)
glass = material('Оптический картридж — защитное стекло', (.07,.12,.10), .15, .18)

parts = {'engraver_frame': [], 'engraver_controller': [], 'laser_head': [], 'fixed': []}
group = 'engraver_frame'

def finish(obj, name, mat, bevel=0):
    obj.name = name
    obj.data.materials.append(mat)
    if bevel:
        mod = obj.modifiers.new('Скруглённая кромка', 'BEVEL')
        mod.width = bevel
        mod.segments = 3
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.modifier_apply(modifier=mod.name)
    for polygon in obj.data.polygons:
        polygon.use_smooth = True
    mod = obj.modifiers.new('Взвешенные нормали', 'WEIGHTED_NORMAL')
    mod.keep_sharp = True
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=1.1, island_margin=.025)
    bpy.ops.object.mode_set(mode='OBJECT')
    parts[group].append(obj)
    return obj

def box(name, pos, size, mat, bevel=.002):
    bpy.ops.mesh.primitive_cube_add(size=1, location=pos)
    obj=bpy.context.object
    obj.scale=size
    return finish(obj,name,mat,bevel)

def cylinder(name, pos, radius, depth, mat, direction=(0,0,1), vertices=32):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=pos)
    obj=bpy.context.object
    obj.rotation_mode='QUATERNION'
    obj.rotation_quaternion=Vector((0,0,1)).rotation_difference(Vector(direction))
    return finish(obj,name,mat,.0006)

def screw(pos, direction=(0,0,1)):
    cap = cylinder('Винт M4 — шестигранник',pos,.0034,.0025,steel,direction,12)
    axis=Vector(direction)
    cylinder('Гнездо шестигранника', Vector(pos)+axis*.0014,.0016,.0002,black,direction,6)
    return cap

def cable(name, points, radius, mat):
    curve=bpy.data.curves.new(name,'CURVE')
    curve.dimensions='3D'
    curve.bevel_depth=radius
    curve.bevel_resolution=3
    poly=curve.splines.new('BEZIER')
    poly.bezier_points.add(len(points)-1)
    for p,co in zip(poly.bezier_points,points):
        p.co=co
        p.handle_left_type=p.handle_right_type='AUTO'
    obj=bpy.data.objects.new(name,curve)
    bpy.context.collection.objects.link(obj)
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active=obj
    bpy.ops.object.convert(target='MESH')
    return finish(obj,name,mat)

def label(name, text, pos, size, mat, rot=(math.pi/2,0,0)):
    bpy.ops.object.text_add(location=pos, rotation=rot)
    obj=bpy.context.object
    obj.data.body=text
    obj.data.size=size
    obj.data.extrude=.00002
    obj.data.align_x='CENTER'
    bpy.ops.object.convert(target='MESH')
    return finish(obj,name,mat)

# Координаты Blender: +Z вверх, передняя сторона -Y; столешница станка 400×450 мм.
base = box('Основание 400×450 мм',(0,0,.028),(.40,.45,.025),alum,.004)
for x in [-.17,.17]:
    for y in [-.195,.195]:
        cylinder('Резиновая опора',(x,y,.012),.015,.024,rubber)
for x in range(-6,7):
    for y in range(-6,5):
        cylinder('Резьбовое отверстие монтажной плиты',(x*.025,y*.025,.0408),.0022,.0006,black,vertices=12)
box('Башмак колонны',(0,.15,.056),(.16,.13,.028),alum)
for x in [-.065,.065]:
    for y in [.102,.198]: screw((x,y,.071))
box('Колонна с фрезерованными пазами',(0,.175,.40),(.075,.085,.66),alum,.003)
for x in [-.031,.031]:
    box('Паз стойки',(x,.130,.40),(.009,.001,.62),black,.0004)
    cylinder('Направляющая',(x,.123,.40),.0045,.61,steel)
box('Линейка фокусировки',(-.05,.123,.39),(.013,.001,.61),alum,.0003)
for k in range(61):
    box('Деление линейки',(-.05,.122,.095+k*.0095),(.009 if k%5==0 else .004,.0005,.00055),black,.0001)
box('Каретка Z',(0,.111,.555),(.105,.055,.10),alum)
box('Кронштейн консоли',(0,.062,.518),(.085,.09,.05),alum)
cylinder('Винт фокусировки',(0,.178,.752),.006,.055,steel)
cylinder('Маховик фокусировки',(0,.178,.785),.061,.015,black,vertices=64)
cylinder('Ручка маховика',(.043,.178,.816),.009,.05,black)
for x in [-.04,.04]:
    screw((x,.083,.58),(0,-1,0))

group='fixed'
box('Кожух источника на консоли',(0,.009,.571),(.135,.235,.105),paint,.009)
box('Торец консоли',(0,-.109,.571),(.143,.012,.116),alum,.004)
for x in [-.06,.06]:
    for z in [.525,.613]: screw((x,-.116,z),(0,-1,0))
for x in [-.068,.068]:
    for k in range(9): box('Ребро теплоотвода',(x,.002,.539+k*.007),(.003,.16,.002),black,.0004)
box('Корпус сканатора',(0,-.14,.565),(.15,.13,.11),alum,.007)
cylinder('Объектив сканатора',(0,-.14,.495),.043,.06,black)
cylinder('Рифлёное кольцо объектива',(0,-.14,.466),.046,.009,black)
for k in range(40):
    a=k*math.tau/40
    cylinder('Насечка кольца',(math.cos(a)*.045,-.14+math.sin(a)*.045,.466),.001,.009,alum,vertices=8)
label('Шильдик корпуса','LP-03',(0,-.206,.585),.012,black)
for x in [-.052,.052]:
    cylinder('Указатель фокуса',(x,-.153,.502),.004,.025,brass)

group='laser_head'
box('Сервисный оптический картридж',(0,-.14,.494),(.115,.085,.056),black,.004)
box('Крышка картриджа',(0,-.184,.494),(.12,.003,.059),alum,.002)
cylinder('Линза картриджа',(0,-.14,.46),.032,.006,glass)
for x in [-.048,.048]:
    for z in [.474,.514]: screw((x,-.187,z),(0,-1,0))
label('Маркировка картриджа','OPT / 03',(0,-.188,.491),.009,black)
for x in [-.04,.04]: cylinder('Контакт картриджа',(x,-.098,.492),.004,.009,brass,(0,1,0))

group='engraver_controller'
cx=.32
box('Блок управления',(cx,.04,.198),(.19,.32,.35),paint,.008)
box('Передняя панель',(cx,-.124,.198),(.197,.008,.352),alum,.004)
for x in [cx-.087,cx+.087]:
    for z in [.035,.354]: screw((x,-.13,z),(0,-1,0))
for z in range(16):
    for x in [-.043,.013]: box('Прорезь вентиляции',(cx+x,-.129,.07+z*.011),(.041,.001,.0035),black,.001)
for x,mat,name in [(cx-.052,black,'Питание'),(cx,green,'Головка'),(cx+.052,red,'Стоп')]:
    cylinder('Обойма кнопки '+name,(x,-.138,.309),.014,.012,steel,(0,-1,0))
    cylinder('Кнопка '+name,(x,-.145,.309),.011,.009,mat,(0,-1,0))
    label('Подпись '+name, {'Питание':'POWER','Головка':'SCAN','Стоп':'STOP'}[name], (x,-.131,.336),.005,black)
for y in [-.055,.13]:
    cable('Ручка переноски',[(cx-.06,y,.375),(cx-.055,y,.391),(cx+.055,y,.391),(cx+.06,y,.375)],.005,steel)
for x in [cx-.07,cx+.07]:
    for y in [-.09,.17]: cylinder('Опора блока',(x,y,.013),.012,.025,rubber)
label('Идентификатор блока','LP-03  /  CONTROL',(cx,-.13,.267),.007,black)

group='fixed'
cable('Оптоволоконный кабель',[(cx,.205,.25),(.24,.28,.4),(.17,.31,.61),(0,.15,.60)],.0045,rubber)
cable('Сигнальный кабель',[(cx,.205,.13),(.31,.32,.22),(.10,.33,.3),(.06,.18,.53)],.003,rubber)
cable('Сетевой шнур',[(cx,.19,.04),(.43,.2,.025),(.46,.15,.026),(.46,-.2,.02)],.003,rubber)
# Две регулируемые опоры для ствольной коробки на плите.
for x in [-.07,.07]:
    box('Опора ложемента',(x,-.055,.055),(.024,.12,.027),black)
    box('Накладка ложемента',(x,-.055,.071),(.026,.09,.007),rubber,.002)

all_parts=[o for objects in parts.values() for o in objects]

def export(name, objects, offset=Vector((0,0,0))):
    # Готовый GLB — один меш на материал; детали исходника остаются редактируемыми.
    buckets={}
    for source in objects:
        copy=source.copy()
        copy.data=source.data.copy()
        copy.location-=offset
        bpy.context.collection.objects.link(copy)
        buckets.setdefault(source.data.materials[0].name,[]).append(copy)
    joined=[]
    for mat, members in buckets.items():
        bpy.ops.object.select_all(action='DESELECT')
        for obj in members:obj.select_set(True)
        bpy.context.view_layer.objects.active=members[0]
        bpy.ops.object.join()
        obj=bpy.context.object
        obj.name=name+'_'+mat
        joined.append(obj)
    bpy.ops.object.select_all(action='DESELECT')
    for obj in joined:obj.select_set(True)
    bpy.ops.export_scene.gltf(filepath=str(OUT/(name+'.glb')),use_selection=True,export_format='GLB',export_yup=True)
    for obj in joined:bpy.data.objects.remove(obj,do_unlink=True)

export('engraver',all_parts)
for key in ['engraver_frame','engraver_controller','laser_head']:
    objects=parts[key]
    offset=Vector((cx,.04,0)) if key=='engraver_controller' else Vector((0,-.14,.46)) if key=='laser_head' else Vector((0,0,0))
    export(key,objects,offset)

# Превью до внедрения: редактируемый источник и студийный рендер.
scene=bpy.context.scene
scene.render.engine='CYCLES'
scene.cycles.samples=32
scene.cycles.use_denoising=True
scene.world.color=(.22,.22,.22)
for location,energy,size in [((1,-2,2),180,2),((-1,-.2,1.7),110,1.3),((0,2,2),190,1.5)]:
    bpy.ops.object.light_add(type='AREA', location=location)
    light=bpy.context.object
    light.data.energy=energy
    light.data.shape='DISK'
    light.data.size=size
    light.rotation_euler=(Vector((.12,0,.4))-light.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.object.camera_add(location=(1.22,-1.65,1.02))
camera=bpy.context.object
camera.rotation_euler=(Vector((.16,.02,.4))-camera.location).to_track_quat('-Z','Y').to_euler()
camera.data.type='ORTHO'
camera.data.ortho_scale=1.27
scene.camera=camera
scene.render.resolution_x=1200
scene.render.resolution_y=1000
scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG'
scene.render.filepath=str(ROOT/'docs/screens/engraver_asset_preview.png')
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'engraver.blend'))
bpy.ops.render.render(write_still=True)
print('engraver: source, separate modules, preview exported')
