"""Геометрия → сохранение → повторное открытие → аудит → нейтральные виды."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import argparse
import hashlib
import importlib
import json
import math
import time
import bpy
import bmesh
from mathutils import Vector
import meshkit as k
from catalog import ROOT, assets


def bounds(objects):
    bpy.context.view_layer.update()
    dg=bpy.context.evaluated_depsgraph_get()
    pts=[ob.matrix_world@Vector(c) for ob in objects if ob.type in ('MESH','CURVE','FONT')
         for c in ob.evaluated_get(dg).bound_box]
    low=Vector(tuple(min(p[i] for p in pts) for i in range(3)))
    high=Vector(tuple(max(p[i] for p in pts) for i in range(3)))
    return low,high


def audit(objects):
    dg=bpy.context.evaluated_depsgraph_get()
    totals=dict(objects=len(objects),vertices=0,triangles=0,loose_vertices=0,
                zero_area_faces=0,nonmanifold_edges=0,boundary_edges=0)
    digest=hashlib.sha256()
    part_flags=[]
    for ob in sorted(objects,key=lambda x:x.name):
        if ob.type not in ('MESH','CURVE','FONT'): continue
        ev=ob.evaluated_get(dg)
        me=ev.to_mesh()
        me.calc_loop_triangles()
        totals['vertices']+=len(me.vertices)
        totals['triangles']+=len(me.loop_triangles)
        bm=bmesh.new(); bm.from_mesh(me)
        loose=sum(not v.link_edges for v in bm.verts)
        zero=sum(f.calc_area()<1e-12 for f in bm.faces)
        boundary=sum(e.is_boundary for e in bm.edges)
        overfull=sum(len(e.link_faces)>2 for e in bm.edges)
        totals['loose_vertices']+=loose
        totals['zero_area_faces']+=zero
        totals['boundary_edges']+=boundary
        totals['nonmanifold_edges']+=overfull
        if loose or zero or boundary or overfull:
            part_flags.append(dict(part=ob.name,type=ob.type,loose=loose,zero=zero,boundary=boundary,overfull=overfull))
        for v in me.vertices:
            pos=ob.matrix_world@v.co
            digest.update((','.join(f'{t:.6f}' for t in pos)+';').encode())
        digest.update(str([tuple(p.vertices) for p in me.polygons]).encode())
        bm.free(); ev.to_mesh_clear()
    low,high=bounds(objects)
    totals.update(dimensions_m=[round(x,5) for x in high-low],
                  bounds_min_m=[round(x,6) for x in low],bounds_max_m=[round(x,6) for x in high],
                  geometry_sha256=digest.hexdigest(),
                  production_uv=False,production_textures=False,
                  part_flags=part_flags,
                  visual_review='Individual neutral images; automated audit does not certify resemblance')
    return totals


def studio(low,high):
    sc=bpy.context.scene
    col=bpy.data.collections.new('STUDIO | exclude from export')
    sc.collection.children.link(col)
    camdata=bpy.data.cameras.new('Review_camera')
    cam=bpy.data.objects.new('Review_camera',camdata)
    col.objects.link(cam)
    sc.camera=cam
    sc.render.engine='BLENDER_WORKBENCH'
    sc.render.resolution_x=1000; sc.render.resolution_y=850
    sc.render.resolution_percentage=100
    sc.render.image_settings.file_format='PNG'
    sh=sc.display.shading
    sh.light='STUDIO'; sh.color_type='MATERIAL'
    sh.show_shadows=True; sh.show_cavity=True; sh.cavity_type='BOTH'
    sh.curvature_ridge_factor=1.15; sh.curvature_valley_factor=1.05
    sh.cavity_ridge_factor=1.1; sh.cavity_valley_factor=1.0
    sh.show_specular_highlight=True
    sh.background_type='WORLD'
    if not sc.world: sc.world=bpy.data.worlds.new('Neutral_world')
    sc.world.color=(.22,.22,.22)
    sc.view_settings.view_transform='Standard'
    sc.render.film_transparent=False
    sc.display.render_aa='16'
    return cam


def camera_fit(cam,low,high,direction):
    center=(low+high)/2
    vec=Vector(direction).normalized()
    distance=(high-low).length*2+2
    cam.location=center+vec*distance
    cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler()
    cam.data.type='ORTHO'
    bpy.context.view_layer.update()
    inv=cam.matrix_world.inverted()
    corners=[inv@Vector((x,y,z)) for x in (low.x,high.x) for y in (low.y,high.y) for z in (low.z,high.z)]
    width=max(v.x for v in corners)-min(v.x for v in corners)
    height=max(v.y for v in corners)-min(v.y for v in corners)
    aspect=bpy.context.scene.render.resolution_x/bpy.context.scene.render.resolution_y
    cam.data.ortho_scale=max(height,width/aspect)*1.19
    cam.data.clip_end=distance*5
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type=='VIEW_3D':
                space=area.spaces.active
                space.region_3d.view_location=center
                space.region_3d.view_distance=(high-low).length*1.5
                space.region_3d.view_rotation=cam.rotation_euler.to_quaternion()


def run_one(a,fn,render=True):
    start=time.time()
    folder=ROOT/'assets'/f"{a['id']}_{a['key']}"
    modeldir=folder/'model'; modeldir.mkdir(parents=True,exist_ok=True)
    checkdir=folder/'checks'; checkdir.mkdir(exist_ok=True)
    path=modeldir/f"{a['id']}_{a['key']}_geometry_v01.blend"
    k.initialize()
    fn()
    parts=list(k.PARTS)
    if not parts: raise RuntimeError(f"Empty asset {a['id']}")
    low,high=bounds(parts)
    # Основание — строго Z=0; центр в плане у origin. Сохраняем относительные стыки.
    offset=Vector((-(low.x+high.x)/2,-(low.y+high.y)/2,-low.z))
    for ob in parts: ob.location+=offset
    root=bpy.data.objects.new(a['id']+' | '+a['name'],None)
    k.COLLECTION.objects.link(root)
    for ob in parts:
        ob.parent=root
    for key in ('id','key','name','source','construction','finish_target','dimension_basis','axis'):
        root[key]=a[key]
    root['stage']='geometry_v01_candidate_not_approved'
    root['geometry_approved']=False
    root['production_uv']=False
    low,high=bounds(parts)
    cam=studio(low,high)
    camera_fit(cam,low,high,(4,-6,3.7))
    bpy.context.scene['asset_id']=a['id']
    bpy.context.scene['source_reference']='../../../'+a['source']
    bpy.context.scene['stage']='Geometry review; no production UV or textures'
    bpy.context.scene.tool_settings.statvis.type='OVERHANG'
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(path),compress=True)
    # Аудит актуального файла после повторного открытия, а не памяти генератора.
    bpy.ops.wm.open_mainfile(filepath=str(path))
    parts=[o for o in bpy.data.collections['MODEL | editable components'].objects if o.type!='EMPTY']
    report=audit(parts)
    report['blend_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
    report['saved_file_reopened']=True
    report['planned_dimensions_m']=a['planned_dimensions_m']
    (checkdir/'geometry.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    low,high=bounds(parts)
    if render:
        previews=folder/'previews'; previews.mkdir(exist_ok=True)
        for view,direction in [('front34',(4,-6,3.7)),('rear34',(-4,6,3.5)),('front',(0,-1,.06)),('right',(1,0,.06))]:
            camera_fit(bpy.context.scene.camera,low,high,direction)
            bpy.context.scene.render.filepath=str(previews/(view+'.png'))
            bpy.ops.render.render(write_still=True)
    state=f"""# {a['id']} — {a['name']}

Стадия: **геометрический кандидат v01; ещё не принят**.
Модель: `model/{path.name}`. Редактируемая сборка, коллекция `MODEL | editable components`.
Студия и камера находятся в отдельной коллекции; это не часть модели.

Источник: `../../{a['source']}` — кадр {a['screenshot']:02d} владельца.
Подтверждены общая форма и видимые детали; скрытые стороны реконструированы.
Размеры — оценка по кадру, а не обмер. Оси: {a['axis']}.
Измеренный evaluated-габарит: {' × '.join(str(v) for v in report['dimensions_m'])} м.
Origin — центр основания, низ геометрии Z=0. Самостоятельные части редактируются отдельно.

Конструкция: {a['construction']}.
Будущая отделка: {a['finish_target']}.
Материалы SLOT_* — только нейтральные диагностические слоты. Производственные UV и текстуры не начаты.
Геометрия и сторонние текстуры из игры не извлекались. Маркировки — авторские.

Проверки: файл сохранён и повторно открыт; `checks/geometry.json` — габарит, треугольники,
SHA-256, свободные вершины, нулевые грани и рёбра. Раздельные соприкасающиеся детали допустимы.
Изображения: `previews/front34.png`, `rear34.png`, `front.png`, `right.png` — нейтральный свет.
Скриптовый аудит не является подтверждением художественного качества или принятия владельцем.

Следующий этап: просмотр и принятие формы владельцем, затем UCUPaint/PBR;
игровая сетка, LOD и коллизии готовятся после принятия отдельно.
SHA-256 файла: `{report['blend_sha256']}`.
"""
    (folder/'asset-state.md').write_text(state,encoding='utf-8')
    print('ASSET_OK',a['id'],a['key'],report['triangles'],f'{time.time()-start:.1f}s',flush=True)
    return dict(id=a['id'],key=a['key'],blend=str(path),**report)


def main():
    args=argparse.ArgumentParser()
    args.add_argument('--ids',default='all')
    args.add_argument('--no-render',action='store_true')
    args.add_argument('--resume',action='store_true')
    opts=args.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    registry={}
    for module in ('street','architecture','interiors','extras'):
        try: registry.update(importlib.import_module(module).REGISTRY)
        except ModuleNotFoundError as error:
            if error.name!=module: raise
    targets=assets()
    if opts.ids!='all':
        ids=opts.ids.split(',')
        targets=[a for a in targets if a['id'] in ids or f"{a['screenshot']:02d}" in ids or a['key'] in ids]
    for a in targets:
        if a['key'] not in registry: raise RuntimeError(f"Missing recipe: {a['key']}")
    reports=[]
    for a in targets:
        folder=ROOT/'assets'/f"{a['id']}_{a['key']}"
        if opts.resume and (folder/'asset-state.md').exists():
            print('SKIP_EXISTING',a['id'],flush=True); continue
        reports.append(run_one(a,registry[a['key']],not opts.no_render))
    out=ROOT/'checks'; out.mkdir(exist_ok=True)
    (out/('run_'+time.strftime('%H%M%S')+'.json')).write_text(json.dumps(reports,ensure_ascii=False,indent=2),encoding='utf-8')
    print('RUN_OK',len(reports),flush=True)


if __name__=='__main__': main()
