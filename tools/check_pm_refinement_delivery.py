"""Reopen the three review assets; verify scale, dependencies and provenance."""
from pathlib import Path
import argparse, hashlib, json, math, sys
import bpy, numpy as np

ap=argparse.ArgumentParser();ap.add_argument('--folder',default='');ap.add_argument('--out',default='');ap.add_argument('--revision',default='v06',choices=['v06','v07','v08','v09','v10','v11']);args=ap.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
PROJECT=Path(__file__).resolve().parents[1];STAGE=PROJECT/('_asset_src/pm_refinement/review_'+args.revision)
accessory_revision={'v06':'v01','v07':'v02','v08':'v03','v09':'v04','v10':'v05','v11':'v06'}[args.revision]
folder=Path(args.folder) if args.folder else STAGE
if args.revision in {'v09','v10','v11'}:
    import addon_utils
    bpy.context.preferences.use_preferences_save=False
    addon_utils.enable('bl_ext.blender_org.ucupaint',default_set=True)
qa=json.loads((STAGE/'Проверки/fresh_file_geometry.json').read_text(encoding='utf-8'))
revision=json.loads((STAGE/'Проверки/revision_manifest.json').read_text(encoding='utf-8'))
rows=[]
def within(o,root):
    while o:
        if o==root:return True
        o=o.parent
    return False
for sub,name,rootname,key in [('01_ПМ',f'PM_Geometry_{args.revision}.blend','PM_CONTROLS • select me','assembly_closed'),('02_Крепление',f'PM_OpticMount_Geometry_{accessory_revision}.blend','PM_OpticMount • asset root','mount'),('03_Коллиматор',f'PM_ReflexSight_Geometry_{accessory_revision}.blend','PM_ReflexSight • asset root','optic')]:
    path=folder/sub/name;bpy.ops.wm.open_mainfile(filepath=str(path))
    S=bpy.context.scene;S.frame_set(1);bpy.context.view_layer.update();root=bpy.data.objects[rootname]
    objects=[o for o in bpy.data.objects if within(o,root) and o.type in {'MESH','CURVE','FONT'} and not o.get('PM engraving helper') and not o.get('PM geometry helper')]
    if key=='assembly_closed':
        suppressor=bpy.data.objects['Suppressor • removal']
        props=[o for o in bpy.data.objects if o.type=='EMPTY' and o.name.startswith('Animation |')]
        objects=[o for o in objects if not within(o,suppressor) and not any(within(o,p) for p in props) and not o.name.startswith(('Animation','Reference','Safety wear'))]
    low=np.array([math.inf]*3);high=-low.copy();dg=bpy.context.evaluated_depsgraph_get()
    for o in objects:
        eo=o.evaluated_get(dg);me=eo.to_mesh()
        if me and me.vertices:
            v=np.empty(len(me.vertices)*3,dtype=np.float32);me.vertices.foreach_get('co',v);v=v.reshape(-1,3)
            matrix=np.asarray(eo.matrix_world,dtype=np.float32);v=v@matrix[:3,:3].T+matrix[:3,3]
            low=np.minimum(low,v.min(axis=0));high=np.maximum(high,v.max(axis=0))
        eo.to_mesh_clear()
    dimensions=((high-low)*1000).tolist();expected=qa[key]['dimensions_mm']
    external=[i.filepath for i in bpy.data.images if i.source=='FILE' and i.users>0 and not i.packed_file]
    row=dict(file=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),dimensions_mm=dimensions,
        expected_mm=expected,scale_pass=max(abs(a-b) for a,b in zip(dimensions,expected))<.001,
        external_images=external,external_fonts=[f.filepath for f in bpy.data.fonts if f.users>0 and f.filepath!='<builtin>' and not f.packed_file],resources_pass=not external,objects=len(objects),root_parent=root.parent.name if root.parent else None,
        actions=[a.name for a in bpy.data.actions],camera=S.camera.name if S.camera else None)
    if key=='assembly_closed':row['file_hash_pass']=row['sha256']==qa['sha256']
    else:row['independent_pass']=root.parent is None and all(o.name.startswith(('Mount |',)) if key=='mount' else o.name.startswith(('Reflex |',)) for o in objects)
    if args.revision in {'v09','v10','v11'} and key!='mount':
        sys.path.insert(0,str(Path(__file__).resolve().parent))
        from pm_engraving_geometry import engraving_report,paint_fill_report
        row['engraving']=engraving_report(json.loads((STAGE/'Проверки/engraving.json').read_text(encoding='utf-8')),optic_only=key=='optic')
        if key=='assembly_closed':row['paint_fill']=paint_fill_report()
    row['pass']=row['scale_pass'] and row['resources_pass'] and not row['external_fonts'] and row.get('file_hash_pass',True) and row.get('independent_pass',True)
    if 'engraving' in row:row['pass']=row['pass'] and row['engraving']['pass_engraving']
    if 'paint_fill' in row:row['pass']=row['pass'] and row['paint_fill']['pass_paint']
    if args.revision in {'v10','v11'} and key=='assembly_closed':
        row['manual_controls_pass']=not root.animation_data or root.animation_data.action is None
        row['pass']=row['pass'] and row['manual_controls_pass']
    rows.append(row);print('PM_DELIVERY_FILE',name,row['pass'],dimensions,flush=True)
source=Path(revision['source']);source_pass=hashlib.sha256(source.read_bytes()).hexdigest()==revision['source_sha256']
parent_pass=not revision.get('parent_geometry') or hashlib.sha256(Path(revision['parent_geometry']).read_bytes()).hexdigest()==revision['parent_sha256']
report=dict(folder=str(folder),files=rows,source_unchanged=source_pass,parent_unchanged=parent_pass,pass_delivery=all(r['pass'] for r in rows) and source_pass and parent_pass)
out=Path(args.out) if args.out else STAGE/'Проверки/delivery_check.json';out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('PM_DELIVERY_PASS',report['pass_delivery'],flush=True)
if not report['pass_delivery']:raise RuntimeError('Saved delivery files failed verification')
