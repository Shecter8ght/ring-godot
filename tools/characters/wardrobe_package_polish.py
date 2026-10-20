"""Довести скрытый под одеждой край балаклав и кадрирование отдельных верхов."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import argparse,bpy,math,shutil,zipfile
import m02_custom_clothes as G
import m02_custom_clothes_deliver as D

ROOT=Path(__file__).resolve().parents[2]


def hem(obj,code):
    bottom=1.453 if code=='B06' else 1.493
    for vertex in obj.data.vertices:
        p=vertex.co
        if p.z<1.561:
            a=math.atan2(p.x,-(p.y+.035))
            fade=1-G.smooth(1.525,1.561,p.z)
            width=G.profile(p.z,[(bottom,.108 if code=='B06' else .076),(1.525,.065),(1.561,.073)])
            depth=G.profile(p.z,[(bottom,.098 if code=='B06' else .079),(1.525,.067),(1.561,.086)])
            desired_x=width*math.sin(a)
            desired_y=-.035-depth*math.cos(a)
            p.x=G.mix(p.x,desired_x,fade);p.y=G.mix(p.y,desired_y,fade)
        if p.z>1.783: p.z=1.783+(p.z-1.783)*.30
    obj.data.update()


def setup(samples=48):
    scene=bpy.context.scene;scene.cycles.samples=samples;scene.cycles.use_denoising=True
    prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='OPTIX';prefs.get_devices()
    for device in prefs.devices: device.use=device.type=='OPTIX'
    scene.cycles.device='GPU'
    return scene


def main(out):
    D.enable_layers();bpy.context.preferences.filepaths.save_version=0
    master=out/'RING_NPC_Wardrobe_M02_v01.blend';previews=out/'Previews'
    bpy.ops.wm.open_mainfile(filepath=str(master))
    for col in bpy.data.collections:
        code=str(col.get('wardrobe_id',''))
        if code.startswith('B'):
            for obj in col.objects:
                if obj.type=='MESH': hem(obj,code)
    control=bpy.data.objects['RING | Wardrobe Controls'];control['Комплект']=1;control['Предмет']=0;control.update_tag();bpy.context.view_layer.update()
    scene=setup();scene.camera=bpy.data.objects['Wardrobe_ThreeQuarter']
    bpy.ops.wm.save_as_mainfile(filepath=str(master),check_existing=False,relative_remap=False)
    for number in range(1,7):
        control['Комплект']=number;control.update_tag();bpy.context.view_layer.update()
        for view in ['Front','ThreeQuarter','Back']:
            scene.camera=bpy.data.objects['Wardrobe_'+view];scene.render.resolution_x=1600;scene.render.resolution_y=1800
            scene.render.filepath=str(previews/f'C{number:02d}_{view.lower()}.png');bpy.ops.render.render(write_still=True)
        scene.camera=bpy.data.objects['Balaclava_ThreeQuarter'];scene.render.resolution_x=1100;scene.render.resolution_y=1200
        scene.render.filepath=str(previews/f'B{number:02d}_threequarter.png');bpy.ops.render.render(write_still=True)
        print('WARDROBE_FINAL_RENDER C%02d'%number,flush=True)
    for file in sorted((out/'Separate_Assets').glob('*.blend')):
        code=file.stem.split('_')[0];bpy.ops.wm.open_mainfile(filepath=str(file))
        bpy.context.preferences.filepaths.save_version=0
        for im in bpy.data.images:
            if im.packed_file and im.filepath.startswith('//textures/'):
                im.filepath='//../textures/'+im.filepath.rsplit('/',1)[-1]
        col=next(c for c in bpy.data.collections if c.get('wardrobe_id')==code and c.asset_data)
        if code.startswith('B'):
            for obj in col.objects:
                if obj.type=='MESH': hem(obj,code)
        scene=setup(40)
        if code.startswith('T'):
            scene.render.resolution_x=1600;scene.render.resolution_y=1000
            scene.camera.data.ortho_scale=1.08
        if code.startswith(('B','T')):
            scene.render.filepath=str(previews/(code+'_asset.png'))
        bpy.ops.wm.save_as_mainfile(filepath=str(file),check_existing=False,relative_remap=False)
        if code.startswith(('B','T')): bpy.ops.render.render(write_still=True)
        print('WARDROBE_FINAL_ASSET '+code,flush=True)
    scripts=out/'construction_scripts'
    for file in (ROOT/'tools/characters').glob('wardrobe_*.py'): shutil.copy2(file,scripts/file.name)
    for name in ['npc_wardrobe.py','m02_custom_clothes.py','m02_custom_clothes_deliver.py','m02_custom_clothes_verify.py']:
        shutil.copy2(ROOT/'tools/characters'/name,scripts/name)
    with zipfile.ZipFile(out/'RING_NPC_Wardrobe_Photos_v01.zip','w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for png in sorted(previews.glob('*.png')): z.write(png,'Previews/'+png.name)
    print('WARDROBE_PACKAGE_POLISH_PASS '+str(master),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('output',type=Path)
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:]);main(args.output.resolve())
