"""Шесть собственных балаклав на M02 без изменения головы.

Радиальные замеры задают оболочку ткани. Вырезы лица, глаз и рта,
окантовка, швы и удлинённая горловина остаются редактируемыми сетками.
"""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import argparse
import addon_utils
import bpy
import bmesh
import importlib
import io
import json
import math
from contextlib import redirect_stdout
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
import m02_custom_clothes as G
import wardrobe_geometry as W
import wardrobe_materials as M

ROOT=Path(__file__).resolve().parents[2]
WORK=ROOT/'_asset_src/npc_wardrobe'
PI=math.pi
DESIGNS={
 'B01':dict(title='Open-face cotton hood',fabric='balaclava_grey',color=(.080,.088,.091),scan='jersey_melange',bottom=1.493,rib=.55),
 'B02':dict(title='Three-hole heavy rib knit',fabric='balaclava_charcoal',color=(.013,.015,.014),scan='jersey_melange',bottom=1.490,rib=1.),
 'B03':dict(title='Olive cotton single eye slit',fabric='balaclava_olive',color=(.057,.064,.038),scan='stretch_poplin',bottom=1.495,rib=0.),
 'B04':dict(title='Panelled stretch sports hood',fabric='balaclava_sport',color=(.016,.019,.023),scan='bi_stretch',bottom=1.498,rib=0.),
 'B05':dict(title='Thin coyote tactical hood',fabric='balaclava_coyote',color=(.135,.095,.055),scan='bi_stretch',bottom=1.490,rib=0.),
 'B06':dict(title='Long-skirt field ripstop hood',fabric='balaclava_field',color=(.061,.072,.044),scan='stretch_poplin',bottom=1.453,rib=0.),
}


def head_surface(body):
    ev=body.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=ev.to_mesh()
    vertices=[v.co.copy() for v in mesh.vertices]
    faces=[tuple(f.vertices) for f in mesh.polygons
           if all(vertices[i].z>1.510 and abs(vertices[i].x)<.145 for i in f.vertices)]
    tree=BVHTree.FromPolygons(vertices,faces,all_triangles=False)
    ev.to_mesh_clear()
    return tree


def opening(code,x,z):
    if code=='B01': return (x/.073)**2+((z-1.636)/.080)**2<1
    if code=='B02':
        return any(((x-sign*.031)/.022)**2+((z-1.6645)/.014)**2<1 for sign in [-1,1]) or (x/.030)**2+((z-1.603)/.0115)**2<1
    if code=='B03': return (x/.067)**4+((z-1.665)/.0185)**2<1
    if code=='B04': return (x/.067)**6+((z-(1.664+.035*abs(x)))/.018)**4<1
    if code=='B05': return (x/.064)**4+((z-1.6645)/.0175)**2<1
    return (x/.067)**4+((z-(1.666+.035*abs(x)))/.019)**2<1


def shell(code,col,mat,tree):
    cfg=DESIGNS[code];na=160;nz=112;bottom=cfg['bottom'];top=1.784
    angles=np.arange(na)*2*PI/na
    heights=np.linspace(bottom,top,nz+1)
    radii=np.zeros((nz+1,na))
    cy=-.035
    for row,z in enumerate(heights):
        for i,a in enumerate(angles):
            d=Vector((math.sin(a),-math.cos(a),0));centre=Vector((0,cy,z))
            point,normal,index,distance=tree.ray_cast(centre+d*.40,-d,.8)
            fallback=.072*math.sqrt(max(.015,1-((z-1.653)/.135)**2))
            radius=(point-centre).dot(d) if point is not None else fallback
            if z<1.525:
                width=G.mix(.112 if code=='B06' else .080,.066,G.smooth(bottom,1.525,z))
                front=G.mix(.112 if code=='B06' else .082,.073,G.smooth(bottom,1.525,z))
                radius=1/math.sqrt((math.sin(a)/width)**2+(math.cos(a)/front)**2)
            radii[row,i]=max(.009,radius)
    smooth=radii.copy()
    for _ in range(5):
        smooth=(smooth*4+np.roll(smooth,1,axis=1)+np.roll(smooth,-1,axis=1)+np.roll(smooth,1,axis=0)+np.roll(smooth,-1,axis=0))/8
        smooth[0]=radii[0];smooth[-1]=radii[-1]
    radii=np.maximum(radii+.0045,smooth+.0065)
    verts=[];faces=[];face_mats=[]
    for row,z in enumerate(heights):
        for i,a in enumerate(angles):
            r=radii[row,i]
            neck=(1-G.smooth(1.53,1.59,z))*G.smooth(bottom,bottom+.015,z)
            r+=neck*(.0018*math.cos(9*a+38*z)+.0012*math.sin(17*a-54*z))
            if code in ['B02','B06']: r+=.0015
            verts.append((math.sin(a)*r,cy-math.cos(a)*r,z))
    for row in range(nz):
        for i,a in enumerate(angles):
            j=(i+1)%na;ids=(row*na+i,row*na+j,(row+1)*na+j,(row+1)*na+i)
            centre=sum((Vector(verts[k]) for k in ids),Vector())/4
            if math.cos(a+PI/na)>.25 and opening(code,centre.x,centre.z): continue
            faces.append(ids)
            angle=(a+PI/na+PI)%(2*PI)-PI
            face_mats.append(1 if code=='B04' and .83<abs(angle)<2.28 else 0)
    apex=len(verts);verts.append((0,cy,top+.005))
    for i in range(na): faces.append((nz*na+i,nz*na+(i+1)%na,apex));face_mats.append(0)
    obj=W.object_mesh(code+' | tailored hood shell',verts,faces,col,mat,sub=2,thickness=.0016 if code=='B02' else .0010)
    mesh=obj.data
    uv=mesh.uv_layers.new(name='UV_Fabric_Metres')
    for face in mesh.polygons:
        indices=[mesh.loops[k].vertex_index for k in face.loop_indices]
        wrapped=any(index%na==0 for index in indices) and any(index%na==na-1 for index in indices)
        for loop,index in zip(face.loop_indices,indices):
            p=mesh.vertices[index].co;a=math.atan2(p.x,-(p.y-cy))%(2*PI)
            if wrapped and a<.01: a=2*PI
            uv.data[loop].uv=(a*.091,p.z-bottom)
    if code=='B04':
        side=G.material('balaclava_sport_side',(.039,.044,.049),.76)
        M.SCAN[side.name]='bi_stretch';mesh.materials.append(side)
        for f,index in zip(mesh.polygons,face_mats): f.material_index=index
    obj['construction']='Original radial sewing draft; open boundaries for face/eyes/mouth. No boolean changes to the head.'
    obj['fit_clearance_m']=.0045
    return obj


def boundary_paths(obj):
    # Окантовка идёт по сглаженному наружному краю без внутренней толщины Solidify.
    flags=[(m,m.show_viewport) for m in obj.modifiers if m.type=='SOLIDIFY']
    for m,_ in flags: m.show_viewport=False
    bpy.context.view_layer.update()
    ev=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=ev.to_mesh()
    bm=bmesh.new();bm.from_mesh(mesh)
    adjacent={}
    for edge in bm.edges:
        if edge.is_boundary:
            a,b=edge.verts
            adjacent.setdefault(a,[]).append(b);adjacent.setdefault(b,[]).append(a)
    pending=set(adjacent);paths=[]
    while pending:
        start=next(iter(pending));current=start;previous=None;path=[]
        while current in pending:
            pending.remove(current);path.append(current.co.copy())
            candidates=[v for v in adjacent[current] if v!=previous]
            if not candidates: break
            previous,current=current,candidates[0]
        if len(path)>5: paths.append(path)
    bm.free();ev.to_mesh_clear()
    for m,flag in flags: m.show_viewport=flag
    bpy.context.view_layer.update()
    return paths


def detail(code,main,col,mat,thread):
    paths=boundary_paths(main)
    surface=W.outer_surface(main)
    for number,path in enumerate(paths):
        if max(p.z for p in path)-min(p.z for p in path)<.012: label='neck hem'
        else: label='face opening binding'
        # Узкий подогнутый край ткани.
        obj=G.line_mesh(code+' | '+label+' %02d'%number,[path],.0008,col,mat,cyclic=True)
        obj['wardrobe_id']=code;W.metric_uv(obj)
        G.stitches(code+' | '+label+' stitches %02d'%number,[path+[path[0]]],col,thread,radius=.00013)
    seams=[]
    cy=-.035
    for a in ([PI/2,3*PI/2] if code in ['B01','B02'] else [.85,-.85,2.28,-2.28] if code=='B04' else [PI]):
        path=[]
        for step in range(111):
            z=G.mix(DESIGNS[code]['bottom']+.006,1.779,step/110)
            target=Vector((math.sin(a)*.11,cy-math.cos(a)*.11,z))
            point,normal,_,_=surface.nearest(target)
            if point is None: continue
            radial=Vector((point.x,point.y-cy,0))
            if normal.dot(radial)<0: normal=-normal
            path.append(point+normal*.0012)
        seams.append(path)
    G.stitches(code+' | flatlock panel seams',seams,col,thread,radius=.00016)
    if code=='B05':
        # Местная маска микроперфорации сохраняет тонкую оболочку редактируемой.
        attr=main.data.color_attributes.new('BalaclavaBreathingPanel','FLOAT_COLOR','CORNER')
        for loop in main.data.loops:
            p=main.data.vertices[loop.vertex_index].co
            value=G.smooth(.041,.033,abs(p.x))*G.smooth(1.575,1.585,p.z)*(1-G.smooth(1.617,1.625,p.z))*G.smooth(-.10,-.13,p.y)
            attr.data[loop.index].color=(value,value,value,1)
    for obj in col.objects:
        obj['wardrobe_id']=code
        if obj.type=='MESH' and not obj.data.uv_layers.get('UV_Fabric_Metres'): W.metric_uv(obj)


def bind(col,rig):
    names=[n for n in ['head','neck01','neck02'] if n in rig.data.bones]
    neck='neck01' if 'neck01' in names else names[-1]
    for obj in col.objects:
        if obj.type!='MESH': continue
        groups={n:obj.vertex_groups.new(name=n) for n in names}
        for vertex in obj.data.vertices:
            head=G.smooth(1.516,1.574,vertex.co.z)
            groups['head'].add([vertex.index],head,'REPLACE')
            groups[neck].add([vertex.index],1-head,'REPLACE')
        mod=obj.modifiers.new('M02 anatomical head and neck','ARMATURE');mod.object=rig
        G.activate(obj)
        while obj.modifiers[0]!=mod: bpy.ops.object.modifier_move_up(modifier=mod.name)
        obj.parent=rig


def procedural_image(out,name,kind):
    size=1024;yy,xx=np.mgrid[0:size,0:size]/size
    if kind=='rib':
        # Физический раппорт 40 мм с шагом рубчика 1,8 мм.
        height=.5+.30*np.cos(xx*2*PI*22)+.13*np.sin(yy*2*PI*80+np.sin(xx*2*PI*22)*.65)
    elif kind=='ripstop':
        gridx=np.exp(-(np.minimum((xx*8)%1,1-(xx*8)%1)/.045)**2)
        gridy=np.exp(-(np.minimum((yy*8)%1,1-(yy*8)%1)/.045)**2)
        height=.38+.22*np.maximum(gridx,gridy)+.08*np.sin(xx*2*PI*180)*np.sin(yy*2*PI*180)
    else:
        height=.5+.30*(np.sin(xx*2*PI*20)**12)*(np.sin(yy*2*PI*20)**12)
    height=np.clip(height,0,1)
    rgba=np.ones((size,size,4),np.float32);rgba[:,:,:3]=height[:,:,None]
    image=bpy.data.images.new(name,width=size,height=size);image.colorspace_settings.name='Non-Color'
    image.pixels.foreach_set(rgba.ravel());image.filepath_raw=str(out/(name+'.png'));image.file_format='PNG';image.save();image.pack()
    return image


def texture(items,mats,out):
    report=M.apply(items,mats,out)
    U=importlib.import_module('bl_ext.blender_org.ucupaint');M.U=U
    rib=procedural_image(out,'RING_balaklava_rib_40mm','rib')
    rip=procedural_image(out,'RING_balaklava_ripstop_40mm','ripstop')
    vents=procedural_image(out,'RING_balaklava_vents_40mm','vent')
    with redirect_stdout(io.StringIO()):
        for code,cfg in DESIGNS.items():
            mat=mats[cfg['fabric']]
            tree=next(n.node_tree for n in mat.node_tree.nodes if n.type=='GROUP' and getattr(n.node_tree,'yp',None) and n.node_tree.yp.is_ypaint_node)
            bsdf=next(n for n in mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED');bsdf.inputs['Sheen Weight'].default_value=.055
            if cfg['rib']:
                ly=M.layer(tree,'10 | knitted vertical ribs',source='IMAGE',image=rib,height='source',distance=.00038*cfg['rib'])
                M.scale_image(ly,25.)
            if code=='B06':
                ly=M.layer(tree,'10 | woven ripstop reinforcement grid',source='IMAGE',image=rip,height='source',rough='source',amount=.32,distance=.00020)
                M.scale_image(ly,25.)
            if code=='B05':
                ly=M.layer(tree,'10 | breathing panel micro perforations',source='IMAGE',image=vents,height='source',rough=.86,distance=-.0008)
                M.scale_image(ly,25.);M.masked(ly,'BalaclavaBreathingPanel')
            U.node_connections.reconnect_yp_nodes(tree)
    return report


def controls(items,control):
    control['Балаклава']=True
    control.id_properties_ui('Балаклава').update(description='Show the hood; hiding it restores the original scalp groom.')
    control['Вариант балаклавы']=0
    control.id_properties_ui('Вариант балаклавы').update(min=0,max=6,description='0 follows outfit; 1–6 selects any balaclava with any outfit.')
    highest=max((col.get('isolation_index',0) for col in bpy.data.collections if not str(col.get('wardrobe_id','')).startswith('B')),default=15)
    for number,(code,col) in enumerate(items.items(),1):
        col['isolation_index']=highest+number;col['used_in_outfits']=str(number)
        for obj in col.objects:
            for path in ['hide_render','hide_viewport']:
                driver=obj.driver_add(path).driver
                while driver.variables: driver.variables.remove(driver.variables[0])
                for var,key in [('outfit','Комплект'),('preview','Предмет'),('enabled','Балаклава'),('choice','Вариант балаклавы')]:
                    v=driver.variables.new();v.name=var;v.targets[0].id=control;v.targets[0].data_path='["'+key+'"]'
                driver.expression=f'not (preview == {highest+number} or (preview == 0 and enabled and (choice == {number} or (choice == 0 and outfit == {number}))))'
    control.id_properties_ui('Предмет').update(max=highest+6)
    hair=bpy.data.objects.get('M02_Groom_Chestnut_Short')
    if hair:
        for path in ['hide_render','hide_viewport']:
            driver=hair.driver_add(path).driver
            while driver.variables: driver.variables.remove(driver.variables[0])
            for var,key in [('enabled','Балаклава'),('preview','Предмет')]:
                v=driver.variables.new();v.name=var;v.targets[0].id=control;v.targets[0].data_path='["'+key+'"]'
            driver.expression=f'enabled and (preview == 0 or preview > {highest})'


def main(args):
    source=args.source.resolve();out=WORK/args.version;out.mkdir(parents=True,exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(source))
    bpy.context.preferences.use_preferences_save=False
    module='bl_ext.blender_org.ucupaint'
    if module not in bpy.context.preferences.addons: bpy.context.preferences.addons.new().module=module
    addon_utils.enable(module,default_set=False,persistent=False)
    root=bpy.data.collections['09_Ring_Original_Wardrobe'];body=bpy.data.objects['M02_Body_Head'];rig=bpy.data.objects['M02_New_Anatomical_Rig']
    control=bpy.data.objects['RING | Wardrobe Controls']
    tree=head_surface(body);mats={};items={}
    thread=G.material('balaclava_thread',(.028,.028,.023),.85);mats[thread.name]=thread
    for code,cfg in DESIGNS.items():
        print('BALACLAVA_DRAFT '+code,flush=True)
        col=G.collection(code+' | '+cfg['title'],root);col['wardrobe_id']=code
        mat=G.material(cfg['fabric'],cfg['color'],.79);mats[mat.name]=mat;M.SCAN[mat.name]=cfg['scan']
        main_obj=shell(code,col,mat,tree);detail(code,main_obj,col,mat,thread);bind(col,rig)
        for slot in main_obj.material_slots:
            if slot.material: mats[slot.material.name]=slot.material
        col.asset_mark();col.asset_data.description=cfg['title']+'; original editable cloth with shared M02 head/neck weights'
        items[code]=col
    texture(items,mats,out)
    controls(items,control)
    control['Комплект']=1;control['Предмет']=0;control.update_tag();bpy.context.view_layer.update()
    studio=bpy.data.collections['06_Review_Studio']
    for view,pos in [('Front',(0,-1.2,1.65)),('ThreeQuarter',(.7,-1.2,1.68)),('Side',(1.2,-.035,1.66)),('Back',(0,1.2,1.65))]:
        data=bpy.data.cameras.new('Balaclava_'+view);data.type='ORTHO';data.ortho_scale=.43
        camera=bpy.data.objects.new('Balaclava_'+view,data);studio.objects.link(camera);camera.location=pos
        camera.rotation_euler=(Vector((0,-.035,1.636))-camera.location).to_track_quat('-Z','Y').to_euler()
    scene=bpy.context.scene;scene.cycles.samples=args.samples
    prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='OPTIX';prefs.get_devices()
    for device in prefs.devices: device.use=device.type=='OPTIX'
    scene.cycles.device='GPU';scene.camera=bpy.data.objects['Wardrobe_ThreeQuarter']
    bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=str(out/'RING_Wardrobe_Balaclavas.blend'),check_existing=False)
    (out/'balaclavas_report.json').write_text(json.dumps(DESIGNS,indent=2),encoding='utf-8')
    scene.render.resolution_x=1100;scene.render.resolution_y=1200
    for number in range(1,7):
        control['Комплект']=number;control.update_tag();bpy.context.view_layer.update()
        for view in args.render.split(','):
            scene.camera=bpy.data.objects['Balaclava_'+view];scene.render.filepath=str(out/f'B{number:02d}_{view.lower()}.png')
            bpy.ops.render.render(write_still=True)
            print(f'BALACLAVA_RENDER B{number:02d} {view}',flush=True)
    print('BALACLAVA_PASS '+str(out/'RING_Wardrobe_Balaclavas.blend'),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('source',type=Path)
    parser.add_argument('--version',default='balaclavas_v01');parser.add_argument('--samples',type=int,default=48)
    parser.add_argument('--render',default='Front,ThreeQuarter')
    main(parser.parse_args(sys.argv[sys.argv.index('--')+1:]))
