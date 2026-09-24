# Генератор раскладки кольца 1F → data/sectors/f1_ring.json.
# python tools/gen_f1_ring.py
#
# Здание Ø250: крытый атриум Ø60 под куполом, галерея вокруг него, внутренние магазины,
# кольцевая улица, внешние магазины, подсобки, служебный коридор. Один главный вход с севера:
# прямая аллея 24 м (полосы "axis") от фасада до галереи атриума, кольцевая улица пересекает её
# перекрёстком. Вдоль аллеи — торговые модули (кольцевые помещения, обрезанные стеной аллеи,
# витрины — на аллею). Эскалаторы, постройки, спавны и эвакуации — узлы scenes/levels/f1_ring.tscn.
import json
import math
import os

R = dict(atr=(0.5, 30), gal=(30, 40), inn=(40, 65), st=(65, 79), out=(79, 109),
         back=(109, 121), svc=(121, 125))
OUTER, SITE = 125, 210
# ось главной аллеи (север) и её полуширина: проходы по ~10 м по бокам от пары эскалаторов
AX, HW = -90, 12
# открытая половина кольца и пожарные отсеки по 60°
A0, A1 = -180, 0
TILE, WORN, CONC = "large_floor_tiles_02", "worn_tile_floor", "concrete_floor_worn_001"
PLASTER, CWALL = "painted_plaster_wall", "concrete_wall_006"
ASPH, BLOCK = "asphalt_02", "concrete_block_wall_02"

rooms, ops = [], []


def room(id, name, type, a, r, floor=WORN, wall=PLASTER, **kw):
    d = {"id": id, "name": name, "type": type, "a": [round(a[0], 3), round(a[1], 3)], "r": list(r), "floor": floor, "wall": wall}
    d.update(kw)
    rooms.append(d)
    return d


def strip(id, name, type, r, floor=TILE, wall=PLASTER, **kw):
    d = {"id": id, "name": name, "type": type, "axis": AX, "t": [-HW, HW], "r": list(r), "floor": floor, "wall": wall}
    d.update(kw)
    rooms.append(d)


def op(wall, kind, **kw):
    d = {"wall": wall, "kind": kind}
    d.update(kw)
    ops.append(d)


def front(r, a0, a1, kind="storefront", frac=0.7):
    m, h = (a0 + a1) / 2, (a1 - a0) * frac / 2
    op("arc", kind, r=r, a=[round(m - h, 3), round(m + h, 3)])


def door(r, a0, a1, kind="door", w_m=1.8):
    m = (a0 + a1) / 2
    h = math.degrees(w_m / 2 / r)
    op("arc", kind, r=r, a=[round(m - h, 3), round(m + h, 3)])


def s_at(r, t):
    """Где боковая линия аллеи t пересекает дугу r — м вдоль оси от центра."""
    return math.sqrt(r * r - t * t)


def a_at(r, t):
    """Угол точки на дуге r, лежащей на боковой линии аллеи t."""
    return AX + math.degrees(math.asin(t / r))


def along(t, s0, s1, kind="storefront", frac=0.7, w_m=None):
    m = (s0 + s1) / 2
    h = (s1 - s0) * frac / 2 if w_m is None else w_m / 2
    op("along", kind, axis=AX, t=t, s=[round(m - h, 3), round(m + h, 3)])


# ---------------------------------------------------------------- пояса кольца
room("atrium", "Атриум под куполом", "atrium", (A0, A1), R["atr"], TILE, note="крытый атриум Ø60, фонтан в центре")
room("gallery", "Галерея атриума", "gallery", (A0, A1), R["gal"], TILE, label_a=-100)
room("ring_street", "Кольцевая улица", "gallery", (A0, A1), R["st"], TILE, label_a=-100, note="пересекает главную аллею перекрёстком")
op("arc", "open", r=R["atr"][1], a=[A0, A1], note="атриум открыт на галерею")
for a in (A0, A1):
    op("radial", "barrier", a=a, r=list(R["atr"]))
    for k in ("gal", "st", "svc"):
        op("radial", "locked", a=a, r=list(R[k]))

# ---------------------------------------------------------------- главная аллея (полосы)
strip("alley_in", "Главная аллея", "gallery", (R["inn"][0], R["inn"][1]))
strip("alley_out", "Главная аллея", "gallery", (R["out"][0], 115), note="пара эскалаторов — узел сцены")
strip("vestibule", "Главный вестибюль", "gallery", (115, OUTER), note="единственный вход для посетителей")
for r in (R["inn"][0], R["inn"][1], R["st"][1], 115):
    op("arc", "open", r=r, a=[round(a_at(r, -HW), 3), round(a_at(r, HW), 3)])
# фасад входа: три стеклянных секции, в каждой — двери
e0, e1 = a_at(OUTER, -HW), a_at(OUTER, HW)
for i in range(3):
    op("arc", "storefront", r=OUTER, a=[round(e0 + (e1 - e0) * i / 3, 3), round(e0 + (e1 - e0) * (i + 1) / 3, 3)],
       note="главный вход" if i == 1 else "")
# служебные двери из вестибюля в служебный коридор (по обе стороны)
for t in (-HW, HW):
    along(t, s_at(122, t), s_at(124, t), "door", w_m=1.8)

# ---------------------------------------------------------------- сектор N: модули вдоль аллеи
N0, N1 = -118, -62
OUT_BANDS = [(79, 89), (89, 99), (99, 109)]
IN_BANDS = [(40, 52.5), (52.5, 65)]
N_SIDES = [
    # сторона, угол, t стены аллеи, модули внешнего пояса, внутреннего, подсобки [(id, name, type, от, до)]
    dict(a=(N0, AX), t=-HW,
         out=[("clothes", "Одежда", "retail"), ("sport", "Спорттовары", "retail"), ("jewelry", "Ювелирный", "retail")],
         inn=[("coffee", "Кофейня", "retail"), ("pharmacy", "Аптека", "retail")],
         back=[("jewelry_vault", "Сейфовая ювелирного", "storage", N0, -104, {"key": "key_jewelry"}),
               ("clothes_st", "Склад одежды", "storage", -104, AX, {})]),
    dict(a=(AX, N1), t=HW,
         out=[("phones", "Салон связи", "retail"), ("electronics", "Электроника", "retail"), ("photo", "Фото", "retail")],
         inn=[("bank", "Банк", "office"), ("cosmetics", "Косметика", "retail")],
         back=[("electronics_st", "Склад электроники", "storage", AX, -76, {}),
               ("staff", "Раздевалка персонала", "office", -76, N1, {})]),
]
for side in N_SIDES:
    a0, a1 = side["a"]
    t = side["t"]
    # видимая часть дуги модуля — от стены аллеи до края сектора
    vis = lambda r: (a0, a_at(r, t)) if t < 0 else (a_at(r, t), a1)
    for (rid, name, typ), band in zip(side["out"], OUT_BANDS):
        room(rid, name, typ, (a0, a1), band, WORN, PLASTER)
        along(t, s_at(band[0], t), s_at(band[1], t))
        if band[0] == R["out"][0]:
            front(band[0], *vis(band[0]))  # угловой: витрина и на кольцевую улицу
    for (rid, name, typ), band in zip(side["inn"], IN_BANDS):
        room(rid, name, typ, (a0, a1), band, WORN, PLASTER)
        along(t, s_at(band[0], t), s_at(band[1], t))
        if band[0] == R["inn"][0]:
            front(band[0], *vis(band[0]))  # угловой: витрина и на галерею атриума
        else:
            front(band[1], *vis(band[1]))  # угловой: витрина и на кольцевую улицу
    for rid, name, typ, b0, b1, extra in side["back"]:
        room(rid, name, typ, (b0, b1), R["back"], CONC, CWALL, **extra)
        v0, v1 = max(b0, vis(R["back"][0])[0]), min(b1, vis(R["back"][0])[1])
        door(R["back"][0], v0, v1)
        w0, w1 = max(b0, vis(R["back"][1])[0]), min(b1, vis(R["back"][1])[1])
        door(R["back"][1], w0, w1)

# ---------------------------------------------------------------- переходы на границах отсеков
for b, tag in ((-120, "w"), (-60, "e")):
    a = (b - 2, b + 2)
    room(f"pass_in_{tag}", "Проход", "corridor", a, R["inn"], TILE)
    room(f"pass_out_{tag}", "Проход", "corridor", a, R["out"], TILE)
    room(f"core_{tag}", "Техядро", "utility", a, R["back"], CONC, CWALL, core=True, note="лестницы, лифты, WC")
    for r in (R["inn"][0], R["inn"][1], R["out"][0]):
        op("arc", "open", r=r, a=list(a))
    door(R["back"][0], *a)
    door(R["back"][1], *a)

# ---------------------------------------------------------------- боковые отсеки
SECTORS = [
    dict(c=-150, id="nw", w0=A0, e1=-122,
         inner=[("shoes", "Обувь", "retail", 13.75), ("watches", "Часы", "retail", 13.75), None,
                ("kids", "Детские товары", "retail", 12.75), ("toys", "Игрушки", "retail", 12.75)],
         outer=[("diy", "Дом и ремонт", "retail", 27.5), None, ("hardware", "Хозтовары", "retail", 25.5)],
         back=[("diy_st", "Склад «Дом и ремонт»", "storage", 17.5), ("workshop", "Мастерская", "utility", 10), None,
               ("hardware_st", "Склад хозтоваров", "storage", 15.5), ("service", "Сервисный центр", "office", 10)],
         hall=("exit_nw", "Выход к паркингу", "exit")),
    dict(c=-30, id="ne", w0=-58, e1=A1,
         inner=[("flowers", "Цветы", "retail", 12.75), ("press", "Пресса и табак", "retail", 12.75), None,
                ("books", "Книги", "retail", 13.75), ("optics", "Оптика", "retail", 13.75)],
         outer=[("hyper", "Гипермаркет", "retail", 25.5), None, ("department", "Универмаг", "retail", 27.5)],
         back=[("hyper_st", "Склад гипермаркета", "storage", 14.5), ("cold", "Холодильные камеры", "storage", 11), None,
               ("electrical", "Электрощитовая", "utility", 8), ("server", "Серверная", "office", 8, {"key": "key_server"}),
               ("cpu", "ЦПУ охраны", "security", 11.5)],
         hall=("loading_bay", "Грузовой шлюз", "loading")),
]
PW = 2.5  # полуширина радиального прохода по центру отсека, град
svc_segments = [(N0, N1)]
for s in SECTORS:
    c = s["c"]
    pa = (c - PW, c + PW)
    room(f"pass_in_{s['id']}", "Проход", "corridor", pa, R["inn"], TILE)
    room(f"pass_out_{s['id']}", "Проход", "corridor", pa, R["out"], TILE)
    for r in (R["inn"][0], R["inn"][1], R["out"][0]):
        op("arc", "open", r=r, a=list(pa))
    hid, hname, hkind = s["hall"]
    if hkind == "exit":
        room(hid, hname, "corridor", pa, (R["back"][0], OUTER), TILE, note="пожарный выход, крытый переход к паркингу")
        op("arc", "open", r=R["back"][0], a=list(pa))
        door(OUTER, *pa, w_m=2.0)
    else:
        room(hid, hname, "storage", pa, (R["back"][0], OUTER), CONC, CWALL)
        op("arc", "shutter", r=R["back"][0], a=[c - 1.5, c + 1.5])
        op("arc", "gate", r=OUTER, a=[c - 2, c + 2], note="ворота на погрузку")
    # из служебного коридора — двери в зал выхода / шлюз
    for a in pa:
        op("radial", "door", a=a, r=[122.1, 123.9])
    for ring_key, row in (("inn", s["inner"]), ("out", s["outer"]), ("back", s["back"])):
        a = s["w0"]
        for item in row:
            if item is None:
                a = c + PW
                continue
            rid, name, typ, span = item[:4]
            extra = item[4] if len(item) > 4 else {}
            b = a + span
            if ring_key == "back":
                room(rid, name, typ, (a, b), R["back"], CONC, CWALL, **extra)
                door(R["back"][0], a, b)
                door(R["back"][1], a, b)
            else:
                room(rid, name, typ, (a, b), R[ring_key], WORN, PLASTER, **extra)
                if ring_key == "inn":
                    front(R["inn"][0], a, b)
                    door(R["inn"][1], a, b)  # чёрный ход на кольцевую улицу
                else:
                    front(R["out"][0], a, b)
            a = b
        assert abs(a - s["e1"]) < 0.01, (s["id"], ring_key, a, s["e1"])
    svc_segments.append((s["w0"], c - PW))
    svc_segments.append((c + PW, s["e1"]))

merged = []
for seg in sorted(svc_segments):
    if merged and abs(merged[-1][1] - seg[0]) <= 4.01:
        merged[-1] = (merged[-1][0], seg[1])
    else:
        merged.append(seg)
for i, (a, b) in enumerate(merged):
    room(f"svc_{i}", "Служебный коридор", "corridor", (a, b), R["svc"], CONC, CWALL)

# ---------------------------------------------------------------- снаружи — только земля
room("ring_drive", "Кольцевой проезд", "yard", (A0, A1), (OUTER, 140), ASPH, BLOCK, outdoor=True, label_a=-68)
room("plaza_n", "Площадь главного входа", "yard", (-104, -76), (140, 185), TILE, BLOCK, outdoor=True,
     note="клумбы, остановка автобуса")
room("dock_yard", "Грузовой двор", "yard", (-42, -18), (140, 172), ASPH, BLOCK, outdoor=True)
room("lot_nw", "Открытая парковка", "parking", (-178, -160), (140, 195), ASPH, BLOCK, outdoor=True)

d = {
    "id": "f1_ring",
    "name": "1F · открытая половина кольца",
    "floor": 1,
    "angle": [A0, A1],
    "ring": {"outer_r": OUTER, "atrium_r": R["atr"][1], "floors": 4, "zones": R, "sectors_deg": 60, "site_r": SITE},
    "alley": {"axis": AX, "half_width": HW},
    "sectors": [{"id": "nw", "name": "Паркинг", "a": [-180, -120]},
                {"id": "n", "name": "Главный вход", "a": [-120, -60]},
                {"id": "ne", "name": "Технический", "a": [-60, 0]}],
    "walls": {"height": 6.0, "thickness": 0.3, "fence_height": 2.2, "barrier_height": 1.2,
              "facade": 0.5, "fire": 0.3, "structural": 0.3, "partition": 0.15, "fence": 0.25,
              "column": 0.6, "column_grid": 9.0, "building_height": 22.5, "site_fence_height": 3.0},
    "greybox": True,
    "arch": {"storefront_h": 3.6, "door_h": 2.1, "shutter_h": 3.2, "gate_h": 4.5, "entrance_w": 3.2, "broken_pane_pct": 22},
    "camera_yaw": -45,
    "spawn": {"a": -100, "r": 176},
    "rooms": rooms,
    "openings": ops,
}
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "sectors", "f1_ring.json")
with open(out, "w", encoding="utf-8") as f:
    json.dump(d, f, ensure_ascii=False, indent=1)
print(len(rooms), "rooms", len(ops), "openings")
