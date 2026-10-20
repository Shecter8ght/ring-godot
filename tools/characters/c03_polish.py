"""Уточнить художественный кандидат по реальным рендерам крупным планом."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import argparse,importlib,io,math,json
from contextlib import redirect_stdout
import bpy
import numpy as np
from mathutils import Vector
import m02_custom_clothes as G
import m02_custom_clothes_deliver as D
import wardrobe_geometry as W
import wardrobe_materials as M
import wardrobe_balaclavas as B
import c03_geometry as C
import c03_refine as R


def native(mat):
    return next(n.node_tree for n in mat.node_tree.nodes if n.type=='GROUP' and getattr(n.node_tree,'yp',None) and n.node_tree.yp.is_ypaint_node)


def colour_attribute(ob,name,values):
    attr=ob.data.color_attributes.get(name) or ob.data.color_attributes.new(name,'FLOAT_COLOR','CORNER')
    colors=np.array([(*([G.clamp(values[loop.vertex_index])]*3),1) for loop in ob.data.loops],dtype=np.float32).ravel()
    attr.data.foreach_set('color',colors)


def wear(ob,code):
    points=ob.data.shape_keys.key_blocks[-1].data if ob.data.shape_keys else ob.data.vertices
    values=[];dirt=[]
    for v in points:
        x,y,z=v.co;front=G.smooth(.01,-.08,y)
        irregular=.70+.17*math.sin(93*x+43*z+11*y)+.11*math.sin(173*z-91*x+39*y)
        if code=='P01':
            thigh=math.exp(-((abs(x)-.108)/.055)**2-((z-.76)/.15)**2)*front
            knee=math.exp(-((abs(x)-.105)/.062)**2-((z-(.525+.012*(1 if x>0 else -1)))/.069)**2)*front
            seat=.50*math.exp(-((z-.966)/.073)**2)*(1-front)
            creases=0
            for line,w,a in [([(.025,.935),(.074,.895),(.151,.875)],.006,.5),([(.023,.902),(.078,.858),(.173,.838)],.005,.45),([(.049,.519),(.110,.506),(.163,.482)],.006,.35),([(.048,.197),(.102,.172),(.155,.160)],.005,.45)]:
                creases+=max(0,C.ridge(abs(x),z,line,w,a))*front
            values.append(G.clamp((.46*thigh+.54*knee+.40*seat+creases)*irregular))
            dirt.append((1-G.smooth(.115,.24,z))*(.35+.25*front)*irregular+.12*knee)
        else:
            hem=(1-G.smooth(.985,1.04,z))*(1-G.smooth(.18,.23,abs(x)))
            elbow=math.exp(-((abs(x)-.45)/.07)**2-((z-1.465)/.065)**2)
            pockets=math.exp(-((abs(x)-.15)/.025)**2-((z-1.068)/.065)**2)*front
            values.append((.20*hem+.22*elbow+.28*pockets)*irregular)
            dirt.append((.38*hem+.38*pockets+.10*elbow)*irregular)
    colour_attribute(ob,'WardrobeWear',values);colour_attribute(ob,'C03EmbeddedGrime',dirt)


def textile_image(out,name,kind):
    size=2048;y,x=np.mgrid[0:size,0:size]/size
    if kind=='mesh':
        # Воздушные ячейки сетки, масштаб раппорта 80 мм.
        xx=(x*48)%1;yy=(y*48)%1
        cell=np.exp(-(((xx-.5)/.22)**2+((yy-.5)/.31)**2))
        height=.56-.34*cell+.045*np.sin(x*2*np.pi*192)
    elif kind=='knit':
        row=(y*70)%1;column=(x*52+np.floor(y*70)*.5)%1
        height=.5+.23*np.cos(2*np.pi*(column+(.24*np.sin(2*np.pi*row))))+.07*np.cos(2*np.pi*row)
    else:
        fine=.5+.16*np.sin(2*np.pi*x*220)*np.sin(2*np.pi*y*220)
        # Тонкая усиливающая нить через 5 мм.
        line=np.exp(-(((x*16)%1-.5)/.055)**2)+np.exp(-(((y*16)%1-.5)/.055)**2)
        height=fine+.07*line
    array=np.ones((size,size,4),dtype=np.float32);array[:,:,:3]=np.clip(height,0,1)[:,:,None]
    im=bpy.data.images.new('C03 | original '+name,width=size,height=size,alpha=True,float_buffer=False)
    im.colorspace_settings.name='Non-Color';im.pixels.foreach_set(array.ravel());im.filepath_raw=str(out/(name+'.png'));im.file_format='PNG';im.save();im.pack()
    return im


def materials(items,mats,out):
    U=importlib.import_module('bl_ext.blender_org.ucupaint');M.U=U
    colors={'nylon_olive':(.052,.064,.045),'denim':(.012,.027,.047),'jersey':(.125,.128,.122),
        'trek_mesh':(.021,.025,.025),'suede':(.077,.064,.045),'midsole':(.17,.145,.110),
        'rubber':(.009,.010,.009),'thread_boot':(.098,.079,.052),'thread_dark':(.049,.059,.041),
        'thread_jeans':(.155,.098,.039),'zip_tape':(.023,.027,.019)}
    for key,mat in mats.items():
        tree=native(mat);base=colors.get(key,tuple(mat.diffuse_color[:3]));mat.diffuse_color=(*base,1)
        target=next(o for col in items.values() for o in col.objects if o.type=='MESH' and any(s.material==mat for s in o.material_slots))
        G.activate(target);target.active_material_index=next(i for i,s in enumerate(target.material_slots) if s.material==mat)
        for ly in tree.yp.layers:
            for root,ch in zip(tree.yp.channels,ly.channels):
                if ly.name.startswith('01 |') and root.name=='Color':M.sync(ch,'override_color',base)
                if ly.name.startswith('04 |') and root.type=='NORMAL':M.sync(ch,'bump_distance',.00022 if key in ['denim','suede'] else .00012)
                if ly.name.startswith('06 |') and root.name=='Color':M.sync(ch,'override_color',(.084,.132,.189) if key=='denim' else tuple(c*1.55+.012 for c in base))
                if ly.name.startswith('07 |') and root.name=='Color':M.sync(ch,'override_color',tuple(c*1.6+.009 for c in base))
            if ly.name.startswith('03 |'):M.sync(ly,'intensity_value',.50 if key=='denim' else .32)
            if ly.name.startswith('05 |'):M.sync(ly,'intensity_value',.28)
            if ly.name.startswith('06 |'):M.sync(ly,'intensity_value',.92 if key=='denim' else .60)
        if key in ['nylon_olive','denim']:
            ly=M.layer(tree,'10 | grime retained by hems and pocket entries',color=(.036,.029,.019),rough=.88,amount=.50)
            M.masked(ly,'C03EmbeddedGrime');M.fade_noise(ly,85)
        if key in ['nylon_olive','trek_mesh']:
            im=textile_image(out,key+'_weave','mesh' if key=='trek_mesh' else 'woven')
            ly=M.layer(tree,'11 | original sewn textile structure',source='IMAGE',image=im,height='source',distance=.00036 if key=='trek_mesh' else .00016)
            M.scale_image(ly,12.5)
            if key=='trek_mesh':
                ly=M.layer(tree,'12 | shadows inside woven mesh cells',source='IMAGE',image=im,color='source',blend='MULTIPLY',amount=.55);M.scale_image(ly,12.5)
        U.input_outputs.check_all_channel_ios(tree.yp,reconnect=True)
        U.input_outputs.check_start_end_root_ch_nodes(tree)
        for ly in tree.yp.layers:U.node_connections.reconnect_layer_nodes(ly)
        U.node_connections.reconnect_yp_nodes(tree)
    # Маска получает читаемый трикотаж; цвет связан с оливковой верхней одеждой.
    main=next(o for o in items['B03'].objects if 'tailored hood shell' in o.name)
    mat=main.data.materials[0];tree=native(mat);G.activate(main);main.active_material_index=0
    im=textile_image(out,'balaclava_cotton_loops','knit')
    ly=M.layer(tree,'12 | original cotton interlocked loops',source='IMAGE',image=im,height='source',distance=.00030);M.scale_image(ly,12.5)
    ly=M.layer(tree,'13 | cotton yarn colour variation',source='IMAGE',image=im,color='source',blend='MULTIPLY',amount=.25);M.scale_image(ly,12.5)
    for ly in tree.yp.layers:
        for root,ch in zip(tree.yp.channels,ly.channels):
            if ly.name.startswith('01 |') and root.name=='Color':M.sync(ch,'override_color',(.034,.043,.026))
    U.input_outputs.check_all_channel_ios(tree.yp,reconnect=True)
    for ly in tree.yp.layers:U.node_connections.reconnect_layer_nodes(ly)
    U.node_connections.reconnect_yp_nodes(tree)


def collar(top,col,mats,body,rig):
    for ob in list(col.objects):
        if 'soft neckline facing' in ob.name or 'neckline stitch' in ob.name:bpy.data.objects.remove(ob,do_unlink=True)
    path=next(path for path in B.boundary_paths(top) if min(p.z for p in path)>1.40 and max(abs(p.x) for p in path)<.14)
    verts=[];faces=[];n=len(path)
    for j in range(6):
        t=j/5
        for p in path:
            rise=.003+.024*G.smooth(1.46,1.53,p.z)
            q=p+Vector((p.x*.02*t,(p.y+.015)*.02*t,rise*t));verts.append(q)
    for j in range(5):
        for i in range(n):k=(i+1)%n;faces.append((j*n+i,j*n+k,(j+1)*n+k,(j+1)*n+i))
    ob=C.mesh('T03 | continuous soft neck facing',verts,faces,col,mats['nylon_olive'],1,.0009)
    line=[Vector(verts[4*n+i])+Vector((0,-.0004,.0006)) for i in range(n)]
    stitch=G.stitches('T03 | continuous neckline topstitch',[line+[line[0]]],col,mats['thread_dark'],radius=.00013)
    G.bind([ob,stitch],body,rig)


def mask_shape(col,body):
    main=next(o for o in col.objects if 'tailored hood shell' in o.name)
    for v in main.data.vertices:
        p=v.co
        if 1.549<p.z<1.652 and p.y<-.07:
            depth=G.profile(p.z,[(1.549,.100),(1.576,.146),(1.605,.156),(1.635,.158),(1.652,.126)])
            y=-.035-depth*math.sqrt(max(0,1-(p.x/.105)**2))
            influence=G.smooth(1.549,1.569,p.z)*(1-G.smooth(1.642,1.652,p.z))
            p.y=G.mix(p.y,min(p.y,y),influence)
    main.data.update()
    # Натяжение у переносицы и висков, с малыми непериодическими складками.
    for v in main.data.vertices:
        p=v.co
        if p.y<-.095 and 1.687<p.z<1.73:
            d=C.ridge(p.x,p.z,[(-.08,1.698),(-.035,1.708),(.018,1.703)],.003,.002)
            d+=C.ridge(p.x,p.z,[(.02,1.697),(.053,1.702),(.086,1.717)],.0025,.0015)
            p.y-=d
    main.data.update()
    return main


def main(args):
    D.enable_layers();bpy.ops.wm.open_mainfile(filepath=str(args.source.resolve()));bpy.context.preferences.filepaths.save_version=0
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    items={str(col['wardrobe_id']):col for col in bpy.data.collections if col.get('wardrobe_id') and col.asset_data}
    mats={name.split(' | ',1)[1]:mat for name,mat in [(m.name,m) for m in bpy.data.materials] if name.startswith('C03 | ') and any(any(s.material==mat for s in o.material_slots) for col in items.values() for o in col.objects if o.type=='MESH')}
    body=bpy.data.objects['M02_Body_Head'];rig=bpy.data.objects['M02_New_Anatomical_Rig']
    masks=[(m,m.show_viewport,m.show_render) for m in body.modifiers if m.type=='MASK']
    for m,_,_ in masks:m.show_viewport=False;m.show_render=False
    bpy.context.view_layer.update()
    print('C03_REBUILD_SHOES',flush=True)
    for ob in list(items['F01'].objects):bpy.data.objects.remove(ob,do_unlink=True)
    C.shoes(items['F01'],mats)
    for ob in items['F01'].objects:
        if ob.type!='MESH':continue
        x=sum(v.co.x for v in ob.data.vertices)/len(ob.data.vertices);name='foot.L' if x>0 else 'foot.R'
        vg=ob.vertex_groups.new(name=name);vg.add(list(range(len(ob.data.vertices))),1,'REPLACE')
        arm=ob.modifiers.new('M02 shared footwear rig','ARMATURE');arm.object=rig;ob.parent=rig
        M.attributes(ob,'F01')
    top=next(o for o in items['T03'].objects if 'sewn main surface' in o.name)
    collar(top,items['T03'],mats,body,rig)
    mask_shape(items['B03'],body)
    for code in ['T03','P01']:
        for ob in items[code].objects:
            if ob.type=='MESH':wear(ob,code)
    print('C03_REFINE_MATERIALS',flush=True)
    with redirect_stdout(io.StringIO()):materials(items,mats,out)
    for m,view,ren in masks:m.show_viewport=view;m.show_render=ren
    for ob in bpy.data.objects:
        if ob.type=='CURVES' and any(token in ob.name for token in ['Chestnut','Stubble']):
            for prop in ['hide_render','hide_viewport']:
                try:ob.driver_remove(prop)
                except TypeError:pass
            ob.hide_render=True;ob.hide_set(True)
    scene=bpy.context.scene;scene.view_settings.exposure=0
    for name,energy in [('C03_Key',280),('C03_Fill',110),('C03_Rim',210)]:bpy.data.objects[name].data.energy=energy
    next(n for n in scene.world.node_tree.nodes if n.type=='BACKGROUND').inputs['Strength'].default_value=.30
    floor=bpy.data.objects['C03 | matte studio floor'];mat=floor.data.materials[0];next(n for n in mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED').inputs['Base Color'].default_value=(.22,.25,.28,1)
    scene.camera=bpy.data.objects['C03_ThreeQuarter'];bpy.ops.file.pack_all()
    filename=out/'C03_Refinement_M02.blend';bpy.ops.wm.save_as_mainfile(filepath=str(filename),check_existing=False)
    R.render(out,args.views,args.samples);print('C03_POLISH_PASS '+str(filename),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('output',type=Path);p.add_argument('--views',default='Jacket,Shoes,ThreeQuarter,Mask');p.add_argument('--samples',type=int,default=40)
    main(p.parse_args(sys.argv[sys.argv.index('--')+1:]))
