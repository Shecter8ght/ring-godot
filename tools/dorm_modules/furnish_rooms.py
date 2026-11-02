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
         "furn_basin", "furn_basin_broken", "furn_toilet", "furn_toilet_torn", "furn_stall", "furn_stall_end"}
SMALL = {"furn_tv", "furn_hotplate", "furn_shelf", "furn_pot", "furn_kettle", "furn_pan", "furn_can", "furn_bucket",
         "furn_mirror", "furn_dishrack"}
# конфорки плиты в осях модели Godot (x, z — build_furniture2.stove: Blender (x, y) → (x, −y)), верх конфорок
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
            variant: str | None = None, pose: dict | None = None) -> None:
        a = VARIANTS[model]["aabb"]
        lift = 0.0
        if tilt:
            # опрокинутая вещь не уходит под пол: низ после наклона на ±90° вокруг своей X — от её глубины по Z
            zmin = a["center"][2] - a["size"][2] / 2
            zmax = a["center"][2] + a["size"][2] / 2
            lift = zmax if tilt > 0 else -zmin
        item = {"id": f"{self.s['id']}_{len(self.items)}_{model[5:]}", "section": self.section, "model": model,
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
        item["far"] = 25.0 if model in SMALL else 60.0
        self.items.append(item)

    def wall(self, model: str, wall: str, along: float, h: float = 0.0, off: float = 0.0, **kw) -> None:
        """Вплотную к стене лицом в комнату; along — середина вдоль стены (u для стен коридора и фасада, v для боковых);
        off — отступ от стены (стол у окна — на батарею)."""
        a = VARIANTS[model]["aabb"]
        back = -(a["center"][2] - a["size"][2] / 2) + GAP + off  # от корня до задней грани
        if wall == "x0":
            self.add(model, back, along, "+u", h, **kw)
        elif wall == "x1":
            self.add(model, self.W - back, along, "-u", h, **kw)
        elif wall == "corridor":
            self.add(model, along, back, "room", h, **kw)
        else:  # facade
            self.add(model, along, self.D - back, "corridor", h, **kw)

    def bed(self, model: str, wall: str, mattress: bool = True, variant: str | None = None) -> None:
        """Кровать вдоль боковой стены у окна (0,6 м от фасада, как серые в плане), изголовьем к окну; матрасы на ярусах."""
        v = self.D - 0.6 - 1.0
        # 6 см от стены: стойки кровати не задевают ковёр
        u = 0.456 + 0.06 if wall == "x0" else self.W - 0.456 - 0.06
        self.add(model, u, v, "corridor", variant=variant)
        if mattress:
            for z in ((0.355, 1.305) if model == "furn_bunk_bed" else (0.425,)):
                self.add("furn_mattress", u, v, "corridor", h=z)

    def on(self, model: str, host: dict, lx: float, lz: float, h: float, yaw_add: float = 0.0, **kw) -> None:
        """Вещь на другой (кастрюля на конфорке, сковорода на столе-тумбе): lx, lz — точка в осях модели-основы."""
        psi = math.radians(host["yaw"])
        dx = lx * math.cos(psi) + lz * math.sin(psi)
        dz = -lx * math.sin(psi) + lz * math.cos(psi)
        u = host["at"][0] + dx - self.x0
        v = self.side * (host["at"][2] + dz - self.zc)
        self.add(model, u, v, "room", h, yaw_add=host["yaw"] + yaw_add - self.yaw_facing("room"), **kw)

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


def main() -> None:
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    items, clears = [], []
    for s in plan["spaces"]:
        if s.get("kind") in SERVICE:
            r = Room(s)
            r.clears = []
            SERVICE[s["kind"]](r)
            items += r.items
            clears += r.clears
            continue
        if s.get("kind") != "room":
            continue
        r = Room(s)
        r.breaches = [b for b in plan.get("breaches", []) if s["id"] in (b["room_below"], b["room_above"])]
        STATES[s["state"]](r)
        # у проломов в перегородках (plan.wall_breaches) мебель не стоит: проход должен быть открыт
        for wb in plan.get("wall_breaches", []):
            if wb["floor"] != s["floor"]:
                continue
            r.items = [i for i in r.items if not (abs(i["at"][0] - wb["x"]) < 1.15 and abs(i["at"][2] - wb["z"]) < wb["width"] / 2 + .75)]
        items += r.items
        clears += r.clear()
    OUT.write_text(json.dumps({"version": 1, "source": "tools/dorm_modules/furnish_rooms.py", "furniture": items,
                               "clear": clears}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    from collections import Counter
    print("FURNISH", len(items), "вещей,", len(clears), "мест серых кроватей;", dict(Counter(i["model"] for i in items)))


if __name__ == "__main__":
    main()
