# -*- coding: utf-8 -*-
"""Общежитие, редакция 5: принятая геометрия r4 и отдельный пробный свет.

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
SILL = .85
STATES = ["жилая", "разграбленная", "сгоревшая", "баррикада у окна", "пустая с матрасами"]
# Вертикальные пути (владелец 2026-11-02, docs/design/dorm_routes.md). Проломы стихийные, без лестниц (вторая редакция
# того же дня): slab — кусок перекрытия обломился у края hinge и лежит скатом (по нему заходят пешком, боты тоже; у П1
# под низом ещё куча — 1-й этаж выше), pile — куча обломков ступенями под краем edge, наверх — подтянуться на руках
# (Climb, 1,6 м: с перегрузом не залезть; ботам не по силам), drop — провал вниз (на кучу, обратно не залезть),
# hatch — люк на крышу с вертикальной стальной лестницей (Ladder). floor — этаж, в полу которого дыра; hole — x0, z0,
# x1, z1; start / end / width — где скат или куча (по ним мебель держится в стороне).
BREACHES = [
    {"id": "П1", "kind": "slab", "floor": 2, "room_below": "f1_room_1_2", "room_above": "f2_room_1_2",
     "hole": [9.935, 2.6, 11.335, 7.7], "hinge": "z0", "mound": .8, "start": [10.635, 8.3], "end": [10.635, 2.6], "width": 1.3},
    {"id": "П2", "kind": "pile", "floor": 3, "room_below": "f2_room_-1_5", "room_above": "f3_room_-1_5",
     "hole": [25.4, -6.7, 27.0, -4.9], "edge": "z1", "start": [26.2, -7.8], "end": [26.2, -4.9], "width": 1.6},
    {"id": "П3", "kind": "slab", "floor": 4, "room_below": "f3_room_1_7", "room_above": "f4_room_1_7",
     "hole": [36.15, 2.6, 37.55, 7.7], "hinge": "z0", "mound": 0.0, "start": [36.85, 6.6], "end": [36.85, 2.6], "width": 1.3},
    {"id": "П4", "kind": "pile", "floor": 5, "room_below": "f4_storage_-1_6", "room_above": "roof_hall",
     "hole": [31.6, -6.7, 33.2, -4.9], "edge": "z1", "start": [32.4, -7.8], "end": [32.4, -4.9], "width": 1.6},
    {"id": "Л", "kind": "hatch", "floor": 6, "room_below": "f5_tech_hall", "room_above": "roof",
     "hole": [2.25, 3.4, 3.35, 4.6]},
    {"id": "С1", "kind": "drop", "floor": 4, "room_below": "f3_room_-1_3", "room_above": "f4_room_-1_3",
     "hole": [15.3, -6.2, 17.0, -4.4]},
]
# Проломы в перегородках между соседними помещениями (обход дверей и коридора): этаж, сторона корпуса, отсек слева.
WALL_BREACHES = [(1, 1, 1), (1, -1, 2), (2, -1, 1), (2, 1, 6), (3, 1, 2), (3, -1, 5), (4, -1, 2), (4, 1, 1)]
WALL_BREACH_W, WALL_BREACH_H, WALL_BREACH_V = 1.3, 2.15, 3.2
# Мусор, расставленный по истории (data/blockouts/dorm_props.json, ведётся руками): пролом в стене сдвигается вдоль
# неё, чтобы твёрдая вещь не перегородила проход.
_PROPS_PATH = Path(__file__).resolve().parents[1] / "data/blockouts/dorm_props.json"
SOLID_PROPS = [it["at"] for it in (json.loads(_PROPS_PATH.read_text(encoding="utf-8")).get("props", []) if _PROPS_PATH.exists() else [])
               if it.get("solid")]


def wall_breach_v(x, side, y):
    """Отступ пролома от стены коридора: первый из вариантов, у которого рядом нет твёрдого мусора."""
    for v in [WALL_BREACH_V, 2.6, 3.8, 4.4, 5.0, 2.1]:
        zc = side * (2.08 + v)
        if not any(abs(a[1] - y) < .6 and abs(a[0] - x) < 1.3 and abs(a[2] - zc) < WALL_BREACH_W / 2 + .6 for a in SOLID_PROPS):
            return v
    return WALL_BREACH_V
BREACH_ROOMS = {b[k] for b in BREACHES for k in ("room_below", "room_above") if b[k] not in ("roof", "roof_hall", "f5_tech_hall")}


def subtract(rect, holes):
    """Прямоугольник без дыр — набор прямоугольников (перекрытие с проломами и люками)."""
    out = [rect]
    for h in holes:
        nxt = []
        for x0, z0, x1, z1 in out:
            hx0, hz0, hx1, hz1 = max(x0, h[0]), max(z0, h[1]), min(x1, h[2]), min(z1, h[3])
            if hx0 >= hx1 or hz0 >= hz1:
                nxt.append([x0, z0, x1, z1])
                continue
            for r in ([x0, z0, hx0, z1], [hx1, z0, x1, z1], [hx0, z0, hx1, hz0], [hx0, hz1, hx1, z1]):
                if r[2] - r[0] > .001 and r[3] - r[1] > .001:
                    nxt.append(r)
        out = nxt
    return out


def rounded(v):
    if isinstance(v, float):
        return round(v, 4)
    if isinstance(v, list):
        return [rounded(x) for x in v]
    if isinstance(v, dict):
        return {k: rounded(x) for k, x in v.items()}
    return v


def make_plan():
    p = {"version": 6, "stage": 1, "greybox": True, "north": "-Z",
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
         "reference": {"owner_images": "референсы/dorm/01.png … 20.png; eft_dorm_21.webp … eft_dorm_28.webp", "passport": "https://files.stroyinf.ru/Data2/2/4294852/4294852709.pdf"},
         "sections": {}, "spaces": [], "doors": [], "windows": [], "stairs": [], "barriers": [],
         "portals": [], "niches": [],
         "details": {"beam_drop": .4, "beam_width": .4, "pilaster_width": .45, "pilaster_projection": .18,
                     "casing_width": .08, "casing_projection": .025, "leaf_thickness": .04,
                     "sill_height": SILL, "sill_projection": .28, "radiator_size": [1.0,.55,.1],
                     "skirting_height": .08, "skirting_projection": .02},
         "locations": [], "shots": [], "routes": [], "floor_routes": [], "circulation": [],
         "stair_core": {"rect": [SC0, -FACADE, SC1, -ROOM_EDGE], "front_z": SZ, "center_x": SCX},
         "outline": [[-EXT,-FACADE-EXT],[ANNEX_X-EXT,-FACADE-EXT],[ANNEX_X-EXT,ANNEX_END-EXT],
                     [LENGTH+EXT,ANNEX_END-EXT],[LENGTH+EXT,FACADE+EXT],[-EXT,FACADE+EXT]],
         "checks": {"ceiling_probe_x": (BAYS[1]["x0"] + BAYS[1]["x1"]) / 2},
         "breaches": BREACHES}

    def section(key, group=None):
        s=p["sections"].setdefault(key, {"boxes": [], "beams": [], "stairs": [], "labels": [], "lights": [], "probes": [], "groups": {}})
        if group:
            return s["groups"].setdefault(group, {"boxes": [], "beams": [], "labels": [], "doors": [], "modules": []})
        return s

    def box(key, name, rect, y0, y1, mat="wall", solid=True, group=None):
        x0,z0,x1,z1 = rect
        if min(x1-x0,z1-z0,y1-y0) <= .0005:
            return
        # Верх стены нижнего этажа не совпадает с полом следующего: краска проступала у порогов.
        # Только скрытый торец уходит на 5 мм внутрь плиты; чистые размеры и проёмы прежние.
        if mat=="wall" and any(abs(y1-floor)<.00001 for floor in LEVELS):
            y1-=.005
        # То же под кровлей: перегородки и стены коридора 5-го этажа доходили верхом ровно до верха плиты крыши и мерцали.
        roof_top=LEVELS[-1]+HEIGHTS[-1]+SLAB
        if abs(y1-roof_top)<.00001 and y0<roof_top-SLAB-.001:
            y1-=.005
        section(key,group)["boxes"].append({"id": name, "at": [(x0+x1)/2,(y0+y1)/2,(z0+z1)/2],
                                      "size": [x1-x0,y1-y0,z1-z0], "mat": mat, "solid": solid, "yaw": 0})

    def beam(key, a, b, w=.06, depth=.06, mat="rail", solid=True):
        section(key)["beams"].append({"start": a, "end": b, "width": w, "depth": depth, "mat": mat, "solid": solid})

    def label(key, text, at, yaw=0, group=None, permanent=False):
        section(key,group)["labels"].append({"text": text, "at": at, "yaw": yaw, "permanent": permanent})

    def wall(key, name, a0, a1, center, thick, y, h, holes=(), axis="z", mat="wall", solid=True, group=None, portal_centers=()):
        def piece(lo,hi,bottom,top,lintel=False):
            r = [lo,center-thick/2,hi,center+thick/2] if axis=="z" else [center-thick/2,lo,center+thick/2,hi]
            box(key,name,r,bottom,top,"ceiling" if lintel else mat,solid,"beams" if lintel else group)
        pos = a0
        for c,w,sill,dh in sorted(holes):
            lo,hi = c-w/2,c+w/2
            assert lo>=pos-.001 and hi<=a1+.001, (name,axis,a0,a1,lo,hi,pos)
            piece(pos,lo,y,y+h)
            piece(lo,hi,y,y+sill)
            piece(lo,hi,y+sill+dh,y+h,any(abs(c-pc)<.001 for pc in portal_centers))
            pos = hi
        piece(pos,a1,y,y+h)

    def door(key, name, along, constant, y, side=1, w=DOOR_W, dh=DOOR_H, axis="z", opened=True,
             leaf=True, pose="wide", grille=False, thick=LOAD, inward=None, wide_angle=None):
        x,z = (along,constant) if axis=="z" else (constant,along)
        item={"id": name, "uid":f"door_{len(p['doors']):03d}", "section":key, "at": [x,y,z],
              "width":w, "height":dh, "axis":axis, "open":opened, "leaf":leaf, "pose":pose,
              "grille":grille, "thickness":thick, "inward":side if inward is None else inward, "wide_angle":wide_angle}
        p["doors"].append(item)
        if not opened:
            r = [along-w/2,constant-.06,along+w/2,constant+.06] if axis=="z" else [constant-.06,along-w/2,constant+.06,along+w/2]
            box(key,name+"_sealed",r,y,y+dh,"sealed")
        at = [x,y+dh+.12,z-side*(thick/2+.035)] if axis=="z" else [x+side*(thick/2+.035),y+dh+.12,z]
        label(key,name,at,(180 if side>0 else 0) if axis=="z" else (90 if side>0 else -90),"door_frames",name.isdigit())

    def window(key, x, z, bottom, floor, axis="z", width=WINDOW_W, height=1.65):
        p["windows"].append({"at": [x,bottom,z], "width": width, "height": height, "floor": floor,
                             "axis":axis, "section":key, "leaf_scale": 1.15})
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
             "open": True,"path": path,"probe_points": probes or []}
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

    def fire_escape(name, door_xz, out, along):
        """Наружная маршевая пожарная лестница — каркасная башня (владелец 2026-11-02; образцы — серийные П2 и лестницы
        3-го типа, ограждение 1,2 м по ГОСТ Р 53254): стойки из трубы по углам, обвязка швеллером по краю каждой
        площадки, связи крест-накрест по наружной грани, площадки — решётчатый настил в раме, марши — два косоура из
        швеллера и ступени из просечного листа (видны; ходят по наклонной плоскости), ограждение — поручень, средний
        ряд, стойки и бортик. Площадка у двери каждого этажа и у крыши, между этажами — два марша по 10 ступеней через
        промежуточную площадку, к земле — три ступени. Окраска — сурик с ржавчиной."""
        key="FireEscapes"
        ox,oz=door_xz
        def P(a,o):   # вдоль стены a, от стены o → x, z
            return [ox+along[0]*a+out[0]*o, oz+along[1]*a+out[1]*o]
        def R(a0,o0,a1,o1):
            (x0,z0),(x1,z1)=P(a0,o0),P(a1,o1)
            return [min(x0,x1),min(z0,z1),max(x0,x1),max(z0,z1)]
        def B(a0,o0,y0,a1,o1,y1,w=.045,d=.045,mat="steel_stair",solid=False):
            (x0,z0),(x1,z1)=P(a0,o0),P(a1,o1)
            beam(key,[x0,y0,z0],[x1,y1,z1],w,d,mat,solid)
        def rail(a0,o0,y0,a1,o1,y1,height,posts=1.0,solid=True):
            """Ограждение по прямой: поручень (держит от падения), средний ряд, стойки через ~1 м, бортик 0,1 м."""
            B(a0,o0,y0+height,a1,o1,y1+height,.045,.045,"steel_stair",solid)
            B(a0,o0,y0+height*.5,a1,o1,y1+height*.5,.03,.03)
            B(a0,o0,y0+.06,a1,o1,y1+.06,.012,.1)
            n=max(1,int(round(math.hypot(a1-a0,o1-o0)/posts)))
            for i in range(n+1):
                k=i/n
                aa,oo,yb=a0+(a1-a0)*k,o0+(o1-o0)*k,y0+(y1-y0)*k
                B(aa,oo,yb,aa,oo,yb+height,.035,.035)
        levels=LEVELS+[LEVELS[-1]+HEIGHTS[-1]+SLAB]
        run=2.5
        a_far=-1.0-run
        a_end=a_far-1.2
        W=2.3
        def deck(rect_a0,rect_a1,y):
            box(key,name+"_deck",R(rect_a0,.08,rect_a1,W),y-.035,y,"grating")
            for a0,o0,a1,o1 in [(rect_a0,.08,rect_a1,.08),(rect_a0,W,rect_a1,W),(rect_a0,.08,rect_a0,W),(rect_a1,.08,rect_a1,W)]:
                B(a0,o0,y-.105,a1,o1,y-.105,.06,.14)
        def flight(a0,a1,o,y0,y1,count=10):
            x0,z0=P(a0,o)
            x1,z1=P(a1,o)
            section(key)["stairs"].append({"start":[x0,y0,z0],"end":[x1,y1,z1],"width":1.0,"count":count,"mat":"steel_stair","visual":False})
            for i in range(count):
                k0,k1=i/count,(i+1)/count
                yt=y0+(y1-y0)*k1
                aa,ab=a0+(a1-a0)*k0,a0+(a1-a0)*k1
                box(key,name+"_tread",R(min(aa,ab)+.01,o-.48,max(aa,ab)+.03,o+.48),yt-.03,yt,"grating",False)
            for side in [-.52,.52]:
                B(a0,o+side,y0-.1,a1,o+side,y1-.1,.06,.2)
        for k,y in enumerate(levels):
            deck(-1.0,1.0,y)
            top=k==len(levels)-1
            # ограждение площадки у двери: наружная грань и торец; у 1-го этажа в торце — выход к земле
            rail(-1.0,W,y,1.0,W,y,1.2)
            if k==0:
                rail(1.0,1.75,y,1.0,W,y,1.2)
            else:
                rail(1.0,.08,y,1.0,W,y,1.2)
            if top:
                rail(-1.0,.08,y,-1.0,1.12,y,1.2)
                break
            yy=levels[k+1]
            ym=(y+yy)/2
            deck(a_end,a_far,ym)
            rail(a_end,.08,ym,a_end,W,ym,1.2)
            rail(a_end,W,ym,a_far,W,ym,1.2)
            rail(a_end,.08,ym,a_far,.08,ym,1.2)
            flight(-1.0,a_far,.6,y,ym)
            flight(a_far,-1.0,1.7,ym,yy)
            # между маршами — общий поручень, снаружи второго марша — ограждение марша
            rail(-1.0,1.15,y,a_far,1.15,ym,1.0,1.25,False)
            rail(a_far,W,ym,-1.0,W,yy,1.0,1.25)
        # каркас: стойки до верха ограждения у крыши, связи крест-накрест по наружной грани между этажами
        top_y=levels[-1]+1.2
        for a in [1.0,-1.0,a_far,a_end]:
            for o in [.12,W]:
                if o<1 and a in [-1.0,a_far]:
                    continue
                x,z=P(a,o)
                beam(key,[x,0.0,z],[x,top_y,z],.12,.12,"steel_stair",True)
        for k in range(len(levels)-1):
            y,yy=levels[k],levels[k+1]
            for a0,a1 in [(1.0,-1.0),(a_far,a_end)]:
                B(a0,W+.07,y,a1,W+.07,yy,.05,.05)
                B(a1,W+.07,y,a0,W+.07,yy,.05,.05)
            B(a_end-.07,.12,y,a_end-.07,W,yy,.05,.05)
            B(a_end-.07,W,y,a_end-.07,.12,yy,.05,.05)
        # анкеры площадок в стену
        for k,y in enumerate(levels):
            for a in [-.8,.8]:
                B(a,0.0,y-.18,a,.08,y-.18,.08,.08)
        # три ступени к земле с площадки 1-го этажа (наружу, вдоль стены)
        x0,z0=P(1.0,1.15)
        x1,z1=P(1.9,1.15)
        section(key)["stairs"].append({"start":[x0,LEVELS[0],z0],"end":[x1,0.0,z1],"width":1.0,"count":3,"mat":"steel_stair","visual":False})
        for i in range(3):
            yt=LEVELS[0]*(1-(i+1)/3)
            box(key,name+"_tread",R(1.0+i*.3,.65,1.0+(i+1)*.3,1.65),max(yt-.03,0.0),yt+(0.0 if yt>0 else .03),"grating",False)
        for o in [.6,1.7]:
            B(1.0,o,LEVELS[0]+1.0,1.9,o,1.0)
            B(1.9,o,0.0,1.9,o,1.0,.035,.035)
        # маршрут проверки: от земли до крыши по всем площадкам
        pts=[[P(2.6,1.15)[0],0.0,P(2.6,1.15)[1]],[P(1.0,1.15)[0],LEVELS[0],P(1.0,1.15)[1]],
             [P(0.0,.6)[0],LEVELS[0],P(0.0,.6)[1]]]
        for k,y in enumerate(levels[:-1]):
            yy=levels[k+1]; ym=(y+yy)/2
            pts+=[[P(-1.0,.6)[0],y,P(-1.0,.6)[1]],[P(a_far,.6)[0],ym,P(a_far,.6)[1]],
                  [P(a_far-.6,1.15)[0],ym,P(a_far-.6,1.15)[1]],[P(a_far,1.7)[0],ym,P(a_far,1.7)[1]],
                  [P(-1.0,1.7)[0],yy,P(-1.0,1.7)[1]],[P(0.0,1.15)[0],yy,P(0.0,1.15)[1]]]
        pts.append([P(0.0,-1.2)[0],levels[-1],P(0.0,-1.2)[1]])
        p["routes"].append({"id":"fire_"+name,"label":f"Пожарная лестница {name}: земля → все площадки → крыша","points":pts})
        p["routes"].append({"id":"fire_"+name+"_down","label":f"Пожарная лестница {name}: крыша → земля","points":list(reversed(pts))})

    def rebar(key,hole,y,skip=""):
        """Рваный край дыры: торчащая и загнутая вниз арматура по краям (кроме края skip — у ската он сломан иначе)."""
        x0,z0,x1,z1=hole
        edges={"z0":[(x,z0,0,-1) for x in [x0+.12+i*.22 for i in range(int((x1-x0-.2)/.22)+1)]],
               "z1":[(x,z1,0,1) for x in [x0+.12+i*.22 for i in range(int((x1-x0-.2)/.22)+1)]],
               "x0":[(x0,z,-1,0) for z in [z0+.12+i*.22 for i in range(int((z1-z0-.2)/.22)+1)]],
               "x1":[(x1,z,1,0) for z in [z0+.12+i*.22 for i in range(int((z1-z0-.2)/.22)+1)]]}
        for edge,bars in edges.items():
            if edge==skip:
                continue
            for i,(x,z,nx,nz) in enumerate(bars):
                if (i*7+len(edge))%5==3:
                    continue
                reach=.18+((i*37)%11)/40
                drop=.12+((i*53)%7)/25
                # стержень торчит из среза плиты внутрь дыры и загнут вниз
                beam(key,[x+nx*.02,y-.08,z+nz*.02],[x-nx*reach,y-.08-drop,z-nz*reach],.014,.014,"rebar",False)
        # обломки бетона по краю: висят и лежат у кромки
        for i,(xa,za) in enumerate([(x0,z0),(x1,z1),(x0,z1),(x1,z0)]):
            cx,cz=xa+(.15 if xa==x0 else -.15),za+(.15 if za==z0 else -.15)
            box(key,"slab_chunk",[cx-.14,cz-.1,cx+.14,cz+.1],y-.22,y-.05,"slab",False)
            section(key)["boxes"][-1]["yaw"]=17+i*31

    def rubble(key,cx,cz,y,spread,count,seed):
        """Россыпь обломков на полу — низкие куски (не мешают ходить)."""
        for i in range(count):
            a=(seed*13+i*2.399)%6.283
            r=spread*(.35+((seed+i*7)%10)/14)
            x,z=cx+math.cos(a)*r,cz+math.sin(a)*r
            s=.08+((seed+i*5)%6)/30
            box(key,"rubble_chunk",[x-s,z-s*.8,x+s,z+s*.8],y,y+min(.16,s*.9),"rubble",False)
            section(key)["boxes"][-1]["yaw"]=(seed*41+i*67)%180

    def vertical_routes():
        """Стихийные проломы: плита скатом, куча и залезть, провал; люк на крышу с вертикальной лестницей."""
        roof_top=LEVELS[-1]+HEIGHTS[-1]+SLAB
        levels=LEVELS+[roof_top]
        for n,b_ in enumerate(BREACHES):
            f_above=b_["floor"]-1          # индекс уровня с дырой в полу
            y1=levels[f_above]
            y0=levels[f_above-1]
            key=f"Floor{f_above}"
            x0,z0,x1,z1=b_["hole"]
            cx,cz=(x0+x1)/2,(z0+z1)/2
            kind=b_["kind"]
            upper="крыша" if f_above==5 else f"{f_above+1} этаж"
            if kind=="hatch":
                # люк на крышу: стальная вертикальная лестница у края z0 (лезут со стороны +Z, крыша — за лестницей)
                section(key).setdefault("ladders",[]).append({"at":[cx,y0,z0+.23],"height":y1-y0,"yaw":0.0})
                p["routes"].append({"id":"breach_"+b_["id"],"label":f"Люк {b_['id']}: техэтаж → крыша по вертикальной лестнице",
                                    "ladder":True,"points":[[cx,y0,z1+.5],[cx,y0,z0+.75],[cx,y1,z0-.6]]})
                continue
            rebar(key,b_["hole"],y1,b_.get("hinge",""))
            rubble(key,cx,cz,y0,1.2,9,n+3)
            if kind=="drop":
                box(key,"rubble_pile",[x0+.1,z0+.1,x1-.1,z1-.1],y0,y0+1.1,"rubble")
                for i,(a,b,h) in enumerate([(.3,.2,.5),(-.4,.3,.35),(.1,-.45,.6)]):
                    box(key,"rubble_pile",[cx+a-.35,cz+b-.3,cx+a+.35,cz+b+.3],y0+1.1,y0+1.1+h*.4,"rubble",False)
                    section(key)["boxes"][-1]["yaw"]=23+i*41
                p["routes"].append({"id":"drop_"+b_["id"],"label":f"Провал {b_['id']}: {f_above+1} → {f_above} этаж (вниз)",
                                    "points":[[cx,y1,z1+.7],[cx,y0+1.1,cz],[cx+1.2,y0,cz]]})
                continue
            if kind=="slab":
                # кусок плиты обломился у края hinge и лёг низом на пол (у П1 — на кучу высотой mound)
                sgn=1 if b_["hinge"]=="z0" else -1        # куда от шарнира идёт плита (по z)
                z_h=z0 if sgn>0 else z1
                L=z1-z0
                y_f=y0+b_["mound"]
                dy=y1-(y_f+.04)
                dz=math.sqrt(max(L*L-dy*dy,.01))
                z_f=z_h+sgn*dz
                length=math.hypot(dz,dy)
                # верхняя грань — от низа (z_f, y_f+.04) к шарниру (z_h, y1); ось бруса ниже на полтолщины
                vy,vz=dz/length,sgn*dy/length
                off=SLAB/2
                w=b_["width"]
                beam(key,[cx,y_f+.04-vy*off,z_f-vz*off],[cx,y1-vy*off,z_h-vz*off],w,SLAB,"slab",True)
                # арматура из слома у шарнира: висит вниз вдоль плиты
                for i in range(6):
                    xx=cx-w/2+.1+i*(w-.2)/5
                    beam(key,[xx,y1-.1,z_h],[xx+.03,y1-.55-(i%3)*.12,z_h+sgn*.12],.014,.014,"rebar",False)
                start_z=z_f
                if b_["mound"]>0:
                    # куча под низом плиты — пологий скат обломков
                    run_m=b_["mound"]/math.tan(math.radians(27))
                    zs=z_f+sgn*run_m
                    ml=math.hypot(run_m,b_["mound"])
                    my,mz=run_m/ml,sgn*b_["mound"]/ml
                    beam(key,[cx,y0+.02-my*.15,zs-mz*.15],[cx,y_f+.02-my*.15,z_f-mz*.15],w+.4,.3,"rubble",True)
                    rubble(key,cx,zs,y0,.9,7,n+11)
                    start_z=zs
                p["routes"].append({"id":"breach_"+b_["id"],"label":f"{b_['id']}: {f_above} этаж → {upper} по обрушенной плите",
                                    "points":([[x0-.75,y0,start_z-sgn*.35],[cx,y0+.04,start_z-sgn*.25]] if b_["mound"]>0
                                              else [[x0-.75,y0,z_f+sgn*.45],[cx,y0,z_f+sgn*.3]])+
                                             [[cx,y_f+.04,z_f],[cx,y1,z_h],[x0-.75,y1,z_h-sgn*.1]]})
                continue
            # pile: куча ступенями к краю edge; верх — на 1,6 м ниже пола сверху (подтянуться на руках)
            sgn=1 if b_["edge"]=="z1" else -1
            z_e=z1 if sgn>0 else z0
            top_h=(y1-y0)-1.6
            tiers=[(top_h/3,.9,1.0),(top_h*2/3,.8,.9),(top_h,.95,.8)]  # высота, глубина вдоль z, доля ширины
            zc=z_e-sgn*.05
            pile_pts=[]
            for i,(hh,depth,share) in enumerate(reversed(tiers)):
                za,zb=sorted([zc,zc-sgn*depth])
                half=(x1-x0)*share/2
                box(key,"rubble_pile",[cx-half,za,cx+half,zb],y0,y0+hh,"rubble")
                section(key)["boxes"][-1]["yaw"]=(-4,3,-2)[i]
                pile_pts.append([cx,y0+hh,(za+zb)/2])
                zc=zc-sgn*depth
            # сверху кучи — пара кусков плиты и кирпичи (не мешают стоять)
            box(key,"slab_chunk",[cx-.35,z_e-sgn*.6-.25,cx+.15,z_e-sgn*.6+.25],y0+top_h,y0+top_h+.06,"slab",False)
            section(key)["boxes"][-1]["yaw"]=11
            rubble(key,cx,zc,y0,.8,8,n+21)
            p["routes"].append({"id":"breach_"+b_["id"],"label":f"{b_['id']}: {f_above} этаж → {upper} по куче, наверх — на руках",
                                "climb":True,"points":[[cx,y0,zc-sgn*.6]]+list(reversed(pile_pts))+[[cx,y1,z_e+sgn*.6]]})

    def tech_floor():
        """Техэтаж — открытый зал (владелец 2026-11-02): вместо стен коридора — колонны под ригелями, поперечные балки
        по осям отсеков, короб вентиляции и трубы на подвесах, баки и венткамеры; щитовая и кладовая — выгородки из
        сетки-рабицы. Лестница к будке на крыше — в своей клетке, люк Л — вертикальная лестница."""
        f=4
        key="Floor5"
        y,h=LEVELS[f],HEIGHTS[f]
        top=y+h
        core_axes=[BAYS[3]["x1"]+.075,BAYS[4]["x1"]+.075]
        axes=[BAYS[b]["x1"]+.075 for b in range(len(BAYS)-1)]
        for side in [-1,1]:
            zc=side*(HALF+LOAD/2)
            for xx in axes:
                if side<0 and xx in core_axes:
                    continue
                box(key,"tech_column",[xx-.2,zc-.2,xx+.2,zc+.2],y,top-.45,"wall")
            spans=[(0.0,SC0-.15),(SC1+.15,LENGTH)] if side<0 else [(0.0,LENGTH)]
            for a,b in spans:
                box(key,"tech_girder",[a,zc-.2,b,zc+.2],top-.45,top,"ceiling")
        for xx in axes:
            if xx in core_axes:
                continue
            for z_a,z_b in [(-FACADE,-HALF-LOAD),(-HALF,HALF),(HALF+LOAD,FACADE)]:
                box(key,"tech_beam",[xx-.15,z_a,xx+.15,z_b],top-.35,top,"ceiling")
        # короб вентиляции вдоль зала под балками, на подвесах
        for x0,x1 in [(.6,SC0-.4),(SC1+.4,LENGTH-.6)]:
            box(key,"tech_duct",[x0,-1.05,x1,-.25],top-.9,top-.5,"duct")
            xx=x0+.5
            while xx<x1:
                for zz in [-1.0,-.3]:
                    beam(key,[xx,top-.5,zz],[xx,top,zz],.02,.02,"rail",False)
                xx+=2.4
        # трубы отопления и водопровода на подвесах вдоль зала
        for zz,r,yy in [(1.25,.06,2.4),(1.0,.045,2.25),(-1.45,.05,2.35)]:
            beam(key,[.3,y+yy,zz],[LENGTH-.3,y+yy,zz],r*2,r*2,"pipe")
            xx=1.0
            while xx<LENGTH-.5:
                beam(key,[xx,y+yy+r,zz],[xx,top,zz],.016,.016,"rail",False)
                xx+=3.0
        tanks=[(BAYS[2],-1),(BAYS[3],-1),(BAYS[6],1)]
        for bay,side in tanks:
            cx=(bay["x0"]+bay["x1"])/2
            za,zb=sorted([side*(FACADE-.6),side*(FACADE-2.4)])
            box(key,"tech_tank",[cx-.9,za,cx+.9,zb],y,y+1.45,"tank")
            beam(key,[cx,y+1.45,(za+zb)/2],[cx,top-.02,(za+zb)/2],.12,.12,"pipe")
        for bay,side in [(BAYS[5],-1),(BAYS[7],1),(BAYS[1],1)]:
            cx=(bay["x0"]+bay["x1"])/2
            za,zb=sorted([side*(FACADE-.5),side*(FACADE-1.9)])
            box(key,"tech_fan",[cx-.8,za,cx+.8,zb],y,y+1.9,"duct")

        def cage(name,rect,door_edge,door_at,label_at):
            """Выгородка из сетки-рабицы на стальных стойках, проём двери 1 м."""
            x0,z0,x1,z1=rect
            for edge,(a0,a1,const,axis) in {"z0":(x0,x1,z0,"z"),"z1":(x0,x1,z1,"z"),"x0":(z0,z1,x0,"x"),"x1":(z0,z1,x1,"x")}.items():
                holes=[(door_at,1.0,0,2.1)] if edge==door_edge else []
                wall(key,"cage_mesh",a0,a1,const,.03,y,2.5,holes,axis,"mesh")
                pos=a0
                while pos<=a1+.01:
                    at=[pos,const] if axis=="z" else [const,pos]
                    beam(key,[at[0],y,at[1]],[at[0],y+2.55,at[1]],.05,.05,"steel_stair",False)
                    pos+=1.5
                ends=[[a0,const],[a1,const]] if axis=="z" else [[const,a0],[const,a1]]
                beam(key,[ends[0][0],y+2.52,ends[0][1]],[ends[1][0],y+2.52,ends[1][1]],.04,.04,"steel_stair",False)
            label(key,name,label_at,0,None,True)
        cage("ЭЛЕКТРОЩИТОВАЯ",[34.1,-8.6,37.6,-4.2],"z1",35.0,[35.0,y+2.3,-4.15])
        box(key,"switchboard",[34.3,-8.5,37.3,-8.1],y,y+2.0,"panel")
        cage("КЛАДОВАЯ",[38.15,-8.6,40.6,-4.2],"z1",39.4,[39.4,y+2.3,-4.15])
        for i,(a,b) in enumerate([(38.35,-8.4),(39.3,-8.4),(38.35,-7.4)]):
            box(key,"crate",[a,b,a+.8,b+.8],y,y+.6,"wood")
    def add_details():
        # Все новые категории отделены от несущей коробки. На этапе 2 их заменят модули Blender.
        def strip(key,name,lo,hi,constant,depth,y0,y1,axis,mat,group):
            rect=[lo,constant-depth/2,hi,constant+depth/2] if axis=="z" else [constant-depth/2,lo,constant+depth/2,hi]
            box(key,name,rect,y0,y1,mat,True,group)

        def skirt(key,lo,hi,constant,inward,y,axis="z",holes=()):
            cursor=lo
            for center,width in sorted(holes):
                a,b=max(lo,center-width/2),min(hi,center+width/2)
                if b<=lo or a>=hi:
                    continue
                if a>cursor:
                    strip(key,"skirting",cursor,a,constant+inward*.01,.02,y+.003,y+.08,axis,"skirting","baseboards")
                cursor=max(cursor,b)
            if cursor<hi:
                strip(key,"skirting",cursor,hi,constant+inward*.01,.02,y+.003,y+.08,axis,"skirting","baseboards")

        # Шаг следует существующим межкомнатным стенам. У лестницы и гостиной порталы стоят ближе.
        stations=[(BAYS[1]["x1"]+BAYS[2]["x0"])/2,
                  (BAYS[2]["x1"]+BAYS[3]["x0"])/2,
                  (BAYS[3]["x1"]+SC0)/2,
                  (SC1+BAYS[5]["x0"])/2,
                  (BAYS[5]["x1"]+BAYS[6]["x0"])/2,
                  (BAYS[6]["x1"]+BAYS[7]["x0"])/2]
        for f,(y,h) in enumerate(zip(LEVELS,HEIGHTS)):
            key=f"Floor{f+1}"
            if f==4:
                continue   # техэтаж — зал без коридора (tech_floor)
            for i,xx in enumerate(stations):
                uid=f"f{f+1}_portal_{i}"
                box(key,uid,[xx-.2,-HALF-LOAD,xx+.2,HALF+LOAD],y+h-.4,y+h,"ceiling",True,"beams")
                for side in [-1,1]:
                    za,zb=sorted([side*HALF,side*(HALF-.18)])
                    box(key,uid+"_pilaster",[xx-.225,za,xx+.225,zb],y,y+h-.4,"wall",True,"pilasters")
                    skirt(key,xx-.225,xx+.225,side*(HALF-.18),-side,y)
                p["portals"].append({"id":uid,"floor":f+1,"at":[xx,y,0],"ceiling":h,
                                     "clear_height":h-.4,"clear_width":HALF*2-.4,"kind":"transverse"})
            # Перемычки широких проёмов уже лежат в группе beams, внутри стены коридора.
            for name,along,side,width in [("stair",SCX,-1,2.4),
                                         ("lounge",(SC0+BAYS[5]["x1"])/2,1,BAYS[5]["x1"]-SC0-.24)]:
                p["portals"].append({"id":f"f{f+1}_{name}_lintel","floor":f+1,
                                     "at":[along,y,side*(HALF+LOAD/2)],"clear_height":h-.4,
                                     "clear_width":width,"kind":"side_opening"})
            # Перегородка стоит между дверями комнат: распахнутые створки не заслоняют соседний вход.
            wall(key,"service_partition",-HALF,HALF,36.7,PART,y,h,[(0,2.4,0,2.7)],"x",group="portals")
            door(key,"ХОЗКРЫЛО",0,36.7,y,-1,w=2.4,dh=2.7,axis="x",opened=True,thick=PART,inward=1)
            p["portals"].append({"id":f"f{f+1}_service_door","floor":f+1,"at":[36.7,y,0],
                                 "clear_height":2.7,"clear_width":2.4,"kind":"double_door"})
            for side in [-1,1]:
                openings=[]
                for item in p["doors"]:
                    if abs(item["at"][1]-y)<.01 and item["axis"]=="z" and abs(item["at"][2]-side*(HALF+LOAD/2))<.01:
                        openings.append((item["at"][0],item["width"]+.02))
                if side>0:
                    openings.append(((SC0+BAYS[5]["x1"])/2,BAYS[5]["x1"]-SC0-.24))
                openings += [(xx,.45) for xx in stations]
                skirt(key,0,LENGTH,side*HALF,-side,y,holes=openings)
            for xx,kind in [(12.6,"fire"),(26.0,"electric"),(39.8,"fire")]:
                # В стене настоящий карман 0,25 м, за ним остаётся 0,13 м несущей стены.
                uid=f"f{f+1}_{kind}_{xx}"
                box(key,uid+"_back",[xx-.3,-ROOM_EDGE,xx+.3,-HALF-.25],y+.9,y+1.8,"wall",True,"wall_niches")
                for dx in [-.3,.3]:
                    box(key,uid+"_side",[xx+dx-.018,-HALF-.25,xx+dx+.018,-HALF+.015],y+.9,y+1.8,"frame",True,"wall_niches")
                for yy in [.9,1.8]:
                    box(key,uid+"_edge",[xx-.32,-HALF-.25,xx+.32,-HALF+.015],y+yy-.018,y+yy+.018,"frame",True,"wall_niches")
                box(key,uid+"_cabinet",[xx-.26,-HALF-.23,xx+.26,-HALF-.20],y+.94,y+1.76,
                    "fire_cabinet" if kind=="fire" else "panel",True,"wall_niches")
                box(key,uid+"_handle",[xx+.18,-HALF-.20,xx+.20,-HALF-.16],y+1.2,y+1.4,"rail",False,"wall_niches")
                p["niches"].append({"id":uid,"floor":f+1,"at":[xx,y+1.35,-HALF],"depth":.25,"back_wall":LOAD-.25,"kind":kind})

        # Наличники не уменьшают чистый проём. Полотно и вся фурнитура вращаются одним узлом на петле.
        for item in p["doors"]:
            if not item["leaf"]:
                continue
            key=item["section"]
            x,y,z=item["at"]
            axis=item["axis"]
            along,constant=(x,z) if axis=="z" else (z,x)
            w,dh,thick=item["width"],item["height"],item["thickness"]
            lo,hi=along-w/2,along+w/2
            uid=item["uid"]
            # обкладка на 3 мм в проёме: её грань не совпадает с откосом стены (совпавшие плоскости мерцали у входа)
            for aa in [lo-.0095,hi+.0095]:
                strip(key,uid+"_lining",aa-.0125,aa+.0125,constant,thick,y,y+dh,axis,"frame","door_frames")
            for face in [-1,1]:
                depth=constant+face*(thick/2+.0125)
                for a,b in [(lo-.08,lo),(hi,hi+.08)]:
                    strip(key,uid+"_casing",a,b,depth,.025,y,y+dh+.08,axis,"frame","door_frames")
                strip(key,uid+"_casing_top",lo,hi,depth,.025,y+dh,y+dh+.08,axis,"frame","door_frames")
            if not item["open"]:
                continue
            double=w>=2.0
            leaf_mat="door_green" if int(uid.rsplit("_",1)[1])%3==0 else "door_wood"
            for leaf_index in range(2 if double else 1):
                hand=1 if leaf_index==0 else -1
                pivot=lo+.008 if hand>0 else hi-.008
                face=constant+item["inward"]*(thick/2+.022)
                at=[pivot,y,face] if axis=="z" else [face,y,pivot]
                open_angle=item["wide_angle"] or (90.0 if double or w>1.3 else 112.0)
                angle={"wide":open_angle,"ajar":25.0,"closed":0.0}[item["pose"]]
                section(key,"door_leaves")["doors"].append({"id":uid+f"_{leaf_index}","door_uid":uid,
                    "label":item["id"],"at":at,"width":w/(2 if double else 1)-.016,"height":dh-.024,
                    "thickness":.04,"yaw_closed":(0 if axis=="z" else -90)+(180 if hand<0 else 0),
                    "swing_sign":hand*item["inward"]*(-1 if axis=="z" else 1),"angle":angle,
                    "open_angle":open_angle,"pose":item["pose"],"grille":item["grille"],
                    "front":hand*item["inward"]*(-1 if axis=="z" else 1),
                    "mat":leaf_mat})

        for i,item in enumerate(p["windows"]):
            key=item["section"]
            x,bottom,z=item["at"]
            axis=item["axis"]
            along,constant=(x,z) if axis=="z" else (z,x)
            inward=(-1 if z>0 else 1) if axis=="z" else (-1 if x>LENGTH else 1)
            inside=constant+inward*EXT/2
            w,h=item["width"],item["height"]
            uid=f"window_{i:03d}"
            # Откос от рамы в середине кладки до её внутренней грани.
            for a in [along-w/2+.009,along+w/2-.009]:
                strip(key,uid+"_reveal",a-.009,a+.009,(constant+inside)/2,EXT/2,bottom,bottom+h,axis,"reveal","window_reveals")
            strip(key,uid+"_reveal_top",along-w/2,along+w/2,(constant+inside)/2,EXT/2,bottom+h-.018,bottom+h,axis,"reveal","window_reveals")
            edge=inside+inward*.28
            # верх подоконника на 3 мм выше кладки под окном: совпавшие плоскости мерцали
            strip(key,uid+"_sill",along-w/2-.08,along+w/2+.08,(constant+edge)/2,abs(edge-constant),bottom-.04,bottom+.003,axis,"reveal","window_sills")
            base=bottom-SILL
            for rib in range(10):
                cc=along-.45+rib*.1
                strip(key,uid+"_radiator",cc-.039,cc+.039,inside+inward*.12,.1,base+.20,base+.75,axis,"radiator","radiators")
            for yy in [.27,.68]:
                strip(key,uid+"_radiator_link",along-.50,along+.50,inside+inward*.12,.06,base+yy-.025,base+yy+.025,axis,"radiator","radiators")
            section(key,"radiators")["modules"].append({"id":uid,"at":[x,base,z],"size":[1.0,.55,.1],"axis":axis,"inward":inward})
            section(key,"window_sills")["modules"].append({"id":uid,"width":w+.16,"height":bottom,"projection":.28})

        for s in p["spaces"]:
            if s["kind"] in ["watch","stairs"]:
                continue
            key=f"Floor{s['floor']}" if "_annex_" not in s["id"] else "NorthAnnex"
            y=s["y"]
            r=s["rect"]
            poly=s.get("polygon",[[r[0],r[1]],[r[2],r[1]],[r[2],r[3]],[r[0],r[3]]])
            for a,b in zip(poly,poly[1:]+poly[:1]):
                axis="z" if abs(a[1]-b[1])<.001 else "x"
                lo,hi=sorted([a[0],b[0]] if axis=="z" else [a[1],b[1]])
                const=a[1] if axis=="z" else a[0]
                direction=1 if (b[0]>a[0] if axis=="z" else b[1]<a[1]) else -1
                holes=[]
                for d in p["doors"]:
                    if abs(d["at"][1]-y)>.01 or d["axis"]!=axis:
                        continue
                    dc=d["at"][2] if axis=="z" else d["at"][0]
                    if abs(dc-const)<=d["thickness"]/2+.02:
                        holes.append((d["at"][0] if axis=="z" else d["at"][2],d["width"]+.02))
                if s["id"].endswith("_lounge") and abs(const-ROOM_EDGE)<.01 and axis=="z":
                    holes.append(((SC0+BAYS[5]["x1"])/2,BAYS[5]["x1"]-SC0-.24))
                skirt(key,lo,hi,const,direction,y,axis,holes)
        # Хозкрыло: порталы по стенам между службами, через два модуля (8,6 м).
        annex_stations=[-FACADE-EXT-.2-4.15-.075,-FACADE-EXT-.2-4.15-.075-8.6]
        for f,(y,h) in enumerate(zip(LEVELS,HEIGHTS)):
            if f==4:
                continue
            for i,zz in enumerate(annex_stations):
                uid=f"f{f+1}_annex_portal_{i}"
                box("NorthAnnex",uid,[ANNEX_CORRIDOR-LOAD,zz-.2,LENGTH+EXT,zz+.2],y+h-.4,y+h,"ceiling",True,"beams")
                for xx,inward in [(ANNEX_CORRIDOR,1),(LENGTH,-1)]:
                    a,b=sorted([xx,xx+inward*.18])
                    box("NorthAnnex",uid+"_pilaster",[a,zz-.225,b,zz+.225],y,y+h-.4,"wall",True,"pilasters")
                    skirt("NorthAnnex",zz-.225,zz+.225,xx+inward*.18,inward,y,"x")
                p["portals"].append({"id":uid,"floor":f+1,"at":[TURN_X,y,zz],"ceiling":h,
                                     "clear_height":h-.4,"clear_width":3.0,"kind":"transverse","travel_axis":"z"})
        for y in LEVELS[:4]:
            for x,inward in [(ANNEX_CORRIDOR,1),(LENGTH,-1)]:
                holes=[(d["at"][2],d["width"]+.02) for d in p["doors"] if d["axis"]=="x" and abs(d["at"][1]-y)<.01 and abs(d["at"][0]-x)<LOAD/2+.02]
                holes += [(zz,.45) for zz in annex_stations]
                skirt("NorthAnnex",ANNEX_END,-FACADE-EXT,x,inward,y,"x",holes)

    tech_floor()
    fire_escape("А",(-EXT,0.0),(-1.0,0.0),(0.0,-1.0))
    fire_escape("Б",(TURN_X,ANNEX_END-EXT),(0.0,-1.0),(-1.0,0.0))
    # Двор и оба входа. Въездов, транспорта и новых игровых механик здесь нет.
    box("Site","ground",[-14,-49,LENGTH+15,26],-.3,0,"ground")
    box("Site","main_plinth",[-EXT,-FACADE-EXT,LENGTH+EXT,FACADE+EXT],0,BASE-SLAB,"slab")
    box("Site","front_apron",[-1,FACADE+EXT,LENGTH+1,FACADE+EXT+1.2],-.04,.025,"paving")
    # Крыльца — крупная разбитая плитка (владелец 2026-11-02: «не ламинат»), кромки ступеней — стальной уголок.
    box("Site","entry_porch",[-.35,FACADE+EXT,4.25,PORCH_END],0,BASE,"porch_tile")
    for i in range(3):
        box("Site","entry_step",[-.1,PORCH_END+i*.3,4,PORCH_END+(i+1)*.3],0,BASE-i*.16,"porch_tile")
        z=PORCH_END+i*.3
        box("Site","step_nosing",[-.1,z-.004,4,z+.036],BASE-i*.16-.036,BASE-i*.16+.004,"rail",False)
    box("Site","step_nosing",[-.35,PORCH_END-.004,4.25,PORCH_END+.036],BASE-.036,BASE+.004,"rail",False)
    # Козырёк входа (владелец 2026-11-02): железобетонная плита на двух кирпичных столбах по углам крыльца,
    # отлив по краю, лампа под плитой; перила из трубы вдоль ступеней.
    cy=BASE+3.05
    box("Site","canopy_slab",[-.75,FACADE+EXT,4.65,PORCH_END+.45],cy,cy+.18,"slab")
    box("Site","canopy_edge",[-.75,PORCH_END+.37,4.65,PORCH_END+.45],cy-.1,cy,"slab")
    for xa in [-.35,3.87]:
        box("Site","canopy_pillar",[xa,PORCH_END-.38,xa+.38,PORCH_END],BASE,cy,"brick")
    box("Site","canopy_lamp",[1.8,FACADE+EXT+1.1,2.1,FACADE+EXT+1.4],cy-.1,cy,"frame",False)
    for xr in [.12,3.78]:
        beam("Site",[xr,BASE+.9,PORCH_END],[xr,.9,PORCH_END+.9],.045,.045,"rail")
        beam("Site",[xr,0,PORCH_END+.9],[xr,.92,PORCH_END+.9],.04,.04,"rail")
    box("Site","rear_porch",[LENGTH+EXT,-1.7,LENGTH+2.2,1.7],0,BASE,"porch_tile")
    for i in range(3):
        box("Site","rear_step",[LENGTH+2.2+i*.3,-1.5,LENGTH+2.5+i*.3,1.5],0,BASE-i*.16,"porch_tile")
        x=LENGTH+2.2+i*.3
        box("Site","step_nosing",[x-.004,-1.5,x+.036,1.5],BASE-i*.16-.036,BASE-i*.16+.004,"rail",False)
    for x,z in [(-6,-13),(LENGTH-7,17)]:
        box("Site","tree_trunk",[x-.18,z-.18,x+.18,z+.18],0,5,"tree")
        box("Site","tree_crown",[x-1.6,z-1.6,x+1.6,z+1.6],3.1,8,"tree",False)
    box("Site","lamp",[7.9,16.9,8.1,17.1],0,5.5,"rail")
    box("Site","lamp_head",[7.6,16.6,8.4,17.4],5.4,5.55,"frame",False)

    for f,(y,h) in enumerate(zip(LEVELS,HEIGHTS)):
        key = f"Floor{f+1}"
        # Проём центральной лестницы вырезан из перекрытий, а не закрыт невидимой плоскостью.
        holes=[b_["hole"] for b_ in BREACHES if b_["floor"]==f+1]
        for rect in [[0,-FACADE,SC0,FACADE],[SC1,-FACADE,LENGTH,FACADE],[SC0,-ROOM_EDGE,SC1,FACADE]]:
            for piece_rect in subtract(rect,holes):
                box(key,"floor",piece_rect,y-SLAB,y,"floor")
        if f==0:
            box(key,"stair_ground",[SC0,-FACADE,SC1,-ROOM_EDGE],y-SLAB,y,"floor")
        corridor_holes = {-1:[],1:[]}
        for b,bay in enumerate(BAYS):
            x0,x1,w = bay["x0"],bay["x1"],bay["width"]
            cx = (x0+x1)/2
            for side in [-1,1]:
                if side==-1 and b==4:
                    corridor_holes[side].append((SCX,2.4,0,h-.4))
                    door(key,"ЛЕСТНИЦА",SCX,-HALF-LOAD/2,y,-1,w=2.4,dh=h-.4,opened=True,leaf=False)
                    continue
                # Примыкание крыла: наружная стена становится внутренней, окон между комнатами нет.
                if side==-1 and b>=7:
                    holes = [(TURN_X,2.4,0,DOOR_H)] if b==8 else []
                    offset=SLAB if f==0 else 0
                    wall(key,"annex_junction",x0,x1,-FACADE-EXT/2,EXT,y-offset,h+SLAB+offset,[(a,w,s+offset,dh) for a,w,s,dh in holes])
                else:
                    entrance = f==0 and side==1 and b==0
                    offset=SLAB if f==0 else 0
                    wh = [(cx,2.4,offset,2.7)] if entrance else [(cx,WINDOW_W,SILL+offset,1.65)]
                    wall(key,"facade",x0,x1,side*(FACADE+EXT/2),EXT,y-offset,h+SLAB+offset,wh)
                    if entrance:
                        door(key,"ВХОД",cx,side*(FACADE+EXT/2),y,1,w=2.4,dh=2.7,thick=EXT,inward=-1)
                    else:
                        window(key,cx,side*(FACADE+EXT/2),y+SILL,f+1)
                if f==4:
                    continue   # техэтаж — открытый зал (tech_floor): без комнат, дверей и перегородок
                if side==1 and b in [4,5]:
                    if b==4:
                        a,big = BAYS[4]["x0"]+.12,BAYS[5]["x1"]-.12
                        corridor_holes[side].append(((a+big)/2,big-a,0,h-.4))
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
                # 5-й этаж — технический: вместо жилых комнат — венткамеры, баки, кладовые за сеткой
                if f==4 and kind in ["room","toilets","laundry"]:
                    kind,name = "tech",{"laundry":"ВЕНТКАМЕРА"}.get(kind,"ТЕХ. ПОМ.")
                dx = cx if kind in ["hall","turn"] else x0+1.1
                if kind=="turn":
                    dx=TURN_X
                dw = 2.4 if kind in ["hall","turn"] else DOOR_W
                dh = 2.7 if kind=="hall" else DOOR_H
                corridor_holes[side].append((dx,dw,0,dh))
                room_state=STATES[(b+f+(1 if side>0 else 0))%len(STATES)] if kind=="room" else ""
                pose=("wide","ajar","closed")[(b+f+(1 if side>0 else 0))%3] if kind=="room" else "wide"
                door(key,name,dx,side*(HALF+LOAD/2),y,side,w=dw,dh=dh,opened=True,
                     leaf=kind!="turn",pose=pose,grille="баррикада" in room_state,wide_angle=112.0 if kind=="hall" else None)
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
                    s["state"]="пролом" if s["id"] in BREACH_ROOMS else room_state
                    s["probe_points"]=[[cx,y,side*(FACADE-.95)],[cx,y,side*5.9],
                                       [x0+.8,y,side*(ROOM_EDGE+1.0)],[x1-.8,y,side*(ROOM_EDGE+1.0)]]
                    if s["id"] not in BREACH_ROOMS:
                        bunks(key,rect,y)
                if kind=="tech":
                    s["probe_points"]=[[cx,y,side*(ROOM_EDGE+1.0)],[x0+.7,y,side*(FACADE-.9)]]
                if s["id"] in BREACH_ROOMS:
                    # дыра, скат или стремянка — посередине или у стены x1; путь и точки осмотра — вдоль стены x0
                    s["path"][-1]=[x0+.7,y,side*5.7]
                    s["probe_points"]=[[x0+.6,y,side*(ROOM_EDGE+1.0)],[x0+.6,y,side*(FACADE-.7)]]
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
                    # техэтаж: остаются только стены лестничной клетки
                    if f==4 and not (side<0 and b in [3,4]):
                        continue
                    za,zb=sorted([side*ROOM_EDGE,side*FACADE])
                    if (f+1,side,b) in WALL_BREACHES:
                        # пролом в перегородке: рваный проём у середины комнат, по краям — сколы, внизу — обломки
                        zc=side*(ROOM_EDGE+wall_breach_v((x1+next_x)/2,side,y))
                        hz0,hz1=zc-WALL_BREACH_W/2,zc+WALL_BREACH_W/2
                        box(key,"partition",[x1,za,next_x,hz0],y,y+h+SLAB)
                        box(key,"partition",[x1,hz1,next_x,zb],y,y+h+SLAB)
                        box(key,"partition",[x1,hz0,next_x,hz1],y+WALL_BREACH_H,y+h+SLAB)
                        for dz,w_,top_ in [(.18,.32,.2),(.62,.22,.1),(1.0,.26,.16)]:
                            box(key,"partition",[x1,hz0+dz-w_/2,next_x,hz0+dz+w_/2],y+WALL_BREACH_H-top_,y+WALL_BREACH_H)
                        for z_,lo,hi in [(hz0,.35,1.15),(hz1,.6,1.5)]:
                            sgn_=1 if z_==hz0 else -1
                            box(key,"partition",[x1,z_ if sgn_>0 else z_-.12,next_x,z_+.12 if sgn_>0 else z_],y+lo,y+hi)
                        xm=(x1+next_x)/2
                        rubble(key,xm-.55,zc,y,.5,6,b*7+f)
                        rubble(key,xm+.55,zc,y,.5,6,b*11+f)
                        p.setdefault("wall_breaches",[]).append({"floor":f+1,"x":xm,"z":zc,"width":WALL_BREACH_W,"height":WALL_BREACH_H})
                        p["routes"].append({"id":f"wall_f{f+1}_{side}_{b}","label":f"{f+1} этаж: пролом в стене между комнатами (отсеки {b} и {b+1})",
                                            "points":[[x1-.9,y,zc],[next_x+.9,y,zc]]})
                    else:
                        box(key,"partition",[x1,za,next_x,zb],y,y+h+SLAB)
        for side in [-1,1]:
            if f==4:
                # техэтаж: от несущей стены коридора — только перед лестничной клеткой (с её проёмом)
                if side<0:
                    wall(key,"corridor_load",SC0-.15,SC1+.15,side*(HALF+LOAD/2),LOAD,y,h+SLAB,[(SCX,2.4,0,h-.4)],portal_centers=[SCX])
                continue
            niches=[(xx,.6,.9,.9) for xx in [12.6,26.0,39.8]] if side<0 else []
            centers=[SCX] if side<0 else [(BAYS[4]["x0"]+.12+BAYS[5]["x1"]-.12)/2]
            wall(key,"corridor_load",0,LENGTH,side*(HALF+LOAD/2),LOAD,y,h+SLAB,corridor_holes[side]+niches,portal_centers=centers)
        # Торцы корпуса: чёрный выход только на первом, выше — дневное окно в конце коридора.
        offset=SLAB if f==0 else 0
        # Пожарный выход к наружной лестнице А — в торце коридора на каждом этаже.
        wall(key,"west_end",-FACADE,FACADE,-EXT/2,EXT,y-offset,h+SLAB+offset,[(0,DOOR_W,offset,DOOR_H)],axis="x")
        door(key,"ПОЖАРНЫЙ ВЫХОД",0,-EXT/2,y,-1,axis="x",thick=EXT,leaf=False)
        east_holes=[(0,1.8,offset,DOOR_H)] if f==0 else [(0,1.8,SILL+offset,1.65)]
        wall(key,"east_end",-FACADE,FACADE,LENGTH+EXT/2,EXT,y-offset,h+SLAB+offset,east_holes,axis="x")
        if f==0:
            door(key,"ЧЁРНЫЙ ВЫХОД",0,LENGTH+EXT/2,y,w=1.8,axis="x",thick=EXT,inward=1)
        else:
            window(key,LENGTH+EXT/2,0,y+SILL,f+1,"x",1.8)
        # Общая зона напротив лестницы: окно в широком объёме и неглубокая боковая ниша.
        a,b,c=BAYS[4]["x0"],BAYS[5]["x0"],BAYS[5]["x1"]
        if f<4:
            poly=[[a,ROOM_EDGE],[c,ROOM_EDGE],[c,FACADE],[b,FACADE],[b,5.6],[a,5.6]]
            space(f"f{f+1}_lounge","ГОСТИНАЯ","lounge",f,[a,ROOM_EDGE,c,FACADE],
                  [[SCX,y,0],[SCX,y,3.8],[b+1.4,y,3.8],[b+1.4,y,7.1]],
                  [[c-1.4,y,FACADE-1.0],[b+1.4,y,FACADE-1.0],[b+1.4,y,3.8],[a+1.0,y,3.8]],poly)
            wall(key,"lounge_store",a,SC1,5.675,PART,y,h,[(SCX,DOOR_W,0,DOOR_H)])
            door(key,"КЛАДОВАЯ",SCX,5.675,y,1,opened=True,thick=PART)
            # Кладовка ограничена только шириной своего модуля.
            box(key,"lounge_store_side",[SC1,5.6,b,FACADE],y,y+h+SLAB)
            space(f"f{f+1}_lounge_store","КЛАДОВАЯ ПРИ ГОСТИНОЙ","storage",f,[a,5.75,SC1,FACADE],
                  [[SCX,y,0],[SCX,y,3.8],[SCX,y,7.4]],[[SCX,y,FACADE-.8]])
            for xx in [b+.7,c-.7]:
                box(key,"seat_scale",[xx-.25,FACADE-3.78,xx+.25,FACADE-1.98],y,y+.45,"wood")
            box(key,"lounge_table",[b+2.0,FACADE-4.48,c-2.0,FACADE-3.58],y,y+.55,"wood")
        else:
            space("f5_tech_hall","ТЕХНИЧЕСКИЙ ЭТАЖ","tech",f,[0,-FACADE,LENGTH,FACADE],
                  [[SCX,y,0],[SCX+3,y,0],[12,y,0],[12,y,5.5]],
                  [[3,y,-5.5],[16,y,-3.6],[16,y,0],[30,y,0],[30,y,-5.0],[30,y,0],[35.85,y,0],[35.85,y,5.5],[40,y,5.5],[24,y,6.0]])
        # Входной контроль оставлен открытым; новые игровые правила турникета не вводятся.
        if f==0:
            wall(key,"vestibule",0,WIDTHS[0],7.075,PART,y,h,[(ENTRY_X,2.4,0,2.7)])
            door(key,"ТАМБУР",ENTRY_X,7.075,y,1,w=2.4,dh=2.7,thick=PART,inward=-1)
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
        # Вместо рёбер 0,15 м — настоящие пары пилястр и балки (см. add_details ниже).
        if f<3:
            for xx in [2.5,11,SCX,31,LENGTH-2]:
                section(key)["lights"].append({"at":[xx,y+h-.25,0],"energy":.72,"range":7.3})
            for s in p["spaces"]:
                if s["floor"]==f+1 and s["open"]:
                    r=s["rect"]
                    section(key)["lights"].append({"at":[(r[0]+r[2])/2,y+h-.25,(r[1]+r[3])/2],"energy":.35,"range":6.5})
        if True:
            p["floor_routes"].append({"floor":f+1,"start":[SCX,y,0],"end":[LENGTH-.8,y,0]})
            p["circulation"].extend([{"floor":f+1,"rect":[0,-HALF,LENGTH,HALF]},
                                      {"floor":f+1,"rect":[ANNEX_CORRIDOR,ANNEX_END,LENGTH,-FACADE]}])

    # Лестница внутри корпуса: по 1,5 м от стены до центрального промежутка, без боковых щелей.
    key="CentralStair"
    holes=[]
    for f,y in enumerate(LEVELS):
        if f<4:
            ym=(y+LEVELS[f+1])/2
            holes.append((ym+SILL,1.65))
        else:
            holes.append((y+SILL,1.65))
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
    roof_top=LEVELS[-1]+HEIGHTS[-1]+SLAB
    for f,y in enumerate(LEVELS):
        box(key,"stair_front_landing",[SC0,SZ,SC1,-ROOM_EDGE],y-SLAB,y,"floor")
        # с 5-го этажа марши ведут в будку выхода на крышу
        yy=LEVELS[f+1] if f<4 else roof_top
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
        if f<4:
            pts=[[SCX,y,0],[SCX,y,-ROOM_EDGE-.65],[left,y,SZ+.45],[left,y,SZ],
                 [left,ym,zm-.6],[right,ym,zm-.6],[right,ym,zm],
                 [right,yy,SZ],[right,yy,SZ+.45],[SCX,yy,-ROOM_EDGE-.65],[SCX,yy,0]]
            p["routes"].extend([{"id":f"up{f+1}","label":f"Лестница {f+1} → {f+2}","points":pts},
                                {"id":f"down{f+1}","label":f"Лестница {f+2} → {f+1}","points":list(reversed(pts))}])
        if f==4:
            pts=[[SCX,y,0],[SCX,y,-ROOM_EDGE-.65],[left,y,SZ+.45],[left,y,SZ],
                 [left,ym,zm-.6],[right,ym,zm-.6],[right,ym,zm],[right,yy,SZ],[right,yy,SZ+.45],[SCX,yy,-ROOM_EDGE+.9]]
            p["routes"].extend([{"id":"up_roof","label":"Лестница 5 → будка → крыша","points":pts},
                                {"id":"down_roof","label":"Крыша → будка → 5 этаж","points":list(reversed(pts))}])
        space(f"f{f+1}_stairs","ЦЕНТРАЛЬНАЯ ЛЕСТНИЦА","stairs",f,[SC0,SZ,SC1,-ROOM_EDGE],
              [[SCX,y,0],[SCX,y,-ROOM_EDGE-.65]],[[SC0+.75,y,SZ+.55],[SC1-.75,y,SZ+.55]])
        if f<3:
            section(key)["lights"].append({"at":[SCX,y+2.4,SZ-.8],"energy":.7,"range":7})
    # Будка выхода на крышу над лестничной клеткой: стены, плита, дверь к середине крыши.
    box(key,"stair_front_landing",[SC0,SZ,SC1,-ROOM_EDGE],roof_top-SLAB,roof_top,"floor")
    hut_top=roof_top+2.9
    box(key,"hut_wall",[SC0-.25,-FACADE-EXT,SC0,-ROOM_EDGE+.25],roof_top,hut_top)
    box(key,"hut_wall",[SC1,-FACADE-EXT,SC1+.25,-ROOM_EDGE+.25],roof_top,hut_top)
    box(key,"hut_wall",[SC0,-FACADE-EXT,SC1,-FACADE],roof_top,hut_top)
    wall(key,"hut_wall",SC0,SC1,-ROOM_EDGE+.125,.25,roof_top,hut_top-roof_top,[(SCX,DOOR_W,0,DOOR_H)])
    door(key,"ВЫХОД НА КРЫШУ",SCX,-ROOM_EDGE+.125,roof_top,1,thick=.25,inward=1)
    box(key,"hut_roof",[SC0-.35,-FACADE-EXT-.1,SC1+.35,-ROOM_EDGE+.35],hut_top,hut_top+.2,"slab")

    # Хозяйственный отворот буквой Г. Остаток за решёткой виден, но не доступен.
    key="NorthAnnex"
    service_kinds=[("kitchen","КУХНЯ"),("wash","УМЫВАЛЬНЯ"),("showers","ДУШЕВЫЕ"),("toilets","ТУАЛЕТЫ")]
    for f,(y,h) in enumerate(zip(LEVELS,HEIGHTS)):
        box(key,"annex_floor",[ANNEX_X,ANNEX_END,LENGTH,-FACADE-EXT],y-SLAB,y,"floor")
        wh,dh=[],[]
        for i,(kind,name) in enumerate(service_kinds):
            sid=f"f{f+1}_annex_{kind}"
            if f==4:
                # техэтаж: хозкрыло — часть открытого зала, окна прежние
                zc=-FACADE-EXT-.2-i*4.3-4.15/2
                wh.append((zc,WINDOW_W,SILL,1.65))
                window(key,ANNEX_X-EXT/2,zc,y+SILL,f+1,"x")
                continue
            z1=-FACADE-EXT-.2-i*4.3
            z0=z1-4.15
            zc=(z0+z1)/2
            wh.append((zc,WINDOW_W,SILL,1.65))
            dh.append((zc,DOOR_W,0,DOOR_H))
            box(key,"service_partition",[ANNEX_X,z0-PART,ANNEX_CORRIDOR-LOAD,z0],y,y+h+SLAB)
            if i==0:
                box(key,"service_partition",[ANNEX_X,z1,ANNEX_CORRIDOR-LOAD,z1+PART],y,y+h+SLAB)
            window(key,ANNEX_X-EXT/2,zc,y+SILL,f+1,"x")
            door(key,name,zc,ANNEX_WALL,y,axis="x",opened=True,inward=-1)
            rect=[ANNEX_X,z0,ANNEX_CORRIDOR-LOAD,z1]
            cc=(rect[0]+rect[2])/2
            space(sid,name,kind,f,rect,
                  [[TURN_X,y,0],[TURN_X,y,-6],[TURN_X,y,zc],[cc,y,zc]],
                  [[ANNEX_X+.8,y,z0+.8],[cc,y,z1-.8]])
            if kind in ["wash","showers","toilets"]:
                bathroom(key,rect,f,zc,"x")
            if f<3:
                section(key)["lights"].append({"at":[cc,y+h-.25,zc],"energy":.45,"range":5.5})
        # Конец хозкрыла за службами — склад (прежде закрытая часть): дверь из коридора, два окна.
        store_z1=-FACADE-EXT-.2-3*4.3-4.15-PART
        store_zc=(ANNEX_END+store_z1)/2
        for zz in [store_zc+2.9,store_zc-2.9]:
            wh.append((zz,WINDOW_W,SILL,1.65))
            window(key,ANNEX_X-EXT/2,zz,y+SILL,f+1,"x")
        if f<4:
            dh.append((store_zc,DOOR_W,0,DOOR_H))
            door(key,"СКЛАД",store_zc,ANNEX_WALL,y,axis="x",opened=True,inward=-1)
            srect=[ANNEX_X,ANNEX_END,ANNEX_CORRIDOR-LOAD,store_z1]
            space(f"f{f+1}_annex_store","СКЛАД","storage",f,srect,
                  [[TURN_X,y,0],[TURN_X,y,-6],[TURN_X,y,store_zc],[(srect[0]+srect[2])/2,y,store_zc]],
                  [[ANNEX_X+.9,y,ANNEX_END+.9],[(srect[0]+srect[2])/2,y,store_z1-.9]])
        else:
            space("f5_annex_hall","ТЕХНИЧЕСКИЙ ЭТАЖ · ХОЗКРЫЛО","tech",f,[ANNEX_X,ANNEX_END,LENGTH,-FACADE-EXT],
                  [[TURN_X,y,0],[TURN_X,y,-6],[TURN_X,y,-20],[36,y,-20]],[[36,y,-12],[36,y,-31]])
            # вместо стены коридора — колонны под ригелем
            for zz in [-12.5,-17.0,-21.5,-26.0,-30.5,-35.0]:
                box(key,"tech_column",[ANNEX_WALL-.2,zz-.2,ANNEX_WALL+.2,zz+.2],y,y+h-.45,"wall")
            box(key,"tech_girder",[ANNEX_WALL-.2,ANNEX_END,ANNEX_WALL+.2,-FACADE-EXT],y+h-.45,y+h,"ceiling")
        wall(key,"annex_facade",ANNEX_END,-FACADE-EXT,ANNEX_X-EXT/2,EXT,y,h+SLAB,wh,"x")
        wall(key,"annex_east",ANNEX_END,-FACADE-EXT,LENGTH+EXT/2,EXT,y,h+SLAB,axis="x")
        if f<4:
            wall(key,"annex_corridor",ANNEX_END,-FACADE-EXT,ANNEX_WALL,LOAD,y,h+SLAB,dh,"x")
        # пожарный выход к наружной лестнице Б — в торце коридора хозкрыла на каждом этаже
        wall(key,"annex_end",ANNEX_X,LENGTH,ANNEX_END-EXT/2,EXT,y,h+SLAB,[(TURN_X,DOOR_W,0,DOOR_H)])
        door(key,"ПОЖАРНЫЙ ВЫХОД",TURN_X,ANNEX_END-EXT/2,y,-1,thick=EXT,leaf=False)
        if f<3:
            for z in [-13,-21,-27.5]:
                section(key)["lights"].append({"at":[TURN_X,y+h-.25,z],"energy":.65,"range":6.5})
        if True:
            p["routes"].append({"id":f"turn_f{f+1}","label":f"{f+1} этаж: лестница → гостиная → поворот Г → торец хозкрыла",
                                "points":[[SCX,y,0],[SCX,y,3.8],[BAYS[5]["x0"]+2,y,3.8],
                                          [SCX,y,3.8],[SCX,y,0],[TURN_X,y,0],[TURN_X,y,-6],[TURN_X,y,ANNEX_END+.6]]})
    roof=LEVELS[-1]+HEIGHTS[-1]
    roof_holes=[[SC0,-FACADE,SC1,-ROOM_EDGE]]+[b_["hole"] for b_ in BREACHES if b_["floor"]==6]
    for rect in subtract([0,-FACADE,LENGTH,FACADE],roof_holes):
        box("Roof","roof",rect,roof,roof+SLAB,"slab")
    box("Roof","annex_roof",[ANNEX_X,ANNEX_END,LENGTH,-FACADE-EXT],roof,roof+SLAB,"slab")
    # Парапет 0,4 м по всему краю кровли, проёмы — у выходов пожарных лестниц (запад у оси коридора, торец хозкрыла).
    top=roof+SLAB
    par=lambda rect: box("Roof","parapet",rect,top,top+.4,"wall")
    par([-EXT,FACADE+EXT/2-.15,LENGTH+EXT,FACADE+EXT/2+.15])
    par([-EXT,-FACADE-EXT/2-.15,ANNEX_X-EXT,-FACADE-EXT/2+.15])
    par([-EXT/2-.15,-FACADE-EXT,-EXT/2+.15,-.75])
    par([-EXT/2-.15,.75,-EXT/2+.15,FACADE+EXT])
    par([LENGTH+EXT/2-.15,ANNEX_END-EXT,LENGTH+EXT/2+.15,FACADE+EXT])
    par([ANNEX_X-EXT/2-.15,ANNEX_END-EXT,ANNEX_X-EXT/2+.15,-FACADE-EXT])
    par([ANNEX_X-EXT,ANNEX_END-EXT/2-.15,TURN_X-.75,ANNEX_END-EXT/2+.15])
    par([TURN_X+.75,ANNEX_END-EXT/2-.15,LENGTH+EXT,ANNEX_END-EXT/2+.15])
    # Откинутая крышка люка Л рядом с проёмом.
    lx0,lz0,lx1,lz1=next(b_["hole"] for b_ in BREACHES if b_["id"]=="Л")
    box("Roof","hatch_lid",[lx1+.05,lz0,lx1+.11,lz1],top,top+.9,"steel_stair")
    for x in [lx0-.06,lx1]:
        box("Roof","hatch_curb",[x,lz0-.06,x+.06,lz1+.06],top,top+.12,"steel_stair")
    vertical_routes()
    p["routes"].append({"id":"entry_to_back","label":"Вход → турникет → коридор → чёрный выход",
                        "points":[[ENTRY_X,0,17],[ENTRY_X,0,14.4],[ENTRY_X,BASE,12.0],[ENTRY_X,BASE,8.4],
                                  [LANE_X,BASE,6.5],[LANE_X,BASE,5.4],[LANE_X,BASE,4.5],[ENTRY_X,BASE,3.1],
                                  [ENTRY_X,BASE,0],[SCX,BASE,0],[LENGTH-1,BASE,0],[LENGTH+1.3,BASE,0],
                                  [LENGTH+3.8,0,0],[LENGTH+5,0,4]]})
    p["routes"].append({"id":"back_to_entry","label":"Чёрный выход → турникет → главный вход",
                        "points":list(reversed(p["routes"][-1]["points"]))})
    add_details()
    # Камеры редакции 3 сохранены без изменений; FOV по умолчанию остаётся 80°.
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
        ("15_fire_a","Пожарная лестница А у торца",[-4.5,0,4.5],[-1.5,8.0,-2.0]),
        ("16_roof","Крыша: будка и люк",[10.0,LEVELS[-1]+HEIGHTS[-1]+SLAB,3.0],[SCX,LEVELS[-1]+HEIGHTS[-1]+SLAB+1.5,-4.0]),
        ("17_tech","Техэтаж: короб и трубы",[ENTRY_X+2,LEVELS[4],0],[LENGTH-1,LEVELS[4]+1.62,0]),
        ("18_breach","Пролом П1: плита скатом",[8.8,BASE,8.3],[10.635,BASE+2.2,4.0]),
        ("19_canopy","Вход: козырёк и крыльцо",[1.95,0,15.5],[1.95,1.8,10.5]),
    ]
    for i,(sid,name,foot,look) in enumerate(views,1):
        p["locations"].append({"id":i,"label":name,"foot":foot,"look":look})
        p["shots"].append({"id":sid,"label":name,"foot":foot,"look":look,"eye_height":1.62})
    from dorm_lighting_data import add_lighting
    add_lighting(p)
    return rounded(p)


def scene_text(plan):
    text='''[gd_scene load_steps=7 format=3]

[ext_resource type="Script" path="res://src/blockout/dorm_geometry.gd" id="1"]
[ext_resource type="Script" path="res://src/blockout/dorm_lighting.gd" id="2"]
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
    text+='\n[node name="Lighting" type="Node3D" parent="."]\nscript = ExtResource("2")\n'
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
