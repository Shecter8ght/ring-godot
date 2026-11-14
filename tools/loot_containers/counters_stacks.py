"""Опоры касс v01, отделка: стек Painter (заводская отделка по фото-основам CC0 + износ сразу, как в v03 партии 1: вещь послужила
лет десять и брошена два года назад). Выполняется внутри Painter (counters_sp.py через мост). Помощники износа — lc3_stacks.py.

Основы (ambientCG, CC0 1.0; _asset_src/textures/<id>/):
  ЛДСП (пласть)         Wood092 — светлый шпон-ламинат, волокно вдоль длинной стороны; поверх плоский тон (0,74; 0,64; 0,47)
  накладка / тёмный акцент   Wood066 — тёмный орех
  сердечник ДСП         Chipboard001 / Chipboard003 — стружка, на сбитых кромках и углах, у пола — вспученные куски
  нержавейка            Metal009 — шлифовка вдоль X
  крашеная сталь бокса  Metal030 — серо-синяя краска
  столешница, стол      Plastic011 — тёмно-серый постформинг (мелкая неровность), крошка — высотой
  чёрный пластик, лента Plastic012A;  пластик бортов Plastic018A;  оцинковка Metal014 (спангл)
РИСУНОК износа — фото-маски из masks_v03 (E:/Models Blender/Маски_АЛЬФА, lc3_masks.py); МЕСТО — карты зон wear_counters
(counters_zones.py: кромки из 3D, верх, низ, ручка, место кассира, дорожка товара).
"""
import os

import substance_painter.layerstack as L

import lc3_stacks as S
import sp_finish
import sp_lib
from sp_lib import CH

SRC = S.SRC
TEX = "E:/Games/RING-godot/_asset_src/textures"
S.zone_path = lambda zone: f"{SRC}/wear_counters/{S.CTX['game']}_{zone}.png"   # зоны этих наборов — своя папка
_m, _above, _layer, _scope, zone, spread, ao_seams = S._m, S._above, S._layer, S._scope, S.zone, S.spread, S.ao_seams
PRINT = "Печать"
LEVEL = 0.5   # уровень высоты краски / ламината


# ---------------------------------------------------------------------------------------------- классы деталей
def base_name(m: str) -> str:
    return m.rsplit(".", 1)[0] if m.rsplit(".", 1)[-1].isdigit() else m


COUNTER = {
    "lam": ["ПТ_боковины", "ПТ_дно", "ПТ_перегородки", "ПТ_полки", "ПТ_панель_передняя", "ПТ_ящик_лицо", "ПТ_ящик_короб"],
    "lam_edge": ["ПТ_боковины__кромка", "ПТ_дно__кромка", "ПТ_перегородки__кромка", "ПТ_полки__кромка", "ПТ_панель_передняя__кромка",
                 "ПТ_ящик_лицо__кромка", "ПТ_ящик_короб__кромка", "ПТ_ящик_дно_ХДФ", "ПТ_накладка_полоса__кромка"],
    "trim": ["ПТ_накладка_полоса"],
    "top": ["ПТ_столешница"],
    "top_edge": ["ПТ_столешница__кромка"],
    "skirt": ["ПТ_цоколь_планка"],
    "dark": ["ПТ_кабельный_вывод", "ПТ_опоры_пятки", "ПТ_монетница", "ПТ_монетница_коврик"],
    "zinc": ["ПТ_штифты_полок", "ПТ_эксцентрики", "ПТ_уголки", "ПТ_опоры_штанги", "ПТ_ящик_рельсы_неподвижные",
             "ПТ_ящик_рельсы_подвижные", "ПТ_ящик_ручка", "ПТ_держатель_пакетов"],
    "plug": ["ПТ_заглушки_конфирматов"],
    "bags": ["ПТ_пакеты_стопка"],
    "label": ["ПТ_наклейка_инвентарник"],
}
CHECKOUT = {
    "paint": ["КБ_корпус", "КБ_полка_корзин", "КБ_подставка_кассы"],
    "skirt": ["КБ_цоколь"],
    "dark": ["КБ_швы_панелей", "КБ_кабельные_выводы", "КБ_сканер_рамка"],
    "ss": ["КБ_столешница_нержавейка", "КБ_столешница_сканер", "КБ_столешница_сканер__кромка", "КБ_ограждение_труба", "КБ_отбойник_труба",
           "КБ_стол_ножка", "КБ_стойка_номера", "КБ_накопитель_бортик"],
    "belt": ["КБ_лента_транспортёра"],
    "plastic": ["КБ_борта_пластик", "КБ_дверца_сервисная", "КБ_табличка_корпус"],
    "top": ["КБ_стол_кассира"],
    "lam_edge": ["КБ_стол_кассира__кромка", "КБ_стол_торцевая_панель__кромка"],
    "glam": ["КБ_стол_торцевая_панель"],
    "zinc": ["КБ_полка_уголки"],
    "white": ["КБ_табличка_панели", "КБ_лампа"],
    "glass": ["КБ_сканер_стекло"],
}
CLASSES = {"cn_counter": COUNTER, "cn_checkout": CHECKOUT}


def classify(game: str, meshes: list[str]) -> dict:
    table = CLASSES[game]
    out = {k: [] for k in table}
    miss = []
    for m in meshes:
        b = base_name(m)
        for k, names in table.items():
            if b in names:
                out[k].append(m)
                break
        else:
            miss.append(m)
    if miss:   # неизвестная деталь — по префиксу: кромка к кромке, остальное в пластик
        print("без класса:", miss)
    return {k: v for k, v in out.items() if v}


# ---------------------------------------------------------------------------------------------- основа
def photo(name, pos, setname, period, bbox, rot=0.0, color=0.55, rough=0.5, height=0.35, cmode=None):
    """Слой фото-основы CC0: цвет — наложением на плоский тон, блеск — смесью, рельеф — картой высоты; трёхпроекционно."""
    lay = L.insert_fill(pos)
    lay.set_name(f"{name} · фото {setname}")
    p = f"{TEX}/{setname}"
    chans = {CH.BaseColor: sp_finish._bitmap(f"{p}/color_2k.jpg")} if color else {}
    if rough:
        chans[CH.SpecularRoughness] = sp_finish._bitmap(f"{p}/roughness_2k.jpg")
    if height:
        chans[CH.Height] = sp_finish._bitmap(f"{p}/height_2k.jpg")
    lay.active_channels = set(chans)
    for c, src in chans.items():
        lay.set_source(c, src)
    if color:
        lay.set_blending_mode(cmode or L.BlendingMode.Overlay, CH.BaseColor)
        lay.set_opacity(color, CH.BaseColor)
    if rough:
        lay.set_opacity(rough, CH.SpecularRoughness)
    if height:
        lay.set_blending_mode(L.BlendingMode.Overlay, CH.Height)
        lay.set_opacity(height, CH.Height)
    sp_lib.triplanar(lay, bbox / period, rot)
    return lay


def core_layer(name, pos, setname, period, bbox, tint=None, rot=0.0):
    """Сердечник ДСП: фото стружки целиком (цвет, блеск, рельеф), маску кладёт зона × чешуйки."""
    lay = L.insert_fill(pos)
    lay.set_name(name)
    p = f"{TEX}/{setname}"
    chans = {CH.BaseColor: sp_finish._bitmap(f"{p}/color_2k.jpg"), CH.SpecularRoughness: sp_finish._bitmap(f"{p}/roughness_2k.jpg"),
             CH.Height: sp_finish._bitmap(f"{p}/height_2k.jpg"), CH.BaseMetalness: sp_lib._val(0.0, data=True)}
    lay.active_channels = set(chans)
    for c, src in chans.items():
        lay.set_source(c, src)
    lay.set_blending_mode(L.BlendingMode.Normal, CH.BaseColor)
    lay.set_opacity(1.0, CH.BaseColor)
    lay.set_opacity(0.95, CH.SpecularRoughness)
    lay.set_blending_mode(L.BlendingMode.Overlay, CH.Height)
    lay.set_opacity(0.15, CH.Height)
    sp_lib.triplanar(lay, bbox / period, rot)
    return lay


def flat(name, pos, color, rough, metal=0.0, height=LEVEL):
    return sp_lib.fill(name, pos, color=color, rough=rough, metal=metal, height=height)


def base_layers(pos, meshes, bbox, k, kind, game):
    """Заводская отделка вида: плоский тон + фото-основа (+ рельеф). Круг 2: ламинат — серый высокочастотный декор
    Wood066_decor поверх ровного тона (печатный декор ЛДСП, без «досок» и розового), краска бокса — тон ровный, от фото
    Metal029 только шагрень (блеск и рельеф), лента — продольный рельеф от шлифовки Metal009, цоколи — ровный чёрный."""
    made = []
    spec = {
        "lam": ((0.80, 0.71, 0.56), 0.55, 0.0, "Wood066_decor", 380, 0.0, 0.55, 0.12, 0.02),
        "trim": ((0.17, 0.11, 0.08), 0.50, 0.0, "Wood066_decor", 300, 0.0, 0.60, 0.12, 0.0),
        "lam_edge": ((0.74, 0.65, 0.51), 0.40, 0.0, None, 0, 0, 0, 0, 0),
        "top_edge": ((0.15, 0.15, 0.16), 0.40, 0.0, None, 0, 0, 0, 0, 0),
        "top": ((0.17, 0.175, 0.185), 0.45, 0.0, "Plastic011", 400, 0.0, 0.20, 0.20, 0.0),
        "dark": ((0.13, 0.13, 0.13), 0.65, 0.0, "Plastic012A", 300, 0.0, 0.25, 0.15, 0.03),
        "skirt": ((0.115, 0.115, 0.115), 0.62, 0.0, "Plastic012A", 300, 0.0, 0.0, 0.15, 0.02),
        "zinc": ((0.60, 0.61, 0.60), 0.40, 1.0, "Metal014", 300, 0.0, 0.30, 0.25, 0.05),
        "plug": ((0.70, 0.61, 0.48), 0.45, 0.0, None, 0, 0, 0, 0, 0),
        "bags": ((0.84, 0.84, 0.80), 0.35, 0.0, None, 0, 0, 0, 0, 0),
        "label": ((0.85, 0.84, 0.78), 0.70, 0.0, None, 0, 0, 0, 0, 0),
        "paint": ((0.40, 0.47, 0.52), 0.52, 0.0, "Metal029", 150, 0.0, 0.0, 0.12, 0.0),
        "ss": ((0.74, 0.74, 0.73), 0.32, 1.0, "Metal009", 450, 0.0, 0.40, 0.55, 0.0),
        "belt": ((0.12, 0.12, 0.12), 0.85, 0.0, "Metal009", 220, 0.0, 0.0, 0.20, 0.12),
        "plastic": ((0.66, 0.67, 0.67), 0.48, 0.0, "Plastic018A", 350, 0.0, 0.30, 0.30, 0.04),
        "glam": ((0.22, 0.23, 0.24), 0.50, 0.0, "Plastic011", 400, 0.0, 0.30, 0.25, 0.0),
        "white": ((0.86, 0.86, 0.83), 0.35, 0.0, "Plastic018A", 350, 0.0, 0.20, 0.30, 0.03),
        "glass": ((0.12, 0.14, 0.16), 0.12, 0.0, None, 0, 0, 0, 0, 0),
    }[kind]
    color, rough, metal, pset, period, rot, c, r, h = spec
    f = flat(f"Основа — {kind}", pos, color, rough, metal)
    made.append(_scope(f, meshes))
    if pset:
        p = photo(f"Фото — {kind}", _above(f), pset, period, bbox, rot, c, r, h)
        made.append(_scope(p, meshes))
    return made


# ---------------------------------------------------------------------------------------------- износ
CORE = "Chipboard001_pale"
CORE2 = "Chipboard003_pale"


def _chips_core(pos, meshes, bbox, name="Сколы до ДСП (зона chips)"):
    """Сколы — мелкие пятна по причине (counters_zones.chip_blobs: углы, кромка у продавца, низ, лицо ящика): в них
    сердечник ДСП. Маска — карта мест по развёртке целиком, без порога (без «лесенки»)."""
    c = core_layer(name, pos, CORE, 380, bbox)
    zone(c, "chips")
    return _scope(c, meshes)


def wear_lam(pos, meshes, bbox, k, trim=False):
    """ЛДСП: печатный декор почти ровный; сколы до ДСП точками, низ у пола — сырость узкой полосой, следы обуви внизу,
    грязь в стыках, жир у ручки ящика. Пыли пятнами нет (круглые пятна SI012 владелец не принимает)."""
    made = []
    last = None
    if not trim:
        t = _layer("Тон декора — мягкие пятна (SI014)", pos, color=(0.86, 0.84, 0.80), cmode=L.BlendingMode.Multiply, cop=0.45 * k,
                   rough=0.04, rmode="add", rop=0.3)
        spread(t, S.si(14), 2200, bbox, rot=0.4)
        made.append(_scope(t, meshes))
        last = t
    c = _chips_core(pos if last is None else _above(last), meshes, bbox)
    made.append(c)
    last = c
    d = _layer("Грязь в стыках (AO × dirt_4)", _above(last), color=(0.20, 0.17, 0.13), cop=0.45 * k, rough=0.88, rop=0.8, metal=0.0, height=0.5)
    ao_seams(d, bbox, "dirt_4", 1400)
    made.append(_scope(d, meshes))
    last = d
    if trim:
        return made
    w = _layer("Низ — сырость (floor × grunge_3)", _above(last), color=(0.62, 0.55, 0.46), cmode=L.BlendingMode.Multiply, cop=0.55 * k,
               rough=0.8, rop=0.5, metal=0.0)
    zone(w, "floor", S.sh("grunge_3"), 1500, bbox, rot=0.2)
    made.append(_scope(w, meshes))
    r = _layer("Следы обуви внизу (kick_low × Rubber01)", _above(w), color=(0.40, 0.37, 0.33), cmode=L.BlendingMode.Multiply,
               cop=0.45 * k, rough=-0.05, rmode="add", rop=0.4)
    zone(r, "kick_low", _m("Rubber01"), 500, bbox, rot=0.0)
    made.append(_scope(r, meshes))
    hd = _layer("Ручка ящика — жир (touch × Fingerprints001)", _above(r), color=(0.66, 0.60, 0.50), cmode=L.BlendingMode.Multiply,
                cop=0.30 * k, rough=-0.1, rmode="add", rop=0.6)
    zone(hd, "touch", S.fp(1), 600, bbox, rot=0.7)
    made.append(_scope(hd, meshes))
    return made


def wear_trim(pos, meshes, bbox, k):
    return wear_lam(pos, meshes, bbox, k, trim=True)


def wear_edge(pos, meshes, bbox, k, top=False):
    """Кромка ПВХ 2 мм: почти целая. Затёртость и светлая полоса истирания по ребру (зона кромки из 3D × SI007),
    у столешницы — сильнее со стороны продавца; 3–6 мелких сколов 2–8 мм до ДСП по местам (зона chips) с побелевшим
    пластиком вокруг (chips_halo)."""
    made = []
    e = _layer("Истирание по ребру (edge × SI007)", pos, color=(0.55, 0.53, 0.50) if top else (0.86, 0.80, 0.70), cmode=L.BlendingMode.Screen,
               cop=0.16 * k, rough=0.12, rmode="add", rop=0.6)
    zone(e, "edge", S.si(7), 500, bbox, rot=0.3)
    made.append(_scope(e, meshes))
    last = e
    if top:
        rs = _layer("Полоса истирания у продавца (rim_sell × SI007)", _above(last), color=(0.62, 0.60, 0.57), cmode=L.BlendingMode.Screen,
                    cop=0.30 * k, rough=0.10, rmode="add", rop=0.6)
        zone(rs, "rim_sell", S.si(7), 400, bbox, rot=1.1)
        made.append(_scope(rs, meshes))
        last = rs
    hl = _layer("Побелевший ПВХ вокруг сколов (chips_halo)", _above(last), color=(0.60, 0.58, 0.55) if top else (0.90, 0.86, 0.78),
                cmode=L.BlendingMode.Screen, cop=0.35, rough=0.1, rmode="add", rop=0.5)
    zone(hl, "chips_halo")
    made.append(_scope(hl, meshes))
    c = _chips_core(_above(hl), meshes, bbox)
    made.append(c)
    return made


def wear_top_edge(pos, meshes, bbox, k):
    return wear_edge(pos, meshes, bbox, k, top=True)


def wear_top(pos, meshes, bbox, k):
    """Постформинг (столешница, стол кассира): чуть неоднородный матовый пластик; перед кассой и у монетницы затёрто
    глаже и с бликом (руки, монеты), там же мелкие царапины маской владельца с малой силой; грязь в стыках.
    Пыли пятнами и «паутины» царапин нет."""
    made = []
    m = _layer("Неоднородность матового (Smear004, блеск)", pos, rough=0.06, rmode="add", rop=0.6)
    spread(m, S.sm(4), 1800, bbox, rot=0.3)
    made.append(_scope(m, meshes))
    g = _layer("Затёрто руками перед кассой (touch × SI014)", _above(m), color=(0.50, 0.50, 0.50), cmode=L.BlendingMode.Screen, cop=0.05 * k,
               rough=-0.16, rmode="add", rop=0.8)
    zone(g, "touch", S.si(14), 900, bbox, rot=0.3)
    made.append(_scope(g, meshes))
    gc = _layer("Затёрто у монетницы (cups × SI014)", _above(g), color=(0.50, 0.50, 0.50), cmode=L.BlendingMode.Screen, cop=0.05 * k,
                rough=-0.14, rmode="add", rop=0.8)
    zone(gc, "cups", S.si(14), 900, bbox, rot=1.2)
    made.append(_scope(gc, meshes))
    sc = _layer("Мелкие царапины (touch × Scratches004)", _above(gc), color=(0.42, 0.42, 0.42), cmode=L.BlendingMode.Screen, cop=0.12 * k,
                rough=-0.04, rmode="add", rop=0.4)
    zone(sc, "touch", S.sc(4), 700, bbox, rot=0.2)
    made.append(_scope(sc, meshes))
    d = _layer("Грязь в стыках (AO × dirt_4)", _above(sc), color=(0.16, 0.14, 0.11), cop=0.30 * k, rough=0.85, rop=0.6)
    ao_seams(d, bbox, "dirt_4", 1200)
    made.append(_scope(d, meshes))
    return made


def wear_belt(pos, meshes, bbox, k):
    """Чёрная резина ленты: продольный рельеф (основа), по ходу ленты затёрто глаже, продольные полосы истирания."""
    made = []
    p = _layer("Затёрто по ходу ленты (track)", pos, color=(0.30, 0.30, 0.30), cmode=L.BlendingMode.Screen, cop=0.05 * k,
               rough=-0.14, rmode="add", rop=0.7)
    zone(p, "track")
    made.append(_scope(p, meshes))
    tr = _layer("Продольные полосы истирания (track × Scratches004)", _above(p), color=(0.34, 0.34, 0.34), cmode=L.BlendingMode.Screen,
                cop=0.22 * k, rough=-0.08, rmode="add", rop=0.5)
    zone(tr, "track", S.sc(4), 600, bbox, rot=0.0)
    made.append(_scope(tr, meshes))
    return made


def wear_plastic(pos, meshes, bbox, k):
    """Светло-серый пластик бортов: затёртые кромки, тёмные риски, грязь в стыках (без пыли пятнами)."""
    made = []
    e = _layer("Затёртые кромки (edge × ChipsEdge50)", pos, color=(0.80, 0.80, 0.79), cmode=L.BlendingMode.Screen, cop=0.25 * k, rough=0.15,
               rmode="add", rop=0.6)
    zone(e, "edge", _m("ChipsEdge50"), 520, bbox, rot=0.3, harden=(0.45, 0.5))
    made.append(_scope(e, meshes))
    r = _layer("Тёмные риски (Scratches003)", _above(e), color=(0.40, 0.40, 0.40), cmode=L.BlendingMode.Multiply, cop=0.45 * k, rough=0.1,
               rmode="add", rop=0.4)
    spread(r, S.sc(3), 800, bbox, rot=0.4)
    made.append(_scope(r, meshes))
    d = _layer("Грязь в стыках (AO × dirt_4)", _above(r), color=(0.20, 0.18, 0.15), cop=0.40 * k, rough=0.85, rop=0.7)
    ao_seams(d, bbox, "dirt_4", 1000)
    made.append(_scope(d, meshes))
    return made


def wear_paint(pos, meshes, bbox, k):
    """Порошковая краска бокса: ровная, лёгкая шагрень (основа), неоднородность тона σ 5–8/255 одной мягкой маской;
    износ только у низа (носки обуви, тележки — пояс 5–25 см, тёмная полоса у пола) и у отбойника; сколы точками
    до грунта и металла на нижних углах и у фланцев отбойника; грязь в стыках."""
    made = []
    t = _layer("Тон краски — мягкая неоднородность (SI014_soft)", pos, color=(0.80, 0.82, 0.85), cmode=L.BlendingMode.Multiply, cop=1.0 * k,
               rough=0.04, rmode="add", rop=0.3)
    spread(t, _m("SI014_soft"), 1800, bbox, rot=0.4)   # размытая копия SI014: пятна крупные и мягкие, без «крупы»
    made.append(_scope(t, meshes))
    b = _layer("Грунт вокруг сколов (chips_halo)", _above(t), color=S.PRIMER, rough=0.62, metal=0.0, height=0.498)
    zone(b, "chips_halo")
    made.append(_scope(b, meshes))
    c = _layer("Сколы до металла (chips)", _above(b), color=S.STEEL, rough=0.50, metal=0.85, height=0.497)
    zone(c, "chips")
    made.append(_scope(c, meshes))
    f = _layer("Низ у пола темнее (floor_low × grunge_3)", _above(c), color=(0.45, 0.45, 0.44), cmode=L.BlendingMode.Multiply, cop=0.6 * k,
               rough=0.8, rop=0.5, metal=0.0)
    zone(f, "floor_low", S.sh("grunge_3"), 1600, bbox, rot=0.2)
    made.append(_scope(f, meshes))
    r = _layer("Носки обуви и тележки (kick_low × Rubber01)", _above(f), color=(0.30, 0.30, 0.30), cmode=L.BlendingMode.Multiply,
               cop=0.5 * k, rough=-0.05, rmode="add", rop=0.4)
    zone(r, "kick_low", _m("Rubber01"), 450, bbox, rot=0.0)
    made.append(_scope(r, meshes))
    rl = _layer("У отбойника — следы тележек (rail × Rubber01)", _above(r), color=(0.32, 0.32, 0.32), cmode=L.BlendingMode.Multiply,
                cop=0.45 * k, rough=-0.05, rmode="add", rop=0.4)
    zone(rl, "rail", _m("Rubber01"), 380, bbox, rot=0.1)
    made.append(_scope(rl, meshes))
    d = _layer("Грязь в стыках (AO × dirt_4)", _above(rl), color=(0.16, 0.14, 0.11), cop=0.40 * k, rough=0.88, rop=0.7, metal=0.0, height=0.5)
    ao_seams(d, bbox, "dirt_4", 1400)
    made.append(_scope(d, meshes))
    return made


def wear_skirt(pos, meshes, bbox, k):
    """Цоколь — ровный чёрный пластик: потёрт по рёбрам, светлая пыль в нижней кромке у пола."""
    made = []
    e = _layer("Потёрто по рёбрам (edge × SI007)", pos, color=(0.34, 0.34, 0.34), cmode=L.BlendingMode.Screen, cop=0.18 * k, rough=0.10,
               rmode="add", rop=0.5)
    zone(e, "edge", S.si(7), 500, bbox, rot=0.3)
    made.append(_scope(e, meshes))
    # пыль ровной полосой у самого пола (зона без рисунка: облачные dirt_* на чёрном читались «камуфляжем»)
    f = _layer("Пыль в нижней кромке (floor_low)", _above(e), color=(0.46, 0.44, 0.41), cop=0.30 * k, rough=0.9, rop=0.6, metal=0.0)
    zone(f, "floor_low")
    made.append(_scope(f, meshes))
    return made


def wear_dark(pos, meshes, bbox, k):
    """Прочий чёрный пластик (выводы, рамка сканера, монетница, пятки опор): затёртые рёбра и грязь в углублениях."""
    made = []
    e = _layer("Затёртые рёбра (edge × SI007)", pos, color=(0.32, 0.32, 0.32), cmode=L.BlendingMode.Screen, cop=0.20 * k, rough=0.12,
               rmode="add", rop=0.5)
    zone(e, "edge", S.si(7), 400, bbox, rot=0.3)
    made.append(_scope(e, meshes))
    d = _layer("Грязь в углублениях (AO × dirt_4)", _above(e), color=(0.22, 0.20, 0.17), cop=0.25 * k, rough=0.85, rop=0.4, metal=0.0)
    ao_seams(d, bbox, "dirt_4", 1000, pos=0.55)
    made.append(_scope(d, meshes))
    return made


def wear_white(pos, meshes, bbox, k):
    """Белая пластина таблички и лампа: лёгкое пожелтение."""
    y = _layer("Пожелтение (SI014)", pos, color=(0.90, 0.84, 0.70), cmode=L.BlendingMode.Multiply, cop=0.30 * k)
    spread(y, S.si(14), 1800, bbox, rot=0.2)
    return [_scope(y, meshes)]


def wear_misc(pos, meshes, bbox, k):
    return []


def wear_ss(pos, meshes, bbox, k):
    """Нержавейка: тусклая дорожка вдоль бокса, мелкие царапины вдоль движения товара, отпечатки и разводы, пыль в стыках."""
    made = []
    # круг 2: дорожка — только зоной (без пятен Smear: на блике они читались «плавленым» отражением)
    tr = _layer("Дорожка товаров — тусклее (track)", pos, color=(0.80, 0.80, 0.80), cmode=L.BlendingMode.Multiply, cop=0.25 * k,
                rough=0.14, rmode="add", rop=0.9)
    zone(tr, "track")
    made.append(_scope(tr, meshes))
    sc = _layer("Царапины вдоль движения (track × Scratches004)", _above(tr), color=(0.90, 0.90, 0.90), cmode=L.BlendingMode.Screen, cop=0.5 * k,
                rough=0.18, rmode="add", rop=0.8)
    zone(sc, "track", S.sc(4), 800, bbox, rot=0.0)
    made.append(_scope(sc, meshes))
    sc2 = _layer("Редкие царапины (Scratches001)", _above(sc), color=(0.88, 0.88, 0.88), cmode=L.BlendingMode.Screen, cop=0.25 * k,
                 rough=0.12, rmode="add", rop=0.6)
    spread(sc2, S.sc(1), 900, bbox, rot=0.0)
    made.append(_scope(sc2, meshes))
    fp = _layer("Отпечатки (Fingerprints001)", _above(sc2), color=(0.70, 0.68, 0.64), cmode=L.BlendingMode.Multiply, cop=0.20 * k,
                rough=-0.1, rmode="add", rop=0.6)
    spread(fp, S.fp(1), 450, bbox, rot=0.4)
    made.append(_scope(fp, meshes))
    d = _layer("Грязь в стыках (AO × dirt_4)", _above(fp), color=(0.18, 0.15, 0.12), cop=0.45 * k, rough=0.85, rop=0.7, metal=0.0)
    ao_seams(d, bbox, "dirt_4", 1000)
    made.append(_scope(d, meshes))
    return made


def wear_zinc(pos, meshes, bbox, k):
    """Оцинковка и хром (ручка, уголки, штифты, держатель): налёт пятнами окисла слабо, пыль в углублениях — у тонких
    деталей (ручка-скоба) AO почти везде, поэтому грязь слабее, чем в lc3_stacks.bare_wear (ручка выходила чёрной)."""
    made = []
    a = _layer("Налёт окисла (SI015)", pos, color=(0.70, 0.68, 0.64), cmode=L.BlendingMode.Multiply, cop=0.25 * k, rough=0.10, rmode="add",
               rop=0.3)
    spread(a, S.si(15), 1500, bbox, rot=0.8)
    made.append(_scope(a, meshes))
    d = _layer("Грязь в углублениях (AO × dirt_5)", _above(a), color=(0.20, 0.18, 0.15), cop=0.25 * k, rough=0.8, rop=0.5, metal=0.0)
    ao_seams(d, bbox, "dirt_5", 1000, ao=0.30, pos=0.45)
    made.append(_scope(d, meshes))
    return made


WEAR = {"lam": wear_lam, "glam": wear_top, "trim": wear_trim, "lam_edge": wear_edge, "top_edge": wear_top_edge, "top": wear_top,
        "ss": wear_ss, "belt": wear_belt, "plastic": wear_plastic, "paint": wear_paint, "dark": wear_dark, "skirt": wear_skirt,
        "zinc": wear_zinc, "white": wear_white, "plug": wear_misc, "bags": wear_misc, "label": wear_misc, "glass": wear_misc}


def build(setname: str, game: str, bbox: float, k: float = 1.0) -> str:
    import substance_painter.textureset as TS
    S.CTX["game"] = game
    st = sp_lib.stack_by_name(setname)
    sp_lib.clear(st, force=True)
    meshes = [m for t in TS.all_texture_sets() if t.name() == setname for m in t.all_mesh_names()]
    kinds = classify(game, meshes)
    # ---- заводская отделка
    g1 = L.insert_group(L.InsertPosition.from_textureset_stack(st))
    g1.set_name("Этап 1 — заводская отделка (фото-основы CC0)")
    for ch in st.all_channels():
        g1.set_blending_mode(L.BlendingMode.Passthrough, ch)
    pos = L.InsertPosition.inside_node(g1, L.NodeStack.Substack)
    log, last = [], None
    for kind, ms in kinds.items():
        sub = L.insert_group(pos if last is None else _above(last))
        sub.set_name(f"Отделка — {kind}")
        for ch in st.all_channels():
            sub.set_blending_mode(L.BlendingMode.Passthrough, ch)
        made = base_layers(L.InsertPosition.inside_node(sub, L.NodeStack.Substack), ms, bbox, k, kind, game)
        log.append(f"{kind}:{len(ms)}м/{len(made)}сл")
        last = sub
    # ---- печать
    top = _above(g1)
    apath = f"{SRC}/wear_counters/{game}_print_alpha.png"
    cpath = f"{SRC}/wear_counters/{game}_print_color.png"
    if os.path.exists(apath):
        pl = L.insert_fill(top)
        pl.set_name(PRINT)
        pl.active_channels = {CH.BaseColor, CH.SpecularRoughness, CH.BaseMetalness}
        pl.set_source(CH.BaseColor, sp_finish._bitmap(cpath))
        pl.set_source(CH.SpecularRoughness, sp_lib._val(0.55, data=True))
        pl.set_source(CH.BaseMetalness, sp_lib._val(0.0, data=True))
        sp_lib.uvscale(pl, 1.0)
        sp_finish.bitmap_mask(pl, apath)
        top = _above(pl)
    # ---- износ
    g2 = L.insert_group(top)
    g2.set_name("Этап 2 — износ")
    for ch in st.all_channels():
        g2.set_blending_mode(L.BlendingMode.Passthrough, ch)
    inner = L.InsertPosition.inside_node(g2, L.NodeStack.Substack)
    last = None
    for kind, ms in kinds.items():
        sub = L.insert_group(inner if last is None else _above(last))
        sub.set_name(f"Износ — {kind}")
        for ch in st.all_channels():
            sub.set_blending_mode(L.BlendingMode.Passthrough, ch)
        made = WEAR[kind](L.InsertPosition.inside_node(sub, L.NodeStack.Substack), ms, bbox, k)
        log.append(f"износ {kind}:{len(made)}сл")
        last = sub
    return f"{game}: " + " ".join(log)
