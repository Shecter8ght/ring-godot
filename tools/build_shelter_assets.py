"""Фиксированный authored kit убежища: bpy → GLB. Ни layout, ни assets не генерируются в игре.

Blender 5.2, --background --factory-startup --python tools/build_shelter_assets.py
Все координаты функций — Godot X/Y/Z (метры), экспорт glTF Y-up.
"""
from __future__ import annotations
import bpy, math, json, sys
from pathlib import Path
from mathutils import Vector

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'assets/shelter/models'; OUT.mkdir(parents=True,exist_ok=True)
SRC=ROOT/'_asset_src/shelter'; SRC.mkdir(parents=True,exist_ok=True)
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
bpy.context.scene.unit_settings.system='METRIC'
MATS={}; PARTS=[]; ASSETS={}; COLLISIONS=[]

COLORS={'RawConcrete':(.42,.41,.38),'PaintedConcrete':(.26,.34,.29),'IndustrialConcreteFloor':(.42,.41,.35),'WetConcrete':(.27,.28,.24),'DampConcrete':(.30,.32,.27),'PaintedSteel':(.22,.29,.23),'OchreSteel':(.49,.34,.10),'BareSteel':(.29,.32,.32),'RustedSteel':(.33,.17,.09),'GalvanizedSteel':(.47,.52,.52),'DirtyAluminum':(.38,.41,.39),'OldWood':(.31,.22,.13),'RawWood':(.48,.36,.20),'Rubber':(.05,.06,.05),'OldPlastic':(.12,.12,.10),'Canvas':(.38,.33,.21),'MilitaryFabric':(.21,.28,.16),'Leatherette':(.25,.13,.07),'Glass':(.10,.13,.11),'Oil':(.03,.03,.02),'PuddleWater':(.22,.25,.24),'WornCarpet':(.28,.15,.08),'Paper':(.72,.68,.50),'Cardboard':(.43,.34,.19),'RedPaint':(.36,.10,.06),'IndustrialTrim':(.46,.36,.12),'Labels':(.67,.62,.46),'PlanningMap':(.68,.63,.46),'WarmEmitter':(1,.65,.28),'CoolEmitter':(.84,.92,1),'Screen':(.01,.015,.01)}

def mat(name):
    if name not in MATS:
        m=bpy.data.materials.new(name); m.diffuse_color=(*COLORS[name],1); m.use_nodes=True
        bs=m.node_tree.nodes.get('Principled BSDF'); bs.inputs['Base Color'].default_value=(*COLORS[name],1)
        bs.inputs['Roughness'].default_value=.65
        if 'Emitter' in name:
            bs.inputs['Emission Color'].default_value=(*COLORS[name],1); bs.inputs['Emission Strength'].default_value=2
        MATS[name]=m
    return MATS[name]

def xyz(v):return (v[0],-v[2],v[1])

def finish(o,name,material,bevel=0):
    o.name=name; bpy.context.view_layer.objects.active=o
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    if bevel:
        mod=o.modifiers.new('Manufactured edge radius','BEVEL'); mod.width=bevel; mod.segments=2
        bpy.ops.object.modifier_apply(modifier=mod.name)
        mod=o.modifiers.new('Face weighted normals','WEIGHTED_NORMAL'); mod.keep_sharp=True
        bpy.ops.object.modifier_apply(modifier=mod.name)
    o.data.materials.append(mat(material))
    # UV в метрах по основной оси поверхности: нет растяжения у стен, полов и фасок.
    uv=o.data.uv_layers.active or o.data.uv_layers.new(name='UVMap')
    tile={'RawConcrete':3,'PaintedConcrete':3,'IndustrialConcreteFloor':4,'WetConcrete':3,'OldWood':2,'WornCarpet':2}.get(material,1)
    for p in o.data.polygons:
        axis=max(range(3),key=lambda i:abs(p.normal[i])); axes=[i for i in range(3) if i!=axis]
        for li in p.loop_indices:
            v=o.data.vertices[o.data.loops[li].vertex_index].co
            uv.data[li].uv=(v[axes[0]]/tile,v[axes[1]]/tile)
    PARTS.append(o); return o

def box(name,pos,size,m='PaintedSteel',bevel=.01,yaw=0):
    bpy.ops.mesh.primitive_cube_add(size=1,location=xyz(pos)); o=bpy.context.object
    o.scale=(size[0],size[2],size[1]); o.rotation_euler.z=math.radians(yaw)
    return finish(o,name,m,min(bevel,min(size)*.25))

def cyl(name,a,b,r,m='BareSteel',r2=None,verts=16):
    va=Vector(xyz(a)); vb=Vector(xyz(b)); delta=vb-va
    bpy.ops.mesh.primitive_cone_add(vertices=verts,radius1=r,radius2=r if r2 is None else r2,depth=delta.length,location=(va+vb)*.5)
    o=bpy.context.object; o.rotation_euler=delta.to_track_quat('Z','Y').to_euler()
    return finish(o,name,m,.0015 if r>.01 else 0)

def curve(name,points,r,m='BareSteel'):
    c=bpy.data.curves.new(name,'CURVE'); c.dimensions='3D'; c.bevel_depth=r; c.bevel_resolution=2
    s=c.splines.new('POLY'); s.points.add(len(points)-1)
    for p,v in zip(s.points,points):p.co=(*xyz(v),1)
    o=bpy.data.objects.new(name,c); bpy.context.collection.objects.link(o)
    bpy.ops.object.select_all(action='DESELECT'); o.select_set(True); bpy.context.view_layer.objects.active=o
    bpy.ops.object.convert(target='MESH'); return finish(bpy.context.object,name,m)

def face(name,points,m,uvcoords=None):
    mesh=bpy.data.meshes.new(name); mesh.from_pydata([xyz(p) for p in points],[],[list(range(len(points)))]);mesh.update()
    o=bpy.data.objects.new(name,mesh);bpy.context.collection.objects.link(o); finish(o,name,m)
    if uvcoords:
        for l,uv in zip(o.data.uv_layers.active.data,uvcoords):l.uv=uv
    return o

def begin():
    global PARTS,COLLISIONS
    PARTS=[];COLLISIONS=[]

def collision(pos,size,yaw=0):COLLISIONS.append({'pos':pos,'size':size,'yaw':yaw})

def export(name,screen=False):
    # Один mesh на сборку; material slots общие, screen отдельный для сохранения TV shader.
    bpy.ops.object.select_all(action='DESELECT')
    screens=[p for p in PARTS if p.name=='Screen']
    parts=[p for p in PARTS if p.name!='Screen']
    for p in parts:p.select_set(True)
    bpy.context.view_layer.objects.active=parts[0]; bpy.ops.object.join(); main=bpy.context.object
    main.name=name
    # Pivot в нуле сборки; это важно для повторяемых размеров и transforms в .tscn.
    bpy.context.scene.cursor.location=(0,0,0); bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
    bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
    # Удаление повторных material slots после join: меньше draw calls.
    unique=[]; mapping={}
    for i,m in enumerate(main.data.materials):
        if m.name not in [a.name for a in unique]:unique.append(m)
        mapping[i]=next(k for k,a in enumerate(unique) if a.name==m.name)
    polygon_materials=[mapping[p.material_index] for p in main.data.polygons]
    main.data.materials.clear()
    for m in unique:main.data.materials.append(m)
    for p,i in zip(main.data.polygons,polygon_materials):p.material_index=i
    for p in screens:p.select_set(True)
    selected=list(bpy.context.selected_objects)
    # Сохраняем метрические UV0 и печатные атласы. Выбранный в проекте SDFGI не требует UV2.
    bounds=[main.matrix_world@Vector(v) for v in main.bound_box]
    dims=[max(v[i] for v in bounds)-min(v[i] for v in bounds) for i in range(3)]
    ASSETS[name]={'collisions':COLLISIONS.copy(),'bounds_m': [round(dims[0],4),round(dims[2],4),round(dims[1],4)],'triangles':sum(len(p.vertices)-2 for o in selected if o.type=='MESH' for p in o.data.polygons)}
    bpy.ops.export_scene.gltf(filepath=str(OUT/(name+'.glb')),export_format='GLB',use_selection=True,export_yup=True,export_texcoords=True,export_normals=True,export_materials='EXPORT',export_animations=False)
    for o in selected:o.hide_set(True);o.select_set(False)
    print('SHELTER_ASSET',name,ASSETS[name]['bounds_m'],flush=True)

def legs(w,d,h,m='PaintedSteel'):
    for x in [-w/2+.06,w/2-.06]:
        for z in [-d/2+.06,d/2-.06]:box('Leg',(x,h/2,z),(.055,h,.055),m,.006)

def table(name,w,d,h):
    begin();legs(w,d,h-.045);box('Wood top',(0,h-.035,0),(w,.07,d),'OldWood',.016)
    box('Apron',(0,h-.18,0),(w-.15,.12,d-.12),'PaintedSteel',.01)
    collision((0,h/2,0),(w,h,d)); export(name)

def shelf(name,w=1.4):
    begin()
    for x in [-w/2+.03,w/2-.03]:
        for z in [-.24,.24]:box('Angle upright',(x,1.05,z),(.04,2.1,.04),'PaintedSteel',.005)
    for y in [.15,.63,1.11,1.59,2.06]:
        box('Shelf tray',(0,y,0),(w,.04,.56),'GalvanizedSteel',.005)
        box('Shelf lip',(0,y+.035,.285),(w,.065,.018),'PaintedSteel',.003)
    box('Brace cross',(0,1,-.25),(w-.1,.025,.025),'BareSteel',.003,yaw=0)
    collision((0,1.05,0),(w,2.1,.56));export(name)

def locker():
    begin()
    box('Back',(0,1,-.27),(.68,2,.035));box('Top',(0,2,0),(.74,.045,.60))
    box('Plinth',(0,.07,0),(.72,.14,.58),'Rubber')
    for x in [-.35,.35]:box('Cabinet side',(x,1,0),(.04,2,.58))
    box('Door',(0,1,.29),(.67,1.88,.035),'PaintedSteel',.012)
    for y in [1.62,1.69,1.76,.28,.35]:box('Louver slit',(0,y,.314),(.38,.019,.008),'Rubber',0)
    cyl('Pull',( .23,.92,.35),(.23,1.10,.35),.018)
    for y in [.48,1.55]:box('Hinge',(-.32,y,.316),(.025,.12,.024),'BareSteel')
    face('Inventory label',[(-.13,1.44,.32),(.13,1.44,.32),(.13,1.51,.32),(-.13,1.51,.32)],'Labels',[(0,.88),(1,.88),(1,1),(0,1)])
    collision((0,1,0),(.74,2,.60));export('Locker')

def crate(name='Case',cardboard=False):
    begin(); m='Cardboard' if cardboard else 'MilitaryFabric'
    box('Case body',(0,.23,0),(.76,.46,.46),m,.035)
    box('Lid',(0,.45,0),(.79,.06,.49),'Cardboard' if cardboard else 'PaintedSteel',.012)
    for x in [-.25,.25]:box('Strap',(x,.245,0),(.036,.5,.48),'Rubber',.007)
    for x in [-.28,.28]:box('Latch',(x,.34,.255),(.07,.1,.026),'BareSteel',.009)
    cyl('Handle',(-.1,.26,.275),(.1,.26,.275),.02,'Rubber')
    collision((0,.26,0),(.79,.52,.50));export(name)

def couch():
    begin(); legs(2.25,.82,.2,'OldWood')
    box('Sofa base',(0,.3,0),(2.25,.32,.86),'Leatherette',.09)
    box('Upholstered back',(0,.69,-.34),(2.25,.74,.24),'Leatherette',.09)
    for x in [-1.02,1.02]:box('Rolled arm',(x,.55,.05),(.25,.5,.90),'Leatherette',.095)
    for x in [-.63,0,.63]:
        box('Seat cushion',(x,.51,.08),(.59,.18,.65),'Leatherette',.07)
        box('Back cushion',(x,.85,-.19),(.59,.48,.16),'Leatherette',.07)
        for k in [-.17,.17]:cyl('Upholstery button',(x+k,.85,-.10),(x+k,.85,-.083),.015,'OldWood',verts=12)
    box('Folded throw',(.72,.63,.06),(.36,.065,.7),'Canvas',.03)
    collision((0,.48,0),(2.25,.96,.90));export('Couch')

def chair():
    begin(); legs(.45,.47,.43);box('Seat',(0,.45,0),(.46,.045,.45),'OldWood',.012)
    for x in [-.19,.19]:box('Back upright',(x,.72,-.19),(.035,.59,.035),'PaintedSteel',.008)
    box('Backrest',(0,.83,-.19),(.44,.22,.045),'OldWood',.018)
    collision((0,.43,0),(.46,.86,.47));export('Chair')

def bed():
    begin();legs(.86,1.96,.40);box('Bed frame',(0,.39,0),(.9,.09,2),'PaintedSteel')
    box('Mattress',(0,.49,0),(.85,.16,1.95),'Canvas',.06)
    box('Sleeping blanket',(0,.595,.22),(.86,.08,1.37),'MilitaryFabric',.04)
    box('Pillow',(0,.64,-.67),(.56,.14,.36),'Canvas',.08)
    for z in [-.98,.98]:
        for x in [-.43,.43]:cyl('Bed post',(x,0,z),(x,.75,z),.025)
        cyl('Bed rail',(-.43,.74,z),(.43,.74,z),.025)
    for i in range(6):curve('Blanket fold',[(-.42,.636,-.41+i*.22),(0,.653,-.4+i*.22),(.42,.636,-.4+i*.22)],.008,'Canvas')
    collision((0,.35,0),(.9,.7,2));export('Bed')

def blast_door():
    begin()
    for x in [-1.17,1.17]:box('Massive jamb',(x,1.2,0),(.18,2.4,.35),'BareSteel',.018)
    box('Door lintel',(0,2.35,0),(2.52,.18,.35),'BareSteel',.014)
    box('Sealed leaf',(0,1.14,0),(2.18,2.25,.18),'PaintedSteel',.018)
    for y in [.25,.7,1.2,1.7,2.1]:box('Leaf stiffener',(0,y,.11),(1.99,.07,.055),'BareSteel',.005)
    for x in [-.7,0,.7]:box('Vertical stiffener',(x,1.2,.12),(.07,2,.06),'PaintedSteel',.006)
    for y in [.4,1.3,2.1]:cyl('Hinge',(1.03,y-.085,.1),(1.03,y+.085,.1),.065,'BareSteel')
    # Круглый штурвал не имитация плоским диском: обод и 4 спицы.
    pts=[(.62+.23*math.cos(i*math.tau/32),1.18+.23*math.sin(i*math.tau/32),.24) for i in range(33)]
    curve('Handwheel',pts,.025,'RedPaint')
    for a in [0,90,180,270]:cyl('Wheel spoke',(.62,1.18,.24),(.62+.21*math.cos(math.radians(a)),1.18+.21*math.sin(math.radians(a)),.24),.015)
    face('Warning plaque',[(-.85,1.75,.158),(-.05,1.75,.158),(-.05,1.89,.158),(-.85,1.89,.158)],'Labels',[(0,.375),(1,.375),(1,.5),(0,.5)])
    collision((0,1.18,0),(2.55,2.42,.35));export('BlastDoor')

def generator():
    begin()
    for x in [-1.15,1.15]:box('Isolation foot',(x,.12,0),(.24,.24,1.15),'Rubber',.035)
    box('Skid',(0,.25,0),(2.8,.15,1.35),'BareSteel',.018)
    for x in [-1.24,1.24]:
        for z in [-.53,.53]:cyl('Tube frame',(x,.30,z),(x,1.43,z),.045,'BareSteel')
        cyl('Tube rail',(x,1.43,-.53),(x,1.43,.53),.045)
    box('Diesel acoustic enclosure',(0,.89,0),(2.43,1.15,1.12),'OchreSteel',.025)
    for x in [-.72,.65]:box('Access cover',(x,.85,.572),(1.02,.80,.025),'OchreSteel',.012)
    for i in range(14):box('Cooling louver',(-.72,.5+i*.041,.591),(.80,.017,.016),'Rubber',.003)
    box('Control panel',(.66,1.05,.60),(.6,.3,.035),'Rubber',.015)
    for x in [.52,.72]:cyl('Gauge glass',(x,1.10,.63),(x,1.1,.65),.048,'Glass',verts=24)
    for x in [.44,.58,.72,.86]:cyl('Switch',(x,.97,.63),(x,.97,.66),.019,'RedPaint',verts=12)
    box('Fuel tank',(.35,1.55,-.08),(1.1,.20,.74),'OchreSteel',.02)
    cyl('Tank cap',(.73,1.64,-.08),(.73,1.70,-.08),.064)
    curve('Exhaust',[(-.8,1.4,-.32),(-.8,1.78,-.32),(-1.02,1.98,-.32),(-1.05,2.6,-.32)],.055,'RustedSteel')
    cyl('Silencer',(-1.05,1.98,-.32),(-1.05,2.40,-.32),.13,'BareSteel')
    face('Diesel label',[(-.48,1.23,.58),(.26,1.23,.58),(.26,1.38,.58),(-.48,1.38,.58)],'Labels',[(0,.25),(1,.25),(1,.375),(0,.375)])
    collision((0,.85,0),(2.8,1.7,1.35));export('Generator')

def workshop():
    begin();legs(2.4,.82,.86);box('Worktop',(0,.89,0),(2.4,.09,.86),'OldWood',.018)
    box('Drawer cabinet',(.68,.42,0),(.74,.78,.71),'RedPaint',.018)
    for y in [.2,.38,.56,.74]:
        box('Drawer front',(.68,y,.366),(.69,.15,.035),'RedPaint',.008)
        cyl('Drawer pull',(.45,y,.407),(.91,y,.407),.015,'BareSteel')
    box('Tool board',(0,1.62,-.42),(2.38,1.12,.06),'OldWood',.005)
    for x in [-.9,-.66,-.4,-.14,.14,.4,.66,.9]:
        for y in [1.24,1.44,1.64,1.84,2.04]:cyl('Peg hole',(x,y,-.376),(x,y,-.366),.009,'Rubber',verts=8)
    for i in range(6):
        x=-.9+i*.29
        cyl('Wrench shaft',(x,1.44,-.33),(x,1.83,-.33),.012,'BareSteel')
        curve('Wrench open head',[(x-.042,1.90,-.33),(x-.046,1.84,-.33),(x,1.80,-.33),(x+.046,1.84,-.33),(x+.042,1.90,-.33)],.013,'BareSteel')
    box('Vise base',(-.77,.975,.17),(.34,.075,.3),'BareSteel',.008)
    for z in [.08,.27]:box('Vise jaws',(-.77,1.065,z),(.32,.12,.085),'BareSteel',.004)
    cyl('Vise screw',(-.77,1.015,.24),(-.77,1.015,.48),.026)
    cyl('Vise lever',(-.94,1.015,.48),(-.60,1.015,.48),.012)
    collision((0,.45,0),(2.4,.9,.86));collision((0,1.63,-.43),(2.4,1.1,.07));export('Workbench')

def electrical():
    begin();box('Electrical cabinet',(0,.9,0),(.85,1.8,.36),'PaintedSteel',.018)
    box('Panel door',(0,.99,.2),(.78,1.5,.035),'DirtyAluminum',.012)
    box('Breakers window',(0,1.3,.225),(.58,.31,.02),'Rubber',.005)
    for x in [-.23,-.115,0,.115,.23]:box('Breaker',(x,1.31,.25),(.07,.2,.03),'OldPlastic',.004)
    cyl('Door handle',(.25,.67,.26),(.25,.82,.26),.019)
    face('High voltage',[(-.17,.87,.229),(.17,.87,.229),(.17,1.04,.229),(-.17,1.04,.229)],'Labels',[(0,.125),(1,.125),(1,.25),(0,.25)])
    collision((0,.9,0),(.85,1.8,.42));export('ElectricalCabinet')

def radio():
    begin();box('Radio shell',(0,.145,0),(.48,.29,.16),'OldPlastic',.025)
    for x in [-.15,.15]:
        cyl('Speaker grille',(x,.15,.083),(x,.15,.089),.087,'Rubber',verts=24)
        for i in [-3,-2,-1,0,1,2,3]:box('Speaker slot',(x+i*.02,.15,.095),(.005,.12,.004),'BareSteel',0)
    box('Frequency dial',(0,.21,.087),(.11,.065,.006),'OchreSteel',.004)
    for x in [-.03,.03]:cyl('Tuning knob',(x,.09,.087),(x,.09,.105),.019,'Rubber')
    curve('Carry handle',[(-.16,.27,0),(-.16,.35,0),(.16,.35,0),(.16,.27,0)],.018,'Rubber')
    cyl('Aerial',(.19,.28,-.05),(.12,.72,-.05),.003,'BareSteel',verts=8)
    export('Radio')

def television():
    begin();box('TV housing',(0,0,-.045),(1.10,.66,.10),'OldPlastic',.022)
    box('Inset bezel',(0,0,.012),(1.04,.60,.025),'Rubber',.015)
    face('Screen',[(-.495,-.278,.03),(.495,-.278,.03),(.495,.278,.03),(-.495,.278,.03)],'Screen',[(0,1),(1,1),(1,0),(0,0)])
    box('Stand stem',(0,-.39,-.03),(.08,.20,.07),'OldPlastic',.02)
    box('Stand foot',(0,-.49,.01),(.50,.025,.22),'OldPlastic',.008)
    export('Television',screen=True)

def bottles():
    begin()
    for x in [-.10,.10]:
        cyl('Amber bottle',(x,0,0),(x,.21,0),.032,'Glass',r2=.028,verts=24)
        cyl('Bottle shoulder',(x,.21,0),(x,.25,0),.028,'Glass',r2=.012,verts=24)
        cyl('Bottle neck',(x,.25,0),(x,.31,0),.012,'Glass',verts=16)
        cyl('Cap',(x,.305,0),(x,.318,0),.014,'OchreSteel')
        cyl('Paper label',(x,.09,0),(x,.16,0),.0324,'Paper',verts=24)
    export('Beer')

def canister():
    begin();box('Fuel can',(0,.26,0),(.33,.50,.18),'PaintedSteel',.032)
    curve('Handle',[(-.1,.48,0),(-.1,.58,0),(.1,.58,0),(.1,.48,0)],.021,'BareSteel')
    cyl('Cap',(.12,.47,0),(.12,.53,0),.035)
    for z in [-.097,.097]:
        curve('Pressed rib',[(-.10,.10,z),(.10,.39,z),(-.10,.39,z),(.10,.10,z)],.009,'BareSteel')
    export('JerryCan')

def misc():
    begin();box('Pack body',(0,.3,0),(.38,.58,.24),'MilitaryFabric',.09)
    box('Front pocket',(0,.23,.145),(.32,.28,.13),'Canvas',.04)
    for x in [-.13,.13]:curve('Webbing',[(x,.04,.22),(x,.55,.12),(x,.59,-.1),(x,.13,-.17)],.015,'Rubber')
    export('Backpack')
    begin()
    for x in [-.09,.09]:
        box('Boot sole',(x,.025,.025),(.135,.045,.28),'Rubber',.019)
        box('Boot leather',(x,.09,.02),(.12,.13,.25),'Leatherette',.05)
        cyl('Boot shaft',(x,.08,-.05),(x,.25,-.05),.068,'Leatherette',r2=.054)
        for i in range(5):cyl('Lace',(x-.035,.16+i*.018,.01),(x+.035,.16+i*.018,.01),.003,'Canvas',verts=8)
    export('Boots')
    begin();cyl('Mug',(0,.006,0),(0,.105,0),.042,'Paper',verts=24)
    curve('Handle',[(.039,.08,0),(.065,.089,0),(.076,.058,0),(.062,.025,0),(.039,.03,0)],.006,'Paper');export('Mug')
    begin();box('Notebook',(0,.011,0),(.20,.022,.27),'MilitaryFabric',.004)
    box('Page block',(0,.014,0),(.187,.016,.256),'Paper',.002);export('Notebook')
    begin();cyl('Water bottle',(0,0,0),(0,.27,0),.042,'Glass',r2=.034,verts=24)
    cyl('Water cap',(0,.27,0),(0,.3,0),.022,'OldPlastic');export('WaterBottle')
    begin();cyl('Tinned food',(0,0,0),(0,.11,0),.055,'DirtyAluminum',verts=24)
    cyl('Food label',(0,.02,0),(0,.10,0),.0555,'Paper',verts=24);export('FoodCan')
    begin();box('Medical case',(0,.17,0),(.46,.34,.28),'Paper',.03)
    box('Cross vertical',(0,.17,.148),(.036,.19,.008),'RedPaint',0)
    box('Cross horizontal',(0,.17,.152),(.19,.036,.008),'RedPaint',0);export('MedicalCase')
    begin();box('Planning map',(0,.001,0),(2.1,.003,1.04),'Paper',0)
    face('Printed plan',[(-1.05,.003,.52),(1.05,.003,.52),(1.05,.003,-.52),(-1.05,.003,-.52)],'PlanningMap',[(0,1),(1,1),(1,0),(0,0)]);export('PlanningMap')
    begin();box('Rug',(0,.008,0),(4.1,.016,3.0),'WornCarpet',.005);export('Rug')
    begin();box('Fixture housing',(0,0,0),(1.15,.13,.18),'PaintedSteel',.012)
    box('Frosted diffuser',(0,-.063,0),(1.05,.035,.14),'WarmEmitter',.01)
    for x in [-.46,.46]:box('Safety bracket',(x,-.075,0),(.022,.025,.19),'BareSteel',.003)
    export('PracticalLight')
    begin();box('Lamp mounting plate',(0,0,-.055),(.22,.40,.07),'PaintedSteel',.018)
    cyl('Frosted glass',(0,-.13,0),(0,.13,0),.062,'WarmEmitter',verts=24)
    for i in range(6):
        a=i*math.tau/6;curve('Lamp cage',[(math.cos(a)*.085,-.14,math.sin(a)*.085),(math.cos(a)*.085,.14,math.sin(a)*.085)],.005,'BareSteel')
    export('CageLamp')
    begin();box('Rack backing',(0,1.05,-.18),(2.3,2.1,.05),'PaintedSteel',.007)
    box('Rack base',(0,.14,0),(2.4,.12,.45),'BareSteel')
    for x in [-1.12,1.12]:box('Rack upright',(x,1.1,.02),(.06,2.2,.09),'BareSteel')
    for x in [-.9,-.6,-.3,0,.3,.6,.9]:
        for y in [.36,1.35]:curve('Rubber cradle',[(x-.06,y,-.13),(x-.06,y,.06),(x+.06,y,.06),(x+.06,y,-.13)],.012,'Rubber')
    collision((0,1.1,-.06),(2.4,2.2,.4));export('WeaponRack')
    begin();box('Vent square',(0,0,0),(1.2,1.2,.13),'DirtyAluminum',.02)
    cyl('Fan well',(0,0,.09),(0,0,.105),.51,'Rubber',verts=32)
    for a in range(0,360,72):
        rad=math.radians(a);box('Fan blade',(.23*math.cos(rad),.23*math.sin(rad),.113),(.51,.12,.03),'BareSteel',.025,yaw=0)
    for y in [-.4,-.3,-.2,-.1,0,.1,.2,.3,.4]:box('Safety grille',(0,y,.147),(1.03,.016,.025),'BareSteel',.003)
    export('IndustrialFan')

def architecture():
    # Каждый модуль сохранён: потолок отдельно, проёмы настоящие, collision не concave на каждом prop.
    floors=[('MainHub',0,0,16,16,0),('Living',-13,-8,10,6,0),('Trader',-13,-2,10,6,0),('Armory',-13,4,10,6,0),('Generator',13,-8,10,6,0),('Workshop',13,-2,10,6,0),('Storage',13,4,10,6,0),('NorthGallery',0,-9.5,16,3,0),('Entry',0,10,8,4,0),('Sleeping',0,-9,6,4,2.6)]
    for name,x,z,w,d,h in floors:
        begin();box(name+' floor',(x,h-.10,z),(w,.2,d),'WetConcrete' if name=='Entry' else ('OldWood' if name=='Sleeping' else 'IndustrialConcreteFloor'),.009)
        collision((x,h-.10,z),(w,.2,d));export('Floor_'+name)
        if name!='Sleeping':
            begin();height=4.5 if name=='MainHub' else (5.0 if name=='NorthGallery' else 3.25)
            box(name+' ceiling',(x,height+.10,z),(w,.2,d),'RawConcrete',.008)
            for xx in [-w*.3,w*.3]:box('Structural ceiling rib',(x+xx,height-.14,z),(.2,.3,d),'RawConcrete',.009)
            collision((x,height+.1,z),(w,.2,d));export('Ceiling_'+name)
    # Разделённые стены со свободными проёмами 2.0 м и перемычками выше 2.3 м.
    walls=[]
    def wall(name,a,b,height=3.25,opening=None):
        begin();x1,z1=a;x2,z2=b
        alongx=z1==z2;start=x1 if alongx else z1;end=x2 if alongx else z2
        segments=[(start,end)] if opening is None else [(start,opening-1),(opening+1,end)]
        for lo,hi in segments:
            if hi<=lo:continue
            pos=((lo+hi)/2,height/2,z1) if alongx else (x1,height/2,(lo+hi)/2)
            size=(hi-lo,height,.4) if alongx else (.4,height,hi-lo)
            box('Concrete wall',pos,size,'RawConcrete',.014);collision(pos,size)
            # Окрашенный низ стены отделён рельефным швом; бетон виден над ним.
            low=(pos[0],.75,pos[2]);sz=(size[0]+.009,1.5,size[2]+.009)
            box('Civil defense paint',low,sz,'PaintedConcrete',.005)
            sk=(pos[0],.13,pos[2]);skz=(size[0]+.04,.26,size[2]+.04)
            box('Damp concrete plinth',sk,skz,'DampConcrete',.005)
        if opening is not None:
            pos=(opening,(height+2.3)/2,z1) if alongx else (x1,(height+2.3)/2,opening)
            sz=(2,height-2.3,.4) if alongx else (.4,height-2.3,2)
            box('Reinforced lintel',pos,sz,'RawConcrete',.012);collision(pos,sz)
            for v in [-1,1]:
                pos=(opening+v,1.14,z1) if alongx else (x1,1.14,opening+v)
                sz=(.11,2.28,.46) if alongx else (.46,2.28,.11)
                box('Steel doorway liner',pos,sz,'BareSteel',.007)
        export('Wall_'+name);walls.append(name)
    wall('North',(-18,-11),(18,-11),5)
    wall('West',(-18,-11),(-18,7))
    wall('East',(18,-11),(18,7))
    for side,x in [('West',-8),('East',8)]:
        for room,z0,z1,door in [('Living',-11,-5,-6.8),('Trader',-5,1,-2),('Armory',1,7,4)]:
            wall(side+room,(x,z0),(x,z1),3.25,door)
    for side,x0,x1 in [('West',-18,-8),('East',8,18)]:
        for name,z in [('NorthDivide',-5),('MidDivide',1),('South',7)]:wall(side+name,(x0,z),(x1,z))
    wall('EntryWest',(-4,8),(-4,12))
    wall('EntryEast',(4,8),(4,12))
    wall('EntrySouth',(-4,12),(4,12),3.25)
    wall('BaySouthWest',(-8,8),(-4,8));wall('BaySouthEast',(4,8),(8,8))
    wall('HubWestReturn',(-8,7),(-8,8));wall('HubEastReturn',(8,7),(8,8))
    # Equipment bays с открытым фронтом: не перекрывают маршрут от тамбура к хабу.
    begin()
    for x in [-6.2,-4.0,4.0,6.2]:
        box('Bay divider',(x,1.05,6.45),(.08,2.1,1.45),'PaintedSteel',.014)
        collision((x,1.05,6.45),(.08,2.1,1.45))
    for x,z in [(-7.6,-4.8),(7.6,-4.8),(-7.6,4.8),(7.6,4.8),(-3.3,-7.1),(3.3,-7.1)]:
        height=5.0 if z==-7.1 else 4.5
        box('Reinforced column',(x,height/2,z),(.5,height,.5),'RawConcrete',.015);collision((x,height/2,z),(.5,height,.5))
    export('TechnicalStructure')
    begin()
    # Stair pitch 33° / risers 0.173 m, collision заменяется плавной hidden ramp.
    for i in range(15):
        z=-2.45-i*.27;y=(i+1)*2.6/15
        box('Metal tread',(5.3,y-.045,z),(1.8,.09,.30),'BareSteel',.004)
        box('Tread nosing',(5.3,y+.003,z+.145),(1.8,.01,.017),'IndustrialTrim',.001)
    for x in [4.35,6.25]:
        curve('Stringer',[(x,.03,-2.25),(x,2.56,-6.5)],.065,'PaintedSteel')
        curve('Stair handrail',[(x,1.1,-2.25),(x,3.7,-6.5),(x,3.7,-7.5)],.035,'BareSteel')
        for i in range(0,15,3):cyl('Rail post',(x,(i+1)*2.6/15,-2.45-i*.27),(x,1.1+(i+1)*2.6/15,-2.45-i*.27),.025,'BareSteel')
    box('Landing',(4.65,2.5,-7.3),(3.5,.2,1.6),'BareSteel',.01);collision((4.65,2.5,-7.3),(3.5,.2,1.6))
    # Связь landing с mezzanine.
    box('Mezzanine approach',(1.0,2.5,-7.3),(4,.2,1.6),'BareSteel',.01);collision((1,2.5,-7.3),(4,.2,1.6))
    for x0,x1,z in [(-3,-1,-7),(-1,3,-6.5),(-3,3,-11),(3,4.35,-6.5),(3,6.4,-8.1)]:
        curve('Mezzanine rail',[(x0,3.7,z),(x1,3.7,z)],.034,'BareSteel')
        curve('Mezzanine midrail',[(x0,3.1,z),(x1,3.1,z)],.02,'BareSteel')
        for k in range(int(x1-x0)+1):cyl('Balustrade post',(x0+k,2.6,z),(x0+k,3.7,z),.023,'BareSteel')
    export('StairsAndRailing')
    # Fixed service runs: north-south trunk справа, ответвления к каждой комнате.
    begin()
    curve('Air duct trunk',[(7.1,4.05,6.8),(7.1,4.05,-9.8),(-15.8,4.05,-9.8)],.31,'GalvanizedSteel')
    for z in [-8,-2,4]:
        curve('East air branch',[(7.1,2.94,z),(16.4,2.94,z)],.17,'GalvanizedSteel')
        curve('West air branch',[(-7.1,2.94,z),(-16.4,2.94,z)],.17,'GalvanizedSteel')
        for x in [10,13,16,-10,-13,-16]:
            cyl('Duct bracket',(x,2.94,z),(x,3.18,z),.02,'BareSteel')
    for i in range(14):
        z=6.7-i*1.2
        cyl('Trunk collar',(7.1,4.05,z-.023),(7.1,4.05,z+.023),.325,'BareSteel',verts=24)
        curve('Trunk hanger',[(6.73,4.45,z),(6.73,4.05,z),(7.47,4.05,z),(7.47,4.45,z)],.015,'BareSteel')
    export('Ventilation')
    begin()
    for y,r,m in [(2.54,.06,'RedPaint'),(2.72,.04,'BareSteel')]:
        curve('North water main',[(-17.7,y,-10.65),(17.6,y,-10.65),(17.6,y,6.7)],r,m)
        curve('West water main',[(-17.7,y,-10.65),(-17.7,y,6.7)],r,m)
    for z in [-7.5,-1.5,4.5]:
        for x in [-17.7,17.6]:cyl('Pipe wall bracket',(x,2.56,z),(x,2.9,z),.016,'BareSteel')
    # Кабельный лоток: ladder mesh виден в FPS; логичные линии от щитовой к хабу.
    for x in [-6.9,6.9]:
        for dx in [-.15,.15]:box('Tray side',(x+dx,4.15,-.8),(.027,.08,16),'PaintedSteel',.005)
        for z in range(-8,8):box('Tray rung',(x,4.15,z),(.32,.025,.028),'BareSteel',.002)
        for dx in [-.05,0,.05]:curve('Power cable',[(x+dx,4.17,-8.5),(x+dx,4.17,7.0)],.012,'Rubber')
    export('PipesAndElectrical')
    begin()
    for z in [8.55,11.1]:
        box('Drain channel',(0,-.008,z),(7.6,.017,.23),'Rubber',.003)
        for x in range(-37,38):box('Drain grate bar',(x*.10,.005,z),(.018,.024,.23),'BareSteel',.002)
    for z in [-5,1,7]:
        for x in [-8,8]:box('Door threshold',(x,.007,z),(1.1,.014,2.0),'BareSteel',.003)
    export('DrainsAndThresholds')

def utility_props():
    begin();box('Lamp base',(0,.02,0),(.23,.035,.17),'PaintedSteel',.016)
    curve('Articulated arm',[(0,.035,0),(0,.28,-.06),(0,.47,.04)],.015,'BareSteel')
    cyl('Lamp shade',(0,.43,.04),(0,.53,.04),.13,'PaintedSteel',r2=.065,verts=24)
    cyl('Lamp diffuser',(0,.426,.04),(0,.43,.04),.105,'WarmEmitter',verts=24);export('DeskLamp')
    begin();box('Peg rail',(0,.03,0),(1.5,.09,.045),'OldWood',.008)
    for x in [-.6,-.3,0,.3,.6]:curve('Coat hook',[(x,.045,.02),(x,-.05,.15),(x,-.02,.17)],.01,'BareSteel')
    export('HookRail')
    begin()
    for x in [-.06,.06]:
        cyl('Binocular barrel',(x,.06,-.09),(x,.06,.09),.047,'Rubber',r2=.035,verts=24)
        cyl('Objective lens',(x,.06,-.095),(x,.06,-.09),.043,'Glass',verts=24)
        cyl('Eyepiece',(x,.06,.07),(x,.06,.12),.028,'Rubber')
    box('Optics bridge',(0,.06,0),(.10,.035,.04),'BareSteel',.005);export('Binoculars')
    begin();cyl('Graphite pencil',(-.075,.005,0),(.07,.005,0),.004,'OchreSteel',verts=6)
    cyl('Pencil point',(.07,.005,0),(.09,.005,0),.004,'OldWood',r2=0,verts=6);export('Pencil')
    begin();box('Plate carrier front',(0,.31,0),(.37,.54,.10),'MilitaryFabric',.035)
    for x in [-.13,.13]:box('Shoulder strap',(x,.64,0),(.07,.18,.05),'Canvas',.023)
    for x in [-.11,0,.11]:box('Magazine pouch',(x,.28,.093),(.10,.20,.07),'Canvas',.017)
    for y in [.14,.39,.46]:box('Webbing strip',(0,y,.06),(.37,.013,.014),'Rubber',.002)
    export('TacticalVest')
    begin()
    # Не сплошной шар: открытый снизу шлем с реальным краем оболочки.
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24,ring_count=12,radius=1,location=xyz((0,.07,0)))
    o=bpy.context.object;o.scale=(.135,.15,.13);bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    import bmesh
    bm=bmesh.new();bm.from_mesh(o.data)
    bmesh.ops.delete(bm,geom=[v for v in bm.verts if v.co.z<-.018],context='VERTS');bm.to_mesh(o.data);bm.free()
    mod=o.modifiers.new('Helmet shell thickness','SOLIDIFY');mod.thickness=.006;bpy.context.view_layer.objects.active=o;bpy.ops.object.modifier_apply(modifier=mod.name)
    finish(o,'Steel helmet','PaintedSteel',.001)
    curve('Chinstrap',[(-.11,.03,0),(0,-.015,.12),(.11,.03,0)],.009,'Canvas');export('Helmet')
    begin();box('Map board',(0,0,0),(2.2,1.3,.06),'OldWood',.015)
    face('Wall plan',[(-1.02,-.57,.035),(1.02,-.57,.035),(1.02,.57,.035),(-1.02,.57,.035)],'PlanningMap',[(0,1),(1,1),(1,0),(0,0)]);export('WallMap')
    begin()
    for z in [-.16,.16]:cyl('Reel flange',(0,.24,z-.025),(0,.24,z+.025),.25,'OldWood',verts=24)
    cyl('Cable reel',(0,.24,-.13),(0,.24,.13),.17,'Rubber',verts=24)
    for z in [-.13,-.08,-.03,.03,.08,.13]:
        curve('Wound cable',[(.177*math.cos(i*math.tau/32),.24+.177*math.sin(i*math.tau/32),z) for i in range(33)],.012,'Rubber')
    export('CableReel')

table('PlanningTable',2.4,1.2,.75);table('CoffeeTable',1.15,.65,.44);table('Bench',1.7,.43,.45);table('Counter',2.7,.80,.92)
shelf('Shelf');locker();crate();crate('CardboardBox',True);couch();chair();bed();blast_door();generator();workshop();electrical();radio();television();bottles();canister();misc();utility_props();architecture()
(OUT/'manifest.json').write_text(json.dumps(ASSETS,ensure_ascii=False,indent=2),encoding='utf-8')
for o in bpy.context.scene.objects:o.hide_set(False)
bpy.ops.wm.save_as_mainfile(filepath=str(SRC/'shelter.blend'))
(SRC/'license.txt').write_text('Собственные модели RING, авторинг OpenAI Codex для владельца проекта, 2026-10-05. Фотографические текстуры отдельно: Poly Haven CC0. Исходные авторы перечислены в assets/ASSET_CREDITS.md.',encoding='utf-8')
print('SHELTER_DONE',len(ASSETS),sum(v['triangles'] for v in ASSETS.values()))
