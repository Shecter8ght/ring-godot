# -*- coding: utf-8 -*-
"""Общежитие, этап 1, редакция 3: уточнение пропорций после прогулки 2026-10-28.

python -X utf8 tools/build_dorm.py -> JSON, сцена и поэтажный PNG.
Только план, габариты мебели и базовые цвета. Чистовые модули ещё не делаются.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PART, LOAD, EXT, SLAB = .15, .38, .64, .24
HALF, ROOM_D, BASE = 1.7, 6.8, .48
ROOM_EDGE, FACADE = HALF + LOAD, HALF + LOAD + ROOM_D
HEIGHTS = [3.7, 3.0, 3.0, 3.0, 3.0]
LEVELS = [BASE]
for height in HEIGHTS[:-1]:
    LEVELS.append(round(LEVELS[-1] + height + SLAB, 4))
WIDTHS = [3.9, 3.9, 5.07, 5.46, 3.3, 5.85, 5.07, 3.9, 5.46]
BAYS = []
cursor = 0.
for i, width in enumerate(WIDTHS):
    BAYS.append({"x0": cursor, "x1": cursor + width, "width": width})
    cursor += width + (.3 if i in [3, 4] else PART)
LENGTH = BAYS[-1]["x1"]
SC0, SC1 = BAYS[4]["x0"], BAYS[4]["x1"]
SCX, SZ = (SC0 + SC1) / 2, -ROOM_EDGE - 1.6
ANNEX_X, ANNEX_END = BAYS[7]["x0"], -39.
ANNEX_CORRIDOR = LENGTH - HALF * 2
ANNEX_WALL = ANNEX_CORRIDOR - LOAD / 2
TURN_X = (ANNEX_CORRIDOR + LENGTH) / 2
ENTRY_X, LANE_X = WIDTHS[0] / 2, 2.65
PORCH_END = FACADE + EXT + 2.58
DOOR_W, DOOR_H = 1.17, 2.415
WINDOW_W = 2 * .82 * 1.15 + .21
STATES = ["жилая", "разграбленная", "сгоревшая", "баррикада у окна", "пустая с матрасами"]


def rounded(v):
    if isinstance(v, float):
        return round(v, 4)
    if isinstance(v, list):
        return [rounded(x) for x in v]
    if isinstance(v, dict):
        return {k: rounded(x) for k, x in v.items()}
    return v


def make_plan():
    p = {"version": 3, "stage": 1, "greybox": True, "north": "-Z",
         "purpose": "Общежитие: проверка планировки, масштаба, центральной лестницы и базовой раскраски",
         "bounds": [-11, -46, LENGTH + 13, 24],
         "main_rect": [0,-FACADE,LENGTH,FACADE],
         "annex_rect": [ANNEX_X,ANNEX_END,LENGTH,-FACADE-EXT],
         "scale": {"width_k": 1.3, "height_k": 1.15, "room_widths": [3.9, 5.07, 5.46, 5.85],
                   "room_depth": ROOM_D, "corridor_clear": HALF * 2, "ceiling_clear": HEIGHTS, "floor_y": LEVELS,
                   "door_clear": [DOOR_W, DOOR_H], "entrance_clear": [2.4, 2.7],
                   "walls": {"facade": EXT, "load": LOAD, "partition": PART, "stair": .3},
                   "stair_width": 1.5, "stair_gap": .3, "stair_core_width": SC1 - SC0,
                   "tread": .3, "eye": 1.62, "fov_h": 80., "window_width": WINDOW_W, "window_leaf_scale": 1.15},
         "finish": {"paint_lower_fraction": 2 / 3, "green": "59654c", "white": "dfe1d9", "tile_m": .2},
         "reference": {"owner_images": "референсы/dorm/01.png … 20.png", "passport": "https://files.stroyinf.ru/Data2/2/4294852/4294852709.pdf"},
         "sections": {}, "spaces": [], "doors": [], "windows": [], "stairs": [], "barriers": [],
         "locations": [], "shots": [], "routes": [], "floor_routes": [], "circulation": [],
         "stair_core": {"rect": [SC0, -FACADE, SC1, -ROOM_EDGE], "front_z": SZ, "center_x": SCX},
         "outline": [[-EXT,-FACADE-EXT],[ANNEX_X-EXT,-FACADE-EXT],[ANNEX_X-EXT,ANNEX_END-EXT],
                     [LENGTH+EXT,ANNEX_END-EXT],[LENGTH+EXT,FACADE+EXT],[-EXT,FACADE+EXT]],
         "checks": {"ceiling_probe_x": (BAYS[1]["x0"] + BAYS[1]["x1"]) / 2}}

    def section(key):
        return p["sections"].setdefault(key, {"boxes": [], "beams": [], "stairs": [], "labels": [], "lights": [], "probes": []})

    def box(key, name, rect, y0, y1, mat="wall", solid=True):
        x0,z0,x1,z1 = rect
        if min(x1-x0,z1-z0,y1-y0) <= .0005:
            return
        section(key)["boxes"].append({"id": name, "at": [(x0+x1)/2,(y0+y1)/2,(z0+z1)/2],
                                      "size": [x1-x0,y1-y0,z1-z0], "mat": mat, "solid": solid, "yaw": 0})

    def beam(key, a, b, w=.06, depth=.06, mat="rail", solid=True):
        section(key)["beams"].append({"start": a, "end": b, "width": w, "depth": depth, "mat": mat, "solid": solid})

    def label(key, text, at, yaw=0):
        section(key)["labels"].append({"text": text, "at": at, "yaw": yaw})

    def wall(key, name, a0, a1, center, thick, y, h, holes=(), axis="z", mat="wall", solid=True):
        def piece(lo,hi,bottom,top):
            r = [lo,center-thick/2,hi,center+thick/2] if axis=="z" else [center-thick/2,lo,center+thick/2,hi]
            box(key,name,r,bottom,top,mat,solid)
        pos = a0
        for c,w,sill,dh in sorted(holes):
            lo,hi = c-w/2,c+w/2
            assert lo>=pos-.001 and hi<=a1+.001, (name,axis,a0,a1,lo,hi,pos)
            piece(pos,lo,y,y+h)
            piece(lo,hi,y,y+sill)
            piece(lo,hi,y+sill+dh,y+h)
            pos = hi
        piece(pos,a1,y,y+h)

    def door(key, name, along, constant, y, side=1, w=DOOR_W, dh=DOOR_H, axis="z", opened=True):
        x,z = (along,constant) if axis=="z" else (constant,along)
        p["doors"].append({"id": name, "at": [x,y,z], "width": w, "height": dh, "axis": axis, "open": opened})
        for a in [along-w/2-.025,along+w/2+.025]:
            r = [a-.025,constant-.22,a+.025,constant+.22] if axis=="z" else [constant-.22,a-.025,constant+.22,a+.025]
            box(key,name+"_jamb",r,y,y+dh,"frame")
        r = [along-w/2-.05,constant-.22,along+w/2+.05,constant+.22] if axis=="z" else [constant-.22,along-w/2-.05,constant+.22,along+w/2+.05]
        box(key,name+"_header",r,y+dh,y+dh+.05,"frame")
        if not opened:
            r = [along-w/2,constant-.06,along+w/2,constant+.06] if axis=="z" else [constant-.06,along-w/2,constant+.06,along+w/2]
            box(key,name+"_sealed",r,y,y+dh,"sealed")
        at = [x,y+dh+.12,z-side*.25] if axis=="z" else [x+side*.25,y+dh+.12,z]
        label(key,name,at,(180 if side>0 else 0) if axis=="z" else 90)

    def window(key, x, z, bottom, floor, axis="z", width=WINDOW_W, height=1.65):
        p["windows"].append({"at": [x,bottom,z], "width": width, "height": height, "floor": floor, "leaf_scale": 1.15})
        r = [x-width/2,z-.02,x+width/2,z+.02] if axis=="z" else [x-.02,z-width/2,x+.02,z+width/2]
        box(key,"window_glass",r,bottom,bottom+height,"glass")
        for off in [-width/2+.035,0,width/2-.035]:
            r = [x+off-.035,z-.06,x+off+.035,z+.06] if axis=="z" else [x-.06,z+off-.035,x+.06,z+off+.035]
            box(key,"window_frame",r,bottom,bottom+height,"frame")
        for yy in [bottom,bottom+height]:
            r = [x-width/2,z-.10,x+width/2,z+.10] if axis=="z" else [x-.10,z-width/2,x+.10,z+width/2]
            box(key,"window_rail",r,yy-.035,yy+.035,"frame")

    def space(sid,name,kind,f,rect,path,probes=None,polygon=None):
        s = {"id": sid,"label": name,"kind": kind,"floor": f+1,"y": LEVELS[f],"rect": rect,
             "open": f<3,"path": path,"probe_points": probes or []}
        if polygon:
            s["polygon"] = polygon
        p["spaces"].append(s)
        return s

    def bathroom(key, rect, f, door_at, axis="z", side=-1):
        x0,z0,x1,z1 = rect
        y,h = LEVELS[f],HEIGHTS[f]
        # Тонкая облицовка даёт плитку только внутри; снаружи остаётся краска коридора.
        box(key,"tile_floor",[x0+.01,z0+.01,x1-.01,z1-.01],y+.002,y+.008,"tile_floor",False)
        for z in [z0+.008,z1-.008]:
            holes = [(door_at,DOOR_W,0,DOOR_H)] if axis=="z" and ((side<0 and z>0.5*(z0+z1)) or (side>0 and z<.5*(z0+z1))) else []
            wall(key,"tile_lining",x0+.01,x1-.01,z,.012,y+.01,h-.02,holes,mat="tile",solid=False)
        for x in [x0+.008,x1-.008]:
            holes = [(door_at,DOOR_W,0,DOOR_H)] if axis=="x" and x>.5*(x0+x1) else []
            wall(key,"tile_lining",z0+.01,z1-.01,x,.012,y+.01,h-.02,holes,axis="x",mat="tile",solid=False)
        mz = (z0+z1)/2
        if axis=="x":
            mx=(x0+x1)/2
            box(key,"mirror_frame",[mx-.95,z0+.025,mx+.95,z0+.10],y+1.0,y+2.15,"frame",False)
            box(key,"mirror",[mx-.87,z0+.10,mx+.87,z0+.105],y+1.08,y+2.07,"mirror",False)
            box(key,"sink_counter",[mx-.97,z0+.08,mx+.97,z0+.62],y+.78,y+.88,"ceramic")
            for dx in [-.5,.5]:
                box(key,"sink_basin",[mx+dx-.23,z0+.16,mx+dx+.23,z0+.55],y+.88,y+.92,"basin",False)
                beam(key,[mx+dx,y+.92,z0+.2],[mx+dx,y+1.1,z0+.2],.035,.035,"rail",False)
        else:
            box(key,"mirror_frame",[x1-.10,mz-.95,x1-.025,mz+.95],y+1.0,y+2.15,"frame",False)
            box(key,"mirror",[x1-.105,mz-.87,x1-.10,mz+.87],y+1.08,y+2.07,"mirror",False)
            box(key,"sink_counter",[x1-.62,mz-.97,x1-.08,mz+.97],y+.78,y+.88,"ceramic")
            for dz in [-.5,.5]:
                box(key,"sink_basin",[x1-.55,mz+dz-.23,x1-.16,mz+dz+.23],y+.88,y+.92,"basin",False)
                beam(key,[x1-.2,y+.92,mz+dz],[x1-.2,y+1.1,mz+dz],.035,.035,"rail",False)
        if f<3:
            section(key)["probes"].append({"at": [(x0+x1)/2,y+h/2,mz],"size": [x1-x0,h,z1-z0]})

    def bunks(key, rect, y):
        x0,z0,x1,z1 = rect
        side = -1 if z1<0 else 1
        za,zb = sorted([side*(FACADE-.6),side*(FACADE-2.6)])
        for xa,xb in [(x0+.14,x0+1.04),(x1-1.04,x1-.14)]:
            for x in [xa+.025,xb-.025]:
                for z in [za+.025,zb-.025]:
                    box(key,"bunk_post",[x-.025,z-.025,x+.025,z+.025],y,y+1.78,"rail")
            for yy in [.37,1.32]:
                box(key,"bunk_frame",[xa,za,xb,zb],y+yy-.06,y+yy,"frame")
                box(key,"bunk_mattress",[xa+.04,za+.03,xb-.04,zb-.03],y+yy,y+yy+.10,"mattress")
            beam(key,[xa,y+1.64,za],[xa,y+1.64,zb],.035,.035)

    def gate(key, sid, center, y, h, x0, x1, label_text):
        box(key,sid+"_base",[x0,center-.10,x1,center+.10],y,y+1.25,"sealed")
        for i in range(int((x1-x0)/.16)+1):
            x = min(x1-.02,x0+.02+i*.16)
            box(key,sid+"_bar",[x-.02,center-.05,x+.02,center+.05],y+1.25,y+h,"rail")
        p["barriers"].append({"id":sid,"label":label_text,"from":[(x0+x1)/2,y,center+.85],
                              "to":[(x0+x1)/2,y,center-.85],"point":[(x0+x1)/2,y,center],"normal":[0,0,1]})

    # Двор и оба входа. Въездов, транспорта и новых игровых механик здесь нет.
    box("Site","ground",[-14,-49,LENGTH+15,26],-.3,0,"ground")
    box("Site","main_plinth",[-EXT,-FACADE-EXT,LENGTH+EXT,FACADE+EXT],0,BASE-SLAB,"slab")
    box("Site","front_apron",[-1,FACADE+EXT,LENGTH+1,FACADE+EXT+1.2],-.04,.025,"paving")
    box("Site","entry_porch",[-.35,FACADE+EXT,4.25,PORCH_END],0,BASE,"floor")
    for i in range(3):
        box("Site","entry_step",[-.1,PORCH_END+i*.3,4,PORCH_END+(i+1)*.3],0,BASE-i*.16,"floor")
    box("Site","rear_porch",[LENGTH+EXT,-1.7,LENGTH+2.2,1.7],0,BASE,"floor")
    for i in range(3):
        box("Site","rear_step",[LENGTH+2.2+i*.3,-1.5,LENGTH+2.5+i*.3,1.5],0,BASE-i*.16,"floor")
    for x,z in [(-6,-13),(LENGTH-7,17)]:
        box("Site","tree_trunk",[x-.18,z-.18,x+.18,z+.18],0,5,"tree")
        box("Site","tree_crown",[x-1.6,z-1.6,x+1.6,z+1.6],3.1,8,"tree",False)
    box("Site","lamp",[7.9,16.9,8.1,17.1],0,5.5,"rail")
    box("Site","lamp_head",[7.6,16.6,8.4,17.4],5.4,5.55,"frame",False)

    for f,(y,h) in enumerate(zip(LEVELS,HEIGHTS)):
        key = f"Floor{f+1}"
        # Проём центральной лестницы вырезан из перекрытий, а не закрыт невидимой плоскостью.
        for rect in [[0,-FACADE,SC0,FACADE],[SC1,-FACADE,LENGTH,FACADE],[SC0,-ROOM_EDGE,SC1,FACADE]]:
            box(key,"floor",rect,y-SLAB,y,"floor")
        if f==0:
            box(key,"stair_ground",[SC0,-FACADE,SC1,-ROOM_EDGE],y-SLAB,y,"floor")
        corridor_holes = {-1:[],1:[]}
        for b,bay in enumerate(BAYS):
            x0,x1,w = bay["x0"],bay["x1"],bay["width"]
            cx = (x0+x1)/2
            for side in [-1,1]:
                if side==-1 and b==4:
                    corridor_holes[side].append((SCX,1.8,0,DOOR_H))
                    door(key,"ЛЕСТНИЦА",SCX,-HALF-LOAD/2,y,-1,w=1.8,opened=f<3)
                    continue
                # Примыкание крыла: наружная стена становится внутренней, окон между комнатами нет.
                if side==-1 and b>=7:
                    holes = [(TURN_X,2.4,0,DOOR_H)] if b==8 else []
                    offset=SLAB if f==0 else 0
                    wall(key,"annex_junction",x0,x1,-FACADE-EXT/2,EXT,y-offset,h+SLAB+offset,[(a,w,s+offset,dh) for a,w,s,dh in holes])
                else:
                    entrance = f==0 and side==1 and b==0
                    offset=SLAB if f==0 else 0
                    wh = [(cx,2.4,offset,2.7)] if entrance else [(cx,WINDOW_W,.95+offset,1.65)]
                    wall(key,"facade",x0,x1,side*(FACADE+EXT/2),EXT,y-offset,h+SLAB+offset,wh)
                    if entrance:
                        door(key,"ВХОД",cx,side*(FACADE+EXT/2),y,1,w=2.4,dh=2.7)
                    else:
                        window(key,cx,side*(FACADE+EXT/2),y+.95,f+1)
                if side==1 and b in [4,5]:
                    if b==4:
                        a,big = BAYS[4]["x0"]+.12,BAYS[5]["x1"]-.12
                        corridor_holes[side].append(((a+big)/2,big-a,0,DOOR_H))
                    continue
                if side==-1 and b==0:
                    kind,name = "toilets","ТУАЛЕТ"
                elif side==-1 and b==6:
                    kind,name = ("commandant","КОМЕНДАНТ") if f==0 else ("storage","БЕЛЬЕВАЯ")
                elif side==-1 and b==7:
                    kind,name = "laundry","ПОСТИРОЧНАЯ"
                elif side==-1 and b==8:
                    kind,name = "turn","ХОЗКРЫЛО"
                elif side==1 and b==0:
                    kind,name = ("hall","ХОЛЛ / ВАХТА") if f==0 else ("storage","КЛАДОВАЯ")
                else:
                    kind,name = "room",str((f+1)*100+b*2+(1 if side<0 else 2))
                dx = cx if kind in ["hall","turn"] else x0+1.1
                if kind=="turn":
                    dx=TURN_X
                dw = 2.4 if kind in ["hall","turn"] else DOOR_W
                dh = 2.7 if kind=="hall" else DOOR_H
                corridor_holes[side].append((dx,dw,0,dh))
                door(key,name,dx,side*(HALF+LOAD/2),y,side,w=dw,dh=dh,opened=f<3)
                z0,z1 = sorted([side*ROOM_EDGE,side*FACADE])
                rect=[x0,z0,x1,z1]
                path=[[dx,y,0],[dx,y,side*(ROOM_EDGE+1.0)],[cx,y,side*5.7]]
                probes=[[cx,y,side*(FACADE-1.0)],[cx,y,side*(ROOM_EDGE+1.0)]]
                if kind=="hall":
                    rect=[x0,ROOM_EDGE,x1,7.0]
                    path=[[ENTRY_X,y,0],[ENTRY_X,y,3.2],[LANE_X,y,5.4],[LANE_X,y,6.4]]
                    probes=[]
                s=space(f"f{f+1}_{kind}_{side}_{b}",name,kind,f,rect,path,probes)
                if kind=="room":
                    s["width_scale"]=w/3.9
                    s["state"]=STATES[(b+f+(1 if side>0 else 0))%len(STATES)]
                    s["probe_points"]=[[cx,y,side*(FACADE-.95)],[cx,y,side*5.9],
                                       [x0+.8,y,side*(ROOM_EDGE+1.0)],[x1-.8,y,side*(ROOM_EDGE+1.0)]]
                    bunks(key,rect,y)
                if kind=="toilets":
                    bathroom(key,rect,f,dx)
                    s["probe_points"]=[[cx,y,-FACADE+2.5],[cx,y,-3.3]]
                    # Пока только габариты кабин и чаш; центр остаётся проходом к умывальникам.
                    for k in range(3):
                        xx=x0+.7+k*1.15
                        box(key,"wc_pan",[xx-.22,-FACADE+.5,xx+.22,-FACADE+1.15],y,y+.42,"ceramic")
                if kind=="commandant":
                    box(key,"office_desk",[x0+.35,z0+1.0,x0+2.1,z0+1.8],y,y+.75,"wood")
                    box(key,"office_chair",[x0+.8,z0+2.15,x0+1.3,z0+2.65],y,y+.46,"frame")
                    box(key,"office_cabinet",[x1-.65,z0+.35,x1-.1,z0+2.1],y,y+1.9,"wood")
            if b<len(BAYS)-1:
                next_x=BAYS[b+1]["x0"]
                for side in [-1,1]:
                    offset=SLAB if f==0 else 0
                    box(key,"facade_pier",[x1,side*(FACADE+EXT/2)-EXT/2,next_x,side*(FACADE+EXT/2)+EXT/2],y-offset,y+h+SLAB)
                    if side==1 and b==4:
                        continue
                    za,zb=sorted([side*ROOM_EDGE,side*FACADE])
                    box(key,"partition",[x1,za,next_x,zb],y,y+h+SLAB)
        for side in [-1,1]:
            wall(key,"corridor_load",0,LENGTH,side*(HALF+LOAD/2),LOAD,y,h+SLAB,corridor_holes[side])
        # Торцы корпуса: чёрный выход только на первом, выше — дневное окно в конце коридора.
        offset=SLAB if f==0 else 0
        wall(key,"west_end",-FACADE,FACADE,-EXT/2,EXT,y-offset,h+SLAB+offset,axis="x")
        east_holes=[(0,1.8,offset,DOOR_H)] if f==0 else [(0,1.8,.95+offset,1.65)]
        wall(key,"east_end",-FACADE,FACADE,LENGTH+EXT/2,EXT,y-offset,h+SLAB+offset,east_holes,axis="x")
        if f==0:
            door(key,"ЧЁРНЫЙ ВЫХОД",0,LENGTH+EXT/2,y,w=1.8,axis="x")
        else:
            window(key,LENGTH+EXT/2,0,y+.95,f+1,"x",1.8)
        # Общая зона напротив лестницы: окно в широком объёме и неглубокая боковая ниша.
        a,b,c=BAYS[4]["x0"],BAYS[5]["x0"],BAYS[5]["x1"]
        poly=[[a,ROOM_EDGE],[c,ROOM_EDGE],[c,FACADE],[b,FACADE],[b,5.6],[a,5.6]]
        space(f"f{f+1}_lounge","ГОСТИНАЯ","lounge",f,[a,ROOM_EDGE,c,FACADE],
              [[SCX,y,0],[SCX,y,3.8],[b+1.4,y,3.8],[b+1.4,y,7.1]],
              [[c-1.4,y,FACADE-1.0],[b+1.4,y,FACADE-1.0],[b+1.4,y,3.8],[a+1.0,y,3.8]],poly)
        wall(key,"lounge_store",a,SC1,5.675,PART,y,h,[(SCX,DOOR_W,0,DOOR_H)])
        door(key,"КЛАДОВАЯ",SCX,5.675,y,1,opened=f<3)
        # Кладовка ограничена только шириной своего модуля.
        box(key,"lounge_store_side",[SC1,5.6,b,FACADE],y,y+h+SLAB)
        space(f"f{f+1}_lounge_store","КЛАДОВАЯ ПРИ ГОСТИНОЙ","storage",f,[a,5.75,SC1,FACADE],
              [[SCX,y,0],[SCX,y,3.8],[SCX,y,7.4]],[[SCX,y,FACADE-.8]])
        for xx in [b+.7,c-.7]:
            box(key,"seat_scale",[xx-.25,FACADE-3.78,xx+.25,FACADE-1.98],y,y+.45,"wood")
        box(key,"lounge_table",[b+2.0,FACADE-4.48,c-2.0,FACADE-3.58],y,y+.55,"wood")
        # Входной контроль оставлен открытым; новые игровые правила турникета не вводятся.
        if f==0:
            wall(key,"vestibule",0,WIDTHS[0],7.075,PART,y,h,[(ENTRY_X,2.4,0,2.7)])
            door(key,"ТАМБУР",ENTRY_X,7.075,y,1,w=2.4,dh=2.7)
            space("f1_vestibule","ТАМБУР","vestibule",f,[0,7.15,WIDTHS[0],FACADE],
                  [[ENTRY_X,y,0],[ENTRY_X,y,3.2],[LANE_X,y,5.4],[LANE_X,y,6.4],[ENTRY_X,y,(7.15+FACADE)/2]],[[ENTRY_X,y,FACADE-.6]])
            box(key,"guard_desk",[.18,4.0,1.55,4.7],y,y+.9,"wood")
            box(key,"guard_screen",[.45,4.2,1.05,4.33],y+1.0,y+1.36,"frame",False)
            box(key,"turnstile_body",[1.5,5.0,1.9,5.8],y,y+1.0,"rail")
            box(key,"turnstile_right_post",[3.45,5.2,3.62,5.45],y,y+1.05,"rail")
            beam(key,[1.83,y+.9,5.25],[1.83,y+.9,6.05],.055,.055)
            beam(key,[3.5,y+1.0,5.3],[3.5,y+1.0,6.4],.05,.05)
            beam(key,[.1,y+1.0,5.3],[1.5,y+1.0,5.3],.06,.06)
            label(key,"ВАХТА · ПРОХОД",[.9,y+1.9,4.05],180)
            space("f1_watch","ВАХТА / СТОЛ","watch",f,[.1,2.3,1.6,3.9],
                  [[ENTRY_X,y,0],[ENTRY_X,y,3.0],[.9,y,3.0]],[[.9,y,3.3]])
        for bay in BAYS[1:8:2]:
            xx=bay["x1"]+.07
            box(key,"corridor_rib",[xx-.12,-HALF,xx+.12,HALF],y+h-.15,y+h,"slab")
        if f<3:
            for xx in [2.5,11,SCX,31,LENGTH-2]:
                section(key)["lights"].append({"at":[xx,y+h-.25,0],"energy":.72,"range":7.3})
            for s in p["spaces"]:
                if s["floor"]==f+1 and s["open"]:
                    r=s["rect"]
                    section(key)["lights"].append({"at":[(r[0]+r[2])/2,y+h-.25,(r[1]+r[3])/2],"energy":.35,"range":6.5})
        if f<3:
            p["floor_routes"].append({"floor":f+1,"start":[SCX,y,0],"end":[LENGTH-.8,y,0]})
            p["circulation"].extend([{"floor":f+1,"rect":[0,-HALF,LENGTH,HALF]},
                                      {"floor":f+1,"rect":[ANNEX_CORRIDOR,ANNEX_END,LENGTH,-FACADE]}])

    # Лестница внутри корпуса: по 1,5 м от стены до центрального промежутка, без боковых щелей.
    key="CentralStair"
    holes=[]
    for f,y in enumerate(LEVELS):
        if f<4:
            ym=(y+LEVELS[f+1])/2
            holes.append((ym+.55,1.65))
        else:
            holes.append((y+.8,1.65))
    wz=-FACADE-EXT/2
    wx=WINDOW_W
    wall(key,"stair_window_left",SC0,SCX-wx/2,wz,EXT,BASE-SLAB,LEVELS[-1]+HEIGHTS[-1]+SLAB-BASE+SLAB)
    wall(key,"stair_window_right",SCX+wx/2,SC1,wz,EXT,BASE-SLAB,LEVELS[-1]+HEIGHTS[-1]+SLAB-BASE+SLAB)
    bottom=BASE-SLAB
    for f,(wy,wh) in enumerate(holes):
        box(key,"stair_spandrel",[SCX-wx/2,wz-EXT/2,SCX+wx/2,wz+EXT/2],bottom,wy,"wall")
        window(key,SCX,wz,wy,f+1,height=wh)
        bottom=wy+wh
    box(key,"stair_spandrel",[SCX-wx/2,wz-EXT/2,SCX+wx/2,wz+EXT/2],bottom,LEVELS[-1]+HEIGHTS[-1]+SLAB,"wall")
    for f,y in enumerate(LEVELS):
        box(key,"stair_front_landing",[SC0,SZ,SC1,-ROOM_EDGE],y-SLAB,y,"floor")
        if f==4:
            continue
        yy=LEVELS[f+1]
        count=12 if f==0 else 10
        run=count*.3
        zm=SZ-run
        ym=(y+yy)/2
        box(key,"stair_half_landing",[SC0,-FACADE,SC1,zm],ym-SLAB,ym,"floor")
        left,right=SC0+.75,SC1-.75
        for start,end in [([left,y,SZ],[left,ym,zm]),([right,ym,zm],[right,yy,SZ])]:
            s={"start":start,"end":end,"width":1.5,"count":count,"mat":"slab","floor":f+1}
            section(key)["stairs"].append(s)
            p["stairs"].append({**s,"side":"central","riser":(yy-y)/(2*count),"tread":.3})
            edge=SC0+1.5 if start[0]<SCX else SC1-1.5
            beam(key,[edge,start[1]+1.05,start[2]],[edge,end[1]+1.05,end[2]],.055,.065)
            for k in [.05,.35,.65,.95]:
                zz=start[2]+(end[2]-start[2])*k
                hh=start[1]+(end[1]-start[1])*k
                beam(key,[edge,hh,zz],[edge,hh+1.05,zz],.035,.035)
        if f<2:
            pts=[[SCX,y,0],[SCX,y,-ROOM_EDGE-.65],[left,y,SZ+.45],[left,y,SZ],
                 [left,ym,zm-.6],[right,ym,zm-.6],[right,ym,zm],
                 [right,yy,SZ],[right,yy,SZ+.45],[SCX,yy,-ROOM_EDGE-.65],[SCX,yy,0]]
            p["routes"].extend([{"id":f"up{f+1}","label":f"Лестница {f+1} → {f+2}","points":pts},
                                {"id":f"down{f+1}","label":f"Лестница {f+2} → {f+1}","points":list(reversed(pts))}])
        if f==2:
            gate(key,"upper_floors",SZ-.12,y,HEIGHTS[f],SC0,SC0+1.5,"Подъём на 4–5 этажи")
        if f<3:
            space(f"f{f+1}_stairs","ЦЕНТРАЛЬНАЯ ЛЕСТНИЦА","stairs",f,[SC0,SZ,SC1,-ROOM_EDGE],
                  [[SCX,y,0],[SCX,y,-ROOM_EDGE-.65]],[[SC0+.75,y,SZ+.55],[SC1-.75,y,SZ+.55]])
            section(key)["lights"].append({"at":[SCX,y+2.4,SZ-.8],"energy":.7,"range":7})

    # Хозяйственный отворот буквой Г. Остаток за решёткой виден, но не доступен.
    key="NorthAnnex"
    service_kinds=[("kitchen","КУХНЯ"),("wash","УМЫВАЛЬНЯ"),("showers","ДУШЕВЫЕ"),("toilets","ТУАЛЕТЫ")]
    for f,(y,h) in enumerate(zip(LEVELS,HEIGHTS)):
        box(key,"annex_floor",[ANNEX_X,ANNEX_END,LENGTH,-FACADE-EXT],y-SLAB,y,"floor")
        wh,dh=[],[]
        for i,(kind,name) in enumerate(service_kinds):
            z1=-FACADE-EXT-.2-i*4.3
            z0=z1-4.15
            zc=(z0+z1)/2
            wh.append((zc,WINDOW_W,.95,1.65))
            dh.append((zc,DOOR_W,0,DOOR_H))
            box(key,"service_partition",[ANNEX_X,z0-PART,ANNEX_CORRIDOR-LOAD,z0],y,y+h+SLAB)
            if i==0:
                box(key,"service_partition",[ANNEX_X,z1,ANNEX_CORRIDOR-LOAD,z1+PART],y,y+h+SLAB)
            window(key,ANNEX_X-EXT/2,zc,y+.95,f+1,"x")
            door(key,name,zc,ANNEX_WALL,y,axis="x",opened=f<3)
            rect=[ANNEX_X,z0,ANNEX_CORRIDOR-LOAD,z1]
            cc=(rect[0]+rect[2])/2
            space(f"f{f+1}_annex_{kind}",name,kind,f,rect,
                  [[TURN_X,y,0],[TURN_X,y,-6],[TURN_X,y,zc],[cc,y,zc]],
                  [[ANNEX_X+.8,y,z0+.8],[cc,y,z1-.8]])
            if kind in ["wash","showers","toilets"]:
                bathroom(key,rect,f,zc,"x")
            if f<3:
                section(key)["lights"].append({"at":[cc,y+h-.25,zc],"energy":.45,"range":5.5})
        wall(key,"annex_facade",ANNEX_END,-FACADE-EXT,ANNEX_X-EXT/2,EXT,y,h+SLAB,wh,"x")
        wall(key,"annex_east",ANNEX_END,-FACADE-EXT,LENGTH+EXT/2,EXT,y,h+SLAB,axis="x")
        wall(key,"annex_corridor",ANNEX_END,-FACADE-EXT,ANNEX_WALL,LOAD,y,h+SLAB,dh,"x")
        wall(key,"annex_end",ANNEX_X,LENGTH,ANNEX_END-EXT/2,EXT,y,h+SLAB)
        if f<3:
            gate(key,f"annex_f{f+1}",-29.2,y,h,ANNEX_CORRIDOR,LENGTH,f"Закрытая часть хозкрыла, {f+1} этаж")
            for z in [-13,-21,-27.5]:
                section(key)["lights"].append({"at":[TURN_X,y+h-.25,z],"energy":.65,"range":6.5})
            p["routes"].append({"id":f"turn_f{f+1}","label":f"{f+1} этаж: лестница → гостиная → поворот Г",
                                "points":[[SCX,y,0],[SCX,y,3.8],[BAYS[5]["x0"]+2,y,3.8],
                                          [SCX,y,3.8],[SCX,y,0],[TURN_X,y,0],[TURN_X,y,-6],[TURN_X,y,-28.2]]})
    roof=LEVELS[-1]+HEIGHTS[-1]
    box("Roof","roof",[0,-FACADE,LENGTH,FACADE],roof,roof+SLAB,"slab")
    box("Roof","annex_roof",[ANNEX_X,ANNEX_END,LENGTH,-FACADE-EXT],roof,roof+SLAB,"slab")
    for z in [-FACADE-EXT/2,FACADE+EXT/2]:
        box("Roof","parapet",[-EXT,z-.15,LENGTH+EXT,z+.15],roof+SLAB,roof+SLAB+.4,"wall")
    p["routes"].append({"id":"entry_to_back","label":"Вход → турникет → коридор → чёрный выход",
                        "points":[[ENTRY_X,0,17],[ENTRY_X,0,14.4],[ENTRY_X,BASE,12.0],[ENTRY_X,BASE,8.4],
                                  [LANE_X,BASE,6.5],[LANE_X,BASE,5.4],[LANE_X,BASE,4.5],[ENTRY_X,BASE,3.1],
                                  [ENTRY_X,BASE,0],[SCX,BASE,0],[LENGTH-1,BASE,0],[LENGTH+1.3,BASE,0],
                                  [LENGTH+3.8,0,0],[LENGTH+5,0,4]]})
    p["routes"].append({"id":"back_to_entry","label":"Чёрный выход → турникет → главный вход",
                        "points":list(reversed(p["routes"][-1]["points"]))})
    # Редакция камер 3: ракурсы сохранены, позиции лестницы и крыла следуют за их геометрией.
    wide=BAYS[2]
    narrow=BAYS[7]
    kitchen_z=-FACADE-EXT-.2-4.15/2
    bath_x=(ANNEX_X+ANNEX_CORRIDOR-LOAD)/2
    views=[
        ("01_corridor","Коридор от входа",[ENTRY_X,LEVELS[1],0],[LENGTH-1,LEVELS[1]+1.62,0]),
        ("02_room","Широкая комната ×1,3",[(wide["x0"]+wide["x1"])/2,LEVELS[1],-3.3],[(wide["x0"]+wide["x1"])/2,LEVELS[1]+1.62,-FACADE]),
        ("03_kitchen","Кухня в хозкрыле",[bath_x+1,LEVELS[1],kitchen_z],[ANNEX_X,LEVELS[1]+1.62,kitchen_z]),
        ("04_wash","Плитка и зеркало",[bath_x-.8,LEVELS[1],kitchen_z-3.2],[bath_x,LEVELS[1]+1.55,kitchen_z-6.2]),
        ("05_stairs_bottom","Центральная лестница снизу",[SC0+.75,LEVELS[0],SZ+.55],[SC0+.75,LEVELS[0]+2.7,SZ-3.4]),
        ("06_stairs_top","Центральная лестница сверху",[SC1-.75,LEVELS[1],SZ+.55],[SC1-.75,LEVELS[0]+2.4,SZ-3.4]),
        ("07_hall","Вход, турникет и вахта",[ENTRY_X,BASE,6.6],[1.8,BASE+1.3,3.5]),
        ("08_street","Главный вход с улицы",[-7,0,23],[13,5.5,0]),
        ("09_lounge","Гостиная напротив лестницы",[SCX,LEVELS[1],3.4],[BAYS[5]["x1"]-1,LEVELS[1]+1.62,8.5]),
        ("10_turn","Поворот в хозкрыло",[TURN_X,LEVELS[1],-4],[TURN_X,LEVELS[1]+1.62,-27]),
        ("11_back_exit","Чёрный выход",[LENGTH-4,BASE,0],[LENGTH+4,BASE+1.62,0]),
        ("12_commandant","Кабинет коменданта",[BAYS[6]["x0"]+2.6,BASE,-3.3],[BAYS[6]["x0"]+1,BASE+1.62,-8]),
        ("13_narrow_room","Узкая комната ×1,0",[(narrow["x0"]+narrow["x1"])/2,LEVELS[1],3.3],[(narrow["x0"]+narrow["x1"])/2,LEVELS[1]+1.62,FACADE]),
        ("14_toilets","Первый туалет у входа",[2,BASE,-3.3],[2.7,BASE+1.55,-7.2]),
    ]
    for i,(sid,name,foot,look) in enumerate(views,1):
        p["locations"].append({"id":i,"label":name,"foot":foot,"look":look})
        p["shots"].append({"id":sid,"label":name,"foot":foot,"look":look,"eye_height":1.62})
    return rounded(p)


def scene_text(plan):
    text='''[gd_scene load_steps=6 format=3]

[ext_resource type="Script" path="res://src/blockout/dorm_geometry.gd" id="1"]
[sub_resource type="ProceduralSkyMaterial" id="SkyMaterial"]
sky_top_color = Color(0.38, 0.48, 0.62, 1)
sky_horizon_color = Color(0.73, 0.77, 0.8, 1)
ground_bottom_color = Color(0.24, 0.25, 0.27, 1)
ground_horizon_color = Color(0.73, 0.77, 0.8, 1)
[sub_resource type="Sky" id="Sky"]
sky_material = SubResource("SkyMaterial")
[sub_resource type="Environment" id="Environment"]
background_mode = 2
sky = SubResource("Sky")
ambient_light_source = 3
ambient_light_color = Color(0.8, 0.84, 0.92, 1)
ambient_light_energy = 0.42
reflected_light_source = 2
tonemap_mode = 0
ssao_enabled = true
ssao_radius = 1.0
ssao_intensity = 1.25
ssr_enabled = true
[sub_resource type="CameraAttributesPractical" id="Attributes"]
auto_exposure_enabled = false

[node name="DormStudy" type="Node3D"]
[node name="WorldEnvironment" type="WorldEnvironment" parent="."]
environment = SubResource("Environment")
camera_attributes = SubResource("Attributes")
[node name="StudySun" type="DirectionalLight3D" parent="."]
rotation_degrees = Vector3(-35, -32, 0)
light_color = Color(1, 0.94, 0.86, 1)
light_energy = 1.15
shadow_enabled = true
directional_shadow_max_distance = 150.0
'''
    for key in plan["sections"]:
        text+=f'\n[node name="{key}" type="Node3D" parent="."]\nscript = ExtResource("1")\nsection_id = "{key}"\n'
    return text


def main():
    plan=make_plan()
    for rel,text in [("data/blockouts/dorm.json",json.dumps(plan,ensure_ascii=False,indent=2)+"\n"),
                     ("scenes/levels/dorm_study.tscn",scene_text(plan))]:
        path=ROOT/rel
        path.parent.mkdir(parents=True,exist_ok=True)
        if not path.exists() or path.read_text(encoding="utf-8")!=text:
            path.write_text(text,encoding="utf-8",newline="\n")
    from dorm_plan import draw_plan
    draw_plan(plan,ROOT/"docs/plans/dorm.png")
    print(f"dorm v{plan['version']}: {sum(s['open'] for s in plan['spaces'])} помещений; лестница x={SCX:.2f}, корпус {LENGTH:.2f} м; комнаты {plan['scale']['room_widths']}")


if __name__=="__main__":
    main()
