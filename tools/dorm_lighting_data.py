# -*- coding: utf-8 -*-
"""Собственный пробный свет общежития. Настройки других карт не используются."""
import hashlib
import json


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
    for f in range(3):
        key=f"Floor{f+1}"
        y,h=levels[f],heights[f]
        for i in range(0,len(cuts)-1,2):
            xx=(cuts[i]+cuts[i+1])/2
            on=(i//2+f)%3!=1
            lamp("main_corridor",key,[xx,y+h-.22,0],2.0,4.6,on,on=on)
        for i,zz in enumerate([-10.2,-18.6,-27.0]):
            lamp("annex_corridor","NorthAnnex",[41.71,y+h-.22,zz],1.8,4.5,True,on=(i+f)%3!=0)
        lamp("stairs","CentralStair",[20.73,y+2.3,-5.1],.9,4.1,f==0)
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
    lamp("watch","Floor1",[.85,1.65,4.4],1.3,3.3,True)
    # Широкий источник в плоскости окна приближает рассеянный свет неба.
    # Короткая дальность и тени стен сохраняют тёмную глубину комнаты и закрытые углы.
    for w in p["windows"]:
        if w["floor"]>3:
            continue
        x,y,z=w["at"]
        axis=w["axis"]
        inward=(-1 if z>0 else 1) if axis=="z" else (-1 if x>p["main_rect"][2] else 1)
        at=[x,y+w["height"]/2,z]
        at[2 if axis=="z" else 0]+=inward*.35
        lamp("window_sky",w["section"],at,.32,8.,True,True,spot=True)
        record=p["lights"]["window_sky"][-1]
        record.update({"rotation":[0,180 if inward>0 else 0,0] if axis=="z" else [0,-90 if inward>0 else 90,0],
                       "angle":78.,"attenuation":1.2,"sky_fill":True,"floor":w["floor"]})
    # Неподвижная геометрия, не свет: освещение BAKE_DYNAMIC меняется без повторного запекания.
    geometry={k:{"boxes":v["boxes"],"beams":v["beams"],"stairs":v["stairs"],
                 "groups":{g:d["boxes"] for g,d in v.get("groups",{}).items()}}
              for k,v in p["sections"].items()}
    digest=hashlib.sha256(json.dumps(geometry,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    p["environment"]={
        "author":"dorm_r5_independent","default":"evening_A","geometry_sha256":digest,
        "cases":[{"id":"evening_A","time":"evening","gi":"A","label":"Вечер А · SDFGI"},
                 {"id":"evening_B","time":"evening","gi":"B","label":"Вечер Б · VoxelGI"},
                 {"id":"night_A","time":"night","gi":"A","label":"Ночь А · SDFGI"},
                 {"id":"overcast_A","time":"overcast","gi":"A","label":"Пасмурно А · SDFGI"}],
        "times":{
            "evening":{"label":"Вечер · около 20:00","sun_rotation":[-12,145,0],"sun_energy":3.2,"sun_color":"ffd4a0",
                       "sky_top":"385570","sky_horizon":"b0bdc5","background_energy":.9,"ambient":.14,"exposure":1.15,"window_energy":.32},
            "night":{"label":"Ночь · только лампы","sun_rotation":[-12,145,0],"sun_energy":0.,"sun_color":"ffd4a0",
                     "sky_top":"000000","sky_horizon":"000000","background_energy":0.,"ambient":0.,"exposure":1.55,"window_energy":0.},
            "overcast":{"label":"Пасмурный день","sun_rotation":[-40,145,0],"sun_energy":0.,"sun_color":"ffffff",
                        "sky_top":"748695","sky_horizon":"c1c7c9","background_energy":.85,"ambient":.22,"exposure":1.25,"window_energy":1.15}},
        "sdfgi":{"min_cell_size":.12,"cascades":4,"energy":2.4,"bounce_feedback":.65,"normal_bias":1.,"probe_bias":1.},
        "voxel":{"subdiv":2,"energy":1.,"bias":.3,"normal_bias":.5,"volumes":[
            {"id":f"floor_{f+1}","at":[21.7,levels[f]+heights[f]/2,-15.0],"size":[46,heights[f]+.6,51],
             "cache":f"res://data/blockouts/dorm_voxel/floor_{f+1}.res"} for f in range(3)]},
        "effects":{"ssao":True,"ssao_radius":1.2,"ssao_intensity":1.5,"ssil":False,"ssil_radius":2.,"ssil_intensity":.6,
                   "fog":True,"fog_density":.006,"fog_length":38.,"post":True,"tonemap_mode":2,"tonemap_name":"Filmic",
                   "saturation":.91,"sharpen":.65,"grain":.005,"vignette":.08,
                   "lut":[[0,0,0],[.19,.205,.22],[.475,.495,.51],[.75,.755,.75],[1.,.99,.97]]},
        "shadow_atlas":4096,"active_reflection_limit":32,
        "notes":"Свои настройки стенда. LightmapGI нет; неподвижная воксельная геометрия, динамические источники."}
