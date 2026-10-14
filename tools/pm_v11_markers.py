import bpy, json
import numpy as np
from pathlib import Path
bpy.ops.wm.open_mainfile(filepath='E:/Models Blender/WEAPONS/ПМ — модели и текстуры/17_Текстуры_v4_20_на_проверку/01_ПМ/PM_Textures_20_v04.blend')
S=bpy.context.scene; S.frame_set(1)
rig=bpy.data.objects['PM_CONTROLS • select me']
for k in ('Slide','Hammer','Trigger','Safety','Magazine','MagCatch','SlideStop','Suppressor'):
    if k in rig.keys(): rig[k]=0.0
rig.update_tag(); bpy.context.view_layer.update(); dg=bpy.context.evaluated_depsgraph_get()
def pts(name):
    o=bpy.data.objects[name]; eo=o.evaluated_get(dg); me=eo.to_mesh(); mw=np.array(eo.matrix_world)
    co=np.empty(len(me.vertices)*3); me.vertices.foreach_get('co',co); eo.to_mesh_clear()
    return co.reshape(-1,3)@mw[:3,:3].T+mw[:3,3]
f=pts('Front sight | low rounded post'); r=pts('Rear sight | beveled twin-ear blade'); m=pts('Muzzle | recessed steel rim'); b=pts('Barrel | stepped cylindrical chamber and open bore')
sup=[o.name for o in bpy.data.objects if o.name.startswith('Suppressor | eccentric front face')]
axis_y, axis_z = float(np.median(b[:,1])), float((b[:,2].min()+b[:,2].max())/2)
notch=r[np.abs(r[:,1])<0.0006]
out=dict(SightFront=[float(f[:,0].mean()), 0.0, float(f[:,2].max())],
         SightRear=[float(r[:,0].mean()), 0.0, float(notch[:,2].max()) if len(notch) else float(r[:,2].max())],
         Muzzle=[float(m[:,0].min()), axis_y, axis_z])
if sup:
    s=pts(sup[0]); out['MuzzleSuppressed']=[float(s[:,0].min()), axis_y, axis_z]
for k in ('Slide • translation','Hammer • pivot','Trigger • pivot','Safety • pivot','SlideStop • pivot','MagCatch • pivot'):
    out['pivot:'+k]=list(bpy.data.objects[k].matrix_world.translation)
Path('E:/Games/RING-godot/_asset_src/pm_game/lp/markers.json').write_text(json.dumps(out,indent=1))
print('MARKERS', {k:[round(x*1000,2) for x in v] for k,v in out.items()})
