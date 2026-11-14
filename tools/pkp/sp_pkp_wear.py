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

# слои по классу снизу вверх: (имя, умная маска, каналы заливки, непрозрачность, место по форме, порог)
# Место — карты tools/pkp/wear_place.py (кривизна в 1/мм: «edge» — скругления меньше ~1 мм, «edge_wide» — до ~20 мм
# (краска коробок), «cavity» — вогнутые и затенённые места), рисунок — умная маска владельца, произведение. Порог (Histogram Scan, Position) — только где
# следов надо меньше рисунка; None — без порога (мягкий переход). Степень — образцы 01–06: тёмная сталь, тонкие
# светлые кромки, редкие слабые царапины, пыль в углах; первая проба 14.11 (серебро по всем скруглениям, светлые
# пятна пыли по плоскостям) отвергнута.
RECIPES = {
    "steel": [
        ("пыль в углах и швах", "cavity dirt", dict(color=(0.24, 0.23, 0.21), rough=0.85, metal=0.0), 0.6, "cavity", None),
        ("царапины", "micro scratches", dict(color=(0.36, 0.37, 0.38), rough=0.3, metal=1.0), 0.5, None, 0.97),
        ("кромки вытерты до стали", "gun scratch edge", dict(color=(0.54, 0.55, 0.56), rough=0.27, metal=1.0), 1.0,
         "edge", None),
    ],
    "bolt": [
        ("масло и нагар в углах", "AO dirt", dict(color=(0.10, 0.09, 0.08), rough=0.4, metal=0.5), 0.7, "cavity", None),
        ("кромки заполированы трением", "gun scratch edge", dict(color=(0.80, 0.81, 0.82), rough=0.18, metal=1.0), 0.6,
         "edge", None),
        ("царапины", "micro scratches", dict(color=(0.70, 0.71, 0.72), rough=0.22, metal=1.0), 0.5, None, 0.97),
    ],
    "plastic": [
        ("пыль в углах и насечке", "cavity dirt", dict(color=(0.20, 0.19, 0.18), rough=0.85, metal=0.0), 0.4, "cavity", None),
        ("царапины", "micro scratches", dict(color=(0.12, 0.12, 0.12), rough=0.45, metal=0.0), 0.3, None, 0.95),
        ("потёртые кромки", "gun scratch edge", dict(color=(0.10, 0.10, 0.10), rough=0.45, metal=0.0), 0.6, "edge", None),
    ],
    "paint": [
        ("грязь пятнами", "dirt", dict(color=(0.13, 0.13, 0.08), rough=0.8, metal=0.0), 0.65, None, None),
        ("пыль в углах", "cavity dirt", dict(color=(0.30, 0.28, 0.22), rough=0.85, metal=0.0), 0.6, "cavity", None),
        ("сколы до грунта", "hard damage", dict(color=(0.30, 0.12, 0.08), rough=0.72, metal=0.0), 0.85, "edge_wide", None),
        ("кромки до металла", "edge damage", dict(color=(0.55, 0.56, 0.57), rough=0.35, metal=1.0), 0.9, "edge_wide", 0.3),
        ("царапины до металла", "micro scratches", dict(color=(0.50, 0.51, 0.52), rough=0.35, metal=1.0), 0.6, None, 0.97),
    ],
    "fabric": [
        ("грязь, засаленность", "dirt fabric", dict(color=(0.20, 0.17, 0.12), rough=0.9, metal=0.0), 0.6, None, None),
    ],
    "links": [
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
GREASE_POS = 0.5
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
        if n.get_name() == GROUP:
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


def wear_layer(group, name, mask_name, ch, opacity, meshes, scene_mm, position=None, where=None, set_name=None):
    import sp_lib
    lay = sp_lib.fill(name, L.InsertPosition.inside_node(group, L.NodeStack.Substack), **ch)
    sp_lib.only_meshes(lay, meshes)
    for c in (sp_lib.CH.BaseColor, sp_lib.CH.SpecularRoughness, sp_lib.CH.Metallic):
        try:
            lay.set_opacity(opacity, c)
        except Exception:      # noqa: BLE001
            pass
    lay.add_mask(L.MaskBackground.Black)
    L.insert_smart_mask(L.InsertPosition.inside_node(lay, L.NodeStack.Mask), smart_mask(mask_name))
    to_triplanar(lay, scene_mm)
    if where:
        place(lay, where, set_name)
    if position is not None:
        scan(lay, position)
    return lay


def grease_layer(group, meshes, scene_mm):
    """Засаленные следы пальцев: только блеск и чуть темнее, рисунок — «finger print»."""
    import sp_lib
    lay = sp_lib.fill("засаленные следы пальцев", L.InsertPosition.inside_node(group, L.NodeStack.Substack),
                      color=(0.5, 0.5, 0.5), rough=0.14)
    lay.set_blending_mode(L.BlendingMode.Multiply, sp_lib.CH.BaseColor)
    lay.set_opacity(0.25, sp_lib.CH.BaseColor)
    lay.set_blending_mode(L.BlendingMode.Subtract, sp_lib.CH.SpecularRoughness)
    sp_lib.only_meshes(lay, meshes)
    lay.add_mask(L.MaskBackground.Black)
    L.insert_smart_mask(L.InsertPosition.inside_node(lay, L.NodeStack.Mask), smart_mask("finger print"))
    to_triplanar(lay, scene_mm)
    scan(lay, GREASE_POS)
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
        for name, mask, ch, op, where, pos in recipe:
            wear_layer(g, f"{cls} · {name}", mask, ch, op, ms, scene_mm, position=pos, where=where,
                       set_name=set_name)
        log.append(f"{cls}:{len(ms)}")
    hm = sorted(n for n, r in meshes_json.items() if r["set"] == set_name and r["obj"] in HANDLE)
    for name, mask, ch, op, where, pos in (HANDLE_RECIPE if hm else []):
        wear_layer(g, f"рукоятка · {name}", mask, ch, op, hm, scene_mm, position=pos, where=where, set_name=set_name)
    gm = sorted(n for n, r in meshes_json.items() if r["set"] == set_name and r["obj"] in GREASE)
    if gm:
        grease_layer(g, gm, scene_mm)
        log.append(f"жир:{len(gm)}")
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
