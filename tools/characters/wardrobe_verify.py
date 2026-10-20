"""Переоткрытие выдачи: анатомия, слои, переключатели, веса и статичные сгибы."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import argparse,addon_utils,bpy,bmesh,hashlib,importlib,json,math
from mathutils import Vector
import m02_custom_clothes as G
import m02_custom_clothes_verify as V
import npc_wardrobe as N
import wardrobe_balaclavas as B


def anatomical_signature(obj):
    digest=hashlib.sha256()
    for v in obj.data.vertices: digest.update((','.join('%.8f'%x for x in v.co)+';').encode())
    for p in obj.data.polygons: digest.update(str(tuple(p.vertices)).encode())
    for uv in obj.data.uv_layers:
        digest.update(uv.name.encode())
        for d in uv.data: digest.update((','.join('%.8f'%x for x in d.uv)+';').encode())
    if obj.data.shape_keys:
        for key in obj.data.shape_keys.key_blocks:
            digest.update((key.name+'%.8f'%key.value).encode())
            for d in key.data: digest.update((','.join('%.8f'%x for x in d.co)+';').encode())
    return digest.hexdigest()


def check(path,render):
    bpy.ops.wm.open_mainfile(filepath=str(path));bpy.context.preferences.use_preferences_save=False
    module='bl_ext.blender_org.ucupaint'
    if module not in bpy.context.preferences.addons: bpy.context.preferences.addons.new().module=module
    addon_utils.enable(module,default_set=False,persistent=False)
    body=bpy.data.objects['M02_Body_Head'];rig=bpy.data.objects['M02_New_Anatomical_Rig'];control=bpy.data.objects['RING | Wardrobe Controls']
    root=bpy.data.collections['09_Ring_Original_Wardrobe']
    items={col['wardrobe_id']:col for col in root.children if col.get('wardrobe_id') and col.asset_data}
    assert len(items)==21,(len(items),list(items))
    current=anatomical_signature(body)
    with bpy.data.libraries.load(str(G.SOURCE),link=False) as (_,dst): dst.objects=['M02_Body_Head']
    reference=dst.objects[0];original=anatomical_signature(reference)
    assert current==original,'Анатомия / UV / исходные формы изменены'
    bpy.data.objects.remove(reference,do_unlink=True)
    report={'status':'PASS','file':str(path),'source':str(G.SOURCE),'source_sha256':hashlib.sha256(G.SOURCE.read_bytes()).hexdigest(),
            'body_topology_uv_and_shape_keys_unchanged':True,'anatomy_signature':current,'items':[],
            'outfit_checks':[],'static_pose_checks':[],'native_materials':[]}
    native={}
    for code,col in items.items():
        control['Предмет']=col['isolation_index'];control.update_tag();bpy.context.view_layer.update()
        meshes=[o for o in col.objects if o.type=='MESH']
        unweighted=[];abnormal=[]
        for obj in meshes:
            assert not obj.hide_render and not obj.hide_viewport,(code,obj.name)
            assert obj.parent==rig,obj.name
            arm=next((m for m in obj.modifiers if m.type=='ARMATURE'),None)
            assert arm and arm.object==rig,obj.name
            assert obj.data.uv_layers.get('UV_Fabric_Metres'),obj.name
            names={group.index:group.name for group in obj.vertex_groups}
            for v in obj.data.vertices:
                total=sum(g.weight for g in v.groups if names[g.group] in rig.data.bones and rig.data.bones[names[g.group]].use_deform)
                if total<.001: unweighted.append((obj.name,v.index))
                elif not .975<total<1.025: abnormal.append((obj.name,v.index,total))
            assert len(V.evaluated_points(obj))>0,obj.name
            for slot in obj.material_slots:
                mat=slot.material
                if mat:
                    node=next((n for n in mat.node_tree.nodes if n.type=='GROUP' and getattr(n.node_tree,'yp',None) and n.node_tree.yp.is_ypaint_node),None)
                    assert node,(code,mat.name,'Материал не в UCUPaint')
                    native[mat.name]=node.node_tree
        assert not unweighted,(code,unweighted[:5])
        assert not abnormal,(code,abnormal[:5])
        mains=[o for o in meshes if any(t in o.name for t in ['sewn main surface','sewn trouser panels','tailored hood shell'])]
        topology={o.name:V.boundaries(o) for o in mains}
        assert all(t['nonmanifold_nonboundary_edges']==0 and t['zero_area_faces']==0 for t in topology.values()),topology
        report['items'].append({'id':code,'collection':col.name,'isolation_index':col['isolation_index'],'objects':len(meshes),'vertices':sum(len(o.data.vertices) for o in meshes),'topology':topology,'normalized_weights':True})
    control['Предмет']=0;control['Балаклава']=True;control['Вариант балаклавы']=0
    for preset in range(1,7):
        control['Комплект']=preset;control.update_tag();bpy.context.view_layer.update()
        visible={code for code,col in items.items() if any(not o.hide_render for o in col.objects)}
        expected=set(N.OUTFITS[preset])|{'B%02d'%preset}
        assert visible==expected,(preset,visible,expected)
        assert bpy.data.objects['M02_Groom_Chestnut_Short'].hide_render
        report['outfit_checks'].append({'preset':preset,'visible':sorted(visible)})
    for choice in range(1,7):
        control['Вариант балаклавы']=choice;control.update_tag();bpy.context.view_layer.update()
        visible=[code for code,col in items.items() if code.startswith('B') and any(not o.hide_render for o in col.objects)]
        assert visible==['B%02d'%choice],(choice,visible)
    control['Балаклава']=False;control.update_tag();bpy.context.view_layer.update()
    assert not bpy.data.objects['M02_Groom_Chestnut_Short'].hide_render
    assert all(o.hide_render for code,col in items.items() if code.startswith('B') for o in col.objects)
    report['balaclava_toggle_restores_hair']=True;report['all_6_balaclavas_can_mix_with_outfits']=True
    control['Комплект']=5;control['Балаклава']=True;control['Вариант балаклавы']=0;control.update_tag();bpy.context.view_layer.update()
    parts=[o for code in ['T05','P04','F03','B05'] for o in items[code].objects if o.type=='MESH']
    rest={o.name:V.evaluated_points(o) for o in parts};saved={bone.name:bone.matrix_basis.copy() for bone in rig.pose.bones}
    for name,rotations in [('arms_down',[('upperarm01.L','Y',.95),('upperarm01.R','Y',-.95)]),
                           ('limb_flex',[('upperleg01.L','X',-.65),('lowerleg01.L','X',1.05),('lowerarm01.L','Z',-.80)]),
                           ('head_turn',[('head','Z',.42)])]:
        for bone,axis,angle in rotations: V.global_rotate(rig,bone,axis,angle)
        displacement={}
        for obj in parts:
            ev=V.evaluated_points(obj);assert len(ev)==len(rest[obj.name])
            displacement[obj.name]=max((a-b).length for a,b in zip(ev,rest[obj.name]))
        moved=max(displacement.values());assert .01<moved<1.7,(name,moved)
        report['static_pose_checks'].append({'pose':name,'maximum_displacement_m':moved})
        if render:
            scene=bpy.context.scene;scene.cycles.samples=32;scene.camera=bpy.data.objects['Wardrobe_ThreeQuarter']
            scene.render.resolution_x=1100;scene.render.resolution_y=1200;scene.render.filepath=str(path.parent/'verification'/(name+'.png'))
            bpy.ops.render.render(write_still=True)
        for bone in rig.pose.bones: bone.matrix_basis=saved[bone.name]
        bpy.context.view_layer.update()
    for name,tree in native.items():
        assert {ch.name for ch in tree.yp.channels}>={'Color','Roughness','Normal'}
        assert len(tree.yp.layers)>=6,(name,len(tree.yp.layers))
        report['native_materials'].append({'name':name,'layers':len(tree.yp.layers),'masks':sum(len(l.masks) for l in tree.yp.layers)})
    images=[im for im in bpy.data.images if im.source in ['FILE','GENERATED'] and im.name!='Render Result' and (im.filepath or im.packed_file)]
    assert all(im.packed_file and im.packed_file.size>0 for im in images),[im.name for im in images if not im.packed_file]
    report['packed_images']=len(images);report['armature_bones']=len(rig.data.bones)
    report['limitations']='Редактируемые исходники для художественной оценки. Игровые сетки, bake, LOD, анимационные коррекции и импорт в Godot — отдельно.'
    directory=path.parent/'verification';directory.mkdir(exist_ok=True)
    (directory/'wardrobe_verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('WARDROBE_VERIFY_PASS '+json.dumps({'items':len(items),'materials':len(native),'packed_images':len(images),'file':str(path)},ensure_ascii=False),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('file',type=Path);parser.add_argument('--render',action='store_true')
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:]);check(args.file.resolve(),args.render)
