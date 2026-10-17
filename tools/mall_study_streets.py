"""Дорожная обстановка черновика территории ТЦ (владелец, 2026-10-17: «система дорог бедная — не хватает
знаков, светофоров, перекрёстков, отбойников, ограничителей»).

  перекрёстки — площадки скругления, стоп-линии на второстепенных, у главных съездов — светофоры;
  разметка    — осевая прерывистая, краевые сплошные, полосы трассы, «зебры» переходов;
  бордюры     — вдоль главных дорог (с разрывами под съезды), на местных проездах — обочина;
  отбойники   — металлические по краям трассы и у моста, бетонный разделитель посередине трассы;
  знаки       — «уступи дорогу», «пешеходный переход», ограничение скорости, «парковка», «остановка»,
                указатели и портал над трассой; часть стоек погнута;
  свет        — фонари вдоль кольцевой и въездов, мачты на парковках, парковые фонари на аллее;
  ограничители — столбики у площади и аллеи, сигнальные столбики вдоль загородных дорог, шлагбаумы КПП;
  провода     — опоры 0,4/10 кВ вдоль загородных дорог к АЗС, КПП, техкомплексу и гаражам.

Координаты игры: X — восток, Z — юг. Правостороннее движение: правая сторона от хода (dx, dz) — (−dz, dx).
Наборы (kit) — в src/blockout/mall_filler.gd, линии (разметка, бордюры, отбойники, опоры) рисует
src/blockout/mall_streets.gd.
"""

from __future__ import annotations

import math
import random

SEED = 20261018
LOOP_LAMP_STEP = 36.0     # фонари вдоль кольцевой, м
ENTRY_LAMP_STEP = 26.0    # вдоль въездов
MAST_STEP = 62.0          # мачты освещения на парковке, по дуге
POLE_STEP = 40.0          # опоры проводов
DELINEATOR_STEP = 25.0    # сигнальные столбики вдоль загородных дорог
SPEED_SIGN_STEP = 320.0   # ограничение скорости на кольцевой
LEAN_SHARE = 0.18         # доля погнутых стоек знаков


def yaw_along(dx: float, dz: float) -> float:
    """Поворот, при котором локальная Z набора смотрит вдоль (dx, dz)."""
    return math.degrees(math.atan2(dx, dz))


def unit(a, b):
    d = math.dist(a, b) or 1.0
    return (b[0] - a[0]) / d, (b[1] - a[1]) / d


def right_of(d):
    return -d[1], d[0]


def seg_dist(p, a, b) -> float:
    dx, dz = b[0] - a[0], b[1] - a[1]
    l2 = dx * dx + dz * dz
    t = 0.0 if l2 == 0.0 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dz) / l2))
    return math.hypot(p[0] - (a[0] + t * dx), p[1] - (a[1] + t * dz))


def poly_dist(p, pts) -> float:
    return min(seg_dist(p, a, b) for a, b in zip(pts, pts[1:]))


def length(pts) -> float:
    return sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))


def along(pts, s: float):
    """Точка и направление на расстоянии s вдоль ломаной."""
    for a, b in zip(pts, pts[1:]):
        d = math.dist(a, b)
        if s <= d or (a, b) == (pts[-2], pts[-1]):
            t = 0.0 if d == 0.0 else min(1.0, max(0.0, s / d))
            return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t), unit(a, b)
        s -= d
    return tuple(pts[-1]), unit(pts[-2], pts[-1])


def sample(pts, step: float, start: float = 0.0, end_gap: float = 0.0):
    """Точки ломаной с шагом step: (s, точка, направление)."""
    total = length(pts)
    s = start
    out = []
    while s <= total - end_gap + 1e-6:
        p, d = along(pts, s)
        out.append((s, p, d))
        s += step
    return out


def offset_points(pts, off: float, step: float = 3.0):
    """Ломаная, сдвинутая вправо от хода на off, с шагом step (для дуг — плавно)."""
    out = []
    for _, p, d in sample(pts, step):
        r = right_of(d)
        out.append([round(p[0] + r[0] * off, 2), round(p[1] + r[1] * off, 2)])
    end, d = along(pts, length(pts))
    r = right_of(d)
    last = [round(end[0] + r[0] * off, 2), round(end[1] + r[1] * off, 2)]
    if not out or math.dist(out[-1], last) > 0.3:
        out.append(last)
    return out


def split_by(points, blocked) -> list[list]:
    """Куски ломаной, где blocked(точка) ложно (точки уже частые)."""
    pieces, current = [], []
    for p in points:
        if blocked(p):
            if len(current) > 1:
                pieces.append(current)
            current = []
        else:
            current.append(p)
    if len(current) > 1:
        pieces.append(current)
    return pieces


class Streets:
    def __init__(self, plan: dict):
        self.plan = plan
        self.rng = random.Random(SEED)
        self.items: list[list] = []
        self.marks: list[dict] = []
        self.curbs: list[list] = []
        self.rails: list[dict] = []
        self.pads: list[list[float]] = []
        self.poles: list[list] = []
        self.roads = {r["id"]: r for r in plan["roads"]}
        self.loop_r = plan["mall"]["loop_r"]
        self.loop_w = float(self.roads["loop"]["width"])
        self.hw = plan["highway"]
        self.junctions = self._junctions()
        self.crossings = plan.get("crossings", [])

    # ---------------------------------------------------------- запись

    def put(self, kit: str, p, yaw: float, s: float = 1.0, roll: float = 0.0) -> None:
        item = [kit, round(p[0], 2), round(p[1], 2), round(yaw % 360.0, 1)]
        if s != 1.0 or roll != 0.0:
            item += [round(s, 2), 0.0, -1, round(roll, 1)]
        self.items.append(item)

    def sign(self, kit: str, p, facing) -> None:
        """Знак лицом к тем, кто едет навстречу facing (его ход); часть стоек погнута."""
        roll = self.rng.choice((-1.0, 1.0)) * self.rng.uniform(6.0, 16.0) if self.rng.random() < LEAN_SHARE else 0.0
        self.put(kit, p, yaw_along(-facing[0], -facing[1]), roll=roll)

    def mark(self, pts, width: float, dash=None, color: str = "stripe") -> None:
        self.marks.append({"points": [[round(x, 2), round(z, 2)] for x, z in pts], "width": width,
                           "dash": dash, "color": color})

    # ---------------------------------------------------------- перекрёстки

    def _junctions(self) -> list[dict]:
        """Где концы дорог упираются в кольцевую, трассу, пожарный проезд или другую дорогу.
        Запись: точка, главная дорога, второстепенная, ход второстепенной к перекрёстку."""
        out = []
        lane = self.plan["mall"]["fire_lane"]
        for road in self.plan["roads"]:
            if road["id"] == "loop":
                continue
            pts = road["points"]
            for end, nxt in ((pts[0], pts[1]), (pts[-1], pts[-2])):
                d = unit(nxt, end)  # к перекрёстку
                r = math.hypot(*end)
                main = None
                if abs(r - self.loop_r) < 2.0:
                    main = "loop"
                elif abs(end[1] - self.hw["z"]) < 2.0:
                    main = "highway"
                elif abs(r - lane[1]) < 2.0:
                    main = "fire_lane"
                else:
                    for other in self.plan["roads"]:
                        if other is road or other["id"] == "loop":
                            continue
                        if poly_dist(end, other["points"]) < float(other["width"]) * 0.5 + 1.0:
                            main = other["id"]
                            break
                if main:
                    out.append({"at": end, "main": main, "minor": road["id"], "dir": d, "width": float(road["width"])})
        return out

    def main_width(self, main: str) -> float:
        if main == "loop":
            return self.loop_w
        if main == "highway":
            return float(self.hw["width"])
        if main == "fire_lane":
            lane = self.plan["mall"]["fire_lane"]
            return lane[1] - lane[0]
        return float(self.roads[main]["width"])

    def junction_work(self) -> None:
        for j in self.junctions:
            at, d, w = j["at"], j["dir"], j["width"]
            mw = self.main_width(j["main"])
            # площадка скругления углов: съезд расширяется к главной дороге
            if j["main"] != "highway":
                self.pads.append([round(at[0], 2), round(at[1], 2), round(w * 0.5 + 4.0, 1)])
            if j["main"] == "fire_lane":
                continue
            # стоп-линия на правой половине второстепенной, в метре от края главной
            r = right_of(d)
            back = mw * 0.5 + 1.0
            c = (at[0] - d[0] * back, at[1] - d[1] * back)
            self.mark([(c[0] + r[0] * 0.2, c[1] + r[1] * 0.2), (c[0] + r[0] * (w * 0.5 - 0.3), c[1] + r[1] * (w * 0.5 - 0.3))], 0.4)
            # «уступи дорогу» справа, на обочине перед перекрёстком
            sp = (at[0] - d[0] * (back + 5.0) + r[0] * (w * 0.5 + 1.2), at[1] - d[1] * (back + 5.0) + r[1] * (w * 0.5 + 1.2))
            self.sign("sign_yield", sp, d)
            # светофоры на главных съездах с кольцевой (выключены — света нет)
            if j["main"] == "loop" and self.roads[j["minor"]].get("class") == "main":
                self.put("traffic_light", (at[0] - d[0] * (back + 1.5) + r[0] * (w * 0.5 + 0.9),
                                           at[1] - d[1] * (back + 1.5) + r[1] * (w * 0.5 + 0.9)), yaw_along(-d[0], -d[1]))
                # на кольцевой — по светофору с каждой стороны съезда, лицом к едущим по кольцу
                tang = (-at[1] / self.loop_r, at[0] / self.loop_r)  # ход кольца против часовой (по углу)
                for sgn in (1.0, -1.0):
                    t = (tang[0] * sgn, tang[1] * sgn)
                    rr = right_of(t)
                    q = (at[0] - t[0] * (w * 0.5 + 6.0) + rr[0] * (mw * 0.5 + 0.9),
                         at[1] - t[1] * (w * 0.5 + 6.0) + rr[1] * (mw * 0.5 + 0.9))
                    self.put("traffic_light", q, yaw_along(-t[0], -t[1]))

    def near_junction(self, p, extra: float = 0.0) -> bool:
        return any(math.dist(p, j["at"]) < j["width"] * 0.5 + 4.5 + extra for j in self.junctions)

    def near_crossing(self, p, extra: float = 0.0) -> bool:
        return any(poly_dist(p, c["points"]) < c["width"] * 0.5 + extra for c in self.crossings)

    # ---------------------------------------------------------- разметка, бордюры

    def lines(self) -> None:
        for road in self.plan["roads"]:
            pts, w = road["points"], float(road["width"])
            main = road.get("class") == "main"
            if road["id"] == "car_wash_drive":
                continue
            # осевая прерывистая (3 м штрих, 6 м разрыв); у перекрёстков и переходов — нет
            axis = offset_points(pts, 0.0, 1.5)
            for piece in split_by(axis, lambda p: self.near_junction(p, -1.0) or self.near_crossing(p, 1.0)):
                self.mark(piece, 0.12, [3.0, 6.0])
            if not main:
                continue
            # краевые сплошные и бордюр; у съездов — разрыв
            for side in (1.0, -1.0):
                edge = offset_points(pts, side * (w * 0.5 - 0.35), 1.5)
                for piece in split_by(edge, lambda p: self.near_junction(p, 1.5) or self.near_crossing(p, 0.5)):
                    self.mark(piece, 0.12)
                curb = offset_points(pts, side * (w * 0.5 + 0.12), 1.5)
                for piece in split_by(curb, lambda p: self.near_junction(p, 2.5)):
                    self.curbs.append(piece)
        # «зебры» переходов: полосы 0,5 м через 0,5 м, вдоль дороги — на ширину перехода
        for c in self.crossings:
            a, b = c["points"]
            d = unit(a, b)
            r = right_of(d)
            n = int(math.dist(a, b) / 1.0)
            for i in range(n):
                q = (a[0] + d[0] * (i + 0.5), a[1] + d[1] * (i + 0.5))
                half = c["width"] * 0.5
                self.mark([(q[0] - r[0] * half, q[1] - r[1] * half), (q[0] + r[0] * half, q[1] + r[1] * half)], 0.5)

    def highway_lines(self) -> None:
        hw = self.hw
        z, half = float(hw["z"]), float(hw["width"]) * 0.5
        x0, x1 = float(hw["x"][0]), float(hw["x"][1])
        gap = hw["crossing_x"]
        for zz in (z - 6.0, z + 6.0):
            self.mark([(x0, zz), (x1, zz)], 0.15, [9.0, 3.0])
        for zz in (z - half + 0.5, z + half - 0.5):
            self.mark([(x0, zz), (x1, zz)], 0.15)
        # металлические отбойники по краям; с севера — разрывы под съезды, у пешеходного пропуска — с обеих
        exits = [j["at"][0] for j in self.junctions if j["main"] == "highway"]
        for zz, north in ((z - half - 0.6, True), (z + half + 0.6, False)):
            pieces = []
            cur = [x0 + 2.0]
            cuts = [(gap[0] - 2.0, gap[1] + 2.0)] + ([(x - 9.0, x + 9.0) for x in exits] if north else [])
            for c0, c1 in sorted(cuts):
                pieces.append((cur[0], c0))
                cur = [c1]
            pieces.append((cur[0], x1 - 2.0))
            for a, b in pieces:
                if b - a > 4.0:
                    self.rails.append({"kind": "wbeam", "points": [[round(a, 2), zz], [round(b, 2), zz]]})
        # бетонный разделитель посередине; у пропуска — разрыв
        self.rails.append({"kind": "jersey", "points": [[x0, z], [gap[0] - 1.0, z]]})
        self.rails.append({"kind": "jersey", "points": [[gap[1] + 1.0, z], [x1, z]]})
        # портал с указателями над трассой у обоих съездов — ориентир издалека
        for x in (min(exits) - 110.0, max(exits) + 110.0):
            self.put("gantry", (x, z), 90.0)
        # ограничение скорости в обе стороны
        for x in (-300.0, 60.0, 400.0):
            self.sign("sign_speed", (x, z - half - 1.8), (-1.0, 0.0))
            self.sign("sign_speed", (x + 20.0, z + half + 1.8), (1.0, 0.0))

    def bridge_rails(self) -> None:
        """Отбойники на восточном подходе к дорожному мосту через речку (с запада — змейка КПП, и туда
        с поля выходит подход B)."""
        river = self.plan.get("relief", {}).get("river", {})
        for bridge in river.get("bridges", []):
            if bridge["kind"] != "road":
                continue
            at = bridge["at"]
            yaw = math.radians(bridge["yaw"])
            along_r = (math.sin(yaw), math.cos(yaw))   # вдоль русла
            across = (-along_r[1], along_r[0])          # вдоль моста
            half_w = bridge["width"] * 0.5 - 0.3
            for side in (1.0, -1.0):
                for end, span in ((bridge["half_left"], 1.0), (bridge["half_right"], -1.0)):
                    a = (at[0] + across[0] * end * span + along_r[0] * half_w * side, at[1] + across[1] * end * span + along_r[1] * half_w * side)
                    b = (a[0] + across[0] * 22.0 * span, a[1] + across[1] * 22.0 * span)
                    if b[0] < at[0]:
                        continue
                    self.rails.append({"kind": "wbeam", "points": [[round(a[0], 2), round(a[1], 2)], [round(b[0], 2), round(b[1], 2)]]})

    # ---------------------------------------------------------- знаки, свет, ограничители

    def loop_furniture(self) -> None:
        pts = self.roads["loop"]["points"]
        inner = self.loop_r - self.loop_w * 0.5 - 1.3
        total = length(pts)
        for s, p, d in sample(pts, LOOP_LAMP_STEP, 5.0):
            q = (p[0] / self.loop_r * inner, p[1] / self.loop_r * inner)
            if self.near_junction(q, 2.0) or self.near_crossing(q, 2.0):
                continue
            # стрела фонаря — к дороге (наружу)
            self.put("lamp", q, yaw_along(p[0], p[1]))
        # ограничение скорости — по ходу в обе стороны
        for s in range(40, int(total), int(SPEED_SIGN_STEP)):
            p, d = along(pts, float(s))
            for sgn in (1.0, -1.0):
                t = (d[0] * sgn, d[1] * sgn)
                r = right_of(t)
                q = (p[0] + r[0] * (self.loop_w * 0.5 + 1.4), p[1] + r[1] * (self.loop_w * 0.5 + 1.4))
                if not self.near_junction(q, 6.0) and not self.near_crossing(q, 6.0):
                    self.sign("sign_speed", q, t)

    def entry_furniture(self) -> None:
        for road in self.plan["roads"]:
            if road["id"] in ("loop", "car_wash_drive"):
                continue
            pts, w = road["points"], float(road["width"])
            main = road.get("class") == "main"
            inside = all(math.hypot(*p) <= self.loop_r + 2.0 for p in pts)
            if main and inside:
                # фонари вдоль въездов к зданию — в шахматном порядке
                for k, (s, p, d) in enumerate(sample(pts, ENTRY_LAMP_STEP, 8.0, 6.0)):
                    side = 1.0 if k % 2 == 0 else -1.0
                    r = right_of(d)
                    q = (p[0] + r[0] * side * (w * 0.5 + 1.2), p[1] + r[1] * side * (w * 0.5 + 1.2))
                    if not self.near_junction(q, 1.0):
                        self.put("lamp", q, yaw_along(-r[0] * side, -r[1] * side))
            if not inside and road["id"] not in ("to_bus_station", "bus_access"):
                # загородные: сигнальные столбики по обеим обочинам
                for s, p, d in sample(pts, DELINEATOR_STEP, 6.0, 6.0):
                    r = right_of(d)
                    for side in (1.0, -1.0):
                        q = (p[0] + r[0] * side * (w * 0.5 + 1.0), p[1] + r[1] * side * (w * 0.5 + 1.0))
                        if not self.near_junction(q, 2.0) and math.hypot(q[0], q[1]) > self.loop_r + 8.0:
                            self.put("delineator", q, yaw_along(d[0], d[1]))
        # «парковка» у въездов на южную парковку
        for road_id in ("parking_in_55", "parking_in_125"):
            pts = self.roads[road_id]["points"]
            p, d = along(pts, 12.0)
            r = right_of(d)
            self.sign("sign_parking", (p[0] + r[0] * 5.0, p[1] + r[1] * 5.0), d)

    def crossing_furniture(self) -> None:
        for c in self.crossings:
            a, b = c["points"]
            d = unit(a, b)
            r = right_of(d)
            half = c["width"] * 0.5
            for end, out in ((a, (-d[0], -d[1])), (b, d)):
                # знак «пешеходный переход» с обеих сторон, лицом к машинам на своей полосе
                q = (end[0] + out[0] * 1.2 - r[0] * (half + 0.8), end[1] + out[1] * 1.2 - r[1] * (half + 0.8))
                self.sign("sign_crossing", q, (r[0], r[1]) if end is a else (-r[0], -r[1]))
                if c.get("lights"):
                    q2 = (end[0] + out[0] * 1.0 + r[0] * (half + 0.8), end[1] + out[1] * 1.0 + r[1] * (half + 0.8))
                    self.put("traffic_light", q2, yaw_along(-r[0], -r[1]) if end is a else yaw_along(r[0], r[1]))
                    self.put("ped_light", (end[0] + out[0] * 1.0 - r[0] * (half + 0.4), end[1] + out[1] * 1.0 - r[1] * (half + 0.4)),
                             yaw_along(-out[0], -out[1]))

    def plaza_furniture(self) -> None:
        """Аллея: парковые фонари, скамейки, урны, вазоны; столбики по краям; у площади — столбики
        поперёк пожарного проезда."""
        alley = self.plan["alley"]
        pts, w = alley["points"], float(alley["width"])
        for k, (s, p, d) in enumerate(sample(pts, 18.0, 6.0, 4.0)):
            r = right_of(d)
            for side in (1.0, -1.0):
                q = (p[0] + r[0] * side * (w * 0.5 - 0.6), p[1] + r[1] * side * (w * 0.5 - 0.6))
                if k % 2 == 0:
                    self.put("lamp_park", q, yaw_along(d[0], d[1]))
                else:
                    self.put("bench", (q[0] - r[0] * side * 0.4, q[1] - r[1] * side * 0.4), yaw_along(-r[0] * side, -r[1] * side))
                    self.put("bin", (q[0] + d[0] * 1.6, q[1] + d[1] * 1.6), 0.0)
        for s, p, d in sample(pts, 3.0, 2.0, 2.0):
            r = right_of(d)
            for side in (1.0, -1.0):
                q = (p[0] + r[0] * side * (w * 0.5 + 0.4), p[1] + r[1] * side * (w * 0.5 + 0.4))
                if not self._on_ramp(q):
                    self.put("bollard", q, 0.0)
        # пожарный проезд у краёв площади — поперёк него столбики (машинам на площадь нельзя)
        pl, lane = self.plan["plaza"], self.plan["mall"]["fire_lane"]
        for a in pl["a"]:
            for k in range(5):
                rr = lane[0] + 1.0 + k * (lane[1] - lane[0] - 2.0) / 4.0
                q = (rr * math.cos(math.radians(a)), rr * math.sin(math.radians(a)))
                self.put("bollard", q, 0.0)

    def _on_ramp(self, p) -> bool:
        t = self.plan["terraces"]
        r = math.hypot(*p)
        return any(abs(r - w) < t["ramp_len"] * 0.5 for w in t["walls"])

    def parking_masts(self) -> None:
        """Мачты освещения в проездах между рядами парковок."""
        t = self.plan["terraces"]
        for park in self.plan["parkings"]:
            a0, a1 = park["a"]
            span = (a1 - a0) % 360.0
            r0, r1 = park["r"]
            rad = r0 + 14.0
            while rad < r1 - 6.0:
                if all(abs(rad - w) > 6.0 for w in t["walls"]):
                    n = max(1, int(math.radians(span) * rad / MAST_STEP))
                    for i in range(n):
                        a = a0 + span * (i + 0.5) / n
                        q = (rad * math.cos(math.radians(a)), rad * math.sin(math.radians(a)))
                        if self._clear(q, 4.0):
                            self.put("mast", q, a)
                rad += 32.0

    def _clear(self, q, margin: float) -> bool:
        """Не на дороге, не на аллее и не под галереей, не у постройки."""
        for road in self.plan["roads"]:
            if road["id"] == "loop":
                if abs(math.hypot(*q) - self.loop_r) < self.loop_w * 0.5 + margin:
                    return False
            elif poly_dist(q, road["points"]) < float(road["width"]) * 0.5 + margin:
                return False
        if poly_dist(q, self.plan["alley"]["points"]) < self.plan["alley"]["width"] * 0.5 + margin:
            return False
        for part in self.plan["gallery"]["parts"]:
            if poly_dist(q, part) < self.plan["gallery"]["width"] * 0.5 + margin:
                return False
        for b in self.plan["buildings"]:
            if math.dist(q, b["at"]) < max(b["size"]) * 0.6 + margin:
                return False
        return True

    def bus_stops(self) -> None:
        """Остановки на кольцевой у аллеи и у въезда к автостанции: павильон, знак, урна, киоск."""
        for a, label in ((84.0, "alley"), (136.0, "bus")):
            r = self.loop_r + self.loop_w * 0.5 + 3.2
            p = (r * math.cos(math.radians(a)), r * math.sin(math.radians(a)))
            # ход по наружной полосе — по часовой (правостороннее)
            t = (math.sin(math.radians(a)), -math.cos(math.radians(a)))
            # стенка павильона — к полю, открытая сторона (локальная +Z) — к дороге
            self.put("bus_stop", p, yaw_along(-p[0], -p[1]))
            q = (p[0] - t[0] * 5.0, p[1] - t[1] * 5.0)
            self.sign("sign_bus", (q[0] - p[0] / r * 1.5, q[1] - p[1] / r * 1.5), t)
            self.put("bin", (p[0] + t[0] * 4.0, p[1] + t[1] * 4.0), 0.0)
            k = (p[0] + t[0] * 9.0 + p[0] / r * 2.0, p[1] + t[1] * 9.0 + p[1] / r * 2.0)
            self.put("kiosk", k, yaw_along(-p[0], -p[1]))

    def checkpoint(self) -> None:
        """КПП на западной дороге: шлагбаумы на въезде и выезде, знак «стоп»."""
        road = self.roads["west_road"]["points"]
        for x in (-362.0, -322.0):
            # точка дороги на этом x
            best = min(((abs(p[0] - x), p, d) for _, p, d in sample(road, 1.0)), key=lambda e: e[0])
            p, d = best[1], best[2]
            r = right_of(d)
            w = float(self.roads["west_road"]["width"])
            post = (p[0] + r[0] * (w * 0.5 + 0.5), p[1] + r[1] * (w * 0.5 + 0.5))
            self.put("barrier_arm", post, yaw_along(-r[0], -r[1]))
        p, d = along(road, 40.0)
        r = right_of(d)
        self.sign("sign_stop", (p[0] + r[0] * 6.0, p[1] + r[1] * 6.0), d)

    # ---------------------------------------------------------- провода

    def power_poles(self) -> None:
        """Опоры с проводами вдоль загородных дорог: от края карты к КПП и кольцевой, к АЗС, вдоль
        служебной дороги к техкомплексу, от подстанции к гаражам."""
        lines = []
        for road_id, side, off in (("west_road", -1.0, 9.0), ("service_road", 1.0, 8.0), ("gas_road", -1.0, 7.5)):
            pts = self.roads[road_id]["points"]
            lines.append(offset_points(pts, side * off, POLE_STEP))
        lines.append([[262.0, -100.0], [262.0, -40.0], [300.0, 10.0], [312.0, 40.0]])
        boundary = self.plan["boundary"]
        for line in lines:
            kept = []
            for p in line:
                if self._clear(p, 2.0) and self._inside(p, boundary, 4.0):
                    kept.append([round(p[0], 2), round(p[1], 2)])
                elif len(kept) > 1:
                    self.poles.append(kept)
                    kept = []
                else:
                    kept = []
            if len(kept) > 1:
                self.poles.append(kept)

    @staticmethod
    def _inside(p, poly, margin: float) -> bool:
        inside = False
        j = len(poly) - 1
        for i in range(len(poly)):
            (xi, zi), (xj, zj) = poly[i], poly[j]
            if (zi > p[1]) != (zj > p[1]) and p[0] < (xj - xi) * (p[1] - zi) / (zj - zi) + xi:
                inside = not inside
            j = i
        return inside and min(seg_dist(p, a, b) for a, b in zip(poly, poly[1:] + poly[:1])) > margin


def make_streets(plan: dict) -> tuple[dict, dict]:
    st = Streets(plan)
    st.junction_work()
    st.lines()
    st.highway_lines()
    st.bridge_rails()
    st.loop_furniture()
    st.entry_furniture()
    st.crossing_furniture()
    st.plaza_furniture()
    st.parking_masts()
    st.bus_stops()
    st.checkpoint()
    st.power_poles()
    kits: dict[str, int] = {}
    for item in st.items:
        kits[item[0]] = kits.get(item[0], 0) + 1
    streets = {"marks": st.marks, "curbs": st.curbs, "rails": st.rails, "pads": st.pads, "poles": st.poles,
               "items": st.items, "junctions": [{"at": [round(j["at"][0], 2), round(j["at"][1], 2)], "main": j["main"],
                                                  "minor": j["minor"]} for j in st.junctions]}
    stats = {"marks": len(st.marks), "curbs": len(st.curbs), "rails": len(st.rails), "pads": len(st.pads),
             "pole_lines": len(st.poles), "junctions": len(st.junctions), "kits": kits}
    return streets, stats
