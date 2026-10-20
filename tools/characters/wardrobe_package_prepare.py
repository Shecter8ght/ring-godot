"""Подготовить проверяемый пакет: UV мелкой строчки и шнуровка под штанинами."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import argparse,addon_utils,bpy,shutil
import math
from mathutils import Vector
import m02_custom_clothes as G
import wardrobe_geometry as W
import wardrobe_materials as M


def folded_hood(control):
    col=next(c for c in bpy.data.collections if c.get('wardrobe_id')=='T03' and c.asset_data)
    original=next(o for o in col.objects if 'folded hood shell' in o.name)
    expression=next(c.driver.expression for c in original.animation_data.drivers if c.data_path=='hide_render')
    material=original.active_material
    bpy.data.objects.remove(original,do_unlink=True)
    n=80;rows=32;verts=[];faces=[]
    # Открытый объём капюшона лежит на спине; изнутри видна тёмная подкладка.
    for row in range(rows):
        t=row/rows;r=math.cos(t*math.pi/2)
        for i in range(n):
            a=2*math.pi*i/n
            x=.116*r*math.sin(a)
            y=.098+.024*math.sin(math.pi*t)+.035*r*math.cos(a)
            z=1.525-.116*t+.016*math.cos(a)*(1-t)
            y+=.0028*math.sin(5*a+13*t)*math.sin(math.pi*t)
            x+=.0018*math.sin(8*a-9*t)*math.sin(math.pi*t)
            verts.append((x,y,z))
    for row in range(rows-1):
        for i in range(n):
            j=(i+1)%n;faces.append((row*n+i,row*n+j,(row+1)*n+j,(row+1)*n+i))
    bottom=len(verts);verts.append((0,.098,1.409))
    for i in range(n): faces.append(((rows-1)*n+i,(rows-1)*n+(i+1)%n,bottom))
    obj=W.object_mesh('T03 | folded hood shell',verts,faces,col,material,sub=2,thickness=.0018)
    obj.data.materials.append(bpy.data.materials['combat_knit'])
    obj.modifiers['Real material thickness'].material_offset=1
    W.metric_uv(obj);M.attributes(obj,'T03')
    rim=[Vector(p)+Vector((0,0,.0008)) for p in verts[:n]]
    edge=G.line_mesh('T03 | hood opening turned edge',[rim],.00085,col,material,cyclic=True)
    seam=G.stitches('T03 | hood opening stitch',[rim+[rim[0]]],col,bpy.data.materials['thread_dark'],radius=.00016)
    new=[obj,edge]+([seam] if seam else [])
    body=bpy.data.objects['M02_Body_Head'];flags=[(m,m.show_viewport) for m in body.modifiers if m.type=='MASK']
    for m,_ in flags: m.show_viewport=False
    bpy.context.view_layer.update();G.bind(new,body,bpy.data.objects['M02_New_Anatomical_Rig'])
    for m,value in flags: m.show_viewport=value
    for item in new:
        item['wardrobe_id']='T03'
        if not item.data.uv_layers.get('UV_Fabric_Metres'): W.metric_uv(item)
        M.attributes(item,'T03')
        for path in ['hide_render','hide_viewport']:
            driver=item.driver_add(path).driver;driver.expression=expression
            for name,key in [('outfit','Комплект'),('preview','Предмет')]:
                v=driver.variables.new();v.name=name;v.targets[0].id=control;v.targets[0].data_path='["'+key+'"]'


def main(source,out):
    bpy.ops.wm.open_mainfile(filepath=str(source));bpy.context.preferences.use_preferences_save=False
    module='bl_ext.blender_org.ucupaint'
    if module not in bpy.context.preferences.addons: bpy.context.preferences.addons.new().module=module
    addon_utils.enable(module,default_set=False,persistent=False)
    root=bpy.data.collections['09_Ring_Original_Wardrobe'];control=bpy.data.objects['RING | Wardrobe Controls']
    folded_hood(control)
    for col in root.children:
        code=col.get('wardrobe_id')
        if not code: continue
        for obj in col.objects:
            if obj.type!='MESH': continue
            obj['wardrobe_id']=code
            if not obj.data.uv_layers.get('UV_Fabric_Metres'): W.metric_uv(obj)
            if code in ['F02','F02B'] and any(t in obj.name for t in ['crossed laces','eyelet']):
                group=obj.vertex_groups.new(name='Fitting | lacing beneath trousers')
                ids=[v.index for v in obj.data.vertices if v.co.z>.112]
                if not ids: continue
                group.add(ids,1.,'REPLACE')
                mask=obj.modifiers.new('Fitting | trouser hem covers upper lacing','MASK');mask.vertex_group=group.name;mask.invert_vertex_group=True
                for path in ['show_render','show_viewport']:
                    driver=mask.driver_add(path).driver
                    v=driver.variables.new();v.name='preview';v.targets[0].id=control;v.targets[0].data_path='["Предмет"]'
                    driver.expression='preview == 0'
    control['Комплект']=1;control['Предмет']=0;control.update_tag();bpy.context.view_layer.update()
    out.mkdir(exist_ok=True,parents=True)
    for png in source.parent.glob('*.png'): shutil.copy2(png,out/png.name)
    scene=bpy.context.scene;scene.camera=bpy.data.objects['Wardrobe_ThreeQuarter'];scene.cycles.samples=64
    prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='OPTIX';prefs.get_devices()
    for device in prefs.devices: device.use=device.type=='OPTIX'
    scene.cycles.device='GPU'
    bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=str(out/'RING_NPC_Wardrobe.blend'),check_existing=False)
    for number in [2,3,4]:
        control['Комплект']=number;control.update_tag();bpy.context.view_layer.update()
        for view in ['Front','ThreeQuarter','Back']:
            scene.camera=bpy.data.objects['Wardrobe_'+view];scene.render.resolution_x=1600;scene.render.resolution_y=1800
            scene.render.filepath=str(out/f'C{number:02d}_{view.lower()}.png');bpy.ops.render.render(write_still=True)
    print('WARDROBE_PACKAGE_PREPARE_PASS '+str(out/'RING_NPC_Wardrobe.blend'),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('source',type=Path);parser.add_argument('output',type=Path)
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:]);main(args.source.resolve(),args.output.resolve())
