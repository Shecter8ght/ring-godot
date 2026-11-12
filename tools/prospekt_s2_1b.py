"""«Проспект», вторая очередь, этап 1б — Объездная: полотно, опоры, экраны, сходы, блоки ЧВК, низ под полотном.

Собирает патч s2_1b_ring (вызывается из tools/prospekt_patch.py). Числа — словари tools/prospekt_stage2_plan.py
(RING_*, UNDER_*, EXITS_NEW, CORDON_REAR), листы 13 и 15, §25.3 и §25.7 docs/design/prospekt_map.md.
Координаты сцены: X — восток, Z — юг, Y — вверх, метры.
"""
from __future__ import annotations

import math

import prospekt_stage2_plan as S2

X0, X1 = S2.RING_DECK                  # −246…−220
XC = -233.0                             # ось полотна: отбойник
Z_N, Z_S = -200.0, 332.0                # полотно строится за границы карты (фон): север −155,3 − 40, юг 290 + 42
H = S2.ring_h
SCREEN_H = S2.RING_SCREEN_H
WALK_X0 = -222.5                        # восточный тротуар полотна X −222,5…−220,3 (дальше — экран)
SCREEN_T = 0.3
RISE = S2.RING_RISE_Z                   # 150…250
OPEN_Z = S2.RING_OPEN_Z
LANE_E = -221.5                         # служебная тропа под полотном вдоль восточной стороны (для маршрута under_ring)
BLOCK_N_H, BLOCK_S_H = 6.0, 6.5         # блоки закрытой части выше досягаемого перелезанием (Balance.CLIMB max_h 2,0 + запас на машину)


def dy(z: float) -> float:
    return round(H(z), 2)


def ground_y(z: float) -> float:
    """Высота насыпи под путями (как у этапа 1а): откос 244…258 до +6, ровно до 290, спуск до 300."""
    if z <= 244.0:
        return 0.0
    if z <= 258.0:
        return 6.0 * (z - 244.0) / 14.0
    if z <= 290.0:
        return 6.0
    if z <= 300.0:
        return 6.0 * (1.0 - (z - 290.0) / 10.0)
    return 0.0


def line(p, kit: str, axis: str, c: float, a0: float, a1: float, step: float, gaps=(), lift=None, yaw=None) -> int:
    n = 0
    a = a0 + step / 2.0
    while a + step / 2.0 <= a1 + 0.01:
        if not any(g0 < a < g1 for g0, g1 in gaps):
            x, z = (a, c) if axis == "x" else (c, a)
            y = yaw if yaw is not None else (90.0 if axis == "x" else 0.0)
            p.put(kit, x, z, y, 1.0, lift(a if axis == "z" else z) if lift else 0.0)
            n += 1
        a += step
    return n


def cut(a0: float, a1: float, gaps) -> list[tuple[float, float]]:
    """Отрезок a0…a1 без разрывов gaps [(от, до)]."""
    out, x = [], a0
    for g0, g1 in sorted(gaps):
        if g0 > x:
            out.append((x, min(g0, a1)))
        x = max(x, g1)
    if x < a1:
        out.append((x, a1))
    return [s for s in out if s[1] - s[0] > 0.05]


def plates_row(p, z: float, x0: float, x1: float, gaps=(), h: float = 2.6, t: float = 0.8, mat: str = "concrete") -> int:
    """Ряд бетонных плит поперёк полосы (вдоль X) на земле: сплошная коробка h × t между разрывами."""
    n = 0
    for a, b in cut(x0, x1, gaps):
        p.box((a + b) / 2.0, h / 2.0, z, b - a, h, t, mat)
        n += 1
    return n


def po2_row(p, z: float, x0: float, x1: float, gaps=()) -> int:
    """Ряд плит ПО-2 (2,4 м) вдоль X: секции по 2,5 м от x0, разрыв — секция с серединой в нём не ставится."""
    return line(p, "po2", "x", z, x0, x1, 2.5, gaps=gaps)


# ------------------------------------------------------------------------------------------------ полотно
def deck(p) -> None:
    # плиты полотна по пролётам между опорами (плита 1,6 м, верх ровно по отметке). Разбивка не только вид: одной плитой
    # в 345 м проверка «пролог» застревает в чужом месте (см. STATUS), тремя — проходит
    for k, (za, zb) in enumerate(((Z_N, -65.0), (-65.0, 40.0), (40.0, RISE[0]))):
        p.slab("ring_deck_n%d" % k, [X0, za, X1, zb], S2.RING_Y, 1.6, "road")
    p.slab("ring_deck_s", [X0, RISE[1], X1, Z_S], S2.RING_Y_RAIL, 1.6, "road")
    p.add["ramps"].append({"mat": "road", "x0": X0, "x1": X1, "y0": S2.RING_Y, "y1": S2.RING_Y_RAIL, "z0": RISE[0], "z1": RISE[1]})
    for xg in (-243.5, -238.0, -228.0, -222.5):                  # продольные балки под наклонной плитой
        p.beam((xg, S2.RING_Y - 0.9, RISE[0]), (xg, S2.RING_Y_RAIL - 0.9, RISE[1]), 0.9, 1.4, "concrete")
    # восточный тротуар (выше полосы на 15 см)
    p.surface("ring_walk_n", "walk", WALK_X0, Z_N, X1 - SCREEN_T, RISE[0], S2.RING_Y, 0.15)
    p.surface("ring_walk_s", "walk", WALK_X0, RISE[1], X1 - SCREEN_T, Z_S, S2.RING_Y_RAIL, 0.15)
    p.add["ramps"].append({"mat": "walk", "x0": WALK_X0, "x1": X1 - SCREEN_T, "y0": S2.RING_Y + 0.15, "y1": S2.RING_Y_RAIL + 0.15,
                           "z0": RISE[0], "z1": RISE[1]})
    # опоры парами X −241 и −225, ригель под полотном
    for z in S2.RING_COLUMNS_Z:
        top = H(z) - 1.6
        gy = ground_y(z)
        for cx in (-241.0, -225.0):
            p.add["columns"].append({"rect": [cx, float(z), cx, float(z)], "grid": 2.0, "size": 1.8, "y0": round(gy - 0.5, 2),
                                     "y1": round(top + 0.05, 2), "mat": "concrete"})
        rtop = H(z) - (0.35 if RISE[0] <= z <= RISE[1] else 1.5)
        p.box(-233.0, rtop - 0.65, float(z), 17.8, 1.3, 1.6, "concrete")
    # старая опора-«пробка» эстакады-заглушки на проспекте мешает новому полотну — убрать
    p.remove["pieces"].append({"list": "boxes", "rect": [-226.1, -50.4, -225.9, -50.2], "mat": "concrete"})
    p.remove["pieces"].append({"list": "boxes", "rect": [-226.1, -50.4, -225.9, -50.2], "mat": "steel"})
    p.log.append("полотно: плиты Z −195…150 (+9,0) и 250…332 (+15,5), наклонная плита 150…250 с четырьмя балками, "
                 f"опор {2 * len(S2.RING_COLUMNS_Z)} с ригелями")


def screens(p) -> None:
    """Шумозащитные экраны 4 м по обоим краям; на восточном — окна-парапеты и проёмы у верхних площадок сходов."""
    t = SCREEN_T

    def seg(x0: float, x1: float, za: float, zb: float, top_h: float, bottom_extra: float = 0.05) -> None:
        p.wall(x0, za, x1, zb, round(H(za) - bottom_extra, 3), round(H(zb) + top_h, 3), "concrete")

    def run(x0: float, x1: float, cuts: list[tuple[float, float, float]]) -> int:
        """Экран по всей длине; cuts [(z0, z1, высота)] — участки пониже (окна) и высота 0 — проём полностью (+ перемычка)."""
        n = 0
        bounds = sorted(set([Z_N, RISE[0], RISE[1], Z_S] + [c for c0, c1, _ in cuts for c in (c0, c1)]))
        for a, b in zip(bounds, bounds[1:]):
            mid = (a + b) / 2.0
            hh = SCREEN_H
            door = False
            for c0, c1, ch in cuts:
                if c0 <= mid <= c1:
                    hh = ch
                    door = ch <= 0.0
            step = 2.5 if (a >= RISE[0] and b <= RISE[1]) else 30.0
            z = a
            while z < b - 0.01:
                z2 = min(z + step, b)
                if not door:                       # проём: стены нет, перемычка ставится отдельно
                    seg(x0, x1, z, z2, hh)
                    n += 1
                z = z2
        return n

    # проёмы у верхних площадок: северный сход — Z 190,7…192,0, южный — по расчёту башни (см. towers)
    doors = [(c - 0.65, c + 0.65) for c in TOWER_DOOR_Z]
    east_cuts = [(w[0], w[1], 1.0) for w in [(160.0, 166.0), (228.0, 234.0)]] + [(a, b, 0.0) for a, b in doors]
    n = run(X0, X0 + t, [])
    # проёмы: сначала убираем стену над ними, потом ставим перемычку от 2,4 м до верха экрана
    n += run(X1 - t, X1, east_cuts)
    for a, b in doors:
        zm = (a + b) / 2.0
        p.wall(X1 - t, a, X1, b, round(H(zm) + 2.4, 3), round(H(zm) + SCREEN_H, 3), "concrete")
    p.log.append(f"экраны 4 м по краям: сегментов {n}; на восточном окна-парапеты 1,0 м Z 160…166 и 228…234, проёмы у сходов {doors}")


def median(p) -> None:
    """Отбойник по оси: куски по 5 м на подъёме и по 18 м на ровном, разрывы по 3 м через ~24 м (переход с полосы на полосу)."""
    gaps = []
    zc = -170.0
    while zc < Z_S - 6.0:
        gaps.append((zc - 1.5, zc + 1.5))
        zc += 24.0
    # не лезем в блоки и в место стоянки автобуса: блок севера Z 148,4…150, колонны юга Z 258…259,8
    gaps = [g for g in gaps if not (140.0 < g[0] < 152.0 or 255.0 < g[0] < 262.0 or 230.0 < g[0] < 246.0)]
    gaps += [(242.0, 245.6), (252.0, 255.8)]           # фура и сожжённый автобус стоят поперёк оси
    n = 0
    for a, b in cut(Z_N, Z_S, gaps):
        z = a
        while z < b - 0.01:
            z2 = min(z + (5.0 if RISE[0] - 1 <= z < RISE[1] else 18.0), b)
            if z < RISE[0] < z2:
                z2 = RISE[0]
            if z < RISE[1] < z2:
                z2 = RISE[1]
            zm = (z + z2) / 2.0
            top = max(H(z), H(z2)) + 0.9
            low = min(H(z), H(z2)) - 0.3
            p.box(XC, (top + low) / 2.0, zm, 0.5, top - low, z2 - z, "concrete")
            n += 1
            z = z2
    p.log.append(f"отбойник по оси X −233: {n} кусков, разрывы по 3 м через 24 м")


# ------------------------------------------------------------------------------------------------ сходы
TOWER_DOOR_Z: list[float] = []


def _tower_defs() -> list[dict]:
    """Две башни: вход с тротуара Вокзальной на земле, наверху проём в экран на тротуар полотна. s — расстояние от входного торца."""
    out = []
    # северная: вход с юга (Z 200,2), подъём на север; южная: вход с севера (Z 214,0), подъём на юг
    for entry_z, sgn in ((200.2, -1.0), (214.0, 1.0)):
        zl = entry_z + sgn * 8.85               # центр верхней площадки
        out.append({"entry_z": entry_z, "sgn": sgn, "z_top": zl, "h_top": round(H(zl) + 0.15, 3)})
    return out


TOWERS = _tower_defs()
TOWER_DOOR_Z[:] = [t["z_top"] for t in TOWERS]


def towers(p) -> None:
    """Крытые лестничные башни X −220…−217: три марша 1,3 м «змейкой» с площадками, глухая обшивка с востока, крыша."""
    wx0, wx1 = -220.0, -217.0
    cxa, cxb = -219.2, -217.9                    # колонны маршей: западная (А, С) и восточная (В)
    L = 9.7
    for tw in TOWERS:
        sgn, ez, ht = tw["sgn"], tw["entry_z"], tw["h_top"]
        z_of = lambda s: ez + sgn * s            # noqa: E731
        zmin, zmax = (ez - L, ez) if sgn < 0 else (ez, ez + L)
        h1, h2 = ht / 3.0, 2.0 * ht / 3.0
        steps = max(6, int(round((ht / 3.0) / 0.172)))
        roof_y = ht + 3.1
        s0, s1 = 1.45, 8.25                      # длина марша 6,8 м: ступени ≥ 0,25
        # марши (перила с обеих сторон)
        for (xa, ya, sa, yb, sb) in ((cxa, 0.0, s0, h1, s1), (cxb, h1, s1, h2, s0), (cxa, h2, s0, ht, s1)):
            p.add["stairs"].append({"from": [xa, round(ya, 3), round(z_of(sa), 3)], "to": [xa, round(yb, 3), round(z_of(sb), 3)],
                                    "width": 1.3, "count": steps, "mat": "concrete", "rails": "both"})
        # площадки: нижняя (на h2), верхние (на h1 и на ht) — на обе колонны
        def landing(sa: float, sb: float, y: float, tag: str) -> None:
            za, zb = sorted((z_of(sa), z_of(sb)))
            p.slab("ring_tower_%s_%s" % (tag, str(round(ez))), [-219.85, za, -217.25, zb], round(y, 3), 0.25, "concrete")
        landing(0.25, s0, h2, "land2")
        landing(s1, 9.45, h1, "land1")
        landing(s1, 9.45, ht, "land3")
        # стены: восток глухая (до крыши), запад — с проёмом на верхней площадке, торцы; вход — дверь 1,17 × 2,42 на земле
        p.wall_z(-217.125, zmin, zmax, 0.0, roof_y, t=0.25, mat="wall")
        zt = tw["z_top"]
        p.wall_z(-219.925, zmin, zmax, 0.0, roof_y, gaps=[(zt, 1.3, ht + 2.4, ht)], t=0.15, mat="wall")
        p.wall_x(ez + sgn * 0.125, -219.85, -217.25, 0.0, roof_y, gaps=[(cxa, 1.17, 2.42)], t=0.25, mat="wall")   # торец со входом
        p.wall_x(z_of(9.575), -219.85, -217.25, 0.0, roof_y, t=0.25, mat="wall")                                   # глухой торец
        p.slab("ring_tower_roof_%s" % str(round(ez)), [wx0, zmin, wx1, zmax], round(roof_y, 3), 0.3, "concrete")
        # забор старого западного ограждения на месте башни убрать
        p.drop_items(["district_fence"], [-217.7, zmin - 0.1, -217.3, zmax + 0.1])
    p.log.append("сходы: две башни (Z 190,5…200,2 и 214,0…223,7), три марша «змейкой» по 23 и 27 ступеней, площадки, крыша, "
                 "вход с тротуара Вокзальной, проём в восточный экран на верхней площадке")


# ------------------------------------------------------------------------------------------------ верх: блоки и вещи
def deck_top(p) -> None:
    # блок ЧВК севернее открытого участка: плиты на всю ширину + два грузовика за ним
    wz0, wz1 = 148.4, 150.0
    p.box((X0 + X1) / 2.0, S2.RING_Y + BLOCK_N_H / 2.0 - 0.05, (wz0 + wz1) / 2.0, X1 - X0, BLOCK_N_H + 0.1, wz1 - wz0, "concrete")
    p.box((X0 + X1) / 2.0, S2.RING_Y + BLOCK_N_H + 0.25, wz0 + 0.3, X1 - X0, 0.5, 0.2, "dark", 0.0, False)         # колючка поверху
    p.put("truck", -238.5, 141.5, 92.0, 1.0, 9.0)
    p.put("truck", -227.0, 137.5, 85.0, 1.0, 9.0)
    p.put("sandbag_post", -229.5, 133.0, 180.0, 1.0, 9.0)
    p.put("floodlight", -243.0, 144.8, 180.0, 1.0, 9.0)
    # сгоревшая колонна на Z 258: стена плит и сожжённые машины вплотную (все ниже 3,1 м)
    sz0, sz1 = 258.0, 259.8
    p.box((X0 + X1) / 2.0, S2.RING_Y_RAIL + BLOCK_S_H / 2.0 - 0.05, (sz0 + sz1) / 2.0, X1 - X0, BLOCK_S_H + 0.1, sz1 - sz0, "concrete")
    p.box((X0 + X1) / 2.0, S2.RING_Y_RAIL + BLOCK_S_H + 0.25, sz0 + 0.3, X1 - X0, 0.5, 0.2, "dark", 0.0, False)
    y = S2.RING_Y_RAIL
    p.put("bus_wreck", -233.0, 253.8, 90.0, 1.0, y)
    p.put("car_wreck", -243.3, 254.2, 95.0, 1.0, y)
    p.put("car_wreck", -224.3, 254.6, 80.0, 1.0, y)
    p.put("car_wreck", -228.0, 250.0, 20.0, 1.0, y)
    p.put("tires", -222.0, 255.6, 0.0, 1.0, y)
    p.put("trash_pile", -236.0, 250.0, 30.0, 1.0, y)
    # остановка «Вокзальная»: павильон на восточном тротуаре, автобус у неё
    p.put("bus_stop", -221.3, 204.0, 270.0, 1.0, round(dy(204.0) + 0.15, 2))
    p.put("bus_city", -225.0, 206.0, 0.0, 1.0, dy(206.0))
    p.put("bench", -221.5, 208.3, 90.0, 1.0, round(dy(208.3) + 0.15, 2))
    # брошенные машины — укрытия по трассе (с запасом от экранов: на крышу не залезть и через экран не перелезть)
    cars = [("car", -241.0, 162.0, 8.0), ("car_wreck", -237.0, 181.5, -12.0), ("police_car", -226.0, 172.0, 170.0),
            ("car", -240.5, 205.0, 3.0), ("car_wreck", -227.0, 190.0, 15.0), ("van", -236.5, 229.0, 200.0)]
    for kit, x, z, yaw in cars:
        p.put(kit, x, z, yaw, 1.0, dy(z))
    # фура поперёк полос: прицеп и тягач, проход справа у тротуара остаётся
    p.put("trailer", -238.0, 243.8, 90.0, 1.0, dy(243.8))
    p.put("truck_cab", -228.0, 243.8, 90.0, 1.0, dy(243.8))
    # мелочь: стёкла, мусор, конусы, сорванный ограждающий щит
    for k, (kit, x, z, yaw) in enumerate([("glass_shards", -241.4, 163.5, 30.0), ("trash_pile", -238.0, 176.0, 80.0), ("bags", -229.5, 186.0, 10.0),
                                          ("glass_shards", -226.5, 173.6, 120.0), ("tires", -243.0, 214.0, 0.0), ("trash_pile", -229.0, 219.0, 200.0),
                                          ("shell", -235.0, 238.0, 0.0), ("cone", -239.0, 195.0, 0.0), ("cone", -238.2, 195.4, 0.0)]):
        p.put(kit, x, z, yaw, 1.0, dy(z))
    # закрытая часть: техника ЧВК россыпью, 2–3 единицы на 100 м
    for z, kit, x, yaw in [(-185.0, "truck", -239.0, 5.0), (-150.0, "btr", -228.0, 175.0), (-118.0, "truck", -241.0, 355.0),
                           (-82.0, "dump_truck", -227.5, 10.0), (-50.0, "btr", -240.0, 190.0), (-30.0, "truck", -228.0, 0.0),
                           (30.0, "truck", -240.0, 5.0), (62.0, "btr", -228.0, 175.0), (95.0, "truck", -239.0, 180.0),
                           (120.0, "dump_truck", -229.0, 5.0), (276.0, "truck", -240.0, 90.0), (300.0, "btr", -228.0, 100.0),
                           (322.0, "truck", -238.0, 85.0)]:
        p.put(kit, x, z, yaw, 1.0, dy(z))
    # гнездо ЧВК над кордоном (RING_NEST): мешки и блоки по восточному краю, прожектор над проспектом
    nz0, nz1 = S2.RING_NEST[2], S2.RING_NEST[3]
    p.box(-221.4, S2.RING_Y + 0.15 + 0.7, (nz0 + nz1) / 2.0, 0.9, 1.4, nz1 - nz0, "concrete")
    for k in range(5):
        p.put("sandbags", -222.6, nz0 + 1.4 + 2.8 * k, 0.0, 1.0, S2.RING_Y + 0.15)
    p.put("floodlight", -221.0, (nz0 + nz1) / 2.0, 90.0, 1.0, S2.RING_Y + 0.15 + 1.4)
    p.put("army_tent", -226.0, (nz0 + nz1) / 2.0 + 20.0, 0.0, 1.0, S2.RING_Y)
    p.log.append("верх: блок Z 150 (плиты 6,0 м + колючка, два грузовика), колонна Z 258 (плиты 6,5 м, сожжённые машины), "
                 "остановка с автобусом, 6 машин, фура поперёк, техника закрытой части, гнездо ЧВК")


# ------------------------------------------------------------------------------------------------ низ
def surfaces(p) -> None:
    p.surface("ur_shells", "parking", -248.0, -155.3, -218.0, -105.0, 0.0, 0.08)
    p.surface("ur_lot", "parking", -248.0, -105.0, -218.0, -50.0, 0.0, 0.08)
    p.surface("ur_bp_north", "parking", -248.0, -50.0, -218.0, -46.95, 0.0, 0.08)
    p.surface("ur_bp_road", "road", -248.0, -35.15, -218.0, 3.85, 0.0, 0.08)
    p.surface("ur_bp_walk_n", "walk", -248.0, -46.95, -218.0, -35.15, 0.0, 0.15)
    p.surface("ur_bp_walk_s", "walk", -248.0, 3.85, -218.0, 15.65, 0.0, 0.15)
    p.surface("ur_bp_south", "parking", -248.0, 15.65, -218.0, 16.0, 0.0, 0.08)
    p.surface("ur_fine", "parking", -248.0, 16.0, -218.0, 60.0, 0.0, 0.08)
    p.surface("ur_market", "walk", -248.0, 60.0, -218.0, 112.0, 0.0, 0.1)
    p.surface("ur_pass", "road", -248.0, 112.0, -218.0, 138.0, 0.0, 0.08)
    p.surface("ur_road", "mud", -248.0, 138.0, -218.0, 200.2, 0.0, 0.05)
    p.surface("ur_mail", "parking", -248.0, 214.0, -218.0, 244.0, 0.0, 0.08)


GATES_REMOVE = [(-128.0, "калитка из двора ЖК", 1), (-70.0, "ворота тыла кордона", 2), (38.0, "ворота двора полиции", 2),
                (62.0, "проход между полицией и домом 7", 2), (86.0, "из двора дома 7", 1)]


def gates(p) -> None:
    for z, name, secs in GATES_REMOVE:
        half = 2.6 if secs == 2 else 1.3
        n = p.drop_items(["district_fence"], [-217.6, z - half, -217.4, z + half])
        p.log.append(f"проход «{name}» Z {z:g}: убрано секций забора {n}")
    # пролом в ограждении ЧВК за Объездной (выход): секции Z 167,5…172,5 сняты, одна лежит
    n = p.drop_items(["district_fence"], [-247.6, 167.4, -247.4, 172.6])
    p.put("po2_fallen", -246.2, 170.0, 0.0)
    p.log.append(f"пролом в ограждении X −248 на Z 170: снято секций {n}, плита повалена")


def under_north(p) -> None:
    """Z −155…−50: гаражи-ракушки, стоянка с порталом паркинга −1, тыл кордона (CORDON_REAR)."""
    # ракушки вдоль западного ограждения (двери на восток) и ряд поперёк Z −105 (X −246…−228)
    n = 0
    z = -153.0
    while z < -108.5:
        if all(abs(z - cz) > 2.7 for cz in (-150.0, -120.0)):
            p.put("garage_open" if n % 6 == 2 else "garage", -244.5, z, 90.0)
            n += 1
        z += 3.4
    for k, x in enumerate([-244.3 + 3.3 * i for i in range(6)]):
        p.put("garage_open" if k == 3 else "garage", x, -105.0, 0.0)
        n += 1
    p.put("car_wreck", -230.0, -135.0, 80.0)
    p.put("car", -226.5, -143.0, 100.0)
    p.put("barrel", -236.0, -130.0)
    p.put("tires", -233.0, -112.0, 15.0)
    # стоянка: брошенные машины, будка, мусор
    for kit, x, z, yaw in [("car", -244.0, -98.0, 0.0), ("car_wreck", -239.0, -92.0, 5.0), ("police_car", -243.5, -83.0, 175.0),
                           ("van", -235.0, -76.0, 0.0), ("car", -244.0, -66.0, 3.0), ("car_wreck", -229.0, -88.0, 350.0)]:
        p.put(kit, x, z, yaw)
    # портал выезда паркинга −1 на поверхности: закрытые ворота у восточного края (сам выезд — под землёй)
    p.box(-218.9, 1.75, -82.0, 0.8, 3.5, 0.8, "concrete")
    p.box(-218.9, 1.75, -74.0, 0.8, 3.5, 0.8, "concrete")
    p.box(-218.9, 3.35, -78.0, 0.8, 0.5, 8.6, "concrete")
    p.box(-218.9, 1.4, -78.0, 0.25, 2.8, 7.2, "steel")
    p.put("lamp", -219.6, -85.0)
    # блоки: поперёк (Z −105) уже ряд ракушек; поперёк стоянки у блокпоста — плиты Z −50
    plates_row(p, -50.0, -248.0, -218.0, gaps=[(-237.0, -233.5)])
    # тыл кордона за сеткой (CORDON_REAR X −216…−196, Z −90…−48): палатка, два контейнера, пост мешков, сетка с калиткой по X −196
    p.put("army_tent", -208.5, -80.0, 0.0)
    p.put("container20", -214.3, -86.0, 0.0)
    p.put("container20", -214.3, -79.0, 0.0)
    p.put("sandbag_post", -202.0, -68.5, 180.0)
    p.put("barrel", -205.0, -72.0)
    p.put("pallets", -212.5, -70.0, 10.0)
    p.put("floodlight", -199.0, -88.0, 270.0)
    line(p, "chainlink", "z", -196.0, -90.0, -61.5, 2.0, gaps=[(-77.0, -74.5)])
    p.log.append("низ, север: ракушки и стоянка, портал паркинга, плиты блокпоста Z −50, тыл кордона (палатка, 2 контейнера, мешки, сетка с калиткой)")


def blockpost(p) -> None:
    """Z −50…16: блокпост ЧВК — плиты, БТР, грузовик, палатка, мешки, шлагбаумы поперёк проспекта у X −232."""
    plates_row(p, 16.0, -248.0, -218.0, gaps=[(-231.0, -227.5)])
    # заслон поперёк проспекта: джерси по X −232 с тремя проездами, в каждом шлагбаум
    gaps = [(-28.0, -22.0), (-13.0, -7.0), (-2.0, 3.85)]
    a = -35.15
    n = 0
    while a < 3.85 - 0.01:
        zc = a + 1.5
        if not any(g0 - 1.0 < zc < g1 + 1.0 for g0, g1 in gaps):
            p.put("jersey", -232.0, zc, 0.0)
            n += 1
        a += 3.0
    for g0, g1 in gaps:
        p.put("barrier_arm", -232.0, g0, 0.0)
    # техника и позиции
    p.put("btr", -241.0, -24.0, 5.0)
    p.put("truck", -243.5, -6.0, 180.0)
    p.put("army_tent", -238.0, 10.0, 0.0)
    p.put("army_tent", -243.5, -42.0, 90.0)
    p.put("sandbag_post", -236.0, -30.5, 0.0)
    p.put("sandbag_post", -236.0, -20.0, 180.0)
    p.put("sandbag_post", -229.0, -18.0, 0.0)
    p.put("sandbag_post", -229.0, -4.5, 180.0)
    p.put("booth", -230.0, -38.0, 90.0)
    p.put("floodlight", -234.0, -35.0, 270.0)
    p.put("floodlight", -234.0, 4.5, 270.0)
    p.put("barrel", -244.5, 8.0)
    p.put("barrel", -243.8, 8.6)
    p.put("tires", -226.5, -35.5, 40.0)
    p.put("cone", -229.5, -29.0)
    p.put("cone", -229.5, -12.0)
    p.put("cone", -229.5, 4.5)
    p.log.append(f"блокпост ЧВК Z −50…16: плиты по краям (проходы 3,5 м), джерси {n} секций с тремя проездами и шлагбаумами у X −232, БТР, грузовик, 2 палатки, 4 мешочных поста")


def under_south(p) -> None:
    """Z 16…290: штрафстоянка, рынок «Под мостом», проезд, техника дорожников, Вокзальная, почтовые фургоны, поперечные преграды."""
    # штрафстоянка: два ряда машин вдоль Z, будка у ворот
    for k, z in enumerate((24.0, 29.5, 35.0, 41.0, 47.0, 52.5)):
        for x, kit in ((-244.0, "car"), (-238.5, "car_wreck" if k % 3 == 1 else "car")):
            p.put(kit, x, z, 0.0 if k % 2 == 0 else 180.0)
    p.put("police_car", -233.5, 31.0, 90.0)
    p.put("van", -229.0, 47.0, 0.0)
    p.put("booth", -219.6, 27.0, 90.0)
    # рынок «Под мостом»: ларьки и контейнеры рядами, брезент; проход вдоль восточной стороны (LANE_E) свободен
    for i in range(5):
        p.put("stall", -246.0 + 3.3 * i, 64.0, 0.0)
    for i in range(4):
        p.put("stall", -245.0 + 3.6 * i, 86.0, 180.0)
    p.put("kiosk", -229.0, 90.0, 90.0)
    p.put("food_kiosk", -228.5, 69.0, 270.0)
    p.put("kiosk", -240.0, 104.0, 0.0)
    p.put("container20", -241.0, 78.0, 90.0)
    p.put("container20", -234.8, 78.0, 90.0)
    for x in (-233.0, -226.8):
        p.put("container20", x, 96.0, 90.0)
    for k in range(6):
        p.put(["boxes", "pallets", "cart"][k % 3], -243.0 + 3.1 * k, 72.0 + 1.0 * (k % 2), 17.0 * k)
    p.put("crowd_barrier", -245.0, 100.0, 90.0)
    # проезд к гаражам: конусы и джерси
    for x in (-246.0, -240.0, -236.0):
        p.put("jersey", x, 118.0, 90.0)
    p.put("cone", -238.0, 128.0)
    p.put("cone", -237.4, 128.6)
    p.put("car", -236.0, 133.0, 90.0)
    # техника дорожников и бытовки
    p.put("roller", -243.5, 150.0, 20.0)
    p.put("dump_truck", -236.0, 156.5, 80.0)
    p.put("excavator", -231.0, 178.0, -30.0)
    p.put("tractor", -244.0, 188.0, 140.0)
    p.put("cabin", -229.0, 185.0, 0.0)
    p.put("cabin", -229.0, 191.6, 0.0)
    p.put("pile_sand", -243.0, 163.0, 20.0)
    p.put("barrel", -228.5, 150.5)
    p.put("pallets", -228.0, 164.0, 10.0)
    line(p, "hazard_fence", "x", 143.0, -246.0, -224.0, 2.5)
    # Вокзальная: пост ЧВК у шлагбаума на границе
    p.put("booth", -243.0, 215.0, 0.0)
    p.put("sandbag_post", -244.5, 199.0, 0.0)
    p.put("sandbag_post", -244.5, 216.5, 180.0)
    p.put("cone", -240.0, 204.2)
    p.put("cone", -240.0, 209.8)
    # почтовые фургоны
    for x in (-244.0, -240.2, -236.4):
        p.put("van", x, 219.0, 0.0)
    p.put("van", -232.0, 233.0, 20.0)
    p.put("van", -243.5, 236.0, 180.0)
    p.put("truck", -229.5, 240.0, 5.0)
    p.put("cart", -226.0, 228.0, 20.0)
    p.put("pallets", -240.0, 229.0, 0.0)
    p.put("bags", -239.0, 232.5, 40.0)
    # поперечные преграды UNDER_BREAKS: проход остаётся в незанятой части ширины (восточная тропа X −223,5…−219,5 свободна)
    po2_row(p, 60.0, -248.0, -224.0, gaps=[(-237.0, -233.0)])                 # сетка и ворота
    po2_row(p, 112.0, -248.0, -226.0)
    po2_row(p, 138.0, -240.0, -226.0, gaps=[(-232.5, -229.5)])                 # забор; проход у середины и у восточной тропы
    po2_row(p, 170.0, -244.5, -230.0)                                          # ряд плит
    po2_row(p, 226.0, -246.0, -232.0)                                          # затор почтовых фургонов: плиты и фургоны
    p.log.append("низ, юг: штрафстоянка, рынок, проезд, техника, Вокзальная, фургоны; преграды Z 60, 112, 138, 170, 226")


def exits(p) -> None:
    pass


def build(p):
    deck(p)
    screens(p)
    median(p)
    towers(p)
    deck_top(p)
    surfaces(p)
    gates(p)
    under_north(p)
    blockpost(p)
    under_south(p)
    return p
