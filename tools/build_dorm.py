# -*- coding: utf-8 -*-
"""Общежитие: только этап 1, серый план отдельного стенда.

python -X utf8 tools/build_dorm.py
  -> data/blockouts/dorm.json, scenes/levels/dorm_study.tscn,
     docs/plans/dorm.png (схема, не снимок сверху с крышей).
Масштаб E; задание — docs/tasks/dorm_vertical_slice.md.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WK, HK = 1.3, 1.15
ROOM_W, ROOM_D, PART = 3.9, 7.8, 0.15
BAY = ROOM_W + PART
HALF, LOAD, EXT, SLAB = 1.65, 0.38, 0.64, 0.24
ROOM_EDGE = HALF + LOAD
FACADE_IN = ROOM_EDGE + ROOM_D
WING, LENGTH = 8 * BAY, 8 * BAY + PART
ANNEX_X, ANNEX_END = 6 * BAY, -40.0
ANNEX_CORRIDOR = LENGTH - HALF * 2
ANNEX_WALL = ANNEX_CORRIDOR - LOAD / 2
TURN_X = (ANNEX_CORRIDOR + LENGTH) / 2
BASE = 0.48
HEIGHTS = [4.2, 3.2, 3.2, 3.2, 3.2]
LEVELS = [BASE]
for h in HEIGHTS[:-1]:
    LEVELS.append(round(LEVELS[-1] + h + SLAB, 4))
DOOR_W, DOOR_H = 1.17, 2.415
STATES = ["жилая", "разграбленная", "сгоревшая", "баррикада у окна", "пустая с матрасами"]


def rounded(value):
    if isinstance(value, float):
        return round(value, 4)
    if isinstance(value, list):
        return [rounded(v) for v in value]
    if isinstance(value, dict):
        return {k: rounded(v) for k, v in value.items()}
    return value


def make_plan() -> dict:
    p = {
        "version": 1, "stage": 1, "greybox": True,
        "purpose": "Общежитие: серый план для оценки владельцем, отдельный стенд",
        "north": "-Z", "bounds": [-16, -47, 47, 24],
        "scale": {"width_k": WK, "height_k": HK, "room_clear": [ROOM_W, ROOM_D],
                  "corridor_clear": HALF * 2, "ceiling_clear": HEIGHTS,
                  "floor_y": LEVELS, "door_clear": [DOOR_W, DOOR_H],
                  "entrance_clear": [2.4, 2.7], "walls": {"facade": EXT, "load": LOAD, "partition": PART},
                  "stair_width": 1.5, "tread": 0.3, "eye": 1.62, "fov_h": 80.0},
        "reference": {"typology": "Кирпичное общежитие с продольными несущими стенами и общими службами",
                      "passport": "https://files.stroyinf.ru/Data2/2/4294852/4294852709.pdf",
                      "project": "164-87-119пв, КиевЗНИИЭП, 1976; конструктивный ориентир, план свой",
                      "owner_images": "референсы/dorm/01.png … 20.png; только референсы, не игровые текстуры"},
        "sections": {}, "spaces": [], "doors": [], "windows": [], "stairs": [],
        "barriers": [], "locations": [], "shots": [], "routes": [], "floor_routes": [],
        "outline": [[-0.64,-10.47],[ANNEX_X-EXT,-10.47],[ANNEX_X-EXT,ANNEX_END-EXT],
                    [LENGTH+EXT,ANNEX_END-EXT],[LENGTH+EXT,-3.99],[LENGTH+8.79,-3.99],
                    [LENGTH+8.79,3.99],[LENGTH+EXT,3.99],[LENGTH+EXT,10.47],[-0.64,10.47],
                    [-0.64,3.99],[-8.79,3.99],[-8.79,-3.99],[-0.64,-3.99]],
    }

    def section(key):
        return p["sections"].setdefault(key, {"boxes": [], "beams": [], "stairs": [], "labels": [], "lights": []})

    def box(key, name, rect, y0, y1, mat="wall", solid=True, yaw=0):
        x0, z0, x1, z1 = rect
        if x1 - x0 < 0.001 or z1 - z0 < 0.001 or y1 - y0 < 0.001:
            return
        section(key)["boxes"].append({"id": name, "at": [(x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2],
                                      "size": [x1 - x0, y1 - y0, z1 - z0], "mat": mat,
                                      "solid": solid, "yaw": yaw})

    def beam(key, start, end, width=0.07, depth=0.07, mat="rail", solid=True):
        section(key)["beams"].append({"start": start, "end": end, "width": width, "depth": depth, "mat": mat, "solid": solid})

    def label(key, text, at, yaw=0):
        section(key)["labels"].append({"text": text, "at": at, "yaw": yaw})

    def wall_z(key, name, x0, x1, z, thickness, y, h, holes):
        """Горизонтальная на плане стена; проёмы действительно вырезаны из коллизии."""
        cursor = x0
        for center, width, sill, height in sorted(holes):
            a, b = center - width / 2, center + width / 2
            box(key, name, [cursor, z - thickness / 2, a, z + thickness / 2], y, y + h)
            box(key, name + "_sill", [a, z - thickness / 2, b, z + thickness / 2], y, y + sill)
            box(key, name + "_head", [a, z - thickness / 2, b, z + thickness / 2], y + sill + height, y + h)
            cursor = b
        box(key, name, [cursor, z - thickness / 2, x1, z + thickness / 2], y, y + h)

    def wall_x(key, name, z0, z1, x, thickness, y, h, holes):
        cursor = z0
        for center, width, sill, height in sorted(holes):
            a, b = center-width/2, center+width/2
            box(key,name,[x-thickness/2,cursor,x+thickness/2,a],y,y+h)
            box(key,name+"_sill",[x-thickness/2,a,x+thickness/2,b],y,y+sill)
            box(key,name+"_head",[x-thickness/2,a,x+thickness/2,b],y+sill+height,y+h)
            cursor = b
        box(key,name,[x-thickness/2,cursor,x+thickness/2,z1],y,y+h)

    def door(key, name, x, z, y, side, width=DOOR_W, height=DOOR_H, opened=True):
        p["doors"].append({"id": name, "at": [x, y, z], "width": width, "height": height, "open": opened})
        # Пока только габарит рамы: сама деревянная дверь появится после приёмки модулей.
        for dx in [-width / 2 - 0.035, width / 2 + 0.035]:
            box(key, name + "_jamb", [x + dx - 0.035, z - 0.22, x + dx + 0.035, z + 0.22], y, y + height, "frame")
        box(key, name + "_lintel", [x - width / 2 - 0.07, z - 0.22, x + width / 2 + 0.07, z + 0.22], y + height, y + height + 0.07, "frame")
        if not opened:
            box(key, name + "_sealed", [x - width / 2, z - 0.06, x + width / 2, z + 0.06], y, y + height, "sealed")
        label(key, name, [x, y + height + 0.2, z - side * 0.25], 180 if side > 0 else 0)

    def space(key, sid, name, kind, floor, rect, path, state="", accessible=True):
        s = {"id": sid, "label": name, "kind": kind, "floor": floor + 1, "y": LEVELS[floor],
             "rect": rect, "open": accessible, "state": state, "path": path}
        p["spaces"].append(s)
        return s

    # Минимальный двор: отмостка, крыльцо и земля, без чужих моделей.
    box("Site", "ground", [-20, -50, 52, 30], -0.35, 0, "ground")
    box("Site", "apron", [-0.64, -FACADE_IN - 1.55, LENGTH + 0.64, FACADE_IN + 1.55], -0.06, 0.025, "paving")
    box("Site", "plinth", [-EXT,-FACADE_IN-EXT,LENGTH+EXT,FACADE_IN+EXT],0,BASE-SLAB,"slab")
    box("Site", "porch", [-0.25, FACADE_IN + EXT, 4.45, 13.15], 0, BASE, "floor")
    for i in range(3):
        box("Site", "porch_step", [0, 13.15 + 0.3 * i, 4.2, 13.15 + 0.3 * (i + 1)], 0, BASE - 0.16 * i, "floor")
    # При обходе крыльца можно прочитать его высоту; верх не ограждает дверной проём.
    for x in [-0.2, 4.4]:
        beam("Site", [x, BASE + 1.05, FACADE_IN + EXT], [x, BASE + 1.05, 13.1], 0.06, 0.06)
    for x, z in [(-10.5, -12.5), (34, 17.5)]:
        box("Site", "tree_trunk", [x - 0.2, z - 0.2, x + 0.2, z + 0.2], 0, 5.4, "tree")
        box("Site", "tree_crown", [x - 1.7, z - 1.7, x + 1.7, z + 1.7], 3.4, 8.4, "tree", False)
    box("Site", "lamp", [9.9, 15.9, 10.1, 16.1], 0, 5.5, "rail")
    box("Site", "lamp_head", [9.5, 15.5, 10.5, 16.5], 5.4, 5.55, "frame", False)

    for f, (y, h) in enumerate(zip(LEVELS, HEIGHTS)):
        key = f"Floor{f + 1}"
        # Торцы плит скрыты внутри кладки: совпадающие наружные грани давали рябь на фасаде.
        box(key, "floor", [0, -FACADE_IN, LENGTH, FACADE_IN], y - SLAB, y, "floor")
        # Перекрытие следующего этажа одновременно служит потолком этого.
        for side in [-1, 1]:
            facade_holes = []
            for b in range(8):
                x = b * BAY + PART + ROOM_W / 2
                entrance = f == 0 and b == 0 and side == 1
                if side == -1 and b >= 6:
                    if b == 7:
                        facade_holes.append((TURN_X, 2.4, 0, 2.7))
                    continue
                width, sill, height = (2.4, 0, 2.7) if entrance else (1.85, 0.95, 1.65)
                facade_holes.append((x, width, sill, height))
                if entrance:
                    door(key, "ВХОД", x, side * (FACADE_IN + EXT / 2), y, side, 2.4, 2.7)
                else:
                    z = side * (FACADE_IN + EXT / 2)
                    p["windows"].append({"at": [x, y + sill, z], "width": width, "height": height, "floor": f + 1})
                    # Световой проём открыт; тонкая коллизия стекла предотвращает обход через окна.
                    box(key, "window_glass", [x - width / 2, z - 0.025, x + width / 2, z + 0.025], y + sill, y + sill + height, "glass")
                    for dx in [-width / 2 + 0.035, 0, width / 2 - 0.035]:
                        box(key, "window_mullion", [x + dx - 0.035, z - 0.06, x + dx + 0.035, z + 0.06], y + sill, y + sill + height, "frame")
                    box(key, "window_sill", [x - width / 2, z - 0.20, x + width / 2, z + 0.20], y + sill - 0.06, y + sill, "frame")
            if f==0:
                box(key,"facade_base",[-EXT,side*(FACADE_IN+EXT/2)-EXT/2,LENGTH+EXT,side*(FACADE_IN+EXT/2)+EXT/2],y-SLAB,y,"wall")
            wall_z(key, "facade", -EXT, LENGTH + EXT, side * (FACADE_IN + EXT / 2), EXT, y, h + SLAB, facade_holes)
            corridor_holes = []
            for b in range(8):
                x0, x1 = b * BAY + PART, (b + 1) * BAY
                x = x0 + 1.10
                hall = f == 0 and b == 0 and side == 1
                lounge = side == 1 and b in [2,3,4]
                if hall:
                    x = (x0 + x1) / 2
                if side == -1 and b == 7:
                    x = TURN_X
                width, dh = (2.4, 2.7) if hall else (DOOR_W, DOOR_H)
                if side == -1 and b == 7:
                    width, dh = 2.4, 2.7
                if lounge:
                    if b == 2:
                        corridor_holes.append((12.225, 7.2, 0, 2.9))
                    elif b == 4:
                        corridor_holes.append((18.3, 2.8, 0, 2.9))
                    continue
                corridor_holes.append((x, width, 0, dh))
                opened = f < 3
                if b < 8:
                    if f == 0 and b == 0:
                        kind = "hall" if side == 1 else "guard"
                        name = "ХОЛЛ" if side == 1 else "ВАХТА"
                    elif side == -1 and b == 6:
                        kind, name = "laundry", "ПОСТИРОЧНАЯ"
                    elif side == -1 and b == 7:
                        kind, name = "turn", "К ХОЗБЛОКУ"
                    elif side == 1 and b == 0 and f > 0:
                        kind, name = "storage", "БЕЛЬЕВАЯ"
                    else:
                        kind = "room"
                        number = (f + 1) * 100 + b * 2 + (1 if side == -1 else 2)
                        name = str(number)
                    sid = f"f{f+1}_{kind}_{b}_{side}"
                    z0, z1 = sorted([side * ROOM_EDGE, side * FACADE_IN])
                    rect = [x0, z0, x1, z1]
                    path = [[x, y, 0], [x, y, side * 3.05], [(x0 + x1) / 2, y, side * 6.3]]
                    if kind == "hall":
                        rect = [x0, ROOM_EDGE, x1, 6.50]
                        path[-1][2] = 4.4
                    state = STATES[(b + f + (1 if side > 0 else 0)) % len(STATES)] if kind == "room" else ""
                    space(key, sid, name, kind, f, rect, path, state, opened)
                    door(key, name, x, side * (HALF + LOAD / 2), y, side, width, dh, opened)
                else:
                    door(key, "ЗАВАРЕНО", x, side * (HALF + LOAD / 2), y, side, width, dh, False)
            wall_z(key, "corridor_load", 0, LENGTH, side * (HALF + LOAD / 2), LOAD, y, h + SLAB, corridor_holes)
            for b in range(9):
                x = b * BAY
                z0, z1 = sorted([side * ROOM_EDGE, side * FACADE_IN])
                if side == 1 and b == 3:
                    continue
                if side == 1 and b == 4:
                    z0 = 5.6
                box(key, "room_partition", [x, z0, x + PART, z1], y, y + h + SLAB)
        # Общее пространство разрывает ряд комнат; боковая ниша делает план Г-образным и внутри.
        lounge = space(key, f"f{f+1}_lounge", "ОБЩАЯ ГОСТИНАЯ", "lounge", f,
                       [8.25,ROOM_EDGE,20.25,FACADE_IN],
                       [[10,y,0],[10,y,3.6],[10,y,8.95],[15.6,y,8.95],[15.6,y,4],[18.5,y,4]], accessible=f<3)
        lounge["polygon"] = [[8.25,ROOM_EDGE],[20.25,ROOM_EDGE],[20.25,5.6],[16.2,5.6],[16.2,FACADE_IN],[8.25,FACADE_IN]]
        lounge["probe_points"] = [[9.8,y,3],[9.8,y,8.95],[15.6,y,8.95],[15.6,y,4],[19.2,y,4]]
        wall_z(key, "lounge_store", 16.35,20.25,5.675,PART,y,h,[(18.3,DOOR_W,0,DOOR_H)])
        door(key,"КЛАДОВАЯ",18.3,5.675,y,1,opened=f<3)
        space(key,f"f{f+1}_lounge_store","КЛАДОВАЯ","storage",f,[16.35,5.75,20.25,FACADE_IN],
              [[18.3,y,0],[18.3,y,4],[18.3,y,7.6]],accessible=f<3)
        # Нейтральные габариты мест для сидения, чтобы масштаб общей зоны можно было оценить сейчас.
        for bx in [9.0,14.7]:
            box(key,"seat_scale",[bx-0.25,6.7,bx+0.25,8.5],y,y+0.45,"frame")
        if f == 0:
            cx = PART + ROOM_W / 2
            wall_z(key, "vestibule", PART, BAY, 6.575, PART, y, h, [(cx, 2.4, 0, 2.7)])
            door(key, "ТАМБУР", cx, 6.575, y, 1, 2.4, 2.7)
            space(key, "f1_vestibule", "ТАМБУР", "vestibule", f, [PART, 6.65, BAY, FACADE_IN],
                  [[cx, y, 4.4], [cx, y, 8.4]])
        # Редкие поперечные рёбра читают высоту, не занижая весь потолок.
        for x in [8.1, 16.2, 24.3, 32.0]:
            box(key, "corridor_beam", [x - 0.16, -HALF, x + 0.16, HALF], y + h - 0.22, y + h, "slab")
        # Белый технический свет для оценки плана. Чистовой свет — отдельный этап 5.
        if f < 3:
            for x in [3, 11.8, 20.5, 30]:
                section(key)["lights"].append({"at": [x, y + h - 0.3, 0], "energy": 0.65, "range": 7.0})
            for s in p["spaces"]:
                if s["floor"] == f + 1 and s["open"]:
                    r = s["rect"]
                    section(key)["lights"].append({"at": [(r[0]+r[2])/2, y+h-0.3, (r[1]+r[3])/2], "energy": 0.25, "range": 6.0})

    # Поворот корпуса буквой Г: в поперечном крыле нет жилых комнат.
    # Кухня и мокрые службы — с окнами на запад; по восточной стороне идёт коридор.
    for f,(y,h) in enumerate(zip(LEVELS,HEIGHTS)):
        key = "NorthAnnex"
        box(key,"annex_floor",[ANNEX_X,ANNEX_END,LENGTH,-FACADE_IN-EXT],y-SLAB,y,"floor")
        west_holes, door_holes = [], []
        for i,(kind,name) in enumerate([("kitchen","КУХНЯ"),("wash","УМЫВАЛЬНЯ"),("showers","ДУШЕВЫЕ"),("toilets","ТУАЛЕТЫ")]):
            z1 = -10.65-i*4.3
            z0 = z1-4.15
            zc = (z0+z1)/2
            west_holes.append((zc,1.85,0.95,1.65))
            door_holes.append((zc,DOOR_W,0,DOOR_H))
            box(key,"service_partition",[ANNEX_X,z0-PART,ANNEX_WALL-LOAD/2,z0],y,y+h+SLAB)
            if i==0:
                box(key,"service_partition",[ANNEX_X,z1,ANNEX_WALL-LOAD/2,z1+PART],y,y+h+SLAB)
            box(key,"service_window",[ANNEX_X-EXT/2-0.025,zc-0.925,ANNEX_X-EXT/2+0.025,zc+0.925],y+0.95,y+2.6,"glass")
            box(key,"service_window_frame",[ANNEX_X-EXT/2-0.07,zc-0.035,ANNEX_X-EXT/2+0.07,zc+0.035],y+0.95,y+2.6,"frame")
            if f>=3:
                box(key,"service_sealed",[ANNEX_WALL-0.06,zc-DOOR_W/2,ANNEX_WALL+0.06,zc+DOOR_W/2],y,y+DOOR_H,"sealed")
            label(key,name,[ANNEX_CORRIDOR+0.04,y+2.62,zc],90)
            if f<3:
                service = space(key,f"f{f+1}_{kind}_annex",name,kind,f,[ANNEX_X,z0,ANNEX_WALL-LOAD/2,z1],
                                [[TURN_X,y,0],[TURN_X,y,-6.0],[TURN_X,y,zc],[27.9,y,zc],[26.5,y,zc]])
                service["probe_points"] = [[ANNEX_X+0.8,y,z0+0.8],[ANNEX_WALL-LOAD/2-0.8,y,z1-0.8]]
                section(key)["lights"].append({"at":[26.5,y+h-0.3,zc],"energy":0.35,"range":5})
        for zc in [-32.3,-36.6]:
            west_holes.append((zc,1.85,0.95,1.65))
            door_holes.append((zc,DOOR_W,0,DOOR_H))
            box(key,"annex_closed_door",[ANNEX_WALL-0.06,zc-DOOR_W/2,ANNEX_WALL+0.06,zc+DOOR_W/2],y,y+DOOR_H,"sealed")
            box(key,"closed_window",[ANNEX_X-EXT/2-0.025,zc-0.925,ANNEX_X-EXT/2+0.025,zc+0.925],y+0.95,y+2.6,"glass")
        wall_x(key,"annex_facade",ANNEX_END-EXT,-FACADE_IN-EXT,ANNEX_X-EXT/2,EXT,y,h+SLAB,west_holes)
        wall_x(key,"annex_east",ANNEX_END-EXT,-FACADE_IN-EXT,LENGTH+EXT/2,EXT,y,h+SLAB,[])
        wall_x(key,"annex_corridor",ANNEX_END,-FACADE_IN-EXT,ANNEX_WALL,LOAD,y,h+SLAB,door_holes)
        wall_z(key,"annex_end",ANNEX_X,LENGTH,ANNEX_END-EXT/2,EXT,y,h+SLAB,[])
        if f<3:
            for zc in [-12.5,-21,-27]:
                section(key)["lights"].append({"at":[TURN_X,y+h-0.3,zc],"energy":0.6,"range":6.5})
            gate_z = -28.4
            box(key,"annex_gate_base",[ANNEX_CORRIDOR,gate_z-0.12,LENGTH,gate_z+0.12],y,y+1.35,"sealed")
            for x in [ANNEX_CORRIDOR+0.08+0.18*i for i in range(18)]:
                box(key,"annex_gate_bar",[x-0.025,gate_z-0.06,x+0.025,gate_z+0.06],y+1.35,y+h,"rail")
            for i in range(4):
                box(key,"rubble",[ANNEX_CORRIDOR+0.1+i*0.1,gate_z-2-i*0.4,LENGTH-0.1,gate_z-1-i*0.4],y,y+0.6+i*0.3,"slab",True,i*13)
            p["barriers"].append({"id":f"wing_f{f+1}","label":f"Закрытая часть хозкрыла, {f+1} этаж","floor":f+1,
                                  "from":[TURN_X,y,-27.3],"to":[TURN_X,y,-30.0],"axis":"z_min","stop":gate_z+0.12})
            p["routes"].append({"id":f"annex_f{f+1}","label":f"{f+1} этаж: комнаты → гостиная → поворот Г → хозкрыло",
                               "points":[[2,y,0],[10,y,0],[10,y,4],[18.5,y,4],[18.5,y,0],[TURN_X,y,0],[TURN_X,y,-6],[TURN_X,y,-12],[TURN_X,y,-27.3]]})
    box("Roof","annex_roof",[ANNEX_X,ANNEX_END,LENGTH,-FACADE_IN-EXT],LEVELS[-1]+HEIGHTS[-1],LEVELS[-1]+HEIGHTS[-1]+SLAB,"slab")
    box("Site","annex_apron",[ANNEX_X-EXT-1.2,ANNEX_END-EXT-1.2,LENGTH+EXT+1.2,-FACADE_IN-EXT],-0.06,0.025,"paving")

    # Торцы с настоящими дверными проёмами и выступающими лестничными клетками.
    def end_stair(key, xoff, mirror):
        def tx(x):
            return xoff + mirror * x

        def end_box(name, xa, xb, za, zb, ya, yb, mat="wall", solid=True):
            a, b = sorted([tx(xa), tx(xb)])
            box(key, name, [a, za, b, zb], ya, yb, mat, solid)

        for f, (y, h) in enumerate(zip(LEVELS, HEIGHTS)):
            # Стена торца здания, проход в лестницу — посередине.
            for za, zb in [(-FACADE_IN, -1.2), (1.2, FACADE_IN)]:
                end_box("end_wall", -LOAD, 0, za, zb, y, y+h+SLAB)
            end_box("stair_door_head", -LOAD, 0, -1.2, 1.2, y + 2.7, y+h+SLAB)
            if mirror < 0 or f >= 3:
                end_box("stair_sealed_door", -0.23, -0.12, -1.2, 1.2, y, y+2.7, "sealed")
            for za, zb in [(-3.35-EXT, -3.35), (3.35, 3.35+EXT)]:
                end_box("stair_side", -8.15-EXT, -LOAD, za, zb, y, y+h+SLAB)
            # Большое торцевое окно освещает межэтажную площадку.
            end_box("stair_window_left", -8.15-EXT, -8.15, -3.35, -1.25, y, y+h+SLAB)
            end_box("stair_window_right", -8.15-EXT, -8.15, 1.25, 3.35, y, y+h+SLAB)
            end_box("stair_window_sill", -8.15-EXT, -8.15, -1.25, 1.25, y, y+0.95)
            end_box("stair_window_head", -8.15-EXT, -8.15, -1.25, 1.25, y+2.7, y+h+SLAB)
            end_box("stair_glass", -8.48, -8.43, -1.25, 1.25, y+0.95, y+2.7, "glass")
            end_box("stair_window_frame", -8.5, -8.4, -0.035, 0.035, y+0.95, y+2.7, "frame")
            end_box("landing", -2.03, -LOAD, -3.35, 3.35, y-SLAB, y, "floor")
            # Ограждение края основной площадки не пересекает подходы к маршам.
            for za, zb in [(-3.35, -1.68), (1.68, 3.35)]:
                end_box("landing_guard", -2.1, -2.03, za, zb, y, y+1.1, "rail")
            if f == 0:
                end_box("stair_ground", -8.15, -LOAD, -3.35, 3.35, y-SLAB, y, "floor")
                end_box("stair_plinth",-8.79,-LOAD,-3.99,3.99,0,y-SLAB,"slab")
                for za,zb in [(-3.99,-3.35),(3.35,3.99)]:
                    end_box("stair_base_side",-8.79,-LOAD,za,zb,y-SLAB,y,"wall")
                end_box("stair_base_end",-8.79,-8.15,-3.35,3.35,y-SLAB,y,"wall")
            if mirror<0 and f<3:
                p["barriers"].append({"id":f"east_stair_f{f+1}","label":f"Заваренная восточная лестница, {f+1} этаж","floor":f+1,
                                      "from":[LENGTH-0.9,y,0],"to":[LENGTH+0.7,y,0],"axis":"x_max","stop":LENGTH+0.12})
            if f < 4:
                rise = LEVELS[f+1] - y
                count = 14 if f == 0 else 11
                run = count * 0.3
                xe, xm, ym = -2.03, -2.03-run, y + rise/2
                end_box("half_landing", xm-1.6, xm, -1.68, 1.68, ym-SLAB, ym, "floor")
                flights = [([tx(xe), y, -0.915], [tx(xm), ym, -0.915]),
                           ([tx(xm), ym, 0.915], [tx(xe), LEVELS[f+1], 0.915])]
                for start, end in flights:
                    stair = {"start": start, "end": end, "width": 1.5, "count": count, "mat": "slab", "floor": f+1}
                    section(key)["stairs"].append(stair)
                    p["stairs"].append({**stair, "side": "west" if mirror > 0 else "east", "riser": rise/(2*count), "tread": 0.3})
                    # Простые безопасные перила, без моделирования стоек и поручня этапа 2.
                    zedge = -0.14 if start[2] < 0 else 0.14
                    a, b = [start[0], start[1]+1.1, zedge], [end[0], end[1]+1.1, zedge]
                    beam(key, a, b, 0.07, 0.10)
                    for k in [0.05, 0.35, 0.65, 0.95]:
                        xx, yy = start[0]+(end[0]-start[0])*k, start[1]+(end[1]-start[1])*k
                        beam(key, [xx, yy, zedge], [xx, yy+1.1, zedge], 0.05, 0.05)
                if mirror > 0 and f < 2:
                    pts = [[-0.9,y,0], [xe+0.55,y,-0.915], [xe,y,-0.915], [xm-0.1,ym,-0.915],
                           [xm-0.9,ym,-0.915], [xm-0.9,ym,0.915], [xm-0.1,ym,0.915],
                           [xe,LEVELS[f+1],0.915], [xe+0.55,LEVELS[f+1],0.915], [-0.9,LEVELS[f+1],0]]
                    p["routes"].append({"id": f"up_{f+1}_{f+2}", "label": f"Лестница {f+1} → {f+2}", "points": pts})
                    p["routes"].append({"id": f"down_{f+2}_{f+1}", "label": f"Лестница {f+2} → {f+1}", "points": list(reversed(pts))})
                if mirror > 0 and f == 2:
                    # Дальше есть лестница, но вход в неё перекрыт заваренной решёткой.
                    end_box("upper_gate_base", xe-0.16, xe-0.04, -3.35, -0.15, y, y+1.3, "sealed")
                    for z in [-3.3 + 0.15*i for i in range(22)]:
                        end_box("upper_gate_bar", xe-0.13, xe-0.07, z-0.02, z+0.02, y+1.3, y+3.0, "rail")
                    p["barriers"].append({"id": "upper_floors", "label": "Подъём на 4–5 этажи", "floor": 3,
                                           "from": [xe+0.6,y,-0.915], "to": [xe-1.0,y+0.5,-0.915], "axis": "x_min", "stop": xe-0.04})
            if mirror > 0 and f < 3:
                space(key, f"f{f+1}_stairs", "ЛЕСТНИЦА", "stairs", f, [-2.03,-3.35,-LOAD,3.35],
                      [[1,y,0],[-0.9,y,0]])
                section(key)["lights"].append({"at": [-4.5, y+h-0.3, 0], "energy": 0.65, "range": 7})
                label(key, f"{f+1} ЭТАЖ", [-8.1,y+1.7,2.0], -90)
        end_box("stair_roof", -8.15, -LOAD, -3.35, 3.35, LEVELS[-1]+HEIGHTS[-1], LEVELS[-1]+HEIGHTS[-1]+SLAB, "slab")

    end_stair("WestStair", 0, 1)
    end_stair("EastStair", LENGTH, -1)
    roof_y = LEVELS[-1] + HEIGHTS[-1]
    box("Roof", "roof", [0,-FACADE_IN,LENGTH,FACADE_IN], roof_y, roof_y+SLAB, "slab")
    for z in [-FACADE_IN-EXT/2, FACADE_IN+EXT/2]:
        box("Roof", "parapet", [-EXT,z-0.16,LENGTH+EXT,z+0.16], roof_y+SLAB, roof_y+SLAB+0.55, "wall")
    p["routes"].append({"id": "entrance", "label": "Улица → крыльцо → тамбур → холл → лестница",
                           "points": [[2.1,0,17], [2.1,0,14.4], [2.1,BASE,12], [2.1,BASE,8.5],
                                      [2.1,BASE,4.4], [2.1,BASE,0], [-0.9,BASE,0]]})
    for f in range(3):
        y = LEVELS[f]
        p["floor_routes"].append({"floor": f+1, "start": [-0.9,y,0], "end": [TURN_X,y,0]})

    # Те же координаты будут использованы на этапе 5; высота глаза строго 1,62 м.
    views = [
        ("01_corridor", "Коридор 2-го этажа", [1.8,LEVELS[1],0], [27,LEVELS[1]+1.62,0]),
        ("02_room", "Комната от двери", [5.3,LEVELS[1],-2.85], [6.5,LEVELS[1]+1.62,-9.6]),
        ("03_kitchen", "Кухня в хозкрыле", [28.0,LEVELS[1],-12.5], [24.4,LEVELS[1]+1.62,-13.0]),
        ("04_wash", "Умывальня в хозкрыле", [28.0,LEVELS[1],-16.8], [24.4,LEVELS[1]+1.62,-17.0]),
        ("05_stairs_bottom", "Лестница снизу", [-1.3,LEVELS[0],-1.0], [-6.8,LEVELS[0]+2.9,-0.6]),
        ("06_stairs_top", "Лестница сверху", [-1.3,LEVELS[1],1.0], [-6.4,LEVELS[0]+2.6,0.8]),
        ("07_hall", "Холл и тамбур", [2.1,LEVELS[0],5.7], [2.1,LEVELS[0]+1.62,-3.7]),
        ("08_street", "Вход с улицы", [-13,0,23], [12,7.2,0]),
        ("09_lounge", "Общая гостиная с нишей", [10.2,LEVELS[1],3.4], [17,LEVELS[1]+1.62,7.5]),
        ("10_turn", "Поворот в хозкрыло", [TURN_X,LEVELS[1],-3.8], [TURN_X,LEVELS[1]+1.62,-25]),
    ]
    for i, (sid, text, foot, toward) in enumerate(views, 1):
        p["locations"].append({"id": i, "label": text, "foot": foot, "look": toward})
        p["shots"].append({"id": sid, "label": text, "foot": foot, "look": toward, "eye_height": 1.62})
    return rounded(p)


def scene_text(plan):
    # Только собственное нейтральное освещение стенда, без настроек игровых карт.
    header = '''[gd_scene load_steps=6 format=3]

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
        header += f'\n[node name="{key}" type="Node3D" parent="."]\nscript = ExtResource("1")\nsection_id = "{key}"\n'
    return header


def main():
    plan = make_plan()
    for rel, text in [("data/blockouts/dorm.json", json.dumps(plan, ensure_ascii=False, indent=2)+"\n"),
                      ("scenes/levels/dorm_study.tscn", scene_text(plan))]:
        path = ROOT / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
    from dorm_plan import draw_plan
    draw_plan(plan, ROOT / "docs/plans/dorm.png")
    print(f"dorm: {sum(s['open'] for s in plan['spaces'])} открытых помещений; "
          f"{sum(s['open'] and s['kind']=='room' for s in plan['spaces'])} жилых комнат; 5 этажей, открыты 3")


if __name__ == "__main__":
    main()
