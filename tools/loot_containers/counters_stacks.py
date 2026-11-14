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
    "dark": ["ПТ_цоколь_планка", "ПТ_кабельный_вывод", "ПТ_опоры_пятки", "ПТ_монетница", "ПТ_монетница_коврик"],
    "zinc": ["ПТ_штифты_полок", "ПТ_эксцентрики", "ПТ_уголки", "ПТ_опоры_штанги", "ПТ_ящик_рельсы_неподвижные",
             "ПТ_ящик_рельсы_подвижные", "ПТ_ящик_ручка", "ПТ_держатель_пакетов"],
    "plug": ["ПТ_заглушки_конфирматов"],
    "bags": ["ПТ_пакеты_стопка"],
    "label": ["ПТ_наклейка_инвентарник"],
}
CHECKOUT = {
    "paint": ["КБ_корпус", "КБ_полка_корзин", "КБ_подставка_кассы"],
    "dark": ["КБ_цоколь", "КБ_швы_панелей", "КБ_кабельные_выводы", "КБ_сканер_рамка"],
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
    chans = {CH.BaseColor: sp_finish._bitmap(f"{p}/color_2k.jpg")}
    if rough:
        chans[CH.SpecularRoughness] = sp_finish._bitmap(f"{p}/roughness_2k.jpg")
    if height:
        chans[CH.Height] = sp_finish._bitmap(f"{p}/height_2k.jpg")
    lay.active_channels = set(chans)
    for c, src in chans.items():
        lay.set_source(c, src)
    lay.set_blending_mode(cmode or (L.BlendingMode.Overlay), CH.BaseColor)
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
    """Заводская отделка вида: плоский тон + фото-основа (+ крошка / рельеф)."""
    made = []
    spec = {
        "lam": ((0.84, 0.77, 0.64), 0.55, 0.0, "Wood092_oak", 700, 0.0, 0.70, 0.30, 0.03),
        "trim": ((0.26, 0.17, 0.12), 0.50, 0.0, "Wood066", 600, 0.0, 0.55, 0.25, 0.0),
        "lam_edge": ((0.74, 0.64, 0.50), 0.40, 0.0, None, 0, 0, 0, 0, 0),
        "top_edge": ((0.15, 0.15, 0.16), 0.40, 0.0, None, 0, 0, 0, 0, 0),
        "top": ((0.17, 0.175, 0.185), 0.42, 0.0, "Plastic011", 400, 0.0, 0.40, 0.35, 0.0),
        "dark": ((0.13, 0.13, 0.13), 0.70, 0.0, "Plastic012A", 300, 0.0, 0.40, 0.15, 0.08),
        "zinc": ((0.60, 0.61, 0.60), 0.40, 1.0, "Metal014", 300, 0.0, 0.30, 0.25, 0.05),
        "plug": ((0.70, 0.60, 0.46), 0.45, 0.0, None, 0, 0, 0, 0, 0),
        "bags": ((0.84, 0.84, 0.80), 0.35, 0.0, None, 0, 0, 0, 0, 0),
        "label": ((0.85, 0.84, 0.78), 0.70, 0.0, None, 0, 0, 0, 0, 0),
        "paint": ((0.40, 0.47, 0.52), 0.55, 0.0, "Metal030", 500, 0.0, 0.35, 0.25, 0.08),
        "ss": ((0.74, 0.74, 0.73), 0.32, 1.0, "Metal009", 450, 0.0, 0.40, 0.55, 0.0),
        "belt": ((0.13, 0.13, 0.13), 0.86, 0.0, "Plastic012A", 250, 0.0, 0.40, 0.10, 0.08),
        "plastic": ((0.66, 0.67, 0.67), 0.48, 0.0, "Plastic018A", 350, 0.0, 0.45, 0.30, 0.08),
        "glam": ((0.22, 0.23, 0.24), 0.50, 0.0, "Plastic011", 400, 0.0, 0.45, 0.30, 0.10),
        "white": ((0.86, 0.86, 0.83), 0.35, 0.0, "Plastic018A", 350, 0.0, 0.25, 0.30, 0.05),
        "glass": ((0.12, 0.14, 0.16), 0.12, 0.0, None, 0, 0, 0, 0, 0),
    }[kind]
    color, rough, metal, pset, period, rot, c, r, h = spec
    f = flat(f"Основа — {kind}", pos, color, rough, metal)
    made.append(_scope(f, meshes))
    last = f
    if pset:
        p = photo(f"Фото — {kind}", _above(f), pset, period, bbox, rot, c, r, h)
        made.append(_scope(p, meshes))
        last = p
    return made


# ---------------------------------------------------------------------------------------------- износ
CORE = "Chipboard001_pale"
CORE2 = "Chipboard003_pale"


def wear_lam(pos, meshes, bbox, k):
    """ЛДСП: неоднородность тона (мягкие пятна), сердечник из стружки на сбитых кромках и углах, разбухший низ, обувь, пыль, стыки."""
    made = []
    t = _layer("Тон ламината — тёмные пятна (SI014)", pos, color=(0.66, 0.62, 0.56), cmode=L.BlendingMode.Multiply, cop=0.85 * k,
               rough=0.05, rmode="add", rop=0.4)
    spread(t, S.si(14), 1700, bbox, rot=0.4)
    made.append(_scope(t, meshes))
    t2 = _layer("Тон ламината — светлые пятна (SI016)", _above(t), color=(0.80, 0.76, 0.68), cmode=L.BlendingMode.Screen, cop=0.35 * k,
                rough=-0.04, rmode="add", rop=0.5)
    spread(t2, S.si(16), 2200, bbox, rot=1.2)
    made.append(_scope(t2, meshes))
    last = t2
    # главный признак: сбитая кромка — светлая ДСП со стружкой, шершавая, без блеска
    c = core_layer("Сердечник ДСП на кромках (edge × ChipsEdge45)", _above(last), CORE, 450, bbox)
    zone(c, "edge", _m("ChipsEdge45"), 1100, bbox, rot=0.3, harden=(0.4, 0.6))
    made.append(_scope(c, meshes))
    c2 = core_layer("Сердечник — углы пятнами (edgew × ChipsEdge14)", _above(c), CORE2, 400, bbox, rot=0.6)
    zone(c2, "edgew", _m("ChipsEdge14"), 1200, bbox, rot=1.7, harden=(0.5, 0.6))
    made.append(_scope(c2, meshes))
    last = c2
    # низ у пола: сырость и вспученный ламинат — тёмное, шершавое, из-под него крупными кусками ДСП
    w = _layer("Низ — сырость (floor × grunge_3)", _above(last), color=(0.52, 0.43, 0.34), cmode=L.BlendingMode.Multiply, cop=0.85 * k,
               rough=0.85, rop=0.7, metal=0.0, height=0.485)
    zone(w, "floor", S.sh("grunge_3"), 1500, bbox, rot=0.2)
    made.append(_scope(w, meshes))
    sw = core_layer("Вспученный низ — ДСП из-под ламината (floor × ChipsEdge14)", _above(w), CORE, 380, bbox, rot=0.2)
    zone(sw, "floor", _m("ChipsEdge14"), 1400, bbox, rot=0.9, harden=(0.55, 0.6))
    made.append(_scope(sw, meshes))
    r = _layer("Следы обуви (kick × Rubber03)", _above(sw), color=(0.22, 0.20, 0.17), cmode=L.BlendingMode.Multiply, cop=0.6 * k,
               rough=-0.05, rmode="add", rop=0.5)
    zone(r, "kick", _m("Rubber03"), 500, bbox, rot=0.4)
    made.append(_scope(r, meshes))
    u = _layer("Пыль сверху (up × SI012)", _above(r), color=(0.55, 0.53, 0.50), cop=0.28 * k, rough=0.9, rop=0.4 * k, metal=0.0)
    zone(u, "up", S.si(12), 1500, bbox, rot=0.7)
    made.append(_scope(u, meshes))
    d = _layer("Грязь в стыках (AO × dirt_4)", _above(u), color=(0.20, 0.17, 0.13), cop=0.5 * k, rough=0.88, rop=0.8, metal=0.0, height=0.5)
    ao_seams(d, bbox, "dirt_4", 1400)
    made.append(_scope(d, meshes))
    kn = _layer("Лицо — следы ног и колен (front_knee × Rubber03)", _above(d), color=(0.45, 0.42, 0.38), cmode=L.BlendingMode.Multiply, cop=0.55 * k,
                rough=-0.05, rmode="add", rop=0.5)
    zone(kn, "front_knee", _m("Rubber03"), 500, bbox, rot=0.4)
    made.append(_scope(kn, meshes))
    d = kn
    hd = _layer("Ручка ящика — жир (touch × Fingerprints001)", _above(d), color=(0.62, 0.55, 0.45), cmode=L.BlendingMode.Multiply,
                cop=0.35 * k, rough=-0.1, rmode="add", rop=0.7)
    zone(hd, "touch", S.fp(1), 600, bbox, rot=0.7)
    made.append(_scope(hd, meshes))
    return made


def wear_edge(pos, meshes, bbox, k):
    """Кромка ПВХ: потёртость и риски, местами отклеилась — под ней ДСП (куски 2–5 см по длине кромки)."""
    made = []
    s = _layer("Кромка — риски (Scratches001)", pos, color=(0.80, 0.76, 0.66), cmode=L.BlendingMode.Screen, cop=0.35 * k, rough=-0.1, rmode="add", rop=0.5)
    spread(s, S.sc(1), 500, bbox, rot=0.5)
    made.append(_scope(s, meshes))
    c = core_layer("Кромка отклеилась — ДСП (ChipsEdge14)", _above(s), CORE2, 420, bbox, rot=0.3)
    S.own(c, _m("ChipsEdge14"), 900, bbox, rot=0.2, pos=0.12, contrast=0.6)
    made.append(_scope(c, meshes))
    d = _layer("Кромка — грязь (SI012)", _above(c), color=(0.36, 0.30, 0.23), cmode=L.BlendingMode.Multiply, cop=0.45 * k, rough=0.7, rop=0.5)
    spread(d, S.si(12), 900, bbox, rot=0.9)
    made.append(_scope(d, meshes))
    return made


def wear_top(pos, meshes, bbox, k):
    """Тёмный постформинг: затёрт до матовости у кассы, кольца от стаканов, царапины монетницы, пыль и грязь."""
    made = []
    m = _layer("Затёртость до матового (touch × SI014)", pos, color=(0.50, 0.50, 0.50), cmode=L.BlendingMode.Screen, cop=0.22 * k, rough=0.22,
               rmode="add", rop=0.7)
    zone(m, "touch", S.si(14), 1000, bbox, rot=0.3)
    made.append(_scope(m, meshes))
    cu = _layer("Кольца и следы стаканов (cups × Smear006)", _above(m), color=(0.62, 0.62, 0.60), cmode=L.BlendingMode.Screen, cop=0.20 * k,
                rough=-0.12, rmode="add", rop=0.6)
    zone(cu, "cups", S.sm(6), 900, bbox, rot=0.8)
    made.append(_scope(cu, meshes))
    sc = _layer("Царапины (cups × Scratches002)", _above(cu), color=(0.55, 0.55, 0.54), cmode=L.BlendingMode.Screen, cop=0.45 * k, rough=0.1,
                rmode="add", rop=0.5)
    zone(sc, "cups", S.sc(2), 700, bbox, rot=0.2)
    made.append(_scope(sc, meshes))
    ec = _layer("Края стола — затёртость (edge_cust × SI007)", _above(sc), color=(0.52, 0.52, 0.51), cmode=L.BlendingMode.Screen, cop=0.28 * k,
                rough=0.2, rmode="add", rop=0.6)
    zone(ec, "edge_cust", S.si(7), 600, bbox, rot=0.5)
    made.append(_scope(ec, meshes))
    es = _layer("Края стола у продавца (edge_sell × SI007)", _above(ec), color=(0.52, 0.52, 0.51), cmode=L.BlendingMode.Screen, cop=0.28 * k,
                rough=0.2, rmode="add", rop=0.6)
    zone(es, "edge_sell", S.si(7), 600, bbox, rot=1.1)
    made.append(_scope(es, meshes))
    u = _layer("Пыль (up × SI012)", _above(es), color=(0.50, 0.49, 0.47), cop=0.10 * k, rough=0.85, rop=0.3 * k)
    zone(u, "up", S.si(12), 1500, bbox, rot=0.6)
    made.append(_scope(u, meshes))
    d = _layer("Грязь в стыках (AO × dirt_4)", _above(u), color=(0.16, 0.14, 0.11), cop=0.45 * k, rough=0.85, rop=0.7)
    ao_seams(d, bbox, "dirt_4", 1200)
    made.append(_scope(d, meshes))
    return made


def wear_ss(pos, meshes, bbox, k):
    """Нержавейка: тусклая дорожка вдоль бокса, мелкие царапины вдоль движения товара, отпечатки и разводы, пыль в стыках."""
    made = []
    tr = _layer("Дорожка товаров — тусклее (track × Smear004)", pos, color=(0.62, 0.62, 0.62), cmode=L.BlendingMode.Multiply, cop=0.28 * k,
                rough=0.20, rmode="add", rop=0.9)
    zone(tr, "track", S.sm(4), 1100, bbox, rot=0.0)
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
    sm = _layer("Разводы (Smear001)", _above(fp), color=(0.80, 0.80, 0.78), cmode=L.BlendingMode.Multiply, cop=0.12 * k, rough=0.1, rmode="add", rop=0.5)
    spread(sm, S.sm(1), 1500, bbox, rot=0.3)
    made.append(_scope(sm, meshes))
    d = _layer("Грязь в стыках (AO × dirt_4)", _above(sm), color=(0.18, 0.15, 0.12), cop=0.45 * k, rough=0.85, rop=0.7, metal=0.0)
    ao_seams(d, bbox, "dirt_4", 1000)
    made.append(_scope(d, meshes))
    return made


def wear_belt(pos, meshes, bbox, k):
    """Чёрная лента: продольные потёртые полосы, пыль, края."""
    made = []
    tr = _layer("Продольные потёртые полосы (track × Scratches004)", pos, color=(0.40, 0.40, 0.40), cmode=L.BlendingMode.Screen, cop=0.22 * k,
                rough=-0.1, rmode="add", rop=0.5)
    zone(tr, "track", S.sc(4), 600, bbox, rot=0.0)
    made.append(_scope(tr, meshes))
    u = _layer("Пыль (SI012)", _above(tr), color=(0.30, 0.29, 0.27), cop=0.18 * k, rough=0.9, rop=0.3)
    spread(u, S.si(12), 1200, bbox, rot=0.6)
    made.append(_scope(u, meshes))
    return made


def wear_plastic(pos, meshes, bbox, k):
    """Светло-серый пластик бортов: потёртость кромок, тёмные риски, пыль."""
    made = []
    e = _layer("Затёртые кромки (edge × ChipsEdge50)", pos, color=(0.80, 0.80, 0.79), cmode=L.BlendingMode.Screen, cop=0.30 * k, rough=0.15,
               rmode="add", rop=0.6)
    zone(e, "edge", _m("ChipsEdge50"), 520, bbox, rot=0.3, harden=(0.45, 0.7))
    made.append(_scope(e, meshes))
    r = _layer("Тёмные риски (Scratches003)", _above(e), color=(0.34, 0.34, 0.34), cmode=L.BlendingMode.Multiply, cop=0.55 * k, rough=0.1,
               rmode="add", rop=0.4)
    spread(r, S.sc(3), 800, bbox, rot=0.4)
    made.append(_scope(r, meshes))
    u = _layer("Пыль сверху (up × SI012)", _above(r), color=(0.55, 0.54, 0.52), cop=0.30 * k, rough=0.9, rop=0.4)
    zone(u, "up", S.si(12), 1500, bbox, rot=0.6)
    made.append(_scope(u, meshes))
    d = _layer("Грязь в стыках (AO × dirt_4)", _above(u), color=(0.20, 0.18, 0.15), cop=0.45 * k, rough=0.85, rop=0.7)
    ao_seams(d, bbox, "dirt_4", 1000)
    made.append(_scope(d, meshes))
    return made


def wear_paint(pos, meshes, bbox, k):
    """Крашеная сталь бокса (серо-синяя порошковая краска): неоднородность тона мягкими пятнами, тёмный низ с рваной границей, сколы
    по рёбрам до грунта и металла, углы, пыль, следы обуви и колёс на 5–30 см (нейтральные множители: цвет краски задаёт основа)."""
    made = []
    t = _layer("Тон краски — тёмные пятна (SI014)", pos, color=(0.58, 0.60, 0.63), cmode=L.BlendingMode.Multiply, cop=1.0 * k, rough=0.08,
               rmode="add", rop=0.4 * k)
    spread(t, S.si(14), 1700, bbox, rot=0.4)
    made.append(_scope(t, meshes))
    t2 = _layer("Тон краски — светлые пятна (SI016)", _above(t), color=(0.62, 0.64, 0.66), cmode=L.BlendingMode.Screen, cop=0.22 * k,
                rough=-0.05, rmode="add", rop=0.5)
    spread(t2, S.si(16), 2200, bbox, rot=1.2)
    made.append(_scope(t2, meshes))
    t3 = _layer("Грязь — крупные пятна (Grunge4)", _above(t2), color=(0.56, 0.57, 0.57), cmode=L.BlendingMode.Multiply, cop=0.5 * k, rough=0.10,
                rmode="add", rop=0.4)
    spread(t3, S.sh("Grunge4"), 1900, bbox, rot=0.7)
    made.append(_scope(t3, meshes))
    b = _layer("Кайма грунта у сколов (edge × ChipsEdge85)", _above(t3), color=S.PRIMER, rough=0.62, metal=0.0, height=0.498)
    zone(b, "edge", _m("ChipsEdge85"), 1300, bbox, rot=0.3, harden=(0.35, 0.9))
    made.append(_scope(b, meshes))
    c = _layer("Сколы до металла (edge × ChipsEdge85)", _above(b), color=S.STEEL, rough=0.50, metal=0.85, height=0.497)
    zone(c, "edge", _m("ChipsEdge85"), 1300, bbox, rot=0.3, harden=(0.65, 0.9))
    made.append(_scope(c, meshes))
    cp = _layer("Углы — рваные пятна (edgew × ChipsEdge14)", _above(c), color=S.STEEL, rough=0.50, metal=0.85, height=0.497)
    zone(cp, "edgew", _m("ChipsEdge14"), 1300, bbox, rot=1.7, harden=(0.5, 0.9))
    made.append(_scope(cp, meshes))
    f = _layer("Низ темнее (floor × grunge_3)", _above(cp), color=(0.36, 0.35, 0.33), cmode=L.BlendingMode.Multiply, cop=0.85 * k, rough=0.85,
               rop=0.7, metal=0.0)
    zone(f, "floor", S.sh("grunge_3"), 1600, bbox, rot=0.2)
    made.append(_scope(f, meshes))
    r = _layer("Следы обуви и колёс (kick × Rubber03)", _above(f), color=(0.16, 0.16, 0.15), cmode=L.BlendingMode.Multiply, cop=0.7 * k,
               rough=-0.05, rmode="add", rop=0.5)
    zone(r, "kick", _m("Rubber03"), 450, bbox, rot=0.1)
    made.append(_scope(r, meshes))
    r2 = _layer("Полосы от колёс (kick × Rubber01)", _above(r), color=(0.14, 0.14, 0.14), cmode=L.BlendingMode.Multiply, cop=0.6 * k)
    zone(r2, "kick", _m("Rubber01"), 700, bbox, rot=1.57)
    made.append(_scope(r2, meshes))
    u = _layer("Пыль сверху (up × SI012)", _above(r2), color=(0.55, 0.55, 0.54), cop=0.30 * k, rough=0.9, rop=0.4 * k, metal=0.0)
    zone(u, "up", S.si(12), 1500, bbox, rot=0.7)
    made.append(_scope(u, meshes))
    d = _layer("Грязь в стыках (AO × dirt_4)", _above(u), color=(0.16, 0.14, 0.11), cop=0.5 * k, rough=0.88, rop=0.8, metal=0.0, height=0.5)
    ao_seams(d, bbox, "dirt_4", 1400)
    made.append(_scope(d, meshes))
    return made


def wear_dark(pos, meshes, bbox, k):
    """Чёрный пластик (цоколь, планка, выводы, монетница): износ lc3_stacks.dark_wear + серая пыль и грязь у пола (цоколь у ног и тележек)."""
    made = S.dark_wear(pos, meshes, bbox, k)
    f = _layer("Пыль и грязь у пола (floor × dirt_5)", _above(made[-1]), color=(0.40, 0.38, 0.34), cop=0.35 * k, rough=0.88, rop=0.6, metal=0.0)
    zone(f, "floor", S.sh("dirt_5"), 900, bbox, rot=0.2)
    made.append(_scope(f, meshes))
    return made


def wear_zinc(pos, meshes, bbox, k):
    """Оцинковка и хром: налёт, пыль, грязь в углублениях."""
    made = S.bare_wear(pos, meshes, bbox, k)
    return made


def wear_white(pos, meshes, bbox, k):
    """Белая пластина таблички и лампа: пожелтение, пыль."""
    made = []
    y = _layer("Пожелтение (SI014)", pos, color=(0.88, 0.80, 0.62), cmode=L.BlendingMode.Multiply, cop=0.40 * k)
    spread(y, S.si(14), 1800, bbox, rot=0.2)
    made.append(_scope(y, meshes))
    u = _layer("Пыль (SI012)", _above(y), color=(0.50, 0.48, 0.44), cop=0.30 * k, rough=0.85, rop=0.4)
    spread(u, S.si(12), 1200, bbox, rot=0.6)
    made.append(_scope(u, meshes))
    return made


def wear_misc(pos, meshes, bbox, k):
    u = _layer("Пыль (SI012)", pos, color=(0.45, 0.43, 0.40), cop=0.25 * k, rough=0.85, rop=0.4 * k, metal=0.0)
    spread(u, S.si(12), 1500, bbox, rot=0.6)
    return [_scope(u, meshes)]


WEAR = {"lam": wear_lam, "glam": wear_top, "trim": wear_lam, "lam_edge": wear_edge, "top_edge": wear_edge, "top": wear_top, "ss": wear_ss,
        "belt": wear_belt, "plastic": wear_plastic, "paint": wear_paint, "dark": wear_dark, "zinc": wear_zinc, "white": wear_white,
        "plug": wear_misc, "bags": wear_misc, "label": wear_misc, "glass": wear_misc}


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
