"""Свой служебный смартфон: редактируемая форма, без производственной UV и текстур.

Blender --background --factory-startup --python-exit-code 1 --python tools/quest_phone/build.py -- build|verify|render
Источник размеров корпуса: Apple iPhone 16 Pro Max; блок камер и мелкие размеры — авторская адаптация.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import bpy
import bmesh
from mathutils import Vector, Matrix

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / '_asset_src/quest_phone'
BLEND = OUT / 'models/QuestPhone_v02.blend'
W, H, D = .0776, .163, .00825
CAMERA_X, CAMERA_W, CAMERA_H = .018, .037, .039
CAMERA_GAP = W/2 - (CAMERA_X + CAMERA_W/2)
CAMERA_Y = H/2 - CAMERA_GAP - CAMERA_H/2
CAMERAS_DY = CAMERA_Y - .0535  # Весь блок выше на 6,2 мм: верхний отступ равен боковому.
COLS = {}
MATS = {}


def collection(name):
    col = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(col)
    COLS[name] = col
    return col


def material(name, color, metal=0., rough=.35):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1)
    mat.use_nodes = True
    node = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    node.inputs['Base Color'].default_value = (*color, 1)
    node.inputs['Metallic'].default_value = metal
    node.inputs['Roughness'].default_value = rough
    MATS[name] = mat
    return mat


def mesh(name, vertices, faces, col, mat=None, parent=True):
    data = bpy.data.meshes.new(name)
    data.from_pydata(vertices, [], faces)
    data.update()
    bm = bmesh.new()
    bm.from_mesh(data)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(data)
    bm.free()
    ob = bpy.data.objects.new(name, data)
    COLS[col].objects.link(ob)
    if parent:
        ob.parent = bpy.data.objects['QuestPhone']
    if mat:
        data.materials.append(MATS[mat])
    return ob


def outline(width, height, radius, steps=24):
    points = []
    for cx, cy, start in [(width/2-radius, height/2-radius, 0),
                          (-width/2+radius, height/2-radius, 90),
                          (-width/2+radius, -height/2+radius, 180),
                          (width/2-radius, -height/2+radius, 270)]:
        for j in range(steps+1):
            angle = math.radians(start + 90*j/steps)
            points.append((cx+radius*math.cos(angle), cy+radius*math.sin(angle)))
    return points


def rounded(name, width, height, radius, depth, col, mat=None, at=(0,0,0), rot=(0,0,0), bevel=0.):
    # Профиль по толщине создаёт реальные скругления, сохраняя плоскости стекла и рамки.
    bevel = min(bevel, depth*.48)
    levels = [(-depth/2, 0), (depth/2, 0)]
    if bevel:
        levels = []
        for i in range(7):
            a = (math.pi/2)*i/6
            levels.append((-depth/2 + bevel*(1-math.cos(a)), bevel*(1-math.sin(a))))
        for i in range(7):
            a = (math.pi/2)*i/6
            levels.append((depth/2 - bevel + bevel*math.sin(a), bevel*(1-math.cos(a))))
    n = len(outline(width, height, radius))
    verts = [(x,y,z) for z, inset in levels for x,y in outline(width-2*inset,height-2*inset,max(radius-inset,.00001))]
    faces = [tuple(reversed(range(n)))]
    faces.extend((k*n+j,k*n+(j+1)%n,(k+1)*n+(j+1)%n,(k+1)*n+j)
                 for k in range(len(levels)-1) for j in range(n))
    faces.append(tuple((len(levels)-1)*n+j for j in range(n)))
    ob = mesh(name, verts, faces, col, mat)
    ob.location = at
    ob.rotation_euler = rot
    for face in ob.data.polygons:
        face.use_smooth = len(face.vertices)==4
    return ob


def lathe(name, profile, col, mat, at=(0,0,0), rot=(0,0,0), n=128):
    # Замкнутый профиль (r,z): кольца имеют внутренние стенки и открытый центр.
    verts = [(r*math.cos(2*math.pi*j/n),r*math.sin(2*math.pi*j/n),z)
             for r,z in profile for j in range(n)]
    faces = [(i*n+j,i*n+(j+1)%n,((i+1)%len(profile))*n+(j+1)%n,((i+1)%len(profile))*n+j)
             for i in range(len(profile)) for j in range(n)]
    ob = mesh(name, verts, faces, col, mat)
    ob.location = at
    ob.rotation_euler = rot
    for p in ob.data.polygons:
        p.use_smooth = True
    return ob


def disk(name, radius, depth, col, mat=None, at=(0,0,0), rot=(0,0,0), n=96):
    verts = [(radius*math.cos(j*2*math.pi/n),radius*math.sin(j*2*math.pi/n),z)
             for z in [-depth/2,depth/2] for j in range(n)]
    faces = [tuple(reversed(range(n))),tuple(n+j for j in range(n))]
    faces += [(j,(j+1)%n,n+(j+1)%n,n+j) for j in range(n)]
    ob = mesh(name,verts,faces,col,mat)
    ob.location, ob.rotation_euler = at, rot
    for p in list(ob.data.polygons)[2:]:
        p.use_smooth = True
    return ob


def cut(target, cutter):
    mod = target.modifiers.new('Проём · '+cutter.name, 'BOOLEAN')
    mod.operation = 'DIFFERENCE'
    mod.solver = 'EXACT'
    mod.object = cutter
    cutter.hide_render = True
    cutter.hide_set(True)


def marker(name, at, rot=(0,0,0), size=.003):
    ob = bpy.data.objects.new(name,None)
    COLS['Экран'].objects.link(ob)
    ob.empty_display_type = 'ARROWS'
    ob.empty_display_size = size
    ob.location, ob.rotation_euler = at, rot
    ob.parent = bpy.data.objects['QuestPhone']
    return ob


def point_camera(cam, target, up=(0,1,0)):
    forward=(Vector(target)-cam.location).normalized()
    right=forward.cross(Vector(up)).normalized()
    real_up=right.cross(forward).normalized()
    cam.rotation_euler=Matrix((right,real_up,-forward)).transposed().to_euler()


def build():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    for name in ['Корпус','Экран','Камеры','Кнопки','Разъёмы','Резцы','Проверка']:
        collection(name)
    root = bpy.data.objects.new('QuestPhone',None)
    COLS['Корпус'].objects.link(root)
    root['stage'] = 'Форма v02; не принята, без текстур и игровой версии'
    root['camera_padding_mm'] = CAMERA_GAP*1000
    root['body_mm'] = '163 × 77.6 × 8.25; без выступов камер и кнопок'
    root['axes'] = 'X — ширина, Y — верх, +Z — экран; метры'
    root['owner_choice'] = '2026-11-04: iPhone Pro Max; постоянное оснащение, сохраняется после гибели'
    for name,color,metal,rough in [('Рамка',(0.42,.43,.45),.8,.3),('Задняя панель',(.32,.33,.35),0,.4),
                                  ('Стекло',(.025,.03,.038),0,.18),('Экран',(.075,.085,.10),0,.3),
                                  ('Полимер',(.035,.037,.04),0,.6),('Оптика',(.045,.055,.07),.15,.15),
                                  ('Внутри',(.012,.013,.015),0,.7),('Вспышка',(.65,.65,.61),0,.4),
                                  ('Контакты',(.46,.39,.25),.8,.35)]:
        material(name,color,metal,rough)
    frame = rounded('01 · Несущая рамка',W,H,.0125,.0078,'Корпус','Рамка',bevel=.00055)
    rounded('02 · Задняя панель',.07655,.16195,.0120,.0003,'Корпус','Задняя панель',at=(0,0,-.003975),bevel=.00008)
    glass = rounded('03 · Лицевое стекло и чёрная рамка',.07655,.16195,.0120,.0003,'Экран','Стекло',at=(0,0,.003975),bevel=.00008)
    points = outline(.0732,.1582,.0111,32)
    screen = mesh('DisplaySurface',[(x,y,.004126) for x,y in points],[tuple(range(len(points)))],'Экран','Экран')
    screen['purpose'] = 'Отдельная поверхность под живой экран (ViewportTexture). Открытая плоскость намеренно.'
    screen['active_diagonal_inches'] = math.hypot(.0732,.1582)/.0254
    # Рамка стекла и активный экран не перекрываются плоскостями: нет z-fighting и ложных теней.
    cutter=rounded('Резец · Активная область дисплея',.0732,.1582,.0111,.002,'Резцы',at=(0,0,.003975))
    cut(glass,cutter)
    rounded('04 · Остров фронтальных датчиков',.0205,.0056,.0028,.000002,'Экран','Внутри',at=(0,.068,.004128))
    disk('05 · Передняя камера',.00125,.000002,'Экран','Оптика',at=(.0068,.068,.004131))
    lens_marker=marker('CameraLensMarker',(.0095,.063+CAMERAS_DY,-.0073))
    lens_marker['forward_axis']='-Z: оптическая ось наружу через заднюю камеру'
    marker('ScreenMarker',(0,0,.004126))
    # Открытая прорезь разговорного динамика с утопленной решёткой.
    cutter = rounded('Резец · Динамик',.0135,.0006,.0003,.002,'Резцы',at=(0,.0798,.0038))
    cut(glass,cutter)
    cut(frame,cutter)
    rounded('06 · Подложка разговорного динамика',.0132,.0005,.00025,.0001,'Экран','Внутри',at=(0,.0798,.0031))
    for i in range(22):
        rounded(f'Динамик · Перемычка {i+1:02}',.00011,.00047,.00005,.00007,'Экран','Рамка',at=(-.0061+i*.00058,.0798,.00335))
    # Авторская адаптация блока: три отдельных корпуса с настоящими кольцевыми стенками.
    rounded('10 · Площадка камер',CAMERA_W,CAMERA_H,.0092,.0016,'Камеры','Задняя панель',at=(CAMERA_X,CAMERA_Y,-.0048),bevel=.00038)
    for label,x,y in [('Основная',.0095,.063),('Широкая',.0095,.045),('Телекамера',.0275,.054)]:
        y += CAMERAS_DY
        profile = [(.00655,-.0007),(.0076,-.0007),(.0080,-.00035),(.0080,.00075),
                   (.0077,.00095),(.00655,.00095)]
        lathe('11 · '+label+' · Обод',profile,'Камеры','Рамка',at=(x,y,-.00605),rot=(math.pi,0,0))
        disk('12 · '+label+' · Стекло',.0065,.00014,'Камеры','Стекло',at=(x,y,-.00689))
        lathe('13 · '+label+' · Оптический барабан',[(.0034,-.0002),(.0056,-.0002),(.0056,.0003),(.0034,.0003)],
              'Камеры','Внутри',at=(x,y,-.00655),rot=(math.pi,0,0))
        disk('14 · '+label+' · Внутренняя линза',.0033,.00012,'Камеры','Оптика',at=(x,y,-.00665))
    for name,r,x,y,mat in [('Вспышка',.0027,.028,.069,'Вспышка'),('Датчик глубины',.0026,.028,.038,'Стекло'),('Микрофон камер',.00062,.033,.044,'Внутри')]:
        disk('15 · '+name,r,.00018,'Камеры',mat,at=(x,y+CAMERAS_DY,-.0057))
    # Кнопки и углублённые посадочные места, а не плоские буквы/декали.
    buttons=[('Питание',1,.023,.0130,.0027),('Камера',1,-.039,.0108,.0027),
             ('Действие',-1,.050,.0069,.0026),('Громкость плюс',-1,.032,.0100,.0026),('Громкость минус',-1,.015,.0100,.0026)]
    for name,side,y,length,height in buttons:
        rot=(0,side*math.pi/2,0)
        cutter=rounded('Резец · '+name,height+.00035,length+.0004,(height+.00035)/2,.002,'Резцы',at=(side*.0385,y,0),rot=rot)
        cut(frame,cutter)
        rounded('20 · '+name,height,length,height/2,.00062,'Кнопки','Рамка',at=(side*.03887,y,0),rot=rot,bevel=.00012)
        rounded('21 · Уплотнение '+name,height+.00024,length+.00028,(height+.00024)/2,.0001,'Кнопки','Полимер',at=(side*.03836,y,0),rot=rot)
    # Полимерные вставки пересекают рамку в прорезанных посадочных каналах.
    for side in [-1,1]:
        for y in [-.063,.063]:
            cutter=rounded(f'Резец · Антенна {side} {y}',.0085,.0006,.00028,.0025,'Резцы',at=(side*.0386,y,0),rot=(0,math.pi/2,0))
            cut(frame,cutter)
            rounded(f'22 · Антенна {side} {y}',.0072,.00045,.00022,.0009,'Корпус','Полимер',at=(side*.03835,y,0),rot=(0,math.pi/2,0))
    # USB-C: открытый вход, внутренняя металлическая стенка, язык и контактные площадки.
    port_rot=(math.pi/2,0,0)
    cutter=rounded('Резец · USB-C',.0092,.0032,.00155,.005,'Резцы',at=(0,-.081,0),rot=port_rot)
    cut(frame,cutter)
    shell=rounded('30 · Корпус гнезда USB-C',.0090,.0030,.00145,.0027,'Разъёмы','Рамка',at=(0,-.0800,0),rot=port_rot)
    inside=rounded('Резец · Полость USB-C',.0080,.0022,.00105,.004,'Резцы',at=(0,-.0803,0),rot=port_rot)
    cut(shell,inside)
    rounded('31 · Дно гнезда USB-C',.0084,.0025,.0012,.00015,'Разъёмы','Внутри',at=(0,-.0785,0),rot=port_rot)
    rounded('32 · Язык USB-C',.0063,.00048,.0002,.0016,'Разъёмы','Полимер',at=(0,-.0798,0),rot=port_rot,bevel=.00007)
    for i in range(12):
        for side in [-1,1]:
            rounded(f'33 · USB-C контакт {side} {i+1:02}',.00023,.0011,.00007,.00004,'Разъёмы','Контакты',at=(-.00275+i*.0005,-.0798,side*.00026))
    for bank,xs in [('Динамик',[.011+i*.0028 for i in range(7)]),('Микрофон',[-.014-i*.0028 for i in range(5)])]:
        for i,x in enumerate(xs):
            cutter=disk(f'Резец · {bank} {i+1}',.00067,.0035,'Резцы',at=(x,-.081,0),rot=port_rot,n=48)
            cut(frame,cutter)
            disk(f'34 · {bank} · Дно {i+1}',.00062,.00008,'Разъёмы','Внутри',at=(x,-.0794,0),rot=port_rot,n=48)
    for x in [-.007,.007]:
        disk(f'35 · Винт {x}',.00075,.00012,'Разъёмы','Рамка',at=(x,-.08143,0),rot=port_rot,n=64)
        cutter=rounded(f'Резец · Шлиц {x}',.00075,.00018,.00007,.0003,'Резцы',at=(x,-.08145,0),rot=port_rot)
        cut(bpy.data.objects[f'35 · Винт {x}'],cutter)
    # Малые фаски только на свежих рёбрах прорезей рамки.
    mod=frame.modifiers.new('Кромки проёмов · 0.06 мм','BEVEL')
    mod.width=.00006
    mod.segments=3
    mod.limit_method='ANGLE'
    mod.angle_limit=math.radians(36)
    normal=frame.modifiers.new('Нормали плоскостей рамки','WEIGHTED_NORMAL')
    normal.keep_sharp=True
    normal.weight=50
    scene=bpy.context.scene
    scene.unit_settings.system='METRIC'
    scene.unit_settings.scale_length=1
    scene.render.engine='BLENDER_WORKBENCH'
    scene.display.shading.light='STUDIO'
    scene.display.shading.color_type='MATERIAL'
    scene.display.shading.show_cavity=True
    scene.display.shading.cavity_type='BOTH'
    scene.display.shading.curvature_ridge_factor=1.25
    scene.display.shading.curvature_valley_factor=1.0
    scene.display.shading.show_shadows=True
    scene.display.shading.show_specular_highlight=True
    scene.display.shading.background_type='WORLD'
    scene.world.color=(.13,.14,.16)
    scene.display.render_aa='16'
    scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG'
    scene.view_settings.view_transform='Standard'
    cam_data=bpy.data.cameras.new('Проверочная камера')
    cam=bpy.data.objects.new('Проверочная камера',cam_data)
    COLS['Проверка'].objects.link(cam)
    cam_data.type='ORTHO'
    cam_data.ortho_scale=.203
    cam.location=(.115,-.11,.30)
    point_camera(cam,(0,0,0))
    cam_data.clip_start=.001
    cam_data.clip_end=1.0
    scene.camera=cam
    bpy.ops.object.select_all(action='DESELECT')
    root.select_set(True)
    bpy.context.view_layer.objects.active=root
    for area in bpy.context.screen.areas:
        if area.type=='VIEW_3D':
            area.spaces.active.region_3d.view_distance=.235
            area.spaces.active.region_3d.view_rotation=cam.rotation_euler.to_quaternion()
            area.spaces.active.region_3d.view_location=(0,0,0)
            area.spaces.active.clip_start=.001
    BLEND.parent.mkdir(parents=True,exist_ok=True)
    bpy.data.orphans_purge(do_recursive=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND))
    print('SAVED',BLEND)


def verify():
    bpy.context.view_layer.update()
    deps=bpy.context.evaluated_depsgraph_get()
    report={'body_nominal_mm':[W*1000,H*1000,D*1000], 'objects':[], 'issues':[]}
    all_points=[]
    for ob in bpy.data.objects:
        if ob.type!='MESH' or ob.hide_render:
            continue
        ev=ob.evaluated_get(deps)
        data=ev.to_mesh()
        bm=bmesh.new();bm.from_mesh(data)
        boundary=sum(e.is_boundary for e in bm.edges)
        bad=sum(not e.is_manifold for e in bm.edges)
        expected_open=ob.name=='DisplaySurface'
        if bad and not expected_open:
            report['issues'].append(f'{ob.name}: non-manifold {bad}')
        if not data.vertices:
            report['issues'].append(f'{ob.name}: empty')
        all_points.extend(ev.matrix_world@v.co for v in data.vertices)
        report['objects'].append({'name':ob.name,'verts':len(data.vertices),'faces':len(data.polygons),'boundary':boundary,'non_manifold':bad,'open_expected':expected_open})
        bm.free();ev.to_mesh_clear()
    lo=Vector(tuple(min(p[i] for p in all_points) for i in range(3)))
    hi=Vector(tuple(max(p[i] for p in all_points) for i in range(3)))
    report['assembly_bounds_mm']=[round(v*1000,4) for v in hi-lo]
    body_points=[]
    for name in ['01 · Несущая рамка','02 · Задняя панель','03 · Лицевое стекло и чёрная рамка']:
        ob=bpy.data.objects[name].evaluated_get(deps)
        data=ob.to_mesh()
        body_points.extend(ob.matrix_world@v.co for v in data.vertices)
        ob.to_mesh_clear()
    body_size=[max(p[i] for p in body_points)-min(p[i] for p in body_points) for i in range(3)]
    report['body_measured_mm']=[round(v*1000,4) for v in body_size]
    if any(abs(actual-expected)>.00002 for actual,expected in zip(body_size,[W,H,D])):
        report['issues'].append('Body dimensions outside 0.02 mm tolerance')
    plate=bpy.data.objects['10 · Площадка камер'].evaluated_get(deps)
    data=plate.to_mesh()
    plate_points=[plate.matrix_world@v.co for v in data.vertices]
    plate.to_mesh_clear()
    side_gap=max(p.x for p in body_points)-max(p.x for p in plate_points)
    top_gap=max(p.y for p in body_points)-max(p.y for p in plate_points)
    report['camera_padding_mm']={'side':round(side_gap*1000,4),'top':round(top_gap*1000,4)}
    if 'camera_padding_mm' in bpy.data.objects['QuestPhone'] and abs(side_gap-top_gap)>.000001:
        report['issues'].append('Camera platform: top and side padding differ')
    report['screen_diagonal_inches']=round(bpy.data.objects['DisplaySurface']['active_diagonal_inches'],3)
    report['uv_layers_total']=sum(len(ob.data.uv_layers) for ob in bpy.data.objects if ob.type=='MESH')
    # Просвет настоящего входа USB-C: вне языка луч доходит внутрь, но не видит внешнюю крышку.
    frame=bpy.data.objects['01 · Несущая рамка'].evaluated_get(deps)
    hits=[]
    for x,z in [(-.002,.0008),(0,.0008),(.002,.0008),(-.003,-.0008),(.003,-.0008)]:
        hit,at,normal,index=frame.ray_cast(Vector((x,-.085,z)),Vector((0,1,0)))
        hits.append({'x':x,'z':z,'hit_y':float(at.y) if hit else None})
        if hit and at.y<-.079:
            report['issues'].append('USB-C: entrance blocked')
    report['usb_entrance_rays']=hits
    OUT.joinpath('checks').mkdir(parents=True,exist_ok=True)
    OUT.joinpath('checks/geometry.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('CHECK',len(report['objects']),'meshes; bounds mm',report['assembly_bounds_mm'],'issues',report['issues'])
    if report['issues']:
        raise RuntimeError('Geometry check failed')


def render(only=None):
    scene=bpy.context.scene
    cam=scene.camera
    shots=[('front',(.055,-.05,.30),(0,0,0),.198,1050,1250),
           ('back',(-.08,.055,-.30),(0,0,-.002),.198,1050,1250),
           ('bottom',(.028,-.12,.055),(0,-.072,0),.075,1400,800),
           ('camera_macro',(-.018,.078+CAMERAS_DY,-.12),(.018,.054+CAMERAS_DY,-.005),.062,1100,1000)]
    out=OUT/'previews';out.mkdir(parents=True,exist_ok=True)
    for name,eye,target,scale,w,h in shots:
        if only and name not in only:
            continue
        cam.location=eye
        point_camera(cam,target,up=(0,0,1) if name=='bottom' else (0,1,0))
        cam.data.ortho_scale=scale
        cam.data.clip_start=.001
        scene.render.resolution_x,scene.render.resolution_y=w,h
        version=Path(bpy.data.filepath).stem.rsplit('_',1)[-1]
        scene.render.filepath=str(out/f'quest_phone_{version}_{name}.png')
        bpy.ops.render.render(write_still=True)
        print('RENDER',name)


if __name__=='__main__':
    args=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else ['build']
    command=args[0]
    if command=='build':
        build()
        verify()
    else:
        bpy.ops.wm.open_mainfile(filepath=str(Path(args[1]) if len(args)>1 else BLEND))
        if command=='verify':verify()
        elif command=='render':render(only=args[2:])
        else:raise ValueError(command)
