"""Контейнеры для лута, партия 1, отделка v03 (заводская + износ сразу, в Painter): группа износа «Этап 2 — износ»
(Passthrough) над печатью и заводской группой. Выполняется внутри Painter (задание lc3_sp.py через мост).

Образцы владельца (2026-11-13): оружейный шкаф, сейф, касса — вещь прослужила лет десять и брошена. Материал читается
разницей краски и оголённого металла, чистого и грязного; износ собран ПО ФОРМЕ (кромки и наружные углы, вокруг ручек /
замков / лимба, низ у пола, верх — пыль).

Круг 3 (замеры владельца пипеткой по образцам): шкаф — краска sRGB ≈ (72, 88, 60), на плоскости двери разброс цвета 5–8/255
мягкими пятнами 10–40 см (фото-маски SurfaceImperfections014–016, grunge), вертикальные потёки под жалюзи и ручкой
(SurfaceImperfections010), нижние 20–25 см темнее и грязнее с рваной границей, цепочка светлых сколов по всем наружным
рёбрам (зона 4–16 мм × чешуйки SurfaceImperfections013 ~50 % длины, по краю скола кайма грунта); сейф и ячейка — почти чисто:
только осветление рёбер до серого sRGB ~79 (1,5–5 мм, ~65 % длины), неоднородность ШЕРОХОВАТОСТИ на плоскости (Smear, без
изменения цвета), пыль сверху и в зазорах, 2–3 слабых коротких царапины у штурвала; касса — чёрный пластик без серых клякс,
тёмная грязь между клавишами (AO и зона поля клавиш × dirt), верх всех клавиш заполирован, на ходовых клавишах подписи
затёрты, на окнах индикаторов — зелёные сегментные «0.00» (lc3_digits.py).

РИСУНОК износа — только фото-маски из библиотеки владельца E:/Models Blender/Маски_АЛЬФА (lc3_masks.py: рабочие копии 2K и
рисунки с заданной долей площади по их же пикселям). МЕСТО — карты зон в развёртке по картам геометрии (lc3_zones.py).
Облаков и noise_* / grunge_* Painter в видимых слоях износа нет.
"""
import substance_painter.layerstack as L

import sp_finish
import sp_lib
from sp_lib import CH, fill

GROUP = "Этап 2 — износ"
PRINT = "Печать (этап 1)"
STEEL = (0.68, 0.68, 0.69)   # светлая оголённая сталь: в тёмной студии зеркальный металл читается чёрным — светлее и шершавее
GRAYWORN = (0.31, 0.31, 0.31)   # осветлённое ребро сейфа и ячейки: серый sRGB ~79, не блестящий металл
PRIMER = (0.15, 0.17, 0.14)   # кайма грунта по краю скола
SRC = "E:/Games/RING-godot/_asset_src/loot_containers"
MASKS = SRC + "/masks_v03"   # рабочие копии масок владельца и рисунки по их пикселям (lc3_masks.py)
CTX = {"game": ""}
SOFT = ("lc_safe", "lc_cell")   # почти чистые: плоскость без изменения цвета


def _m(name):
    return f"{MASKS}/{name}.png"


def si(n):
    """ambientCG SurfaceImperfections0NN (7, 10, 12, 13 — Opacity; 14, 15, 16 — Color), серая копия."""
    return _m(f"SI{n:03d}")


def sc(n):
    return _m(f"Scratches{n:03d}")


def sm(n):
    return _m(f"Smear{n:03d}")


def fp(n):
    return _m(f"Fingerprints{n:03d}")


def sh(name):
    """ShareTextures: dirt_4, dirt_5, grunge_3, scratches_5 (и Grunge1/2/4)."""
    return _m(name)


def zone_path(zone):
    return f"{SRC}/wear_v03/{CTX['game']}_{zone}.png"


def _above(node):
    return L.InsertPosition.above_node(node)


def _layer(name, pos, color=None, cmode=L.BlendingMode.Normal, cop=1.0, rough=None, rmode=None, rop=1.0, metal=None,
           height=None, hop=1.0):
    """Слой износа: цвет режимом наложения; блеск — числом (Normal) или прибавкой / вычитанием (rmode add; знак rough);
    металл — числом; высота — абсолютным уровнем (Normal). Только блеск (color=None) — цвет плоскости не меняется."""
    ch = {}
    if color is not None:
        ch["color"] = color
    if rough is not None:
        ch["rough"] = abs(rough)
    if metal is not None:
        ch["metal"] = metal
    if height is not None:
        ch["height"] = height
    f = fill(name, pos, **ch)
    if color is not None:
        f.set_blending_mode(cmode, CH.BaseColor)
        f.set_opacity(cop, CH.BaseColor)
    if rough is not None:
        if rmode == "add":
            f.set_blending_mode(L.BlendingMode.Subtract if rough < 0 else L.BlendingMode.LinearDodge, CH.SpecularRoughness)
        f.set_opacity(rop, CH.SpecularRoughness)
    if metal is not None:
        f.set_opacity(1.0, CH.BaseMetalness)
    if height is not None:
        f.set_opacity(hop, CH.Height)
    return f


def _scope(layer, meshes):
    if meshes:
        sp_lib.only_meshes(layer, meshes)
    return layer


def thresh(node, position, contrast, warp=None):
    last = sp_finish._mfilter(node, "histogram_scan", {"Position": position, "Contrast": contrast})
    if warp:
        last = sp_finish._mfilter(last, "warp", {"intensity": warp})
    return last


def own(layer, path, period, bbox, above=None, rot=0.0, blend=L.BlendingMode.Multiply, pos=None, contrast=0.6,
        opacity=1.0):
    """РИСУНОК: маска владельца заливкой в маску слоя (трёхпроекционно, плитка period мм; картинка импортируется заново на
    каждую сборку — sp_finish._bitmap по времени файла); первая в маске или умножает «место» (above).
    pos — порог Histogram Scan (выше — больше белого), None — как есть."""
    sp_lib.mask_black(layer)
    place = _above(above) if above is not None else L.InsertPosition.inside_node(layer, L.NodeStack.Mask)
    m = L.insert_fill(place)
    m.set_source(None, sp_finish._bitmap(path))
    sp_lib.triplanar(m, bbox / period, rot)
    if above is not None:
        m.set_blending_mode(blend)
    m.set_opacity(opacity)
    return thresh(m, pos, contrast) if pos is not None else m


def zone(layer, name, pattern=None, period=700, bbox=1000.0, rot=0.0, opacity=1.0, harden=None):
    """МЕСТО (карта зоны в развёртке) × РИСУНОК (маска владельца, трёхпроекционно); pattern None — зона как есть.
    Зона первой в маске слоя, рисунок умножает её; harden=(порог, контраст) — резкий край (чешуйки скола, не пух)."""
    sp_lib.mask_black(layer)
    z = L.insert_fill(L.InsertPosition.inside_node(layer, L.NodeStack.Mask))
    z.set_source(None, sp_finish._bitmap(zone_path(name)))
    z.set_projection_mode(L.ProjectionMode.UV)
    z.set_opacity(opacity)
    if pattern is None:
        return z
    last = own(layer, pattern, period, bbox, above=z, rot=rot)
    return thresh(last, *harden) if harden else last


def spread(layer, pattern, period, bbox, rot=0.0, opacity=1.0):
    """РИСУНОК по всей детали, без зоны: первым в маске."""
    return own(layer, pattern, period, bbox, rot=rot, opacity=opacity)


def ao_seams(layer, bbox, dirt, period=1000, rot=0.5, ao=0.22, pos=0.5):
    """Грязь в углублениях и стыках: AO (место) × рисунок владельца dirt_* (порог — рваный край)."""
    g = sp_lib.mask_generator(layer, "mg_ambient_occlusion/mg_ambient_occlusion", {"ao_invert": 1})
    g = thresh(g, ao, 0.4)
    return own(layer, sh(dirt), period, bbox, above=g, rot=rot, pos=pos, contrast=0.6)


# ------------------------------------------------------------------------------------------------------------- виды
def paint_wear(pos, meshes, bbox, k, floor, edge=None):
    """Крашеная сталь. Шкаф, картотека, аптечка, денежный ящик: неоднородность тона и грязи мягкими пятнами, потёки под
    жалюзи и ручкой, тёмный низ с рваной границей, цепочка сколов по рёбрам; сейф и ячейка (SOFT): плоскость без изменения
    цвета — только шероховатость, осветлённые рёбра, пыль сверху и в зазорах."""
    pat, col, rgh, met, hgt, ezone, border = edge or ("ChipsEdge50", STEEL, 0.50, 0.85, 0.497, "edge", True)
    soft = CTX["game"] in SOFT
    made = []
    if soft:
        # плоскость: только неоднородность шероховатости ±0,06 (разводы Smear), цвет не меняется
        t = _layer("Шероховатость — разводы (Smear004)", pos, rough=0.06, rmode="add", rop=0.6)
        spread(t, sm(4), 2000, bbox, rot=1.1)
        made.append(_scope(t, meshes))
        t2 = _layer("Шероховатость — крупно (SI014)", _above(t), rough=-0.05, rmode="add", rop=0.6)
        spread(t2, si(14), 2400, bbox, rot=0.4)
        made.append(_scope(t2, meshes))
        last = t2
    else:
        # тон краски и грязь — крупные мягкие пятна 10–40 см из масок владельца (разброс на плоскости 5–8/255)
        t = _layer("Тон краски — тёмные пятна (SI014)", pos, color=(0.55, 0.60, 0.50), cmode=L.BlendingMode.Multiply,
                   cop=0.95 * k, rough=0.08, rmode="add", rop=0.4 * k)
        spread(t, si(14), 1700, bbox, rot=0.4)
        made.append(_scope(t, meshes))
        t2 = _layer("Тон краски — светлые пятна (SI016)", _above(t), color=(0.50, 0.56, 0.45), cmode=L.BlendingMode.Screen,
                    cop=0.34 * k, rough=-0.05, rmode="add", rop=0.5)
        spread(t2, si(16), 2200, bbox, rot=1.2)
        made.append(_scope(t2, meshes))
        t3 = _layer("Грязь — крупные пятна (grunge_4)", _above(t2), color=(0.38, 0.40, 0.34), cmode=L.BlendingMode.Multiply,
                    cop=0.75 * k, rough=0.10, rmode="add", rop=0.4)
        spread(t3, sh("Grunge4"), 1900, bbox, rot=0.7)
        made.append(_scope(t3, meshes))
        last = t3
        # вертикальные потёки: под жалюзи (зона drip) и под ручкой (touch) × SI010 (капли и потёки)
        for zn, rot in (("drip", 0.0), ("touch", 0.1)):
            d = _layer(f"Потёки (зона {zn} × SI010)", _above(last), color=(0.45, 0.46, 0.40), cmode=L.BlendingMode.Multiply,
                       cop=0.55 * k, rough=0.10, rmode="add", rop=0.5)
            zone(d, zn, si(10), 1500, bbox, rot=rot)
            made.append(_scope(d, meshes))
            last = d
    # кромки: цепочка светлых рваных чешуек вдоль наружных рёбер (зона × чешуйки SI013, порог — резкий край)
    if border:
        b = _layer("Кайма грунта у сколов (зона × " + pat + ")", _above(last), color=PRIMER, rough=0.62, metal=0.0, height=0.498)
        zone(b, ezone, _m(pat), 520, bbox, rot=0.3, harden=(0.35, 0.9))
        made.append(_scope(b, meshes))
        last = b
    c = _layer("Сколы кромок (зона × " + pat + ")", _above(last), color=col, rough=rgh, metal=met, height=hgt)
    zone(c, ezone, _m(pat), 520, bbox, rot=0.3, harden=(0.5, 0.9))
    made.append(_scope(c, meshes))
    last = c
    if not soft:
        # затёртость у ребра и на углах: широкая зона × крапинки SI007, светлее краски (без блеска металла)
        w = _layer("Затёртость у кромки (зона edgew × SI007)", _above(last), color=(0.55, 0.58, 0.52),
                   cmode=L.BlendingMode.Screen, cop=0.25 * k, rough=0.12, rmode="add", rop=0.5)
        zone(w, "edgew", _m("ChipsSpeck"), 700, bbox, rot=1.4)
        made.append(_scope(w, meshes))
        last = w
        # ладони у ручек: слабо, узко
        hd = _layer("Ладони у ручки (touch_core × Palm)", _above(last), color=(0.55, 0.55, 0.54), cmode=L.BlendingMode.Multiply,
                    cop=0.25 * k, rough=-0.12, rmode="add", rop=0.7)
        zone(hd, "touch_core", _m("Palm"), 400, bbox, rot=0.2)
        made.append(_scope(hd, meshes))
        last = hd
    else:
        # 2–3 коротких слабых царапины у штурвала / ручки: на 15–20/255 светлее краски
        s = _layer("Царапины у штурвала (зона touch_core × ScrTouch)", _above(last), color=(0.28, 0.28, 0.28),
                   cmode=L.BlendingMode.Screen, cop=0.5 * k, rough=0.10, rmode="add", rop=0.4)
        zone(s, "touch_core", _m("ScrTouch"), 650, bbox, rot=1.9)
        made.append(_scope(s, meshes))
        last = s
    # пыль: сверху (up × SI012), светлее и шершавее краски; в зазорах — по AO
    u = _layer("Пыль сверху (зона up × SI012)", _above(last), color=(0.50, 0.50, 0.49), cop=0.28 * k, rough=0.9, rop=0.4 * k,
               metal=0.0)
    zone(u, "up", si(12), 1500, bbox, rot=0.7)
    made.append(_scope(u, meshes))
    last = u
    # низ у пола: нижние 20–25 см темнее и грязнее, граница рваная (floor × grunge_3 / dirt_5)
    f = _layer("Низ темнее (зона floor × grunge_3)", _above(last), color=(0.28, 0.27, 0.23), cmode=L.BlendingMode.Multiply,
               cop=(0.35 if soft else 0.85) * k, rough=0.85, rop=0.7, metal=0.0)
    zone(f, "floor", sh("grunge_3"), 1600, bbox, rot=0.2)
    made.append(_scope(f, meshes))
    f2 = _layer("Грязь у пола (зона floor × dirt_5)", _above(f), color=(0.12, 0.10, 0.08), cop=(0.25 if soft else 0.55) * k,
                rough=0.85, rop=0.8, metal=0.0)
    zone(f2, "floor", sh("dirt_5"), 900, bbox, rot=0.2)
    made.append(_scope(f2, meshes))
    d = _layer("Грязь в стыках (AO × dirt_4)", _above(f2), color=(0.14, 0.12, 0.09), cop=(0.35 if soft else 0.55) * k, rough=0.88,
               rop=0.8, metal=0.0, height=0.5)
    ao_seams(d, bbox, "dirt_4", 1400)
    made.append(_scope(d, meshes))
    last = d
    if CTX["game"] in ("lc_gun", "lc_file"):   # внизу шкафов — обувь и тележка
        r = _layer("Следы обуви внизу (зона kick × Резина_03)", _above(last), color=(0.20, 0.19, 0.17),
                   cmode=L.BlendingMode.Multiply, cop=0.55 * k, rough=-0.05, rmode="add", rop=0.5)
        zone(r, "kick", _m("Rubber03"), 500, bbox, rot=0.4)
        made.append(_scope(r, meshes))
    return made


def bare_wear(pos, meshes, bbox, k):
    """Голый металл (петли, тяги, фурнитура): блеск кромок, налёт, грязь в углублениях."""
    made = []
    e = _layer("Блеск кромок (зона edge × ChipsEdge50)", pos, color=(0.86, 0.86, 0.86), cmode=L.BlendingMode.Screen,
               cop=0.35 * k, rough=-0.05, rmode="add", rop=0.4)
    zone(e, "edge", _m("ChipsEdge50"), 520, bbox, rot=0.3, harden=(0.45, 0.7))
    made.append(_scope(e, meshes))
    a = _layer("Налёт и пятна окисла (SI015)", _above(e), color=(0.40, 0.37, 0.33), cmode=L.BlendingMode.Multiply,
               cop=0.30 * k, rough=0.12, rmode="add", rop=0.2 * k)
    spread(a, si(15), 1800, bbox, rot=0.8)
    made.append(_scope(a, meshes))
    d = _layer("Грязь в углублениях (AO × dirt_5)", _above(a), color=(0.12, 0.10, 0.08), cop=0.75 * k, rough=0.85, rop=0.8,
               metal=0.0)
    ao_seams(d, bbox, "dirt_5", 1000)
    made.append(_scope(d, meshes))
    return made


def dark_wear(pos, meshes, bbox, k):
    """Чёрный пластик, резина, войлок (ложемент, стойки, дисплеи, крышка принтера): без серых клякс — светлые затёртые кромки
    мелко, пыль сверху тонко и равномерной дымкой."""
    made = []
    e = _layer("Затёртые кромки (зона edge × ChipsEdge50)", pos, color=(0.30, 0.30, 0.30), cmode=L.BlendingMode.Screen,
               cop=0.30 * k, rough=0.15, rmode="add", rop=0.7)
    zone(e, "edge", _m("ChipsEdge50"), 520, bbox, rot=0.3, harden=(0.45, 0.7))
    made.append(_scope(e, meshes))
    h = _layer("Пыль — дымка", _above(e), color=(0.30, 0.29, 0.27), cop=0.06 * k, rough=0.85, rop=0.12, metal=0.0)
    made.append(_scope(h, meshes))
    u = _layer("Пыль сверху (зона up × SI012)", _above(h), color=(0.30, 0.29, 0.27), cop=0.12 * k, rough=0.9, rop=0.2,
               metal=0.0)
    zone(u, "up", si(12), 1500, bbox, rot=0.6)
    made.append(_scope(u, meshes))
    d = _layer("Пыль в углублениях (AO × dirt_4)", _above(u), color=(0.22, 0.20, 0.17), cop=0.20 * k, rough=0.85, rop=0.4,
               metal=0.0)
    ao_seams(d, bbox, "dirt_4", 1000, pos=0.55)
    made.append(_scope(d, meshes))
    return made


def abs_wear(pos, meshes, bbox, k):
    """Бежевый АБС: неровное жёлто-бурое пожелтение на верхних и выступающих местах, тёмная грязь в щелях и в поле клавиш
    (AO и зона keyfield × dirt), затёртый глянец на кромках, жир у замка."""
    made = []
    y = _layer("Пожелтение — верх (зона up × SI014)", pos, color=(0.80, 0.60, 0.30), cmode=L.BlendingMode.Multiply,
               cop=0.42 * k)
    zone(y, "up", si(14), 2000, bbox, rot=0.2)
    made.append(_scope(y, meshes))
    y2 = _layer("Пожелтение — выступы (зона edgew × SI015)", _above(y), color=(0.76, 0.54, 0.26),
                cmode=L.BlendingMode.Multiply, cop=0.38 * k)
    zone(y2, "edgew", si(15), 1800, bbox, rot=1.0)
    made.append(_scope(y2, meshes))
    # тёмная грязь между клавишами и в стыках корпуса: цвет ~(60, 50, 40) умножением до 0,5
    d = _layer("Грязь в щелях (AO × dirt_4)", _above(y2), color=(0.24, 0.20, 0.16), cmode=L.BlendingMode.Multiply,
               cop=0.9, rough=0.8, rop=0.8)
    ao_seams(d, bbox, "dirt_4", 900, ao=0.16, pos=0.45)
    made.append(_scope(d, meshes))
    d2 = _layer("Грязь между клавишами (зона keyfield × dirt_5)", _above(d), color=(0.24, 0.20, 0.16),
                cmode=L.BlendingMode.Multiply, cop=0.9, rough=0.8, rop=0.8)
    zone(d2, "keyfield", sh("dirt_5"), 800, bbox, rot=0.4, harden=(0.35, 0.5))
    made.append(_scope(d2, meshes))
    e = _layer("Затёртый глянец кромок (зона edge × ChipsEdge50)", _above(d2), color=(0.86, 0.82, 0.74),
               cmode=L.BlendingMode.Screen, cop=0.20 * k, rough=-0.20, rmode="add", rop=0.9)
    zone(e, "edge", _m("ChipsEdge50"), 520, bbox, rot=0.9, harden=(0.45, 0.7))
    made.append(_scope(e, meshes))
    f = _layer("Жирные следы у замка (touch × Fingerprints001)", _above(e), color=(0.66, 0.60, 0.50),
               cmode=L.BlendingMode.Multiply, cop=0.40 * k, rough=-0.14, rmode="add", rop=0.8)
    zone(f, "touch", fp(1), 600, bbox, rot=0.7)
    made.append(_scope(f, meshes))
    return made


def keys_wear(pos, meshes, bbox, k):
    """Клавиши: всё, что у корпуса АБС (грязь между клавишами и т. д.), плюс верх ВСЕХ заполирован пальцами (глаже на 0,12) и
    на ~7 % клавиш подпись затёрта (крупные пятна ChipsEdge14 поверх печати: цвет клавиши, 55 %)."""
    made = abs_wear(pos, meshes, bbox, k)
    last = made[-1]
    pol = _layer("Верх клавиш заполирован (весь)", _above(last), rough=-0.12, rmode="add", rop=1.0)
    made.append(_scope(pol, meshes))
    leg = _layer("Подписи затёрты на ходовых клавишах", _above(pol), color=(0.52, 0.51, 0.48), cop=0.55)
    spread(leg, _m("ChipsEdge14"), 260, bbox, rot=0.6)
    made.append(_scope(leg, meshes))
    return made


def misc_wear(pos, meshes, bbox, k):
    """Этикетки, экраны, стекло: пыль; у кассы на окнах индикаторов — зелёные сегментные «0.00» (lc3_digits.py)."""
    u = _layer("Пыль (SI012)", pos, color=(0.45, 0.43, 0.40), cop=0.25 * k, rough=0.85, rop=0.4 * k, metal=0.0)
    spread(u, si(12), 1500, bbox, rot=0.6)
    out = [_scope(u, meshes)]
    if CTX["game"] == "lc_cash":
        dg = _layer("Цифры «0.00» (lc3_digits)", _above(u), color=(0.10, 0.75, 0.25), rough=0.35, metal=0.0)
        sp_finish.bitmap_mask(dg, f"{SRC}/wear_v03/lc_cash_digits_alpha.png")
        screens = [m for m in meshes if "экран" in m]
        out.append(_scope(dg, screens or meshes))
    return out


KINDS = {"paint": paint_wear, "bare": bare_wear, "dark": dark_wear, "abs": abs_wear, "keys": keys_wear, "misc": misc_wear}
# сколы кромок по предмету: (рисунок, цвет, шероховатость, металл, высота, зона, кайма грунта)
EDGE = {
    "lc_gun": ("ChipsEdge65", STEEL, 0.50, 0.85, 0.497, "edge", True),
    "lc_file": ("ChipsEdge65", STEEL, 0.50, 0.85, 0.497, "edge", True),
    "lc_safe": ("ChipsEdge65", GRAYWORN, 0.55, 0.0, 0.499, "edge_s", False),
    "lc_cell": ("ChipsEdge65", GRAYWORN, 0.55, 0.0, 0.499, "edge_s", False),
    "lc_aid": ("ChipsEdge50", (0.55, 0.55, 0.55), 0.5, 0.7, 0.497, "edge", True),
    "lc_cash": ("ChipsEdge14", (0.40, 0.38, 0.35), 0.55, 0.4, 0.498, "edge", True),
}


def wear(setname, base, game, bbox, kinds, k=1.0, floor=0.80):
    """Печать этапа 1 слоем и группа износа над заводской: kinds — {вид: [сетки]}."""
    import sp_dorm_wear as W
    CTX["game"] = game
    pos = W._new_group(setname, base, game)
    log = []
    last = None
    for kind, meshes in kinds.items():
        if not meshes:
            continue
        sub = L.insert_group(pos if last is None else _above(last))
        sub.set_name(f"Износ — {kind}")
        for ch in sp_lib.stack_by_name(setname).all_channels():
            sub.set_blending_mode(L.BlendingMode.Passthrough, ch)
        inner = L.InsertPosition.inside_node(sub, L.NodeStack.Substack)
        fn = KINDS[kind]
        made = fn(inner, meshes, bbox, k, floor, EDGE[game]) if kind == "paint" else fn(inner, meshes, bbox, k)
        log.append(f"{kind}:{len(meshes)}м/{len(made)}сл")
        last = sub
    return f"{game}: " + " ".join(log)
