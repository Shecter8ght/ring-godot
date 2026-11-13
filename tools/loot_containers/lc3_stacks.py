"""Контейнеры для лута, партия 1, отделка v03 (заводская + износ сразу, в Painter): группа износа «Этап 2 — износ»
(Passthrough) над печатью и заводской группой. Выполняется внутри Painter (задание lc3_sp.py через мост).

Образцы владельца (2026-11-13): оружейный шкаф, сейф, касса — вещь прослужила лет десять и брошена. Материал читается
разницей краски и оголённого металла, чистого и грязного; ПЛОСКОСТИ ПОЧТИ ЧИСТЫЕ, износ собран ПО ФОРМЕ (замечание
владельца по листам сверки v03, круг 2): кромки и наружные углы, вокруг ручек / замков / лимба, низ у пола, верх (пыль).

РИСУНОК износа — только фото-маски из библиотеки владельца E:/Models Blender/Маски_АЛЬФА (lc3_masks.py: рабочие копии 2K и
рисунки с заданной долей площади по их же пикселям: ChipsEdge45 / ChipsEdge14 — чешуйки SurfaceImperfections013,
ScrFew / ScrTouch — линии Scratches003 / 002, порезанные на отрезки пятнами SurfaceImperfections012). МЕСТО — карты зон
в развёртке по картам геометрии (lc3_zones.py: кромка 1,5–4,5 мм, наружные рёбра, низ, верх, вокруг ручек), у Painter
для листовых деталей кривизна полосу кромки не даёт. Облаков и noise_* / grunge_* в видимых слоях износа нет.

Виды износа (kind): paint — крашеная сталь; bare — голый металл; dark — чёрный пластик, резина, войлок; abs — бежевый
АБС; misc — этикетки, стекло.
"""
import substance_painter.layerstack as L

import sp_finish
import sp_lib
from sp_lib import CH, fill

GROUP = "Этап 2 — износ"
PRINT = "Печать (этап 1)"
STEEL = (0.68, 0.68, 0.69)   # светлая оголённая сталь: в тёмной студии зеркальный металл читается чёрным — светлее и шершавее
GRAYWORN = (0.34, 0.34, 0.35)   # затёртый тёмно-серый (сейф, ячейка: кромки не до блестящего металла)
SRC = "E:/Games/RING-godot/_asset_src/loot_containers"
MASKS = SRC + "/masks_v03"   # рабочие копии масок владельца и рисунки по их пикселям (lc3_masks.py)
CTX = {"game": ""}


def _m(name):
    return f"{MASKS}/{name}.png"


def si(n):
    """ambientCG SurfaceImperfections0NN (7, 12, 13 — Opacity; 14, 15, 16 — Color), серая копия."""
    return _m(f"SI{n:03d}")


def sc(n):
    return _m(f"Scratches{n:03d}")


def sm(n):
    return _m(f"Smear{n:03d}")


def fp(n):
    return _m(f"Fingerprints{n:03d}")


def sh(name):
    """ShareTextures: dirt_4, dirt_5, grunge_3, scratches_5."""
    return _m(name)


def zone_path(zone):
    return f"{SRC}/wear_v03/{CTX['game']}_{zone}.png"


def _above(node):
    return L.InsertPosition.above_node(node)


def _layer(name, pos, color=None, cmode=L.BlendingMode.Normal, cop=1.0, rough=None, rmode=None, rop=1.0, metal=None,
           height=None, hop=1.0):
    """Слой износа: цвет режимом наложения; блеск — числом (Normal) или прибавкой / вычитанием (rmode add; знак rough);
    металл — числом; высота — абсолютным уровнем (Normal)."""
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


def zone(layer, name, pattern=None, period=700, bbox=1000.0, rot=0.0, opacity=1.0, power=1.0):
    """МЕСТО (карта зоны в развёртке) × РИСУНОК (маска владельца, трёхпроекционно); pattern None — зона как есть.
    Зона первой в маске слоя, рисунок умножает её; opacity — сила зоны, power не используется (резерв)."""
    sp_lib.mask_black(layer)
    z = L.insert_fill(L.InsertPosition.inside_node(layer, L.NodeStack.Mask))
    z.set_source(None, sp_finish._bitmap(zone_path(name)))
    z.set_projection_mode(L.ProjectionMode.UV)
    z.set_opacity(opacity)
    if pattern is None:
        return z
    return own(layer, pattern, period, bbox, above=z, rot=rot)


def spread(layer, pattern, period, bbox, rot=0.0, opacity=1.0):
    """РИСУНОК по всей детали, без зоны (редкие царапины на плоскости): первым в маске."""
    return own(layer, pattern, period, bbox, rot=rot, opacity=opacity)


def ao_seams(layer, bbox, dirt, period=1000, rot=0.5):
    """Грязь в углублениях и стыках: AO (место) × рисунок владельца dirt_* (порог — рваный край)."""
    g = sp_lib.mask_generator(layer, "mg_ambient_occlusion/mg_ambient_occlusion", {"ao_invert": 1})
    g = thresh(g, 0.22, 0.4)
    return own(layer, sh(dirt), period, bbox, above=g, rot=rot, pos=0.5, contrast=0.6)


# ------------------------------------------------------------------------------------------------------------- виды
def paint_wear(pos, meshes, bbox, k, floor, edge=None):
    """Крашеная сталь: плоскости чистые; сколы цепочкой вдоль рёбер (доля длины — рисунок ChipsEdge45 / ChipsEdge14),
    редкие короткие царапины, следы рук у ручек и замков, пыль сверху, грязь у пола и в стыках, следы обуви внизу.
    edge: (рисунок, цвет сколов, шероховатость, металл, высота) — у шкафа и картотеки до светлого металла, у сейфа и
    ячейки до тёмно-серого затёртого."""
    pat, col, rgh, met, hgt = edge or ("ChipsEdge45", STEEL, 0.50, 0.85, 0.497)
    made = []
    # 0. неровность краски: тон ±3–4 %, шероховатость ±0,08 — крупные фото-пятна SI014 / Smear004
    t = _layer("Тон краски — крупно (SI014)", pos, color=(0.45, 0.50, 0.42), cop=0.05 * k, rough=0.08, rmode="add",
               rop=0.30 * k)
    spread(t, si(14), 2600, bbox, rot=0.4)
    made.append(_scope(t, meshes))
    t2 = _layer("Блеск — разводы (Smear004)", _above(t), color=(0.5, 0.5, 0.5), cmode=L.BlendingMode.Multiply, cop=0.04 * k,
                rough=-0.06, rmode="add", rop=0.5)
    spread(t2, sm(4), 2000, bbox, rot=1.1, opacity=0.8)
    made.append(_scope(t2, meshes))
    last = t2
    # 1. кромки: цепочка сколов вдоль наружных рёбер (зона edge 1,5–4,5 мм × чешуйки SI013 с долей площади 45 % / 14 %)
    c = _layer("Сколы кромок (зона × " + pat + ")", _above(last), color=col, rough=rgh, metal=met, height=hgt)
    zone(c, "edge", _m(pat), 520, bbox, rot=0.3)
    made.append(_scope(c, meshes))
    last = c
    # 1б. рядом с ребром металл не блестит, а затёрт: широкая зона edgew × крапинки SI007 — светлее краски, шершавее
    w = _layer("Затёртость у кромки (зона × SI007)", _above(last), color=(0.62, 0.62, 0.60), cmode=L.BlendingMode.Screen,
               cop=0.25 * k, rough=0.12, rmode="add", rop=0.5)
    zone(w, "edgew", _m("ChipsSpeck"), 700, bbox, rot=1.4)
    made.append(_scope(w, meshes))
    last = w
    # 2. редкие короткие тонкие царапины по плоскости: чуть светлее краски (не до металла)
    s = _layer("Царапины редкие короткие (ScrFew)", _above(last), color=(0.70, 0.70, 0.66), cmode=L.BlendingMode.Screen,
               cop=0.30 * k, rough=0.10, rmode="add", rop=0.5)
    spread(s, _m("ScrFew"), 900, bbox, rot=0.8)
    made.append(_scope(s, meshes))
    last = s
    # 3. следы рук у ручек и замков: царапины гуще (ScrTouch × touch), потёртость до грунта узким пятном (touch_core ×
    #    «сколы с потёртостями»), ладони — темнее и глаже
    s2 = _layer("Царапины у ручки (зона × ScrTouch)", _above(last), color=(0.72, 0.72, 0.68), cmode=L.BlendingMode.Screen,
                cop=0.40 * k, rough=0.10, rmode="add", rop=0.5)
    zone(s2, "touch", _m("ScrTouch"), 650, bbox, rot=1.9)
    made.append(_scope(s2, meshes))
    pr = _layer("Потёртость до грунта у ручки (touch_core × ChipsWorn)", _above(s2), color=(0.42, 0.43, 0.42), rough=0.62,
                metal=0.0, height=0.498)
    zone(pr, "touch_core", _m("ChipsEdge14"), 500, bbox, rot=0.5)
    made.append(_scope(pr, meshes))
    hd = _layer("Ладони у ручки (touch × Palm)", _above(pr), color=(0.55, 0.55, 0.54), cmode=L.BlendingMode.Multiply,
                cop=0.35 * k, rough=-0.14, rmode="add", rop=0.8)
    zone(hd, "touch_core", _m("Palm"), 400, bbox, rot=0.2)
    made.append(_scope(hd, meshes))
    last = hd
    # 4. пыль: сверху (up × SI012), светлее и шершавее краски
    u = _layer("Пыль сверху (зона up × SI012)", _above(last), color=(0.50, 0.50, 0.49), cop=0.28 * k, rough=0.9, rop=0.4 * k,
               metal=0.0)
    zone(u, "up", si(12), 1500, bbox, rot=0.7)
    made.append(_scope(u, meshes))
    last = u
    # 5. тёмная грязь: низ у пола (floor × grunge_3) и стыки (AO × dirt_4)
    f = _layer("Грязь у пола (зона floor × dirt_5)", _above(last), color=(0.12, 0.10, 0.08), cop=0.60 * k, rough=0.85, rop=0.8,
               metal=0.0)
    zone(f, "floor", sh("dirt_5"), 900, bbox, rot=0.2)
    made.append(_scope(f, meshes))
    d = _layer("Грязь в стыках (AO × dirt_4)", _above(f), color=(0.14, 0.12, 0.09), cop=0.55 * k, rough=0.88, rop=0.8,
               metal=0.0, height=0.5)
    ao_seams(d, bbox, "dirt_4", 1400)
    made.append(_scope(d, meshes))
    last = d
    # 6. следы обуви / тележки внизу (kick × Резина_03): тёмные мазки
    if CTX["game"] in ("lc_gun", "lc_file"):   # внизу шкафов — обувь и тележка; настенные и настольные предметы — нет
        r = _layer("Следы обуви внизу (зона kick × Резина_03)", _above(last), color=(0.20, 0.19, 0.17),
                   cmode=L.BlendingMode.Multiply, cop=0.55 * k, rough=-0.05, rmode="add", rop=0.5)
        zone(r, "kick", _m("Rubber03"), 500, bbox, rot=0.4)
        made.append(_scope(r, meshes))
    return made


def bare_wear(pos, meshes, bbox, k):
    """Голый металл (петли, тяги, фурнитура): затёртость, царапины, грязь в углублениях, следы рук."""
    made = []
    e = _layer("Блеск кромок (зона edge × ChipsEdge45)", pos, color=(0.86, 0.86, 0.86), cmode=L.BlendingMode.Screen,
               cop=0.35 * k, rough=-0.05, rmode="add", rop=0.4)
    zone(e, "edge", _m("ChipsEdge45"), 520, bbox, rot=0.3)
    made.append(_scope(e, meshes))
    a = _layer("Налёт и пятна окисла (SI015)", _above(e), color=(0.40, 0.37, 0.33), cmode=L.BlendingMode.Multiply,
               cop=0.30 * k, rough=0.12, rmode="add", rop=0.2 * k)
    spread(a, si(15), 1800, bbox, rot=0.8)
    made.append(_scope(a, meshes))
    s = _layer("Царапины металла (ScrFew)", _above(a), color=(0.86, 0.86, 0.86), cmode=L.BlendingMode.Screen, cop=0.4 * k,
               rough=0.14, rmode="add", rop=0.6)
    spread(s, _m("ScrFew"), 700, bbox, rot=0.4)
    made.append(_scope(s, meshes))
    d = _layer("Грязь в углублениях (AO × dirt_5)", _above(s), color=(0.12, 0.10, 0.08), cop=0.75 * k, rough=0.85, rop=0.8,
               metal=0.0)
    ao_seams(d, bbox, "dirt_5", 1000)
    made.append(_scope(d, meshes))
    r = _layer("Точки коррозии у пола (floor × 12_Коррозия_02)", _above(d), color=(0.26, 0.15, 0.09), cop=0.30 * k,
               rough=0.85, rop=0.7, metal=0.0)
    zc = zone(r, "floor", _m("Corrosion02"), 900, bbox, rot=0.5)
    made.append(_scope(r, meshes))
    return made


def dark_wear(pos, meshes, bbox, k):
    """Чёрный пластик, резина, войлок: светлые затёртые кромки, следы рук, пыль сверху."""
    made = []
    e = _layer("Затёртые кромки (зона edge × ChipsEdge45)", pos, color=(0.34, 0.34, 0.34), cmode=L.BlendingMode.Screen,
               cop=0.5 * k, rough=0.18, rmode="add", rop=0.9)
    zone(e, "edge", _m("ChipsEdge45"), 520, bbox, rot=0.3)
    made.append(_scope(e, meshes))
    hd = _layer("Заглажено ладонями (touch × Palm)", _above(e), color=(0.7, 0.7, 0.7), cmode=L.BlendingMode.Screen, cop=0.12 * k,
                rough=-0.14, rmode="add", rop=0.7)
    zone(hd, "touch", _m("Palm"), 400, bbox, rot=0.2)
    made.append(_scope(hd, meshes))
    s = _layer("Царапины (ScrFew)", _above(hd), color=(0.36, 0.36, 0.36), cmode=L.BlendingMode.Screen, cop=0.40 * k,
               rough=0.10, rmode="add", rop=0.5)
    spread(s, _m("ScrFew"), 800, bbox, rot=1.0)
    made.append(_scope(s, meshes))
    u = _layer("Пыль сверху (up × SI012)", _above(s), color=(0.34, 0.33, 0.31), cop=0.25 * k, rough=0.9, rop=0.4, metal=0.0)
    zone(u, "up", si(12), 1500, bbox, rot=0.6)
    made.append(_scope(u, meshes))
    return made


def abs_wear(pos, meshes, bbox, k):
    """Бежевый АБС: неровное жёлто-бурое пожелтение на верхних и выступающих местах, тёмная жирная грязь в щелях, затёртый
    глянец на кромках и под пальцами, жир у клавиш и замка, редкие царапины."""
    made = []
    y = _layer("Пожелтение — верх (зона up × SI014)", pos, color=(0.80, 0.60, 0.30), cmode=L.BlendingMode.Multiply,
               cop=0.42 * k)
    zone(y, "up", si(14), 2000, bbox, rot=0.2)
    made.append(_scope(y, meshes))
    y2 = _layer("Пожелтение — выступы (зона edgew × SI015)", _above(y), color=(0.76, 0.54, 0.26),
                cmode=L.BlendingMode.Multiply, cop=0.38 * k)
    zone(y2, "edgew", si(15), 1800, bbox, rot=1.0)
    made.append(_scope(y2, meshes))
    d = _layer("Грязь в щелях (AO × dirt_4)", _above(y2), color=(0.10, 0.085, 0.06), cop=0.95 * k, rough=0.8, rop=0.8,
               metal=0.0)
    g = sp_lib.mask_generator(d, "mg_ambient_occlusion/mg_ambient_occlusion", {"ao_invert": 1})
    g = thresh(g, 0.30, 0.4)
    own(d, sh("dirt_4"), 900, bbox, above=g, rot=0.5, pos=0.55, contrast=0.6)
    made.append(_scope(d, meshes))
    e = _layer("Затёртый глянец кромок (зона edge × ChipsEdge45)", _above(d), color=(0.86, 0.82, 0.74),
               cmode=L.BlendingMode.Screen, cop=0.25 * k, rough=-0.20, rmode="add", rop=0.9)
    zone(e, "edge", _m("ChipsEdge45"), 520, bbox, rot=0.9)
    made.append(_scope(e, meshes))
    s = _layer("Царапины редкие (ScrFew)", _above(e), color=(0.88, 0.86, 0.80), cmode=L.BlendingMode.Screen, cop=0.30 * k,
               rough=0.10, rmode="add", rop=0.6)
    spread(s, _m("ScrFew"), 700, bbox, rot=0.5)
    made.append(_scope(s, meshes))
    f = _layer("Жирные следы у клавиш и замка (touch × Fingerprints001)", _above(s), color=(0.66, 0.60, 0.50),
               cmode=L.BlendingMode.Multiply, cop=0.40 * k, rough=-0.14, rmode="add", rop=0.8)
    zone(f, "touch", fp(1), 600, bbox, rot=0.7)
    made.append(_scope(f, meshes))
    return made


def misc_wear(pos, meshes, bbox, k):
    """Этикетки, экраны, стекло: пыль и отпечатки."""
    u = _layer("Пыль (SI012)", pos, color=(0.45, 0.43, 0.40), cop=0.25 * k, rough=0.85, rop=0.4 * k, metal=0.0)
    spread(u, si(12), 1500, bbox, rot=0.6)
    return [_scope(u, meshes)]


KINDS = {"paint": paint_wear, "bare": bare_wear, "dark": dark_wear, "abs": abs_wear, "misc": misc_wear}
# сколы кромок по предмету (рисунок, цвет, шероховатость, металл, высота): сейф и ячейка — до тёмно-серого затёртого, ~10–15 %
EDGE = {
    "lc_gun": ("ChipsEdge45", STEEL, 0.50, 0.85, 0.497),
    "lc_file": ("ChipsEdge45", STEEL, 0.50, 0.85, 0.497),
    "lc_safe": ("ChipsEdge14", GRAYWORN, 0.58, 0.4, 0.498),
    "lc_cell": ("ChipsEdge14", GRAYWORN, 0.58, 0.4, 0.498),
    "lc_aid": ("ChipsEdge14", (0.55, 0.55, 0.55), 0.5, 0.7, 0.497),
    "lc_cash": ("ChipsEdge14", (0.40, 0.38, 0.35), 0.55, 0.4, 0.498),
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
