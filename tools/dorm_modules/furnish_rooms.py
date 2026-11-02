"""Мебель общежития в стенд: расстановка по комнатам плана (data/blockouts/dorm.json) → data/blockouts/dorm_furniture.json.

  python -X utf8 tools/dorm_modules/furnish_rooms.py

Интервью 2026-10-31: казённая мебель вперемешку с вещами жильцов, «целая, но старая». Комната — по своему виду
(space.state в плане): жилая — всё на местах и вещи жильцов (холодильник, телевизор, плитка, ковёр на стене, в широких —
диван); разграбленная — техники нет, стулья опрокинуты, матрасы сброшены, тумбочка и стол сдвинуты; сгоревшая — только
железные каркасы кроватей; баррикада у окна — шкаф, стол, кровать и матрасы стеной у окна; пустая с матрасами — матрасы
на полу. Случай — по номеру комнаты, повторяемый. Серые кровати плана (bunk_*) стенд убирает в прямоугольниках clear —
только если модели мебели на месте (без assets/models стоит серый план).

Кухни, умывальни, душевые и туалеты — мебель партии 2 (furniture2_game.py, владелец 2026-11-02): на кухне плиты, мойки
и столы-тумбы рядами у обеих длинных стен, над ними шкафчики и полки для посуды, обеденный стол у окна с табуретами,
посуда на плитах, бидон и бак у двери; в умывальне — раковины с зеркалами рядами у длинных стен; в туалетах — ряд кабинок
с унитазами и раковины; в душевых — раковины вместо серых. Подвижное — по pose (дверцы приоткрыты, ящик выдвинут,
дверца кабинки распахнута или выбита), одна раковина отбита, один унитаз без бачка, нескольких зеркал нет — по случаю.
Серые умывальники, зеркала и чаши унитазов плана стенд снимает в прямоугольниках clear.

Оси комнаты: u — поперёк от стены x0, v — от стены коридора к фасаду; модели смотрят лицом в +Z Godot (в Blender −Y),
корень — середина опоры на полу (полка и ковёр — у стены; у партии 2 навесное, раковина, унитаз и кабинка — у стены,
навесное — серединой верха). У комнат хозкрыла «коридор» — перегородка к главному корпусу, «фасад» — дальняя
перегородка, x0 — окно, x1 — стена коридора хозкрыла с дверью посередине.
"""
from __future__ import annotations

import json
import math
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / "data/blockouts/dorm.json"
INDEX = ROOT / "assets/models/dorm/furniture/furniture.json"
OUT = ROOT / "data/blockouts/dorm_furniture.json"
SOLID = {"furn_bunk_bed", "furn_bed", "furn_nightstand", "furn_wardrobe", "furn_table", "furn_chair", "furn_stool",
         "furn_fridge", "furn_sofa", "furn_stove", "furn_sink", "furn_counter", "furn_dining", "furn_wallcab",
         "furn_basin", "furn_basin_broken", "furn_toilet", "furn_toilet_torn", "furn_stall", "furn_stall_end",
         # партия 3: обысканные ящики и корпус ПК (ящики с лутом — коробкой всегда, crate())
         "it_ammo_open", "it_zip_open", "it_trunk_open", "it_toolbox_open", "it_carton_open", "it_suitcase_open",
         "it_pc", "it_pc_opened"}
SMALL = {"furn_tv", "furn_hotplate", "furn_shelf", "furn_pot", "furn_kettle", "furn_pan", "furn_can", "furn_bucket",
         "furn_mirror", "furn_dishrack"}
# конфорки плиты в осях модели Godot (x, z — build_furniture2.stove: Blender (x, y) → (x, −y)), верх конфорок
# партия 3: мелочь (книги, тетради, мышь, клавиатура, ноутбук, вырезка, тубус) не рисуется дальше 15 м, бумага на стенах,
# рамы и мониторы — дальше 30 м, остальное (ящики, корпус ПК) — 40 м
FAR3 = {**{m: 15.0 for m in ("it_book", "it_book_open", "it_book_stack", "it_book_row", "it_notebook", "it_notebook_open",
                             "it_notebook_stack", "it_notebook48", "it_mouse", "it_keyboard", "it_clip", "it_tube",
                             "it_tube_open", "it_laptop", "it_laptop_closed", "it_laptop_broken")},
        **{m: 30.0 for m in ("it_poster", "it_poster_torn", "it_poster_curl", "it_poster_s", "it_poster_s_curl",
                             "it_calendar", "it_chart", "it_chart_fallen", "it_drawing", "it_drawing_roll", "it_frame",
                             "it_frame_broken", "it_frame_fallen", "it_frame_pl", "it_monitor", "it_monitor_broken")}}
BURNERS = ((-0.11, 0.1), (0.12, 0.12), (-0.12, -0.14), (0.11, -0.12))
BURNER_TOP = 0.862
COUNTER_TOP = 0.852
GAP = 0.015
RADIATOR = 0.13  # батарея под окном (модуль radiator.glb) выступает от стены
# варианты отделки — вперемешку (у предметов, где они есть)
VARIANTS = json.loads(INDEX.read_text(encoding="utf-8"))


class Room:
    def __init__(self, s: dict):
        x0, z0, x1, z1 = s["rect"]
        self.s = s
        self.y = float(s["y"])
        self.side = 1 if z1 > 0 else -1
        self.x0, self.x1 = x0, x1
        self.zc = z0 if self.side > 0 else z1          # стена коридора
        self.W = x1 - x0
        self.D = abs(z1 - z0)
        self.door_u = s["path"][0][0] - x0
        # хозкрыло стенд строит отдельным разделом (build_dorm.py: key NorthAnnex) — по нему же снимается его серое
        self.section = "NorthAnnex" if "_annex_" in s["id"] else f"Floor{s['floor']}"
        self.rng = random.Random(s["id"])
        self.items: list[dict] = []

    def world(self, u: float, v: float, h: float = 0.0) -> list[float]:
        return [round(self.x0 + u, 4), round(self.y + h, 4), round(self.zc + self.side * v, 4)]

    def yaw_facing(self, direction: str) -> float:
        """Куда смотрит лицо: «room» (от коридора к фасаду, +v), «corridor» (−v), «+u», «−u»."""
        fv = self.side  # +v в мире — это +Z у комнат справа, −Z у комнат слева
        return {"room": 0.0 if fv > 0 else 180.0, "corridor": 180.0 if fv > 0 else 0.0,
                "+u": 90.0, "-u": -90.0}[direction]

    def add(self, model: str, u: float, v: float, facing: str, h: float = 0.0, tilt: float = 0.0, yaw_add: float = 0.0,
            variant: str | None = None, pose: dict | None = None) -> dict:
        a = VARIANTS[model]["aabb"]
        lift = 0.0
        if tilt:
            # опрокинутая вещь не уходит под пол: низ после наклона на ±90° вокруг своей X — от её глубины по Z
            zmin = a["center"][2] - a["size"][2] / 2
            zmax = a["center"][2] + a["size"][2] / 2
            lift = zmax if tilt > 0 else -zmin
        item = {"id": f"{self.s['id']}_{len(self.items)}_{model.split('_', 1)[1]}", "section": self.section, "model": model,
                "at": self.world(u, v, h + lift), "yaw": round(self.yaw_facing(facing) + yaw_add, 2)}
        if tilt:
            item["tilt"] = tilt
        if variant is None and VARIANTS[model]["variants"]:
            pool = [None] + VARIANTS[model]["variants"]
            variant = self.rng.choice(pool)
        if variant:
            item["variant"] = variant
        if pose:
            item["pose"] = pose
        # опрокинутый табурет — без коробки: лёгкий и низкий, проход им не перегораживается
        if model in SOLID and not (tilt and model == "furn_stool"):
            item["solid"] = True
        item["far"] = FAR3.get(model, 40.0 if model.startswith("it_") else 25.0 if model in SMALL else 60.0)
        self.items.append(item)
        return item

    def wall(self, model: str, wall: str, along: float, h: float = 0.0, off: float = 0.0, **kw) -> dict:
        """Вплотную к стене лицом в комнату; along — середина вдоль стены (u для стен коридора и фасада, v для боковых);
        off — отступ от стены (стол у окна — на батарею)."""
        a = VARIANTS[model]["aabb"]
        back = -(a["center"][2] - a["size"][2] / 2) + GAP + off  # от корня до задней грани
        if model.startswith("it_"):
            # партия 3: along — середина габарита (у раскрытого чемодана и сумки корень не посередине); локальная +X
            # модели у стены идёт вдоль неё в сторону dir
            along -= a["center"][0] * {"x0": -self.side, "x1": self.side, "corridor": self.side,
                                       "facade": -self.side}[wall]
        if wall == "x0":
            return self.add(model, back, along, "+u", h, **kw)
        elif wall == "x1":
            return self.add(model, self.W - back, along, "-u", h, **kw)
        elif wall == "corridor":
            return self.add(model, along, back, "room", h, **kw)
        else:  # facade
            return self.add(model, along, self.D - back, "corridor", h, **kw)

    def bed(self, model: str, wall: str, mattress: bool = True, variant: str | None = None) -> None:
        """Кровать вдоль боковой стены у окна (0,6 м от фасада, как серые в плане), изголовьем к окну; матрасы на ярусах."""
        v = self.D - 0.6 - 1.0
        # 6 см от стены: стойки кровати не задевают ковёр
        u = 0.456 + 0.06 if wall == "x0" else self.W - 0.456 - 0.06
        self.add(model, u, v, "corridor", variant=variant)
        if mattress:
            for z in ((0.355, 1.305) if model == "furn_bunk_bed" else (0.425,)):
                self.add("furn_mattress", u, v, "corridor", h=z)

    def on(self, model: str, host: dict, lx: float, lz: float, h: float, yaw_add: float = 0.0, **kw) -> dict:
        """Вещь на другой (кастрюля на конфорке, сковорода на столе-тумбе): lx, lz — точка в осях модели-основы."""
        psi = math.radians(host["yaw"])
        dx = lx * math.cos(psi) + lz * math.sin(psi)
        dz = -lx * math.sin(psi) + lz * math.cos(psi)
        u = host["at"][0] + dx - self.x0
        v = self.side * (host["at"][2] + dz - self.zc)
        return self.add(model, u, v, "room", h, yaw_add=host["yaw"] + yaw_add - self.yaw_facing("room"), **kw)

    def box(self, u0: float, u1: float, v0: float, v1: float, y1: float) -> dict:
        """Прямоугольник clear в осях комнаты (u, v, высота над полом) → мир."""
        p0, p1 = self.world(u0, v0), self.world(u1, v1, y1)
        lo = [min(p0[i], p1[i]) for i in range(3)]
        hi = [max(p0[i], p1[i]) for i in range(3)]
        lo[1] = round(self.y - 0.01, 3)
        return {"section": self.section, "min": [round(x, 3) for x in lo], "max": [round(x, 3) for x in hi]}

    def clear(self) -> list[dict]:
        """Где в плане стоят серые двухъярусные (build_dorm.bunks): по ним стенд снимает бруски и перекладины."""
        out = []
        for a, b in ((0.14, 1.04), (self.W - 1.04, self.W - 0.14)):
            za, zb = sorted([self.zc + self.side * (self.D - 0.6), self.zc + self.side * (self.D - 2.6)])
            out.append({"section": self.section, "min": [round(self.x0 + a - 0.05, 3), round(self.y - 0.01, 3), round(za - 0.05, 3)],
                        "max": [round(self.x0 + b + 0.05, 3), round(self.y + 1.9, 3), round(zb + 0.05, 3)]})
        return out


def lived(r: Room) -> None:
    rng = r.rng
    bunk_left = rng.random() < 0.5
    r.bed("furn_bunk_bed" if bunk_left else "furn_bed", "x0")
    r.bed("furn_bed" if bunk_left else "furn_bunk_bed", "x1")
    single = "x1" if bunk_left else "x0"
    # ковёр — над одноярусной: низ на 0,6 м, середина — над кроватью
    r.wall("furn_carpet", single, r.D - 1.6, h=0.6)
    # тумбочки — у изголовий, в простенке между кроватью и окном
    r.wall("furn_nightstand", "x0", r.D - 0.3)
    r.wall("furn_nightstand", "x1", r.D - 0.3)
    # полка — над диваном / у входа, дальше распахнутой двери
    r.wall("furn_shelf", "x0", 1.9, h=1.65)
    r.wall("furn_wardrobe", "x1", 0.7)
    r.wall("furn_fridge", "x1", 1.5)
    # стол — вплотную к батарее под окном (она выступает на ~12 см)
    r.wall("furn_table", "facade", r.W / 2, off=RADIATOR)
    r.add("furn_chair", r.W / 2 - 0.22, r.D - 0.95 - RADIATOR, "room", yaw_add=rng.uniform(-12, 12))
    r.add("furn_stool", r.W / 2 + 0.3, r.D - 1.0 - RADIATOR, "room", yaw_add=rng.uniform(0, 90))
    if rng.random() < 0.7:
        r.wall("furn_hotplate", "facade", r.W / 2 + 0.3, h=0.75, off=RADIATOR, yaw_add=rng.uniform(-10, 10))
    # телевизор — на тумбочке у одноярусной
    a = VARIANTS["furn_nightstand"]["aabb"]
    r.wall("furn_tv", single, r.D - 0.3, h=a["size"][1], yaw_add=rng.uniform(-8, 8))
    if r.W >= 5.0:
        r.wall("furn_sofa", "x0", 2.65)


def looted(r: Room) -> None:
    rng = r.rng
    r.bed("furn_bunk_bed", "x0", mattress=False)
    r.bed("furn_bed", "x1", mattress=rng.random() < 0.5)
    # матрасы сброшены на пол, тумбочка выдвинута и развёрнута, стул опрокинут, стол сдвинут
    # сброшенные матрасы — врозь (второй — ближе к коридору и в стороне), не друг в друге
    for k in range(rng.randint(1, 2)):
        r.add("furn_mattress", r.W / 2 + (0.55 if k else -0.35) + rng.uniform(-0.15, 0.15), r.D - 2.5 - k * 1.6, "room",
              yaw_add=rng.uniform(-25, 25) + (90 if k else 0))
    r.add("furn_nightstand", 1.2 + rng.uniform(0, 0.4), r.D - 2.9, "room", yaw_add=rng.uniform(30, 150))
    r.wall("furn_wardrobe", "x1", 0.7)
    r.add("furn_table", r.W / 2 + rng.uniform(-0.3, 0.3), r.D - 0.75, "corridor" if r.side > 0 else "room",
          yaw_add=rng.uniform(-25, 25))
    r.add("furn_chair", r.W / 2 + rng.uniform(-0.6, 0.6), r.D - 1.8, "room", tilt=90.0, yaw_add=rng.uniform(0, 360))
    # табурет опрокинут у входа, в стороне от двери и сброшенных матрасов
    r.add("furn_stool", rng.uniform(2.0, r.W - 0.9), rng.uniform(1.3, 1.8), "room", tilt=-90.0, yaw_add=rng.uniform(0, 360))
    if rng.random() < 0.5:
        r.wall("furn_shelf", "x0", 1.9, h=1.65)


def burned(r: Room) -> None:
    rng = r.rng
    # дерево и ткань сгорели — стоят железные каркасы, один сдвинут
    r.bed("furn_bunk_bed", "x0", mattress=False, variant="EN-DGR-SAT")
    r.add("furn_bed", r.W - 0.6, r.D - 1.7, "room", yaw_add=rng.uniform(-14, 14), variant="EN-DGR-SAT")
    if rng.random() < 0.5:
        r.add("furn_chair", rng.uniform(1.2, r.W - 1.2), rng.uniform(2.0, 3.5), "room", tilt=90.0,
              yaw_add=rng.uniform(0, 360), variant="EN-GBL-SAT")


def barricade(r: Room) -> None:
    rng = r.rng
    # у окна: шкаф на спине поперёк окна (верх — к стене x0), перед ним стол на боку, двухъярусная у стены
    r.add("furn_wardrobe", r.W / 2 + 1.05, r.D - 0.62, "+u", tilt=-90.0)
    r.add("furn_table", r.W / 2 + 0.2, r.D - 1.0, "corridor", tilt=90.0, yaw_add=rng.uniform(-8, 8))
    r.bed("furn_bunk_bed", "x0", mattress=False)
    r.add("furn_mattress", r.W - 0.7, r.D - 2.2, "room", yaw_add=rng.uniform(-20, 20))
    r.add("furn_chair", r.W / 2 - 0.5, r.D - 1.7, "room", yaw_add=rng.uniform(150, 210))
    r.wall("furn_nightstand", "x1", 0.5)


def empty(r: Room) -> None:
    rng = r.rng
    n = min(rng.randint(3, 4), int((r.W - 0.3) / 0.85))
    for k in range(n):
        u = (r.W - n * 0.85) / 2 + 0.425 + k * 0.85
        r.add("furn_mattress", u, r.D - 1.9 + rng.uniform(-0.3, 0.3), "room", yaw_add=rng.uniform(-8, 8))
    if rng.random() < 0.6:
        r.add("furn_stool", rng.uniform(1.0, r.W - 1.0), 2.0, "room", yaw_add=rng.uniform(0, 90))


def breach(r: Room) -> None:
    """Комната с проломом (docs/design/dorm_routes.md): посередине или у стены x1 — дыра в полу или скат под дырой в
    потолке, путь вдоль стены x0 свободен. Каркас кровати без матраса — у стены x1, если рядом с дырой хватает места."""
    free = r.W
    for b in r.breaches:
        x0, _, x1, _ = b["hole"]
        half = max(b.get("width", 0.0), x1 - x0) / 2
        cx = b["start"][0] if "start" in b else (x0 + x1) / 2
        free = min(free, r.x1 - (cx + half))
    if free >= 1.1:
        r.bed("furn_bed", "x1", mattress=False, variant="EN-DGR-SAT")
    if r.rng.random() < 0.6:
        r.add("furn_stool", 0.7, 1.6, "room", tilt=-90.0, yaw_add=r.rng.uniform(0, 360))


STATES = {"жилая": lived, "разграбленная": looted, "сгоревшая": burned, "баррикада у окна": barricade,
          "пустая с матрасами": empty, "пролом": breach}


# ---------------------------------------------------------------- партия 2: кухни, умывальни, туалеты


def doors_pose(rng: random.Random, model: str) -> dict | None:
    """Дверцы тумб и шкафчиков — по случаю приоткрыты (угол открывает, ось в index), ящик выдвинут."""
    pose = {}
    for node in ("дверца_лев", "дверца_прав"):
        if rng.random() < 0.3:
            pose[node] = round(rng.uniform(15, 100), 1)
    if model == "furn_counter" and rng.random() < 0.35:
        pose["ящик"] = round(rng.uniform(0.05, 0.3), 3)
    return pose or None


def kitchen_row(r: Room, wall: str, plan: list[tuple[str, float]]) -> None:
    """Ряд у стены: плиты, мойки, столы-тумбы; над столами-тумбами — шкафчики, над мойками — полки для посуды;
    на плитах — посуда, на столе-тумбе — сковорода."""
    rng = r.rng
    for model, u in plan:
        pose = doors_pose(rng, model) if model in ("furn_sink", "furn_counter") else None
        if model == "furn_stove" and rng.random() < 0.15:
            pose = {"дверца": round(rng.uniform(40, 85), 1)}
        r.wall(model, wall, u, pose=pose)
        host = r.items[-1]
        if model == "furn_counter":
            r.wall("furn_wallcab", wall, u, h=1.95, pose=doors_pose(rng, "furn_wallcab"))
            if rng.random() < 0.5:
                r.on("furn_pan", host, rng.uniform(-0.15, 0.15), rng.uniform(-0.05, 0.1), COUNTER_TOP, rng.uniform(-40, 40))
        elif model == "furn_sink":
            r.wall("furn_dishrack", wall, u, h=1.9)
        elif model == "furn_stove":
            spots = list(BURNERS)
            rng.shuffle(spots)
            if rng.random() < 0.7:
                r.on("furn_pot", host, *spots[0], BURNER_TOP, rng.uniform(0, 360))
            if rng.random() < 0.6:
                r.on("furn_kettle", host, *spots[1], BURNER_TOP, rng.uniform(0, 360))


def kitchen(r: Room) -> None:
    rng = r.rng
    # у перегородки к корпусу: стол-тумба, плита, мойка, плита, стол-тумба; у дальней — плита, стол-тумба, мойка
    kitchen_row(r, "corridor", [("furn_counter", 1.0), ("furn_stove", 1.67), ("furn_sink", 2.33), ("furn_stove", 2.99),
                                ("furn_counter", 3.66)])
    kitchen_row(r, "facade", [("furn_stove", 1.3), ("furn_counter", 1.96), ("furn_sink", 2.78)])
    # обеденный стол у окна вдоль простенка (над батареей — отступ), табуреты партии 1
    r.add("furn_dining", RADIATOR + 0.12 + 0.4025, r.D / 2, "room", yaw_add=90 + rng.uniform(-4, 4))
    for k in range(rng.randint(1, 3)):
        r.add("furn_stool", 1.2 + rng.uniform(-0.05, 0.1), r.D / 2 - 0.45 + k * 0.45, "room", yaw_add=rng.uniform(0, 90))
    # бидон и бак — в углах у двери
    r.add("furn_bucket", r.W - 0.35, 0.35, "room", yaw_add=rng.uniform(0, 360))
    if rng.random() < 0.7:
        r.add("furn_can", r.W - 0.35, r.D - 0.35, "room", yaw_add=rng.uniform(0, 360))


def basins(r: Room, wall: str, places: list[float], broken: int | None = None, mirrors: bool = True) -> None:
    """Раковины на кронштейнах у стены, над каждой — зеркало (по случаю его нет); broken — номер отбитой."""
    rng = r.rng
    for k, at in enumerate(places):
        r.wall("furn_basin_broken" if k == broken else "furn_basin", wall, at)
        if mirrors and rng.random() < 0.8:
            r.wall("furn_mirror", wall, at, h=1.75)


def wash(r: Room) -> None:
    rng = r.rng
    row = [1.0, 1.9, 2.8, 3.7, 4.6]
    basins(r, "corridor", row, broken=rng.randrange(len(row)) if rng.random() < 0.6 else None)
    basins(r, "facade", row, broken=rng.randrange(len(row)) if rng.random() < 0.4 else None)
    if rng.random() < 0.6:
        r.add("furn_bucket", 0.45, r.D / 2 + rng.uniform(-0.5, 0.5), "room", yaw_add=rng.uniform(0, 360))
    r.clears.append(r.box(r.W / 2 - 1.05, r.W / 2 + 1.05, r.D - 0.7, r.D + 0.02, 2.3))


def showers(r: Room) -> None:
    basins(r, "facade", [r.W / 2 - 0.5, r.W / 2 + 0.5])
    r.clears.append(r.box(r.W / 2 - 1.05, r.W / 2 + 1.05, r.D - 0.7, r.D + 0.02, 2.3))


def stalls(r: Room, wall: str, places: list[float], facing_sign: int) -> None:
    """Ряд кабинок с унитазами у стены; крайняя перегородка — у последней открытой стороны. Дверца по случаю
    прикрыта (как в форме), распахнута внутрь или выбита; один унитаз без бачка."""
    rng = r.rng
    torn = rng.randrange(len(places)) if rng.random() < 0.5 else None
    for k, at in enumerate(places):
        roll = rng.random()
        pose = {"дверца": round(rng.uniform(70, 100), 1)} if roll < 0.45 else {"дверца": "removed"} if roll < 0.6 else None
        r.wall("furn_stall", wall, at, pose=pose)
        r.wall("furn_toilet_torn" if k == torn else "furn_toilet", wall, at,
               pose={"сиденье": round(rng.uniform(60, 85), 1)} if k != torn and rng.random() < 0.3 else None)
    r.wall("furn_stall_end", wall, places[-1] + facing_sign * 0.55)


def toilets(r: Room) -> None:
    if r.s["id"].endswith("annex_toilets"):
        # хозкрыло: кабинки у дальней перегородки (лицом к перегородке корпуса: +u вдоль ряда), раковины напротив
        stalls(r, "facade", [1.75, 2.85, 3.95], 1)
        basins(r, "corridor", [2.3, 3.2])
        r.clears.append(r.box(r.W / 2 - 1.05, r.W / 2 + 1.05, r.D - 0.7, r.D + 0.02, 2.3))
    else:
        # туалет корпуса у входа: кабинки у глухой торцевой стены x0 (у фасада — окно с батареей), ряд — за проходом
        # от двери; раковины — у стены x1 вместо серого умывальника; серые чаши у фасада сняты (батарея — нет)
        stalls(r, "x0", [3.2, 4.3, 5.4], 1)
        basins(r, "x1", [r.D / 2 - 0.5, r.D / 2 + 0.5])
        r.clears.append(r.box(0.3, 3.4, r.D - 1.25, r.D - 0.4, 0.6))
        r.clears.append(r.box(r.W - 0.7, r.W + 0.02, r.D / 2 - 1.05, r.D / 2 + 1.05, 2.3))


SERVICE = {"kitchen": kitchen, "wash": wash, "showers": showers, "toilets": toilets}


# ---------------------------------------------------------------- партия 3: вещи жильцов, бумага, техника, ящики
# Владелец 2026-11-02: в комнатах — вещи жильцов, техника на столах, книги и тетради, студенческие плакаты, картины;
# в коридорах, на вахте и в комнате отдыха — советские плакаты, правила, календарь, учебная таблица; военные ящики,
# сундук и ящик для инструментов — в кладовых, в клетке техэтажа и в двух обжитых комнатах (баррикада у окна).
# Ящики, сундук, ящик для инструментов, чемодан, сумка и коробка обыскиваются (item.loot → LootContainer, таблица
# по виду): закрытые — с лутом, открытые и полупустые рядом — обысканы до игрока.

# модель → (название, таблица data/loot.json, секунд обыска, модель открытого после обыска)
LOOT = {"it_ammo": ("Ящик с патронами", "dorm_ammo_crate", 3.0, "it_ammo_open"),
        "it_zip": ("Ящик ЗИП", "dorm_zip_crate", 3.5, "it_zip_open"),
        "it_trunk": ("Сундук", "dorm_trunk", 3.5, "it_trunk_open"),
        "it_toolbox": ("Ящик с инструментами", "tools", 2.5, "it_toolbox_open"),
        # чемодан с лутом лежит на полу закрытым (модель раскрытого, створка в позе SHUT): при обыске откидывается
        "it_suitcase_open": ("Чемодан", "resident", 3.0, "it_suitcase_open"),
        "it_duffel": ("Спортивная сумка", "resident", 2.5, "it_duffel_half"),
        "it_carton": ("Коробка", "home", 2.0, "it_carton_open")}
SHUT = {"it_suitcase_open": {"створка": -176.0}}
FLAT = 0.001                 # бумага и рамы — вплотную к стене
TABLE_TOP = 0.75
NIGHTSTAND_TOP = 0.65
SHELF_TOP = 1.668            # верх полки партии 1 (корень — на 1,65 м)
POSTERS_ROOM = ("it_poster_s", "it_poster_s_curl", "it_drawing", "it_drawing_roll", "it_clip", "it_frame_pl")
POSTERS_SOVIET = ("it_poster", "it_poster", "it_poster_torn", "it_poster_curl")
CORRIDOR_FACE = 1.7          # грань несущей стены коридора (ось 1,89, толщина 0,38)


def find(r: Room, model: str) -> dict | None:
    return next((i for i in r.items if i["model"] == model), None)


def side_of(r: Room, item: dict) -> str:
    return "x0" if item["at"][0] - r.x0 < r.W / 2 else "x1"


def back(model: str) -> float:
    """От корня до задней грани габарита; у вещи с лутом — с открытым (крышка, клапаны не уходят в стену)."""
    out = 0.0
    for m in {model, LOOT[model][3] if model in LOOT else model}:
        a = VARIANTS[m]["aabb"]
        out = max(out, -(a["center"][2] - a["size"][2] / 2))
    return out


def width(model: str) -> float:
    return max(VARIANTS[m]["aabb"]["size"][0] for m in {model, LOOT[model][3] if model in LOOT else model})


def crate(r: Room, model: str, wall: str, along: float, off: float = 0.0, **kw) -> dict:
    """Вещь с лутом у стены: коробка столкновений, точка обыска; отступ — под открытую крышку; после обыска стенд
    ставит модель открытого."""
    a = VARIANTS[model]["aabb"]
    extra = back(model) + a["center"][2] - a["size"][2] / 2
    item = r.wall(model, wall, along, off=off + extra, pose=SHUT.get(model), **kw)
    name, table, search, opened = LOOT[model]
    item["loot"] = {"name": name, "table": table, "search": search, "open": opened}
    item["solid"] = True
    return item


def hang(r: Room, model: str, wall: str, along: float, center: float, **kw) -> dict:
    """Бумага и рама на стене: середина на высоте center над полом (корень листа — у верхнего края, рамы — у гвоздя)."""
    a = VARIANTS[model]["aabb"]
    return r.wall(model, wall, along, h=center - a["center"][1], off=FLAT - GAP, **kw)


def lived3(r: Room, rng: random.Random) -> None:
    """Жилая: на столе у окна ноутбук или монитор с клавиатурой и мышью (корпус — на полу у стола) либо тетрадь;
    книги на тумбочке у двухъярусной (на другой — телевизор), ряд учебников на полке; плакат над верхним ярусом,
    второй — у двери, картина над холодильником, календарь над тумбочкой; сумка у изножья и чемодан у двери —
    с лутом."""
    bunk = side_of(r, find(r, "furn_bunk_bed"))
    mid, vt = r.W / 2, r.D - RADIATOR      # vt — задняя кромка стола у батареи
    roll = rng.random()
    if roll < 0.45:
        r.add("it_laptop", mid - 0.22, vt - 0.35, "corridor", h=TABLE_TOP, yaw_add=rng.uniform(-12, 12))
        if rng.random() < 0.5:
            # мышь носом к окну (лицо модели — нос), провод — дальше по столу
            r.add("it_mouse", mid + 0.03, vt - 0.5, "room", h=TABLE_TOP, yaw_add=rng.uniform(-15, 15))
    elif roll < 0.8:
        r.add("it_monitor", mid - 0.22, vt - 0.17, "corridor", h=TABLE_TOP, yaw_add=rng.uniform(-6, 6))
        r.add("it_keyboard", mid - 0.22, vt - 0.53, "corridor", h=TABLE_TOP, yaw_add=rng.uniform(-5, 5))
        r.add("it_mouse", mid + 0.05, vt - 0.52, "room", h=TABLE_TOP, yaw_add=rng.uniform(-12, 12))
        r.wall("it_pc", "facade", mid + 0.66, off=RADIATOR, yaw_add=rng.uniform(-4, 4))
    else:
        r.add(rng.choice(("it_notebook", "it_notebook_open", "it_notebook48")), mid - 0.2, vt - 0.4, "corridor",
              h=TABLE_TOP, yaw_add=rng.uniform(-25, 25))
    r.wall(rng.choice(("it_book_stack", "it_notebook_stack", "it_book")), bunk, r.D - 0.3, h=NIGHTSTAND_TOP,
           yaw_add=rng.uniform(-20, 20))
    r.wall("it_book_row", "x0", 1.9 + rng.uniform(-0.2, 0.2), h=SHELF_TOP)
    hang(r, rng.choice(POSTERS_ROOM), bunk, r.D - 1.6, 2.3)
    if rng.random() < 0.7:
        hang(r, rng.choice(POSTERS_ROOM), "corridor", r.W - 1.25, 1.6)
    if rng.random() < 0.6:
        hang(r, rng.choice(("it_frame", "it_frame_pl")), "x1", 1.5, 1.65)
    if rng.random() < 0.5:
        hang(r, "it_calendar", bunk, r.D - 0.3, 1.4)
    # у широкой комнаты с двухъярусной у x0 там диван — сумки нет
    if rng.random() < 0.6 and not (bunk == "x0" and r.W >= 5.0):
        crate(r, "it_duffel", bunk, r.D - 3.05, yaw_add=rng.uniform(-6, 6))
    if rng.random() < 0.6:
        crate(r, "it_suitcase_open", "corridor", r.W - 1.1, yaw_add=rng.uniform(-4, 4))


def looted3(r: Room, rng: random.Random) -> None:
    """Разграбленная: разбитый монитор и ноутбук на сдвинутом столе, вскрытый корпус у стены, раскрытые книга и тетрадь
    на полу, упавшая картина, обысканные чемодан и коробка, завёрнутый плакат."""
    table = find(r, "furn_table")
    if rng.random() < 0.5:
        r.on("it_monitor_broken", table, -0.2, -0.1, TABLE_TOP, rng.uniform(-20, 20))
    if rng.random() < 0.4:
        r.on("it_laptop_broken", table, 0.3, 0.05, TABLE_TOP, rng.uniform(-15, 15))
    if rng.random() < 0.6:
        r.wall("it_pc_opened", "x0", 2.6, yaw_add=rng.uniform(-10, 10))
    if rng.random() < 0.7:
        r.add("it_book_open", r.W - 0.7, 1.85, "room", yaw_add=rng.uniform(0, 360))
    if rng.random() < 0.5:
        r.add("it_notebook_open", r.W - 1.2, 1.7, "room", yaw_add=rng.uniform(0, 360))
    if rng.random() < 0.6:
        r.wall("it_frame_fallen", "x1", 3.6)
    if rng.random() < 0.5:
        hang(r, rng.choice(("it_poster_s_curl", "it_clip")), "corridor", r.W - 1.25, 1.6)
    if rng.random() < 0.5:
        r.wall("it_suitcase_open", "x0", 3.4, yaw_add=rng.uniform(-6, 6))
    if rng.random() < 0.4:
        r.wall("it_carton_open", "corridor", r.W - 1.25, yaw_add=rng.uniform(-8, 8))


def barricade3(r: Room, rng: random.Random, settled: bool) -> None:
    """Баррикада: в двух обжитых — ящики ЗИП и с патронами у стены x1, сундук у x0 (с лутом), рядом обысканный ящик;
    в остальных — завёрнутый плакат и брошенная тетрадь."""
    if settled:
        crate(r, "it_zip", "x1", 1.6, yaw_add=rng.uniform(-3, 3))
        crate(r, "it_ammo", "x1", 2.55, yaw_add=rng.uniform(-3, 3))
        crate(r, "it_trunk", "x0", 3.1, yaw_add=rng.uniform(-3, 3))
        if rng.random() < 0.6:
            r.wall("it_ammo_open", "x1", 3.25, yaw_add=rng.uniform(-6, 6))
        return
    if rng.random() < 0.5:
        hang(r, "it_poster_s_curl", "corridor", r.W - 1.25, 1.6)
    if rng.random() < 0.3:
        r.add("it_notebook48", rng.uniform(1.6, r.W - 1.0), rng.uniform(1.5, 2.2), "room", yaw_add=rng.uniform(0, 360))


def empty3(r: Room, rng: random.Random) -> None:
    """Пустая с матрасами: сумка и коробка с лутом, тубус и учебники на полу, календарь у двери."""
    if rng.random() < 0.6:
        crate(r, "it_duffel", "x1", 3.0, yaw_add=rng.uniform(-8, 8))
    if rng.random() < 0.5:
        crate(r, "it_carton", "corridor", r.W - 0.55, yaw_add=rng.uniform(-5, 5))
    if rng.random() < 0.4:
        r.wall("it_tube", "x0", 2.9, yaw_add=rng.uniform(-5, 5))
    if rng.random() < 0.3:
        r.wall("it_book_stack", "x0", 2.2, yaw_add=rng.uniform(-20, 20))
    if rng.random() < 0.4:
        hang(r, "it_calendar", "corridor", max(r.W / 2, 2.2), 1.5)


def breach3(r: Room, rng: random.Random) -> None:
    """С проломом: плакат у двери, стопка учебников у стены коридора (не в дыре — их снимает main)."""
    if rng.random() < 0.4:
        hang(r, rng.choice(("it_poster_s_curl", "it_clip")), "corridor", r.W - 1.25, 1.6)
    if rng.random() < 0.3:
        r.wall("it_book_stack", "corridor", 2.2, yaw_add=rng.uniform(-20, 20))


THINGS3 = {"жилая": lived3, "разграбленная": looted3, "пустая с матрасами": empty3, "пролом": breach3}


def row(r: Room, rng: random.Random, wall: str, start: float, end: float, plan: list, off: float = 0.0) -> None:
    """Вещи рядом у стены от start к end (вдоль — u у стены коридора и фасада, v у боковых), зазор 6–14 см; что не
    влезло — не ставится. plan: [(модель, с лутом)], вещь — по случаю 3 из 4."""
    step = 1.0 if end > start else -1.0
    pos = start
    for model, loot in plan:
        if rng.random() > 0.75:
            continue
        L = width(model) if loot else VARIANTS[model]["aabb"]["size"][0]
        c = pos + step * L / 2
        if (c + step * L / 2 - end) * step > 0:
            break
        if loot:
            crate(r, model, wall, c, off=off, yaw_add=rng.uniform(-3, 3))
        else:
            r.wall(model, wall, c, off=off, yaw_add=rng.uniform(-4, 4))
        pos = c + step * (L / 2 + rng.uniform(0.06, 0.14))


# кладовая: ряд у боковой стены, ряд у окна (над батареей — отступ); закрытое — с лутом, открытое — уже обыскано
STORES = {"военная": ([("it_zip", True), ("it_ammo", True), ("it_ammo_open", False), ("it_zip_open", False)],
                      [("it_trunk", True), ("it_toolbox_open", False), ("it_ammo", True)]),
          "хозяйственная": ([("it_carton", True), ("it_carton", True), ("it_carton_open", False)],
                            [("it_toolbox", True), ("it_carton_open", False), ("it_carton", True)]),
          "вещи жильцов": ([("it_suitcase_open", True), ("it_duffel", True), ("it_duffel_half", False)],
                           [("it_suitcase_open", True), ("it_carton", True), ("it_suitcase_open", False)])}


def storage3(r: Room, rng: random.Random) -> None:
    side, window = STORES[rng.choice(sorted(STORES))]
    if r.s["id"].endswith("annex_store"):
        # хозкрыло: дверь — посередине стены x1, окна — на x0: ряды у окон и у обеих поперечных стен
        row(r, rng, "x0", 0.5, r.D - 0.5, side + window, off=RADIATOR)
        row(r, rng, "corridor", r.W - 0.5, 0.4, window)
        row(r, rng, "facade", r.W - 0.5, 0.4, side)
        return
    row(r, rng, "x1", 0.9 if r.door_u > r.W / 3 else 0.5, r.D - 0.45, side)
    row(r, rng, "facade", r.W - 0.75, 0.35, window, off=RADIATOR)


def tech3(r: Room, rng: random.Random) -> None:
    """Техэтаж: в клетке у щитовой — вместо трёх серых ящиков ЗИП, ящик с патронами и сундук (с лутом), обысканный ящик
    для инструментов; у окна между баками — ящик с патронами, ящик для инструментов, обысканная коробка."""
    def at(x: float, z: float) -> tuple[float, float]:
        return x - r.x0, r.side * (z - r.zc)
    mesh = -8.6 + GAP                          # задняя сетка клетки
    u, v = at(39.0, mesh + back("it_zip"))
    item = r.add("it_zip", u, v, "room", yaw_add=rng.uniform(-2, 2))
    item.update(solid=True, loot=dict(zip(("name", "table", "search", "open"), LOOT["it_zip"])))
    u, v = at(40.15, mesh + back("it_ammo"))
    item = r.add("it_ammo", u, v, "room", yaw_add=rng.uniform(-3, 3))
    item.update(solid=True, loot=dict(zip(("name", "table", "search", "open"), LOOT["it_ammo"])))
    u, v = at(38.15 + GAP + back("it_trunk"), -6.6)
    item = r.add("it_trunk", u, v, "+u", yaw_add=rng.uniform(-3, 3))
    item.update(solid=True, loot=dict(zip(("name", "table", "search", "open"), LOOT["it_trunk"])))
    a = VARIANTS["it_toolbox_open"]["aabb"]
    u, v = at(40.6 - GAP - a["size"][2] / 2 + a["center"][2], -6.3)
    r.add("it_toolbox_open", u, v, "-u", yaw_add=rng.uniform(-6, 6))
    r.clears.append({"section": r.section, "min": [38.3, round(r.y - 0.01, 3), -8.45],
                     "max": [40.15, round(r.y + 0.8, 3), -6.55]})
    # у южного окна между баками (x 11,5…15,2): стена фасада — «коридор» этой комнаты (v от z = −8,88)
    crate(r, "it_toolbox", "corridor", 12.4, off=RADIATOR, yaw_add=rng.uniform(-4, 4))
    crate(r, "it_ammo", "corridor", 13.4, off=RADIATOR, yaw_add=rng.uniform(-4, 4))
    r.wall("it_carton_open", "corridor", 14.5, off=RADIATOR, yaw_add=rng.uniform(-6, 6))


def item3(rng: random.Random, iid: str, section: str, model: str, at: list[float], yaw: float,
          variant: str | None = None) -> dict:
    """Вещь вне комнат (коридор, вахта, комната отдыха): вариант — как у Room.add, если не задан."""
    item = {"id": iid, "section": section, "model": model, "at": [round(x, 4) for x in at], "yaw": round(yaw, 2),
            "far": FAR3.get(model, 40.0)}
    if variant is None and VARIANTS[model]["variants"]:
        variant = rng.choice([None] + VARIANTS[model]["variants"])
    if variant:
        item["variant"] = variant
    return item


def wall_item(rng: random.Random, iid: str, section: str, model: str, floor_y: float, face: tuple, along: float,
              center: float, variant: str | None = None) -> dict:
    """Бумага на стене вне комнат: face — (ось стены «x» или «z», координата грани, знак нормали в помещение)."""
    a = VARIANTS[model]["aabb"]
    back = -(a["center"][2] - a["size"][2] / 2) + FLAT
    axis, c, sign = face
    h = floor_y + center - a["center"][1]
    if axis == "z":   # грань поперёк z: вдоль — x
        return item3(rng, iid, section, model, [along, h, c + sign * back], 0.0 if sign > 0 else 180.0, variant)
    return item3(rng, iid, section, model, [c + sign * back, h, along], 90.0 if sign > 0 else -90.0, variant)


def corridors3(plan: dict) -> tuple[list, list]:
    """Коридоры этажей 1–4: советские плакаты и правила проживания на глухих отрезках несущих стен (между дверями, не
    у перегородок — там пилястры, не у ниш шкафов); комната отдыха — учебная таблица на торцевой стене, книги, тетради
    и тубус на столе; вахта — календарь, правила и плакат на торцевой стене, монитор, клавиатура и мышь на столе
    вахтёра вместо серого экрана."""
    rng = random.Random("dorm_items3_corridors")
    items, clears = [], []
    floor_y = plan["scale"]["floor_y"]
    for floor in (1, 2, 3, 4):
        sec, y = f"Floor{floor}", floor_y[floor - 1]
        cuts = {1: [], -1: [n["at"][0] for n in plan["niches"] if n["floor"] == floor]}
        for s in plan["spaces"]:
            if s["floor"] == floor and s.get("kind") not in ("stairs",) and "_annex_" not in s["id"]:
                x0, z0, x1, z1 = s["rect"]
                cuts[1 if z1 > 0 else -1] += [x0, x1]
        segs = []
        for b in plan["sections"][sec]["boxes"]:
            if b.get("id") != "corridor_load" or abs(abs(b["at"][2]) - 1.89) > 0.05:
                continue
            (x, by, z), (sx, sy, _) = b["at"], b["size"]
            if abs(by - sy / 2 - y) > 0.05:
                continue  # над дверью
            side = 1 if z > 0 else -1
            a, c = x - sx / 2 + 0.3, x + sx / 2 - 0.3
            pts = sorted(set([a, c] + [k for k in cuts[side] if a < k < c]))
            # отрезки между точками раздела без ±0,5 у перегородок и ниш
            for p0, p1 in zip(pts, pts[1:]):
                lo = p0 + (0.5 if p0 != a else 0.0)
                hi = p1 - (0.5 if p1 != c else 0.0)
                if hi - lo > 0.75:
                    segs.append((side, lo, hi))
        rng.shuffle(segs)
        used: list[float] = []
        n = 0
        plan_items = [rng.choice(POSTERS_SOVIET) for _ in range(3)] + ["it_clip"]
        for model in plan_items:
            w = VARIANTS[model]["aabb"]["size"][0]
            for side, lo, hi in segs:
                if hi - lo < w + 0.1:
                    continue
                x = rng.uniform(lo + w / 2, hi - w / 2)
                if any(abs(x - u) < 2.5 for u in used):
                    continue
                used.append(x)
                face = ("z", side * CORRIDOR_FACE, -side)
                variant = "pravila" if model == "it_clip" else None
                center = 1.5 if model == "it_clip" else 1.65
                items.append(wall_item(rng, f"f{floor}_corridor_{n}_{model[3:]}", sec, model, y, face, x, center, variant))
                n += 1
                break
        # комната отдыха: таблица на восточной стене, на столе — книга, тетради, тубус
        items.append(wall_item(rng, f"f{floor}_lounge_chart", sec, "it_chart", y, ("x", 28.53, -1), 4.6, 1.75))
        table = next((b for b in plan["sections"][sec]["boxes"] if b.get("id") == "lounge_table"), None)
        if table is not None:
            tx, ty, tz = table["at"]
            top = ty + table["size"][1] / 2
            for k, (model, p) in enumerate((("it_book_open", 0.6), ("it_notebook_stack", 0.5), ("it_tube", 0.35))):
                if rng.random() < p:
                    items.append(item3(rng, f"f{floor}_lounge_{k}_{model[3:]}", sec, model,
                                       [tx - 0.55 + 0.55 * k + rng.uniform(-0.08, 0.08), top, tz + rng.uniform(-0.15, 0.15)],
                                       rng.uniform(-30, 30)))
    # вахта (1-й этаж, у западного торца x = 0): стол вахтёра x 0,18…1,55, z 4,0…4,7, верх 0,9 м над полом
    y = floor_y[0]
    wall = ("x", 0.0, 1)
    items.append(wall_item(rng, "f1_watch_calendar", "Floor1", "it_calendar", y, wall, 3.2, 1.55))
    items.append(wall_item(rng, "f1_watch_rules", "Floor1", "it_clip", y, wall, 2.7, 1.5, "pravila"))
    items.append(wall_item(rng, "f1_watch_poster", "Floor1", "it_poster", y, wall, 6.1, 1.7))
    desk = y + 0.9
    items.append(item3(rng, "f1_watch_monitor", "Floor1", "it_monitor", [0.75, desk, 4.2], 0.0))
    items.append(item3(rng, "f1_watch_keyboard", "Floor1", "it_keyboard", [0.75, desk, 4.52], 0.0))
    items.append(item3(rng, "f1_watch_mouse", "Floor1", "it_mouse", [1.15, desk, 4.5], 180.0))
    clears.append({"section": "Floor1", "min": [0.4, round(desk + 0.01, 3), 4.15], "max": [1.1, round(desk + 0.6, 3), 4.38]})
    return items, clears


def in_hole(r: Room, item: dict) -> bool:
    x, _, z = item["at"]
    for b in getattr(r, "breaches", []):
        x0, z0, x1, z1 = b["hole"]
        if min(x0, x1) - 0.3 < x < max(x0, x1) + 0.3 and min(z0, z1) - 0.3 < z < max(z0, z1) + 0.3:
            return True
    return False


def main() -> None:
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    items, clears = [], []
    # две обжитые комнаты с военными ящиками — из комнат с баррикадой у окна
    settled = set(random.Random("dorm_items3_settled").sample(
        sorted(s["id"] for s in plan["spaces"] if s.get("state") == "баррикада у окна"), 2))
    for s in plan["spaces"]:
        if s.get("kind") in SERVICE:
            r = Room(s)
            r.clears = []
            SERVICE[s["kind"]](r)
            items += r.items
            clears += r.clears
            continue
        if s.get("kind") == "storage" or s["id"] == "f5_tech_hall":
            r = Room(s)
            r.clears = []
            (storage3 if s.get("kind") == "storage" else tech3)(r, random.Random(s["id"] + "/3"))
            items += r.items
            clears += r.clears
            continue
        if s.get("kind") != "room":
            continue
        r = Room(s)
        r.breaches = [b for b in plan.get("breaches", []) if s["id"] in (b["room_below"], b["room_above"])]
        STATES[s["state"]](r)
        n0 = len(r.items)
        rng3 = random.Random(s["id"] + "/3")
        if s["state"] == "баррикада у окна":
            barricade3(r, rng3, s["id"] in settled)
        elif s["state"] in THINGS3:
            THINGS3[s["state"]](r, rng3)
        r.items = r.items[:n0] + [i for i in r.items[n0:] if not in_hole(r, i)]
        # у проломов в перегородках (plan.wall_breaches) мебель не стоит: проход должен быть открыт
        for wb in plan.get("wall_breaches", []):
            if wb["floor"] != s["floor"]:
                continue
            r.items = [i for i in r.items if not (abs(i["at"][0] - wb["x"]) < 1.15 and abs(i["at"][2] - wb["z"]) < wb["width"] / 2 + .75)]
        items += r.items
        clears += r.clear()
    more, more_clears = corridors3(plan)
    items += more
    clears += more_clears
    OUT.write_text(json.dumps({"version": 1, "source": "tools/dorm_modules/furnish_rooms.py", "furniture": items,
                               "clear": clears}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    from collections import Counter
    print("FURNISH", len(items), "вещей,", len(clears), "мест серых кроватей;", dict(Counter(i["model"] for i in items)))


if __name__ == "__main__":
    main()
