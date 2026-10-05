"""Редактируемые предметы обстановки: Blender + слои Ucupaint → сохранённые GLB.

Производственный инструмент. Игра загружает готовые меши, карты и анимации.
Запуск в выбранном Blender: --background --factory-startup --python этот_файл.
"""
from __future__ import annotations
import bpy, sys, math, json, shutil
from pathlib import Path
import numpy as np
from mathutils import Vector

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT/'_asset_src/shelter/dressing'
OUT = ROOT/'assets/shelter/dressing'
SRC.mkdir(parents=True, exist_ok=True); OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(Path(r'C:/Users/Schecter_8ght/AppData/Roaming/Blender Foundation/Blender/5.2/extensions/blender_org')))
bpy.ops.preferences.addon_enable(module='ucupaint')
import ucupaint

bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
bpy.context.scene.unit_settings.system='METRIC'
PARTS=[]; MANIFEST={}
PALETTE=[(.61,.58,.49),(.17,.24,.19),(.045,.052,.049),(.48,.50,.49),
         (.38,.34,.23),(.19,.27,.30),(.28,.18,.12),(.73,.69,.57),
         (.48,.34,.19),(.46,.10,.055),(.56,.39,.12),(.12,.23,.34),
         (.35,.39,.41),(.34,.23,.13),(.35,.43,.23),(.028,.032,.03)]
S=1024; TILE=S//4

def image_pixels(image, pixels):
    image.pixels.foreach_set(np.asarray(pixels,dtype=np.float32).reshape(-1)); image.update()
    image.pack()

def paint_atlas():
    # Ucupaint сохраняет настоящие image layers; в runtime нет noise/geometry nodes.
    bpy.ops.mesh.primitive_plane_add(size=2)
    plane=bpy.context.object; plane.name='Texture bake reference'
    material=bpy.data.materials.new('DressingAtlas'); material.use_nodes=True
    plane.data.materials.append(material)
    bpy.ops.wm.y_quick_ypaint_node_setup(tree_name='Shelter dressing — Ucupaint',color=True,metallic=True,roughness=True,normal=False,ao=False,switch_to_material_view=False)
    node=next(n for n in material.node_tree.nodes if n.type=='GROUP' and n.node_tree.yp.is_ypaint_node)
    material.node_tree.nodes.active=node
    color=np.ones((S,S,4),dtype=np.float32)
    wear=np.zeros_like(color); rough=np.ones_like(color); metal=np.ones_like(color)
    for idx,rgb in enumerate(PALETTE):
        x=(idx%4)*TILE; y=(idx//4)*TILE
        color[y:y+TILE,x:x+TILE,:3]=rgb
        rough[y:y+TILE,x:x+TILE,:3]=.82 if idx not in (3,12) else .52
        metal[y:y+TILE,x:x+TILE,:3]=.85 if idx in (3,12) else 0
        # Уже лицензированные фотографии из основного комплекта, собранные в Ucupaint.
        photograph={0:'PaintedSteel',1:'PaintedSteel',3:'BareSteel',4:'Canvas',5:'Canvas',6:'Canvas',7:'Paper',8:'Cardboard',12:'BareSteel',13:'OldWood'}.get(idx)
        if photograph:
            photo=bpy.data.images.load(str(ROOT/'assets/shelter/textures'/(photograph+'_base.jpg')),check_existing=True)
            samples=np.empty(photo.size[0]*photo.size[1]*4,dtype=np.float32);photo.pixels.foreach_get(samples)
            pixels=samples.reshape(photo.size[1],photo.size[0],4)
            rows=np.linspace(0,photo.size[1]-1,TILE).astype(int);cols=np.linspace(0,photo.size[0]-1,TILE).astype(int)
            grey=pixels[rows[:,None],cols[None,:],:3].mean(axis=2)
            shade=np.clip(grey/max(.01,float(grey.mean())),.65,1.35)
            color[y:y+TILE,x:x+TILE,:3]*=shade[:,:,None]
            photo.pack()
        # Написанные штрихи ткани и картона, масштабируемые отдельно от геометрии.
        if idx in (4,5,6):
            for d in range(8,TILE-8,6):
                color[y+d,x+8:x+TILE-8,:3]=np.array(rgb)*.88
                color[y+8:y+TILE-8,x+d,:3]=np.array(rgb)*1.05
        if idx in (8,13):
            for d in (19,38,63,91,124,166,199,228):
                color[y+d:y+d+2,x+8:x+TILE-8,:3]=np.array(rgb)*.92
        # Контактный износ ограничен краями UV-плитки и несколькими полосами.
        if idx in (0,1,9,10,11):
            for a,b,c in [(24,82,22),(132,178,24),(55,116,231),(159,210,232)]:
                wear[y+c:y+c+2,x+a:x+b,:3]=(.30,.29,.25)
                wear[y+c:y+c+2,x+a:x+b,3]=.45
    for title,channel,buf in [('01 — surface colour',0,color),('02 — contact wear',0,wear),('03 — measured roughness',2,rough),('04 — exposed metal',1,metal)]:
        bpy.ops.wm.y_new_layer(name=title,type='IMAGE',width=S,height=S,use_custom_resolution=True,channel_idx=str(channel),uv_map='UVMap')
        layer=node.node_tree.yp.layers[node.node_tree.yp.active_layer_index]
        image_pixels(ucupaint.common.get_layer_source(layer).image,buf)
    bpy.context.scene.render.engine='CYCLES'
    ucupaint.Bake.YBakeChannels.no_layer_using=False
    area=next(a for a in bpy.context.screen.areas if a.type=='VIEW_3D')
    with bpy.context.temp_override(area=area,region=next(r for r in area.regions if r.type=='WINDOW')):
        bpy.ops.wm.y_bake_channels(uv_map='UVMap',use_custom_resolution=True,width=S,height=S,samples=1,fxaa=False,bake_device='CPU',margin=2)
    maps={}
    for channel in node.node_tree.yp.channels:
        assert channel.baked, channel.name
        img=node.node_tree.nodes[channel.baked].image
        filename={'Color':'Dressing_base.png','Roughness':'Dressing_roughness.png','Metallic':'Dressing_metallic.png'}[channel.name]
        img.filepath_raw=str(OUT/filename); img.file_format='PNG'; img.save(); img.pack()
        maps[channel.name]=img
    node.node_tree.yp.use_baked=False
    bpy.data.objects.remove(plane,do_unlink=True)
    export_mat=bpy.data.materials.new('DressingAtlas_export'); export_mat.use_nodes=True
    bs=export_mat.node_tree.nodes.get('Principled BSDF')
    for channel,socket in [('Color','Base Color'),('Roughness','Roughness'),('Metallic','Metallic')]:
        tex=export_mat.node_tree.nodes.new('ShaderNodeTexImage');tex.image=maps[channel]
        export_mat.node_tree.links.new(tex.outputs['Color'],bs.inputs[socket])
    return material,export_mat

PAINT_MAT,EXPORT_MAT=paint_atlas()

def xyz(p): return (p[0],-p[2],p[1])

def uv_tile(o,tile):
    uv=o.data.uv_layers.active or o.data.uv_layers.new(name='UVMap')
    bounds=[(min(v.co[a] for v in o.data.vertices),max(v.co[a] for v in o.data.vertices)) for a in range(3)]
    for face in o.data.polygons:
        axis=max(range(3),key=lambda i:abs(face.normal[i]));axes=[i for i in range(3) if i!=axis]
        coords=[o.data.vertices[o.data.loops[li].vertex_index].co for li in face.loop_indices]
        mins=[bounds[a][0] for a in axes]; maxs=[bounds[a][1] for a in axes]
        for li,v in zip(face.loop_indices,coords):
            u=(v[axes[0]]-mins[0])/max(.001,maxs[0]-mins[0]);w=(v[axes[1]]-mins[1])/max(.001,maxs[1]-mins[1])
            uv.data[li].uv=((tile%4+.06+u*.88)/4,(tile//4+.06+w*.88)/4)

def finish(o,name,tile,bevel=0,smooth=False):
    o.name=name; bpy.context.view_layer.objects.active=o
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    if bevel:
        mod=o.modifiers.new('Rounded manufactured edges','BEVEL');mod.width=bevel;mod.segments=3
        bpy.ops.object.modifier_apply(modifier=mod.name)
        mod=o.modifiers.new('Weighted face normals','WEIGHTED_NORMAL');mod.keep_sharp=True
        bpy.ops.object.modifier_apply(modifier=mod.name)
    if smooth:
        for p in o.data.polygons:p.use_smooth=True
    o.data.materials.append(PAINT_MAT);uv_tile(o,tile);PARTS.append(o);return o

def box(name,p,size,tile=1,bevel=.003,yaw=0):
    bpy.ops.mesh.primitive_cube_add(size=1,location=xyz(p));o=bpy.context.object
    o.scale=(size[0],size[2],size[1]);o.rotation_euler.z=math.radians(yaw)
    return finish(o,name,tile,min(bevel,min(size)*.24))

def cyl(name,a,b,r,tile=3,r2=None,verts=40):
    va=Vector(xyz(a));vb=Vector(xyz(b));d=vb-va
    bpy.ops.mesh.primitive_cone_add(vertices=verts,radius1=r,radius2=r if r2 is None else r2,depth=d.length,location=(va+vb)/2)
    o=bpy.context.object;o.rotation_euler=d.to_track_quat('Z','Y').to_euler()
    return finish(o,name,tile,min(.0015,r*.12),True)

def path(name,pts,r,tile=3):
    data=bpy.data.curves.new(name,'CURVE');data.dimensions='3D';data.resolution_u=12
    data.bevel_depth=r;data.bevel_resolution=3
    s=data.splines.new('BEZIER');s.bezier_points.add(len(pts)-1)
    for b,p in zip(s.bezier_points,pts): b.co=xyz(p);b.handle_left_type='AUTO';b.handle_right_type='AUTO'
    o=bpy.data.objects.new(name,data);bpy.context.collection.objects.link(o)
    bpy.ops.object.select_all(action='DESELECT');o.select_set(True);bpy.context.view_layer.objects.active=o
    bpy.ops.object.convert(target='MESH');return finish(bpy.context.object,name,tile,0,True)

def lathe(name,profile,tile=0,verts=48):
    points=[];faces=[]
    for y,r in profile:
        for i in range(verts):
            a=2*math.pi*i/verts;points.append(xyz((math.cos(a)*r,y,math.sin(a)*r)))
    for j in range(len(profile)-1):
        for i in range(verts):
            n=(i+1)%verts;faces.append((j*verts+i,(j+1)*verts+i,(j+1)*verts+n,j*verts+n))
    mesh=bpy.data.meshes.new(name);mesh.from_pydata(points,[],faces);mesh.update()
    o=bpy.data.objects.new(name,mesh);bpy.context.collection.objects.link(o)
    return finish(o,name,tile,0,True)

def shift(o,p):o.location+=Vector(xyz(p));return o

def text(body,p,size=.025,tile=7):
    data=bpy.data.curves.new('Printed '+body,'FONT');data.body=body;data.size=size;data.extrude=0;data.align_x='CENTER'
    o=bpy.data.objects.new('Printed '+body,data);bpy.context.collection.objects.link(o);o.location=xyz(p)
    o.rotation_euler=(math.pi/2,0,0)
    bpy.ops.object.select_all(action='DESELECT');o.select_set(True);bpy.context.view_layer.objects.active=o
    bpy.ops.object.convert(target='MESH');return finish(bpy.context.object,'Print '+body,tile)

def cloth(name,w,d,tile=4,fold=.03,drape=False):
    # Зафиксированные складки; в игре нет симуляции ткани.
    nx=24;nz=24;points=[];faces=[]
    for j in range(nz+1):
        for i in range(nx+1):
            u=i/nx;v=j/nz;x=(u-.5)*w;z=(v-.5)*d
            y=.008+fold*(.6*math.sin(u*15+v*5)+.3*math.sin(v*24-u*4))
            if drape and v>.63:y-=(v-.63)*d*.9
            points.append(xyz((x,y,z)))
    for j in range(nz):
        for i in range(nx):
            a=j*(nx+1)+i;faces.append((a,a+nx+1,a+nx+2,a+1))
    mesh=bpy.data.meshes.new(name);mesh.from_pydata(points,[],faces);mesh.update()
    o=bpy.data.objects.new(name,mesh);bpy.context.collection.objects.link(o)
    sol=o.modifiers.new('Sewn fabric thickness','SOLIDIFY');sol.thickness=.003
    return finish(o,name,tile,0,True)

def begin():
    global PARTS
    PARTS=[]

def export(name,collision=None):
    bpy.ops.object.select_all(action='DESELECT')
    for p in PARTS:p.select_set(True)
    bpy.context.view_layer.objects.active=PARTS[0];bpy.ops.object.join();o=bpy.context.object;o.name=name
    bpy.context.scene.cursor.location=(0,0,0);bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
    bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
    o.data.materials.clear();o.data.materials.append(PAINT_MAT)
    for p in o.data.polygons:p.material_index=0
    deps=bpy.context.evaluated_depsgraph_get();evaluated=o.evaluated_get(deps)
    mesh=evaluated.to_mesh();coords=[evaluated.matrix_world@v.co for v in mesh.vertices]
    dims=[max(v[i] for v in coords)-min(v[i] for v in coords) for i in range(3)]
    tris=sum(len(p.vertices)-2 for p in mesh.polygons);evaluated.to_mesh_clear()
    MANIFEST[name]={'bounds_m':[round(dims[0],4),round(dims[2],4),round(dims[1],4)],'triangles':tris,'collision':collision,'material':'DressingAtlas','ucupaint_layers':4}
    o.data.materials[0]=EXPORT_MAT
    bpy.ops.export_scene.gltf(filepath=str(OUT/(name+'.glb')),export_format='GLB',use_selection=True,export_yup=True,export_materials='EXPORT',export_animations=False)
    o.data.materials[0]=PAINT_MAT;o.hide_set(True);o.hide_render=True;o.select_set(False)
    print('DRESSING_ASSET',name,MANIFEST[name],flush=True)

def little_bottle(p,tile=10,h=.13):
    o=lathe('Service bottle',[(0,.023),(.01,.027),(h*.7,.027),(h*.78,.012),(h,.012)],tile);shift(o,p)
    cyl('Bottle cap',(p[0],p[1]+h,p[2]),(p[0],p[1]+h+.015,p[2]),.015,2)

def carton(p,size=(.28,.20,.22),tile=8,label='SUPPLY'):
    x,y,z=p;w,h,d=size
    box('Dented carton', (x,y+h/2,z),(w,h,d),tile,.008)
    box('Folded lid',(x,y+h+.002,z),(w-.004,.008,d-.004),tile,.002)
    box('Packing tape',(x,y+h+.007,z),(.042,.002,d-.002),0,.0003)
    box('Paper inventory label',(x,y+h*.54,z+d/2+.002),(w*.58,h*.36,.002),7,.0003)
    text(label,(x,y+h*.50,z+d/2+.0038),min(.028,w/13),15)

def can(p,tile=14):
    x,y,z=p;cyl('Tin food',(x,y,z),(x,y+.112,z),.041,tile)
    for h in (.007,.106):cyl('Rolled tin rim',(x,y+h,z),(x,y+h+.004,z),.044,3)
    cyl('Sealed lid',(x,y+.11,z),(x,y+.114,z),.04,3)

def tea_corner():
    begin();lathe('Enamel kettle',[(0,0),(0,.07),(.015,.095),(.09,.103),(.155,.082),(.18,.066)],0)
    cyl('Kettle lid',(0,.18,0),(0,.187,0),.069,3)
    cyl('Lid knob',(0,.187,0),(0,.218,0),.021,2)
    path('Kettle carrying handle',[(-.087,.12,0),(-.09,.28,0),(0,.31,0),(.09,.28,0),(.087,.12,0)],.013,2)
    lathe_obj=lathe('Open kettle spout',[(0,.025),(.105,.017),(.107,.012),(.008,.017)],0)
    lathe_obj.rotation_euler.y=.8;shift(lathe_obj,(.079,.10,0))
    for x,z in [(.25,.025),(.33,-.13)]:
        shift(lathe('Open enamel cup',[(0,0),(0,.034),(.07,.043),(.073,.038),(.008,.029),(.008,0)],0),(x,-.041,z))
        path('Cup handle',[(x+.036,-.025,z),(x+.065,-.016,z),(x+.065,.015,z),(x+.039,.022,z)],.006,3)
    box('Serving tray',(.30,-.05,0),(.36,.018,.35),13,.006)
    export('TeaSet')

def book_stack():
    begin()
    for y,w,d,t in [(0,.25,.18,5),(.029,.23,.17,9),(.053,.26,.19,4)]:
        box('Page block',(0,y+.011,0),(w-.009,.018,d-.007),7,.001)
        for k in (y,y+.022):box('Cloth binding',(0,k,0),(w,.004,d),t,.001)
        box('Spine',(-w/2+.005,y+.012,0),(.012,.024,d),t,.003)
    export('BooksStack')

def wall_clock():
    begin();cyl('Clock rim',(0,0,-.035),(0,0,.008),.20,1)
    cyl('Dial',(0,0,.01),(0,0,.014),.182,7)
    for i in range(12):
        a=i*math.pi/6;box('Dial mark',(math.sin(a)*.15,math.cos(a)*.15,.016),(.009,.023,.002),15,.0004,yaw=-i*30)
    path('Hour hand',[(0,0,.02),(-.055,.077,.02)],.007,15)
    path('Minute hand',[(0,0,.023),(.105,.08,.023)],.005,15)
    cyl('Hand hub',(0,0,.02),(0,0,.03),.013,3);export('WallClock')

def cushion():
    begin();box('Stuffed pillow',(0,.055,0),(.46,.11,.33),5,.04)
    for z in (-.158,.158):path('Pillow seam',[(-.205,.052,z),(0,.063,z),(.205,.052,z)],.002,0)
    export('Cushion')

def maintenance_set():
    begin();box('Cleaning mat',(0,.004,0),(.62,.008,.35),2,.005)
    shift(cloth('Oil rag',.20,.18,7,.008),(.19,.017,.07))
    little_bottle((-.23,.011,-.08),10)
    for i,x in enumerate((-.15,-.06,.03)):
        cyl('Brush handle',(x,.025,-.1),(x+.13,.025,-.1),.008,13)
        for z in (-.018,0,.018):box('Brush bristles',(x+.13,.035,-.1+z),(.034,.027,.008),0,.001)
    box('Parts tray',(0,.025,.08),(.21,.035,.12),3,.008)
    for x,z in [(-.06,.08),(.03,.065),(.05,.09)]:cyl('Loose screw',(x,.05,z),(x+.026,.05,z),.004,3)
    export('WeaponCleaningSet')

def ammo_pack():
    begin();carton((-.095,0,0),(.16,.07,.095),4,'9x19');carton((.095,0,.01),(.16,.075,.095),8,'5.45')
    for x,z in [(-.04,.13),(.055,.14)]:
        box('Magazine body',(x,.04,z),(.065,.08,.025),2,.005,yaw=-12)
        box('Magazine baseplate',(x,.004,z),(.072,.009,.031),3,.001)
    export('AmmoAndMagazines')

def tools():
    begin();box('Repair mat',(0,.003,0),(.66,.006,.4),5,.003)
    for x,z,h in [(-.23,-.03,.16),(-.1,.08,.20)]:
        cyl('Driver shaft',(x,.021,z),(x+h*.6,.021,z),.004,3)
        cyl('Driver grip',(x+h*.6,.021,z),(x+h,.021,z),.017,9)
        box('Grip end',(x+h,.021,z),(.012,.025,.025),2,.003)
    path('Pliers steel',[(-.04,.026,-.13),(.01,.026,-.06),(.03,.026,-.02)],.011,3)
    path('Pliers grip',[(.03,.026,-.02),(.10,.026,.075)],.015,9)
    path('Pliers other jaw',[(.04,.024,-.14),(.01,.024,-.06),(-.01,.024,-.02)],.01,3)
    path('Pliers other grip',[(-.01,.024,-.02),(-.075,.024,.07)],.015,9)
    box('Fastener tray',(.20,.019,.06),(.18,.035,.16),12,.008)
    for x,z in [(.16,.03),(.21,.09),(.23,.055),(.175,.095)]:cyl('Fastener',(x,.04,z),(x+.025,.04,z),.004,3)
    export('RepairTools')

def organizer():
    begin();box('Drawer cabinet',(0,.25,0),(.66,.5,.20),1,.006)
    for y in (.085,.245,.405):
        for x in (-.235,-.08,.08,.235):
            box('Small parts drawer',(x,y,.018),(.143,.145,.19),11,.005)
            box('Drawer pull',(x,y+.033,.128),(.055,.009,.014),2,.002)
            box('Paper drawer label',(x,y-.028,.117),(.072,.023,.0015),7,.0002)
    export('PartsOrganizer')

def toolbox():
    begin();box('Toolbox bottom',(0,.032,0),(.48,.06,.26),9,.008)
    for x in (-.232,.232):box('Toolbox end',(x,.12,0),(.017,.20,.26),9,.004)
    for z in (-.122,.122):box('Toolbox wall',(0,.12,z),(.46,.20,.017),9,.004)
    box('Open toolbox lid',(0,.27,-.16),(.48,.018,.25),9,.005)
    for x in (-.15,.15):box('Lid hinge',(x,.21,-.13),(.033,.03,.03),3,.005)
    path('Carry handle',[(-.12,.20,.015),(-.12,.31,.015),(.12,.31,.015),(.12,.20,.015)],.011,3)
    for x in (-.14,0,.14):cyl('Tool grip',(x,.075,-.08),(x+.045,.10,.08),.016,2)
    export('OpenToolbox')

def meter_panel():
    begin();box('Meter enclosure',(0,.31,0),(.62,.62,.085),1,.011)
    for x in (-.18,0,.18):
        box('Gauge surround',(x,.43,.053),(.14,.12,.018),2,.005)
        box('Gauge dial',(x,.43,.063),(.12,.10,.002),7,.001)
        for i in range(7):
            a=math.radians(-65+i*22)
            path('Gauge graduation',[(x+math.sin(a)*.041,.438+math.cos(a)*.036,.067),(x+math.sin(a)*.045,.438+math.cos(a)*.042,.067)],.001,15)
        path('Gauge pointer',[(x,.405,.067),(x+(.026 if x<0 else -.02),.463,.067)],.0015,15)
        text('A' if x<0 else ('V' if x==0 else 'kW'),(x,.397,.068),.016,15)
    for x in (-.19,-.065,.065,.19):cyl('Control knob',(x,.17,.047),(x,.17,.075),.023,2)
    for x in (-.255,.255):
        for y in (.06,.56):cyl('Mounting screw',(x,y,.044),(x,y,.054),.008,3)
    text('POWER / LOAD',(0,.28,.056),.033)
    export('MeterPanel')

def cable_run():
    begin()
    for x in (-.035,.035):path('Insulated service cable',[(x,0,0),(x,.24,0),(x,.75,-.01),(x,.92,-.05)],.012,2)
    for y in (.1,.36,.68):box('Cable clamp',(0,y,.003),(.11,.025,.044),3,.003)
    box('Junction box',(0,1.04,-.045),(.24,.24,.09),1,.012)
    for x in (-.075,.075):
        for y in (.965,1.115):cyl('Cover screws',(x,y,.001),(x,y,.007),.007,3)
    export('CableJunction')

def generator_detail():
    begin()
    # Плоскость обслуживания вдоль передней стороны существующего генератора.
    for x in (-.8,.8):
        box('Vibration isolator',(x,.08,.42),(.15,.09,.14),2,.011)
        for z in (.37,.47):cyl('Base fixing',(x,.125,z),(x,.14,z),.017,3)
    box('Service pan',(0,.015,.10),(1.65,.028,.8),12,.015)
    for z in (-.3,.5):box('Pan rim',(0,.052,z),(1.65,.075,.018),12,.003)
    for x in (-.81,.81):box('Pan end',(x,.052,.10),(.025,.075,.8),12,.003)
    path('Fuel service hose',[(-.78,.32,.52),(-.96,.22,.61),(-1.05,.13,.36),(-.90,.19,.05)],.016,2)
    for x in (-.71,.68):cyl('Hose coupling',(x,.36,.49),(x,.36,.56),.027,3)
    box('External service gauge',(.52,.54,.51),(.17,.16,.04),2,.008)
    box('Gauge face',(.52,.54,.535),(.145,.13,.002),7,.001)
    path('Gauge needle',[(.47,.505,.538),(.55,.57,.538)],.002,15)
    export('GeneratorServiceDetails')

def extinguisher():
    begin();lathe('Extinguisher bottle',[(0,.05),(.03,.068),(.36,.068),(.405,.033),(.43,.025)],9)
    box('Mount bracket',(0,.25,-.075),(.10,.28,.027),1,.004)
    path('Discharge hose',[(.025,.435,0),(.11,.43,0),(.10,.18,.02)],.01,2)
    box('Operating lever',(0,.455,0),(.12,.025,.037),3,.005)
    text('FIRE',(0,.24,.071),.039,7);export('FireExtinguisher')

def cloth_items():
    begin();cloth('Draped lounge blanket',.86,.88,4,.035,True);export('DrapedBlanket')
    begin();cloth('Folded towel',.38,.28,5,.012);box('Folded towel layers',(0,-.018,0),(.38,.032,.28),5,.01);export('FoldedTowel')
    begin();cloth('Bed blanket',.84,1.15,5,.035);export('BedBlanket')
    begin();cloth('Contact rag',.27,.22,7,.01);export('CleaningRag')

def carton_variants():
    begin();carton((-.17,0,.03),(.30,.23,.26),8,'FOOD');carton((.18,0,-.03),(.31,.28,.26),0,'MEDICAL');export('MixedCartons')
    begin()
    for x,z in [(-.23,-.07),(-.1,-.08),(.035,-.08),(.17,-.08),(-.19,.065),(-.04,.06),(.11,.07)]:can((x,0,z),14 if z<0 else 10)
    export('FoodStock')
    begin()
    for x in (-.2,0,.2):
        for z in (-.08,.08):
            shift(lathe('Water container',[(0,.061),(.015,.071),(.21,.070),(.265,.023),(.29,.023)],11),(x,0,z))
            cyl('Container cap',(x,.29,z),(x,.306,z),.026,0)
    export('WaterStock')
    begin()
    for x,y,z,s,t in [(-.16,0,.025,(.22,.08,.15),0),(.105,0,-.03,(.20,.12,.15),0),(-.16,.09,.025,(.22,.07,.15),7)]:
        carton((x,y,z),s,t,'MED')
        box('Medical stripe',(x,y+s[1]*.56,z+s[2]/2+.004),(.036,.035,.002),9,.001)
    export('MedicalStock')
    begin();carton((0,0,0),(.34,.22,.22),8,'BATTERIES')
    for x in (-.10,-.025,.05):cyl('Battery',(x,.24,0),(x,.30,0),.012,2)
    export('BatteryStock')

def sack():
    begin();box('Filled ration sack',(0,.15,0),(.34,.30,.24),4,.055)
    path('Tied cloth mouth',[(-.13,.28,0),(0,.34,.018),(.13,.28,0)],.025,4)
    path('Binding cord',[(-.10,.30,.026),(0,.31,.035),(.10,.30,.026)],.003,0)
    export('SupplySack')

def trolley():
    begin();box('Hand truck platform',(0,.04,.095),(.5,.04,.35),1,.008)
    for x in (-.215,.215):
        path('Hand truck frame',[(x,.12,0),(x,.78,0),(x,.98,-.025)],.02,1)
        cyl('Wheel axle',(x-.045,.115,0),(x+.045,.115,0),.027,3)
        cyl('Rubber wheel',(x-.027,.115,0),(x+.027,.115,0),.105,2,verts=48)
        cyl('Grip',(x,.82,-.025),(x,.98,-.025),.027,2)
    for y in (.26,.6,.79):cyl('Cross brace',(-.215,y,0),(.215,y,0),.015,1)
    export('HandTruck',{'center':[0,.5,.12],'size':[.62,1.0,.42]})

def clipboard():
    begin();box('Clipboard',(0,.006,0),(.22,.012,.30),13,.008)
    box('Inventory paper',(0,.014,0),(.202,.001,.276),7,.002)
    box('Spring clip',(0,.025,-.117),(.08,.012,.028),3,.004)
    for z in (-.08,-.05,-.02,.01,.04,.07,.10):box('Written inventory rule',(0,.0155,z),(.16,.0005,.001),15,0)
    export('InventoryClipboard')

def calculator():
    begin();box('Calculator body',(0,.017,0),(.11,.035,.17),2,.012)
    box('LCD',(0,.037,-.05),(.082,.002,.025),1,.002)
    for x in (-.031,0,.031):
        for z in (-.005,.025,.055):box('Calculator key',(x,.039,z),(.022,.009,.023),0,.002)
    export('Calculator')

def scales():
    begin();box('Scales enclosure',(0,.043,0),(.34,.086,.26),0,.015)
    box('Weighing pan',(0,.091,-.015),(.3,.017,.20),3,.008)
    box('Display',(0,.062,.135),(.10,.029,.003),2,.003)
    text('0.000',(0,.055,.138),.017,7);export('CounterScales')

def clothes_rail():
    begin();box('Coat rail',(0,.88,0),(.60,.07,.025),13,.006)
    for x in (-.22,0,.22):path('Coat hook',[(x,.89,.02),(x,.84,.07),(x,.86,.09)],.007,3)
    # Ткань куртки: плечи, свисающие рукава, ворот и центральный шов.
    box('Jacket body',(0,.50,.095),(.37,.53,.065),1,.033)
    for x in (-.205,.205):
        o=box('Jacket sleeve',(x,.50,.08),(.12,.50,.062),1,.024)
        o.rotation_euler.y=.14 if x<0 else -.14
    path('Jacket collar',[(-.08,.77,.12),(0,.72,.135),(.08,.77,.12)],.015,4)
    box('Jacket zipper',(0,.49,.132),(.006,.46,.003),3,.001)
    for x in (-.10,.10):box('Patch pocket',(x,.36,.135),(.12,.11,.018),1,.006)
    export('HangingJacket')

def headset():
    begin();path('Headset headband',[(-.105,.04,0),(-.10,.17,0),(0,.225,0),(.10,.17,0),(.105,.04,0)],.012,2)
    for x in (-.105,.105):box('Earcup',(x,.047,0),(.06,.11,.075),1,.025)
    path('Headset lead',[(.10,.02,.01),(.17,.01,.04),(.23,.01,-.06),(.14,.01,-.11)],.0025,2)
    export('HearingProtection')

def gloves():
    begin()
    for x in (-.07,.065):
        box('Glove palm',(x,.014,0),(.085,.028,.09),4,.01)
        box('Glove cuff',(x,.012,.064),(.09,.025,.055),2,.006)
        for i in range(4):box('Glove finger',(x-.03+i*.020,.013,-.068),(.017,.026,.055-(i==0)*.009),4,.007)
        o=box('Glove thumb',(x-.065,.013,-.015),(.027,.028,.052),4,.01);o.rotation_euler.z=.5
    export('WorkGloves')

def water_bucket():
    begin();lathe('Open cleaning bucket',[(0,.085),(.02,.095),(.24,.135),(.245,.127),(.035,.089)],11)
    path('Bucket handle',[(-.13,.20,0),(-.12,.36,0),(0,.40,0),(.12,.36,0),(.13,.20,0)],.005,3)
    path('Brush shaft',[(.04,.05,0),(.16,.65,.04)],.012,13)
    box('Cleaning brush head',(.02,.03,0),(.18,.04,.055),0,.004)
    export('CleaningBucket')

def wall_board():
    begin();box('Notice frame',(0,0,0),(1.0,.70,.033),13,.008)
    box('Cork backing',(0,0,.024),(.94,.64,.009),8,.005)
    for x,y,w,h in [(-.26,.09,.25,.32),(.03,.15,.22,.20),(.29,-.02,.20,.31),(-.03,-.18,.25,.12)]:
        box('Notice paper',(x,y,.031),(w,h,.002),7,.001)
        cyl('Notice pin',(x,y+h/2-.02,.033),(x,y+h/2-.02,.042),.005,9)
        for dy in (-.05,0,.05):box('Printed rule',(x,y+dy,.033),(w*.65,.002,.0008),15,0)
    export('NoticeBoard')

def tea_station():
    begin();box('Prep surface',(0,.86,0),(1.10,.05,.58),13,.012)
    for x in (-.49,.49):
        for z in (-.23,.23):box('Steel leg',(x,.42,z),(.035,.84,.035),1,.005)
    box('Lower shelf',(0,.22,0),(1.04,.03,.51),1,.006)
    box('Hotplate',(0,.906,0),(.31,.045,.27),0,.009)
    cyl('Hotplate ring',(0,.93,0),(0,.942,0),.115,2)
    box('Control knob',(.10,.91,.145),(.035,.022,.013),2,.003)
    path('Appliance lead',[(.15,.91,-.12),(.38,.86,-.24),(.43,.55,-.24),(.46,.18,-.24)],.003,2)
    export('TeaStation',{'center':[0,.44,0],'size':[1.1,.88,.58]})

def exhaust_connection():
    begin()
    points=[(0,0,0),(0,.3,0),(0,.43,-.16),(0,.43,-1.85)]
    outer=path('Exhaust duct',points,.058,12)
    solid=outer.modifiers.new('Open tube inner wall','SOLIDIFY');solid.thickness=.005;solid.offset=-1
    for z in (-.45,-1.62):
        box('Wall support',(0,.50,z),(.20,.14,.027),1,.004)
        cyl('Duct clamp',(0,.43,z-.018),(0,.43,z+.018),.067,3)
    cyl('Wall flange',(0,.43,-1.83),(0,.43,-1.89),.115,12)
    for x,y in [(-.075,.43),(.075,.43),(0,.355),(0,.505)]:cyl('Flange bolt',(x,y,-1.91),(x,y,-1.88),.01,3)
    export('ExhaustConnection')

tea_corner();book_stack();wall_clock();cushion();maintenance_set();ammo_pack();tools();organizer();toolbox()
meter_panel();cable_run();generator_detail();extinguisher();cloth_items();carton_variants();sack();trolley()
clipboard();calculator();scales();clothes_rail();headset();gloves();water_bucket();wall_board()
tea_station();exhaust_connection()

for o in bpy.context.scene.objects:o.hide_set(False)
bpy.context.scene.render.engine='BLENDER_EEVEE'
candidate=SRC/'shelter_dressing.blend'
if candidate.exists():shutil.copy2(candidate,SRC/'shelter_dressing_previous.blend')
bpy.ops.wm.save_as_mainfile(filepath=str(candidate))
(OUT/'manifest.json').write_text(json.dumps(MANIFEST,ensure_ascii=False,indent=2),encoding='utf-8')
(SRC/'license.txt').write_text('Own RING meshes and painted layers, Blender 5.2.2 / Ucupaint 2.4.9. Reuses the existing CC0 Poly Haven photo textures from assets/shelter/textures; exact sources and licenses: assets/ASSET_CREDITS.md.\n',encoding='utf-8')
print('DRESSING_DONE',len(MANIFEST),sum(v['triangles'] for v in MANIFEST.values()),flush=True)
