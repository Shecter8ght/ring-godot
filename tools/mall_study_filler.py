"""Наполнение серого черновика территории ТЦ (владелец, 2026-10-17: «раскидывай серыми кусками»).

Пустые места между участками заполняются с ритмом: укрытие, мелкая находка, ориентир, а между ними —
открытые куски не длиннее 40–60 м. Что ставится:
  укрытия   — блоки ФБС, дорожные плиты, поддоны, кабельные катушки, мусорные баки, мешки с песком,
              брошенные машины вдоль дорог (обычные, сгоревшие, перевёрнутые), дорожные блоки;
  природа   — бурьян пятнами, кусты полосами вдоль дорог и забора, молодые берёзы, лужи;
  ориентиры — ЛЭП через запад и север к подстанции, щиты у трассы, теплотрасса от котельной к ТЦ;
  истории   — стоянка у костра, авария на трассе, брошенная колонна, воронка, старый пост у съезда,
              упавший щит; рядом с каждой — находка (сумка).
Районы: стройка второй очереди (север), поле у КПП (запад), придорожье трассы (юг), теплотрасса,
гаражи и контейнеры (восток).

Координаты игры: X — восток, Z — юг (север — −Z), углы — от +X к +Z. Наборы (kit) и их размеры — в
src/blockout/mall_filler.gd; у вытянутых длинная ось — локальная Z, yaw — поворот вокруг вертикали в
градусах (yaw_along). Рельеф (котлован, отвалы, воронка, кювет) читает MallLandscape.ground().
Укрытия не встают на дороги, маршруты проверки, постройки, стенки террас, парковки и точки участков.
"""

from __future__ import annotations

import math
import random

SEED = 20261017
# Стройка второй очереди ТЦ: между кольцевой дорогой и лесом на севере
SITE_CENTER = (35.0, -290.0)
SITE_SIZE = (140.0, 48.0)
# Опоры ЛЭП: с юга через трассу, полем у КПП на север, просекой вдоль леса — к подстанции техкомплекса
POWER_TOWERS = [(-385.0, 342.0), (-372.0, 170.0), (-358.0, 40.0), (-352.0, -110.0), (-345.0, -225.0),
                (-215.0, -335.0), (-70.0, -340.0), (80.0, -338.0), (225.0, -318.0), (290.0, -236.0),
                (238.0, -112.0)]
POWER_END = (262.0, -112.0, 4.6)  # провода спускаются на крышу подстанции
# Теплотрасса: от котельной к стене ТЦ; над дорогой и пожарным проездом поднимается П-образно
HEAT_MAIN = [(296.0, -133.0), (296.0, -100.0), (252.0, -55.0), (132.0, -41.0), (96.1, -29.8)]
# Колея от КПП через поле к автостанции; по её середине стоит брошенная колонна
RUT_LINE = [(-328.0, -6.0), (-333.0, 60.0), (-346.0, 140.0), (-362.0, 214.0), (-300.0, 240.0), (-240.0, 256.0),
            (-205.0, 264.0)]
CONVOY_FROM = 3  # колонна — от этой точки колеи
CRATER = (-270.0, 120.0)  # на восточном берегу речки, между ней и кольцевой дорогой
CAMP = (-205.0, -240.0)
CRASH = (128.0, 297.0)
SANDBAG_POST = (232.0, 262.0)
DITCH_Z = 299.5
DITCH_PIECES = [(-400.0, -200.0), (-132.0, -68.0), (-12.0, 196.0), (226.0, 385.0)]
# Ритм подходов: укрытия там, где замер проверки нашёл открытые куски длиннее 60 м
# [набор, x, z, поворот°, состояние машины]; земляные кучи [x, z, rx, rz, высота]
ROUTE_COVER = [
    ("wreck", -42.0, 339.0, 80.0, "burnt"), ("roadside_car", -18.0, 303.5, 95.0, ""),
    ("fbs", -4.0, 285.0, 20.0, None), ("roadside_car", 9.0, 240.0, 5.0, "side"), ("jerseys", -10.0, 224.0, 30.0, None),
    ("wreck", -383.0, 52.0, 140.0, "burnt"), ("fbs", -283.0, -72.0, 60.0, None),
    ("fbs", -262.0, -95.0, 10.0, None), ("roadside_car", -264.0, -70.0, 170.0, ""),
    ("pallets", 354.0, 262.0, 30.0, None), ("fbs", 142.0, -308.0, 45.0, None),
]
ROUTE_MOUNDS = [(160.0, -292.0, 6.0, 4.5, 1.8)]
CAR_TINTS = ["6f7880", "8b8a83", "5d5853", "8d7a63", "4f5d6b", "9a9c97", "6b3f35", "7a8a6e"]
BURNT = len(CAR_TINTS)  # индекс цвета сгоревшей машины
TINTS = CAR_TINTS + ["3b3532"]


# ------------------------------------------------------------------ геометрия на плоскости (X, Z)

def seg_dist(p, a, b) -> float:
    dx, dz = b[0] - a[0], b[1] - a[1]
    l2 = dx * dx + dz * dz
    t = 0.0 if l2 == 0.0 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dz) / l2))
    return math.hypot(p[0] - (a[0] + t * dx), p[1] - (a[1] + t * dz))


def poly_dist(p, pts) -> float:
    if len(pts) == 1:
        return math.dist(p, pts[0])
    return min(seg_dist(p, a, b) for a, b in zip(pts, pts[1:]))


def ring_dist(p, poly) -> float:
    return min(seg_dist(p, a, b) for a, b in zip(poly, poly[1:] + poly[:1]))


def in_poly(p, poly) -> bool:
    inside = False
    j = len(poly) - 1
    for i in range(len(poly)):
        (xi, zi), (xj, zj) = poly[i], poly[j]
        if (zi > p[1]) != (zj > p[1]) and p[0] < (xj - xi) * (p[1] - zi) / (zj - zi) + xi:
            inside = not inside
        j = i
    return inside


def ang(p) -> float:
    return math.degrees(math.atan2(p[1], p[0]))


def in_arc(a: float, a0: float, a1: float) -> bool:
    return (a - a0) % 360.0 <= (a1 - a0) % 360.0


def ang_gap(a: float, b: float) -> float:
    return abs((a - b + 180.0) % 360.0 - 180.0)


def polar(a: float, r: float) -> tuple[float, float]:
    return r * math.cos(math.radians(a)), r * math.sin(math.radians(a))


def yaw_along(dx: float, dz: float) -> float:
    """Поворот, при котором локальная Z набора смотрит вдоль (dx, dz)."""
    return math.degrees(math.atan2(dx, dz))


def path_length(pts) -> float:
    return sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))


def along(pts, s: float):
    """Точка и направление на расстоянии s вдоль ломаной."""
    for a, b in zip(pts, pts[1:]):
        d = math.dist(a, b)
        if s <= d or (a, b) == (pts[-2], pts[-1]):
            t = 0.0 if d == 0.0 else min(1.0, s / d)
            return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t), ((b[0] - a[0]) / d, (b[1] - a[1]) / d)
        s -= d
    return pts[-1], (1.0, 0.0)


def offset_line(pts, off: float):
    """Ломаная, сдвинутая вбок на off (влево от хода)."""
    out = []
    for i, p in enumerate(pts):
        a = pts[max(0, i - 1)]
        b = pts[min(len(pts) - 1, i + 1)]
        dx, dz = b[0] - a[0], b[1] - a[1]
        d = math.hypot(dx, dz) or 1.0
        out.append([round(p[0] - dz / d * off, 2), round(p[1] + dx / d * off, 2)])
    return out


class Near:
    """Точки в клетках по 40 м: быстрый ответ «есть ли что-то ближе d»."""

    def __init__(self, cell: float = 40.0):
        self.cell = cell
        self.cells: dict[tuple[int, int], list[tuple[float, float]]] = {}

    def add(self, p) -> None:
        key = (int(p[0] // self.cell), int(p[1] // self.cell))
        self.cells.setdefault(key, []).append((p[0], p[1]))

    def within(self, p, d: float) -> bool:
        reach = int(d // self.cell) + 1
        cx, cz = int(p[0] // self.cell), int(p[1] // self.cell)
        for i in range(cx - reach, cx + reach + 1):
            for j in range(cz - reach, cz + reach + 1):
                for q in self.cells.get((i, j), ()):
                    if math.hypot(p[0] - q[0], p[1] - q[1]) < d:
                        return True
        return False


# ------------------------------------------------------------------ раскладка

class Layout:
    def __init__(self, plan: dict):
        self.plan = plan
        self.rng = random.Random(SEED)
        self.items: list[list] = []
        self.weeds: list[list] = []
        self.stories: list[dict] = []
        self.cover: list[list[float]] = []
        self.earth = {"mounds": [], "craters": [], "pits": [], "ditches": []}
        self.taken: list[tuple[float, float, float]] = []
        self.rects: list[tuple[float, float, float, float]] = []
        self.corridors: list[tuple[list, float]] = []
        self.roads = [(r["points"], float(r["width"])) for r in plan["roads"]]
        # кольцевая дорога — окружность: её проверяем по радиусу, остальные — по ломаной
        self.loop = next(float(r["width"]) for r in plan["roads"] if r["id"] == "loop")
        self.other_roads = [(r["points"], float(r["width"])) for r in plan["roads"] if r["id"] != "loop"]
        self.ruts: list[list] = []
        self.near_cover = Near()
        self.building_spots = [b["at"] for b in plan["buildings"] if b["region"] != "Outside"]
        self.routes = [r["points"] for r in plan["probe_routes"]]
        # точки, у которых ничего не ставится: появления, выходы, места участков и точки замера рельефа проверки
        self.points = ([s["at"] for s in plan["spawns"]] + [e["at"] for e in plan["exits"]]
                       + [loc["spawn"] for loc in plan["locations"]]
                       + [[30.0, 160.0], [30.0, 190.0], [30.0, 225.0], [-200.0, -300.0], [150.0, 318.0]])

    # ---------------------------------------------------------- проверки места

    def _in_building(self, p, b, margin: float) -> bool:
        y = math.radians(b["yaw"])
        dx, dz = p[0] - b["at"][0], p[1] - b["at"][1]
        u = dx * math.cos(y) - dz * math.sin(y)
        v = dx * math.sin(y) + dz * math.cos(y)
        return abs(u) < b["size"][0] * 0.5 + margin and abs(v) < b["size"][1] * 0.5 + margin

    def blocked(self, p, margin: float, veg: bool = False) -> bool:
        """Нельзя ставить: вне участка, здание и проезд, трасса, лес, дороги, постройки, площадь, двор, стенки
        террас, водоём, мосты, точки участков; укрытиям ещё — парковки и маршруты проверки."""
        plan = self.plan
        x, z = p
        r = math.hypot(x, z)
        a = ang(p)
        if not in_poly(p, plan["boundary"]) or ring_dist(p, plan["boundary"]) < 6.0 + margin:
            return True
        if r < 127.0 + margin or 300.0 - margin < z < 336.0 + margin:
            return True
        # в лесу и рощах укрытиям места нет (там деревья), кустам и бурьяну — можно: подлесок
        if not veg and any(in_poly(p, f) for f in plan["forest"]):
            return True
        relief = plan.get("relief", {})
        river = relief.get("river")
        if river and poly_dist(p, river["points"]) < (10.0 if veg else 16.0) + margin:
            return True
        if any(poly_dist(p, c["points"]) < (4.0 if veg else 7.0) + margin for c in relief.get("cliffs", [])):
            return True
        side = 1.0 if veg else 2.5
        if abs(r - plan["mall"]["loop_r"]) < self.loop * 0.5 + margin + side:
            return True
        if any(poly_dist(p, pts) < w * 0.5 + margin + side for pts, w in self.other_roads):
            return True
        if any(self._in_building(p, b, margin + side) for b in plan["buildings"]):
            return True
        pl = plan["plaza"]
        if in_arc(a, *pl["a"]) and pl["r"][0] - margin < r < pl["r"][1] + margin:
            return True
        yd = plan["yard"]
        if in_arc(a, yd["a"][0] - 2.0, yd["a"][1] + 2.0) and yd["r"][0] - 4.0 - margin < r < yd["r"][1] + 4.0 + margin:
            return True
        if ang_gap(a, yd["ramp_a"]) < yd["ramp_half_deg"] + 3.0 and yd["r"][1] - 2.0 < r < yd["ramp_r"][1] + 4.0 + margin:
            return True
        t = plan["terraces"]
        if in_arc(a, t["a"][0] - 2.0, t["a"][1] + 2.0) and any(abs(r - w) < 4.0 + margin for w in t["walls"]):
            return True
        if 165.0 < r < 258.0 and any(math.radians(ang_gap(a, e)) * r < 4.0 + margin for e in t["a"]):
            return True
        if any(math.dist(p, polar(st["a"], st["r"])) < 10.0 + margin for st in t["stairs"]):
            return True
        if not veg:
            # на парковке — только мимо рядов брошенных машин (их ставит MallLandscape)
            for park in plan["parkings"]:
                rows = park["rows"]["a"]
                if in_arc(a, rows[0] - 2.0, rows[1] + 2.0) and park["r"][0] - 2.0 < r < park["r"][1] + 2.0:
                    return True
        pond = plan["pond"]
        py = math.radians(pond["yaw"])
        dx, dz = x - pond["at"][0], z - pond["at"][1]
        u = dx * math.cos(-py) - dz * math.sin(-py)
        v = dx * math.sin(-py) + dz * math.cos(-py)
        if (u / (pond["size"][0] * 0.5 + 3.0 + margin)) ** 2 + (v / (pond["size"][1] * 0.5 + 3.0 + margin)) ** 2 < 1.0:
            return True
        gb = plan["garage_bridge"]
        if seg_dist(p, gb["from"], gb["to"]) < gb["width"] * 0.5 + 3.0 + margin:
            return True
        if any(math.dist(p, q) < 10.0 + margin for q in self.points):
            return True
        route_gap = 1.5 if veg else 6.0
        if any(poly_dist(p, route) < route_gap + margin for route in self.routes):
            return True
        if any(math.hypot(x - tx, z - tz) < tr + margin for tx, tz, tr in self.taken):
            return True
        if any(x0 - margin < x < x1 + margin and z0 - margin < z < z1 + margin for x0, z0, x1, z1 in self.rects):
            return True
        if any(poly_dist(p, pts) < gap + margin for pts, gap in self.corridors):
            return True
        return False

    # ---------------------------------------------------------- запись

    def put(self, kit: str, x: float, z: float, yaw: float = 0.0, s: float = 1.0, dy: float = 0.0,
            tint: int = -1, roll: float = 0.0, cover: bool = False) -> None:
        tail = [round(s, 2), round(dy, 2), tint, round(roll, 1)]
        defaults = [1.0, 0.0, -1, 0.0]
        while tail and tail[-1] == defaults[len(tail) - 1]:
            tail.pop()
        self.items.append([kit, round(x, 2), round(z, 2), round(yaw % 360.0, 1)] + tail)
        if cover:
            self.add_cover(x, z)

    def add_cover(self, x: float, z: float) -> None:
        self.cover.append([round(x, 1), round(z, 1)])
        self.near_cover.add((x, z))

    def story(self, label: str, at, find_at=None, height: float = 6.0) -> None:
        self.stories.append({"label": label, "at": [round(at[0], 1), round(at[1], 1)], "height": height})
        if find_at is not None:
            self.put("find", find_at[0], find_at[1], self.rng.uniform(0.0, 360.0))

    def reserve(self, x: float, z: float, r: float) -> None:
        self.taken.append((x, z, r))

    def car(self, x: float, z: float, yaw: float, state: str = "") -> None:
        """Брошенная машина: обычная, сгоревшая (burnt), на боку (side) или на крыше (roof)."""
        tint = BURNT if state == "burnt" else self.rng.randrange(len(CAR_TINTS))
        roll = {"side": 90.0, "roof": 180.0}.get(state, 0.0)
        self.put("car", x, z, yaw, tint=tint, roll=roll, cover=True)

    def bush(self, x: float, z: float, s: float) -> None:
        self.put("bush", x, z, self.rng.uniform(0.0, 360.0), s)

    def weed_patch(self, x: float, z: float, radius: float, density: float = 0.7) -> None:
        count = max(4, int(radius * radius * density))
        self.weeds.append([round(x, 1), round(z, 1), round(radius, 1), count, self.rng.randrange(1 << 30)])

    # ---------------------------------------------------------- районы

    def construction(self) -> None:
        """Стройка второй очереди: забор из профнастила с воротами к дороге и проломом с запада, котлован
        с пандусом и торчащими сваями, отвалы, бытовки в два яруса, материалы. Кран — постройка в сцене."""
        cx, cz = SITE_CENTER
        sx, sz = SITE_SIZE
        x0, x1, z0, z1 = cx - sx / 2, cx + sx / 2, cz - sz / 2, cz + sz / 2
        gate = (25.0, 37.0)
        breach = (-294.0, -290.0)

        def run(a, b, skip=None, axis=0):
            n = max(1, round(math.dist(a, b) / 3.0))
            for i in range(n):
                t = (i + 0.5) / n
                p = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
                if skip and skip[0] < p[axis] < skip[1]:
                    continue
                self.put("fence", p[0], p[1], yaw_along(b[0] - a[0], b[1] - a[1]))

        run((x0, z1), (x1, z1), gate, 0)      # юг, к кольцевой дороге: ворота
        run((x0, z0), (x1, z0))               # север, к лесу
        run((x0, z0), (x0, z1), breach, 1)    # запад: пролом
        run((x1, z0), (x1, z1))               # восток
        for q in ((x0, cz), (x1, cz), (cx, z0), (cx - 40.0, z1), (cx + 40.0, z1)):
            self.add_cover(*q)
        # котлован 54×22, глубина 4,5 м, откосы 4 м, пандус с востока
        pit = [48.0, -291.0, 54.0, 22.0, 0.0, 4.5, 4.0, 18.0, 7.0]
        self.earth["pits"].append(pit)
        for i, x in enumerate(range(28, 53, 6)):
            for j, z in enumerate((-297.0, -291.0, -285.0)):
                if (i + j) % 4 != 3:
                    self.put("stub", x, z, 0.0, cover=True)
        self.earth["mounds"] += [[-12.0, -302.0, 8.0, 5.0, 10.0, 3.2], [88.0, -303.0, 5.0, 4.0, 0.0, 2.0],
                                 [-18.0, -279.0, 4.5, 3.5, 30.0, 1.8]]
        for q in ((-12.0, -302.0), (88.0, -303.0), (-18.0, -279.0)):
            self.add_cover(*q)
        for x in (-27.0, -20.8):
            for dy in (0.0, 2.62):
                self.put("cabin", x, -271.0, 90.0, dy=dy, cover=True)
        self.put("booth", -13.0, -270.5, 180.0, cover=True)
        for dy in (0.0, 0.19, 0.38, 0.57):
            self.put("slab", 60.0, -271.0, 90.0 + self.rng.uniform(-2.0, 2.0), dy=dy, cover=True)
        for dy in (0.0, 0.19, 0.38):
            self.put("slab", 69.0, -275.0, 80.0, dy=dy)
        self.put("pallets", 82.0, -272.0, 0.0, cover=True)
        self.put("pallets", 84.5, -273.5, 10.0)
        self.put("rebar", 96.0, -280.0, 0.0)
        self.put("rebar", 96.6, -280.2, 3.0, dy=0.3)
        self.put("pipes", 99.0, -300.0, 0.0, cover=True)
        self.put("reel", 6.0, -273.0, 0.0, cover=True)
        self.put("reel", 9.5, -272.5, 15.0)
        for wx, wz, wr in ((-30.0, -308.0, 4.0), (100.0, -310.0, 3.5), (-30.0, -280.0, 3.0), (60.0, -310.0, 4.5)):
            self.weed_patch(wx, wz, wr)
        self.story("Стройка второй очереди", SITE_CENTER, (-22.0, -275.0), 12.0)
        self.rects.append((x0 - 2.0, z0 - 2.0, x1 + 2.0, z1 + 2.0))

    def power_line(self) -> None:
        for x, z in POWER_TOWERS:
            self.reserve(x, z, 8.0)
            self.add_cover(x, z)

    def heat_main(self) -> dict:
        """Теплотрасса: трубы на опорах на 1 м над землёй (под ними можно проползти), над дорогой и
        пожарным проездом — П-образно на 5,6 м, через трубы — два мостика-перелаза."""
        pts = HEAT_MAIN
        total = path_length(pts)
        high = []
        s = 0.0
        while s <= total:
            p, _ = along(pts, s)
            if math.hypot(*p) < 126.0 or any(poly_dist(p, rp) < w * 0.5 + 2.5 for rp, w in self.roads):
                if high and s - high[-1][1] <= 1.0:
                    high[-1][1] = s
                else:
                    high.append([s, s])
            s += 0.5
        portals = [[round(max(0.0, a - 1.0), 1), round(min(total, b + 1.0), 1)] for a, b in high]
        # перелазы — на длинном отрезке у парковки, на трети и двух третях
        seg_start = path_length(pts[:3])
        seg_len = math.dist(pts[2], pts[3])
        stiles = [round(seg_start + seg_len / 3.0, 1), round(seg_start + seg_len * 2.0 / 3.0, 1)]
        self.corridors.append((pts, 5.0))
        s = 8.0
        while s < total - 8.0:
            p, d = along(pts, s)
            side = self.rng.choice((-1.0, 1.0)) * 3.2
            q = (p[0] - d[1] * side, p[1] + d[0] * side)
            if not self.blocked(q, 1.0, veg=True) or math.hypot(*q) > 140.0:
                self.weed_patch(q[0], q[1], self.rng.uniform(1.6, 2.6), 1.0)
            s += self.rng.uniform(14.0, 26.0)
        for i in range(0, int(total), 20):
            p, _ = along(pts, float(i))
            self.add_cover(*p)
        self.story("Теплотрасса", along(pts, seg_start + seg_len * 0.5)[0], None, 7.0)
        return {"points": [list(p) for p in pts], "portals": portals, "stiles": stiles, "low": 1.05, "high": 5.6}

    def east(self) -> None:
        """Гаражи-ракушки двумя рядами, контейнерная площадка, штабеля труб у котельной, баки."""
        for row, (z, yaw) in enumerate(((44.0, 0.0), (66.0, 180.0))):
            for i in range(11):
                x = 313.6 + i * 3.3
                kit = "garage_open" if (row, i) in ((0, 4), (1, 8)) else "garage"
                self.put(kit, x, z, yaw, cover=True)
        self.put("find", 326.8, 43.0, 30.0)
        self.car(331.0, 55.5, 95.0)
        self.put("dumpster", 352.0, 55.0, 0.0, cover=True)
        self.rects.append((309.0, 38.0, 352.0, 72.0))
        self.story("Гаражи", (330.0, 55.0), None, 6.0)
        stack = {(0, 0): 2, (1, 0): 1, (2, 0): 2, (3, 0): 1, (5, 0): 1, (0, 1): 1, (1, 1): 1, (3, 1): 2, (4, 1): 1, (5, 1): 2}
        for (col, row), height in stack.items():
            x = (335.0, 337.5, 350.0, 352.5, 365.0, 367.5)[col]
            z = (-55.0, -35.0)[row]
            for level in range(height):
                self.put("container40", x, z, self.rng.uniform(-1.5, 1.5), dy=level * 2.6, cover=True)
        self.put("container20", 359.0, -45.0, 62.0, cover=True)
        self.put("find", 358.0, -48.5, 0.0)
        self.rects.append((330.0, -64.0, 372.0, -26.0))
        self.story("Контейнерная площадка", (351.0, -45.0), None, 7.0)
        self.put("pipes", 320.0, -100.0, 90.0, cover=True)
        self.put("pipes", 333.0, -96.0, 80.0, cover=True)
        self.reserve(326.0, -98.0, 9.0)
        for x, z, yaw in ((284.0, 258.0, 90.0), (284.0, 260.0, 90.0), (-262.0, -221.0, 0.0), (-259.8, -221.0, 0.0),
                          (-199.0, 283.0, 0.0), (272.0, -128.0, 0.0)):
            self.put("dumpster", x, z, yaw, cover=True)
            self.reserve(x, z, 4.0)

    def west(self) -> None:
        """Змейка дорожных блоков у КПП, колея через поле, брошенная колонна, воронка со сгоревшей машиной."""
        # змейка — на подъезде к КПП с запада (с востока за КПП — мост через речку)
        for i, x in enumerate((-410.0, -403.0, -396.0, -389.0)):
            road_z = -30.0 + 8.0 * (x + 470.0) / 170.0
            c = road_z - 2.5 if i % 2 == 0 else road_z + 2.5
            for dz in (-1.5, 1.5):
                self.put("jersey", x, c + dz, 0.0, cover=True)
        self.story("Змейка у КПП", (-400.0, -27.0), None, 4.0)
        ruts = RUT_LINE
        self.ruts = [offset_line(ruts, -0.9), offset_line(ruts, 0.9)]
        convoy = ruts[CONVOY_FROM:CONVOY_FROM + 3]
        kinds = ["truck", "truck", "bus_wreck", "car", "car", "truck", "car", "car"]
        states = ["", "burnt", "", "", "burnt", "", "roof", ""]
        for i, (kind, state) in enumerate(zip(kinds, states)):
            p, d = along(convoy, 6.0 + i * 14.5)
            yaw = yaw_along(*d) + self.rng.uniform(-12.0, 12.0)
            side = self.rng.uniform(-1.2, 1.2)
            if state == "roof":
                side = 6.0
            x, z = p[0] - d[1] * side, p[1] + d[0] * side
            if kind == "car":
                self.car(x, z, yaw, state)
            else:
                self.put(kind, x, z, yaw, tint=BURNT if state == "burnt" else -1, cover=True)
            self.reserve(x, z, 9.0)
            if kind == "bus_wreck":
                for k in range(3):
                    self.put("suitcase", x + d[1] * (2.4 + k * 0.7), z - d[0] * (2.4 + k * 0.7) + k * 0.4,
                             self.rng.uniform(0.0, 360.0), roll=self.rng.choice((0.0, 90.0)))
                self.put("find", x + d[1] * 3.6, z - d[0] * 3.6, 20.0)
        self.story("Брошенная колонна", along(convoy, 55.0)[0], None, 8.0)
        self.earth["craters"].append([CRATER[0], CRATER[1], 7.0, 1.8, 0.6])
        self.car(CRATER[0] + 7.5, CRATER[1] - 5.0, 35.0, "burnt")
        self.story("Воронка", CRATER, (CRATER[0] + 4.0, CRATER[1] - 8.0), 5.0)
        self.reserve(CRATER[0], CRATER[1], 13.0)
        for k in range(len(ruts) - 1):
            p = ((ruts[k][0] + ruts[k + 1][0]) / 2.0, (ruts[k][1] + ruts[k + 1][1]) / 2.0)
            self.put("puddle", p[0] + 0.9, p[1], 0.0, self.rng.uniform(1.4, 2.4), dy=0.04)

    def south(self) -> None:
        """Кювет вдоль трассы, щиты, упавший щит, авария фуры, остановка, старый пост из мешков у съезда."""
        for xa, xb in DITCH_PIECES:
            self.earth["ditches"].append({"points": [[xa, DITCH_Z], [xb, DITCH_Z]], "width": 6.0, "depth": 1.0})
            x = xa + 10.0
            while x < xb - 10.0:
                self.weed_patch(x, DITCH_Z + self.rng.uniform(-1.5, 1.5), self.rng.uniform(2.0, 3.5), 0.9)
                x += self.rng.uniform(18.0, 34.0)
        for x in (-320.0, -95.0, 90.0, 330.0):
            self.put("billboard", x, 288.0, 0.0)
        for x in (-230.0, 140.0, 360.0):
            self.put("billboard", x, 342.0, 180.0)
        self.put("billboard_fallen", -262.0, 288.0, 10.0, cover=True)
        self.story("Упавший щит", (-262.0, 288.0), (-257.0, 285.0), 5.0)
        cx, cz = CRASH
        self.put("truck_cab", cx - 11.0, cz, 62.0, cover=True)
        self.put("trailer", cx + 1.0, cz - 0.5, 100.0, roll=-6.0, cover=True)
        self.car(cx + 13.0, cz + 4.0, 30.0, "burnt")
        self.story("Авария на трассе", CRASH, (cx - 16.0, cz - 4.0), 6.0)
        self.put("bus_stop", 40.0, 291.0, 0.0, cover=True)
        px, pz = SANDBAG_POST
        for theta in (10.0, 40.0, 70.0, 100.0, 130.0, 160.0):
            q = polar(theta, 3.4)
            self.put("sandbags", px + q[0], pz + q[1], yaw_along(-math.sin(math.radians(theta)), math.cos(math.radians(theta))),
                     cover=True)
        self.put("jersey", px - 7.0, pz - 4.0, 20.0, cover=True)
        self.put("jersey", px + 8.0, pz - 4.0, -20.0, cover=True)
        self.story("Старый пост у съезда", SANDBAG_POST, (px + 0.6, pz + 1.0), 4.5)
        self.reserve(px, pz, 11.0)

    def camp(self) -> None:
        """Стоянка у костра в кустах между АЗС и водоёмом."""
        x, z = CAMP
        self.put("tent", x - 1.0, z - 1.0, 30.0, cover=True)
        self.put("fire_ring", x + 3.5, z + 2.5, 0.0)
        self.put("log", x + 5.5, z + 1.0, 80.0)
        self.put("log", x + 2.0, z + 5.5, 10.0)
        self.put("cart", x - 4.0, z + 4.0, 50.0)
        self.story("Стоянка у костра", CAMP, (x - 2.5, z - 3.0), 4.0)
        for k in range(10):
            a = 120.0 + k * 26.0
            q = polar(a, self.rng.uniform(7.0, 9.5))
            self.bush(x + q[0], z + q[1], self.rng.uniform(1.6, 2.8))
        self.weed_patch(x, z, 8.0, 0.4)
        self.reserve(x, z, 11.0)

    # ---------------------------------------------------------- россыпь

    def nearest_road(self, p):
        best = (1e9, None, 0.0)
        for pts, w in self.roads:
            for a, b in zip(pts, pts[1:]):
                d = seg_dist(p, a, b)
                if d < best[0]:
                    best = (d, (b[0] - a[0], b[1] - a[1]), w)
        return best

    def candidates(self, step: float):
        b = self.plan["bounds"]
        pts = [(x + self.rng.uniform(-step * 0.4, step * 0.4), z + self.rng.uniform(-step * 0.4, step * 0.4))
               for x in range(int(b[0]), int(b[2]), int(step)) for z in range(int(b[1]), int(b[3]), int(step))]
        self.rng.shuffle(pts)
        return pts

    def place_cluster(self, x: float, z: float, kind: str | None = None, yaw: float | None = None, state: str | None = None) -> None:
        """Одно укрытие: у дороги — брошенная машина или дорожные блоки, в поле — блоки ФБС, плиты, поддоны,
        катушки, сгоревшая машина, мешки, баки или трубы. kind / yaw / state — задать руками (ритм подходов)."""
        p = (x, z)
        rng = self.rng
        d, direction, width = self.nearest_road(p)
        if kind is None:
            if d < width * 0.5 + 14.0:
                kind = "roadside_car" if rng.random() < 0.55 else "jerseys"
            else:
                near_building = any(math.dist(p, q) < 70.0 for q in self.building_spots)
                kind = rng.choices(("fbs", "slab", "pallets", "reel", "wreck", "sandbags", "dumpster", "pipes"),
                                   (28, 14, 14, 10, 14, 5, 7 if near_building else 0, 4))[0]
        road_yaw = yaw_along(*direction) + rng.choice((0.0, 180.0))
        if yaw is None:
            yaw = road_yaw + rng.uniform(-25.0, 25.0) if kind in ("roadside_car", "jerseys") else rng.uniform(0.0, 360.0)
        ux, uz = math.sin(math.radians(yaw)), math.cos(math.radians(yaw))
        if kind == "roadside_car":
            self.car(x, z, yaw, state if state is not None else rng.choices(("", "burnt", "side", "roof"), (60, 22, 10, 8))[0])
            if rng.random() < 0.3:
                self.put("suitcase", x + rng.uniform(-3.0, 3.0), z + rng.uniform(-3.0, 3.0), rng.uniform(0.0, 360.0))
        elif kind == "jerseys":
            self.put("jersey", x, z, yaw, cover=True)
            self.put("jersey", x + rng.uniform(1.5, 3.0), z + rng.uniform(1.5, 3.0), yaw + rng.uniform(40.0, 80.0))
        elif kind == "fbs":
            self.put("fbs", x - uz * 0.31, z + ux * 0.31, yaw, cover=True)
            self.put("fbs", x + uz * 0.31, z - ux * 0.31, yaw)
            self.put("fbs", x, z, yaw + rng.uniform(-8.0, 8.0), dy=0.6)
            if rng.random() < 0.5:
                self.put("fbs", x + ux * 2.8 + uz * 1.2, z + uz * 2.8 - ux * 1.2, yaw + rng.uniform(60.0, 120.0))
        elif kind == "slab":
            for k in range(rng.randint(3, 5)):
                self.put("slab", x, z, yaw + rng.uniform(-4.0, 4.0), dy=k * 0.19, cover=k == 0)
        elif kind == "pallets":
            self.put("pallets", x, z, yaw, cover=True)
            self.put("pallets", x + uz * 1.3, z - ux * 1.3, yaw + rng.uniform(-10.0, 10.0))
            if rng.random() < 0.5:
                self.put("reel", x + ux * 2.6, z + uz * 2.6, yaw + 90.0)
        elif kind == "reel":
            self.put("reel", x, z, yaw, cover=True)
            if rng.random() < 0.5:
                self.put("reel", x + ux * 2.4, z + uz * 2.4, yaw + rng.uniform(-30.0, 30.0))
        elif kind == "wreck":
            self.car(x, z, yaw, state if state is not None else rng.choices(("", "burnt", "side", "roof"), (35, 45, 10, 10))[0])
        elif kind == "sandbags":
            for k in range(3):
                self.put("sandbags", x + ux * (k - 1) * 1.7, z + uz * (k - 1) * 1.7, yaw, cover=k == 1)
        elif kind == "dumpster":
            self.put("dumpster", x, z, yaw, cover=True)
            self.put("dumpster", x + uz * 1.5, z - ux * 1.5, yaw + rng.uniform(-6.0, 6.0))
        else:
            self.put("pipes", x, z, yaw, cover=True)

    def route_rhythm(self) -> None:
        """Укрытия, которые закрывают длинные открытые куски на подходах A–D (замер — проверка mall_study,
        «открытый кусок не длиннее 60 м»): у перехода через трассу, по главной аллее парковки, в поле у
        КПП, у начала восточного и северного подходов."""
        for kind, x, z, yaw, state in ROUTE_COVER:
            self.place_cluster(x, z, kind, yaw, state)
            self.reserve(x, z, 6.0)
        for x, z, rx, rz, h in ROUTE_MOUNDS:
            self.earth["mounds"].append([x, z, rx, rz, 0.0, h])
            self.add_cover(x, z)
            self.reserve(x, z, max(rx, rz) + 2.0)

    def _rect_dist(self, p, b) -> float:
        y = math.radians(b["yaw"])
        dx, dz = p[0] - b["at"][0], p[1] - b["at"][1]
        u = abs(dx * math.cos(y) - dz * math.sin(y)) - b["size"][0] * 0.5
        v = abs(dx * math.sin(y) + dz * math.cos(y)) - b["size"][1] * 0.5
        return math.hypot(max(u, 0.0), max(v, 0.0))

    def covered(self, p) -> bool:
        """Есть ли укрытие ближе 15 м — как считает проверка mall_study; машины на парковках и стенки
        террас и двора (их ставит MallLandscape) — по их рядам и радиусам."""
        if math.hypot(*p) < 115.0 or self.near_cover.within(p, 15.0):
            return True
        if any(b["region"] != "Outside" and self._rect_dist(p, b) < 15.0 for b in self.plan["buildings"]):
            return True
        a, r = ang(p), math.hypot(*p)
        for park in self.plan["parkings"]:
            rows = park["rows"]["a"]
            if in_arc(a, *rows) and park["r"][0] + 6.0 <= r <= park["r"][1] - 4.0:
                return True
        t = self.plan["terraces"]
        if in_arc(a, *t["a"]) and any(abs(r - w) < 12.0 for w in t["walls"]):
            return True
        yd = self.plan["yard"]
        return in_arc(a, *yd["a"]) and any(abs(r - w) < 12.0 for w in yd["r"])

    def fill_route_gaps(self) -> int:
        """Ритм подходов: идём по каждому маршруту проверки, и если впереди больше 36 м без укрытия ближе
        15 м — ставим укрытие сбоку, в 8–12,5 м от тропы (сама тропа свободна)."""
        added = 0
        for route in self.routes:
            run = 0.0
            for a, b in zip(route, route[1:]):
                seg = math.dist(a, b)
                if seg < 0.01:
                    continue
                dx, dz = (b[0] - a[0]) / seg, (b[1] - a[1]) / seg
                steps = max(1, math.ceil(seg / 2.0))
                for k in range(steps):
                    p = (a[0] + (b[0] - a[0]) * k / steps, a[1] + (b[1] - a[1]) * k / steps)
                    if self.covered(p):
                        run = 0.0
                        continue
                    run += seg / steps
                    if run < 36.0:
                        continue
                    for off in (10.0, -10.0, 12.5, -12.5, 8.0, -8.0):
                        q = (p[0] - dz * off, p[1] + dx * off)
                        if not self.blocked(q, 1.0):
                            self.place_cluster(*q)
                            self.reserve(q[0], q[1], 4.0)
                            added += 1
                            run = 0.0
                            break
        return added

    def cover_clusters(self) -> int:
        """Укрытия с шагом 34–42 м: у дорог — брошенные машины и дорожные блоки, в поле — блоки ФБС, плиты,
        поддоны, катушки, баки, мешки; у трети — кусты и бурьян рядом."""
        placed = Near()
        count = 0
        for p in self.candidates(7.0):
            spacing = 34.0 if math.hypot(*p) < 300.0 else 42.0
            if placed.within(p, spacing) or self.near_cover.within(p, spacing * 0.6):
                continue
            if self.blocked(p, 3.0):
                continue
            placed.add(p)
            count += 1
            x, z = p
            self.place_cluster(x, z)
            if self.rng.random() < 0.3:
                for _ in range(self.rng.randint(2, 3)):
                    q = polar(self.rng.uniform(0.0, 360.0), self.rng.uniform(4.0, 7.0))
                    if not self.blocked((x + q[0], z + q[1]), 0.5, veg=True):
                        self.bush(x + q[0], z + q[1], self.rng.uniform(1.2, 2.2))
            if self.rng.random() < 0.4:
                self.weed_patch(x + self.rng.uniform(-2.0, 2.0), z + self.rng.uniform(-2.0, 2.0), self.rng.uniform(3.0, 5.0))
        return count

    def field_mounds(self, count: int) -> None:
        """Земляные кучи в полях — укрытие самим рельефом."""
        placed = 0
        mounds = Near()
        for p in self.candidates(11.0):
            if placed >= count:
                break
            if mounds.within(p, 90.0) or self.blocked(p, 12.0):
                continue
            mounds.add(p)
            rx, rz = self.rng.uniform(5.0, 8.0), self.rng.uniform(4.0, 6.0)
            self.earth["mounds"].append([round(p[0], 1), round(p[1], 1), round(rx, 1), round(rz, 1),
                                         round(self.rng.uniform(0.0, 180.0), 1), round(self.rng.uniform(1.2, 2.2), 1)])
            self.add_cover(*p)
            self.reserve(p[0], p[1], max(rx, rz) + 2.0)
            self.weed_patch(p[0], p[1], max(rx, rz) * 0.8, 0.5)
            placed += 1

    def vegetation(self) -> None:
        rng = self.rng
        # кусты полосами вдоль кольцевой дороги с обеих сторон — с разрывами
        loop = self.plan["mall"]["loop_r"]
        for radius in (loop + 9.5, loop - 9.5):
            steps = int(2.0 * math.pi * radius / 7.0)
            for i in range(steps):
                if (i // 7) % 3 == 0:
                    continue
                p = polar(360.0 * i / steps + rng.uniform(-0.4, 0.4), radius + rng.uniform(-1.0, 1.0))
                if not self.blocked(p, 1.0, veg=True):
                    self.bush(p[0], p[1], rng.uniform(1.4, 2.6))
        # вдоль забора участка изнутри
        poly = self.plan["boundary"]
        for a, b in zip(poly, poly[1:] + poly[:1]):
            dx, dz = b[0] - a[0], b[1] - a[1]
            d = math.hypot(dx, dz)
            nx, nz = -dz / d, dx / d
            mid = ((a[0] + b[0]) / 2.0 + nx, (a[1] + b[1]) / 2.0 + nz)
            if not in_poly(mid, poly):
                nx, nz = -nx, -nz
            for i in range(int(d / 6.0)):
                if (i // 6) % 3 == 1:
                    continue
                t = (i + 0.5) / int(d / 6.0)
                p = (a[0] + dx * t + nx * 7.5, a[1] + dz * t + nz * 7.5)
                if not self.blocked(p, 0.5, veg=True):
                    self.bush(p[0], p[1], rng.uniform(1.6, 3.0))
        # кусты кучками и молодые берёзы рощицами по пустырям
        for groups, count, radius, kit in ((70, (3, 7), 6.0, "bush"), (45, (3, 9), 8.0, "sapling")):
            made = 0
            for p in self.candidates(13.0):
                if made >= groups:
                    break
                if self.blocked(p, 4.0, veg=True):
                    continue
                made += 1
                for _ in range(rng.randint(*count)):
                    q = polar(rng.uniform(0.0, 360.0), rng.uniform(0.0, radius))
                    x, z = p[0] + q[0], p[1] + q[1]
                    if self.blocked((x, z), 0.5, veg=True):
                        continue
                    if kit == "bush":
                        self.bush(x, z, rng.uniform(1.2, 2.8))
                    else:
                        self.put("sapling", x, z, rng.uniform(0.0, 360.0), rng.uniform(0.8, 1.6))
        # бурьян пятнами по пустырям и вдоль дорог
        made = 0
        for p in self.candidates(9.0):
            if made >= 260:
                break
            radius = rng.uniform(3.0, 9.0)
            if self.blocked(p, radius, veg=True):
                continue
            self.weed_patch(p[0], p[1], radius)
            made += 1
        for pts, w in self.roads:
            total = path_length(pts)
            s = rng.uniform(5.0, 20.0)
            while s < total:
                p, d = along(pts, s)
                side = rng.choice((-1.0, 1.0)) * (w * 0.5 + 3.0)
                q = (p[0] - d[1] * side, p[1] + d[0] * side)
                if not self.blocked(q, 2.5, veg=True):
                    self.weed_patch(q[0], q[1], 2.5, 0.9)
                s += rng.uniform(25.0, 45.0)

    def puddles(self) -> None:
        """Лужи: на парковках (асфальт просел) и у дорог."""
        rng = self.rng
        t = self.plan["terraces"]
        made = 0
        while made < 60:
            park = rng.choice(self.plan["parkings"])
            a = park["a"][0] + rng.uniform(0.0, (park["a"][1] - park["a"][0]) % 360.0)
            r = rng.uniform(park["r"][0] + 4.0, park["r"][1] - 4.0)
            if any(abs(r - w) < 5.0 for w in t["walls"]) and in_arc(a, t["a"][0] - 2.0, t["a"][1] + 2.0):
                continue
            if any(ang_gap(a, ra) < t["ramp_half_deg"] + 2.0 for ra in t["ramps"]):
                continue
            p = polar(a, r)
            if any(math.dist(p, q) < 6.0 for q in self.points):
                continue
            self.put("puddle", p[0], p[1], 0.0, rng.uniform(1.6, 4.5), dy=0.03)
            made += 1


def make_filler(plan: dict) -> tuple[dict, dict]:
    """Наполнение черновика и сводка для печати."""
    lay = Layout(plan)
    lay.power_line()
    lay.construction()
    heat = lay.heat_main()
    lay.east()
    lay.west()
    lay.south()
    lay.camp()
    lay.route_rhythm()
    clusters = lay.cover_clusters()
    gaps = lay.fill_route_gaps()
    lay.field_mounds(10)
    lay.vegetation()
    lay.puddles()
    kits: dict[str, int] = {}
    for item in lay.items:
        kits[item[0]] = kits.get(item[0], 0) + 1
    filler = {
        "tints": TINTS,
        "items": lay.items,
        "weeds": lay.weeds,
        "earth": lay.earth,
        "lines": {"power": {"towers": [list(p) for p in POWER_TOWERS], "end": list(POWER_END)},
                  "heat": heat, "ruts": lay.ruts},
        "stories": lay.stories,
        "cover": lay.cover,
    }
    stats = {"items": len(lay.items), "cover_clusters": clusters, "route_gaps_filled": gaps, "weed_patches": len(lay.weeds),
             "weed_tufts": sum(w[3] for w in lay.weeds), "stories": len(lay.stories), "kits": kits}
    return filler, stats
