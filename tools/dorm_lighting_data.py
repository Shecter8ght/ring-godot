# -*- coding: utf-8 -*-
"""Собственный пробный свет общежития. Настройки других карт не используются."""
import hashlib
import json

def cct_srgb_hex(kelvin):
    """Godot's CIE-1960 blackbody-to-sRGB approximation; no global physical-unit change."""
    t=kelvin; t2=t*t
    u=(.860117757+1.54118254e-4*t+1.28641212e-7*t2)/(1+8.42420235e-4*t+7.08145163e-7*t2)
    v=(.317398726+4.22806245e-5*t+4.20481691e-8*t2)/(1-2.89741816e-5*t+1.61456053e-7*t2)
    d=1/(2*u-8*v+4); x=3*u*d; y=2*v*d
    xyz=(x/y,1,(1-x-y)/y)
    rgb=[3.2404542*xyz[0]-1.5371385-.4985314*xyz[2],
         -.969266*xyz[0]+1.8760108+.041556*xyz[2],
         .0556434*xyz[0]-.2040259+1.0572252*xyz[2]]
    m=max(rgb)
    def srgb(c):
        c=max(0,min(1,c/m));return c*12.92 if c<=.0031308 else 1.055*c**(1/2.4)-.055
    return ''.join(f'{round(srgb(c)*255):02x}' for c in rgb)


def add_lighting(p):
    levels=p["scale"]["floor_y"]
    heights=p["scale"]["ceiling_clear"]
    p["lights"]={name:[] for name in ["main_corridor","annex_corridor","rooms","wet_rooms","services","lounge","watch","stairs","window_sky"]}
    p["probes"]={"rooms":[],"corridors":[]}
    for s in p["sections"].values():
        s["lights"]=[]
        s["probes"]=[]

    def lamp(group,key,at,energy=1.0,radius=4.5,shadow=False,cold=False,on=True,spot=False):
        record={"id":f"{group}_{sum(map(len,p['lights'].values())):03d}","group":group,"at":at,
                "energy":energy,"range":radius,"shadow":shadow,"on":on,"type":"spot" if spot else "omni",
                "color":"dce8f2" if cold else "ffbd80","kelvin":4500 if cold else 2850,
                "angle":68.0,"attenuation":1.7}
        p["lights"][group].append(record)
        p["sections"][key]["lights"].append(record)

    def probe(group,key,at,size,mirror=False):
        record={"id":f"{group}_{sum(map(len,p['probes'].values())):03d}","group":group,"at":at,"size":size,
                "intensity":.65,"shadows":mirror,"max_distance":12.0,"blend":.12}
        p["probes"][group].append(record)
        p["sections"][key]["probes"].append(record)

    stations=sorted(a["at"][0] for a in p["portals"] if a["floor"]==1 and a["kind"]=="transverse" and a.get("travel_axis","x")=="x")
    cuts=[0,*stations,p["main_rect"][2]]
    # Все пять этажей открыты (владелец 2026-11-02); на техэтаже горит только каждая третья лампа коридора.
    for f in range(5):
        key=f"Floor{f+1}"
        y,h=levels[f],heights[f]
        for i in range(0,len(cuts)-1,2):
            xx=(cuts[i]+cuts[i+1])/2
            on=(i//2+f)%3!=1 if f<4 else (i//2)%3==0
            lamp("main_corridor",key,[xx,y+h-.22,0],2.0,4.6,on,on=on)
        for i,zz in enumerate([-10.2,-18.6,-27.0]):
            lamp("annex_corridor","NorthAnnex",[41.71,y+h-.22,zz],1.8,4.5,True,on=(i+f)%3!=0)
        lamp("stairs","CentralStair",[20.73,y+2.3,-5.1],.35,4.1,f==0)
        for i in range(len(cuts)-1):
            probe("corridors",key,[(cuts[i]+cuts[i+1])/2,y+h/2,0],[cuts[i+1]-cuts[i],h,3.35])
        for zz in [-12.5,-20.8,-27.0]:
            probe("corridors","NorthAnnex",[41.71,y+h/2,zz],[3.35,h,7.8])
    room_index=0
    for s in p["spaces"]:
        if not s["open"] or s["kind"] in ["stairs","watch","vestibule","turn"]:
            continue
        f=s["floor"]-1
        y,h=levels[f],heights[f]
        x0,z0,x1,z1=s["rect"]
        cx,cz=(x0+x1)/2,(z0+z1)/2
        key="NorthAnnex" if "_annex_" in s["id"] else f"Floor{f+1}"
        wet=s["kind"] in ["wash","showers","toilets"]
        probe("rooms",key,[cx,y+h/2,cz],[x1-x0,h,z1-z0],mirror=wet and s["kind"]=="wash")
        if s["kind"]=="room":
            # Окно / тёплая лампа на столе / темно. Окна и мебель остаются прежними.
            s["lighting_state"]=["window_only","table_lamp","unlit"][room_index%3]
            if room_index%3==1:
                lamp("rooms",key,[cx,y+.95,cz],.8,2.9)
            room_index+=1
        elif wet:
            lamp("wet_rooms",key,[cx,y+h-.22,cz],1.6,4.5,s["kind"]=="wash",True)
        elif s["kind"]=="lounge":
            lamp("lounge",key,[cx+.8,y+h-.24,cz+.7],2.0,4.8,True,spot=True)
        elif s["kind"] in ["kitchen","commandant","hall"]:
            lamp("services",key,[cx,y+h-.25,cz],1.2,3.5)
    lamp("watch","Floor1",[1.15,2.35,4.5],.6,4.2,True)
    p["lights"]["watch"][-1].update({"source_size":0.,"shadow_blur":3.0,"falloff":1.0})
    # Широкий источник в плоскости окна приближает рассеянный свет неба.
    # Короткая дальность и тени стен сохраняют тёмную глубину комнаты и закрытые углы.
    for w in p["windows"]:
        x,y,z=w["at"]
        axis=w["axis"]
        inward=(-1 if z>0 else 1) if axis=="z" else (-1 if x>p["main_rect"][2] else 1)
        at=[x,y+w["height"]/2,z]
        at[2 if axis=="z" else 0]+=inward*.35
        lamp("window_sky",w["section"],at,.32,8.,True,True,spot=True)
        record=p["lights"]["window_sky"][-1]
        record.update({"rotation":[0,180 if inward>0 else 0,0] if axis=="z" else [0,-90 if inward>0 else 90,0],
                       "angle":82.,"angle_attenuation":2.,"specular":0.,"attenuation":1.2,
                       "sky_fill":True,"floor":w["floor"],"shadow_bias":.1})
    # Неподвижная геометрия, не свет: освещение BAKE_DYNAMIC меняется без повторного запекания.
    geometry={k:{"boxes":v["boxes"],"beams":v["beams"],"stairs":v["stairs"],
                 "groups":{g:d["boxes"] for g,d in v.get("groups",{}).items()}}
              for k,v in p["sections"].items()}
    digest=hashlib.sha256(json.dumps(geometry,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    p["environment"]={
        "author":"dorm_r6_independent","lighting_revision":"6.1","default":"evening_B","geometry_sha256":digest,
        "sun_shadows":{"distance":90.,"cascades":4},
        "night_exterior":{"default":False,"energy":.08,"color":"abc4e6","rotation":[-35,-35,0],"shadow_distance":50.},
        "cases":[{"id":"evening_A","time":"evening","gi":"A","label":"Вечер А · SDFGI"},
                 {"id":"evening_B","time":"evening","gi":"B","label":"Вечер Б · VoxelGI"},
                 {"id":"night_A","time":"night","gi":"A","label":"Ночь А · SDFGI"},
                 {"id":"overcast_A","time":"overcast","gi":"A","label":"Пасмурно А · SDFGI"},
                 {"id":"night_B","time":"night","gi":"B","label":"Ночь Б · VoxelGI"},
                 {"id":"evening_B_no_windows","time":"evening","gi":"B","windows":False,"label":"Б без оконных источников"}],
        "times":{
            "evening":{"label":"Вечер · около 20:00","sun_rotation":[-12,145,0],"sun_energy":3.2,"sun_color":"ffd4a0",
                       "sky_top":"385570","sky_horizon":"b0bdc5","background_energy":.9,"ambient":.14,"exposure":1.15,"window_energy":.32},
            "night":{"label":"Ночь · только лампы","sun_rotation":[-12,145,0],"sun_energy":0.,"sun_color":"ffd4a0",
                     "sky_top":"000000","sky_horizon":"000000","background_energy":0.,"ambient":0.,"exposure":1.55,"window_energy":0.},
            "overcast":{"label":"Пасмурный день","sun_rotation":[-40,145,0],"sun_energy":0.,"sun_color":"ffffff",
                        "sky_top":"748695","sky_horizon":"c1c7c9","background_energy":.85,"ambient":.22,"exposure":1.25,"window_energy":1.15}},
        "sdfgi":{"min_cell_size":.12,"cascades":4,"energy":2.4,"bounce_feedback":.65,"normal_bias":1.,"probe_bias":1.},
        # Объёмы VoxelGI — жилые этажи 1–4 (восемь: больше Forward+ разом не рисует); техэтаж — без них.
        "voxel":{"subdiv":2,"energy":1.05,"bias":.3,"normal_bias":.5,"interior":False,"diffuse_proxy":True,"volumes":[
            volume for f in range(4) for volume in [
                {"id":f"floor_{f+1}","at":[21.705,levels[f]+(heights[f]+.099)/2,0],"size":[43.85,heights[f]+.101,18.2],
                 "cache":f"res://data/blockouts/dorm_voxel/floor_{f+1}.res"},
                {"id":f"annex_{f+1}","at":[38.655,levels[f]+(heights[f]+.099)/2,-24.15],"size":[9.95,heights[f]+.101,30.14],
                 "cache":f"res://data/blockouts/dorm_voxel/annex_{f+1}.res"}]]},
        "cool_corridors":{"kelvin":4400,"color":cct_srgb_hex(4400),"default":False},
        # Свет «как в Таркове» (основной с 2026-10-31, F9 — выключить): подсветка-«зона окружения» в каждом помещении
        # и цепочкой вдоль коридоров (без теней и бликов, вне VoxelGI), окна, небо и экспозиция — множители времени
        # суток. Ночью подсветка тусклая и холодная, в окнах — слабый лунный свет вместо нуля.
        "tarkov":{"default":True,"room":.30,"corridor":.26,"wet":.22,"room_color":"fff0e0","corridor_color":"e8eef5",
                  "height":2.1,"range_scale":.62,"attenuation":.45,"corridor_step":4.5,"window":2.5,"ambient":1.6,"exposure":1.1,
                  "times":{"evening":{"fill":1.},"overcast":{"fill":1.},
                           "night":{"fill":.18,"color":"aebcd4","window":.06,"window_color":"abc4e6"}}},
        "effects":{"ssao":True,"ssao_radius":1.2,"ssao_intensity":1.5,"ssil":False,"ssil_radius":2.,"ssil_intensity":.6,
                   "fog":True,"fog_density":0.,"fog_length":32.,"fog_anisotropy":.15,"sun_fog_energy":8.,
                   "dust_density":.025,"dust_volumes":[
                       {"id":f"dust_{part}_{f+1}","at":[cx,levels[f]+heights[f]/2,cz],"size":[sx,heights[f]-.1,sz]}
                       for f in range(5) for part,cx,cz,sx,sz in [("main",21.705,0,43.4,17.75),("annex",38.655,-24.26,9.5,29.47)]],
                   "post":True,"tonemap_mode":2,"tonemap_name":"Filmic",
                   "saturation":.88,"sharpen":.5,"grain":.003,"vignette":.15,
                   "lut":[[0,0,0],[.15,.175,.20],[.46,.485,.50],[.80,.81,.79],[1.,.99,.965]]},
        "shadow_atlas":4096,"shadow_quadrants":[16,16,16,16],"active_reflection_limit":32,
        "notes":"Свои настройки стенда. LightmapGI нет; неподвижная воксельная геометрия, динамические источники."}
