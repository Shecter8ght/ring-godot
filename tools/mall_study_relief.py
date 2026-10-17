"""Рельеф черновика территории ТЦ: горки, утёсы, речка, рощи (владелец, 2026-10-17: «небольших утёсов не
хватает, горушек, речки, лесистости, вертикальности — как в Battlefield или Hunt: Showdown»).

  горки  — пологие холмы 4–9 м во внешнем поясе: западная гора за речкой, сопка у водоёма в лесу,
           холмы на юго-востоке и северо-востоке, бугры у автостанции и у стройки;
  утёсы  — уступ 5–7 м с пологим верхом, концы сходят на нет (их можно обойти): над поймой речки
           на западе, над водоёмом, скальная гряда юго-восточного холма;
  речка  — с севера на юг западнее ТЦ: вода на 1,6 м ниже земли, дно шириной 6 м; у внешнего берега
           излучины берег крутой, у внутреннего — пологий; мост на западной дороге у КПП, пешеходный
           мостик у АЗС, брод на колее (там встала колонна), под трассой — труба;
  рощи   — на горках и по берегам речки (их сажает MallLandscape, как лес).

Координаты игры: X — восток, Z — юг (север — −Z). Высоты считает MallLandscape.ground() по этим данным.
"""

from __future__ import annotations

import math

# холмы: x, z, радиус, высота
HILLS = [(-390.0, 150.0, 75.0, 9.0), (-205.0, -335.0, 60.0, 7.0), (370.0, 160.0, 60.0, 8.0),
         (395.0, -205.0, 45.0, 6.0), (-240.0, 225.0, 40.0, 4.0), (190.0, -320.0, 35.0, 5.0)]
# утёсы: кромка (ломаная), высота, на сколько метров верх сходит к земле, точка на высокой стороне
CLIFFS = [
    {"name": "Обрыв над поймой", "points": [(-338.0, 105.0), (-342.0, 150.0), (-348.0, 195.0)], "height": 6.0, "fall": 35.0,
     "toward": (-380.0, 150.0)},
    {"name": "Обрыв над водоёмом", "points": [(-160.0, -322.0), (-115.0, -327.0), (-70.0, -328.0)], "height": 5.0, "fall": 30.0,
     "toward": (-115.0, -360.0)},
    {"name": "Скальная гряда", "points": [(318.0, 120.0), (320.0, 158.0), (322.0, 195.0)], "height": 7.0, "fall": 40.0,
     "toward": (370.0, 160.0)},
]
# речка: с севера (из-за границы) на юг (под трассой и дальше)
RIVER = [(-285.0, -395.0), (-300.0, -310.0), (-315.0, -250.0), (-310.0, -170.0), (-300.0, -90.0), (-291.0, -45.0),
         (-297.0, 40.0), (-315.0, 110.0), (-333.0, 190.0), (-330.0, 255.0), (-318.0, 302.0), (-312.0, 345.0),
         (-306.0, 410.0)]
RIVER_BELOW = 1.6     # вода ниже окрестной земли, м
RIVER_DEPTH = 1.1     # глубина воды у середины, м
RIVER_BED_HALF = 3.0  # полуширина ровного дна, м
BANK_STEEP = 1.3      # крутизна внешнего берега излучины (высота на метр в сторону)
BANK_SOFT = 0.3       # внутреннего берега
FORD_TRACK = [(-362.0, 214.0), (-300.0, 240.0)]  # колея, на которой брод
FOOTBRIDGE_NEAR = (-311.0, -190.0)
HIGHWAY_Z = (304.0, 332.0)  # трасса на насыпи: речка проходит под ней в трубе
# рощи: круги x, z, радиус; и вдоль берегов — куски речки [s0, s1, сторона]
GROVES = [(-395.0, 150.0, 45.0), (380.0, 165.0, 40.0), (-250.0, 215.0, 25.0), (175.0, -300.0, 22.0), (-258.0, -288.0, 28.0)]
RIPARIAN = [(60.0, 175.0, 1.0), (245.0, 345.0, -1.0), (420.0, 585.0, 1.0), (440.0, 560.0, -1.0), (680.0, 740.0, -1.0)]


def smoothstep(a: float, b: float, x: float) -> float:
    t = min(1.0, max(0.0, (x - a) / (b - a)))
    return t * t * (3.0 - 2.0 * t)


def base_height(plan: dict, x: float, z: float) -> float:
    """Как MallLandscape.base_height: север выше, юг к трассе ниже, у здания ровно."""
    lv = plan["levels"]
    north = lv["north"] * smoothstep(lv["north_from"], lv["north_to"], -z)
    south = lv["south"] * smoothstep(lv["south_from"], lv["south_to"], z)
    h = (north + south) * smoothstep(plan["mall"]["flat_r"], plan["mall"]["flat_r"] + 35.0, math.hypot(x, z))
    hw = plan["highway"]
    if z >= hw["z"] - hw["width"] * 0.5:
        h = hw["y"]
    return h


def _cross(a, b) -> float:
    return a[0] * b[1] - a[1] * b[0]


def _intersect(p1, p2, q1, q2):
    """Точка пересечения отрезков и доля пути по первому, или None."""
    d1 = (p2[0] - p1[0], p2[1] - p1[1])
    d2 = (q2[0] - q1[0], q2[1] - q1[1])
    den = _cross(d1, d2)
    if abs(den) < 1e-9:
        return None
    w = (q1[0] - p1[0], q1[1] - p1[1])
    t = _cross(w, d2) / den
    u = _cross(w, d1) / den
    if 0.0 <= t <= 1.0 and 0.0 <= u <= 1.0:
        return (p1[0] + d1[0] * t, p1[1] + d1[1] * t), t
    return None


def _crossing(river, line):
    """Где речка пересекает ломаную: точка, расстояние вдоль речки, направление речки."""
    s0 = 0.0
    for a, b in zip(river, river[1:]):
        seg = math.dist(a, b)
        for q1, q2 in zip(line, line[1:]):
            hit = _intersect(a, b, q1, q2)
            if hit:
                (x, z), t = hit
                return (x, z), s0 + seg * t, ((b[0] - a[0]) / seg, (b[1] - a[1]) / seg)
        s0 += seg
    return None


def _nearest_s(river, p):
    best = (1e9, 0.0, river[0], (1.0, 0.0))
    s0 = 0.0
    for a, b in zip(river, river[1:]):
        seg = math.dist(a, b)
        dx, dz = (b[0] - a[0]) / seg, (b[1] - a[1]) / seg
        t = max(0.0, min(seg, (p[0] - a[0]) * dx + (p[1] - a[1]) * dz))
        q = (a[0] + dx * t, a[1] + dz * t)
        d = math.dist(p, q)
        if d < best[0]:
            best = (d, s0 + t, q, (dx, dz))
        s0 += seg
    return best[1], best[2], best[3]


def _circle(x: float, z: float, r: float, n: int = 14) -> list[list[float]]:
    return [[round(x + r * math.cos(2.0 * math.pi * i / n), 1), round(z + r * math.sin(2.0 * math.pi * i / n), 1)] for i in range(n)]


def _sub_line(river, s0: float, s1: float, step: float = 8.0):
    pts = []
    s = s0
    while s <= s1:
        pts.append(_at(river, s))
        s += step
    return pts


def _at(river, s: float):
    for a, b in zip(river, river[1:]):
        seg = math.dist(a, b)
        if s <= seg:
            t = s / seg
            return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t), ((b[0] - a[0]) / seg, (b[1] - a[1]) / seg)
        s -= seg
    a, b = river[-2], river[-1]
    seg = math.dist(a, b)
    return b, ((b[0] - a[0]) / seg, (b[1] - a[1]) / seg)


def make_relief(plan: dict) -> dict:
    river = RIVER
    # уровень воды по вершинам: ниже окрестной земли и не выше, чем выше по течению
    water = []
    for x, z in river:
        level = base_height(plan, x, z) - RIVER_BELOW
        water.append(round(min(level, water[-1] - 0.05) if water else level, 2))
    # крутизна берегов по отрезкам: [слева, справа] от хода речки; внешний берег излучины — круче
    dirs = [((b[0] - a[0]) / math.dist(a, b), (b[1] - a[1]) / math.dist(a, b)) for a, b in zip(river, river[1:])]
    banks = []
    for i, d in enumerate(dirs):
        other = dirs[i + 1] if i + 1 < len(dirs) else dirs[i - 1]
        turn = _cross(d, other) if i + 1 < len(dirs) else -_cross(d, other)
        angle = math.degrees(math.asin(max(-1.0, min(1.0, turn))))
        steep = BANK_STEEP if abs(angle) > 10.0 else 0.6
        # поворот влево (turn > 0) — внешний берег справа
        banks.append([BANK_SOFT, steep] if turn > 0.0 else [steep, BANK_SOFT])
    def segment_at(s: float) -> int:
        walked = 0.0
        for i, (a, b) in enumerate(zip(river, river[1:])):
            walked += math.dist(a, b)
            if s <= walked:
                return i
        return len(river) - 2

    def spans(at, s: float, deck: float) -> dict:
        """Длина моста по сторонам: до места, где берег русла выходит к настилу, и ещё 2,5 м."""
        i = segment_at(s)
        walked = sum(math.dist(a, b) for a, b in zip(river[:i + 1], river[1:i + 1]))
        t = (s - walked) / math.dist(river[i], river[i + 1])
        bed = water[i] + (water[i + 1] - water[i]) * t - RIVER_DEPTH
        return {"half_left": round(RIVER_BED_HALF + max(0.0, deck - bed) / banks[i][0] + 2.5, 1),
                "half_right": round(RIVER_BED_HALF + max(0.0, deck - bed) / banks[i][1] + 2.5, 1)}

    road = next(r for r in plan["roads"] if r["id"] == "west_road")["points"]
    road_cross = _crossing(river, road)
    ford_cross = _crossing(river, FORD_TRACK)
    s_foot, foot_at, foot_dir = _nearest_s(river, FOOTBRIDGE_NEAR)
    bridges = []
    if road_cross:
        (x, z), s, d = road_cross
        deck = round(base_height(plan, x, z) + 0.05, 2)
        bridges.append({"kind": "road", "at": [round(x, 2), round(z, 2)], "s": round(s, 1),
                        "yaw": round(math.degrees(math.atan2(d[0], d[1])), 1), "length": 26.0, "width": 11.0,
                        "deck": deck, **spans((x, z), s, deck)})
    deck = round(base_height(plan, *foot_at) + 0.15, 2)
    bridges.append({"kind": "foot", "at": [round(foot_at[0], 2), round(foot_at[1], 2)], "s": round(s_foot, 1),
                    "yaw": round(math.degrees(math.atan2(foot_dir[0], foot_dir[1])), 1), "length": 22.0, "width": 2.2,
                    "deck": deck, **spans(foot_at, s_foot, deck)})
    fords = []
    if ford_cross:
        (x, z), s, _ = ford_cross
        fords.append({"at": [round(x, 2), round(z, 2)], "s": round(s, 1), "half": 8.0})
    culverts = []
    for zc in HIGHWAY_Z:
        hit = _crossing(river, [(-480.0, zc), (520.0, zc)])
        if hit:
            (x, z), s, d = hit
            culverts.append({"at": [round(x, 2), round(z, 2)], "yaw": round(math.degrees(math.atan2(d[0], d[1])), 1)})
    cliffs = []
    for c in CLIFFS:
        a, b = c["points"][0], c["points"][1]
        side = 1.0 if _cross((b[0] - a[0], b[1] - a[1]), (c["toward"][0] - a[0], c["toward"][1] - a[1])) > 0.0 else -1.0
        cliffs.append({"name": c["name"], "points": [list(p) for p in c["points"]], "height": c["height"], "fall": c["fall"],
                       "side": side})
    groves = [_circle(x, z, r) for x, z, r in GROVES]
    crossings = [b["s"] for b in bridges] + [f["s"] for f in fords]
    for s0, s1, side in RIPARIAN:
        if any(s0 - 25.0 < s < s1 + 25.0 for s in crossings):
            continue
        line = _sub_line(river, s0, s1)
        inner = [[round(p[0] - d[1] * 9.0 * side, 1), round(p[1] + d[0] * 9.0 * side, 1)] for p, d in line]
        outer = [[round(p[0] - d[1] * 21.0 * side, 1), round(p[1] + d[0] * 21.0 * side, 1)] for p, d in line]
        groves.append(inner + outer[::-1])
    return {
        "hills": [list(h) for h in HILLS],
        "cliffs": cliffs,
        "river": {"points": [list(p) for p in river], "water": water, "banks": banks, "bed_half": RIVER_BED_HALF,
                  "depth": RIVER_DEPTH, "bridges": bridges, "fords": fords, "culverts": culverts,
                  "dry_z": list(HIGHWAY_Z)},
        "groves": groves,
    }
