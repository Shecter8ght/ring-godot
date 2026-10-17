"""Сквер у ТЦ — парк (владелец, 2026-10-17: «в сквере не хватает лавочек, памятников, фонтана, ларёчков с едой,
каруселей — качели, карусели или колесо обозрения; побольше деревьев, заборчики, интересные тропинки»).

  аллеи      — главная от здания к кольцевой через площадь с фонтаном, полукольца, извилистые дорожки;
  площади    — у фонтана (вокруг клумбы), у памятника, у ларьков (столики под зонтами), у эстрады;
  аттракционы — колесо обозрения (ориентир ~30 м), карусель, детская площадка (качели, горки, песочница,
                лазалка) за низким заборчиком;
  ограда     — кованая по краю сквера с воротами на дорожки (к зданию сквер открыт);
  деревья    — аллейные вдоль главной аллеи и россыпью по газонам, не на дорожках.

Координаты игры: X — восток, Z — юг; углы — от +X к +Z (как SectorBuilder.polar). Дорожки, площади, фонтан,
колесо и ограду рисует MallPark (src/blockout/mall_park.gd), остальное — наборы наполнения.
"""

from __future__ import annotations

import math
import random

SEED = 20261019


def polar(a: float, r: float) -> tuple[float, float]:
    return r * math.cos(math.radians(a)), r * math.sin(math.radians(a))


def yaw_along(dx: float, dz: float) -> float:
    return math.degrees(math.atan2(dx, dz))


def seg_dist(p, a, b) -> float:
    dx, dz = b[0] - a[0], b[1] - a[1]
    l2 = dx * dx + dz * dz
    t = 0.0 if l2 == 0.0 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dz) / l2))
    return math.hypot(p[0] - (a[0] + t * dx), p[1] - (a[1] + t * dz))


def poly_dist(p, pts) -> float:
    return min(seg_dist(p, a, b) for a, b in zip(pts, pts[1:]))


def catmull(points, step: float = 2.0):
    """Плавная кривая через точки (Catmull-Rom), шаг ~step м — извилистые дорожки."""
    pts = [points[0]] + list(points) + [points[-1]]
    out = []
    for i in range(1, len(pts) - 2):
        p0, p1, p2, p3 = pts[i - 1], pts[i], pts[i + 1], pts[i + 2]
        n = max(2, int(math.dist(p1, p2) / step))
        for k in range(n):
            t = k / n
            t2, t3 = t * t, t * t * t
            out.append([round(0.5 * (2 * p1[c] + (-p0[c] + p2[c]) * t + (2 * p0[c] - 5 * p1[c] + 4 * p2[c] - p3[c]) * t2 +
                                     (-p0[c] + 3 * p1[c] - 3 * p2[c] + p3[c]) * t3), 2) for c in (0, 1)])
    out.append([round(points[-1][0], 2), round(points[-1][1], 2)])
    return out


def arc(a0: float, a1: float, r: float, step: float = 3.0):
    n = max(2, int(abs(math.radians(a1 - a0)) * r / step))
    return [[round(v, 2) for v in polar(a0 + (a1 - a0) * i / n, r)] for i in range(n + 1)]


def resample(pts, step: float):
    out = []
    for a, b in zip(pts, pts[1:]):
        n = max(1, int(math.dist(a, b) / step))
        for i in range(n):
            t = i / n
            out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
    out.append(tuple(pts[-1]))
    return out


# центр композиции — площадь с фонтаном посреди сквера (угол −110°, радиус 182 м)
FOUNTAIN = (-110.0, 182.0)
MONUMENT = (-134.0, 160.0)
PLAYGROUND = (-127.0, 206.0)
CAROUSEL = (-117.0, 222.0)
WHEEL = (-88.0, 206.0)
FOOD = (-101.0, 163.0)
STAGE = (-82.0, 168.0)


class Park:
    def __init__(self, lay):
        self.lay = lay
        self.plan = lay.plan
        self.rng = random.Random(SEED)
        sq = self.plan["square"]
        self.a0, self.a1 = sq["a"]   # −146 … −74
        self.r0, self.r1 = sq["r"]   # 128 … 236
        self.paths: list[dict] = []
        self.plazas: list[list[float]] = []
        self.fence: list[list] = []
        self.trees: list[list[float]] = []
        self.features: list[tuple[float, float, float]] = []  # где ничего не сажать: x, z, радиус

    def put(self, kit: str, p, yaw: float = 0.0, s: float = 1.0) -> None:
        self.lay.put(kit, p[0], p[1], yaw, s, cover=kit in ("kiosk", "monument", "carousel", "stage", "wheel_booth"))

    def path(self, pts, width: float) -> None:
        self.paths.append({"points": [list(p) for p in pts], "width": width})

    def build(self) -> dict:
        rng = self.rng
        a0, a1, r0, r1 = self.a0, self.a1, self.r0, self.r1
        fc = polar(*FOUNTAIN)
        # --- дорожки
        main = [list(polar(FOUNTAIN[0], r0 + 1.0)), list(polar(FOUNTAIN[0], r1 - 0.5))]
        self.path(main, 6.0)
        self.path(arc(a0 + 1.0, a1 - 1.0, 182.0), 3.6)
        self.path(arc(a0 + 6.0, a1 - 6.0, 150.0), 3.0)
        winding = [
            [polar(a0 + 3.0, r1 - 0.5), polar(-139.0, 214.0), polar(-133.0, 198.0), polar(-124.0, 190.0), polar(-115.0, 184.0)],
            [polar(a1 - 4.0, r1 - 0.5), polar(-83.0, 220.0), polar(-92.0, 199.0), polar(-100.0, 189.0), polar(-106.0, 184.0)],
            [polar(-141.0, r0 + 1.0), polar(-138.0, 142.0), polar(-136.0, 152.0), MONUMENT_P, polar(-129.0, 170.0), polar(-121.0, 181.0)],
            [polar(a1 - 5.0, r0 + 1.0), polar(-84.0, 145.0), polar(-86.0, 156.0), polar(-84.0, 164.0)],
            [polar(-120.0, 182.0), polar(-121.0, 196.0), polar(-118.0, 212.0)],
        ]
        for pts in winding:
            self.path(catmull(pts), 2.6)
        # --- площади
        self.plazas.append([round(fc[0], 2), round(fc[1], 2), 16.0])
        mp = MONUMENT_P
        self.plazas.append([round(mp[0], 2), round(mp[1], 2), 8.0])
        fp = polar(*FOOD)
        self.plazas.append([round(fp[0], 2), round(fp[1], 2), 10.0])
        sp = polar(*STAGE)
        self.plazas.append([round(sp[0], 2), round(sp[1], 2), 12.0])
        wp = polar(*WHEEL)
        self.plazas.append([round(wp[0], 2), round(wp[1], 2), 18.0])
        cp = polar(*CAROUSEL)
        self.plazas.append([round(cp[0], 2), round(cp[1], 2), 9.0])
        self.features += [(fc[0], fc[1], 17.0), (mp[0], mp[1], 9.0), (fp[0], fp[1], 11.0), (sp[0], sp[1], 13.0),
                          (wp[0], wp[1], 19.0), (cp[0], cp[1], 10.0)]
        # --- памятник: обелиск на ступенчатом постаменте, клумбы по углам, лавочки лицом к нему
        self.put("monument", mp, yaw_along(-mp[0], -mp[1]))
        for k in range(4):
            q = (mp[0] + 5.5 * math.cos(math.radians(45 + 90 * k)), mp[1] + 5.5 * math.sin(math.radians(45 + 90 * k)))
            self.put("flowerbed", q, 0.0, 0.7)
        # --- фонтан (рисует MallPark), клумбы вокруг площади
        for k in range(8):
            ang = 22.5 + 45.0 * k
            q = (fc[0] + 12.5 * math.cos(math.radians(ang)), fc[1] + 12.5 * math.sin(math.radians(ang)))
            if all(poly_dist(q, p["points"]) > p["width"] * 0.5 + 1.0 for p in self.paths):
                self.put("flowerbed", q, 0.0, 1.0)
        # --- ларьки с едой и столики под зонтами
        d = (math.cos(math.radians(FOOD[0] + 90)), math.sin(math.radians(FOOD[0] + 90)))
        out = (math.cos(math.radians(FOOD[0])), math.sin(math.radians(FOOD[0])))
        for k in range(3):
            q = (fp[0] + d[0] * (k - 1) * 4.2 + out[0] * 6.5, fp[1] + d[1] * (k - 1) * 4.2 + out[1] * 6.5)
            self.put("food_kiosk", q, yaw_along(-out[0], -out[1]))
        for k in range(6):
            q = (fp[0] + d[0] * ((k % 3) - 1) * 4.0 - out[0] * (1.0 + (k // 3) * 4.0), fp[1] + d[1] * ((k % 3) - 1) * 4.0 - out[1] * (1.0 + (k // 3) * 4.0))
            self.put("cafe_table", q, rng.uniform(0.0, 90.0))
        self.put("bin", (fp[0] + d[0] * 7.0, fp[1] + d[1] * 7.0))
        # --- эстрада («ракушка») и ряды скамеек перед ней
        self.put("stage", sp, yaw_along(math.cos(math.radians(STAGE[0])), math.sin(math.radians(STAGE[0]))))
        so = (math.cos(math.radians(STAGE[0])), math.sin(math.radians(STAGE[0])))
        st = (-so[1], so[0])
        for row in range(3):
            for k in (-1, 0, 1):
                q = (sp[0] - so[0] * (5.0 + row * 2.2) + st[0] * k * 2.4, sp[1] - so[1] * (5.0 + row * 2.2) + st[1] * k * 2.4)
                self.put("bench", q, yaw_along(so[0], so[1]))
        # --- колесо обозрения (рисует MallPark) и касса у его подножия
        self.put("wheel_booth", (wp[0] - math.cos(math.radians(WHEEL[0])) * 12.0, wp[1] - math.sin(math.radians(WHEEL[0])) * 12.0),
                 yaw_along(-math.cos(math.radians(WHEEL[0])), -math.sin(math.radians(WHEEL[0]))))
        # --- карусель
        self.put("carousel", cp, 0.0)
        # --- детская площадка: качели, горки, песочница, лазалка, скамейки по краю, низкий заборчик
        pg = polar(*PLAYGROUND)
        u = (math.cos(math.radians(PLAYGROUND[0] + 90)), math.sin(math.radians(PLAYGROUND[0] + 90)))
        v = (math.cos(math.radians(PLAYGROUND[0])), math.sin(math.radians(PLAYGROUND[0])))
        def at(a: float, b: float):
            return pg[0] + u[0] * a + v[0] * b, pg[1] + u[1] * a + v[1] * b
        self.put("swing", at(-8.0, -3.0), yaw_along(*u))
        self.put("swing", at(-8.0, 3.0), yaw_along(*u))
        self.put("slide", at(3.0, -4.0), yaw_along(*v))
        self.put("sandbox", at(-1.0, 4.0), 0.0)
        self.put("climber", at(7.0, 3.5), 15.0)
        self.put("seesaw", at(1.0, -0.5), yaw_along(*u))
        for k in (-1.0, 1.0):
            self.put("bench", at(k * 11.5, -7.5), yaw_along(*v))
        corners = [at(-14.0, -10.0), at(14.0, -10.0), at(14.0, 10.0), at(-14.0, 10.0)]
        self.fence.append({"points": [list(corners[0]), list(corners[1]), list(corners[2]), list(corners[3]), list(corners[0])],
                           "height": 0.9, "gaps": [[3, 0.42, 0.58]]})
        self.features.append((pg[0], pg[1], 16.0))
        # --- ограда по краю сквера с воротами на дорожки (к зданию — открыто)
        self.fence.append({"points": arc(a0, a1, r1, 2.5), "height": 1.6,
                           "gaps": self._gaps_on(arc(a0, a1, r1, 2.5))})
        for edge in (a0, a1):
            line = [[round(v, 2) for v in q] for q in resample([polar(edge, r0 + 2.0), polar(edge, r1)], 2.5)]
            self.fence.append({"points": line, "height": 1.6, "gaps": self._gaps_on(line)})
        # --- лавочки, урны и парковые фонари вдоль дорожек
        for p in self.paths:
            pts = resample([tuple(q) for q in p["points"]], 1.0)
            total = len(pts)
            k = 6
            side = 1.0
            while k < total - 6:
                a, b = pts[k - 1], pts[k + 1]
                dl = math.dist(a, b) or 1.0
                dx, dz = (b[0] - a[0]) / dl, (b[1] - a[1]) / dl
                off = p["width"] * 0.5 + 0.7
                q = (pts[k][0] - dz * off * side, pts[k][1] + dx * off * side)
                # отступ меньше выноса от края дорожки — иначе своя же дорожка «занимает» место
                if self._free(q, 0.5):
                    if (k // 14) % 2 == 0:
                        self.put("bench", q, yaw_along(dz * side, -dx * side))
                        if rng.random() < 0.4:
                            self.put("bin", (q[0] + dx * 1.4, q[1] + dz * 1.4))
                    else:
                        self.put("lamp_park", q, 0.0)
                    self.features.append((q[0], q[1], 1.5))
                k += 14
                side = -side
        # --- живая изгородь вдоль главной аллеи между площадями
        for r in range(int(r0) + 6, int(r1) - 4, 5):
            for sgn in (-1.0, 1.0):
                q = polar(FOUNTAIN[0] + sgn * math.degrees(4.6 / r), r)
                if self._free(q, 1.5) and abs(r - FOUNTAIN[1]) > 18.0:
                    self.put("hedge", q, yaw_along(math.cos(math.radians(FOUNTAIN[0])), math.sin(math.radians(FOUNTAIN[0]))))
        # --- деревья: аллейные рядами вдоль главной аллеи и россыпью по газонам
        for r in range(int(r0) + 8, int(r1) - 6, 9):
            for sgn in (-1.0, 1.0):
                q = polar(FOUNTAIN[0] + sgn * math.degrees(7.5 / r), r)
                if self._free(q, 2.5):
                    self.trees.append([round(q[0], 2), round(q[1], 2)])
        tries = 0
        while len(self.trees) < 170 and tries < 6000:
            tries += 1
            q = polar(rng.uniform(a0 + 1.5, a1 - 1.5), rng.uniform(r0 + 5.0, r1 - 4.0))
            if self._free(q, 3.0) and all(math.dist(q, t) > 6.0 for t in self.trees):
                self.trees.append([round(q[0], 2), round(q[1], 2)])
        return {"paths": self.paths, "plazas": self.plazas, "fence": self.fence, "trees": self.trees,
                "fountain": [round(fc[0], 2), round(fc[1], 2), 7.0], "wheel": [round(wp[0], 2), round(wp[1], 2), WHEEL[0]],
                "playground": {"at": [round(pg[0], 2), round(pg[1], 2)], "size": [28.0, 20.0], "yaw": PLAYGROUND[0] + 90.0}}

    def _gaps_on(self, line) -> list:
        """Ворота в ограде там, где к ней подходят дорожки: [номер отрезка, доля от, доля до]."""
        gaps = []
        for i, (a, b) in enumerate(zip(line, line[1:])):
            mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
            for p in self.paths:
                if poly_dist(mid, p["points"]) < p["width"] * 0.5 + 2.5:
                    gaps.append([i, 0.0, 1.0])
                    break
        return gaps

    def _free(self, q, margin: float) -> bool:
        for p in self.paths:
            if poly_dist(q, p["points"]) < p["width"] * 0.5 + margin:
                return False
        for x, z, r in self.features:
            if math.hypot(q[0] - x, q[1] - z) < r + margin * 0.5:
                return False
        for b in self.plan["buildings"]:
            if math.dist(q, b["at"]) < max(b["size"]) * 0.6 + margin:
                return False
        return True


MONUMENT_P = polar(*MONUMENT)


def make_park(lay) -> dict:
    return Park(lay).build()
