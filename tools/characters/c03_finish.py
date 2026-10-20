"""Финальная форма C03 после проверки ткани, швов и обуви на рендерах."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import argparse,math,json,importlib
import bpy
import numpy as np
from mathutils import Vector
import m02_custom_clothes as G
import m02_custom_clothes_deliver as D
import wardrobe_geometry as W
import wardrobe_materials as M
import wardrobe_balaclavas as B
import c03_geometry as C
import c03_polish as P
import c03_refine as R

PI=math.pi


def mask(col,body,mat,thread,rig):
    # Непрерывный мягкий чехол с запасом ткани, без отпечатка губ.
    for ob in list(col.objects):bpy.data.objects.remove(ob,do_unlink=True)
    tree=B.head_surface(body);na=192;nz=144;bottom=1.495;top=1.784
    heights=np.linspace(bottom,top,nz+1);angles=np.arange(na)*2*PI/na
    width=[(1.495,.077),(1.53,.070),(1.553,.074),(1.58,.086),(1.61,.093),(1.67,.094),(1.705,.090),(1.73,.083),(1.755,.065),(1.775,.040),(1.784,.006)]
    front=[(1.495,.080),(1.53,.092),(1.553,.115),(1.58,.130),(1.61,.136),(1.638,.143),(1.663,.131),(1.705,.113),(1.73,.101),(1.755,.075),(1.775,.045),(1.784,.006)]
    back=[(1.495,.076),(1.53,.075),(1.553,.082),(1.58,.091),(1.61,.098),(1.67,.101),(1.705,.097),(1.73,.089),(1.755,.067),(1.775,.041),(1.784,.006)]
    radii=np.zeros((nz+1,na));minimum=np.zeros_like(radii)
    for j,z in enumerate(heights):
        w=C.linear(z,width)
        for i,a in enumerate(angles):
            d=C.linear(z,front if math.cos(a)>=0 else back)
            radius=1/math.sqrt((math.sin(a)/w)**2+(math.cos(a)/d)**2)
            direction=Vector((math.sin(a),-math.cos(a),0));centre=Vector((0,-.035,z))
            q,_,_,_=tree.ray_cast(centre+direction*.40,-direction,.8)
            clearance=(q-centre).dot(direction)+.0055 if q is not None else .001
            minimum[j,i]=max(.001,clearance);radii[j,i]=max(radius,clearance)
    for _ in range(12):
        temp=(radii*4+np.roll(radii,1,axis=0)+np.roll(radii,-1,axis=0)+np.roll(radii,1,axis=1)+np.roll(radii,-1,axis=1))/8
        temp[0]=radii[0];temp[-1]=radii[-1];radii=np.maximum(temp,minimum)
    v=[];f=[]
    for j,z in enumerate(heights):
        for i,a in enumerate(angles):
            r=radii[j,i];r+=.0016*math.sin(7*a+11*z)*math.exp(-((z-1.535)/.028)**2)
            v.append((r*math.sin(a),-.035-r*math.cos(a),z))
    for j in range(nz):
        for i,a in enumerate(angles):
            k=(i+1)%na;ids=(j*na+i,j*na+k,(j+1)*na+k,(j+1)*na+i)
            p=sum((Vector(v[t]) for t in ids),Vector())/4
            if math.cos(a+PI/na)>.25 and B.opening('B03',p.x,p.z):continue
            f.append(ids)
    tip=len(v);v.append((0,-.035,top+.002))
    for i in range(na):f.append((nz*na+i,nz*na+(i+1)%na,tip))
    ob=C.mesh('B03 | tailored cotton hood shell',v,f,col,mat,2,.0009)
    uv=ob.data.uv_layers.get('UV_Fabric_Metres')
    for face in ob.data.polygons:
        wrapped=any(ob.data.loops[k].vertex_index%na==0 for k in face.loop_indices) and any(ob.data.loops[k].vertex_index%na==na-1 for k in face.loop_indices)
        for index in face.loop_indices:
            p=ob.data.vertices[ob.data.loops[index].vertex_index].co;a=math.atan2(p.x,-(p.y+.035))%(2*PI)
            if wrapped and a<.01:a=2*PI
            uv.data[index].uv=(a*.091,p.z-bottom)
    # Закруглить границу глаз в плоскости ткани, сохраняя реальный вырез.
    import bmesh
    bm=bmesh.new();bm.from_mesh(ob.data)
    edge=[v for v in bm.verts if v.is_boundary and v.co.z>1.60]
    for _ in range(10):
        proposed={}
        for q in edge:
            others=[e.other_vert(q) for e in q.link_edges if e.is_boundary]
            if len(others)==2:proposed[q]=q.co.lerp((others[0].co+others[1].co)/2,.42)
        for q,co in proposed.items():q.co=co
    bm.to_mesh(ob.data);bm.free();ob.data.update()
    B.detail('B03',ob,col,mat,thread);B.bind(col,rig)
    for obj in col.objects:
        if obj.type=='MESH':M.attributes(obj,'B03')
    return ob


def finer_folds(top,pants):
    key=top.shape_key_add(name='Artist | secondary sewn folds');key.value=1
    # Новая форма хранит суммарное состояние, предыдущая остаётся редактируемым этапом.
    prev=top.data.shape_keys.key_blocks[-2]
    for old,v in zip(prev.data,key.data):v.co=old.co
    prev.value=0
    paths=[([(.173,1.35),(.131,1.315),(.10,1.309)],.004,.004),([(.184,1.291),(.144,1.267),(.098,1.26)],.005,.003),
        ([(-.194,1.386),(-.159,1.348),(-.121,1.336)],.0045,.004),([(-.194,1.23),(-.143,1.214),(-.105,1.185)],.004,.0038),
        ([(-.156,1.12),(-.115,1.092),(-.086,1.078)],.0035,.003),([(.155,1.12),(.125,1.097),(.111,1.064)],.0035,.004),
        ([(.177,1.075),(.164,1.053),(.158,1.019)],.0035,.004),([(-.058,.987),(-.068,1.035),(-.060,1.095)],.004,.004),
        ([(.066,.986),(.081,1.040),(.087,1.110)],.0045,.0045),([(-.122,.987),(-.104,1.045),(-.112,1.091)],.0038,.0035)]
    for v in key.data:
        p=v.co;x,y,z=p
        if abs(x)<.222:
            front=y<-.008
            if front:amount=sum(C.ridge(x,z,line,w,a) for line,w,a in paths)
            else:
                amount=sum(C.ridge(x,z,line,w,a) for line,w,a in [([(-.14,1.08),(-.12,1.24),(-.155,1.40)],.009,.006),([(.12,1.05),(.144,1.21),(.175,1.38)],.009,.007),([(-.19,1.33),(-.085,1.295),(.03,1.31)],.008,.004)])
            p.y+=(-1 if front else 1)*amount
        else:
            a=math.atan2(z-1.465,y+.003);normal=Vector((0,math.cos(a),math.sin(a)))
            amount=0
            for pos,tilt,w,amp in [(.372,-.023,.005,.0028),(.421,.017,.005,.004),(.462,-.021,.004,.0035),(.499,.014,.006,.0035),(.626,.017,.0045,.004),(.661,-.016,.004,.003),(.683,.014,.004,.0035),(.711,-.009,.004,.003)]:
                d=abs(x)-pos-tilt*math.cos(a+.7)
                amount+=amp*(math.exp(-(d/w)**2)-.28*math.exp(-((d+.011)/(w*2))**2))
            p+=normal*amount
    top.data.update()
    # Низ джинсов слегка ложится на обувь, разные заломы у двух штанин.
    points=pants.data.shape_keys.key_blocks[-1].data
    for v in points:
        p=v.co
        if p.z<.24:
            side=1 if p.x>0 else -1;theta=math.atan2(p.y+.012,p.x-side*.102)
            weight=1-G.smooth(.16,.24,p.z)
            p.z-=.013*weight*G.smooth(-.05,-.13,p.y)
            r=Vector((p.x-side*.102,p.y+.012,0)).normalized()
            amount=.003*weight*math.exp(-((p.z-(.153+.012*math.sin(theta+.6*side)))/.008)**2)
            p+=r*amount
    pants.data.update();bpy.context.view_layer.update()


def footwear(col,mats):
    for ob in list(col.objects):
        if 'suede toe guard' in ob.name:bpy.data.objects.remove(ob,do_unlink=True)
    for ob in list(col.objects):
        if ob.type!='MESH':continue
        if 'woven low upper' in ob.name:
            ob.data.materials.append(mats['suede']);idx=len(ob.data.materials)-1
            for face in ob.data.polygons:
                if face.center.y<-.197:face.material_index=idx
            # Кромка носовой детали проходит по колодке без зависших накладок.
            surface=W.outer_surface(ob);xs=np.linspace(-.052,.052,120);line=[]
            cx=sum(v.co.x for v in ob.data.vertices)/len(ob.data.vertices)
            for x in xs:
                y=-.197;q,normal,_,_=surface.nearest(Vector((cx+x,y,.075)))
                if q is not None:line.append(q+normal*.0012)
            stitch=G.stitches('F01 | flush toe cap seam '+str(cx),[line],col,mats['thread_boot'],radius=.00012)
            group=stitch.vertex_groups.new(name='foot.L' if cx>0 else 'foot.R');group.add(list(range(len(stitch.data.vertices))),1,'REPLACE')
            rig=bpy.data.objects['M02_New_Anatomical_Rig'];arm=stitch.modifiers.new('M02 toe cap sewing binding','ARMATURE');arm.object=rig;stitch.parent=rig;M.attributes(stitch,'F01');stitch['wardrobe_id']='F01'
            W.metric_uv(stitch)
        # Корректная метрическая проекция для крыши обуви, включая замшевые детали.
        uv=ob.data.uv_layers.get('UV_Fabric_Metres')
        if uv is None:
            W.metric_uv(ob);uv=ob.data.uv_layers.get('UV_Fabric_Metres')
        for face in ob.data.polygons:
            n=face.normal
            for index in face.loop_indices:
                p=ob.data.vertices[ob.data.loops[index].vertex_index].co
                uv.data[index].uv=(p.x,p.y) if abs(n.z)>max(abs(n.x),abs(n.y)) else (p.y,p.z) if abs(n.x)>abs(n.y) else (p.x,p.z)
    for ob in col.objects:
        if ob.type=='MESH' and 'suede' not in ob.name and any(s.material==mats['suede'] for s in ob.material_slots):M.attributes(ob,'F01')


def controls(items,body,rig):
    control=bpy.data.objects['RING | Wardrobe Controls']
    for key in list(control.keys()):
        if key not in ['Балаклава']:del control[key]
    for code,key in [('T03','Ветровка'),('P01','Джинсы'),('F01','Обувь'),('B03','Балаклава')]:
        control[key]=True;control.id_properties_ui(key).update(description='Показывать '+key.lower())
        for ob in items[code].objects:
            for prop in ['hide_render','hide_viewport']:
                d=ob.driver_add(prop).driver;d.type='SCRIPTED'
                while d.variables:d.variables.remove(d.variables[0])
                var=d.variables.new();var.name='enabled';var.targets[0].id=control;var.targets[0].data_path='["'+key+'"]';d.expression='not enabled'
    for name in ['M02_Groom_Chestnut_Short','M02_Groom_Short_Stubble']:
        ob=bpy.data.objects.get(name)
        if not ob:continue
        ob.hide_set(False)
        for prop in ['hide_render','hide_viewport']:
            d=ob.driver_add(prop).driver
            while d.variables:d.variables.remove(d.variables[0])
            var=d.variables.new();var.name='enabled';var.targets[0].id=control;var.targets[0].data_path='["Балаклава"]';d.expression='enabled'
    # Исходный обратимый MASK тела можно снять в Blender; все вершины и формы сохранены.
    control['Описание']='C03: четыре независимых выключателя. Снятие балаклавы возвращает волосы и щетину. Исходная анатомия М02 сохранена.'
    old=next(m for m in body.modifiers if m.type=='MASK' and 'Wardrobe' in m.name)
    group_index=body.vertex_groups[old.vertex_group].index
    covered=[v.index for v in body.data.vertices if any(g.group==group_index and g.weight>.5 for g in v.groups)]
    body.modifiers.remove(old)
    for key,label,test in [('Ветровка','top',lambda p:p.z>=.973),('Джинсы','pants',lambda p:.108<p.z<1.067 and abs(p.x)<.28),('Обувь','shoes',lambda p:p.z<.140)]:
        group=body.vertex_groups.new(name='C03 | reversible '+label+' coverage')
        indices=[i for i in covered if test(body.data.vertices[i].co)]
        if indices:group.add(indices,1,'REPLACE')
        mod=body.modifiers.new('C03 | reversible '+label+' coverage','MASK');mod.vertex_group=group.name;mod.invert_vertex_group=True
        G.activate(body)
        while body.modifiers[0]!=mod:bpy.ops.object.modifier_move_up(modifier=mod.name)
        for prop in ['show_render','show_viewport']:
            d=mod.driver_add(prop).driver;var=d.variables.new();var.name='enabled';var.targets[0].id=control;var.targets[0].data_path='["'+key+'"]';d.expression='enabled'
    control.update_tag();bpy.context.view_layer.update()


def main(args):
    D.enable_layers();bpy.ops.wm.open_mainfile(filepath=str(args.source.resolve()));bpy.context.preferences.filepaths.save_version=0
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    items={str(c['wardrobe_id']):c for c in bpy.data.collections if c.get('wardrobe_id') and c.asset_data}
    mats={key:bpy.data.materials['C03 | '+key] for key in ['nylon_olive','denim','suede','trek_mesh','thread_boot','thread_dark']}
    body=bpy.data.objects['M02_Body_Head'];rig=bpy.data.objects['M02_New_Anatomical_Rig']
    flags=[(m,m.show_viewport,m.show_render) for m in body.modifiers if m.type=='MASK']
    for m,_,_ in flags:m.show_viewport=False;m.show_render=False
    bpy.context.view_layer.update()
    # Диагностика посторонних деталей у горловины.
    candidates=[]
    for ob in bpy.context.scene.objects:
        if ob.type!='MESH' or ob.hide_render:continue
        surf=G.BodySurface(ob)
        for x in [-.075,.075]:
            q,*_=surf.tree.ray_cast(Vector((x,-.8,1.535)),Vector((0,1,0)))
            if q is not None and -.3<q.y<.1:candidates.append({'object':ob.name,'point':list(q)})
    (out/'neck_diagnostics.json').write_text(json.dumps(candidates,indent=2),encoding='utf-8')
    print('C03_HEAD_AND_FOLDS',flush=True)
    for ob in list(items['T03'].objects):
        if 'jersey crew neck binding' in ob.name:bpy.data.objects.remove(ob,do_unlink=True)
    old=next(o for o in items['B03'].objects if 'hood shell' in o.name);mat=old.data.materials[0];thread=bpy.data.materials['balaclava_thread']
    mask(items['B03'],body,mat,thread,rig)
    top=next(o for o in items['T03'].objects if 'sewn main surface' in o.name);pants=next(o for o in items['P01'].objects if 'sewn trouser panels' in o.name)
    finer_folds(top,pants);W.resolve_layers(top,pants,.004)
    # Швы передних регланов и спинки лежат на готовом наружном полотне.
    surf=W.outer_surface(top);new=[]
    for side in [-1,1]:
        for front in [-1,1]:
            line=W.path_on(surf,[(side*G.mix(.075,.216,t),1.531-.145*t+.012*math.sin(PI*t)) for t in np.linspace(0,1,80)],front,.0013)
            new.append(G.stitches('T03 | raglan fine stitching '+str(side)+' '+str(front),[line],items['T03'],mats['thread_dark'],radius=.00012))
    G.bind([o for o in new if o],body,rig)
    for code in ['T03','P01']:
        for ob in items[code].objects:
            if ob.type=='MESH':P.wear(ob,code)
    print('C03_FOOTWEAR_UV',flush=True);footwear(items['F01'],mats)
    for m,vis,ren in flags:m.show_viewport=vis;m.show_render=ren
    controls(items,body,rig)
    for col in items.values():
        for ob in col.objects:
            if ob.type=='MESH' and not ob.get('wardrobe_id'):ob['wardrobe_id']=col['wardrobe_id']
            if ob.type=='MESH' and not ob.data.uv_layers.get('UV_Fabric_Metres'):W.metric_uv(ob)
    scene=bpy.context.scene;scene.camera=bpy.data.objects['C03_ThreeQuarter'];bpy.ops.file.pack_all()
    filename=out/'C03_Refinement_M02.blend';bpy.ops.wm.save_as_mainfile(filepath=str(filename),check_existing=False)
    bpy.ops.wm.open_mainfile(filepath=str(filename));bpy.context.view_layer.update()
    R.render(out,args.views,args.samples);print('C03_FINISH_PASS '+str(filename),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('output',type=Path);p.add_argument('--views',default='Mask,Jacket,Shoes,ThreeQuarter,Back,Jeans');p.add_argument('--samples',type=int,default=40)
    main(p.parse_args(sys.argv[sys.argv.index('--')+1:]))
