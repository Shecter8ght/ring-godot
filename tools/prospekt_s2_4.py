"""«Проспект», вторая очередь, этап 4 — малые зоны: отдел полиции, лагерь эвакуации, сквер, хоздвор «Зерна».

Собирает патч s2_4_small (вызывается из tools/prospekt_patch.py). Числа — словари tools/prospekt_stage2_plan.py (POLICE*, CAMP*,
PLAYGROUND2, WC_*, TREE_*, ZERNO_YARD), лист 14 и §25.4 docs/design/prospekt_map.md. Координаты сцены: X — восток, Z — юг,
Y — вверх, метры. Здания — стенами и плитами (как «Ярус» и вокзал): наружные стены 0,3 м, перегородки 0,15 м, двери 1,17 × 2,42.
«Под ключ» — обычная закрытая дверь-коробка с meta lock = "key" (ключи владелец согласует отдельно).
"""
from __future__ import annotations

import json
import math

import prospekt_stage2_plan as S2
from prospekt_s2_2 import B, Patch_windows, spans

D = 2.415
TE, TI = 0.3, 0.15
LOCK = {"lock": "key", "note": "под ключ: ключ согласует владелец"}


def kits_in(p, rect, skip=()):
    base = p.base()["filler"]["items"]
    return sorted({it[0] for it in base if rect[0] <= it[1] <= rect[2] and rect[1] <= it[2] <= rect[3]} - set(skip))


def closed_door(p, x: float, z: float, axis: str, w: float, y0: float = 0.0, label: str = "") -> None:
    """Закрытая дверь с пометкой «под ключ»: коробка в проёме."""
    size = [w, D, 0.1] if axis == "x" else [0.1, D, w]
    p.add["boxes"].append({"at": [round(x, 3), round(y0 + D / 2.0, 3), round(z, 3)], "size": size, "mat": "dark", "yaw": 0.0,
                           "solid": True, "meta": dict(LOCK, label=label)})


def bars(p, axis: str, c: float, gaps, y0: float = 0.0) -> int:
    """Решётки на окнах: axis «x» — стена вдоль X на z = c; gaps — (центр, ширина, верх, низ)."""
    n = 0
    for g in gaps:
        a, w, top, low = g[0], g[1], g[2], g[3]
        if low < 0.3:
            continue
        k = max(3, int(w / 0.22))
        for i in range(k + 1):
            o = -w / 2.0 + 0.05 + (w - 0.1) * i / k
            if axis == "x":
                p.box(a + o, y0 + (low + top) / 2.0, c, 0.035, top - low, 0.035, "steel")
            else:
                p.box(c, y0 + (low + top) / 2.0, a + o, 0.035, top - low, 0.035, "steel")
        for yy in (low + 0.05, (low + top) / 2.0, top - 0.05):
            if axis == "x":
                p.box(a, y0 + yy, c, w, 0.04, 0.04, "steel")
            else:
                p.box(c, y0 + yy, a, 0.04, 0.04, w, "steel")
        n += 1
    return n


# =============================================================================================== полиция
PX0, PX1, PZ0, PZ1 = S2.POLICE            # −208…−178, 16…30
H1, Y2, H2, YR = 3.2, 3.5, 3.2, 7.0


def police_removals(p) -> None:
    # площадка остановки под зданием и двором: лавки, урны, мусор, светильники, ларёк «R05», тополь и заборные огрызки
    n = 0
    names: set = set()
    for rect in ([-209.0, 15.8, -176.9, 31.0], [-217.0, 15.8, -207.9, 60.5]):
        kits = kits_in(p, rect)
        names |= set(kits)
        n += p.drop_items(kits, rect)
    p.log.append(f"полиция: убрано вещей в контуре здания и двора: {n} ({', '.join(sorted(names))})")
    # низкая бетонная кромка по Z 112 и X −4,3 в сквере — в разделе туалета/площадки


def police_building(p, b: B) -> None:
    p.slab("pol_f1", [PX0 - 0.15, PZ0 - 0.15, PX1 + 0.15, PZ1 + 0.15], 0.02, 0.3, "walk")
    # ---------- наружные стены, этаж 1
    win_n = Patch_windows(PX0, PX1, 4.0, 1.6, 1.0, 2.4, [(-192.0, 2.4)])
    b.wx(PZ0, PX0 - 0.15, PX1 + 0.15, 0.0, H1, [(-192.0, 2.4, 2.6)] + win_n, TE)
    bars(p, "x", PZ0, win_n)
    win_e = [(19.5, 1.6, 2.4, 1.0), (26.5, 0.8, 2.2, 1.2)]
    b.wz(PX1, PZ0 + 0.15, PZ1 - 0.15, 0.0, H1, win_e, TE)
    bars(p, "z", PX1, win_e)
    win_s = [(-193.0, 1.6, 2.4, 1.0), (-180.5, 0.8, 2.2, 1.2)]
    b.wx(PZ1, PX0 - 0.15, PX1 + 0.15, 0.0, H1, win_s, TE)
    bars(p, "x", PZ1, win_s)
    b.wz(PX0, PZ0 + 0.15, PZ1 - 0.15, 0.0, H1, [(19.5, 1.2, D)], TE)           # камеры — дверь во двор
    # ---------- перегородки, этаж 1
    win_hall = [(-189.8, 1.6, 2.2, 1.0)]                                          # окно-стойка в дежурную часть
    b.wx(23.0, PX0 + 0.15, PX1 - 0.15, 0.0, H1, [(-193.0, 1.2, D)] + win_hall + [(-187.0, 1.2, D)], TI)
    b.wz(-198.0, PZ0 + 0.15, 23.0 - 0.075, 0.0, H1, [(19.5, 1.2, D)], TI)         # камеры | холл
    b.wz(-198.0, 23.0 + 0.075, PZ1 - 0.15, 0.0, H1, [(26.5, 1.2, D)], TI)         # КХО | дежурная часть (закрыта «под ключ»)
    closed_door(p, -198.0, 26.5, "z", 1.2, 0.0, "КХО")
    b.wz(-186.0, PZ0 + 0.15, 23.0 - 0.075, 0.0, H1, [(19.5, 1.2, D)], TI)         # холл | приём граждан
    b.wz(-188.0, 23.0 + 0.075, PZ1 - 0.15, 0.0, H1, [], TI)                       # дежурная часть | лестница
    b.wz(-183.0, 23.0 + 0.075, PZ1 - 0.15, 0.0, H1, [(26.5, 1.2, D)], TI)         # лестница | с/у
    # ---------- камеры ×3: решётчатые перегородки внутри помещения (проход по Z 19,5 — 1,4 м)
    for x in (-203.0,):                                                            # две северные камеры
        for zc, (za, zb) in ((None, (16.15, 18.8)),):
            for z in [za + i * (zb - za) / 10.0 for i in range(11)]:
                p.box(x, 1.2, z, 0.035, 2.4, 0.035, "steel")
            p.box(x, 0.1, (za + zb) / 2.0, 0.04, 0.05, zb - za, "steel")
            p.box(x, 2.35, (za + zb) / 2.0, 0.04, 0.05, zb - za, "steel")
    gz = (18.8, 20.2)
    for z in (gz[0], gz[1]):                                                       # решётка вдоль проходной полосы
        n = 12
        for side, (xa, xb) in enumerate(((-207.85, -198.15),)):
            for i in range(n + 1):
                xx = xa + (xb - xa) * i / n
                if side == 0 and z == gz[0] and abs(xx + 205.5) < 0.55:
                    continue                                                       # дверца камеры 1 (проём 1,1 м)
                if side == 0 and z == gz[0] and abs(xx + 200.5) < 0.55:
                    continue                                                       # дверца камеры 2
                if z == gz[1] and abs(xx + 203.0) < 0.55:
                    continue                                                       # дверца камеры 3
                p.box(xx, 1.2, z, 0.035, 2.4, 0.035, "steel")
            p.box((xa + xb) / 2.0, 2.35, z, xb - xa, 0.05, 0.05, "steel")
    for x, z in ((-205.5, 17.4), (-200.5, 17.4), (-203.0, 21.7)):                  # нары в камерах
        p.box(x, 0.4, z, 1.9, 0.12, 0.8, "wood")
        p.box(x, 0.2, z, 1.8, 0.4, 0.7, "steel")
    # ---------- мебель этажа 1
    for x in (-196.5, -188.0):
        p.box(x, 0.25, 17.0, 2.0, 0.5, 0.5, "accent")                              # скамьи в холле
    p.box(-189.8, 0.55, 22.55, 2.2, 1.1, 0.5, "accent")                            # стойка у окна дежурной части
    p.box(-182.0, 0.4, 17.6, 2.6, 0.8, 0.9, "accent")                              # приём граждан: стол
    p.box(-181.0, 0.2, 20.8, 1.6, 0.4, 0.5, "accent")
    for x in (-195.0, -191.0):
        p.box(x, 0.4, 28.0, 2.0, 0.8, 0.9, "accent")                               # дежурная часть: столы
    p.box(-197.0, 0.9, 24.5, 0.6, 1.8, 0.8, "dark")                                # пульт связи
    for z in (24.5, 27.0, 29.2):
        p.box(-205.0, 1.0, z, 4.0, 2.0, 0.6, "steel")                              # КХО: стеллажи оружейной
    p.box(-201.5, 0.6, 28.0, 0.8, 1.2, 1.6, "steel")                               # сейф
    for z in (24.4, 26.6, 28.6):
        p.box(-180.5, 1.0, z, 0.04, 2.0, 0.9, "steel")                             # с/у: кабинки
    p.box(-180.6, 0.45, 30.0 - 0.6, 0.5, 0.9, 0.45, "steel")
    # ---------- лестница: два марша с площадкой, шахта 5 × 7 (X −188…−183, Z 23…30), подъём 3,5
    ax, bx = -187.05, -185.25
    p.add["stairs"].append({"from": [ax, 0.0, 23.2], "to": [ax, 1.75, 27.4], "width": 1.7, "count": 11, "mat": "concrete", "rails": "both"})
    p.slab("pol_land", [-187.925, 27.4, -184.3, 29.925], 1.75, 0.2, "concrete")
    p.box(-186.1, 0.8, 28.66, 3.6, 1.6, 2.5, "concrete")
    p.add["stairs"].append({"from": [bx, 1.75, 27.4], "to": [bx, Y2, 23.6], "width": 1.7, "count": 11, "mat": "concrete", "rails": "both"})
    # ---------- перекрытие второго этажа: проём шахты; к северу от него — полоса 23,0…23,7
    p.slab("pol_f2", [PX0 - 0.15, PZ0 - 0.15, PX1 + 0.15, PZ1 + 0.15], Y2, 0.3, "slab", [[-187.925, 23.7, -184.3, 29.925]])
    b.rail_x(23.7, -187.925, -186.1, Y2)
    b.rail_z(-184.3, 24.2, 29.925, Y2)
    # ---------- наружные стены, этаж 2
    wn = Patch_windows(PX0, PX1, 4.0, 1.6, 0.9, 2.5, [])
    b.wx(PZ0, PX0 - 0.15, PX1 + 0.15, Y2, H2, wn, TE)
    we = Patch_windows(PZ0, PZ1, 4.5, 1.4, 0.9, 2.5, [])
    b.wz(PX1, PZ0 + 0.15, PZ1 - 0.15, Y2, H2, we, TE)
    b.wz(PX0, PZ0 + 0.15, PZ1 - 0.15, Y2, H2, we, TE)
    ws = Patch_windows(PX0, PX1, 4.0, 1.6, 0.9, 2.5, [])
    b.wx(PZ1, PX0 - 0.15, PX1 + 0.15, Y2, H2, ws, TE)
    # ---------- перегородки, этаж 2
    b.wx(21.0, PX0 + 0.15, PX1 - 0.15, Y2, H2, [(-203.0, 1.2, D), (-193.0, 1.2, D), (-183.0, 1.2, D)], TI)
    closed_door(p, -183.0, 21.0, "x", 1.2, Y2, "вещдоки")
    b.wx(23.0, PX0 + 0.15, PX1 - 0.15, Y2, H2, [(-203.0, 1.2, D), (-193.0, 1.2, D), (-185.5, 1.2, D)], TI)
    for x, z0, z1 in ((-198.0, PZ0 + 0.15, 21.0 - 0.075), (-188.0, PZ0 + 0.15, 21.0 - 0.075), (-198.0, 23.0 + 0.075, PZ1 - 0.15),
                      (-188.0, 23.0 + 0.075, PZ1 - 0.15), (-183.0, 23.0 + 0.075, PZ1 - 0.15)):
        b.wz(x, z0, z1, Y2, H2, [], TI)
    # ---------- мебель этажа 2
    p.box(-203.0, Y2 + 0.4, 17.5, 2.2, 0.8, 1.0, "accent")                         # начальник: стол
    p.box(-206.8, Y2 + 0.6, 19.2, 0.9, 1.2, 0.8, "steel")                          # сейф
    p.box(-199.0, Y2 + 1.0, 19.5, 0.5, 2.0, 1.4, "accent")                         # шкаф
    for x in (-195.0, -191.0):
        p.box(x, Y2 + 0.4, 17.8, 1.8, 0.8, 0.9, "accent")                          # следователи: столы
    p.box(-193.0, Y2 + 1.0, 20.5, 3.0, 2.0, 0.4, "steel")
    for x in (-186.0, -182.0, -179.0):
        p.box(x, Y2 + 1.0, 17.0, 1.6, 2.0, 0.6, "steel")                           # вещдоки: стеллажи
    for x in (-206.0, -203.0, -200.0):
        p.box(x, Y2 + 1.1, 26.5, 0.7, 2.2, 5.0, "steel")                           # архив: ряды
    for z in (25.5, 28.5):
        p.box(-195.0, Y2 + 0.3, z, 2.0, 0.6, 0.9, "accent")                        # комната отдыха: койки
    p.box(-190.5, Y2 + 0.4, 28.5, 1.4, 0.8, 0.8, "accent")
    for z in (24.4, 26.6, 28.6):
        p.box(-180.5, Y2 + 1.0, z, 0.04, 2.0, 0.9, "steel")                        # с/у
    # ---------- крыша с парапетом
    p.slab("pol_roof", [PX0 - 0.2, PZ0 - 0.2, PX1 + 0.2, PZ1 + 0.2], YR, 0.3, "slab")
    b.wx(PZ0 - 0.1, PX0 - 0.2, PX1 + 0.2, YR, 0.8, [], 0.2, "concrete")
    b.wx(PZ1 + 0.1, PX0 - 0.2, PX1 + 0.2, YR, 0.8, [], 0.2, "concrete")
    b.wz(PX0 - 0.1, PZ0, PZ1, YR, 0.8, [], 0.2, "concrete")
    b.wz(PX1 + 0.1, PZ0, PZ1, YR, 0.8, [], 0.2, "concrete")
    p.add["signs"].append({"at": [-192.0, 5.1, 15.75], "size": 64.0, "text": "ОТДЕЛ ПОЛИЦИИ"})
    p.add["signs"].append({"at": [-192.0, 2.9, 15.8], "size": 26.0, "text": "дежурная часть"})
    p.add["signs"].append({"at": [-208.2, 2.7, 19.5], "size": 22.0, "text": "камеры — выход во двор"})
    p.log.append("полиция: 30 × 14, два этажа по 3,5 (крыша +7,0, парапет 0,8): 7 комнат внизу, 8 вверху, лестница двумя маршами с площадкой "
                 "(24,7° / 25,6°), 3 камеры с решётками, КХО и вещдоки — закрытые двери «под ключ», решётки на окнах первого этажа")


def police_yard(p, b: B) -> None:
    p.surface("police_yard", "parking", -217.0, 16.0, -208.0, 60.0, 0.0, 0.06)
    # забор: север — ворота 5 м (X −215,5…−210,5), юг и восток — глухо; запад (X −217,5) уже есть, в нём проём у Z 38
    f = "district_fence"
    p.put(f, -216.25, 16.3, 90.0)
    p.put(f, -209.25, 16.3, 90.0)
    for x in (-216.25, -213.75, -211.25, -208.75):
        p.put(f, x, 59.9, 90.0)
    for z in (31.25, 33.75, 36.25, 38.75, 41.25, 43.75, 46.25, 48.75, 51.25, 53.75, 56.25, 58.75):
        pass
    for z in (31.3, 33.8, 36.3, 38.8, 41.3, 43.8, 46.3, 48.8, 51.3, 53.8, 56.3, 58.8):
        p.put(f, -207.9, z, 0.0)
    p.add["signs"].append({"at": [-213.0, 3.0, 16.4], "size": 30.0, "text": "служебный двор · въезд"})
    # три полицейские машины и гараж
    p.put("police_car", -214.4, 24.0, 0.0, 1.0, 0.0, 0.0, 0.0, "PV_police")
    p.put("police_car", -214.4, 29.5, 180.0, 1.0, 0.0, 0.0, 0.0, "PV_police")
    p.put("police_car", -214.4, 44.0, 0.0, 1.0, 0.0, 0.0, 0.0, "PV_police_open")
    gx0, gx1, gz0, gz1 = -216.5, -209.5, 48.0, 58.0
    p.slab("pol_garage_floor", [gx0, gz0, gx1, gz1], 0.02, 0.2, "walk")
    b.wx(gz0, gx0, gx1, 0.0, 3.0, [(-213.0, 3.6, 2.8)], 0.2)
    b.wx(gz1, gx0, gx1, 0.0, 3.0, [], 0.2)
    b.wz(gx0, gz0, gz1, 0.0, 3.0, [], 0.2)
    b.wz(gx1, gz0, gz1, 0.0, 3.0, [], 0.2)
    p.slab("pol_garage_roof", [gx0 - 0.2, gz0 - 0.2, gx1 + 0.2, gz1 + 0.2], 3.2, 0.2, "slab")
    p.box(-213.0, 0.5, 54.5, 2.4, 1.0, 1.0, "steel")                               # верстак
    p.put("barrel", -210.4, 56.8, 0.0)
    p.put("barrel", -210.4, 57.5, 0.0)
    p.put("police_car", -213.0, 52.5, 0.0, 1.0, 0.0, 0.0, 0.0, "PV_police_wreck")
    p.add["signs"].append({"at": [-213.0, 3.4, 47.85], "size": 26.0, "text": "гараж"})
    p.log.append("двор полиции: покрытие, забор с воротами на север (5 м) и глухой с юга и востока, три машины, гараж 7 × 10 с воротами 3,6 м")


# =============================================================================================== лагерь
CX0, CX1, CZ0, CZ1 = S2.CAMP      # 141.3…189.3, −47…58
NET_H = 2.4


def net(p, x0, z0, x1, z1, mat="steel") -> None:
    """Сетка/блок ≥ 2,4 м: тонкая коробка вдоль отрезка (x0,z0)–(x1,z1) по осям."""
    if abs(x1 - x0) < 1e-6:
        p.box(x0, NET_H / 2.0, (z0 + z1) / 2.0, 0.08, NET_H, abs(z1 - z0), mat)
    else:
        p.box((x0 + x1) / 2.0, NET_H / 2.0, z0, abs(x1 - x0), NET_H, 0.08, mat)


def camp_moves(p) -> None:
    """Палатки, техника, вышки, мачты — по зонам листа 14."""
    # палатки: в зоны (большие уходят на новые места, оставшиеся — в «фильтре» и медсанбате)
    for x, z in ((149.3, -1.3), (165.3, -1.3), (181.3, -1.3), (163.3, 18.7), (166.3, 41.0), (180.3, 41.0)):
        p.drop_item("army_tent", x, z)
    # противотанковые «ежи» по северной кромке — на подступы к западным воротам снаружи (стена, вышка и лестница идут по этой полосе)
    for x in (143.3, 150.3, 157.3, 164.3, 171.3, 178.3):
        rec = p.drop_item("m:U09_01", x, -45.3)
    for x, z in ((136.0, -6.0), (136.0, 2.0)):
        p.put("m:U09_01", x, z, 20.0)
    # техника и ящики
    p.drop_item("truck", 186.8, -15.3)
    p.drop_item("armored_truck", 144.3, 17.7)
    p.drop_item("container20", 173.3, -16.3)
    p.drop_item("mast", 151.3, -15.3)
    p.drop_item("mast", 177.3, 12.7)
    p.drop_item("flagpole", 155.3, -15.3)
    for x, z in ((145.3, 52.0), (146.0, 52.0), (145.3, 52.7), (146.0, 52.7)):
        p.drop_item("barrel", x, z)
    # фонарь/надписи
    p.remove["pieces"].append({"list": "signs", "rect": [162.8, 17.5, 163.8, 19.5]})
    p.remove["pieces"].append({"list": "signs", "rect": [138.8, 33.5, 139.8, 35.5]})
    p.add["signs"].append({"at": [153.0, 5.6, 2.1], "size": 44.0, "text": "пункт эвакуации · штаб ЧВК"})
    p.add["signs"].append({"at": [139.6, 3.6, -6.8], "size": 38.0, "text": "лагерь эвакуации · въезд по пропускам"})


def camp_perimeter(p) -> None:
    # север (по Z −47) и запад/юг с воротами; восток — прежний забор участка по X 190,8
    net(p, CX0, CZ0, CX1, CZ0)
    g_w = (-4.5, 0.5)                                         # западные ворота: Z −4,5…0,5 (центр −2, 5 м)
    net(p, CX0, CZ0, CX0, g_w[0])
    net(p, CX0, g_w[1], CX0, CZ1)
    g_s = (150.5, 155.5)                                      # южные ворота: X 150,5…155,5 (центр 153)
    net(p, CX0, CZ1, g_s[0], CZ1)
    net(p, g_s[1], CZ1, CX1, CZ1)
    p.add["signs"].append({"at": [141.0, 3.6, g_w[0] + 0.0], "size": 28.0, "text": "ворота"})
    p.add["signs"].append({"at": [g_s[0] + 2.5, 3.6, 58.1], "size": 28.0, "text": "ворота с автопарка"})
    # «змейка» блоками: у каждых ворот два блока в шахматном порядке, проходы по 2 м
    for x, z, yaw in ((144.0, -3.0, 0.0), (148.0, -1.0, 0.0)):
        p.put("jersey", x, z, yaw)
    for x, z, yaw in ((152.0, 56.5, 90.0), (154.0, 54.4, 90.0)):
        p.put("jersey", x, z, yaw)
    # ограждение зоны склада РАВ: сетка 2,4 м; калитка на западной стороне закрыта «под ключ»
    sx0, sx1, sz0, sz1 = 169.0, 188.0, -8.0, 10.0
    net(p, sx0, sz0, sx1, sz0)
    net(p, sx0, sz1, sx1, sz1)
    net(p, sx1, sz0, sx1, sz1)
    net(p, sx0, sz0, sx0, 0.4)
    net(p, sx0, 1.6, sx0, sz1)
    closed_door(p, sx0, 1.0, "z", 1.2, 0.0, "склад РАВ")
    p.add["signs"].append({"at": [sx0 - 0.3, 3.0, 1.0], "size": 26.0, "text": "склад РАВ · вход по ключу"})


def camp_zones(p) -> None:
    t = "army_tent"
    # --- жилые палатки (ряд, Z 46…56)
    for x in (148.0, 160.0, 172.0, 184.0):
        p.put(t, x, 51.0, 90.0)
    # --- штаб
    p.put(t, 153.0, 8.5, 0.0, 1.25)
    p.put(t, 160.5, 8.0, 0.0)
    p.put("mast", 147.0, 4.0, 0.0)
    p.put("mast", 147.0, 18.5, 0.0)
    p.put("m:U15_03", 148.2, 10.0, 90.0)
    p.put("m:U15_03", 148.2, 13.2, 90.0)
    p.put("armored_truck", 156.0, 18.0, 90.0)
    p.put("flagpole", 160.0, 15.5, 0.0)
    p.box(153.0, 0.2, 3.4, 5.0, 0.4, 0.6, "accent")                                 # штабной стол у входа (отдельно от палатки)
    # --- дезактивация
    p.put(t, 153.0, -14.0, 90.0, 1.4)
    for k in range(3):                                                              # каркасы-душевые
        x = 147.0 + 4.6 * k
        for dx in (-1.0, 1.0):
            for dz in (-0.7, 0.7):
                p.box(x + dx, 1.2, -7.0 + dz, 0.1, 2.4, 0.1, "steel")
        p.box(x, 2.4, -7.0, 2.2, 0.08, 1.7, "steel")
        p.box(x, 0.04, -7.0, 2.0, 0.03, 1.5, "accent", 0.0, False)                  # плёнка на полу
    for k in range(6):
        p.put("barrel", 144.8 + 0.8 * (k % 3), -18.6 + 0.8 * (k // 3), 0.0)
    p.box(158.5, 0.04, -7.0, 3.0, 0.03, 3.0, "dark", 0.0, False)
    # --- фильтр и регистрация: навес над столами, ограждения очередей
    p.slab("camp_filter_canopy", [145.0, -43.0, 163.0, -37.0], 3.2, 0.15, "steel")
    for x in (145.3, 154.0, 162.7):
        for z in (-42.8, -37.2):
            p.box(x, 1.6, z, 0.15, 3.2, 0.15, "steel")
    for x in (147.5, 151.5, 155.5, 159.5):
        p.box(x, 0.42, -39.8, 2.6, 0.84, 0.9, "accent")                             # столы регистрации
    for x in (148.0, 153.0, 158.0):
        for z in (-35.5, -33.0, -30.5):
            pass
    for x in (150.0, 154.0, 158.0):                                                  # очереди: ограждения полосами
        for z in (-35.5, -33.0):
            p.put("m:U01_02", x, z, 90.0)
    for x in (148.0, 152.0, 156.0, 160.0):
        p.put("suitcase", x, -38.3 + (x % 3) * 0.1, 10.0 * (x % 7))
    # --- медсанбат
    p.put(t, 175.5, -40.0, 90.0)
    p.put("ambulance", 178.5, -18.5, 90.0, 1.0, 0.0, 0.0, 0.0, "PV_ambulance")
    for k in range(4):
        p.box(173.5 + 3.0 * k, 0.45, -33.0 + (k % 2) * 3.0, 0.65, 0.35, 1.9, "accent")   # носилки
    p.box(175.5, 0.05, -26.5, 6.0, 0.04, 3.0, "accent", 0.0, False)
    # --- кухня
    p.slab("camp_kitchen_canopy", [146.0, 25.0, 160.0, 35.0], 3.0, 0.12, "steel")
    for x in (146.2, 153.0, 159.8):
        for z in (25.2, 34.8):
            p.box(x, 1.5, z, 0.14, 3.0, 0.14, "steel")
    p.box(150.0, 0.5, 26.6, 3.4, 1.0, 1.1, "steel")                                  # полевая кухня
    p.box(152.0, 1.7, 26.6, 0.3, 1.4, 0.3, "steel")                                  # труба
    for z in (29.5, 32.0):
        p.box(153.0, 0.42, z, 4.5, 0.84, 0.8, "accent")                              # столы
    for x, z in ((158.5, 31.0), (159.2, 31.0), (158.5, 31.7), (159.2, 31.7)):
        p.put("barrel", x, z, 0.0)
    # --- склад РАВ: контейнеры за сеткой
    for x in (172.0, 176.5, 181.0):
        p.put("container20", x, -3.0, 0.0)
    p.put("container20", 173.0, 6.5, 90.0)
    p.put("truck", 183.5, 6.5, 90.0)
    # --- ящик гуманитарки у калитки склада (место лута «Склад гуманитарки» — снаружи сетки)
    p.put("container20_open", 175.0, 13.2, 90.0)
    # --- вертолётная площадка 23 × 28: плита, круг и «Н», угловые огни (вертолёт не ставим)
    hx0, hx1, hz0, hz1 = 165.0, 188.0, 16.0, 44.0
    p.surface("camp_heli", "slab", hx0, hz0, hx1, hz1, 0.0, 0.12)
    cx, cz, r = 176.5, 30.0, 8.5
    for k in range(24):
        a = 2.0 * math.pi * k / 24
        px, pz = cx + r * math.cos(a), cz + r * math.sin(a)
        p.box(px, 0.135, pz, 2.3, 0.02, 0.35, "paint_white", -math.degrees(a) + 90.0, False)
    for dx in (-1.5, 1.5):
        p.box(cx + dx, 0.135, cz, 0.45, 0.02, 4.4, "marker", 0.0, False)
    p.box(cx, 0.135, cz, 3.0, 0.02, 0.45, "marker", 0.0, False)
    for x, z in ((hx0 + 0.6, hz0 + 0.6), (hx1 - 0.6, hz0 + 0.6), (hx0 + 0.6, hz1 - 0.6), (hx1 - 0.6, hz1 - 0.6)):
        p.box(x, 0.3, z, 0.3, 0.6, 0.3, "hazard_yellow")
    p.add["signs"].append({"at": [cx, 0.9, hz0 - 0.3], "size": 40.0, "text": "вертолётная площадка"})


def tower(p, b: B, x_stair0: float, z_stair: float, px: float, pz: float) -> None:
    """Вышка: площадка 3 × 3 на +5,5 на четырёх опорах, ограждение 1,05, прямой марш вдоль кромки лагеря (25°)."""
    top = 5.5
    for dx in (-1.35, 1.35):
        for dz in (-1.35, 1.35):
            p.box(px + dx, top / 2.0, pz + dz, 0.3, top, 0.3, "steel")
    p.slab(f"camp_tower_{int(px)}", [px - 1.5, pz - 1.5, px + 1.5, pz + 1.5], top, 0.2, "steel")
    direction = 1.0 if x_stair0 > px else -1.0
    edge_x = px + direction * 1.5
    gap = (z_stair - 0.7, z_stair + 0.7)
    for (xa, xb), z in (((px - 1.5, px + 1.5), pz - 1.45), ((px - 1.5, px + 1.5), pz + 1.45)):
        b.rail_x(z, xa, xb, top)
    b.rail_z(px - direction * 1.45, pz - 1.5, pz + 1.5, top)
    b.rail_z(edge_x - direction * 0.05, pz - 1.5, gap[0], top)
    b.rail_z(edge_x - direction * 0.05, gap[1], pz + 1.5, top)
    p.add["stairs"].append({"from": [x_stair0, 0.0, z_stair], "to": [edge_x, top, z_stair], "width": 1.2, "count": 33, "mat": "steel", "rails": "both"})
    p.box(px, top + 1.9, pz, 3.4, 0.12, 3.4, "dark")                                  # навес над площадкой
    for dx in (-1.5, 1.5):
        for dz in (-1.5, 1.5):
            p.box(px + dx, top + 0.95, pz + dz, 0.08, 1.9, 0.08, "steel")


def camp(p, b: B) -> None:
    camp_moves(p)
    camp_perimeter(p)
    camp_zones(p)
    tower(p, b, 157.0, -45.8, 143.5, -45.0)
    tower(p, b, 174.2, 57.0, 187.5, 56.0)
    p.log.append("лагерь: периметр сетка 2,4 м (запад, север, юг; восток — прежний забор X 190,8), ворота с площади (X 141,3; Z −2) и с автопарка "
                 "(153; 58) с блоками-«змейкой», 8 зон, склад РАВ за сеткой (калитка «под ключ»), площадка 23 × 28 с кругом и «Н», "
                 "две вышки +5,5 с ступенчатыми маршами 25°")


# =============================================================================================== сквер
def plaza_cuts(p) -> None:
    """Плиты сквера над туалетом остаются; в них режутся только спуски."""
    p.remove["pieces"].append({"list": "surfaces", "id": "square_n", "rect": [-8.0, 150.0, -3.0, 158.0]})
    p.add["surfaces"].append({"id": "square_n", "mat": "walk", "rect": [-50.0, 108.0, 39.35, 200.2], "t": 0.1, "y": 0.0,
                              "holes": [[-39.2, 109.5, -32.15, 112.5], [-17.85, 109.5, -10.8, 112.5]]})
    # низкая бетонная кромка по Z 112 (X −22…−4) пересекает спуск — режется
    p.remove["pieces"].append({"list": "walls", "rect": [-14.0, 111.9, -12.0, 112.4], "mat": "concrete"})
    p.wall(-22.0, 112.0, -17.85, 112.3, 0.0, 0.75, "concrete")
    p.wall(-10.8, 112.0, -4.0, 112.3, 0.0, 0.75, "concrete")
    # низкая кромка по X −4,3 (Z 112…138) пересекает вторую площадку: оставить Z 112…124
    p.remove["pieces"].append({"list": "walls", "rect": [-4.4, 124.0, -3.9, 126.0], "mat": "concrete"})
    p.wall(-4.3, 112.0, -4.0, 124.0, 0.0, 0.75, "concrete")
    # низкая стенка по Z 127,85 (X 2…22) и граффити-панель делят вторую площадку — прочь
    p.remove["pieces"].append({"list": "walls", "rect": [11.0, 127.7, 13.0, 128.0], "mat": "concrete"})
    p.remove["pieces"].append({"list": "boxes", "rect": [11.0, 127.9, 13.0, 128.2], "mat": "graffiti"})


def wc_under(p, b: B) -> None:
    fl, ceil_top, ht = -3.2, -0.02, 2.78
    x0, x1, z0, z1 = S2.WC_UNDER
    p.add["ground_holes"].append([x0 - 0.15, z0 - 0.15, x1 + 0.15, z1 + 0.15])
    p.add["ground_holes"].append([-39.2, 109.5, -32.15, 112.5])
    p.add["ground_holes"].append([-17.85, 109.5, -10.8, 112.5])
    p.slab("wc_floor", [x0 - 0.15, z0 - 0.15, x1 + 0.15, z1 + 0.15], fl, 0.3, "pit_floor")
    p.slab("wc_ceiling", [x0 - 0.15, z0 - 0.15, x1 + 0.15, z1 + 0.15], ceil_top, 0.4, "concrete")
    # наружные стены (0,3), двери со спусков
    b.wx(z0, x0 - 0.15, x1 + 0.15, fl, ht, [], TE, "concrete")
    b.wx(z1, x0 - 0.15, x1 + 0.15, fl, ht, [], TE, "concrete")
    b.wz(x0, z0 + 0.15, z1 - 0.15, fl, ht, [(111.0, 1.2, D)], TE, "concrete")
    b.wz(x1, z0 + 0.15, z1 - 0.15, fl, ht, [(111.0, 1.2, D)], TE, "concrete")
    # перегородки между М, кладовой и Ж: сквозной проход через две двери
    b.wz(-26.0, z0 + 0.15, z1 - 0.15, fl, ht, [(108.0, 1.2, D)], TI, "concrete")
    b.wz(-24.0, z0 + 0.15, z1 - 0.15, fl, ht, [(114.0, 1.2, D)], TI, "concrete")
    # кабинки и умывальники
    for xa, xb in ((-31.85, -26.15), (-23.85, -18.15)):
        k = 4
        for i in range(k + 1):
            x = xa + (xb - xa) * i / k
            p.box(x, fl + 0.95, z0 + 0.15 + 0.65, 0.04, 1.9, 1.3, "steel")
        for i in range(k):
            x = xa + (xb - xa) * (i + 0.5) / k
            p.box(x, fl + 0.2, z0 + 0.45, 0.4, 0.4, 0.6, "accent")                 # унитаз
        for i in range(3):
            x = xa + (xb - xa) * (i + 0.5) / 3.0
            p.box(x, fl + 0.85, z1 - 0.45, 0.55, 0.15, 0.45, "accent")             # умывальник
            p.box(x, fl + 0.4, z1 - 0.3, 0.1, 0.8, 0.1, "steel")
        p.box((xa + xb) / 2.0, fl + 1.55, z1 - 0.2, xb - xa, 0.9, 0.04, "steel")    # зеркала
    p.box(-25.9, fl + 0.9, 112.0, 0.2, 1.8, 0.6, "dark")                            # щит
    p.box(-24.3, fl + 0.5, 109.0, 0.4, 1.0, 1.2, "steel")                           # кладовая: стеллаж
    p.add["signs"].append({"at": [-29.0, fl + 2.3, z0 + 0.3], "size": 26.0, "text": "М"})
    p.add["signs"].append({"at": [-21.0, fl + 2.3, z0 + 0.3], "size": 26.0, "text": "Ж"})
    # спуски: 6,9 м × 3 (25,1°), стены по бокам, парапет 0,9, навес над нижней половиной
    for sx0, sx1, st, en in ((-39.2, -32.15, -39.2, -32.3), (-10.8, -17.85, -10.8, -17.7)):
        lo, hi = min(sx0, sx1), max(sx0, sx1)
        p.add["stairs"].append({"from": [st, 0.0, 111.0], "to": [en, fl, 111.0], "width": 2.9, "count": 19, "mat": "concrete",
                                "fill": fl})
        for zz in (109.35, 112.65):
            p.wall(lo, zz - 0.15, hi, zz + 0.15, fl, 0.9, "concrete")
        mid = (lo + hi) / 2.0
        ca, cb = (mid, hi) if st < en else (lo, mid)
        p.slab(f"wc_canopy_{int(lo)}", [ca, 109.2, cb, 112.8], 3.0, 0.2, "slab")
        for zz in (109.35, 112.65):
            p.wall(ca, zz - 0.15, cb, zz + 0.15, 0.9, 3.0, "concrete")
    p.add["signs"].append({"at": [-39.0, 1.9, 111.0], "size": 30.0, "text": "туалет · спуск"})
    p.add["signs"].append({"at": [-10.9, 1.9, 111.0], "size": 30.0, "text": "туалет · спуск"})
    p.log.append("подземный туалет: зал 14 × 10 на −3,2, свет 2,78, М и Ж по 4 кабины, кладовая со щитом, двери 1,2 в обе половины; "
                 "спуски удлинены до 6,9 м (25° вместо 28°), навес над нижней половиной, парапет 0,9")


def playgrounds(p) -> None:
    x0, x1, z0, z1 = S2.PLAYGROUND2
    p.surface("playground_n2", "walk", x0, z0, x1, z1, 0.0, 0.12)
    # ограда 0,9: две калитки по 2 м (север и юг)
    gate = (7.0, 9.0)
    for z in (z0, z1):
        for a, c in ((x0, gate[0]), (gate[1], x1)):
            p.box((a + c) / 2.0, 0.45, z, c - a, 0.9, 0.05, "steel")
    p.box(x0, 0.45, (z0 + z1) / 2.0, 0.05, 0.9, z1 - z0, "steel")
    p.box(x1, 0.45, (z0 + z1) / 2.0, 0.05, 0.9, z1 - z0, "steel")
    for x, z in ((-2.0, 130.0), (-2.0, 136.0)):
        p.put("swing", x, z, 90.0)
    p.put("slide", 17.0, 130.0, 0.0)
    p.put("climber", 12.0, 137.0, 0.0, 1.4)
    p.put("sandbox", 3.0, 138.0, 0.0)
    p.put("seesaw", 20.0, 138.0, 30.0)
    p.put("carousel", 8.0, 132.0, 0.0)
    for x, z, yaw in ((-5.8, 134.0, 90.0), (21.8, 134.0, 270.0), (3.0, 126.2, 180.0), (14.0, 141.8, 0.0)):
        p.put("bench", x, z, yaw)
    # прежняя площадка: турник, брусья, шведская стенка (X −49…−24, Z 150…178)
    p.box(-33.0, 1.3, 163.0, 0.12, 2.6, 0.12, "steel")
    p.box(-30.0, 1.3, 163.0, 0.12, 2.6, 0.12, "steel")
    p.box(-31.5, 2.45, 163.0, 3.2, 0.08, 0.08, "steel")
    for dz in (-0.35, 0.35):
        for x in (-28.0, -24.8):
            p.box(x, 0.45, 166.0 + dz, 0.08, 0.9, 0.08, "steel")
        p.box(-26.4, 0.95, 166.0 + dz, 3.4, 0.06, 0.06, "steel")
    p.box(-38.0, 1.2, 176.0, 3.0, 2.4, 0.1, "steel")                                  # шведская стенка: рама
    for i in range(7):
        p.box(-38.0, 0.3 + 0.33 * i, 175.95, 3.0, 0.04, 0.04, "paint_white")
    p.log.append("детская площадка 2: резина, ограда 0,9 с калитками (север и юг), городок, 2 качели, горка, песочница, карусель, качалка, 4 лавки; "
                 "на прежней: турник, брусья, шведская стенка")


def tree_points(p) -> tuple[list, int]:
    base = p.base()
    items = base["filler"]["items"]
    tiny = {"paper", "paper_ball", "bottle", "can", "bags", "shell", "dust", "glass_shards", "puddle", "trash_pile", "shell_open", "weed"}
    obst = [(it[1], it[2]) for it in items if it[0] not in tiny and -60 < it[1] < 60 and 95 < it[2] < 255]
    rects = []
    for bld in base["buildings"]:
        a, s = bld["at"], bld["size"]
        w, d = (s[1], s[0]) if abs(abs(bld.get("yaw", 0.0)) % 180.0 - 90.0) < 1.0 else (s[0], s[1])
        if -65 < a[0] < 65 and 90 < a[1] < 260:
            rects.append((a[0] - w / 2.0, a[0] + w / 2.0, a[1] - d / 2.0, a[1] + d / 2.0))
    walls = []
    for w in base["walls"]:
        r = w["rect"]
        if w["y0"] < 2.5 and -60 < r[0] < 60 and 95 < r[1] < 255:
            walls.append(tuple(r))
    routes = [r["points"] for r in base["probe_routes"] if r["id"] in ("prologue", "south_to_site", "yards_to_south", "tower_arch_s")]
    segs = []
    for pts in routes:
        for i in range(len(pts) - 1):
            segs.append((pts[i], pts[i + 1]))
    extra = [S2.PLAYGROUND2[0] - 1.5, S2.PLAYGROUND2[1] + 1.5, S2.PLAYGROUND2[2] - 1.5, S2.PLAYGROUND2[3] + 1.5]

    def seg_dist(px, pz, a, b):
        ax, az, bx, bz = a[0], a[1], b[0], b[1]
        dx, dz = bx - ax, bz - az
        L = dx * dx + dz * dz
        t = 0.0 if L == 0 else max(0.0, min(1.0, ((px - ax) * dx + (pz - az) * dz) / L))
        return math.hypot(px - (ax + t * dx), pz - (az + t * dz))

    out, skipped = [], 0
    for x, z0, z1, step in S2.TREE_ROWS:
        z = z0
        while z <= z1:
            ok = not any(k[0] <= x <= k[1] and k[2] <= z <= k[3] for k in S2.TREE_KEEPOUT)
            if ok and extra[0] <= x <= extra[1] and extra[2] <= z <= extra[3]:
                ok = False
            if ok and any(math.hypot(x - ox, z - oz) < 2.0 for ox, oz in obst):
                ok = False
            if ok and any(r[0] - 2.5 <= x <= r[1] + 2.5 and r[2] - 2.5 <= z <= r[3] + 2.5 for r in rects):
                ok = False
            if ok and any(w[0] - 1.5 <= x <= w[2] + 1.5 and w[1] - 1.5 <= z <= w[3] + 1.5 for w in walls):
                ok = False
            if ok and any(seg_dist(x, z, a, b) < 2.5 for a, b in segs):
                ok = False
            if ok and (-39.5 <= x <= -10.5) and (105.5 <= z <= 117.5):
                ok = False
            if ok:
                out.append((x, z))
            else:
                skipped += 1
            z += step
    return out, skipped


def trees(p) -> None:
    pts, skipped = tree_points(p)
    kinds = [("tree_birch", "P_birch_a", 0.0), ("tree_round", "P_linden_a", 0.7), ("tree_birch", "P_birch_b", 0.0),
             ("tree_round", "P_linden_c", 0.7), ("tree_birch", "P_birch_c", 0.0), ("tree_round", "P_linden_b", 0.7)]
    for i, (x, z) in enumerate(pts):
        kit, model, dy = kinds[(i * 5 + int(abs(x))) % len(kinds)]
        yaw = (i * 137.5) % 360.0
        s = 0.9 + 0.025 * (i % 9)
        p.put(kit, x, z, round(yaw, 1), round(s, 3), dy, -1, 0.0, model)
    p.log.append(f"деревья сквера: посажено {len(pts)}, пропущено {skipped} (кромки, вещи, постройки, стены и маршруты ближе 2,5 м)")
    p.trees_planted = len(pts)
    p.trees_skipped = skipped


# =============================================================================================== хоздвор «Зерна»
def zerno_yard(p, b: B) -> None:
    # лестница к чёрному ходу кофейни — у X −191,7…−185,3 вдоль Z −60,15; площадка у X −184,5 (не трогаем); у цветов — у X −172,7…−165,5.
    # проход — полоса Z −64,3…−60,8 свободна; вещи — вдоль южной кромки проезда (Z −66,3…−64,3).
    p.slab("zerno_canopy", [-194.0, -66.4, -182.0, -63.9], 3.0, 0.15, "steel")
    for x in (-193.8, -188.0, -182.2):
        p.box(x, 1.5, -66.2, 0.14, 3.0, 0.14, "steel")
        p.box(x, 1.5, -64.1, 0.14, 3.0, 0.14, "steel")
    for x in (-192.4, -190.6, -188.8):
        p.put("pallets", x, -65.2, 12.0 * (x % 5))
    p.put("boxes", -186.0, -65.9, 0.0)
    p.put("boxes", -184.8, -65.9, 0.0)
    for x in (-193.0, -192.3, -191.6):
        p.put("barrel", x, -64.6, 0.0)
    p.put("barrel", -182.8, -65.8, 0.0)
    # кеги и тара у восточного конца навеса и баки
    p.box(-181.0, 0.45, -65.9, 1.4, 0.9, 0.8, "steel")                               # ящик-морозильник
    p.put("dumpster", -179.0, -65.7, 0.0)
    p.put("dumpster", -177.2, -65.7, 0.0)
    p.put("pallets", -175.2, -65.4, 5.0)
    p.put("boxes", -175.0, -65.4, 0.0, 1.0, 0.15)
    # ограждение снаружи: сетка вокруг тары (проход вдоль проезда свободен)
    for x in (-174.0,):
        p.put("chainlink", x, -64.9, 0.0)
        p.put("chainlink", x, -66.0, 0.0)
    p.add["signs"].append({"at": [-188.0, 3.2, -66.35], "size": 26.0, "text": "хоздвор · приёмка товара"})
    p.log.append("хоздвор «Зерна»: навес 12 × 2,5 на 6 стойках, поддоны, ящики, кеги, два бака, морозильный ящик, сетка у восточного конца; "
                 "полоса проезда Z −64,3…−60,8 свободна")


# =============================================================================================== итог
def build(p):
    p.add.setdefault("ladders", [])
    b = B(p)
    police_removals(p)
    police_building(p, b)
    police_yard(p, b)
    camp(p, b)
    plaza_cuts(p)
    wc_under(p, b)
    playgrounds(p)
    trees(p)
    zerno_yard(p, b)
    return p
