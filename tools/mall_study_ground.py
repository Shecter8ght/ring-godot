"""Покрытия земли черновика территории ТЦ (владелец, 2026-10-17: «всё зелёное, будто ТЦ стоит в поле —
не хватает сегментации поверхности земли»).

  площадки (zones) — чёткие края, как сделал человек: щебень техкомплекса, гаражей и КПП, бетон
                     контейнерной площадки, АЗС и автостанции, асфальт у кафе, грунт стройки;
  пятна (soil)     — мягкие края: вытоптанная земля у опор ЛЭП, у стоянки, у постов, на точках
                     появления и выходах, гарь у аварии и воронки, грязь у брода;
  тропы (paths)    — грунтовые тропинки по подходам A–E там, где они идут не по дороге, вдоль речки,
                     от гаражей и стройки к кольцевой, к мостику и стоянке.
Остальную землю красит MallLandscape по высоте, уклону, влажности и шуму: трава, сухостой,
проплешины, у воды — грязь и песок, на крутых склонах — глина и камень, в лесу — подстилка.

Координаты игры: X — восток, Z — юг.
"""

from __future__ import annotations

import math

# виды мягких пятен — номера совпадают с MallLandscape.SOIL_COLORS
DIRT, GRAVEL, MUD, SAND, DRY, BURNT = range(6)

# площадки: вид, центр x, z, ширина (X), глубина (Z), поворот°
ZONES = [
    ("gravel", 305.0, -150.0, 124.0, 98.0, 0.0, "техкомплекс: котельная, генераторы, башня, ТП, склад"),
    ("gravel", 330.5, 55.0, 52.0, 40.0, 0.0, "гаражи"),
    ("concrete", 351.0, -45.0, 48.0, 44.0, 0.0, "контейнерная площадка"),
    ("gravel", -346.0, -25.0, 70.0, 58.0, 0.0, "КПП ЧВК"),
    ("concrete", -250.0, -194.0, 70.0, 52.0, 0.0, "АЗС"),
    ("asphalt", 276.0, 255.0, 78.0, 60.0, 0.0, "кафе и мойка"),
    ("concrete", -159.0, 280.0, 84.0, 32.0, 0.0, "автостанция: павильон и перроны"),
    ("dirt", 35.0, -290.0, 142.0, 50.0, 0.0, "стройка второй очереди"),
]
PATH_WIDTH = 1.7


def seg_dist(p, a, b) -> float:
    dx, dz = b[0] - a[0], b[1] - a[1]
    l2 = dx * dx + dz * dz
    t = 0.0 if l2 == 0.0 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dz) / l2))
    return math.hypot(p[0] - (a[0] + t * dx), p[1] - (a[1] + t * dz))


def poly_dist(p, pts) -> float:
    return min(seg_dist(p, a, b) for a, b in zip(pts, pts[1:]))


def densify(pts, step: float = 2.0):
    out = []
    for a, b in zip(pts, pts[1:]):
        n = max(1, int(math.dist(a, b) / step))
        for i in range(n):
            t = i / n
            out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
    out.append(tuple(pts[-1]))
    return out


def in_arc(a: float, a0: float, a1: float) -> bool:
    return (a - a0) % 360.0 <= (a1 - a0) % 360.0


class Ground:
    def __init__(self, plan: dict):
        self.plan = plan
        self.zones: list[dict] = []
        self.soil: list[list[float]] = []
        self.paths: list[list] = []

    def paved(self, p) -> bool:
        """На дороге, площадке, площади, парковке, в здании — тропа не нужна."""
        plan = self.plan
        r = math.hypot(*p)
        a = math.degrees(math.atan2(p[1], p[0]))
        if r < plan["mall"]["fire_lane"][1] + 1.0:
            return True
        for road in plan["roads"]:
            if road["id"] == "loop":
                if abs(r - plan["mall"]["loop_r"]) < road["width"] * 0.5 + 1.0:
                    return True
            elif poly_dist(p, road["points"]) < road["width"] * 0.5 + 1.0:
                return True
        if poly_dist(p, plan["alley"]["points"]) < plan["alley"]["width"] * 0.5 + 0.5:
            return True
        for part in plan["gallery"]["parts"]:
            if poly_dist(p, part) < plan["gallery"]["width"] * 0.5 + 0.5:
                return True
        for c in plan["crossings"]:
            if poly_dist(p, c["points"]) < c["width"] * 0.5 + 1.0:
                return True
        for park in plan["parkings"]:
            if in_arc(a, *park["a"]) and park["r"][0] <= r <= park["r"][1]:
                return True
        pl = plan["plaza"]
        if in_arc(a, *pl["a"]) and pl["r"][0] <= r <= pl["r"][1]:
            return True
        yd = plan["yard"]
        if in_arc(a, *yd["a"]) and yd["r"][0] - 2.0 <= r <= yd["r"][1] + 2.0:
            return True
        hw = plan["highway"]
        if abs(p[1] - hw["z"]) < hw["width"] * 0.5 + 1.0:
            return True
        for kind, cx, cz, w, h, yaw, _ in ZONES:
            if abs(p[0] - cx) < w / 2 and abs(p[1] - cz) < h / 2:
                return True
        return False

    def path(self, pts) -> None:
        """Тропа по ломаной — куски вне дорог и площадок."""
        current = []
        for p in densify(pts, 2.0):
            if self.paved(p):
                if len(current) > 1:
                    self.paths.append(current)
                current = []
            else:
                current.append([round(p[0], 2), round(p[1], 2)])
        if len(current) > 1:
            self.paths.append(current)

    def build(self) -> None:
        plan = self.plan
        for kind, cx, cz, w, h, yaw, label in ZONES:
            self.zones.append({"kind": kind, "rect": [cx, cz, w, h, yaw], "label": label})
        for route in plan["probe_routes"]:
            self.path(route["points"])
        # тропы, которые натоптали бы: вдоль восточного берега речки, к мостику у АЗС, от стоянки к АЗС,
        # от гаражей и контейнеров к кольцевой, от ворот стройки к кольцевой, от поста у съезда к кафе
        river = plan.get("relief", {}).get("river", {})
        if river:
            pts = river["points"]
            bank = []
            for a, b in zip(pts, pts[1:]):
                d = math.dist(a, b)
                nx, nz = (b[1] - a[1]) / d, -(b[0] - a[0]) / d  # влево от хода — при ходе на юг это восток
                for t in (0.0, 0.5):
                    q = (a[0] + (b[0] - a[0]) * t + nx * 13.0, a[1] + (b[1] - a[1]) * t + nz * 13.0)
                    bank.append(q)
            self.path([q for q in bank if -260.0 < q[1] < 280.0])
            for bridge in river.get("bridges", []):
                if bridge["kind"] == "foot":
                    end = (bridge["at"][0] + 14.0, bridge["at"][1] + 2.0)
                    self.path([end, (-262.0, -170.0)])
        self.path([(-205.0, -240.0), (-222.0, -222.0), (-238.0, -212.0)])
        self.path([(326.0, 36.0), (300.0, 30.0), (262.0, 22.0)])
        self.path([(340.0, -24.0), (300.0, -10.0), (262.0, -8.0)])
        self.path([(31.0, -264.0), (28.0, -258.0)])
        self.path([(232.0, 262.0), (238.0, 250.0)])
        # мягкие пятна: у опор ЛЭП — вытоптано, у поста и стоянки — земля, гарь у аварии, воронки и колонны
        filler = plan.get("filler", {})
        for x, z in filler.get("lines", {}).get("power", {}).get("towers", []):
            self.soil.append([x, z, 7.0, DIRT])
        for story in filler.get("stories", []):
            x, z = story["at"]
            kind = BURNT if story["label"] in ("Авария на трассе", "Воронка", "Брошенная колонна") else DIRT
            self.soil.append([x, z, 9.0 if kind == BURNT else 6.0, kind])
        for s in plan["spawns"]:
            self.soil.append([s["at"][0], s["at"][1], 6.0, DIRT])
        for e in plan["exits"]:
            self.soil.append([e["at"][0], e["at"][1], 5.0, GRAVEL])
        for ford in river.get("fords", []) if river else []:
            self.soil.append([ford["at"][0], ford["at"][1], 14.0, MUD])
        self.soil.append([-120.0, -257.0, 10.0, SAND])  # пляжик на южном берегу водоёма
        # пятна уплотнения: грядки дач, пустыри, развалины, ремонт дороги, рыжая трава над теплотрассой
        self.soil += filler.get("soil", [])
        self.soil = [[round(v, 2) if isinstance(v, float) else v for v in s] for s in self.soil]


def make_ground(plan: dict) -> tuple[dict, dict]:
    gr = Ground(plan)
    gr.build()
    ground = {"zones": gr.zones, "soil": gr.soil, "paths": gr.paths, "path_width": PATH_WIDTH}
    stats = {"zones": len(gr.zones), "soil": len(gr.soil), "paths": len(gr.paths),
             "path_m": round(sum(sum(math.dist(a, b) for a, b in zip(p, p[1:])) for p in gr.paths))}
    return ground, stats
