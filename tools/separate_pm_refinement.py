"""Save mount and sight as independent editable Blender files, with exact scale."""
from pathlib import Path
import argparse, json, sys
import bpy
from mathutils import Vector

ap=argparse.ArgumentParser();ap.add_argument('--revision',default='v06',choices=['v06','v07','v08','v09','v10'])
args=ap.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
ROOT=Path(__file__).resolve().parents[1]/('_asset_src/pm_refinement/review_'+args.revision)
SOURCE=ROOT/f'01_ПМ/PM_Geometry_{args.revision}.blend'
accessory_revision={'v06':'v01','v07':'v02','v08':'v03','v09':'v04','v10':'v05'}[args.revision]
def desc(o,root):
    while o:
        if o==root:return True
        o=o.parent
    return False
report=[]
for name,folder,filename,exclude in [
 ('PM_OpticMount • asset root','02_Крепление',f'PM_OpticMount_Geometry_{accessory_revision}.blend','PM_ReflexSight • asset root'),
 ('PM_ReflexSight • asset root','03_Коллиматор',f'PM_ReflexSight_Geometry_{accessory_revision}.blend',None)]:
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
    S=bpy.context.scene;S.frame_set(1);bpy.context.view_layer.update()
    root=bpy.data.objects[name];omit=bpy.data.objects.get(exclude) if exclude else None
    keep=[o for o in bpy.data.objects if desc(o,root) and not(omit and desc(o,omit))]
    old_world=root.matrix_world.copy();root.parent=None;root.matrix_world=old_world
    root.location=(0,0,0)
    for o in list(bpy.data.objects):
        if o not in keep:bpy.data.objects.remove(o,do_unlink=True)
    bpy.data.orphans_purge(do_local_ids=True,do_linked_ids=True,do_recursive=True)
    bpy.context.view_layer.update()
    coords=[];dg=bpy.context.evaluated_depsgraph_get()
    for o in keep:
        if o.type not in {'MESH','CURVE','FONT'} or o.get('PM engraving helper') or o.get('PM geometry helper'):continue
        eo=o.evaluated_get(dg);me=eo.to_mesh();coords.extend(eo.matrix_world@v.co for v in me.vertices);eo.to_mesh_clear()
    low=Vector([min(p[i] for p in coords) for i in range(3)]);high=Vector([max(p[i] for p in coords) for i in range(3)])
    center=(low+high)/2;extent=max(high-low)
    collection=bpy.data.collections.new('Studio — separate');S.collection.children.link(collection)
    camera_data=bpy.data.cameras.new('Review');camera=bpy.data.objects.new('Review',camera_data);collection.objects.link(camera)
    camera.location=center+Vector((-extent*1.2,-extent*1.6,extent*1.1));camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler()
    camera_data.type='ORTHO';camera_data.ortho_scale=extent*(1.85 if args.revision in {'v08','v09','v10'} and name.startswith('PM_ReflexSight') else 1.45);camera_data.clip_start=.0001;camera_data.clip_end=10;S.camera=camera
    for i,(offset,power,size) in enumerate([((-1.0,-1.3,1.7),2.0,.12),((.8,.6,1.1),1.4,.10)]):
        data=bpy.data.lights.new('Review light '+str(i),'AREA');data.energy=power;data.size=size
        light=bpy.data.objects.new(data.name,data);collection.objects.link(light);light.location=center+Vector(offset)*extent
        light.rotation_euler=(center-light.location).to_track_quat('-Z','Y').to_euler()
    S.name=filename.removesuffix('.blend');S.frame_start=1;S.frame_end=1;S.render.resolution_x=1600;S.render.resolution_y=1100
    for marker in list(S.timeline_markers):S.timeline_markers.remove(marker)
    bpy.ops.object.select_all(action='DESELECT');root.hide_set(False);root.select_set(True);bpy.context.view_layer.objects.active=root
    target=ROOT/folder/filename;bpy.ops.wm.save_as_mainfile(filepath=str(target))
    report.append(dict(file=str(target),root=name,objects=[o.name for o in keep],dimensions_mm=[v*1000 for v in high-low],pivot='origin at mounting reference',external_images=[i.filepath for i in bpy.data.images if i.source=='FILE' and not i.packed_file]))
    print('PM_SEPARATE_SAVED',filename,len(keep),report[-1]['dimensions_mm'],flush=True)
(ROOT/'Проверки/separate_assets.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
