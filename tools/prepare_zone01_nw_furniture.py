"""CC0 бытовая мебель: тот же импорт glTF → метры → производный GLB, что у убежища.

Сначала tools/fetch_polyhaven_models.py zone01_nw/external painted_wooden_cabinet wooden_crate_01 --res 2k
Потом Blender --background --factory-startup --python-exit-code 1 --python tools/prepare_zone01_nw_furniture.py
"""
from __future__ import annotations
import json
from pathlib import Path
import bpy
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'assets/zone01/nw'
SOURCE=ROOT/'_asset_src/zone01_nw/external'


def prepare(asset, name, limit):
    bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
    folder=SOURCE/asset
    bpy.ops.import_scene.gltf(filepath=str(folder/(asset+'.gltf')))
    objects=[o for o in bpy.context.scene.objects if o.type=='MESH']
    points=[o.matrix_world@Vector(v) for o in objects for v in o.bound_box]
    lo=Vector([min(p[i] for p in points) for i in range(3)])
    hi=Vector([max(p[i] for p in points) for i in range(3)])
    size=hi-lo
    # Только равномерный масштаб: пропорции настоящего предмета сохраняются.
    scale=min(limit[0]/size.x,limit[1]/size.z,limit[2]/size.y)
    offset=Vector(((lo.x+hi.x)/2,(lo.y+hi.y)/2,lo.z))
    total=sum(len(p.vertices)-2 for o in objects for p in o.data.polygons)
    matrices={obj:obj.matrix_world.copy() for obj in objects}
    for obj in objects:
        obj.data=obj.data.copy()
        matrix=matrices[obj]; obj.parent=None; obj.matrix_world.identity()
        for vertex in obj.data.vertices: vertex.co=(matrix@vertex.co-offset)*scale
        bpy.context.view_layer.objects.active=obj
        if total>16000:
            decimate=obj.modifiers.new('World furniture budget','DECIMATE'); decimate.ratio=16000/total
            bpy.ops.object.modifier_apply(modifier=decimate.name)
    for obj in list(bpy.context.scene.objects):
        if obj not in objects: bpy.data.objects.remove(obj,do_unlink=True)
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.wm.save_as_mainfile(filepath=str(folder/'game_v01.blend'))
    bpy.ops.export_scene.gltf(filepath=str(OUT/(name+'.glb')),export_format='GLB',
                              use_selection=True,export_yup=True,export_animations=False)
    size*=scale
    triangles=sum(len(p.vertices)-2 for o in objects for p in o.data.polygons)
    print('NW_FURNITURE',name,tuple(size),triangles,flush=True)
    return dict(external=True,source='https://polyhaven.com/a/'+asset,license='CC0 1.0',
                bounds_m=[round(size.x,4),round(size.z,4),round(size.y,4)],triangles=triangles,
                collisions=[dict(pos=[0,size.z/2,0],size=[size.x,size.z,size.y],yaw=0)])


def main():
    manifest={}
    for asset,name,limit in [('painted_wooden_cabinet','ph_cabinet',(1.05,1.92,.58)),
                              ('wooden_crate_01','ph_household_chest',(1.2,.72,.6))]:
        manifest[name]=prepare(asset,name,limit)
    (OUT/'furniture.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=1)+'\n',encoding='utf-8')


if __name__=='__main__': main()
