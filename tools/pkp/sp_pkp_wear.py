# «Частокол», текстуры этап 2 — износ в Substance Painter поверх принятой заводской отделки (sp_pkp.py, группа
# «Этап 1 — заводская отделка» не меняется). Износ — группа «Этап 2 — износ» над ней в каждом наборе (Passthrough,
# выключается целиком), слой на вид следа: цвет / блеск / металл заливкой, рисунок — умная маска владельца
# (E:/Models Blender/Маски_АЛЬФА/smart masks — только они, владелец 2026-11-14), место — сетки слотов этого класса.
# Заливки внутри умных масок переводятся с развёртки на трёхпроекционную укладку (у high-poly тысячи островов: по
# развёртке рисунок рвался бы на швах) с плиткой в миллиметрах. Степень — как на образцах владельца refs/owner/01–06
# (интервью — finish-spec.json, раздел wear).
#   … -c "import sys; sys.path.insert(0, r'E:/Games/RING-godot/tools/pkp'); import sp_pkp, sp_pkp_wear; print(sp_pkp_wear.build())"
#   → _wear_done.txt (проект сохраняется); выгрузка — sp_pkp.export(<папка>)
import json
import os

import substance_painter.layerstack as L
import substance_painter.project as P
import substance_painter.resource as R
import substance_painter.textureset as TS

import sp_finish
import sp_pkp
import tex_sets as T

MASKS_DIR = r"E:/Models Blender/Маски_АЛЬФА/smart masks"
GROUP = "Этап 2 — износ"
TILE_MM = 400.0            # плитка развёртки 0…1 в умной маске ≈ 400 мм предмета (масштаб авторов масок — оценка)
_cache = {}
FINE_ONLY = ("curvature_soft", "curvature_medium", "curvature_large", "curvature_big", "curvature_huge", "global_blur",
             "Edges_Smoothness", "Curvature_Smoothness")
CAP = {"ao_blur": 0.5}

# класс износа слота (finish-spec.json → slots[].id)
CLASS = {"receiver": "steel", "barrel": "steel", "sight": "steel", "bipod": "steel", "small": "steel",
         "rail_screws": "steel", "bolt": "bolt", "stock": "plastic", "grip": "plastic", "box": "paint",
         "strap": "fabric", "links": "links", "case": "case", "bullet": "bullet", "rail": "alu"}
# засаленные следы пальцев — места хвата (интервью: рукоятка, рукоятка перезаряжания, защёлка крышки, ручка переноски,
# флажок предохранителя)
GREASE = ["Pistol_Grip", "Charging_Handle", "Cover_Latch", "Carry_Handle", "Safety_Lever"]

# слои по классу снизу вверх: (имя, умная маска или None, каналы заливки, непрозрачность, место по форме, порог
# [, {"blend": "multiply"}])
# Место — карты tools/pkp/wear_place.py (кривизна в 1/мм: «edge» — скругления меньше ~1 мм, «edge_wide» — до ~20 мм
# (краска коробок), «cavity» — вогнутые и затенённые места), рисунок — умная маска владельца, произведение. Порог (Histogram Scan, Position) — только где
# следов надо меньше рисунка; None — без порога (мягкий переход). Степень — образцы 01–06: тёмная сталь, тонкие
# светлые кромки, редкие слабые царапины, пыль в углах; первая проба 14.11 (серебро по всем скруглениям, светлые
# пятна пыли по плоскостям) отвергнута.
RECIPES = {
    "steel": [
        # v02 (сверка с образцами 02, 06): вытертое пятнами воронение на открытых плоскостях, чёрный нагар в швах,
        # кромка — сплошной светлой линией под рисунком, вытертые до блеска верхушки заклёпок и винтов
        # отлив воронения (владелец 2026-11-14: «небольшие тональности других цветов», как у АСТЕН-919): крупные мягкие
        # пятна синевы и тёплого сливово-коричневого в цвете основы — на металле это цвет отражения, под разным светом
        # сталь чуть уходит в синеву или в тепло; блеск и металл не трогаются
        ("отлив воронения — синева", "dirt variation", dict(color=(0.18, 0.215, 0.28)), 0.7, None, None),
        ("отлив воронения — тёплый", "dirt roughness", dict(color=(0.26, 0.21, 0.21)), 0.55, None, None),
        ("вытертое воронение пятнами", "stain roughness", dict(color=(0.33, 0.34, 0.35), rough=0.42, metal=0.9), 0.45,
         "open", None),
        ("грязь в самых глубоких углах", "cavity dirt strong", dict(color=(0.05, 0.047, 0.042), rough=0.7, metal=0.1), 0.8,
         "deep", None),
        ("пыль в углах и швах", "cavity dirt", dict(color=(0.24, 0.23, 0.21), rough=0.85, metal=0.0), 0.45, "cavity", None),
        ("царапины", "micro scratches", dict(color=(0.36, 0.37, 0.38), rough=0.3, metal=1.0), 0.5, None, 0.97),
        ("кромки вытерты до стали", "gun scratch edge", dict(color=(0.62, 0.63, 0.64), rough=0.24, metal=1.0), 1.0,
         "edge", None),
        ("кромки — сколы до металла", "edge damage", dict(color=(0.58, 0.59, 0.60), rough=0.26, metal=1.0), 0.8,
         "edge", None),
        ("верхушки заклёпок и винтов", None, dict(color=(0.60, 0.61, 0.62), rough=0.22, metal=1.0), 0.8, "tops", None),
    ],
    "bolt": [
        ("грязь в самых глубоких углах", "cavity dirt strong", dict(color=(0.05, 0.047, 0.042), rough=0.7, metal=0.1), 0.8,
         "deep", None),
        ("масло и нагар в углах", "AO dirt", dict(color=(0.10, 0.09, 0.08), rough=0.4, metal=0.5), 0.7, "cavity", None),
        ("кромки заполированы трением", "gun scratch edge", dict(color=(0.80, 0.81, 0.82), rough=0.18, metal=1.0), 0.6,
         "edge", None),
        ("царапины", "micro scratches", dict(color=(0.70, 0.71, 0.72), rough=0.22, metal=1.0), 0.5, None, 0.97),
    ],
    "plastic": [
        ("грязь в самых глубоких углах", "cavity dirt strong", dict(color=(0.05, 0.047, 0.042), rough=0.7, metal=0.1), 0.8,
         "deep", None),
        ("пыль в углах и насечке", "cavity dirt", dict(color=(0.20, 0.19, 0.18), rough=0.85, metal=0.0), 0.4, "cavity", None),
        ("царапины", "micro scratches", dict(color=(0.12, 0.12, 0.12), rough=0.45, metal=0.0), 0.3, None, 0.95),
        ("потёртые кромки", "gun scratch edge", dict(color=(0.10, 0.10, 0.10), rough=0.45, metal=0.0), 0.6, "edge", None),
    ],
    "paint": [
        ("грязь в самых глубоких углах", "cavity dirt strong", dict(color=(0.05, 0.047, 0.042), rough=0.7, metal=0.1), 0.8,
         "deep", None),
        # v02: эмаль потемнела от грязи (образцы 02, 03: оливковая темнее и гуще; цвет эмали этапа 1 не меняется —
        # умножение поверх), грязь копится снизу
        ("эмаль потемнела от грязи", "dirt variation", dict(color=(0.55, 0.62, 0.45)), 1.0, None, None,
         {"blend": "multiply"}),
        ("грязь снизу", "dirt", dict(color=(0.10, 0.10, 0.06), rough=0.8, metal=0.0), 0.7, "low", None),
        ("грязь пятнами", "dirt", dict(color=(0.13, 0.13, 0.08), rough=0.8, metal=0.0), 0.5, None, None),
        ("пыль в углах", "cavity dirt", dict(color=(0.30, 0.28, 0.22), rough=0.85, metal=0.0), 0.6, "cavity", None),
        ("сколы до грунта", "hard damage", dict(color=(0.30, 0.12, 0.08), rough=0.72, metal=0.0), 0.85, "edge_wide", None),
        ("кромки до металла", "edge damage", dict(color=(0.55, 0.56, 0.57), rough=0.35, metal=1.0), 0.85, "edge_wide", None),
        ("царапины до металла", "micro scratches", dict(color=(0.50, 0.51, 0.52), rough=0.35, metal=1.0), 0.6, None, 0.97),
    ],
    "fabric": [
        ("грязь, засаленность", "dirt fabric", dict(color=(0.20, 0.17, 0.12), rough=0.9, metal=0.0), 0.6, None, None),
    ],
    "links": [
        ("грязь в самых глубоких углах", "cavity dirt strong", dict(color=(0.05, 0.047, 0.042), rough=0.7, metal=0.1), 0.8,
         "deep", None),
        ("пыль в углах", "cavity dirt", dict(color=(0.24, 0.23, 0.21), rough=0.85, metal=0.0), 0.6, "cavity", None),
        ("кромки вытерты до стали", "gun scratch edge", dict(color=(0.45, 0.46, 0.47), rough=0.3, metal=1.0), 0.7,
         "edge", None),
    ],
    "case": [
        ("потемнения", "dirt", dict(color=(0.16, 0.15, 0.10), rough=0.55, metal=0.5), 0.35, None, None),
        ("лак затёрт до стали", "micro damages", dict(color=(0.52, 0.52, 0.50), rough=0.35, metal=1.0), 0.8, "edge", None),
    ],
    "bullet": [
        ("потемнения томпака", "dirt", dict(color=(0.42, 0.24, 0.15), rough=0.45, metal=1.0), 0.4, None, None),
    ],
    "alu": [
        ("грязь в самых глубоких углах", "cavity dirt strong", dict(color=(0.05, 0.047, 0.042), rough=0.7, metal=0.1), 0.8,
         "deep", None),
        ("пыль в углах", "cavity dirt", dict(color=(0.24, 0.23, 0.21), rough=0.85, metal=0.0), 0.6, "cavity", None),
        ("кромки до алюминия", "gun scratch edge", dict(color=(0.75, 0.75, 0.77), rough=0.3, metal=1.0), 0.85,
         "edge", None),
    ],
}
# рукоятка перезаряжания (владелец 14.11: чёрная сталь, «на износе краска немного сошла» — до светлой стали)
HANDLE = ["Charging_Handle"]
HANDLE_RECIPE = [
    ("вытерта до светлой стали", "gun scratch edge", dict(color=(0.64, 0.65, 0.66), rough=0.24, metal=1.0), 0.9,
     "edge", None),
]
GREASE_POS = 0.75         # шире: при 0,5 отпечатков почти не оставалось (владелец к v03: «не вижу вообще отпечатков»)
# отпечатки и пятна по материалу: на глянцевом пластике след пальца — матовая светлая дымка, на металле — жирный блеск
PRINT = {
    "plastic": dict(color=(0.11, 0.11, 0.11), rough=0.5, color_op=0.45, rough_op=0.8, stain_rough=0.42, stain_op=0.5),
    "metal": dict(color=(0.6, 0.6, 0.6), rough=0.1, color_op=0.3, rough_op=0.85, stain_rough=0.15, stain_op=0.6),
}
PLASTIC_PARTS = {"Pistol_Grip", "Stock"}
# группа кистью владельца — над износом, скриптом не пересобирается (build() её не трогает)
HAND_GROUP = "Этап 2 — кистью (владелец)"
# особые места по деталям (владелец 2026-11-14, к износу v02): (детали, имя, умная маска, каналы, непрозрачность,
# место wear_place.py, порог). Детали — объекты формы; слой ложится на их сетки в наборе, место — карта набора.
SPECIAL = [
    # 2 — пятки сошек, где касаются земли
    ({"Bipod_Foot_L", "Bipod_Foot_R"}, "земля на пятках сошек", "dirt variation",
     dict(color=(0.20, 0.16, 0.11), rough=0.92, metal=0.0), 0.9, "feet", None),
    # 3 — задняя кромка крышки: владелец рисует кистью сам (группа HAND_GROUP; процедурный вариант v03 «как
    # трафаретом» — отвергнут)
    # 5 — вдоль хода рукоятки перезаряжания
    ({"Receiver"}, "царапины вдоль хода рукоятки перезаряжания", "gun scratch edge",
     dict(color=(0.60, 0.61, 0.62), rough=0.25, metal=1.0), 0.85, "charge_path", None),
    # 6 — низ коробки для ленты и соседние рёбра и углы
    ({"Box100_Body", "Box200_Body"}, "низ коробки — сколы", "hard damage",
     dict(color=(0.48, 0.49, 0.50), rough=0.4, metal=1.0), 0.95, "box_bottom", None),
    ({"Box100_Body", "Box200_Body"}, "низ коробки — сильные царапины", "gun scratch storng",
     dict(color=(0.55, 0.56, 0.57), rough=0.35, metal=1.0), 0.9, "box_bottom", None),
]
# 4 — хват (рукоятка, цевьё, спуск, рукоятка перезаряжания, сошки, ручка переноски, верх приклада; защёлка крышки
# и флажок предохранителя — из интервью): отпечатки «finger print» и пятна блеска «stain roughness», место «touch»
TOUCH = ["Pistol_Grip", "Rail_Forend", "Trigger", "Charging_Handle", "Bipod_Yoke", "Bipod_Leg_L", "Bipod_Leg_R",
         "Carry_Handle", "Stock", "Cover_Latch", "Safety_Lever"]
WEAR_DIR = "E:/Games/RING-godot/_asset_src/pkp/tex/wear"


def smart_mask(name):
    """Умная маска владельца ресурсом проекта (по имени папки)."""
    if name in _cache:
        return _cache[name]
    d = os.path.join(MASKS_DIR, name)
    f = [x for x in os.listdir(d) if x.endswith(".spmsk")][0]
    res = R.import_project_resource(os.path.join(d, f), R.Usage.SMART_MASK, name="pkp_" + name.replace(" ", "_"))
    _cache[name] = res.identifier()
    return _cache[name]


def _group(set_name):
    """Группа износа над заводской в наборе (прежняя удаляется)."""
    import sp_lib
    st = sp_lib.stack_by_name(set_name)
    for n in L.get_root_layer_nodes(st):
        if n.get_name() == GROUP:          # группу кисти владельца (HAND_GROUP) не трогать
            L.delete_node(n)
    top = [n for n in L.get_root_layer_nodes(st) if n.get_name() == sp_finish.GROUP][0]
    g = L.insert_group(L.InsertPosition.above_node(top))
    g.set_name(GROUP)
    for ch in st.all_channels():
        g.set_blending_mode(L.BlendingMode.Passthrough, ch)
    return g


def to_triplanar(layer, scene_mm, tile_mm=TILE_MM):
    """Заливки и генераторы внутри маски слоя — с развёртки на трёхпроекционную укладку: плитка развёртки умной маски
    (масштаб s) → s · сцена / tile_mm плиток на сцену (Painter считает трёхпроекционные плитки на габарит сцены)."""
    n = 0
    for e in layer.mask_effects():
        kind = type(e).__name__
        if kind == "FillEffectNode":
            try:
                if e.get_projection_mode() != L.ProjectionMode.UV:
                    continue
                p = e.get_projection_parameters()
                s = p.uv_transformation.scale[0]
                rot = p.uv_transformation.rotation
                e.set_projection_mode(L.ProjectionMode.Triplanar)
                q = e.get_projection_parameters()
                q.hardness = 0.5
                q.uv_transformation.scale_mode = L.ScaleMode.Factors
                k = s * scene_mm / tile_mm
                q.uv_transformation.scale = [k, k]
                q.uv_transformation.rotation = rot
                e.set_projection_parameters(q)
                n += 1
            except Exception:      # noqa: BLE001
                pass
        elif kind == "GeneratorEffectNode":
            try:
                src = e.get_source()
                pr = src.get_parameters()
                upd = {k: 1 for k in ("Use_Triplanar", "texture_triplanar", "triplanar") if k in pr}
                # только мелкий масштаб кривизны и без размытия: крупные масштабы размываются по развёртке, а у
                # high-poly тысячи островов — белые полосы ложились по плоскостям (кромки закрывали 57 % поверхности)
                upd.update({k: 0.0 for k in FINE_ONLY if k in pr})
                for k, v in CAP.items():
                    if k in pr and pr[k] > v:
                        upd[k] = v
                if upd:
                    src.set_parameters(upd)
                    n += 1
            except Exception:      # noqa: BLE001
                pass
    return n


def scan(layer, position, contrast=0.6):
    """Порог поверх всей маски слоя (Histogram Scan над верхним эффектом): у масок авторов своя плотность на нашей
    сетке (кромки закрывали 57 % поверхности, пыль 81 %, царапины 0,1 %) — доля следа подбирается порогом."""
    import sp_lib
    e = L.insert_filter_effect(L.InsertPosition.inside_node(layer, L.NodeStack.Mask),      # вершина стека маски
                               sp_lib.rid("histogram_scan/histogram_scan", "u:filter"))
    e.get_source().set_parameters({"Position": position, "Contrast": contrast})
    return e


def place(layer, kind, set_name):
    """Место следа поверх рисунка маски — карта развёртки tools/pkp/wear_place.py (<набор>_<kind>.png), умножением.
    (Генератор кривизны Painter меряет в пикселях развёртки: на этой форме считал кромкой все скругления — оси, спуск
    и предохранитель выходили серебряными целиком.)"""
    m = L.insert_fill(L.InsertPosition.inside_node(layer, L.NodeStack.Mask))
    m.set_source(None, sp_finish._bitmap(f"{WEAR_DIR}/{set_name}_{kind}.png"))
    m.set_projection_mode(L.ProjectionMode.UV)
    m.set_blending_mode(L.BlendingMode.Multiply)
    return m


def wear_layer(group, name, mask_name, ch, opacity, meshes, scene_mm, position=None, where=None, set_name=None,
               blend=None):
    """Слой следа: заливка каналов ch по маске. mask_name — умная маска владельца (рисунок) × место where;
    None — только место (карта wear_place.py, сплошь: линия кромки, верхушки). blend «multiply» — цвет умножением
    (потемнение отделки, не новый цвет)."""
    import sp_lib
    lay = sp_lib.fill(name, L.InsertPosition.inside_node(group, L.NodeStack.Substack), **ch)
    sp_lib.only_meshes(lay, meshes)
    for c in (sp_lib.CH.BaseColor, sp_lib.CH.SpecularRoughness, sp_lib.CH.Metallic):
        try:
            lay.set_opacity(opacity, c)
        except Exception:      # noqa: BLE001
            pass
    if blend == "multiply":
        lay.set_blending_mode(L.BlendingMode.Multiply, sp_lib.CH.BaseColor)
    lay.add_mask(L.MaskBackground.Black)
    if mask_name is None:
        sp_finish.bitmap_mask(lay, f"{WEAR_DIR}/{set_name}_{where}.png")
        return lay
    L.insert_smart_mask(L.InsertPosition.inside_node(lay, L.NodeStack.Mask), smart_mask(mask_name))
    to_triplanar(lay, scene_mm)
    if where:
        place(lay, where, set_name)
    if position is not None:
        scan(lay, position)
    return lay


def touch_layers(group, meshes_by_kind, scene_mm, set_name):
    """Хват: отпечатки («finger print») и пятна («stain roughness») по месту touch — по материалу (PRINT)."""
    import sp_lib
    for kind, meshes in meshes_by_kind.items():
        if not meshes:
            continue
        pr = PRINT[kind]
        lay = sp_lib.fill(f"отпечатки пальцев ({'пластик' if kind == 'plastic' else 'металл'})",
                          L.InsertPosition.inside_node(group, L.NodeStack.Substack), color=pr["color"], rough=pr["rough"])
        if kind == "metal":
            lay.set_blending_mode(L.BlendingMode.Multiply, sp_lib.CH.BaseColor)
        lay.set_opacity(pr["color_op"], sp_lib.CH.BaseColor)
        lay.set_opacity(pr["rough_op"], sp_lib.CH.SpecularRoughness)
        sp_lib.only_meshes(lay, meshes)
        lay.add_mask(L.MaskBackground.Black)
        L.insert_smart_mask(L.InsertPosition.inside_node(lay, L.NodeStack.Mask), smart_mask("finger print"))
        to_triplanar(lay, scene_mm)
        scan(lay, GREASE_POS)
        place(lay, "touch", set_name)
        st = sp_lib.fill(f"пятна от рук ({'пластик' if kind == 'plastic' else 'металл'})",
                         L.InsertPosition.inside_node(group, L.NodeStack.Substack), rough=pr["stain_rough"])
        st.set_opacity(pr["stain_op"], sp_lib.CH.SpecularRoughness)
        sp_lib.only_meshes(st, meshes)
        st.add_mask(L.MaskBackground.Black)
        L.insert_smart_mask(L.InsertPosition.inside_node(st, L.NodeStack.Mask), smart_mask("stain roughness"))
        to_triplanar(st, scene_mm)
        place(st, "touch", set_name)


def hand_group(set_name, title, ch):
    """Группа для кисти владельца над износом (если нет) и в ней слой: заливка ch, маска чёрная — рисовать белым."""
    import sp_lib
    st = sp_lib.stack_by_name(set_name)
    roots = L.get_root_layer_nodes(st)
    g = next((n for n in roots if n.get_name() == HAND_GROUP), None)
    if g is None:
        top = next(n for n in roots if n.get_name() == GROUP)
        g = L.insert_group(L.InsertPosition.above_node(top))
        g.set_name(HAND_GROUP)
        for c in st.all_channels():
            g.set_blending_mode(L.BlendingMode.Passthrough, c)
    for n in g.sub_layers():
        if n.get_name() == title:
            return n
    lay = sp_lib.fill(title, L.InsertPosition.inside_node(g, L.NodeStack.Substack), **ch)
    lay.add_mask(L.MaskBackground.Black)
    return lay


def build_set(set_name, meshes_json, spec, scene_mm):
    """Группа износа набора: слои по классам слотов, у каждого — сетки всех слотов класса в наборе."""
    by_class = {}
    for slot in spec["slots"]:
        cls = CLASS.get(slot["id"])
        if not cls:
            continue
        ms = [n for n, r in meshes_json.items() if r["set"] == set_name and sp_pkp._match(r, slot["parts"])]
        by_class.setdefault(cls, []).extend(ms)
    g = _group(set_name)
    log = []
    for cls, recipe in RECIPES.items():
        ms = sorted(set(by_class.get(cls, [])))
        if not ms:
            continue
        for r in recipe:
            name, mask, ch, op, where, pos = r[:6]
            ex = r[6] if len(r) > 6 else {}
            wear_layer(g, f"{cls} · {name}", mask, ch, op, ms, scene_mm, position=pos, where=where,
                       set_name=set_name, blend=ex.get("blend"))
        log.append(f"{cls}:{len(ms)}")
    hm = sorted(n for n, r in meshes_json.items() if r["set"] == set_name and r["obj"] in HANDLE)
    for name, mask, ch, op, where, pos in (HANDLE_RECIPE if hm else []):
        wear_layer(g, f"рукоятка · {name}", mask, ch, op, hm, scene_mm, position=pos, where=where, set_name=set_name)
    for objs, name, mask, ch, op, where, pos in SPECIAL:
        sm = sorted(n for n, r in meshes_json.items() if r["set"] == set_name and r["obj"] in objs)
        if sm:
            wear_layer(g, name, mask, ch, op, sm, scene_mm, position=pos, where=where, set_name=set_name)
            log.append(f"{where}:{len(sm)}")
    gm = {"plastic": sorted(n for n, r in meshes_json.items() if r["set"] == set_name and r["obj"] in TOUCH
                            and r["obj"] in PLASTIC_PARTS),
          "metal": sorted(n for n, r in meshes_json.items() if r["set"] == set_name and r["obj"] in TOUCH
                          and r["obj"] not in PLASTIC_PARTS)}
    if gm["plastic"] or gm["metal"]:
        touch_layers(g, gm, scene_mm, set_name)
        log.append(f"хват:{len(gm['plastic']) + len(gm['metal'])}")
    return f"{set_name}: " + " ".join(log)


def build(only=None):
    import sp_lib
    sp_pkp.check_open()
    proj = sp_pkp._proj()
    meshes = sp_pkp._json(os.path.splitext(sp_pkp.paths(proj)[0])[0] + "_meshes.json")
    spec = sp_pkp._json(sp_pkp.SPEC)
    scene = sp_pkp._scene()
    log = []
    for t in TS.all_texture_sets():
        if only and t.name() not in only:
            continue
        log.append(build_set(t.name(), meshes, spec, scene))

    def done():
        P.save()
        return " | ".join(log)
    sp_lib.when_idle(done, "_wear_done.txt")
    return " | ".join(log)


def show(on=True, only=None):
    """Включить / выключить группу износа (сравнение с заводской)."""
    import sp_lib
    for t in TS.all_texture_sets():
        if only and t.name() not in only:
            continue
        for n in L.get_root_layer_nodes(sp_lib.stack_by_name(t.name())):
            if n.get_name() == GROUP:
                n.set_visible(on)
    return "ok"
