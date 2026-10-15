"""Авторские сцены северо-запада зоны 1. Не пересобирает остальную карту.

После Blender: python -X utf8 tools/author_zone01_nw.py
Расставленные сущности сохраняются обычными узлами .tscn; их можно править в редакторе.
Повторный запуск перезаписывает только три новые сцены. Подключение к старым идемпотентно.
"""
from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_zone01 as z1
import build_zone01_materials as materials

ROOT = Path(__file__).resolve().parents[1]
SCENES = ROOT / "scenes/levels/zone01"
ASSET = "res://assets/zone01/nw/"
MANIFEST = ASSET+"manifest.json"
PROPS = "res://levels/shelter/props/"
MODEL_SCRIPT = "res://src/world/district_model.gd"
LOOT = "res://scenes/world/loot_container.tscn"
LOOSE = "res://scenes/world/loose_loot.tscn"
CX = -4.8
OPEN = [(0,"front_left"),(0,"rear_left"),(1,"front_right"),(2,"rear_left"),(3,"front_left"),(4,"rear_right")]
REPORT = {"containers":[],"loose":[],"routes":{},"architecture":[]}


def model(s,name,asset,pos,parent=".",yaw=0.0):
    source_asset=asset
    external=asset in ("wardrobe","chest") and (ROOT/"assets/zone01/nw/furniture.json").exists()
    if external: asset="ph_cabinet" if asset=="wardrobe" else "ph_household_chest"
    surface="wood" if source_asset in ("chest","kitchen","wardrobe","garden_fence","garden_shed") else (
        "metal" if asset.startswith("market_stall") or asset=="ravine_bridge" else "concrete")
    node=s.node(name,parent,kind="StaticBody3D",script=s.resource(MODEL_SCRIPT,"Script"),
                position=z1.v3(*pos),rotation_degrees=z1.v3(0,yaw,0),
                model=ASSET+asset+".glb",manifest=ASSET+"furniture.json" if external else MANIFEST,surface=surface,
                materials_dir="" if external else "res://assets/zone01/materials")
    REPORT["architecture"].append(dict(name=name,asset=asset,position=list(pos),yaw=yaw))
    return node


def prop(s,name,asset,pos,parent=".",yaw=0.0,scale=1.0):
    return s.node(name,parent,scene=PROPS+asset+".tscn",position=z1.v3(*pos),
                  rotation_degrees=z1.v3(0,yaw,0),scale=z1.v3(scale,scale,scale))


def search(s,name,title,table,pos,parent="."):
    s.node(name,parent,scene=LOOT,position=z1.v3(*pos),display_name=title,table=table,
           require_line_of_sight=True)
    REPORT["containers"].append(dict(name=name,title=title,table=table,position=list(pos),parent=parent))


def loose(s,name,table,pos,parent="."):
    s.node(name,parent,scene=LOOSE,position=z1.v3(*pos),table=table,require_line_of_sight=True)
    REPORT["loose"].append(dict(name=name,table=table,position=list(pos),parent=parent))


def label(s,name,text,pos,parent=".",yaw=0.0,size=.004):
    s.node(name,parent,kind="Label3D",position=z1.v3(*pos),rotation_degrees=z1.v3(0,yaw,0),
           text=text,font_size=48,pixel_size=size,billboard=0,no_depth_test=False,
           modulate=z1.Raw("Color(0.78, 0.76, 0.65, 1)"),outline_size=0)


def light(s,name,pos,parent=".",radius=7.0,energy=1.1):
    s.node(name,parent,kind="OmniLight3D",groups=["mall_lights"],position=z1.v3(*pos),
           light_color=z1.Raw("Color(1, 0.78, 0.53, 1)"),light_energy=energy,
           omni_range=radius,shadow_enabled=True,distance_fade_enabled=True,
           distance_fade_begin=35.0,distance_fade_length=8.0)


def build_yard():
    s=z1.Scene("Yard05Gameplay")
    s.node("Interior",groups=["nav_source"],position=z1.v3(-212,.3731,-138))
    # Подъезд остаётся на месте корпуса 1; физика фасада — в panel_playable.
    s.node("Furniture","Interior")
    s.node("Loot","Interior")
    for f in range(5):
        y=1.1+2.8*f
        label(s,f"Floor_{f+1}",str(f+1),(CX,y+1.5,-1.065),"Interior",size=.007)
        prop(s,f"LandingLamp_{f}","PracticalLight",(CX,y+2.45,.6),"Interior")
        light(s,f"LandingLight_{f}",(CX,y+2.35,.6),"Interior",5,.6)
    for i,(f,which) in enumerate(OPEN):
        y=1.1+2.8*f; front=which.startswith("front"); left=which.endswith("left")
        edge=CX+(-1.6 if left else 1.6) if front else CX
        kx=edge+(-1.25 if left else 1.25)
        rz=3.0 if front else -3.0
        cz=4.9 if front else -4.9
        yaw=180 if front else 0
        roomx=-11.25 if left else 1.0
        model(s,f"Kitchen_{i}","kitchen",(kx,y,cz),"Interior/Furniture",yaw)
        prop(s,f"Seat_{i}","PH_Sofa",(roomx,y,rz),"Interior/Furniture",90 if left else -90)
        prop(s,f"RoomTable_{i}","PH_CoffeeTable",(roomx+(.85 if left else -.85),y,rz),"Interior/Furniture")
        prop(s,f"KitchenStool_{i}","PH_FoldingStool",(kx-.6,y,3.4 if front else -3.4),"Interior/Furniture",15)
        prop(s,f"Kettle_{i}","PH_Kettle",(kx+.3,y+.94,cz),"Interior/Furniture")
        model(s,f"Wardrobe_{i}","wardrobe",(roomx,y,1.0 if front else -1.3),"Interior/Furniture",yaw)
        if i in (1,5):
            prop(s,f"Bed_{i}","Bed",(roomx+.55,y,4.2 if front else -4.05),"Interior/Furniture",90)
        # Точки взаимодействия стоят перед мебелью, а не внутри её коллизии.
        if i==0: search(s,"YardKitchen","Кухонный шкаф","home",(kx,y+.6,cz-.5),"Interior/Loot")
        elif i==1: search(s,"YardWardrobe","Вещевой комод","home",(roomx,y+.65,-.8),"Interior/Loot")
        elif i==2:
            prop(s,"MedicineDesk","PH_MetalDesk",(roomx,y,1.8),"Interior/Furniture",90)
            prop(s,"MedicineCase","PH_MedicalBox",(roomx,y+.79,1.8),"Interior/Furniture")
            search(s,"YardMedicine","Домашняя аптечка","pharmacy",(roomx-.6,y+.9,1.8),"Interior/Loot")
        elif i==3:
            prop(s,"WritingDesk","PH_MetalDesk",(-10.8,y,-4.65),"Interior/Furniture")
            search(s,"YardDesk","Ящики письменного стола","office",(-9.5,y+.65,-4.6),"Interior/Loot")
        elif i==4: search(s,"YardDresser","Вещевой комод","home",(roomx,y+.65,.5),"Interior/Loot")
        else: search(s,"YardUpperKitchen","Кухонный шкаф пятого этажа","home",(kx,y+.6,cz+.5),"Interior/Loot")
        loose(s,f"YardLoose_{i:02d}","home",(kx-.25,y+.94,cz),"Interior/Loot")
        if i in (0,2,3):
            loose(s,f"YardLoose_{i+6:02d}","pharmacy" if i==2 else "office",
                  (roomx+(.85 if left else -.85),y+.47,rz),"Interior/Loot")
        prop(s,f"RoomLamp_{i}","PracticalLight",(kx,y+2.43,3.1 if front else -3.1),"Interior/Furniture")
        light(s,f"RoomLight_{i}",(kx,y+2.3,3.1 if front else -3.1),"Interior",4.5,.35)
        prop(s,f"LivingLamp_{i}","PracticalLight",(roomx,y+2.4,rz),"Interior/Furniture")
        light(s,f"LivingLight_{i}",(roomx,y+2.3,rz),"Interior",6.0,1.15)
    prop(s,"BasementWorkbench","Workbench",(-10.6,-1.7,-4.6),"Interior/Furniture")
    prop(s,"BasementChest","PH_ToolChest",(-8.8,-1.7,-4.6),"Interior/Furniture")
    search(s,"YardBasement","Инструмент в подвале","workshop",(-8.8,-1.2,-4.1),"Interior/Loot")
    light(s,"BasementLight",(-8.0,.55,-1.8),"Interior",8,.65)
    label(s,"BasementSign","ПОДВАЛ",(CX,-.45,1.61),"Interior",180,.003)
    s.save(SCENES/"zone01_yard05_gameplay.tscn")


def stall_interior(s,parent,kind,index):
    prop(s,"Counter","Counter",(0,0,0),parent)
    prop(s,"BackShelf","Shelf",(-1.8,0,-2.13),parent)
    prop(s,"SideShelf","Shelf",(2.85,0,-.7),parent,-90)
    label(s,"TradeSign",kind[0],(0,2.75,2.9),parent,0,.004)
    # Содержание соответствует назначению павильона, а доступный обыск — один на место.
    if index==0:
        prop(s,"Tools","PH_Toolbox",(-.6,.93,0),parent)
        prop(s,"ToolVice","PH_Vice",(.65,.93,0),parent)
    elif index==1:
        prop(s,"Laptop","PH_Laptop",(-.65,.93,0),parent)
        prop(s,"Meter","PH_Multimeter",(.65,.93,0),parent)
    elif index==2: prop(s,"MedicalCase","PH_MedicalBox",(0,.93,0),parent)
    elif index==3: prop(s,"ClothesBag","Backpack",(0,0,-1.6),parent)
    else:
        prop(s,"EmptyCrate","PH_PlasticCrate",(0,0,-1.7),parent)
        prop(s,"WorkCan","PH_OilTin",(.65,.93,0),parent)
    if index<4:
        search(s,f"MarketStallSearch_{index}",kind[1],kind[2],(0,.65,.6),parent)
    loose(s,f"MarketLoose_{index:02d}",kind[2],(.8,.94,0),parent)


def fence_segment(b,a,c,height=1.65):
    # Перепады и разрывы — реальные калитки, забор не пересекает проходы.
    ax,az=a; bx,bz=c; length=math.hypot(bx-ax,bz-az)
    if length<.1:return
    yaw=-math.degrees(math.atan2(bz-az,bx-ax))
    count=math.ceil(length/3.0)
    for i in range(count):
        t=(i+.5)/count; x=ax+(bx-ax)*t; z=az+(bz-az)*t
        node=model(b[0],f"{b[1]}_{i}","garden_fence",(x,z1.ground(x,z)+.08,z),b[2],yaw)
        b[0].nodes[-1]+=f"\nscale = Vector3({length/count/3.0}, {height/1.65}, 1)"


def build_market():
    s=z1.Scene("Z06_Market")
    s.node("Architecture",groups=["nav_source"])
    # Асфальтовая площадка без высокой плиты-порога; отделка — существующий PBR двора.
    pave=s.node("Paving",groups=["nav_source"])
    paving_script=s.resource("res://src/world/district_paving.gd","Script")
    for i,x in enumerate((-226,-211,-177,-151,-136,-116)):
        s.node(f"MarketApron_{i}",pave,kind="StaticBody3D",script=paving_script,
               points=z1.Raw(f"PackedVector2Array({x}, -51, {x}, 104)"),width=17.0,curb_height=0.0,
               material=s.resource("res://assets/zone01/materials/YardAsphalt.tres","Material"),lift=.075)
    hangar=model(s,"Hangar","market_hangar",(-192,.48,6),"Architecture")
    s.node("Furniture",hangar)
    for row,x in enumerate((-5.1,5.8)):
        for k,z in enumerate((-15,-8,-1,6)):
            prop(s,f"WarehouseShelf_{row}_{k}","Shelf",(x,0,z),hangar+"/Furniture",90)
            for j in range(2):
                prop(s,f"StockCarton_{row}_{k}_{j}","PH_Carton",(x,.52+j*.53,z),hangar+"/Furniture",15+j*85,.55)
    for i,(x,z) in enumerate(((8,-13),(8,1),(-2.5,-9),(2.4,7))):
        prop(s,f"DeliveryStock_{i}","PH_Crate",(x,0,z),hangar+"/Furniture",i*12)
        prop(s,f"DeliveryBox_{i}","PH_Carton",(x,.64,z),hangar+"/Furniture",i*12,.7)
    for i,(x,z) in enumerate(((8.5,15),(6.5,18))):
        prop(s,f"Cargo_{i}","PH_MilitaryCrate",(x,0,z),hangar+"/Furniture")
        search(s,f"MarketCargo_{i}","Грузовая тара ангара","storage",(x,.35,z+.5),hangar)
    prop(s,"OfficeDesk","PH_MetalDesk",(-6.0,3.61,18.6),hangar+"/Furniture")
    prop(s,"OfficeChair","PH_Chair",(-6.0,3.61,17.6),hangar+"/Furniture")
    prop(s,"OfficeLaptop","PH_Laptop",(-6.2,4.4,18.6),hangar+"/Furniture")
    prop(s,"OfficeCabinet","Locker",(-4.2,3.61,19.9),hangar+"/Furniture")
    prop(s,"WarehouseWorkbench","Workbench",(7.2,0,-19.0),hangar+"/Furniture")
    search(s,"MarketOffice","Служебный шкаф конторы","office",(-4.2,4.45,19.2),hangar)
    loose(s,"MarketLoose_06","office",(-5.6,4.41,18.6),hangar)
    loose(s,"MarketLoose_07","storage",(6.5,.47,18),hangar)
    loose(s,"MarketLoose_08","tools",(7.8,.92,-19.0),hangar)
    label(s,"WarehouseSign","ПРИЁМКА  /  СКЛАД",(-192,5.8,-15.17),".",180,.014)
    label(s,"OfficeSign","КОНТОРА",(-7.0,5.3,12.0),hangar,180,.004)
    for i,z in enumerate((-13,0,13)):
        prop(s,f"HangarLamp_{i}","PH_HangingLamp",(0,6.6,z),hangar)
        light(s,f"HangarLight_{i}",(0,5.8,z),hangar,14,1.5)
    light(s,"OfficeLight",(-7.2,6,16.5),hangar,5,.5)
    kinds=[("ИНСТРУМЕНТ","Инструментальный прилавок","tools"),
           ("РАДИОДЕТАЛИ","Шкаф ремонта электроники","electronics"),
           ("АПТЕЧНЫЕ ТОВАРЫ","Медицинские запасы","pharmacy"),
           ("ОДЕЖДА","Вещи павильона","home"),
           ("ХОЗТОВАРЫ","Хозяйственные товары","tools"),
           ("ПРОДУКТЫ","Продуктовый прилавок","grocery")]
    selected=[(-222,-40,90),(-170,-38,-90),(-170,-8,-90),(-222,41,90),(-145,48,90),(-131,87,-90)]
    used=[]
    for i,(x,z,yaw) in enumerate(selected):
        node=model(s,f"OpenStall_{i}",f"market_stall_{i%3}_open",(x,.48,z),"Architecture",yaw)
        stall_interior(s,node,kinds[i],i)
        light(s,f"StallLight_{i}",(0,2.45,.2),node,5,.35)
        used.append((x,z))
    index=0
    # Закрытые фоновые павильоны выглядят тем же комплектом, между рядами есть поперечные связи.
    for x,yaw in ((-222,90),(-170,-90),(-145,90),(-131,-90),(-114,-90)):
        for z in (-40,-25,-8,8,24,41,57,87):
            if any(math.hypot(x-a,z-c)<10 for a,c in used):continue
            if x==-222 and z in (-8,):continue
            model(s,f"ClosedStall_{index}",f"market_stall_{index%3}_closed",(x,.48,z),"Architecture",yaw)
            index+=1
    s.node("StreetFurniture",groups=["nav_source"])
    for i,(x,z,yaw) in enumerate(((-172,-32,10),(-175,39,85),(-164,67,0),(-208,80,-10))):
        prop(s,f"DeliveryCrate_{i}","PH_Crate",(x,.48,z),"StreetFurniture",yaw)
        prop(s,f"DeliveryCarton_{i}","PH_Carton",(x+.6,.48,z+.5),"StreetFurniture",yaw)
    # Три выхода из рынка: в сторону двора, к ТЦ, к домам. Ограждения не закрывают их.
    for i,(a,c) in enumerate([((-236,-55),(-203,-55)),((-188,-55),(-108,-55)),
                               ((-236,-55),(-236,27)),((-236,43),(-236,107))]):
        fence_segment((s,f"Fence_{i}","StreetFurniture"),a,c)
    REPORT["routes"]["market"]=dict(yard_gate=[-196,-55],west_gate=[-236,35],main_aisle_x=-177,
                                      side_aisles_x=[-210,-138],cross_aisles_z=[-16,33,73])
    s.save(SCENES/"zone01_market06.tscn")


def build_houses():
    s=z1.Scene("Z12_Ravine")
    s.node("Architecture",groups=["nav_source"])
    houses=[(-270,3,10,"house_attic"),(-297,25,-15,"house_mansard"),(-272,50,5,"house_closed")]
    for i,(x,z,yaw,asset) in enumerate(houses):
        y=z1.ground(x,z)+.12
        node=model(s,f"House_{i}",asset,(x,y,z),"Architecture",yaw)
        s.node("Furniture",node)
        model(s,f"Shed_{i}","garden_shed",(x+7,z1.ground(x+7,z+7)+.1,z+7),"Architecture",yaw)
        for j,(dx,dz) in enumerate(((-6,6),(5,-4))):
            prop(s,f"OutsideCrate_{i}_{j}","PH_Crate",(x+dx,z1.ground(x+dx,z+dz),z+dz),"Architecture",yaw)
        if i==2:continue
        model(s,"Kitchen","kitchen",(-2.25,.27,-3.85),node+"/Furniture")
        model(s,"Wardrobe","wardrobe",(-3.25,.27,1.0),node+"/Furniture",90)
        model(s,"AtticChest","chest",(-.8,3.1,-2.7),node+"/Furniture")
        prop(s,"Sofa","PH_Sofa",(-1.0,.27,.4),node+"/Furniture",90)
        prop(s,"KitchenStool","PH_FoldingStool",(-2.3,.27,-2.3),node+"/Furniture")
        prop(s,"KitchenKettle","PH_Kettle",(-2.0,1.21,-3.85),node+"/Furniture")
        prop(s,"AtticCarton","PH_Carton",(-.7,3.1,2.8),node+"/Furniture")
        light(s,"HouseLight",(-1.5,2.55,.4),node,6,.4)
        light(s,"AtticLight",(.1,5.25,.5),node,6,.3)
        # Прямой марш физически проверен капсулой. Явная связь сохраняет маршрут при
        # консервативном отсечении узкой лестницы под скатом навигационной сеткой.
        s.node("AtticStairLink",node,kind="NavigationLink3D",bidirectional=True,
               start_position=z1.v3(.85,.32,-3.45),end_position=z1.v3(.85,3.15,2.45))
        if i==0:
            search(s,"HouseKitchenSearch","Кухонный шкаф","home",(-2.25,.85,-3.3),node)
            search(s,"HouseAtticSearch","Хозяйственный сундук","home",(-.8,3.65,-2.2),node)
        else: search(s,"HouseWardrobeSearch","Вещевой комод","home",(-2.7,.92,1.0),node)
        for k,(table,pos) in enumerate([("home",(-2.5,1.21,-3.85)),("home",(-.7,3.45,2.8)),("tools",(.9,3.1,2.7))]):
            loose(s,f"HouseLoose_{i}_{k}",table,pos,node)
    shed="Architecture/Shed_0"
    prop(s,"GardenWorkbench","Workbench",(0,0,-1.45),shed)
    prop(s,"GardenToolbox","PH_Toolbox",(.6,.92,-1.45),shed)
    search(s,"HouseShedTools","Инструментальный ящик сарая","tools",(.6,1.0,-.9),shed)
    # Мост сохраняет исходные концы. Новая ферма оставляет видимость сквозь перила.
    bridge=z1.ground(-372,38)+.2
    s.node("Bridge",groups=["nav_source"])
    # Сама ходовая плита остаётся физической; архитектурный комплект моста добавляется отдельно.
    model(s,"BridgeDeck","ravine_bridge",(-343,bridge,37),"Bridge",-4)
    # Пешеходная тропа по восточному берегу и подход к мосту — отдельные реальные поверхности.
    s.node("Paths",groups=["nav_source"])
    script=s.resource("res://src/world/district_paving.gd","Script")
    for name,points,width in [("MarketToHouses",[(-236,35),(-254,34),(-282,32),(-305,35),(-315,35)],2.0),
                               ("UpperBank",[(-306,-18),(-312,6),(-315,35),(-310,70)],1.6),
                               ("RavineDescent",[(-310,70),(-323,84),(-331,64),(-335,30)],1.5)]:
        s.node(name,"Paths",kind="StaticBody3D",script=script,
               points=z1.Raw("PackedVector2Array("+", ".join(f"{x}, {z}" for x,z in points)+")"),
               width=width,curb_height=0.0,material=s.resource("res://assets/zone01/materials/NWTrail.tres","Material"),lift=.07)
    for i,(a,c) in enumerate([((-281,-8),(-273,-8)),((-266,-8),(-259,-8)),
                               ((-309,38),(-302,38)),((-294,38),(-286,38)),((-283,62),(-262,62))]):
        fence_segment((s,f"GardenFence_{i}","Architecture"),a,c,1.2)
    REPORT["routes"]["houses"]=dict(upper_bank=[-312,6],lower_route=[-335,30],bridge_approach=[-315,35])
    s.save(SCENES/"zone01_houses12.tscn")


def make_materials():
    specs={"NWPlaster":("concrete_wall_008",1.8,(1.08,1.03,.9)),
           "NWOffice":("concrete_wall_008",1.8,(.7,.82,.76)),
           "NWStairPaint":("concrete_wall_008",1.8,(.24,.47,.43)),
           "NWFloor":("wood_planks_grey",2.0,(.68,.52,.38)),
           "NWTile":("concrete_floor_02",.75,(.84,.82,.69)),
           "NWFurniture":("wood_planks_grey",1.1,(.46,.30,.18)),
           "NWTrail":("gravel_stones",1.5,(.73,.69,.59))}
    for name,(tex,tile,tint) in specs.items():
        data=materials.aged(name,tex,tile,tint,False,dict(streaks=.08,splash=.07,moss=0.0,roof_runoff=0.0,contrast=.75,normal_scale=.2))
        (ROOT/f"assets/zone01/materials/{name}.tres").write_text(data,encoding="utf-8")
    flats={"NWTrim":((.25,.19,.13),.7,0),"NWHandrail":((.19,.12,.07),.55,0),
           "NWEnamel":((.68,.68,.59),.32,.05),"NWHeating":((.51,.53,.47),.6,.3),
           "NWWarehouseSteel":((.17,.22,.21),.64,.65),"NWSign":((.17,.23,.25),.75,.1),
           "NWAwning0":((.32,.42,.28),.94,0),"NWAwning1":((.28,.38,.44),.94,0),
           "NWAwning2":((.57,.43,.24),.94,0)}
    for name,(color,rough,metal) in flats.items():
        (ROOT/f"assets/zone01/materials/{name}.tres").write_text(materials.flat(name,color,rough,metal),encoding="utf-8")


def add_resource(text,path,ident):
    if path in text:return text
    pos=text.index("\n",text.index("[ext_resource"))
    text=text[:pos]+f'\n[ext_resource type="PackedScene" path="{path}" id="{ident}"]'+text[pos:]
    return re.sub(r'load_steps=(\d+)',lambda m:f"load_steps={int(m[1])+1}",text,count=1)


def integrate():
    yard=SCENES/"zone01_yard05.tscn"; text=yard.read_text(encoding="utf-8")
    blocks=re.split(r'(?=\[node )',text)
    for i,block in enumerate(blocks):
        if block.startswith('[node name="Korpus1" '):
            block=re.sub(r'model = "[^"]+"',f'model = "{ASSET}panel_playable.glb"',block)
            block=re.sub(r'manifest = "[^"]+"',f'manifest = "{MANIFEST}"',block)
            blocks[i]=block.replace("shadow_proxy = true","shadow_proxy = false")
    text="".join(blocks)
    text=add_resource(text,"res://scenes/levels/zone01/zone01_yard05_gameplay.tscn","nw_gameplay")
    if '[node name="GameplayInterior"' not in text:
        text+='\n[node name="GameplayInterior" parent="." instance=ExtResource("nw_gameplay")]\n'
    yard.write_text(text,encoding="utf-8")
    blockout=SCENES/"zone01_blockout.tscn"; text=blockout.read_text(encoding="utf-8")
    for zone,path,ident in [("Z06_Market","zone01_market06","nw_market"),("Z12_Ravine","zone01_houses12","nw_houses")]:
        text=add_resource(text,f"res://scenes/levels/zone01/{path}.tscn",ident)
        blocks=re.split(r'(?=\[node )',text); kept=[]
        for block in blocks:
            if block.startswith(f'[node name="{zone}" '):continue
            header=block.split("\n",1)[0]
            if f'parent="{zone}' in header:continue
            kept.append(block)
        text="".join(kept)+f'\n[node name="{zone}" parent="." instance=ExtResource("{ident}")]\n'
    blockout.write_text(text,encoding="utf-8")
    world=SCENES/"zone01_world.tscn"; text=world.read_text(encoding="utf-8")
    blocks=re.split(r'(?=\[node )',text)
    for i,block in enumerate(blocks):
        if block.startswith('[node name="Terrain" '):
            block=re.sub(r'excavations = [^\n]+\n?',"",block)
            blocks[i]=block.rstrip()+"\nexcavations = Array[AABB]([AABB(-225, -1.9, -144, 17, 2.3, 12)])\n\n"
    world.write_text("".join(blocks),encoding="utf-8")
    # Прежние 10 дворовых находок перенесены внутрь. Шесть гаражных точек остаются на месте.
    loose_path=SCENES/"zone01_loose_loot.tscn"
    text=loose_path.read_text(encoding="utf-8")
    text="".join(block for block in re.split(r'(?=\[node )',text)
                 if not re.match(r'\[node name="Found_0[0-9]"',block))
    loose_path.write_text(text,encoding="utf-8")


def main():
    z1.H=np.fromfile(ROOT/"data/terrain/zone01_heights.r32",dtype="<f4").reshape(z1.NZ,z1.NX)
    make_materials(); build_yard(); build_market(); build_houses(); integrate()
    assert len(REPORT["containers"])==18,len(REPORT["containers"])
    assert len(REPORT["loose"])==24,len(REPORT["loose"])
    (ROOT/"data/zone01_nw_placements.json").write_text(json.dumps(REPORT,ensure_ascii=False,indent=1)+"\n",encoding="utf-8")
    print("NW_AUTHORED",len(REPORT["containers"]),"containers",len(REPORT["loose"]),"loose points")


if __name__=="__main__": main()
