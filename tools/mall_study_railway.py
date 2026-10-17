"""Железнодорожная ветка черновика территории ТЦ (владелец, 2026-10-17: «делай железную дорогу — подъездной
путь с насыпью, вагонами и переездом»; Таможня Таркова — длинная простреливаемая линия с вагонами-укрытиями).

Ветка приходит с запада из-за границы участка (от основного хода) и идёт через лес и поле севернее
точки появления «запад», пересекает грунтовку КПП — брод переездом (шлагбаумы подняты, светофоры,
кресты, будка дежурного, знаки), речку — мостом и кончается тупиком с упором у кольцевой: бетонная
платформа напротив палаток эвакопункта на западной парковке.

История: эвакуационный эшелон (тепловоз и четыре вагона) встал, не дойдя до платформы; у платформы —
теплушка, рядом опрокинутый вагон. Насыпь 1,4 м с откосами 1:1,5 — перелезть можно, под рельсами
коллизии нет (капсула не цепляется), вагоны — укрытие.

Координаты игры: X — восток, Z — юг. Насыпь считает MallLandscape (ключ filler.rail), путь, мост,
переезд и платформу рисует MallStreets, вагоны и знаки — наборы наполнения.
"""

from __future__ import annotations

import math

from mall_study_relief import base_height

LINE = [(-565.0, 143.0), (-515.0, 120.0), (-472.0, 99.0), (-445.0, 84.0), (-420.0, 77.0), (-380.0, 74.0), (-336.0, 72.0), (-306.0, 72.0), (-266.0, 72.0)]
EMBANK = 1.4          # высота насыпи над землёй, м
TOP_HALF = 3.2        # полуширина верха насыпи
SLOPE = 1.5           # откос: метров в сторону на метр высоты
GAUGE = 1.52          # колея 1520 мм
CORRIDOR = 7.5        # полоса, где наполнение ничего не ставит
# эшелон: центры по X с востока на запад (тепловоз впереди, к платформе)
TRAIN = [("loco_tem", -402.0, 17.0), ("wagon_pass", -420.0, 16.0), ("wagon_pass", -437.0, 16.0),
         ("wagon_box", -453.0, 14.0), ("wagon_box", -468.0, 14.0)]
PLATFORM = (-292.0, -268.0)  # платформа вдоль пути, X от и до (у тупика)


def resample(pts, step: float):
    out = []
    for a, b in zip(pts, pts[1:]):
        n = max(1, int(math.dist(a, b) / step))
        for i in range(n):
            t = i / n
            out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
    out.append(tuple(pts[-1]))
    return out


def yaw_along(dx: float, dz: float) -> float:
    return math.degrees(math.atan2(dx, dz))


def seg_hit(p1, p2, q1, q2):
    d1 = (p2[0] - p1[0], p2[1] - p1[1])
    d2 = (q2[0] - q1[0], q2[1] - q1[1])
    den = d1[0] * d2[1] - d1[1] * d2[0]
    if abs(den) < 1e-9:
        return None
    w = (q1[0] - p1[0], q1[1] - p1[1])
    t = (w[0] * d2[1] - w[1] * d2[0]) / den
    u = (w[0] * d1[1] - w[1] * d1[0]) / den
    if 0.0 <= t <= 1.0 and 0.0 <= u <= 1.0:
        return (p1[0] + d1[0] * t, p1[1] + d1[1] * t), (d2[0], d2[1])
    return None


class Railway:
    def __init__(self, lay, tracks):
        self.lay = lay
        self.tracks = tracks
        self.plan = lay.plan
        self.rng = lay.rng
        self.line = [(round(x, 2), round(z, 2)) for x, z in resample(LINE, 4.0)]
        self.tops = [round(base_height(self.plan, x, z) + EMBANK, 2) for x, z in self.line]

    def at_x(self, x: float):
        """Точка и ход пути там, где он проходит через данный X (путь с запада на восток монотонен по X)."""
        for a, b in zip(self.line, self.line[1:]):
            if a[0] <= x <= b[0]:
                t = (x - a[0]) / (b[0] - a[0])
                d = math.dist(a, b)
                return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t), ((b[0] - a[0]) / d, (b[1] - a[1]) / d)
        a, b = self.line[-2], self.line[-1]
        d = math.dist(a, b)
        return tuple(b), ((b[0] - a[0]) / d, (b[1] - a[1]) / d)

    def build(self) -> dict:
        lay = self.lay
        rng = self.rng
        lay.corridors.append(([list(p) for p in self.line], CORRIDOR))
        # эшелон: двери нараспашку, вещи у вагонов, у тепловоза — находка
        for kit, x, length in TRAIN:
            p, d = self.at_x(x)
            lay.put(kit, p[0], p[1], yaw_along(*d), dy=0.3, cover=True)
            if kit != "loco_tem":
                side = rng.choice((-1.0, 1.0)) * 3.2
                for _ in range(rng.randint(1, 3)):
                    q = (p[0] - d[1] * side + d[0] * rng.uniform(-5.0, 5.0), p[1] + d[0] * side + d[1] * rng.uniform(-5.0, 5.0))
                    lay.put(rng.choice(("suitcase", "bags")), q[0], q[1], rng.uniform(0.0, 360.0))
        p, d = self.at_x(-396.0)
        lay.put("find", p[0] - d[1] * 2.6, p[1] + d[0] * 2.6, 0.0)
        lay.story("Эвакуационный эшелон", self.at_x(-430.0)[0], None, 9.0)
        # у платформы (с северной стороны, к палаткам): теплушка на пути, опрокинутый вагон — с южной
        p, d = self.at_x(-284.0)
        lay.put("wagon_box", p[0], p[1], yaw_along(*d), dy=0.3, cover=True)
        q = (p[0] - d[1] * 7.5 - d[0] * 4.0, p[1] + d[0] * 7.5 - d[1] * 4.0)
        lay.put("wagon_box", q[0], q[1], yaw_along(*d) + 9.0, roll=82.0, cover=True)
        lay.story("Платформа эвакопункта", self.at_x(-279.0)[0], None, 7.0)
        end, d = self.at_x(LINE[-1][0])
        lay.put("buffer_stop", end[0] - d[0] * 1.0, end[1] - d[1] * 1.0, yaw_along(*d), cover=True)
        # штабели шпал у тупика — с южной стороны
        lay.put("sleepers", end[0] - d[1] * 8.0 - d[0] * 18.0, end[1] + d[0] * 8.0 - d[1] * 18.0, yaw_along(*d) + 90.0, cover=True)
        lay.put("sleepers", end[0] - d[1] * 8.5 - d[0] * 21.0, end[1] + d[0] * 8.5 - d[1] * 21.0, yaw_along(*d) + 84.0)
        crossings = self.crossings()
        return {"points": [list(p) for p in self.line], "tops": self.tops, "top_half": TOP_HALF, "slope": SLOPE,
                "gauge": GAUGE, "crossings": crossings,
                # сторона — от хода пути (на восток): −1 — слева, к северу, к палаткам эвакопункта
                "platform": {"x": list(PLATFORM), "side": -1.0, "width": 4.5, "height": 1.1}}

    def crossings(self) -> list[dict]:
        """Переезды: где путь пересекает грунтовки и дороги. Шлагбаумы подняты (брошено), светофоры,
        андреевские кресты, знаки «переезд» за 40 м, будка дежурного."""
        lay = self.lay
        out = []
        roads = [t["points"] for t in self.tracks] + [r["points"] for r in self.plan["roads"]]
        for a, b in zip(self.line, self.line[1:]):
            for road in roads:
                for q1, q2 in zip(road, road[1:]):
                    hit = seg_hit(a, b, q1, q2)
                    if not hit:
                        continue
                    (x, z), rd = hit
                    L = math.hypot(*rd) or 1.0
                    rd = (rd[0] / L, rd[1] / L)
                    out.append({"at": [round(x, 2), round(z, 2)], "road": [round(rd[0], 3), round(rd[1], 3)], "width": 7.0})
                    for sgn in (1.0, -1.0):
                        t = (rd[0] * sgn, rd[1] * sgn)       # ход машины к переезду
                        right = (-t[1], t[0])
                        def at(back: float, side: float):
                            return (x - t[0] * back + right[0] * side, z - t[1] * back + right[1] * side)
                        lay.put("barrier_arm_up", *at(7.0, 3.2), yaw_along(-right[0], -right[1]))
                        lay.put("rail_signal", *at(5.5, 3.6), yaw_along(-t[0], -t[1]))
                        lay.put("rail_cross_sign", *at(9.0, 3.8), yaw_along(-t[0], -t[1]))
                        lay.put("sign_rail_warn", *at(40.0, 3.4), yaw_along(-t[0], -t[1]))
                    booth = (x - rd[0] * 9.0 + rd[1] * 9.0, z - rd[1] * 9.0 - rd[0] * 9.0)
                    lay.put("booth", booth[0], booth[1], yaw_along(*rd), cover=True)
                    lay.story("Переезд", (x, z), None, 6.0)
        return out


def make_railway(lay, tracks) -> dict:
    return Railway(lay, tracks).build()
