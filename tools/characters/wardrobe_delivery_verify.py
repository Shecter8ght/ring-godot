"""Переоткрыть самостоятельные ассеты и проверить целостность готовой папки выдачи."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import argparse,bpy,hashlib,json,zipfile
import m02_custom_clothes_verify as V
import m02_custom_clothes_deliver as D


def main(out,render=True):
    D.enable_layers()
    manifest=json.loads((out/'wardrobe_manifest.json').read_text(encoding='utf-8'))
    latest=out/'verification/wardrobe_verification.json'
    report=json.loads((latest if latest.is_file() else out/'wardrobe_verification.json').read_text(encoding='utf-8'))
    results=[];bpy.context.preferences.use_preferences_save=False;bpy.context.preferences.filepaths.save_version=0
    for item in manifest['separate_assets']:
        file=out/item['file'];bpy.ops.wm.open_mainfile(filepath=str(file))
        bpy.context.preferences.filepaths.save_version=0
        col=bpy.data.collections[item['collection']];rig=bpy.data.objects['M02_New_Anatomical_Rig'];control=bpy.data.objects['RING | Wardrobe Controls']
        assert col.asset_data and rig.name in col.objects and control.name in col.objects
        assert rig.parent==control
        assert 'M02_Body_Head' not in bpy.data.objects
        meshes=[o for o in col.objects if o.type=='MESH'];assert len(meshes)==item['mesh_objects']
        bpy.context.view_layer.update()
        assert all(not o.hide_render and not o.hide_viewport for o in meshes)
        for obj in meshes:
            assert obj.parent==rig
            assert next(m for m in obj.modifiers if m.type=='ARMATURE').object==rig
            assert V.evaluated_points(obj)
            if obj.animation_data:
                assert all(d.driver.is_valid for d in obj.animation_data.drivers)
            for slot in obj.material_slots:
                if not slot.material: continue
                tree=next((n.node_tree for n in slot.material.node_tree.nodes if n.type=='GROUP' and getattr(n.node_tree,'yp',None) and n.node_tree.yp.is_ypaint_node),None)
                assert tree and len(tree.yp.layers)>=6,(item['id'],slot.material.name)
        count=0;changed=False
        for im in bpy.data.images:
            if im.name in ['Render Result','Viewer Node']: continue
            if im.filepath:
                assert im.packed_file and im.packed_file.size>0,(item['id'],im.name)
                normalized=im.filepath.replace('\\','/')
                if normalized.startswith('//textures/'):
                    im.filepath='//../textures/'+normalized.rsplit('/',1)[-1];changed=True
                assert Path(bpy.path.abspath(im.filepath)).is_file(),(item['id'],im.filepath)
                count+=1
        if render and item['id'].startswith('T'):
            scene=bpy.context.scene
            scene.camera.data.ortho_scale=1.80
            scene.render.resolution_x=1600;scene.render.resolution_y=1000
            scene.render.filepath=str(out/'Previews'/(item['id']+'_asset.png'))
            scene.cycles.samples=40;scene.cycles.device='GPU'
            prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='OPTIX';prefs.get_devices()
            for device in prefs.devices: device.use=device.type=='OPTIX'
            bpy.ops.render.render(write_still=True);changed=True
        if changed: bpy.ops.wm.save_as_mainfile(filepath=str(file),check_existing=False,relative_remap=False)
        results.append({'id':item['id'],'file':item['file'],'mesh_objects':len(meshes),'packed_images':count,'self_contained_native_asset':True})
    assert len(results)==21
    archive=out/'RING_NPC_Wardrobe_Photos_v01.zip'
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for png in sorted((out/'Previews').glob('*.png')): z.write(png,'Previews/'+png.name)
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        previews=list((out/'Previews').glob('*.png'))
        assert len(previews)==45,(len(previews),len(z.namelist()))
        assert len(z.namelist())==len(previews)
    report['standalone_assets_reopened']=results;report['standalone_assets_status']='PASS';report['standalone_native_ucupaint_layers_checked']=True;report['photo_archive_checked']=True;report['render_count']=len(previews)
    (out/'wardrobe_verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    checks={str(p.relative_to(out)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in out.rglob('*') if p.is_file() and p.name!='SHA256.json'}
    (out/'SHA256.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8')
    print('WARDROBE_DELIVERY_VERIFY_PASS '+json.dumps({'assets':len(results),'renders':len(previews),'zip':'PASS'},ensure_ascii=False),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('output',type=Path);parser.add_argument('--skip-previews',action='store_true')
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:]);main(args.output.resolve(),not args.skip_previews)
