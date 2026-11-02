"""Мебель общежития в стенд: расстановка по комнатам плана (data/blockouts/dorm.json) → data/blockouts/dorm_furniture.json.

  python -X utf8 tools/dorm_modules/furnish_rooms.py

Интервью 2026-10-31: казённая мебель вперемешку с вещами жильцов, «целая, но старая». Комната — по своему виду
(space.state в плане): жилая — всё на местах и вещи жильцов (холодильник, телевизор, плитка, ковёр на стене, в широких —
диван); разграбленная — техники нет, стулья опрокинуты, матрасы сброшены, тумбочка и стол сдвинуты; сгоревшая — только
железные каркасы кроватей; баррикада у окна — шкаф, стол, кровать и матрасы стеной у окна; пустая с матрасами — матрасы
на полу. Случай — по номеру комнаты, повторяемый. Серые кровати плана (bunk_*) стенд убирает в прямоугольниках clear —
только если модели мебели на месте (без assets/models стоит серый план).

Оси комнаты: u — поперёк от стены x0, v — от стены коридора к фасаду; модели смотрят лицом в +Z Godot (в Blender −Y),
корень — середина опоры на полу (полка и ковёр — у стены).
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
         "furn_fridge", "furn_sofa"}
SMALL = {"furn_tv", "furn_hotplate", "furn_shelf"}
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
        self.section = f"Floor{s['floor']}"
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
            variant: str | None = None) -> None:
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


def main() -> None:
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    items, clears = [], []
    for s in plan["spaces"]:
        if s.get("kind") != "room":
            continue
        r = Room(s)
        r.breaches = [b for b in plan.get("breaches", []) if s["id"] in (b["room_below"], b["room_above"])]
        STATES[s["state"]](r)
        items += r.items
        clears += r.clear()
    OUT.write_text(json.dumps({"version": 1, "source": "tools/dorm_modules/furnish_rooms.py", "furniture": items,
                               "clear": clears}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    from collections import Counter
    print("FURNISH", len(items), "вещей,", len(clears), "мест серых кроватей;", dict(Counter(i["model"] for i in items)))


if __name__ == "__main__":
    main()
