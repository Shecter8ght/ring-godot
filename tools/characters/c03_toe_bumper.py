"""Закрыть стык верха и подошвы функциональным резиновым бампером носка."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import argparse,bpy,math
from mathutils import Vector
import m02_custom_clothes as G
import m02_custom_clothes_deliver as D
import wardrobe_geometry as W
import wardrobe_materials as M
import c03_geometry as C
import c03_refine as R


def add():
    col=next(c for c in bpy.data.collections if c.get('wardrobe_id')=='F01' and c.asset_data)
    rig=bpy.data.objects['M02_New_Anatomical_Rig'];control=bpy.data.objects['RING | Wardrobe Controls'];mat=bpy.data.materials['C03 | rubber']
    for ob in list(col.objects):
        if 'rubber toe bumper' in ob.name:bpy.data.objects.remove(ob,do_unlink=True)
    keys=[(-.248,.001),(-.240,.030),(-.225,.048),(-.195,.057),(-.15,.056),(-.09,.050)]
    for side in [-1,1]:
        upper=next(ob for ob in col.objects if 'woven low upper' in ob.name and sum(v.co.x for v in ob.data.vertices)/len(ob.data.vertices)*side>0)
        surface=W.outer_surface(upper)
        verts=[];faces=[];n=145
        for row in range(7):
            t=row/6
            for i in range(n):
                a=G.mix(-1.27,1.27,i/(n-1));y=-.0825-.165*math.cos(a)
                x=C.linear(y,keys)*(1 if a>0 else -1 if a<0 else 0)
                normal=Vector((x,y+.0825,0)).normalized();toe=G.smooth(-.185,-.242,y)
                bottom=.030+.006*toe;top=.041+.019*max(0,math.cos(a))**3+.006*toe
                p=Vector((side*.093+x,y,G.mix(bottom,top,t)))+normal*(.002+.0012*math.sin(math.pi*t))
                q,norm,_,_=surface.nearest(p)
                if q is not None:
                    radial=Vector((q.x-side*.093,q.y+.0825,.03))
                    if norm.dot(radial)<0:norm=-norm
                    p=p.lerp(q+norm*.0011,G.smooth(.12,.85,t))
                verts.append(p)
        for j in range(6):
            for i in range(n-1):a=j*n+i;faces.append((a,a+1,a+n+1,a+n))
        ob=C.mesh('F01 | rubber toe bumper '+str(side),verts,faces,col,mat,1,.0010)
        group=ob.vertex_groups.new(name='foot.L' if side>0 else 'foot.R');group.add(list(range(len(ob.data.vertices))),1,'REPLACE')
        arm=ob.modifiers.new('M02 toe bumper foot binding','ARMATURE');arm.object=rig;ob.parent=rig;M.attributes(ob,'F01')
        for prop in ['hide_render','hide_viewport']:
            d=ob.driver_add(prop).driver;d.type='SCRIPTED';v=d.variables.new();v.name='enabled';v.targets[0].id=control;v.targets[0].data_path='["Обувь"]';d.expression='not enabled'


def main(args):
    D.enable_layers();out=args.output.resolve()
    for file,part in [(out/'RING_C03_M02_Art_v01.blend',False),(out/'Separate_Assets/F01_M02_Art_v01.blend',True)]:
        bpy.ops.wm.open_mainfile(filepath=str(file));bpy.context.preferences.filepaths.save_version=0;add()
        bpy.ops.wm.save_as_mainfile(filepath=str(file),check_existing=False,relative_remap=False)
        bpy.ops.wm.open_mainfile(filepath=str(file));bpy.context.view_layer.update()
        if part:
            scene=bpy.context.scene;R.use_render_device(scene);scene.render.filepath=str(out/'Previews/F01_asset.png');bpy.ops.render.render(write_still=True)
        else:R.render(out/'Previews',args.views,48)
        print('C03_TOE_BUMPER_PASS '+str(file),flush=True)
        if args.preview:break


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output',type=Path);p.add_argument('--views',default='ThreeQuarter,Shoes,Front,Side');p.add_argument('--preview',action='store_true');main(p.parse_args(sys.argv[sys.argv.index('--')+1:]))
