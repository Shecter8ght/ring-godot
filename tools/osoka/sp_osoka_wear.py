# «Осока» (ПЗРК), этап 2 — износ (навык weapon-asset-wear) в Substance Painter через мост, поверх принятой заводской
# отделки v1 («Этап 1 — заводская отделка» не меняется; износ — группа «Этап 2 — износ» над ней, выключается целиком).
# Подход — рекомендации для ИЗЛОМ-45 (wpn_smg_03, 05.11) и ответ владельца: «Сделаем всё, но не пихай все везде, нужно
# сделать аккуратно и дозированно. Очень нужны вариации base color, добавь и теплого и холодного, светлого и темного».
# Места и причины — tools/osoka/wear_zones.py (маски _asset_src/osoka/tex/wear/<набор>_<место>.png); рисунок кромок в
# местах «до металла» — генератор Metal Edge Wear, умноженный на маску места (общего износа кромок нет: у ИЗЛОМ-45 он
# сыпал крапом по всем рёбрам). Стёртое до алюминия — с узким тёмным ободком краски, тёмными рисками внутри и чуть
# ниже поверхности (рекомендация 4).
#
#   python -X utf8 tools/asset_kit/finish/sp_run.py -c "import sys; sys.path.insert(0, r'E:/Games/RING-godot/tools/osoka'); import sp_osoka_wear; print(sp_osoka_wear.build())"
#   → группа износа в наборах Tube и Launcher, метка _wear_done.txt, проект сохраняется как Osoka_wear_v1.spp
#   (ракета в запаянной трубе — без износа)
import os

import substance_painter.layerstack as L
import substance_painter.project as P
import substance_painter.textureset as TS

import sp_finish
import sp_lib
import sp_osoka
from sp_lib import CH, fill, mask_generator, mask_proc, only_meshes

GROUP = "Этап 2 — износ"
ZONES = sp_osoka.TEX + "/wear"
PROJECT = sp_osoka.TEX + "/sp/Osoka_wear_v1.spp"
SOFT = getattr(L.BlendingMode, "SoftLight", L.BlendingMode.Overlay)
TUBE_OLIVE = (0.30, 0.32, 0.21)    # основа EN-ODT-MAT (стёртый трафарет открывает её)
ALU = ((0.66, 0.66, 0.65), 0.36, 1.0)       # литьё под краской стёрто до алюминия
ALU_DARK = (0.40, 0.40, 0.39)               # тёмные риски внутри стёртого
RIM = (0.14, 0.14, 0.11)                     # тёмный ободок вокруг стёртого (край краски, грязь)
DUST = (0.50, 0.48, 0.43)                    # городская пыль
SOIL = (0.36, 0.30, 0.22)                    # земля
GRIME = (0.17, 0.16, 0.13)                   # грязь кольцом у крепежа
GRUNGE_TILES = 40                            # гранж генераторов: плиток на сцену (~43 мм)
SCR = {"invert": 0, "balance": 0.36, "contrast": 0.55}


def soft(f):
    """Цвет слоя SoftLight по множителю f (на канал). Painter смешивает в линейном пространстве: на тёмной оливе
    (~0.07) SoftLight почти равен умножению на 2·b, нейтраль — линейные 0.5 (sRGB 0.735). Цвета «на глаз» в sRGB
    0.6–0.7 темнили (проба v1: «тёплые светлые» пятна темнее на 3 %), поэтому тон задаётся множителем: 1.2 — на 20 %
    светлее, 0.85 — на 15 % темнее; fill() переводит sRGB в линейное."""
    def srgb(c):
        c = min(max(c, 0.0), 1.0)
        return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055
    return tuple(srgb(c / 2.0) for c in f)


def _set_params(src, params):
    have = src.get_parameters()
    src.set_parameters({k: v for k, v in params.items() if k in have})


def _new_group(setname):
    """Группа «Этап 2 — износ» заново поверх заводской; Passthrough по всем каналам (урок AR-15 30.10)."""
    st = sp_lib.stack_by_name(setname)
    for n in L.get_root_layer_nodes(st):
        if n.get_name() == GROUP:
            L.delete_node(n)
    grp = L.insert_group(L.InsertPosition.from_textureset_stack(st))
    grp.set_name(GROUP)
    for ch in st.all_channels():
        grp.set_blending_mode(L.BlendingMode.Passthrough, ch)
    return L.InsertPosition.inside_node(grp, L.NodeStack.Substack)


def _last_mask(layer):
    eff = layer.mask_effects()
    return eff[0] if eff else None


def _zone(layer, setname, name, blend=None, opacity=1.0):
    """Маска места (wear_zones.py) в маске слоя: первой — как есть, поверх — режимом blend. Нет файла — False."""
    path = f"{ZONES}/{setname}_{name}.png"
    if not os.path.exists(path):
        return False
    sp_lib.mask_black(layer)
    top = _last_mask(layer)
    pos = L.InsertPosition.above_node(top) if top else L.InsertPosition.inside_node(layer, L.NodeStack.Mask)
    m = L.insert_fill(pos)
    m.set_source(None, sp_finish._bitmap(path))
    m.set_projection_mode(L.ProjectionMode.UV)
    if blend is not None:
        m.set_blending_mode(blend)
    m.set_opacity(opacity)
    return True


def _mew(layer, level, contrast=0.85, hard=True, blend=None):
    """Metal Edge Wear (гранж трёхпроекционно — без швов развёртки), при hard — жёсткой маской (металличность
    без полутонов)."""
    g = mask_generator(layer, "mg_metal_edge_wear/mg_metal_edge_wear", above=_last_mask(layer))
    _set_params(g.get_source(), {"Use_Triplanar": 1, "Wear_Level": level, "Wear_Contrast": contrast,
                                 "Grunge_Amount": 0.7, "grunge_scale": GRUNGE_TILES, "Ambient_Occlusion_Masking": 0.6})
    if blend is not None:
        g.set_blending_mode(blend)
    if hard:
        sp_finish._mfilter(g, "histogram_scan", {"Position": 0.5, "Contrast": 0.9})
    return g


def _tint(add, setname, name, factor, op, label):
    """Тон пятном: SoftLight — сохраняет заводскую неровность распыла и зерно, меняет светлоту и оттенок (множитель)."""
    lay = add(label, color=soft(factor))
    lay.set_blending_mode(SOFT, CH.BaseColor)
    if not _zone(lay, setname, name):
        return None
    sp_lib.lop(lay, op)
    return lay


def _prints(add, setname, name, op, label):
    """Жир (кожа, ладонь, отпечатки): чуть темнее и глаже — Multiply цвета, Subtract шероховатости."""
    lay = add(label, color=(0.90, 0.90, 0.89), rough=0.18)
    lay.set_blending_mode(L.BlendingMode.Multiply, CH.BaseColor)
    lay.set_blending_mode(L.BlendingMode.Subtract, CH.SpecularRoughness)
    _zone(lay, setname, name)
    sp_lib.lop(lay, op)
    return lay


def _polish(add, setname, name, rough, light, op, label):
    """Заполировано контактом: глаже и чуть светлее (краска вытерта до блеска, не до металла); light — множитель."""
    lay = add(label, color=soft(light), rough=rough)
    lay.set_blending_mode(SOFT, CH.BaseColor)
    _zone(lay, setname, name)
    sp_lib.lop(lay, op)
    return lay


def _bare(add, setname, name, level, label, meshes=None, metal=ALU):
    """Стёрто до алюминия в месте name: ободок краски (генератор чуть шире минус сам след), металл (чуть ниже
    поверхности), тёмные риски внутри по трению."""
    col, rough, met = metal
    rim = add(f"{label} — ободок", color=RIM, rough=0.8)
    _mew(rim, min(level + 0.12, 0.95), hard=False)
    _zone(rim, setname, name, L.BlendingMode.Multiply)
    # фильтр над генератором в маске обработал бы всё, что под ним, — у вычитаемого генератора фильтра нет
    _mew(rim, level, hard=False, blend=L.BlendingMode.Subtract)
    sp_lib.lop(rim, 0.55)
    lay = add(label, color=col, rough=rough, metal=met, height=0.4975)
    _mew(lay, level)
    _zone(lay, setname, name, L.BlendingMode.Multiply)
    sc = add(f"{label} — риски внутри", color=ALU_DARK, rough=0.5, metal=1.0)
    _mew(sc, level)
    _zone(sc, setname, name, L.BlendingMode.Multiply)
    mf = mask_proc(sc, "grunge_scratches_fine/grunge_scratches_fine", SCR, scale=sp_osoka._json("scene.json")["size_mm"]
                   / 30.0, blend=L.BlendingMode.Multiply, above=_last_mask(sc))
    sp_lib.lop(sc, 0.6)
    for n in (rim, lay, sc):
        if meshes:
            only_meshes(n, meshes)
    return lay


def _meshes(setname):
    """Сетки набора по слотам (meshes.json)."""
    return {sid: rec["meshes"] for sid, rec in sp_osoka._json("meshes.json").get(setname, {}).items()}


def build_set(setname, scene):
    ms = _meshes(setname)
    painted = ms.get("tube", []) + ms.get("cast", [])
    if not painted:
        return f"{setname}: нет крашеных слотов"
    pos = _new_group(setname)
    st = {"last": None}

    def add(name, **ch):
        lay = fill(name, L.InsertPosition.above_node(st["last"]) if st["last"] else pos, **ch)
        st["last"] = lay
        return lay

    log = []
    # 0. трафарет местами стёрт (открыта олива трубы) и в грязи — первым, чтобы тон ложился и на краску
    if setname == "Tube":
        lay = add("трафарет — стёрто местами", color=TUBE_OLIVE)
        _zone(lay, setname, "stencil_rub")
        sp_lib.lop(lay, 0.85)
        lay = add("трафарет — краска в грязи, серее", color=(0.78, 0.77, 0.72))
        lay.set_blending_mode(L.BlendingMode.Multiply, CH.BaseColor)
        _zone(lay, setname, "stencil_dirt")
        sp_lib.lop(lay, 0.8)
        log.append("трафарет")

    # 1. тон: выгорело сверху, низ темнее и холоднее, пятна четырёх оттенков, партии краски у деталей
    for name, color, op, label in (
            ("sun", (1.32, 1.25, 1.06), 0.6, "тон — выгорело сверху (светлее, теплее)"),
            ("low", (0.84, 0.89, 0.95), 0.6, "тон — снизу темнее, холоднее"),
            ("warm_light", (1.26, 1.18, 1.0), 0.5, "тон — пятна тёплые светлые"),
            ("warm_dark", (0.86, 0.79, 0.70), 0.45, "тон — пятна тёплые тёмные (бурые)"),
            ("cool_light", (1.12, 1.17, 1.23), 0.45, "тон — пятна холодные светлые (серые)"),
            ("cool_dark", (0.82, 0.87, 0.90), 0.4, "тон — пятна холодные тёмные"),
            ("part_a", (1.16, 1.12, 1.02), 0.55, "партии краски — светлее, теплее"),
            ("part_b", (0.87, 0.92, 0.95), 0.55, "партии краски — темнее, холоднее")):
        if _tint(add, setname, name, color, op, label):
            only_meshes(st["last"], painted)
    lay = add("блеск — разводы протирки", rough=0.42)
    _zone(lay, setname, "wipe")
    sp_lib.lop(lay, 0.5)
    only_meshes(lay, painted)
    log.append("тон и блеск")

    # 2. пыль: в углублениях (Dirt) и пятнами на верхних плоскостях — без металличности
    dusty = painted + ms.get("rubber", []) + ms.get("plastic", []) + ms.get("plate", []) + ms.get("steel_dark", [])
    # углы и щели — маска по AO (wear_zones: cavity); генератор Dirt заливал целиком затенённые детали (проба v1)
    lay = add("пыль в углах и щелях", color=DUST, rough=0.92)
    _zone(lay, setname, "cavity")
    sp_lib.lop(lay, 0.5)
    only_meshes(lay, [m for m in dusty if m not in ms.get("rubber", [])])
    # на чёрной резине та же пыль читалась серыми пятнами — слабее
    if ms.get("rubber"):
        lay = add("пыль в углах — резина", color=DUST, rough=0.92)
        _zone(lay, setname, "cavity")
        sp_lib.lop(lay, 0.22)
        only_meshes(lay, ms["rubber"])
    # на чёрной резине пыль пятнами читалась серыми кляксами (шар гнезда, крышки) — только крашеное
    lay = add("пыль на верхних плоскостях", color=DUST, rough=0.88)
    _zone(lay, setname, "dust")
    sp_lib.lop(lay, 0.2)
    only_meshes(lay, painted)
    log.append("пыль")

    if setname == "Tube":
        rub = ms.get("rubber", [])
        tube = ms.get("tube", [])
        _polish(add, setname, "shoulder", 0.42, (1.14, 1.13, 1.08), 0.75, "плечо — заполировано")
        lay = add("плечо — риски вдоль", color=(0.52, 0.53, 0.44), rough=0.5)
        _zone(lay, setname, "shoulder_scuff")
        sp_lib.lop(lay, 0.5)
        _prints(add, setname, "cheek", 0.6, "щека — жир кожи")
        _polish(add, setname, "sling", 0.45, (1.12, 1.11, 1.06), 0.6, "ремень — полоса глаже и светлее")
        _polish(add, setname, "hand_left", 0.45, (1.15, 1.13, 1.06), 0.7, "левая рука — источник питания глаже")
        _prints(add, setname, "hand_prints", 0.5, "левая рука — отпечатки и разводы")
        lay = add("источник — потёртости захода", color=(0.50, 0.50, 0.47), rough=0.42, metal=1.0)
        _zone(lay, setname, "power_rub")
        sp_finish._mfilter(_last_mask(lay), "histogram_scan", {"Position": 0.55, "Contrast": 0.8})
        # кладут на правый бок, ставят на задний торец: резина — светлые ссадины, металл обойм — до алюминия
        for name, label in (("ground", "правый бок о землю"), ("rear_end", "задний торец о землю")):
            lay = add(f"{label} — резина", color=(0.22, 0.22, 0.21), rough=0.78)
            _zone(lay, setname, name)
            sp_lib.lop(lay, 0.35)
            only_meshes(lay, rub)
            _bare(add, setname, name, 0.55, f"{label} — металл", meshes=tube)
        lay = add("земля внизу справа", color=SOIL, rough=0.92)
        _zone(lay, setname, "soil")
        sp_lib.lop(lay, 0.5)
        only_meshes(lay, tube + ms.get("cast", []))
        lay = add("земля внизу справа — резина", color=SOIL, rough=0.92)
        _zone(lay, setname, "soil")
        sp_lib.lop(lay, 0.15)
        only_meshes(lay, rub)
        sl = ms.get("sling", [])
        lay = add("ремень — засален, в грязи", color=(0.72, 0.70, 0.64), rough=0.12)
        lay.set_blending_mode(L.BlendingMode.Multiply, CH.BaseColor)
        lay.set_blending_mode(L.BlendingMode.Subtract, CH.SpecularRoughness)
        _zone(lay, setname, "sling_grime")
        sp_lib.lop(lay, 0.75)
        only_meshes(lay, sl)
        lay = add("ремень — ворс на кромках", color=soft((1.2, 1.2, 1.18)))
        lay.set_blending_mode(SOFT, CH.BaseColor)
        _mew(lay, 0.35, hard=False)
        sp_lib.lop(lay, 0.45)
        only_meshes(lay, sl)
        lay = add("акценты — царапина и ссадина", color=(0.50, 0.51, 0.43), rough=0.58, height=0.4985)
        _zone(lay, setname, "accent")
        sp_finish._mfilter(_last_mask(lay), "histogram_scan", {"Position": 0.45, "Contrast": 0.7})
        log.append("места трубы")

    if setname == "Launcher":
        _polish(add, setname, "grip", 0.42, (1.16, 1.14, 1.06), 0.75, "рукоять — от ладони глаже и светлее")
        _prints(add, setname, "grip_prints", 0.6, "рукоять — отпечатки пальцев")
        _bare(add, setname, "grip_butt", 0.5, "низ рукояти о землю")
        _bare(add, setname, "lever_tip", 0.55, "головка рычага под пальцем")
        _polish(add, setname, "lever_tip", 0.4, (1.15, 1.13, 1.06), 0.6, "головка рычага — заполировано")
        # краска процарапана головкой рычага, не до металла (проба v1: металлом — белые дуги)
        lay = add("бороздки по ходу рычага", color=(0.40, 0.41, 0.36), rough=0.5)
        _zone(lay, setname, "arcs")
        sp_lib.lop(lay, 0.55)
        lay = add("кнопка — центр заполирован", rough=0.45)
        _zone(lay, setname, "button")
        lay = add("грязь кольцом у кнопки", color=GRIME, rough=0.92)
        _zone(lay, setname, "button_ring")
        sp_lib.lop(lay, 0.6)
        _bare(add, setname, "latches", 0.55, "концы защёлок короба")
        _bare(add, setname, "box_bottom", 0.5, "низ короба о землю")
        lay = add("земля на дне короба", color=SOIL, rough=0.92)
        _zone(lay, setname, "box_soil")
        sp_lib.lop(lay, 0.6)
        _bare(add, setname, "ground", 0.55, "правый бок о землю")
        _bare(add, setname, "lids", 0.42, "кромки крышек")
        lay = add("щитки прицела — верх потёрт", color=(0.24, 0.24, 0.23), rough=0.45)
        _mew(lay, 0.5, hard=False)
        _zone(lay, setname, "leaves", L.BlendingMode.Multiply)
        only_meshes(lay, ms.get("plastic", []))
        _bare(add, setname, "dust_cover", 0.55, "край пылезащитной крышки")
        _polish(add, setname, "slider", 0.4, (1.14, 1.13, 1.08), 0.6, "ползунок и полоса по ходу")
        lay = add("грязь кольцом у крепежа", color=GRIME, rough=0.92)
        _zone(lay, setname, "rings")
        sp_lib.lop(lay, 0.65)
        lay = add("следы отвёртки на шлицах", color=(0.62, 0.62, 0.61), rough=0.3, metal=1.0)
        _zone(lay, setname, "tool")
        sp_finish._mfilter(_last_mask(lay), "histogram_scan", {"Position": 0.5, "Contrast": 0.85})
        lay = add("масло у осей", color=(0.62, 0.62, 0.60), rough=0.28)
        lay.set_blending_mode(L.BlendingMode.Multiply, CH.BaseColor)
        _zone(lay, setname, "oil")
        sp_lib.lop(lay, 0.6)
        lay = add("грязь по краю таблички", color=GRIME, rough=0.9)
        _zone(lay, setname, "plate_edge")
        sp_lib.lop(lay, 0.6)
        lay = add("акцент — скол и царапина на коробе", color=ALU[0], rough=ALU[1], metal=1.0, height=0.4975)
        _zone(lay, setname, "accent")
        sp_finish._mfilter(_last_mask(lay), "histogram_scan", {"Position": 0.5, "Contrast": 0.8})
        log.append("места механизма")
    return f"{setname}: " + ", ".join(log)


def build(only=("Tube", "Launcher")):
    """Группа износа в наборах; итог — _wear_done.txt, проект сохраняется копией Osoka_wear_v1.spp."""
    scene = sp_osoka._json("scene.json")["size_mm"]
    log = []
    for t in TS.all_texture_sets():
        if t.name() in only:
            log.append(build_set(t.name(), scene))

    def done():
        sp_finish.save_as(PROJECT)
        return " | ".join(log)
    sp_lib.when_idle(done, "_wear_done.txt")
    return " | ".join(log)
