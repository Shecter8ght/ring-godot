"""Уплотнение черновика территории ТЦ по «карте пустоты» (владелец, 2026-10-17: «если полетать над картой —
лысые участки, хочется уплотнить»; разбор игр — docs/design/mall_density_research.md).

Как работает: поле делится на клетки по 8 м; для каждой свободной клетки (не дорога, не площадка, не
вода, не здание, не лес) считается расстояние до ближайшего «вертикального» предмета — укрытия, куста,
дерева, постройки, стенки, утёса. Пока где-то пусто дальше TARGET_M, в самую пустую клетку ставится
группа по смыслу места:
  у дороги       — цепочка брошенных машин, ремонт дороги, трансформаторная будка (КТП) с сеткой,
                   мусорная площадка, ларьки;
  у речки        — дачные участки (штакетник, сарай, теплица, туалет, яблони), камыш, камни, деревья;
  у опушки       — штабели брёвен, охотничья вышка, куртина деревьев, развалины;
  в поле         — лесополоса с проходами (режет поле на «комнаты» 40–80 м), дачи, вал грунта,
                   тюки сена, развалины дома, огороженный ПО-2 пустырь со свалкой, куча шин и колец.
Группа — 3–7 предметов с понятной причиной (Smith/Worch), а не россыпь. Ещё — жёлтые газовые трубы на
опорах (их рисует MallStreets) и полоса рыжей травы над подземной теплотрассой.

Координаты игры: X — восток, Z — юг. Наборы — src/blockout/mall_filler.gd.
"""

from __future__ import annotations

import math

CELL = 8.0
TARGET_M = 22.0        # дальше этого от любого предмета — «лысое» место
MAX_FEATURES = 420
# что не держит пространство: плоское, мелкое и низкая растительность (сверху и с земли — точки, а не
# «стенки комнат»); их ставит наполнение, но пустоту они не закрывают
FLAT_KITS = {"puddle", "find", "suitcase", "log", "fire_ring", "delineator", "bollard", "bin", "manhole", "cone",
             "rebar", "cart", "bush", "sapling", "reeds", "stump", "bags", "barrel", "weed"}
# газовые трубы на опорах (рисует MallStreets, над дорогой — П-подъём): от техкомплекса к гаражам, вдоль
# западной дороги к КПП (через речку рядом с мостом), от котельной через кольцевую к разгрузочному двору
GAS_PIPES = [
    [[272.0, -100.0], [300.0, -80.0], [306.0, -20.0], [318.0, 36.0]],
    [[-258.0, -12.0], [-290.0, -12.5], [-330.0, -12.0], [-364.0, -13.0]],
    [[278.0, -150.0], [232.0, -152.0], [196.0, -128.0]],
]
# подземная теплотрасса: полоса рыжей травы и люки — от котельной к стройке
UNDERGROUND_HEAT = [[278.0, -160.0], [200.0, -220.0], [120.0, -262.0], [60.0, -268.0]]


def polar(a: float, r: float) -> tuple[float, float]:
    return r * math.cos(math.radians(a)), r * math.sin(math.radians(a))


def seg_dist(p, a, b) -> float:
    dx, dz = b[0] - a[0], b[1] - a[1]
    l2 = dx * dx + dz * dz
    t = 0.0 if l2 == 0.0 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dz) / l2))
    return math.hypot(p[0] - (a[0] + t * dx), p[1] - (a[1] + t * dz))


def yaw_along(dx: float, dz: float) -> float:
    return math.degrees(math.atan2(dx, dz))


class Points:
    """Точки по клеткам 32 м: расстояние до ближайшей."""

    def __init__(self, cell: float = 32.0):
        self.cell = cell
        self.cells: dict[tuple[int, int], list[tuple[float, float]]] = {}

    def add(self, p) -> None:
        self.cells.setdefault((int(p[0] // self.cell), int(p[1] // self.cell)), []).append((p[0], p[1]))

    def nearest(self, p, reach: int = 3) -> float:
        cx, cz = int(p[0] // self.cell), int(p[1] // self.cell)
        best = reach * self.cell
        for i in range(cx - reach, cx + reach + 1):
            for j in range(cz - reach, cz + reach + 1):
                for q in self.cells.get((i, j), ()):
                    d = math.hypot(p[0] - q[0], p[1] - q[1])
                    if d < best:
                        best = d
        return best


class Densify:
    def __init__(self, lay):
        self.lay = lay
        self.plan = lay.plan
        self.rng = lay.rng
        self.occupied = Points()
        self.counts: dict[str, int] = {}
        self.soil: list[list] = []
        self.forest_pts = Points()
        self.roads = [(r["points"], float(r["width"])) for r in self.plan["roads"] if r["id"] != "loop"]
        self.loop_r = self.plan["mall"]["loop_r"]
        self.loop_w = next(float(r["width"]) for r in self.plan["roads"] if r["id"] == "loop")
        river = self.plan.get("relief", {}).get("river", {})
        self.river = river.get("points", [])

    # ---------------------------------------------------------- что уже стоит

    def seed(self) -> None:
        plan = self.plan
        for item in self.lay.items:
            if item[0] not in FLAT_KITS and not (item[0].startswith("rock") and len(item) > 4 and item[4] < 1.0):
                self.occupied.add((item[1], item[2]))
        for street_item in plan.get("streets", {}).get("items", []):
            if street_item[0] in ("lamp", "mast", "kiosk", "bus_stop", "gantry", "traffic_light"):
                self.occupied.add((street_item[1], street_item[2]))
        for b in plan["buildings"]:
            (cx, cz), (sx, sz), yaw = b["at"], b["size"], math.radians(b["yaw"])
            for u in range(-2, 3):
                for v in range(-2, 3):
                    lx, lz = u / 4.0 * sx, v / 4.0 * sz
                    self.occupied.add((cx + lx * math.cos(yaw) + lz * math.sin(yaw), cz - lx * math.sin(yaw) + lz * math.cos(yaw)))
        for c in plan.get("relief", {}).get("cliffs", []):
            for a, b in zip(c["points"], c["points"][1:]):
                n = max(1, int(math.dist(a, b) / 6.0))
                for i in range(n + 1):
                    self.occupied.add((a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n))
        bx0, bz0, bx1, bz1 = plan["bounds"]
        x = bx0
        while x < bx1:
            z = bz0
            while z < bz1:
                if any(self._in_poly((x, z), f) for f in plan["forest"]):
                    self.occupied.add((x, z))
                    self.forest_pts.add((x, z))
                z += 8.0
            x += 8.0
        # ряды машин на парковках и стенки террас — сплошь предметы
        t = plan["terraces"]
        for park in plan["parkings"]:
            a0, a1 = park["a"]
            span = (a1 - a0) % 360.0
            for rad in (park["r"][0] + 6.0 + 16.0 * k for k in range(8)):
                if rad > park["r"][1]:
                    break
                for i in range(int(math.radians(span) * rad / 10.0) + 1):
                    self.occupied.add(polar(a0 + span * i / max(1, int(math.radians(span) * rad / 10.0)), rad))
        for w in t["walls"]:
            span = (t["a"][1] - t["a"][0]) % 360.0
            for i in range(int(math.radians(span) * w / 8.0) + 1):
                self.occupied.add(polar(t["a"][0] + span * i / max(1, int(math.radians(span) * w / 8.0)), w))

    @staticmethod
    def _in_poly(p, poly) -> bool:
        inside = False
        j = len(poly) - 1
        for i in range(len(poly)):
            (xi, zi), (xj, zj) = poly[i], poly[j]
            if (zi > p[1]) != (zj > p[1]) and p[0] < (xj - xi) * (p[1] - zi) / (zj - zi) + xi:
                inside = not inside
            j = i
        return inside

    def fillable(self, p) -> bool:
        """Клетка, которой нужно что-то рядом: на земле участка, не на дороге, площадке, воде, в здании, в лесу."""
        lay = self.lay
        if not self._in_poly(p, self.plan["boundary"]):
            return False
        if any(self._in_poly(p, f) for f in self.plan["forest"]):
            return False
        # всё, что запрещено даже кустам (дороги, площадь, двор, вода, постройки, маршруты вплотную)
        return not lay.blocked(p, -3.0, veg=True)

    # ---------------------------------------------------------- контекст места

    def road_info(self, p):
        best = (abs(math.hypot(*p) - self.loop_r) - self.loop_w * 0.5, None, self.loop_w)
        r = math.hypot(*p)
        if r > 1.0:
            best = (best[0], (-p[1] / r, p[0] / r), self.loop_w)
        for pts, w in self.roads:
            for a, b in zip(pts, pts[1:]):
                d = seg_dist(p, a, b) - w * 0.5
                if d < best[0]:
                    L = math.dist(a, b) or 1.0
                    best = (d, ((b[0] - a[0]) / L, (b[1] - a[1]) / L), w)
        return best

    def river_dist(self, p) -> float:
        if len(self.river) < 2:
            return 1e9
        return min(seg_dist(p, a, b) for a, b in zip(self.river, self.river[1:]))

    def context(self, p) -> str:
        d_road = self.road_info(p)[0]
        if self.river_dist(p) < 55.0:
            return "river"
        if math.hypot(*p) < self.loop_r - 6.0:
            return "inside"
        if d_road < 26.0:
            return "road"
        if self.forest_pts.nearest(p, 2) < 26.0:
            return "edge"
        return "field"

    # ---------------------------------------------------------- проверка и запись группы

    def try_group(self, pieces, need: float = 0.6) -> list:
        """pieces: [набор, x, z, поворот, масштаб, подъём, наклон, укрытие?, отступ, растительность?].
        Ставит те, что не мешают; если влезла меньше доли need — ничего. Возвращает поставленные точки."""
        ok = [pc for pc in pieces if not self.lay.blocked((pc[1], pc[2]), pc[8], veg=pc[9])]
        if not pieces or len(ok) < need * len(pieces):
            return []
        for kit, x, z, yaw, s, dy, roll, cover, margin, veg in ok:
            self.lay.put(kit, x, z, yaw, s, dy, roll=roll, cover=cover)
        for kit, x, z, yaw, s, dy, roll, cover, margin, veg in ok:
            self.lay.reserve(x, z, max(0.8, margin * 0.6))
            if kit not in FLAT_KITS:
                self.occupied.add((x, z))
        return [(pc[1], pc[2]) for pc in ok]

    @staticmethod
    def pc(kit, x, z, yaw=0.0, s=1.0, dy=0.0, roll=0.0, cover=False, margin=1.0, veg=False):
        return [kit, x, z, yaw, s, dy, roll, cover, margin, veg]

    def frame(self, c, theta):
        """Локальные оси группы: u — вдоль, v — поперёк."""
        u = (math.cos(theta), math.sin(theta))
        v = (-u[1], u[0])

        def at(a: float, b: float):
            return c[0] + u[0] * a + v[0] * b, c[1] + u[1] * a + v[1] * b
        return at, u, v

    def fence_run(self, kit, a, b, step: float, gaps=(), fallen: int = -1) -> list:
        """Секции забора от a до b (локальная Z набора — вдоль забора); gaps — номера выпавших секций."""
        n = max(1, round(math.dist(a, b) / step))
        yaw = yaw_along(b[0] - a[0], b[1] - a[1])
        out = []
        for i in range(n):
            if i in gaps:
                continue
            t = (i + 0.5) / n
            x, z = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
            if i == fallen:
                out.append(self.pc(kit, x, z, yaw, roll=72.0, cover=True, margin=1.2))
            else:
                out.append(self.pc(kit, x, z, yaw, cover=kit == "po2", margin=0.9))
        return out

    def weeds_along(self, pts, every: float = 7.0) -> None:
        for a, b in zip(pts, pts[1:]):
            n = max(1, int(math.dist(a, b) / every))
            for i in range(n):
                t = (i + self.rng.random()) / n
                x, z = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
                if not self.lay.blocked((x, z), 0.5, veg=True):
                    self.lay.weed_patch(x + self.rng.uniform(-1.0, 1.0), z + self.rng.uniform(-1.0, 1.0), self.rng.uniform(1.4, 2.4), 1.0)

    # ---------------------------------------------------------- группы

    def windbreak(self, c, theta) -> list:
        """Лесополоса 50–110 м: два ряда деревьев в шахматку, подлесок, проход посередине."""
        rng = self.rng
        length = rng.uniform(50.0, 110.0)
        at, u, v = self.frame(c, theta)
        pieces = []
        s = -length / 2
        k = 0
        while s < length / 2:
            if not (length > 70.0 and abs(s) < 6.0):
                for row in (-3.0, 3.0):
                    off = 2.2 if (k % 2 == 0) == (row > 0) else 0.0
                    p = at(s + off + rng.uniform(-0.8, 0.8), row + rng.uniform(-0.6, 0.6))
                    kit = "tree_poplar" if rng.random() < 0.35 else "tree_birch"
                    pieces.append(self.pc(kit, p[0], p[1], rng.uniform(0, 360), rng.uniform(0.8, 1.2), margin=1.2, veg=True))
                if rng.random() < 0.6:
                    p = at(s + rng.uniform(0.0, 4.0), rng.uniform(-5.5, 5.5))
                    pieces.append(self.pc("bush", p[0], p[1], rng.uniform(0, 360), rng.uniform(1.4, 2.6), margin=0.5, veg=True))
            s += 4.5
            k += 1
        placed = self.try_group(pieces, 0.5)
        if placed:
            self.weeds_along([at(-length / 2, 0.0), at(length / 2, 0.0)], 9.0)
        return placed

    def dacha(self, c, theta) -> list:
        """Дачные участки 16×20: штакетник с калиткой, сарай, теплица, туалет, яблони, грядки."""
        rng = self.rng
        at, u, v = self.frame(c, theta)
        cols, rows = rng.choice(((2, 2), (3, 1), (2, 1), (3, 2)))
        placed_all = []
        for i in range(cols):
            for j in range(rows):
                ox, oz = (i - (cols - 1) / 2) * 17.5, (j - (rows - 1) / 2) * 21.5
                corners = [at(ox - 8, oz - 10), at(ox + 8, oz - 10), at(ox + 8, oz + 10), at(ox - 8, oz + 10)]
                pieces = []
                for k in range(4):
                    gaps = (2,) if k == 0 else (() if rng.random() < 0.7 else (rng.randrange(6),))
                    pieces += self.fence_run("picket", corners[k], corners[(k + 1) % 4], 2.5, gaps)
                yaw = math.degrees(-theta) + 90.0
                shed = at(ox + 5.0, oz + 7.0)
                pieces.append(self.pc("shed", shed[0], shed[1], yaw, cover=True, margin=2.5))
                if rng.random() < 0.6:
                    gh = at(ox - 3.5, oz + 4.0)
                    pieces.append(self.pc("greenhouse", gh[0], gh[1], yaw, margin=2.0))
                if rng.random() < 0.4:
                    ot = at(ox + 6.5, oz - 8.0)
                    pieces.append(self.pc("outhouse", ot[0], ot[1], yaw, margin=1.0))
                if rng.random() < 0.3:
                    hs = at(ox - 2.0, oz + 6.5)
                    pieces = [p for p in pieces if p[0] not in ("greenhouse",)]
                    pieces.append(self.pc("house_small", hs[0], hs[1], yaw, cover=True, margin=4.5))
                for _ in range(rng.randint(2, 3)):
                    t = at(ox + rng.uniform(-5.5, 2.0), oz + rng.uniform(-7.0, -1.0))
                    pieces.append(self.pc("sapling", t[0], t[1], rng.uniform(0, 360), rng.uniform(1.0, 1.4), margin=0.6, veg=True))
                if rng.random() < 0.5:
                    b = at(ox + 6.0, oz + 2.0)
                    pieces.append(self.pc("barrel", b[0], b[1], 0.0, margin=0.6))
                placed = self.try_group(pieces, 0.75)
                if placed:
                    bed = at(ox - 1.0, oz - 3.0)
                    self.soil.append([round(bed[0], 1), round(bed[1], 1), 5.0, 0])
                    placed_all += placed
        if placed_all:
            self.counts["dacha_plots"] = self.counts.get("dacha_plots", 0) + 1
        return placed_all

    def berm(self, c, theta) -> list:
        """Вал грунта 26×7×1,6 поперёк прострела, бурьян по гребню."""
        at, u, v = self.frame(c, theta)
        for q in (c, at(-12, 0), at(12, 0)):
            if self.lay.blocked(q, 4.0):
                return []
        self.lay.earth["mounds"].append([round(c[0], 1), round(c[1], 1), 13.0, 3.5, round(-math.degrees(theta), 1), 1.6])
        pts = [at(s, 0.0) for s in (-10.0, -5.0, 0.0, 5.0, 10.0)]
        for p in pts:
            self.lay.add_cover(*p)
            self.occupied.add(p)
        self.lay.reserve(c[0], c[1], 15.0)
        self.weeds_along([at(-11, 0), at(11, 0)], 5.0)
        return pts

    def hay(self, c, theta) -> list:
        rng = self.rng
        pieces = []
        for _ in range(rng.randint(4, 8)):
            q = polar(rng.uniform(0, 360), rng.uniform(0.0, 13.0))
            pieces.append(self.pc("hay_roll", c[0] + q[0], c[1] + q[1], rng.uniform(0, 360), cover=True, margin=1.5))
        x, z = c
        pieces.append(self.pc("hay_roll", x + 1.6, z, math.degrees(theta), cover=True, margin=1.5))
        pieces.append(self.pc("hay_roll", x - 1.6, z, math.degrees(theta), cover=True, margin=1.5))
        pieces.append(self.pc("hay_roll", x, z, math.degrees(theta), dy=1.35, margin=0.0))
        return self.try_group(pieces, 0.6)

    def ruin(self, c, theta) -> list:
        """Развалины дома 8×10: стены буквой Г и обломок, внутри куча и бурьян, рядом сгоревшая машина."""
        rng = self.rng
        at, u, v = self.frame(c, theta)
        yaw = math.degrees(-theta)
        pieces = [self.pc("ruin_l", *at(-4.0, -5.0), yaw, cover=True, margin=3.0),
                  self.pc("ruin_i", *at(4.0, 2.0), yaw + 90.0, cover=True, margin=2.0),
                  self.pc("ruin_i", *at(-1.0, 5.0), yaw, s=0.8, cover=True, margin=2.0)]
        if rng.random() < 0.5:
            pieces.append(self.pc("car", *at(9.0, -2.0), yaw + rng.uniform(-30, 30), cover=True, margin=2.5))
        placed = self.try_group(pieces, 0.65)
        if placed:
            self.lay.earth["mounds"].append([round(c[0], 1), round(c[1], 1), 3.5, 2.5, 0.0, 0.9])
            self.lay.weed_patch(c[0], c[1], 6.0, 0.6)
            self.soil.append([round(c[0], 1), round(c[1], 1), 7.0, 0])
        return placed

    def lot(self, c, theta) -> list:
        """Пустырь за ПО-2 с трёх сторон: выпавшая и упавшая секции, внутри свалка."""
        rng = self.rng
        at, u, v = self.frame(c, theta)
        w, h = rng.uniform(24.0, 34.0), rng.uniform(18.0, 26.0)
        corners = [at(-w / 2, -h / 2), at(w / 2, -h / 2), at(w / 2, h / 2), at(-w / 2, h / 2)]
        pieces = []
        open_side = rng.randrange(4)
        for k in range(4):
            if k == open_side:
                continue
            n = max(1, round(math.dist(corners[k], corners[(k + 1) % 4]) / 2.5))
            gaps = {rng.randrange(n)} if rng.random() < 0.6 else set()
            fallen = rng.randrange(n) if rng.random() < 0.4 else -1
            pieces += self.fence_run("po2", corners[k], corners[(k + 1) % 4], 2.5, gaps, fallen)
        inside = self.scrap_pieces(c, 7.0)
        placed = self.try_group(pieces + inside, 0.7)
        if placed:
            self.weeds_along(corners + corners[:1], 6.0)
            self.soil.append([round(c[0], 1), round(c[1], 1), min(w, h) * 0.45, 0])
        return placed

    def scrap_pieces(self, c, radius: float) -> list:
        rng = self.rng
        pieces = []
        for _ in range(rng.randint(3, 6)):
            q = polar(rng.uniform(0, 360), rng.uniform(1.5, radius))
            x, z = c[0] + q[0], c[1] + q[1]
            kit = rng.choices(("tires", "ring", "car", "slab", "pallets", "container20", "reel"), (4, 3, 2, 2, 2, 1, 1))[0]
            if kit == "car":
                pieces.append(self.pc("car", x, z, rng.uniform(0, 360), roll=rng.choice((0.0, 0.0, 180.0)), cover=True, margin=2.5))
            elif kit == "ring":
                for k in range(rng.randint(1, 3)):
                    pieces.append(self.pc("ring", x + k * 1.25, z, 0.0, dy=0.0 if k < 2 else 0.9, cover=k == 0, margin=1.0))
            else:
                pieces.append(self.pc(kit, x, z, rng.uniform(0, 360), cover=True, margin=1.6))
        return pieces

    def scrap(self, c, theta) -> list:
        placed = self.try_group(self.scrap_pieces(c, 8.0), 0.6)
        if placed:
            self.lay.weed_patch(c[0], c[1], 5.0, 0.6)
            self.soil.append([round(c[0], 1), round(c[1], 1), 6.0, 0])
        return placed

    def clump(self, c, theta) -> list:
        rng = self.rng
        pieces = []
        for _ in range(rng.randint(4, 9)):
            q = polar(rng.uniform(0, 360), rng.uniform(0.0, 9.0))
            kit = rng.choices(("tree_birch", "tree_poplar", "sapling"), (5, 1, 2))[0]
            pieces.append(self.pc(kit, c[0] + q[0], c[1] + q[1], rng.uniform(0, 360), rng.uniform(0.8, 1.2), margin=1.0, veg=True))
        for _ in range(rng.randint(3, 6)):
            q = polar(rng.uniform(0, 360), rng.uniform(2.0, 11.0))
            pieces.append(self.pc("bush", c[0] + q[0], c[1] + q[1], rng.uniform(0, 360), rng.uniform(1.3, 2.6), margin=0.5, veg=True))
        return self.try_group(pieces, 0.5)

    def car_chain(self, c, theta) -> list:
        """Брошенные машины цепочкой по обочине ближайшей дороги."""
        rng = self.rng
        d, direction, w = self.road_info(c)
        if direction is None:
            return []
        pieces = []
        for k in range(rng.randint(2, 4)):
            x = c[0] + direction[0] * k * 7.0
            z = c[1] + direction[1] * k * 7.0
            state = rng.choices(("", "burnt", "side", "roof"), (55, 25, 12, 8))[0]
            roll = {"side": 90.0, "roof": 180.0}.get(state, 0.0)
            pieces.append(self.pc("car", x, z, yaw_along(*direction) + rng.uniform(-20, 20), roll=roll, cover=True, margin=2.5))
        placed = self.try_group(pieces, 0.6)
        if placed and rng.random() < 0.5:
            q = placed[0]
            self.lay.put("suitcase", q[0] + 2.0, q[1] + 1.0, rng.uniform(0, 360))
        return placed

    def roadworks(self, c, theta) -> list:
        """Ремонт дороги у обочины: ограждения, конусы, куча асфальта, каток, плиты."""
        rng = self.rng
        d, direction, w = self.road_info(c)
        if direction is None:
            return []
        at, u, v = self.frame(c, math.atan2(direction[1], direction[0]))
        yaw = yaw_along(*direction)
        pieces = [self.pc("road_barrier", *at(s, 0.0), yaw, cover=False, margin=0.8) for s in (-6.0, -4.0, -2.0, 0.0, 2.0, 4.0)]
        for s in (-9.0, -7.5, 6.5, 8.0):
            pieces.append(self.pc("cone", *at(s, rng.uniform(-0.5, 0.5)), 0.0, margin=0.4))
        pieces.append(self.pc("roller", *at(2.0, 5.0), yaw + rng.uniform(-15, 15), cover=True, margin=2.5))
        pieces.append(self.pc("slab", *at(-5.0, 5.5), yaw, cover=True, margin=2.0))
        pieces.append(self.pc("slab", *at(-5.0, 5.5), yaw + 3.0, dy=0.19, margin=0.0))
        placed = self.try_group(pieces, 0.6)
        if placed:
            p = at(-1.0, 6.5)
            self.lay.earth["mounds"].append([round(p[0], 1), round(p[1], 1), 3.0, 2.0, 0.0, 1.1])
            self.soil.append([round(p[0], 1), round(p[1], 1), 4.5, 5])
        return placed

    def ktp(self, c, theta) -> list:
        """Трансформаторная будка в сетке-рабице 6×6, кабельная катушка, бурьян."""
        at, u, v = self.frame(c, theta)
        yaw = math.degrees(-theta)
        pieces = [self.pc("ktp", c[0], c[1], yaw, cover=True, margin=2.5)]
        corners = [at(-3, -3), at(3, -3), at(3, 3), at(-3, 3)]
        for k in range(4):
            pieces += [p[:8] + [0.6, False] for p in self.fence_run("chainlink", corners[k], corners[(k + 1) % 4], 2.0, (1,) if k == 0 else ())]
        r = at(5.5, 1.0)
        pieces.append(self.pc("reel", r[0], r[1], yaw, cover=True, margin=1.5))
        placed = self.try_group(pieces, 0.7)
        if placed:
            self.weeds_along(corners + corners[:1], 4.0)
        return placed

    def container_site(self, c, theta) -> list:
        """Мусорная площадка: 3–4 бака в ряд, профнастил буквой П, мешки."""
        rng = self.rng
        at, u, v = self.frame(c, theta)
        yaw = math.degrees(-theta)
        n = rng.randint(3, 4)
        pieces = [self.pc("dumpster", *at((k - (n - 1) / 2) * 1.7, 0.0), yaw + 90.0, cover=k == 0, margin=1.2) for k in range(n)]
        half = n * 0.85 + 0.6
        for a, b in ((at(-half, -1.6), at(half, -1.6)), (at(-half, -1.6), at(-half, 1.4)), (at(half, -1.6), at(half, 1.4))):
            pieces += self.fence_run("fence", a, b, 3.0)
        for _ in range(rng.randint(3, 6)):
            q = at(rng.uniform(-half, half), rng.uniform(1.6, 3.5))
            pieces.append(self.pc("bags", q[0], q[1], rng.uniform(0, 360), margin=0.4))
        return self.try_group(pieces, 0.7)

    def kiosks(self, c, theta) -> list:
        rng = self.rng
        at, u, v = self.frame(c, theta)
        yaw = math.degrees(-theta) + 90.0
        pieces = [self.pc("kiosk", *at((k - 1) * 3.6, 0.0), yaw, cover=True, margin=2.0) for k in range(rng.randint(2, 3))]
        pieces.append(self.pc("bin", *at(-6.0, 2.0), 0.0, margin=0.4))
        pieces.append(self.pc("pallets", *at(2.0, -2.6), yaw, cover=True, margin=1.0))
        return self.try_group(pieces, 0.7)

    def logs(self, c, theta) -> list:
        rng = self.rng
        at, u, v = self.frame(c, theta)
        yaw = math.degrees(-theta)
        pieces = [self.pc("log_pile", *at(0.0, 0.0), yaw, cover=True, margin=2.5),
                  self.pc("log_pile", *at(0.5, 3.2), yaw + rng.uniform(-8, 8), cover=True, margin=2.5)]
        for _ in range(rng.randint(3, 6)):
            q = at(rng.uniform(-9, 9), rng.uniform(-7, 9))
            pieces.append(self.pc("stump", q[0], q[1], rng.uniform(0, 360), margin=0.5))
        placed = self.try_group(pieces, 0.6)
        if placed:
            self.soil.append([round(c[0], 1), round(c[1], 1), 8.0, 0])
        return placed

    def stand(self, c, theta) -> list:
        pieces = [self.pc("hunting_stand", c[0], c[1], math.degrees(-theta), cover=True, margin=2.5)]
        for _ in range(4):
            q = polar(self.rng.uniform(0, 360), self.rng.uniform(3.0, 7.0))
            pieces.append(self.pc("bush", c[0] + q[0], c[1] + q[1], 0.0, self.rng.uniform(1.4, 2.4), margin=0.5, veg=True))
        return self.try_group(pieces, 0.6)

    def reeds(self, c, theta) -> list:
        rng = self.rng
        pieces = []
        for _ in range(rng.randint(4, 7)):
            q = polar(rng.uniform(0, 360), rng.uniform(0.0, 9.0))
            pieces.append(self.pc("reeds", c[0] + q[0], c[1] + q[1], rng.uniform(0, 360), rng.uniform(0.8, 1.4), margin=0.5, veg=True))
        for _ in range(rng.randint(1, 3)):
            q = polar(rng.uniform(0, 360), rng.uniform(2.0, 10.0))
            pieces.append(self.pc("rock_b", c[0] + q[0], c[1] + q[1], rng.uniform(0, 360), rng.uniform(0.6, 1.2), dy=-0.2, cover=True, margin=1.5))
        return self.try_group(pieces, 0.5)

    def planters(self, c, theta) -> list:
        """Внутри кольца: островок с деревьями и вазонами, скамейка."""
        rng = self.rng
        at, u, v = self.frame(c, theta)
        pieces = [self.pc("planter", *at(k * 4.5 - 4.5, 0.0), 0.0, cover=True, margin=1.6) for k in range(3)]
        pieces += [self.pc("tree_birch", *at(k * 4.5 - 4.5, 0.0), rng.uniform(0, 360), 0.85, margin=0.0, veg=True) for k in range(3)]
        pieces.append(self.pc("bench", *at(0.0, 2.2), math.degrees(-theta), margin=0.6))
        return self.try_group(pieces, 0.7)

    # ---------------------------------------------------------- проход по карте пустоты

    CHOICES = {
        "road": (("car_chain", 3), ("roadworks", 2), ("ktp", 2), ("container_site", 1), ("clump", 2), ("scrap", 1)),
        "inside": (("planters", 3), ("ktp", 2), ("container_site", 2), ("kiosks", 1), ("car_chain", 2), ("scrap", 1), ("lot", 1)),
        "river": (("dacha", 3), ("reeds", 2), ("clump", 2), ("hay", 1), ("scrap", 1)),
        "edge": (("logs", 2), ("stand", 1), ("clump", 2), ("ruin", 1), ("scrap", 1), ("windbreak", 1)),
        "field": (("windbreak", 4), ("dacha", 2), ("berm", 2), ("hay", 2), ("ruin", 2), ("lot", 2), ("scrap", 1), ("clump", 2)),
    }
    LIMITS = {"windbreak": 16, "dacha": 6, "ruin": 9, "lot": 8, "stand": 4, "kiosks": 4, "berm": 12, "hay": 12, "logs": 6}

    def run(self) -> dict:
        plan = self.plan
        self.seed()
        bx0, bz0, bx1, bz1 = plan["bounds"]
        cells = []
        x = bx0 + CELL / 2
        while x < bx1:
            z = bz0 + CELL / 2
            while z < bz1:
                if self.fillable((x, z)):
                    cells.append([x, z, self.occupied.nearest((x, z))])
                z += CELL
            x += CELL
        before = sorted(c[2] for c in cells)
        tried: set[tuple[int, int]] = set()
        made = 0
        while made < MAX_FEATURES:
            best = None
            for c in cells:
                if c[2] > TARGET_M and (int(c[0]), int(c[1])) not in tried and (best is None or c[2] > best[2]):
                    best = c
            if best is None:
                break
            p = (best[0], best[1])
            ctx = self.context(p)
            # поперёк линии к ТЦ (режет прострел к зданию) или вдоль ближайшей дороги
            theta = math.atan2(p[1], p[0]) + math.pi / 2 + self.rng.uniform(-0.35, 0.35)
            names = [n for n, w in self.CHOICES[ctx] if self.counts.get(n, 0) < self.LIMITS.get(n, 999)]
            weights = [w for n, w in self.CHOICES[ctx] if self.counts.get(n, 0) < self.LIMITS.get(n, 999)]
            placed = []
            for attempt in range(3):
                name = self.rng.choices(names, weights)[0]
                jitter = (p[0] + self.rng.uniform(-6, 6), p[1] + self.rng.uniform(-6, 6))
                placed = getattr(self, name)(jitter, theta)
                if placed:
                    self.counts[name] = self.counts.get(name, 0) + 1
                    break
            if not placed:
                tried.add((int(best[0]), int(best[1])))
                continue
            made += 1
            for c in cells:
                if abs(c[0] - p[0]) < 140.0 and abs(c[1] - p[1]) < 140.0:
                    for q in placed:
                        d = math.hypot(c[0] - q[0], c[1] - q[1])
                        if d < c[2]:
                            c[2] = d
        after = sorted(c[2] for c in cells)
        self.lines()
        return {"features": made, "by_kind": self.counts, "cells": len(cells),
                "bald_before": sum(1 for d in before if d > TARGET_M), "bald_after": sum(1 for d in after if d > TARGET_M),
                "max_gap_before_m": round(before[-1], 1) if before else 0, "max_gap_after_m": round(after[-1], 1) if after else 0}

    def lines(self) -> None:
        """Газовые трубы и подземная теплотрасса (рыжая полоса и люки)."""
        for a, b in zip(UNDERGROUND_HEAT, UNDERGROUND_HEAT[1:]):
            n = max(1, int(math.dist(a, b) / 9.0))
            for i in range(n + 1):
                t = i / n
                x, z = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
                if not self.lay.blocked((x, z), -2.0, veg=True):
                    self.soil.append([round(x, 1), round(z, 1), 4.0, 4])
            for i in range(1, n, 6):
                t = i / n
                x, z = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
                if not self.lay.blocked((x, z), -2.0, veg=True):
                    self.lay.put("manhole", x, z, 0.0)


def densify(lay) -> tuple[dict, list, list]:
    d = Densify(lay)
    stats = d.run()
    return stats, d.soil, GAS_PIPES
