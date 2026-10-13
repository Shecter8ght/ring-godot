"""Проверка повторно открытого файла: геометрия, входы UCUPaint, карты и визуальный риг."""
import bpy,hashlib,json,sys,importlib.util,math
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'_asset_src/grenade_codex/texture_v08'
def module(name,path):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
T=module('v08_material_author',ROOT/'tools/texture_grenade_cast_v08.py')
R=module('v07_geo_checks',ROOT/'tools/round_grenade_codex_body.py')
FILE=Path(sys.argv[sys.argv.index('--')+1]) if '--' in sys.argv else T.MASTER
approval=json.loads((OUT/'checks/geometry_approved_v07.json').read_text(encoding='utf-8-sig'));assert T.sha(T.SOURCE)==approval['sha256'];T.P.native();bpy.ops.wm.open_mainfile(filepath=str(T.SOURCE));bpy.context.scene.frame_set(1);bpy.context.view_layer.update();before=R.snapshot()
def rig():
    data={}
    for ob in bpy.context.scene.objects:
        if ob.name.startswith('CTRL_'):
            anim=ob.animation_data
            data[ob.name]={'props':{k:float(ob[k]) for k in ['pin_pull','lever_open'] if k in ob},'drivers':[(fc.data_path,fc.array_index,fc.driver.expression,[(v.name,v.targets[0].id.name,v.targets[0].data_path) for v in fc.driver.variables]) for fc in (anim.drivers if anim else [])]}
    return data
rig_before=rig();archive=R.digest_mesh(bpy.data.meshes['ARCHIVE • Body v05 with original UV'])
bpy.ops.wm.open_mainfile(filepath=str(FILE));scene=bpy.context.scene;scene.frame_set(1);bpy.context.view_layer.update()
after=R.snapshot();assert after==before,'Approved object geometry/hierarchy/shape keys changed'
assert rig()==rig_before,'Root properties or controller drivers changed'
assert R.digest_mesh(bpy.data.meshes['ARCHIVE • Body v05 with original UV'])==archive
images=[]
for im in bpy.data.images:
    if im.type in {'RENDER_RESULT','COMPOSITING'}:continue
    assert im.packed_file,im.name
    path=Path(bpy.path.abspath(im.filepath));assert path.is_file(),str(path)
    h=hashlib.sha256(bytes(im.packed_file.data)).hexdigest();assert h==T.sha(path),im.name
    if any(x in path.name for x in ['relief','grains','breaks','Roughness','Metalness','scratches','neck_','seal_','slnshk']):assert im.colorspace_settings.name=='Non-Color',im.name
    images.append({'name':im.name,'sha256':h,'file':im.filepath,'color_space':im.colorspace_settings.name})
checks=[];trees=[n for n in bpy.data.node_groups if getattr(n,'yp',None) and n.yp.is_ypaint_node]
assert len(trees)==4,len(trees)
for tree in trees:
    assert [c.name for c in tree.yp.channels]==['Color','Metallic','Roughness','Normal']
    for layer in tree.yp.layers:
        actual=T.P.U.common.get_entity_prop_value(layer,'intensity_value')
        assert math.isclose(layer.intensity_value,actual,abs_tol=1e-6),layer.name
        for root,ch in zip(tree.yp.channels,layer.channels):
            if not ch.enable:continue
            if ch.override:
                prop='override_color' if root.type=='RGB' else 'override_value'
                rna=getattr(ch,prop);socket=T.P.U.common.get_entity_prop_value(ch,prop)
                if root.type=='RGB':assert np.allclose(list(rna),list(socket)[:3],atol=1e-6)
                else:assert math.isclose(rna,socket,abs_tol=1e-6)
            if root.type=='NORMAL':assert math.isclose(ch.bump_distance,T.P.U.common.get_entity_prop_value(ch,'bump_distance'),abs_tol=1e-8),layer.name
        for mask in layer.masks:
            if mask.type=='NOISE':
                assert all(m.type!='MODIFIER' for m in mask.modifiers)
            if mask.type=='VCOL':
                source=T.P.U.common.get_mask_tree(mask).nodes[mask.source];attribute_name=source.attribute_name;att=next((a for ob in scene.objects if ob.type=='MESH' for a in ob.data.color_attributes if a.name==attribute_name),None)
                assert att is not None,attribute_name
        checks.append({'tree':tree.name,'layer':layer.name,'type':layer.type,'masks':[(m.name,m.type) for m in layer.masks]})
poses=[]
body=R.world_tree('GrenadeBody')
for frame in [1,17,25,30,36,45,54,59,65,75,83,90,96]:
    scene.frame_set(frame);bpy.context.view_layer.update();root=bpy.data.objects['CTRL_Grenade'];p=float(root['pin_pull']);l=float(root['lever_open'])
    expected=-.0006*min(1,p/.16)-.0514*max(0,(p-.16)/.84)
    assert abs(bpy.data.objects['CTRL_PinAssembly'].location.y-expected)<1e-6
    angle=-1.18682389*l*min(1,max(0,(p-.65)/.35));assert abs(bpy.data.objects['CTRL_LeverPose'].rotation_euler.y-angle)<1e-6
    assert not body.overlap(R.world_tree('SafetyLever'))
    poses.append({'frame':frame,'pin':p,'lever':l})
scene.frame_set(1);bpy.context.view_layer.update()
report={'pass':True,'file':str(FILE),'sha256':T.sha(FILE),'source':str(T.SOURCE),'source_sha256':T.sha(T.SOURCE),'unchanged_meshes':after,'native_layers':len(checks),'native_stacks':len(trees),'socket_checks':True,'images':images,'visual_poses':poses,'checks':checks}
name=('delivered_studio_audit.json' if 'Studio' in FILE.name else 'delivered_audit.json') if 'Models Blender' in str(FILE) else ('studio_material_audit.json' if 'Studio' in FILE.name else 'material_audit.json')
(OUT/'checks'/name).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
print('V08_AUDIT_PASS',len(checks),len(images),FILE,flush=True)



