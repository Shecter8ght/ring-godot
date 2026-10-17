"""Сценки и поля черновика территории ТЦ — чтобы было не скучно (владелец, 2026-10-17: «всё нравится, но пока
выглядит слишком скучно»; по разбору игр — docs/design/mall_density_research.md):

  грунтовки   — дороги из грунта с двумя колеями, лужами в них и травой посередине: просека под ЛЭП к
                водоёму и АЗС, колея КПП — брод — автостанция, от кольцевой к гаражам и вдоль газа к
                техкомплексу, вдоль трассы к упавшему щиту (как у Road to Vostok);
  машины      — на кольцевой и въездах брошенные машины, завалы по 2–3, автобус (Тарков, Road to Vostok);
  сценки      — сбитый вертолёт ЧВК под скальной грядой, вышка сотовой связи (ориентир) за кафе;
  поля        — высокая трава (мягкое укрытие по пояс — Hunt, ABI) пятнами и вдоль речки, пшеница
                прямоугольными полями с технологическими колеями и брошенным трактором.

Координаты игры: X — восток, Z — юг. Наборы — src/blockout/mall_filler.gd.
"""

from __future__ import annotations

import math

from mall_study_ground import ZONES
from mall_study_railway import make_railway

# грунтовки: точки игры; колея КПП — брод — автостанция берётся из наполнения (RUT_LINE)
TRACKS = [
    # просека под ЛЭП: от водоёма вдоль опор к сопке у леса, у западного конца — вниз к АЗС
    [(-250.0, -224.0), (-262.0, -250.0), (-250.0, -290.0), (-215.0, -326.0), (-140.0, -330.0), (-70.0, -332.0),
     (10.0, -331.0), (80.0, -330.0), (150.0, -322.0), (150.0, -290.0), (140.0, -246.0), (128.0, -222.0)],
    # от кольцевой к гаражам, дальше на север вдоль газовой трубы к техкомплексу
    [(249.4, 53.0), (288.0, 48.0), (288.0, 0.0), (288.0, -30.0), (292.0, -70.0)],
    # вдоль трассы от съезда к автостанции на запад, к упавшему щиту и речке
    [(-212.0, 284.0), (-240.0, 281.0), (-275.0, 280.0), (-300.0, 283.0)],
]
TRACK_WIDTH = 3.6
WRECK_STEP = (32.0, 68.0)  # шаг брошенных машин вдоль дорог, м
HELI = (285.0, 165.0, 30.0)  # сбитый вертолёт: x, z, поворот
CELL_TOWER = (350.0, 230.0)
# поля пшеницы: центр, ширина (вдоль рядов), глубина, поворот°
WHEAT = [(-395.0, 40.0, 70.0, 44.0, 8.0), (270.0, -270.0, 70.0, 40.0, -20.0), (-372.0, 255.0, 50.0, 40.0, 5.0)]
# высокая трава пятнами: центр, полуоси, поворот°
MEADOWS = [(110.0, 275.0, 70.0, 16.0, 0.0), (-90.0, 282.0, 45.0, 12.0, 0.0), (300.0, 140.0, 40.0, 26.0, 30.0),
           (-272.0, -115.0, 18.0, 30.0, 0.0), (360.0, 215.0, 25.0, 18.0, 0.0), (-350.0, -150.0, 30.0, 40.0, 0.0),
           (60.0, -300.0, 40.0, 12.0, 0.0), (-60.0, 240.0, 30.0, 10.0, 0.0)]
GRASS_STEP = 2.2
# трава и колосья не растут сквозь предметы: радиус вокруг набора, м (остальные — 2,2)
CLEAR_RADIUS = {"car": 3.2, "truck": 5.0, "truck_cab": 4.5, "trailer": 7.5, "bus_wreck": 7.0, "container40": 7.0,
                "container20": 4.0, "heli_wreck": 7.5, "heli_tail": 5.0, "house_small": 6.0, "shed": 3.4, "greenhouse": 4.0,
                "tractor": 3.5, "cabin": 4.0, "garage": 4.0, "garage_open": 4.0, "ktp": 2.8, "pipes": 5.0, "slab": 4.0}
SOFT_KITS = {"tall_grass", "tall_grass_dry", "wheat", "weed", "puddle", "find", "manhole", "bush", "sapling", "reeds"}
# дачи и постройки посреди пшеницы — нет: поле обходит их с запасом
FARM_CLEAR = {"picket", "shed", "greenhouse", "house_small", "outhouse"}
WHEAT_ROW = 1.6
WHEAT_STEP = 1.8


def seg_dist(p, a, b) -> float:
    dx, dz = b[0] - a[0], b[1] - a[1]
    l2 = dx * dx + dz * dz
    t = 0.0 if l2 == 0.0 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dz) / l2))
    return math.hypot(p[0] - (a[0] + t * dx), p[1] - (a[1] + t * dz))


def poly_dist(p, pts) -> float:
    return min(seg_dist(p, a, b) for a, b in zip(pts, pts[1:]))


def resample(pts, step: float):
    out = []
    for a, b in zip(pts, pts[1:]):
        n = max(1, int(math.dist(a, b) / step))
        for i in range(n):
            t = i / n
            out.append([round(a[0] + (b[0] - a[0]) * t, 2), round(a[1] + (b[1] - a[1]) * t, 2)])
    out.append([round(pts[-1][0], 2), round(pts[-1][1], 2)])
    return out


def offset_line(pts, off: float):
    out = []
    for i, p in enumerate(pts):
        a = pts[max(0, i - 1)]
        b = pts[min(len(pts) - 1, i + 1)]
        dx, dz = b[0] - a[0], b[1] - a[1]
        d = math.hypot(dx, dz) or 1.0
        out.append([round(p[0] - dz / d * off, 2), round(p[1] + dx / d * off, 2)])
    return out


def in_poly(p, poly) -> bool:
    inside = False
    j = len(poly) - 1
    for i in range(len(poly)):
        (xi, zi), (xj, zj) = poly[i], poly[j]
        if (zi > p[1]) != (zj > p[1]) and p[0] < (xj - xi) * (p[1] - zi) / (zj - zi) + xi:
            inside = not inside
        j = i
    return inside


def yaw_along(dx: float, dz: float) -> float:
    return math.degrees(math.atan2(dx, dz))


def hash01(x: float, z: float, k: int = 0) -> float:
    """Стабильный «шум» без зависимостей: дыры и рваные края полей."""
    v = math.sin(x * 12.9898 + z * 78.233 + k * 37.719) * 43758.5453
    return v - math.floor(v)


def blob(x: float, z: float, scale: float) -> float:
    """Плавное пятно 0..1 из четырёх соседних значений hash01 — проплешины в траве."""
    gx, gz = x / scale, z / scale
    ix, iz = math.floor(gx), math.floor(gz)
    fx, fz = gx - ix, gz - iz
    fx, fz = fx * fx * (3 - 2 * fx), fz * fz * (3 - 2 * fz)
    a, b = hash01(ix, iz), hash01(ix + 1, iz)
    c, d = hash01(ix, iz + 1), hash01(ix + 1, iz + 1)
    return (a + (b - a) * fx) * (1 - fz) + (c + (d - c) * fx) * fz


class Scenery:
    def __init__(self, lay):
        self.lay = lay
        self.plan = lay.plan
        self.rng = lay.rng
        self.tracks: list[dict] = []
        self.fields: list[dict] = []
        self.counts: dict[str, int] = {}
        self.soil_extra: list[list] = []
        self._taken: dict | None = None
        self._items: dict | None = None
        self._wheat_mode = False

    def count(self, key: str, n: int = 1) -> None:
        self.counts[key] = self.counts.get(key, 0) + n

    # ---------------------------------------------------------- грунтовки (до укрытий: коридоры)

    def make_tracks(self, rut_line) -> None:
        rng = self.rng
        lines = [list(t) for t in TRACKS] + [list(rut_line)]
        for pts in lines:
            dense = resample(pts, 3.0)
            self.tracks.append({"points": dense, "width": TRACK_WIDTH})
            self.lay.corridors.append((dense, TRACK_WIDTH * 0.5 + 1.0))
            # колеи (их рисует наполнение, как колею у КПП) — кроме самой колеи КПП, у неё свои
            if pts is not lines[-1]:
                self.lay.ruts.append(offset_line(dense, -0.85))
                self.lay.ruts.append(offset_line(dense, 0.85))
            # лужи в колеях и трава посередине
            total = sum(math.dist(a, b) for a, b in zip(dense, dense[1:]))
            s = rng.uniform(5.0, 20.0)
            while s < total:
                p, d = self._along(dense, s)
                if rng.random() < 0.65:
                    side = rng.choice((-0.85, 0.85))
                    self.lay.put("puddle", p[0] - d[1] * side, p[1] + d[0] * side, yaw_along(*d), rng.uniform(1.1, 2.4), dy=0.03)
                    self.count("puddles")
                s += rng.uniform(18.0, 40.0)
            s = rng.uniform(2.0, 8.0)
            while s < total:
                p, _ = self._along(dense, s)
                self.lay.weeds.append([round(p[0], 1), round(p[1], 1), 0.45, 3, rng.randrange(1 << 30)])
                s += rng.uniform(6.0, 14.0)

    @staticmethod
    def _along(pts, s: float):
        for a, b in zip(pts, pts[1:]):
            d = math.dist(a, b)
            if s <= d:
                t = s / d if d else 0.0
                return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t), ((b[0] - a[0]) / (d or 1), (b[1] - a[1]) / (d or 1))
            s -= d
        a, b = pts[-2], pts[-1]
        d = math.dist(a, b) or 1.0
        return tuple(b), ((b[0] - a[0]) / d, (b[1] - a[1]) / d)

    # ---------------------------------------------------------- сценки (до укрытий: резерв)

    def heli(self) -> None:
        """Сбитый вертолёт ЧВК у подножия скальной гряды: корпус на боку, хвост отломан, лопасти
        разбросаны, гарь и воронка, ящики груза, находка."""
        rng = self.rng
        x, z, yaw = HELI
        lay = self.lay
        lay.put("heli_wreck", x, z, yaw, cover=True)
        ya = math.radians(yaw)
        fwd = (math.sin(ya), math.cos(ya))
        right = (-fwd[1], fwd[0])
        lay.put("heli_tail", x - fwd[0] * 14.0 + right[0] * 3.0, z - fwd[1] * 14.0 + right[1] * 3.0, yaw + 35.0, cover=True)
        for k in range(3):
            q = (x + rng.uniform(-16.0, 16.0), z + rng.uniform(-16.0, 16.0))
            lay.put("rotor_blade", q[0], q[1], rng.uniform(0.0, 360.0), dy=0.05)
        for k in range(4):
            q = (x + right[0] * (5.0 + k * 1.4) + rng.uniform(-1, 1), z + right[1] * (5.0 + k * 1.4) + rng.uniform(-1, 1))
            lay.put("pallets", q[0], q[1], rng.uniform(0.0, 360.0), cover=k == 0)
        lay.earth["craters"].append([round(x + fwd[0] * 8.0, 1), round(z + fwd[1] * 8.0, 1), 5.0, 1.2, 0.5])
        lay.story("Сбитый вертолёт ЧВК", (x, z), (x + right[0] * 4.0, z + right[1] * 4.0), 8.0)
        lay.reserve(x, z, 20.0)
        for p in ((x, z), (x - fwd[0] * 14.0, z - fwd[1] * 14.0)):
            lay.add_cover(*p)
        self.soil_extra.append([round(x, 1), round(z, 1), 15.0, 5])
        self.count("heli")

    def cell_tower(self) -> None:
        """Вышка сотовой связи 42 м за кафе: ориентир со всей карты, у подножия — сетка и аппаратная."""
        x, z = CELL_TOWER
        lay = self.lay
        lay.put("cell_tower", x, z, 15.0, cover=True)
        for a, b in (((-4.5, -4.5), (4.5, -4.5)), ((4.5, -4.5), (4.5, 4.5)), ((4.5, 4.5), (-4.5, 4.5)), ((-4.5, 4.5), (-4.5, -4.5))):
            n = 4
            for i in range(n):
                if (a, b) == ((-4.5, 4.5), (-4.5, -4.5)) and i == 1:
                    continue  # калитка
                t = (i + 0.5) / n
                px, pz = x + a[0] + (b[0] - a[0]) * t, z + a[1] + (b[1] - a[1]) * t
                lay.put("chainlink", px, pz, yaw_along(b[0] - a[0], b[1] - a[1]))
        lay.put("container20", x + 7.5, z + 1.0, 0.0, cover=True)
        lay.story("Вышка связи", (x, z), None, 10.0)
        lay.reserve(x, z, 12.0)
        self.count("cell_tower")

    # ---------------------------------------------------------- машины на дорогах

    def road_wrecks(self) -> None:
        """Брошенные машины на кольцевой и въездах: поодиночке в полосе, развёрнутые, завалы по 2–3;
        переходы, перекрёстки, мосты и тропы проверки свободны."""
        rng = self.rng
        plan = self.plan
        junctions = [j["at"] for j in plan.get("streets", {}).get("junctions", [])]
        crossings = [c["points"] for c in plan.get("crossings", [])]
        bridges = [b["at"] for b in plan.get("relief", {}).get("river", {}).get("bridges", [])]
        routes = self.lay.routes
        buses = 0
        for road in plan["roads"]:
            if road["id"] in ("car_wash_drive",):
                continue
            pts, w = road["points"], float(road["width"])
            total = sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))
            s = rng.uniform(10.0, 40.0)
            while s < total - 8.0:
                p, d = self._along(pts, s)
                s += rng.uniform(*WRECK_STEP)
                if rng.random() > 0.72:
                    continue
                if any(math.dist(p, j) < 20.0 for j in junctions) or any(poly_dist(p, c) < 12.0 for c in crossings):
                    continue
                if any(math.dist(p, b) < 22.0 for b in bridges) or any(poly_dist(p, r) < 9.0 for r in routes):
                    continue
                if any(abs(p[0] - b["at"][0]) < b["size"][0] / 2 + 8 and abs(p[1] - b["at"][1]) < b["size"][1] / 2 + 8
                       for b in plan["buildings"] if b["region"] != "Outside"):
                    continue
                # своя полоса — справа по ходу (ход машины — вдоль дороги в ту или другую сторону)
                sgn = rng.choice((1.0, -1.0))
                lane = w * 0.25 * sgn
                x, z = p[0] - d[1] * lane, p[1] + d[0] * lane
                heading = yaw_along(d[0] * sgn, d[1] * sgn)
                if road["id"] == "loop" and buses < 2 and rng.random() < 0.08:
                    self.lay.put("bus_wreck", x, z, heading + rng.uniform(-12.0, 12.0), tint=8 if rng.random() < 0.5 else -1, cover=True)
                    buses += 1
                    self.count("road_bus")
                    continue
                pile = rng.random() < 0.18
                for k in range(3 if pile else 1):
                    ox, oz = (rng.uniform(-3.5, 3.5), rng.uniform(-4.0, 4.0)) if pile else (0.0, 0.0)
                    state = rng.choices(("", "burnt", "side", "roof"), (55, 28, 10, 7))[0]
                    turn = rng.uniform(-60.0, 60.0) if (pile or rng.random() < 0.2) else rng.uniform(-10.0, 10.0)
                    self.lay.car(x + ox, z + oz, heading + turn, state)
                    self.count("road_cars")
                if rng.random() < 0.25:
                    self.lay.put("suitcase", x + rng.uniform(-3.0, 3.0), z + rng.uniform(-3.0, 3.0), rng.uniform(0.0, 360.0))

    # ---------------------------------------------------------- поля (после уплотнения: мягкие)

    def grass_ok(self, p) -> bool:
        """Можно ли траве: всё, что запрещено кустам, плюс лес и площадки. Занятые места наполнения —
        по своей сетке (их тысячи; полный перебор в blocked() на десятках тысяч травинок — медленно)."""
        if self._taken is None:
            self._taken = {}
            for tx, tz, tr in self.lay.taken:
                for i in range(int((tx - tr) // 16), int((tx + tr) // 16) + 1):
                    for j in range(int((tz - tr) // 16), int((tz + tr) // 16) + 1):
                        self._taken.setdefault((i, j), []).append((tx, tz, tr))
        for tx, tz, tr in self._taken.get((int(p[0] // 16), int(p[1] // 16)), ()):
            if math.hypot(p[0] - tx, p[1] - tz) < tr:
                return False
        saved = self.lay.taken
        self.lay.taken = []
        try:
            bad = self.lay.blocked(p, 0.3, veg=True)
        finally:
            self.lay.taken = saved
        if bad:
            return False
        if any(in_poly(p, f) for f in self.plan["forest"]):
            return False
        if self._items is None:
            self._items = {}
            for it in self.lay.items:
                if it[0] in SOFT_KITS:
                    continue
                r = CLEAR_RADIUS.get(it[0], 2.2) * (it[4] if len(it) > 4 and it[0].startswith("rock") else 1.0)
                if it[0] in FARM_CLEAR:
                    r = max(r, 11.0) if self._wheat_mode else r
                self._items.setdefault((int(it[1] // 16), int(it[2] // 16)), []).append((it[1], it[2], r))
        cx, cz = int(p[0] // 16), int(p[1] // 16)
        for i in (cx - 1, cx, cx + 1):
            for j in (cz - 1, cz, cz + 1):
                for x, z, r in self._items.get((i, j), ()):
                    if math.hypot(p[0] - x, p[1] - z) < r:
                        return False
        for kind, cx, cz, w, h, yaw, _ in ZONES:
            if abs(p[0] - cx) < w / 2 + 1.0 and abs(p[1] - cz) < h / 2 + 1.0:
                return False
        return True

    def meadows(self) -> None:
        rng = self.rng
        for cx, cz, rx, rz, yaw in MEADOWS:
            ya = math.radians(yaw)
            reach = max(rx, rz)
            x = cx - reach
            while x <= cx + reach:
                z = cz - reach
                while z <= cz + reach:
                    px, pz = x + rng.uniform(-0.7, 0.7), z + rng.uniform(-0.7, 0.7)
                    dx, dz = px - cx, pz - cz
                    u = dx * math.cos(ya) + dz * math.sin(ya)
                    v = -dx * math.sin(ya) + dz * math.cos(ya)
                    q = math.hypot(u / rx, v / rz)
                    # рваный край и проплешины
                    edge = q + (blob(px, pz, 9.0) - 0.5) * 0.45
                    if edge < 1.0 and blob(px + 400.0, pz, 14.0) > 0.22 and self.grass_ok((px, pz)):
                        self._grass(px, pz)
                    z += GRASS_STEP
                x += GRASS_STEP
        # вдоль речки по обоим берегам — полосами, не у переправ
        river = self.plan.get("relief", {}).get("river", {})
        if river:
            pts = river["points"]
            cross = [b["at"] for b in river.get("bridges", [])] + [f["at"] for f in river.get("fords", [])] + \
                    [c["at"] for c in river.get("culverts", [])]
            for a, b in zip(pts, pts[1:]):
                d = math.dist(a, b)
                nx, nz = (b[1] - a[1]) / d, -(b[0] - a[0]) / d
                s = 0.0
                while s < d:
                    t = s / d
                    c = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
                    if all(math.dist(c, q) > 20.0 for q in cross):
                        for side in (1.0, -1.0):
                            off = 11.0
                            while off < 22.0:
                                p = (c[0] + nx * side * off + rng.uniform(-0.7, 0.7), c[1] + nz * side * off + rng.uniform(-0.7, 0.7))
                                if blob(p[0], p[1], 12.0) > 0.45 and self.grass_ok(p):
                                    self._grass(*p)
                                off += GRASS_STEP
                    s += GRASS_STEP

    def _grass(self, x: float, z: float) -> None:
        rng = self.rng
        kit = "tall_grass_dry" if blob(x, z + 300.0, 20.0) > 0.6 else "tall_grass"
        self.lay.items.append([kit, round(x, 2), round(z, 2), round(rng.uniform(0.0, 360.0), 1), round(rng.uniform(0.8, 1.25), 2)])
        self.count(kit)

    def wheat(self) -> None:
        """Пшеница рядами, через 12 м — технологическая колея; посередине одного поля — трактор."""
        rng = self.rng
        self._wheat_mode = True
        self._items = None  # пересобрать с запасом вокруг дач
        for idx, (cx, cz, w, h, yaw) in enumerate(WHEAT):
            ya = math.radians(yaw)
            u = (math.cos(ya), math.sin(ya))
            v = (-u[1], u[0])
            if idx == 1:
                # трактор встал на технологической колее посреди поля — до колосьев, чтобы не росли сквозь него
                tx, tz = cx + u[0] * 6.0 + v[0] * (3.5 * WHEAT_ROW - h / 2), cz + u[1] * 6.0 + v[1] * (3.5 * WHEAT_ROW - h / 2)
                self.lay.put("tractor", tx, tz, yaw_along(*u), cover=True)
                self.lay.story("Брошенный трактор", (tx, tz), None, 5.0)
                self._items = None
            placed = 0
            b = -h / 2
            row = 0
            while b <= h / 2:
                if row % 8 not in (3, 4):  # колея трактора
                    a = -w / 2
                    while a <= w / 2:
                        jitter = rng.uniform(-0.1, 0.1)
                        px, pz = cx + u[0] * (a + jitter) + v[0] * b, cz + u[1] * (a + jitter) + v[1] * b
                        ragged = (abs(a) > w / 2 - 3.0 or abs(b) > h / 2 - 3.0) and hash01(px, pz, 3) < 0.4
                        if not ragged and blob(px, pz + 900.0, 10.0) > 0.12 and self.grass_ok((px, pz)):
                            # блоки по рядам поля — смыкаются в сплошной ковёр
                            self.lay.items.append(["wheat", round(px, 2), round(pz, 2), round((yaw_along(*u) + rng.uniform(-2.0, 2.0)) % 360.0, 1),
                                                   round(rng.uniform(0.96, 1.05), 2)])
                            placed += 1
                        a += WHEAT_STEP
                b += WHEAT_ROW
                row += 1
            if placed:
                self.fields.append({"kind": "field", "rect": [cx, cz, w + 2.0, h + 2.0, yaw]})
                self.count("wheat", placed)


def scenery_early(lay, rut_line) -> "Scenery":
    """До укрытий: грунтовки и железнодорожная ветка (коридоры), вертолёт и вышка (резерв мест)."""
    sc = Scenery(lay)
    sc.make_tracks(rut_line)
    # железнодорожная ветка — после грунтовок (переезд ищет, какую дорогу пересекает), до укрытий
    sc.rail = make_railway(lay, sc.tracks)
    sc.heli()
    sc.cell_tower()
    return sc


def scenery_late(sc: "Scenery") -> dict:
    """После уплотнения: машины на дорогах, высокая трава и пшеница."""
    sc.road_wrecks()
    sc.meadows()
    sc.wheat()
    return sc.counts
