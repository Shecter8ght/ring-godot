"""Крупные нейтральные виды фасада и повреждений из сохранённой модели."""
from pathlib import Path
import sys,json
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy
from mathutils import Vector
from common import ROOT
from building import FRONT

folder=ROOT/'assets/R06_building'
bpy.ops.wm.open_mainfile(filepath=str(folder/'model/R06_building_geometry_v02.blend'))
bpy.context.view_layer.update()
sc=bpy.context.scene
sc.render.engine='CYCLES'; sc.cycles.samples=32; sc.cycles.use_denoising=True
sc.render.resolution_x=1400; sc.render.resolution_y=1150; sc.render.resolution_percentage=100
for ob in bpy.data.collections['STUDIO | neutral lights, no export'].objects:
    if ob.type=='LIGHT': ob.data.energy*=.12
shift=bpy.data.objects['FACADE | continuous rippled plaster'].matrix_world.translation
cam=sc.camera; cam.data.type='ORTHO'
views=[('damage_close',(10.60,FRONT-.02,5.10),(1.0,-8,1.0),5.0),
       ('entry_close',(-7.8,FRONT-.02,3.1),(2.1,-8,1.05),5.4),
       ('plaster_close',(9.45,FRONT-.02,3.6),(.5,-8,.4),3.8)]
lamp_data=bpy.data.lights.new('Inspection raking light','AREA'); lamp_data.energy=200; lamp_data.size=2
lamp=bpy.data.objects.new('Inspection raking light',lamp_data); sc.collection.objects.link(lamp)
records=[]
for name,target,offset,scale in views:
    target=Vector(target)+shift
    cam.location=target+Vector(offset); cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler()
    cam.data.ortho_scale=scale
    lamp.location=target+Vector((-3,-2,1.0)); lamp.rotation_euler=(target-lamp.location).to_track_quat('-Z','Y').to_euler()
    sc.render.filepath=str(folder/'previews'/(name+'.png')); bpy.ops.render.render(write_still=True)
    records.append(dict(view=name,target_m=list(target),orthographic_width_m=scale,purpose='geometry and damage, neutral materials'))
(folder/'checks/inspection-views.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
print('BUILDING_CLOSEUPS_OK',flush=True)
