"""Контейнеры для лута, партия 1, отделка v03 (заводская + износ сразу, в Painter): группа износа «Этап 2 — износ»
(Passthrough) над печатью и заводской группой. Выполняется внутри Painter (задание lc3_sp.py через мост).

Причина v03: v01 / v02 владелец не принял — «не хватает понимания, из какого материала сделан объект». Образцы владельца
(2026-11-13): оружейный шкаф, сейф, касса — вещь прослужила лет десять и брошена. Материал читается разницей краски и
оголённого металла, чистого и грязного; износ привязан к форме (кромки, углы, низ, вокруг ручек), грязь — по AO.

РИСУНОК износа — только фото-маски из библиотеки владельца E:/Models Blender/Маски_АЛЬФА (указание владельца 2026-11-13:
«процедурщина» не принята). Генераторы Painter (кривизна, AO, положение) дают лишь МЕСТО (кромка, угол, низ) и всегда
умножаются на маску. Чистых noise_* / grunge_* / облаков в видимых слоях износа нет. Маски тусклые (среднее 0,03–0,3) —
порог / растяжка Histogram Scan поверх маски.

Виды износа (kind): paint — крашеная сталь; bare — голый металл; dark — чёрный пластик, резина, войлок; abs — бежевый АБС;
misc — этикетки, стекло.
"""
import substance_painter.layerstack as L

import sp_finish
import sp_lib
from sp_lib import CH, fill

GROUP = "Этап 2 — износ"
PRINT = "Печать (этап 1)"
STEEL = (0.68, 0.68, 0.69)   # светлая оголённая сталь: в тёмной студии зеркальный металл читается чёрным, поэтому светлее и шершавее
OWN = "E:/Models Blender/Маски_АЛЬФА"
CC0 = OWN + "/50_Скачанные_CC0_ambientCG_ShareTextures"


MASKS = "E:/Games/RING-godot/_asset_src/loot_containers/masks_v03"   # рабочие копии масок владельца (lc3_masks.py)


def _m(name):
    return f"{MASKS}/{name}.png"


def si(n):
    """ambientCG SurfaceImperfections0NN (7, 12, 13 — Opacity; 14, 15, 16 — Color), серая копия."""
    return _m(f"SI{n:03d}")


def sc(n):
    """ambientCG Scratches00N (Opacity)."""
    return _m(f"Scratches{n:03d}")


def sm(n):
    """ambientCG Smear00N (Color — серая карта мазков)."""
    return _m(f"Smear{n:03d}")


def fp(n):
    """ambientCG Fingerprints00N (Opacity)."""
    return _m(f"Fingerprints{n:03d}")


def sh(name):
    """ShareTextures: dirt_4, dirt_5, grunge_3, scratches_5."""
    return _m(name)


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


def mask_curv(layer, balance, contrast):
    """МЕСТО: кромки и углы (кривизна)."""
    return sp_lib.mask_generator(layer, "mg_curvature/mg_curvature",
                                 sp_finish._curv({"global_balance": balance, "global_contrast": contrast}))


def thresh(node, position, contrast, warp=None):
    last = sp_finish._mfilter(node, "histogram_scan", {"Position": position, "Contrast": contrast})
    if warp:
        last = sp_finish._mfilter(last, "warp", {"intensity": warp})
    return last


def own(layer, path, period, bbox, above=None, rot=0.0, blend=L.BlendingMode.Multiply, pos=None, contrast=0.6,
        opacity=1.0):
    """РИСУНОК: маска владельца заливкой в маску слоя (трёхпроекционно, плитка period мм; картинка при каждой сборке
    импортируется заново — sp_finish._bitmap по времени файла); первая в маске или умножает «место» (above).
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


# Периоды масок — в мм на плитку маски 2K: тексель маски ≈ 2/3 текселя карты (плотность развёрток ~0,7–0,85 пикс/мм →
# ≈ 1,6–2 м на плитку): одна плитка на предмет, разный поворот у разных слоёв — повторов не видно.
def paint_wear(pos, meshes, bbox, k, floor):
    """Крашеная сталь: сколы до стали, царапины, потёртости, грязь. k — сила (1 — как на образце оружейного шкафа)."""
    made = []
    # 0. неровность старой краски: фото-основа ambientCG SurfaceImperfections014 / 016, слабо
    t = _layer("Старая краска — разный тон (SI014)", pos, color=(0.72, 0.70, 0.66), cop=0.07 * k, rough=0.10, rmode="add",
               rop=0.25 * k)
    own(t, si(14), 2400, bbox, rot=0.4)
    made.append(_scope(t, meshes))
    t2 = _layer("Старая краска — тёмные пятна (SI016)", _above(t), color=(0.55, 0.52, 0.48), cmode=L.BlendingMode.Multiply,
                cop=0.10 * k, rough=-0.05, rmode="add", rop=0.5)
    own(t2, si(16), 1800, bbox, rot=1.2)
    made.append(_scope(t2, meshes))
    last = t2
    # 1. сколы по кромкам: кривизна (место) × крапинки SI007 (рисунок) → короткие рваные сколы; сталь, чуть ниже краски
    c = _layer("Сколы краски до стали — кромки (кривизна × SI007)", _above(last), color=STEEL, rough=0.50, metal=0.85,
               height=0.497)
    g = mask_curv(c, 0.66, 0.9)
    own(c, si(7), 650, bbox, above=g, rot=0.3, pos=0.16 + 0.1 * k, contrast=0.5)
    made.append(_scope(c, meshes))
    last = c
    # 1б. крупнее на самых торчащих углах: SI013 (хлопья)
    c2 = _layer("Сколы краски — углы (кривизна × SI013)", _above(last), color=STEEL, rough=0.46, metal=0.85, height=0.496)
    g = mask_curv(c2, 0.78, 0.95)
    own(c2, si(13), 900, bbox, above=g, rot=1.1, pos=0.2 + 0.1 * k, contrast=0.5)
    made.append(_scope(c2, meshes))
    last = c2
    # 2. редкие точечные сколы на плоскостях: SI007 другим поворотом и масштабом
    p = _layer("Сколы краски — точки (SI007)", _above(last), color=STEEL, rough=0.52, metal=0.85, height=0.497)
    own(p, si(7), 650, bbox, rot=2.2, pos=0.22 * k, contrast=0.4)
    made.append(_scope(p, meshes))
    last = p
    # 3. царапины: до стали (Scratches002, редкие) и светлее краски (Scratches003)
    s = _layer("Царапины до стали (Scratches002)", _above(last), color=STEEL, rough=0.48, metal=0.85, height=0.498)
    own(s, sc(2), 700, bbox, rot=0.3, pos=0.36 + 0.08 * k, contrast=0.4)
    made.append(_scope(s, meshes))
    s2 = _layer("Царапины по краске (Scratches003)", _above(s), color=(0.82, 0.82, 0.80), cmode=L.BlendingMode.Screen,
                cop=0.35 * k, rough=0.10, rmode="add", rop=0.7)
    own(s2, sc(3), 600, bbox, rot=1.9, pos=0.45 + 0.1 * k, contrast=0.4)
    made.append(_scope(s2, meshes))
    last = s2
    # 4. разводы блеска: Smear006 (мазки протирания), слабо
    w = _layer("Разводы блеска (Smear006)", _above(last), color=(0.78, 0.78, 0.76), cmode=L.BlendingMode.Overlay,
               cop=0.10 * k, rough=0.12, rmode="add", rop=0.5 * k)
    own(w, sm(6), 1900, bbox, rot=0.7, opacity=0.5)
    made.append(_scope(w, meshes))
    last = w
    # 5. грязь в углах: AO (место) × dirt_4 (ShareTextures, рисунок)
    d = _layer("Грязь в углах (AO × dirt_4)", _above(last), color=(0.20, 0.17, 0.13), cop=0.60 * k, rough=0.88, rop=0.8,
               metal=0.0, height=0.5)
    g = sp_lib.mask_generator(d, "mg_ambient_occlusion/mg_ambient_occlusion", {"ao_invert": 1})
    g = thresh(g, 0.22, 0.4)
    own(d, sh("dirt_4"), 1400, bbox, above=g, rot=0.5, pos=0.5, contrast=0.6)
    made.append(_scope(d, meshes))
    last = d
    # 6. пыль: SurfaceImperfections012
    u = _layer("Пыль (SI012)", _above(last), color=(0.55, 0.52, 0.47), cop=0.10 * k, rough=0.9, rop=0.25 * k, metal=0.0)
    own(u, si(12), 1800, bbox, rot=0.7)
    made.append(_scope(u, meshes))
    last = u
    # 7. грязь у пола: положение (место) × grunge_3 (ShareTextures)
    f = _layer("Грязь у пола (положение × grunge_3)", _above(last), color=(0.15, 0.12, 0.09), cop=0.60 * k, rough=0.85,
               rop=0.8, metal=0.0)
    g = sp_lib.mask_generator(f, "mg_position/mg_position", {"position_direction_topbottom_opacity": 1.0,
                                                           "position_direction_rightleft_opacity": 0.0,
                                                           "position_direction_frontback_opacity": 0.0})
    gg = thresh(g, floor, 0.45)
    own(f, sh("grunge_3"), 1600, bbox, above=gg, rot=0.2)
    made.append(_scope(f, meshes))
    return made


def bare_wear(pos, meshes, bbox, k):
    """Голый металл: налёт, царапины, грязь в углублениях, точки коррозии (маски владельца)."""
    made = []
    a = _layer("Налёт и пятна окисла (SI015)", pos, color=(0.40, 0.37, 0.33), cmode=L.BlendingMode.Multiply, cop=0.35 * k,
               rough=0.12, rmode="add", rop=0.6 * k)
    own(a, si(15), 1800, bbox, rot=0.8)
    made.append(_scope(a, meshes))
    s = _layer("Царапины металла (Scratches002)", _above(a), color=(0.86, 0.86, 0.86), cmode=L.BlendingMode.Screen,
               cop=0.5 * k, rough=0.16, rmode="add", rop=0.7)
    own(s, sc(2), 700, bbox, rot=0.4, pos=0.45, contrast=0.4)
    made.append(_scope(s, meshes))
    d = _layer("Грязь в углублениях (AO × dirt_5)", _above(s), color=(0.12, 0.10, 0.08), cop=0.85 * k, rough=0.85, rop=0.8,
               metal=0.0)
    g = sp_lib.mask_generator(d, "mg_ambient_occlusion/mg_ambient_occlusion", {"ao_invert": 1})
    g = thresh(g, 0.25, 0.4)
    own(d, sh("dirt_5"), 1000, bbox, above=g, rot=0.5, pos=0.5, contrast=0.6)
    made.append(_scope(d, meshes))
    r = _layer("Точки коррозии (12_Пористая_коррозия_02)", _above(d), color=(0.26, 0.15, 0.09), cop=0.30 * k, rough=0.85,
               rop=0.7, metal=0.0)
    own(r, _m("Corrosion02"), 900, bbox, rot=0.5, pos=0.35, contrast=0.5)
    made.append(_scope(r, meshes))
    return made


def dark_wear(pos, meshes, bbox, k):
    """Чёрный пластик, резина, войлок: светлые затёртые кромки, царапины, пыль."""
    made = []
    e = _layer("Затёртые кромки (кривизна × SI007)", pos, color=(0.34, 0.34, 0.34), cmode=L.BlendingMode.Screen,
               cop=0.6 * k, rough=0.18, rmode="add", rop=0.9)
    g = mask_curv(e, 0.68, 0.9)
    own(e, si(7), 900, bbox, above=g, rot=0.3, pos=0.3, contrast=0.5)
    made.append(_scope(e, meshes))
    s = _layer("Царапины (scratches_5)", _above(e), color=(0.36, 0.36, 0.36), cmode=L.BlendingMode.Screen, cop=0.55 * k,
               rough=0.12, rmode="add", rop=0.7)
    own(s, sh("scratches_5"), 800, bbox, rot=1.0, pos=0.4, contrast=0.4)
    made.append(_scope(s, meshes))
    u = _layer("Пыль (SI012)", _above(s), color=(0.34, 0.32, 0.29), cop=0.20 * k, rough=0.9, rop=0.4, metal=0.0)
    own(u, si(12), 1500, bbox, rot=0.6)
    made.append(_scope(u, meshes))
    return made


def abs_wear(pos, meshes, bbox, k):
    """Бежевый АБС: неровное пожелтение (SI014 / SI015), тёмная грязь в щелях, затёртый блеск, жир (Fingerprints)."""
    made = []
    y = _layer("Пожелтение (SI014)", pos, color=(0.78, 0.58, 0.28), cmode=L.BlendingMode.Multiply, cop=0.50 * k)
    own(y, si(14), 2000, bbox, rot=0.2)
    made.append(_scope(y, meshes))
    y2 = _layer("Пожелтение — по выступам (кривизна × SI015)", _above(y), color=(0.74, 0.52, 0.24),
                cmode=L.BlendingMode.Multiply, cop=0.40 * k)
    g = mask_curv(y2, 0.58, 0.45)
    own(y2, si(15), 1800, bbox, above=g, rot=1.0)
    made.append(_scope(y2, meshes))
    d = _layer("Грязь в щелях (AO × dirt_4)", _above(y2), color=(0.10, 0.085, 0.06), cop=0.9 * k, rough=0.8, rop=0.8,
               metal=0.0)
    g = sp_lib.mask_generator(d, "mg_ambient_occlusion/mg_ambient_occlusion", {"ao_invert": 1})
    g = thresh(g, 0.25, 0.4)
    own(d, sh("dirt_4"), 1000, bbox, above=g, rot=0.5, pos=0.5, contrast=0.6)
    made.append(_scope(d, meshes))
    e = _layer("Затёртые выступы (кривизна × SI007)", _above(d), color=(0.86, 0.82, 0.74), cmode=L.BlendingMode.Screen,
               cop=0.25 * k, rough=-0.20, rmode="add", rop=0.9)
    g = mask_curv(e, 0.66, 0.85)
    own(e, si(7), 1000, bbox, above=g, rot=0.9, pos=0.3, contrast=0.5)
    made.append(_scope(e, meshes))
    s = _layer("Царапины (Scratches003)", _above(e), color=(0.88, 0.86, 0.80), cmode=L.BlendingMode.Screen, cop=0.40 * k,
               rough=0.14, rmode="add", rop=0.8)
    own(s, sc(3), 650, bbox, rot=0.5, pos=0.5, contrast=0.4)
    made.append(_scope(s, meshes))
    f = _layer("Жирные следы (Fingerprints001)", _above(s), color=(0.66, 0.60, 0.50), cmode=L.BlendingMode.Multiply,
               cop=0.40 * k, rough=-0.12, rmode="add", rop=0.8)
    own(f, fp(1), 700, bbox, rot=0.7, opacity=0.8)
    made.append(_scope(f, meshes))
    return made


def misc_wear(pos, meshes, bbox, k):
    """Этикетки, экраны, стекло: пыль."""
    u = _layer("Пыль (SI012)", pos, color=(0.45, 0.43, 0.40), cop=0.25 * k, rough=0.85, rop=0.4 * k, metal=0.0)
    own(u, si(12), 1500, bbox, rot=0.6)
    return [_scope(u, meshes)]


KINDS = {"paint": paint_wear, "bare": bare_wear, "dark": dark_wear, "abs": abs_wear, "misc": misc_wear}


def wear(setname, base, game, bbox, kinds, k=1.0, floor=0.80):
    """Печать этапа 1 слоем и группа износа над заводской: kinds — {вид: [сетки]}."""
    import sp_dorm_wear as W
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
        made = fn(inner, meshes, bbox, k, floor) if kind == "paint" else fn(inner, meshes, bbox, k)
        log.append(f"{kind}:{len(meshes)}м/{len(made)}сл")
        last = sub
    return f"{game}: " + " ".join(log)
