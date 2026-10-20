"""Переоткрыть C03: исходная анатомия, веса, слои, выключатели и статичные позы."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import argparse,bpy,json,hashlib,math
import m02_custom_clothes as G
import m02_custom_clothes_deliver as D
import m02_custom_clothes_verify as V
from wardrobe_verify import anatomical_signature


def main(file):
    D.enable_layers();bpy.ops.wm.open_mainfile(filepath=str(file.resolve()))
    body=bpy.data.objects['M02_Body_Head'];rig=bpy.data.objects['M02_New_Anatomical_Rig'];control=bpy.data.objects['RING | Wardrobe Controls']
    signature=anatomical_signature(body)
    with bpy.data.libraries.load(str(G.SOURCE),link=False) as (_,dst):dst.objects=['M02_Body_Head']
    ref=dst.objects[0];assert anatomical_signature(ref)==signature,'Изменена исходная анатомия, UV или форма тела';bpy.data.objects.remove(ref,do_unlink=True)
    items={str(c['wardrobe_id']):c for c in bpy.data.collections if c.get('wardrobe_id') and c.asset_data}
    assert set(items)=={'T03','P01','F01','B03'},list(items)
    report={'status':'PASS','file':str(file),'source_body':str(G.SOURCE),'source_sha256':hashlib.sha256(G.SOURCE.read_bytes()).hexdigest(),
        'body_topology_uv_and_all_shape_keys_unchanged':True,'anatomy_signature':signature,'items':[],'materials':[],'static_poses':[],'toggles':[]}
    materials={};parts=[]
    for code,col in items.items():
        meshes=[o for o in col.objects if o.type=='MESH'];topology={};vertices=0
        for ob in meshes:
            assert ob.parent==rig,ob.name
            assert any(m.type=='ARMATURE' and m.object==rig for m in ob.modifiers),ob.name
            assert ob.data.uv_layers.get('UV_Fabric_Metres'),ob.name
            assert V.evaluated_points(ob),ob.name
            names={g.index:g.name for g in ob.vertex_groups};vertices+=len(ob.data.vertices)
            for v in ob.data.vertices:
                weight=sum(g.weight for g in v.groups if names[g.group] in rig.data.bones and rig.data.bones[names[g.group]].use_deform)
                assert .975<weight<1.025,(ob.name,v.index,weight)
            if any(t in ob.name for t in ['sewn main surface','sewn trouser panels','hood shell','woven low upper']):
                t=V.boundaries(ob);topology[ob.name]=t
                assert t['nonmanifold_nonboundary_edges']==0 and t['zero_area_faces']==0,(ob.name,t)
            for slot in ob.material_slots:
                mat=slot.material
                if not mat:continue
                tree=next((n.node_tree for n in mat.node_tree.nodes if n.type=='GROUP' and getattr(n.node_tree,'yp',None) and n.node_tree.yp.is_ypaint_node),None)
                assert tree and len(tree.yp.layers)>=6,(ob.name,mat.name)
                materials[mat.name]=tree
        report['items'].append({'id':code,'collection':col.name,'meshes':len(meshes),'vertices':vertices,'normalized_weights':True,'topology':topology})
        parts.extend(meshes)
    for code,key in [('T03','Ветровка'),('P01','Джинсы'),('F01','Обувь'),('B03','Балаклава')]:
        control[key]=False;control.update_tag();bpy.context.view_layer.update()
        assert all(o.hide_render for o in items[code].objects if o.type=='MESH'),code
        if code=='B03':assert not bpy.data.objects['M02_Groom_Chestnut_Short'].hide_render
        control[key]=True;control.update_tag();bpy.context.view_layer.update()
        assert all(not o.hide_render for o in items[code].objects if o.type=='MESH'),code
        report['toggles'].append({'id':code,'property':key,'passed':True})
    assert bpy.data.objects['M02_Groom_Chestnut_Short'].hide_render
    report['removing_balaclava_restores_original_hair_and_stubble']=True
    rest={o.name:V.evaluated_points(o) for o in parts};saved={p.name:p.matrix_basis.copy() for p in rig.pose.bones}
    for name,rotations in [('arms_down',[('upperarm01.L','Y',.95),('upperarm01.R','Y',-.95)]),('limb_flex',[('upperleg01.L','X',-.6),('lowerleg01.L','X',1.0),('lowerarm01.L','Z',-.75)]),('head_turn',[('head','Z',.42)])]:
        for bone,axis,angle in rotations:V.global_rotate(rig,bone,axis,angle)
        maximum=0
        for ob in parts:
            points=V.evaluated_points(ob);assert len(points)==len(rest[ob.name]),ob.name
            maximum=max(maximum,max((a-b).length for a,b in zip(points,rest[ob.name])))
        assert .01<maximum<1.6,(name,maximum)
        report['static_poses'].append({'name':name,'maximum_displacement_m':maximum,'finite_coordinates':True})
        for bone in rig.pose.bones:bone.matrix_basis=saved[bone.name]
        bpy.context.view_layer.update()
    for name,tree in materials.items():
        assert {'Color','Roughness','Normal'}<={ch.name for ch in tree.yp.channels},name
        report['materials'].append({'name':name,'native_ucupaint_layers':len(tree.yp.layers),'masks':sum(len(ly.masks) for ly in tree.yp.layers)})
    for ob in parts+[body]:
        if ob.animation_data:assert all(d.driver.is_valid for d in ob.animation_data.drivers),ob.name
    images=[im for im in bpy.data.images if im.packed_file and im.name not in ['Render Result','Viewer Node']]
    assert all(im.packed_file.size>0 for im in images)
    report['packed_images']=len(images);report['rig_bones']=len(rig.data.bones)
    report['scope']='Editable art candidate for M02. Static rig smoke checks are not full animation approval. No game export, bake or LOD.'
    out=file.parent/'verification';out.mkdir(exist_ok=True);(out/'c03_verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('C03_VERIFY_PASS '+json.dumps({'items':len(items),'native_materials':len(materials),'packed_images':len(images),'file':str(file)},ensure_ascii=False),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('file',type=Path);main(parser.parse_args(sys.argv[sys.argv.index('--')+1:]).file.resolve())
