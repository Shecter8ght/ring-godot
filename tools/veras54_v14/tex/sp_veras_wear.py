# ВЕРАС-54 v14, текстуры этап 2 — износ в Substance Painter поверх принятой заводской отделки (sp_veras.py, группа
# «Этап 1 — заводская отделка» не меняется). По образцу tools/pkp/sp_pkp_wear.py («Частокол», износ принят владельцем).
# Износ — группа «Этап 2 — износ» над заводской в каждом наборе (Passthrough, выключается целиком — show(False)), внутри —
# подгруппы по причине (пыль и нагар, ржавчина, царапины, кромки и выступы, места эксплуатации, руки: жир и полировка).
# Слой = заливка (цвет / блеск / металл / высота) по маске: умная маска владельца (E:/Models Blender/Маски_АЛЬФА/smart
# masks — только они) — рисунок и рваный край, × карта места wear_place.py — где (форма в мм, редкие пятна, места
# эксплуатации). Общие слои рода — recipes(); места эксплуатации — данные wear_places.json (дописываются без правки кода),
# вид следа места → слой — kind_layer(). Потёртость снимает покрытие: высота FLAT − DEPTH (режим Normal) — заводское
# микрозерно под ней гаснет, открывается основание рода (BASE).
# Сила: K — общий множитель, KG — по подгруппам; непрозрачность слоя = своя × сила места × K × KG[подгруппа] (≤ 1). Над
# износом — пустая группа «Этап 2 — кистью (владелец)» (скриптом не пересобирается).
# Проекты — копии принятых: VERAS_<проект>_wear_v<VER>.spp (копию делает wear_all.py; принятые _v1.spp не открываются).
# Через мост (FINISH_SP_JOBS=_asset_src/veras54_v14/tex/sp_jobs), см. wear_all.py:
#   … -c "import sys; sys.path.insert(0, r'E:/Games/RING-godot/tools/veras54_v14/tex'); import sp_veras_wear as W; print(W.open_wear('body'))"
#   … print(W.build(k=1.0, kg={'rust': 0.35}))  → _wear_done.txt;  … print(W.export(<папка>)) → _export_done.txt
#   … print(W.restack_factory())  — заводская группа заново по finish-spec.json (стирает и износ: потом build)
import json
import os

import substance_painter.event as E
import substance_painter.layerstack as L
import substance_painter.project as P
import substance_painter.resource as R
import substance_painter.textureset as TS

import sp_finish
import sp_veras
import tex_sets as T

MASKS_DIR = r"E:/Models Blender/Маски_АЛЬФА/smart masks"
WEAR_DIR = T.WORK + "/wear"
PLACES = os.path.dirname(os.path.abspath(__file__)) + "/wear_places.json"
GROUP = "Этап 2 — износ"
HAND_GROUP = "Этап 2 — кистью (владелец)"
# плитка развёртки 0…1 умной маски ≈ TILE_MM предмета (у «Частокола» 400). Износ v02: подбор по штриху царапины
# 0,1–0,3 мм и сколу 0,5–3 мм на кропе карты 1:1 (переменная окружения VERAS_TILE_MM — для проб)
TILE_MM = float(os.environ.get("VERAS_TILE_MM", "250"))
# версия копий проектов износа (VERAS_<проект>_wear_v<VER>.spp): v1 — первый проход (рабочее 2K), v2 — второй
VER = int(os.environ.get("VERAS_WEAR_VER", "2"))
# «Мыло» износа v01 (диагноз 2026-11-19): (1) наборы 4K работали в копиях в 2K и выгружались растянутыми до 4K — спектр
# карт крышки и коробки выше частоты 2K упал в 4–7 раз против заводской, у набора grip (родные 2K) не изменился;
# (2) съём покрытия рисовался непрозрачностью 0,5–0,9 по мягкой маске — 88 % изменённых пикселей промежуточные (серая
# полупрозрачная плёнка). Теперь съём — «есть или нет»: непрозрачность 1, маска (рисунок × место) порогом Histogram Scan
# с высоким контрастом; сила места — доля следа (порог), а не прозрачность.
HARD_CONTRAST = 0.93       # контраст порога съёма: край в 1–2 пикселя, рваный по рисунку маски
HARD_POS = 0.5             # порог съёма при силе 1 (доля белого Histogram Scan)
FINE_ONLY = ("curvature_soft", "curvature_medium", "curvature_large", "curvature_big", "curvature_huge", "global_blur",
             "Edges_Smoothness", "Curvature_Smoothness")
CAP = {"ao_blur": 0.5}
FLAT = 0.5                 # уровень высоты заводской основы (sp_finish.H0): под снятым покрытием — ровно, без зерна

# сила: K и KG — первый проход по списку владельца 2026-11-19 (лёгкие потёртости, сдержанно)
K = 1.0
KG = {"dust": 1.0, "rust": 0.0, "scratch": 1.0, "edge": 1.0, "use": 1.0, "grease": 1.0}
SUB = [("dust", "пыль, грязь и нагар"), ("rust", "ржавчина (не заказана — пусто, выключено)"), ("scratch", "царапины"),
       ("edge", "кромки и выступы"), ("use", "места эксплуатации"), ("grease", "руки: жир и полировка")]
RUST_ON = False            # ржавчину владелец не заказывал: подгруппа есть, пустая и выключенная

# умные маски, одобренные владельцем (лист 2026-11-19, первая и вторая поменяны местами по применению) — других не брать
APPROVED = ("gun scratch edge", "edge damage", "micro scratches", "gun scratch storng", "damage line", "stain roughness",
            "finger print", "dirt roughness", "cavity dirt", "AO dirt", "micro damages", "soft dirt")

# род износа по слоту отделки (finish-spec.json → slots[].id); primer / sealant — маски на гильзе, без своего износа
CLASS = {"corpus": "paint", "dark": "phosphate", "carrier": "oxide", "bolt": "bright", "piston": "chrome",
         "spring": "spring", "polymer_go": "poly_go", "polymer_blk": "poly_blk", "alu": "alu", "rubber": "rubber",
         "case": "lacquer", "bullet": "bullet"}

# Владелец 2026-11-19: «износ должен быть не процедурной текстурой, нанесённой на заводскую отделку, а физически вычитать
# высоты, но не сильно, это должны быть лёгкие потёртости на углах, рёбрах, но не на всех, а очень разбросанно и без
# прямых ровных границ». Потёртость = покрытие снято (высота FLAT − DEPTH, заводское зерно гаснет, под ним основание
# рода), место — кромка по форме × редкие пятна (wear_place.py, sparse) × умная маска (рваный край); плоскости целые.
DEPTH = 0.004              # глубина потёртости в единицах высоты набора (основа 0,5; зерно краски ±0,003 Overlay)

DUST = dict(color=(0.27, 0.26, 0.235), rough=0.88, metal=0.0)
GRIME = dict(color=(0.045, 0.042, 0.038), rough=0.72, metal=0.1)
SOOT = dict(color=(0.035, 0.034, 0.033), rough=0.82, metal=0.15)

# основание под снятым покрытием по роду: (цвет sRGB, шероховатость, металл, снятие вычитает высоту).
# Корпус после подбора владельца — тёмная глянцевая сталь (0,044 / 0,16 / металл 1): стёртое отличается светлотой и
# блеском, а не «металл против неметалла» — светлая сталь 0,58, чуть глаже покрытия (владелец: «до светлого металла,
# у которого шероховатость ниже»).
BASE = {
    # владелец 2026-11-19 (по окну Painter, износ v02): «сколы слишком зеркальные, их надо сделать мутными как на калаше
    # в Escape from Tarkov» — голая сталь под краской мутная: шероховатость 0,42–0,5, тон приглушённый 0,42–0,5 sRGB
    "paint": ((0.30, 0.302, 0.308), 0.50, 1.0, True),      # v03: темнее — на прямом свете была белёсой
    "phosphate": ((0.29, 0.293, 0.30), 0.52, 1.0, True),
    "oxide": ((0.31, 0.313, 0.32), 0.48, 1.0, True),
    "alu": ((0.58, 0.58, 0.60), 0.34, 1.0, True),
    "lacquer": ((0.48, 0.48, 0.46), 0.34, 1.0, True),
    "poly_go": ((0.215, 0.215, 0.192), 0.42, 0.0, False),  # полимер: тот же цвет, светлее и глаже — не металл
    "poly_blk": ((0.115, 0.115, 0.115), 0.44, 0.0, False),
    "rubber": ((0.13, 0.13, 0.13), 0.70, 0.0, False),
    "bright": ((0.78, 0.79, 0.80), 0.18, 1.0, False),      # голая сталь — только заполировка
    "chrome": ((0.80, 0.80, 0.81), 0.15, 1.0, False),
    "spring": ((0.50, 0.50, 0.51), 0.30, 1.0, False),
    "bullet": ((0.86, 0.60, 0.42), 0.20, 1.0, False),
}
METAL_SURF = {"paint", "phosphate", "oxide", "alu", "lacquer", "bright", "chrome", "spring", "bullet"}


def base_ch(cls, depth=1.0):
    c, r, m, sub = BASE[cls]
    return dict(color=c, rough=r, metal=m, height=FLAT - (DEPTH * depth if sub else DEPTH * 0.3 * depth))


def polish_ch(cls):
    """Полировка: глаже, зерно покрытия гаснет; у полимера чуть светлее, металл не появляется."""
    c, r, m, sub = BASE[cls]
    if cls in ("poly_go", "poly_blk", "rubber"):
        return dict(color=c, rough=r - 0.04, height=FLAT)
    # полировка руками — не глаже 0,3 (владелец 2026-11-19: зеркало не нужно)
    if cls == "paint":
        return dict(rough=0.30, height=FLAT)
    if cls == "oxide":
        return dict(color=(0.22, 0.22, 0.225), rough=0.3, height=FLAT)   # оксид протёрт — светлее и глаже
    return dict(rough=max(0.3, r - 0.1), height=FLAT)


# общие слои рода (без мест эксплуатации), снизу вверх: (подгруппа, имя, умная маска, каналы, непрозрачность,
# место wear_place.py, порог Histogram Scan или None). Пыль и грязь в углублениях — пункт 7 владельца: светлая пыль
# «cavity dirt» в углах, тёмная грязь «AO dirt» в щелях.
def recipes(cls):
    out = []
    if cls in ("paint", "phosphate", "alu", "poly_go", "poly_blk", "rubber"):
        out.append(("dust", "тёмная грязь в щелях", "AO dirt",
                    GRIME if cls != "poly_go" else dict(GRIME, color=(0.07, 0.068, 0.06)), 0.45, "deep", None))
        dust = DUST if cls in METAL_SURF else dict(DUST, color=(0.32, 0.31, 0.28) if cls == "poly_go" else (0.23, 0.22, 0.20))
        out.append(("dust", "светлая пыль в углах", "cavity dirt", dust, 0.35, "cavity", None))
    if cls in ("oxide", "bright", "spring", "chrome"):
        out.append(("dust", "масло и нагар в углах", "AO dirt", dict(color=(0.09, 0.085, 0.08), rough=0.42, metal=0.5),
                    0.5, "cavity", None))
    if cls == "bullet":
        out.append(("dust", "потемнения томпака", "soft dirt", dict(color=(0.45, 0.26, 0.16), rough=0.42, metal=1.0),
                    0.25, None, None))
    # редкие кромки (пункт 8): основная — «edge damage», вторым номером — «gun scratch edge» (замена владельца)
    if cls in ("paint", "phosphate", "oxide", "alu"):
        out.append(("edge", "редкие потёртости кромок до основания", "edge damage", base_ch(cls), 0.9, "edge", None))
        out.append(("edge", "редкие потёртости широких скруглений", "gun scratch edge", base_ch(cls, 0.6), 0.45,
                    "edge_wide", None))
        out.append(("edge", "головки заклёпок и осей вытерты", "micro damages", base_ch(cls, 0.5), 0.7, "tops", None))
    if cls in ("poly_go", "poly_blk"):
        out.append(("edge", "кромки затёрты — глаже и светлее", "edge damage", base_ch(cls), 0.6, "edge_wide", None))
    return out


# вид следа места (wear_places.json → kind) по умолчанию: (подгруппа, умная маска, каналы, непрозрачность, порог);
# поля места mask / rough / color / depth / scan — поверх
def kind_layer(kind, cls, depth=1.0):
    if kind == "edge_wear":
        return "use", "edge damage", base_ch(cls, depth), 1.0, None
    if kind == "polish":
        return "use", "stain roughness", polish_ch(cls), 0.8, None
    if kind == "scratch":
        ch = base_ch(cls, 0.5 * depth)
        if depth <= 0.0:
            ch.pop("height")
        # порог Histogram Scan: Position — доля белого (0,9 закрывал плоскость сплошь — первый прогон 19.11)
        return "scratch", "micro scratches", ch, 0.9, 0.15
    if kind == "dust":
        return "dust", "cavity dirt", DUST if cls in METAL_SURF else dict(DUST, color=(0.30, 0.29, 0.26)), 0.6, None
    if kind == "grime":
        return "dust", "AO dirt", GRIME, 0.6, None
    if kind == "soot":
        return "dust", "AO dirt", SOOT, 0.85, None
    raise RuntimeError("неизвестный вид следа " + kind)


SURF = {"paint": "gloss", "phosphate": "metal", "oxide": "metal", "alu": "metal", "bright": "metal", "chrome": "metal",
        "spring": "metal", "lacquer": "metal", "bullet": "metal", "poly_go": "poly_go", "poly_blk": "poly_blk",
        "rubber": "poly_blk"}
GREASE_POS = 0.75          # порог отпечатков (у «Частокола» при 0,5 их почти не оставалось)
# жирная плёнка: на матовом — блеск (шероховатость ниже), на глянцевой стали корпуса — лёгкая дымка (шероховатость выше
# и чуть светлее); цвет почти не меняется (тёмное пятно читается грязью)
PRINT = {
    "metal": dict(color=(0.86, 0.86, 0.86), rough=0.16, color_op=0.2, rough_op=0.7, stain_rough=0.2, stain_op=0.45),
    "gloss": dict(color=(0.09, 0.09, 0.095), rough=0.3, color_op=0.35, rough_op=0.6, stain_rough=0.26, stain_op=0.45,
                  normal_color=True),
    "poly_go": dict(color=None, rough=0.36, rough_op=0.7, stain_rough=0.4, stain_op=0.5),
    "poly_blk": dict(color=None, rough=0.38, rough_op=0.7, stain_rough=0.42, stain_op=0.5),
}
_cache = {}
_handlers = E.__dict__.setdefault("_veras_wear_handlers", {})
CUR = sp_veras.CUR


def wear_spp(proj):
    return T.WORK + f"/sp/VERAS_{proj}_wear_v{VER}.spp"


def _ok(proj):
    return (P.is_open() and P.is_in_edition_state()
            and P.file_path().replace("\\", "/").lower() == wear_spp(proj).lower()
            and sorted(t.name() for t in TS.all_texture_sets()) == sorted(T.PROJECTS[proj]))


def open_wear(proj):
    """Открыть копию проекта для износа (копию делает wear_all.py — принятый _v1.spp не открывается); метка
    _project_ready.txt — когда открыта именно она."""
    spp = wear_spp(proj)
    if not os.path.exists(spp):
        raise RuntimeError("нет копии " + spp)
    CUR["proj"] = proj
    os.environ["OCIO"] = sp_finish.OCIO
    if _ok(proj):
        sp_finish.mark("_project_ready.txt", "OK already open")
        return "already open"
    if P.is_open():
        P.close()

    def ready(e):
        if _ok(proj):
            old = _handlers.pop("open", None)
            if old is not None:
                try:
                    E.DISPATCHER.disconnect(E.ProjectEditionEntered, old)
                except Exception:      # noqa: BLE001
                    pass
            sp_finish.mark("_project_ready.txt", "OK opened " + proj)
    old = _handlers.pop("open", None)
    if old is not None:
        try:
            E.DISPATCHER.disconnect(E.ProjectEditionEntered, old)
        except Exception:      # noqa: BLE001
            pass
    _handlers["open"] = ready
    E.DISPATCHER.connect_strong(E.ProjectEditionEntered, ready)
    P.open(spp)
    return "opening " + spp


def check_open():
    proj = CUR["proj"]
    if not proj or not _ok(proj):
        raise RuntimeError(f"открыт не тот проект: {P.file_path() if P.is_open() else '—'}; нужна копия износа")
    return proj


def smart_mask(name):
    if name in _cache:
        return _cache[name]
    d = os.path.join(MASKS_DIR, name)
    f = [x for x in os.listdir(d) if x.endswith(".spmsk")][0]
    res = R.import_project_resource(os.path.join(d, f), R.Usage.SMART_MASK, name="veras_" + name.replace(" ", "_"))
    _cache[name] = res.identifier()
    return _cache[name]


def flat_mask(layer):
    """Генераторы внутри маски (кривизна, AO) — выключить: место на плоскости задаёт карта места, рисунок — грунж
    умной маски (иначе генератор кривизны гасит след целиком: дуга переводчика, верх планки)."""
    n = 0
    for e in layer.mask_effects():
        if type(e).__name__ == "GeneratorEffectNode":
            e.set_visible(False)
            n += 1
    return n


def to_triplanar(layer, scene_mm, stretch=1.0):
    """Заливки и генераторы внутри маски слоя — с развёртки на трёхпроекционную укладку (у high-poly тысячи островов:
    по развёртке рисунок рвался бы на швах) с плиткой TILE_MM; stretch < 1 — рисунок вытянут (продольные риски)."""
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
                k = s * scene_mm / TILE_MM
                q.uv_transformation.scale = [k * stretch, k]
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


def scan(layer, position, contrast=0.9):     # 0,6 оставлял серую дымку рисунка по всей плоскости (затылок крышки)
    import sp_lib
    e = L.insert_filter_effect(L.InsertPosition.inside_node(layer, L.NodeStack.Mask),
                               sp_lib.rid("histogram_scan/histogram_scan", "u:filter"))
    e.get_source().set_parameters({"Position": position, "Contrast": contrast})
    return e


def place(layer, kind, set_name):
    """Место следа поверх рисунка маски — карта wear_place.py, умножением."""
    m = L.insert_fill(L.InsertPosition.inside_node(layer, L.NodeStack.Mask))
    m.set_source(None, sp_finish._bitmap(f"{WEAR_DIR}/{set_name}_{kind}.png"))
    m.set_projection_mode(L.ProjectionMode.UV)
    m.set_blending_mode(L.BlendingMode.Multiply)
    return m


def _opacity(lay, op):
    import sp_lib
    for c in (sp_lib.CH.BaseColor, sp_lib.CH.SpecularRoughness, sp_lib.CH.Metallic, sp_lib.CH.Height):
        try:
            lay.set_opacity(min(1.0, op), c)
        except Exception:      # noqa: BLE001
            pass


def wear_layer(group, name, mask_name, ch, opacity, meshes, scene_mm, set_name, where=None, position=None, extra=None,
               hard=None):
    """Слой следа: заливка каналов ch по маске = умная маска владельца (рисунок) × место where; mask_name None —
    только место (карта wear_place.py: верхушки заклёпок, насечка). hard — сила съёма покрытия (0…1): слой непрозрачен,
    маска поверх всего — порогом с высоким контрастом (доля следа растёт с силой), без полупрозрачной плёнки."""
    import sp_lib
    extra = extra or {}
    if where and not os.path.exists(f"{WEAR_DIR}/{set_name}_{where}.png"):
        return None
    gritty = hard is not None and ch.get("metal", 0.0) > 0.5
    if gritty:
        # муть наложением шума смещает среднее вниз (замер на выгрузке 2026-11-19: шероховатость ×0,81, тон ×0,80) —
        # заливка задаётся с поправкой, чтобы в среднем вышли заданные числа
        ch = dict(ch)
        if "rough" in ch:
            ch["rough"] = min(1.0, ch["rough"] / GRIT_BIAS[1])
        if "color" in ch and not isinstance(ch["color"], str):
            ch["color"] = tuple(min(1.0, c / GRIT_BIAS[0]) for c in ch["color"])
    lay = sp_lib.fill(name, L.InsertPosition.inside_node(group, L.NodeStack.Substack), **ch)
    sp_lib.only_meshes(lay, meshes)
    _opacity(lay, 1.0 if hard is not None else opacity)
    if gritty:
        grit(lay, scene_mm)
    if extra.get("blend") == "multiply":
        lay.set_blending_mode(L.BlendingMode.Multiply, sp_lib.CH.BaseColor)
    lay.add_mask(L.MaskBackground.Black)
    if mask_name is None:
        sp_finish.bitmap_mask(lay, f"{WEAR_DIR}/{set_name}_{where}.png")
        if hard is not None:
            scan(lay, _hard_pos(HARD_POS, hard), HARD_CONTRAST)
        return lay
    L.insert_smart_mask(L.InsertPosition.inside_node(lay, L.NodeStack.Mask), smart_mask(mask_name))
    to_triplanar(lay, scene_mm, extra.get("stretch", 1.0))
    if extra.get("flat"):
        flat_mask(lay)
    if where:
        place(lay, where, set_name)
    if hard is not None:
        scan(lay, _hard_pos(position if position is not None else HARD_POS, hard), HARD_CONTRAST)
    elif position is not None:
        scan(lay, position)
    return lay


# муть голой стали внутри скола (владелец 2026-11-19: пятно не ровной заливкой): гауссов шум наложением в содержимом
# слоя съёма — только внутри него; два размера: зерно ~0,25 мм и неровность тона ~3 мм
GRIT = ((0.25, 0.22, 0.30), (3.0, 0.30, 0.25))      # (ячейка мм, сила в цвете, сила в шероховатости)
GRIT_BIAS = (0.80, 0.81)                             # во сколько раз муть сдвигает среднее: (тон sRGB, шероховатость)


def grit(lay, scene_mm):
    import sp_lib
    for cell, cop, rop in GRIT:
        try:
            f = L.insert_fill(L.InsertPosition.inside_node(lay, L.NodeStack.Content))
            f.active_channels = {sp_lib.CH.BaseColor, sp_lib.CH.SpecularRoughness}
            for c, o in ((sp_lib.CH.BaseColor, cop), (sp_lib.CH.SpecularRoughness, rop)):
                f.set_source(c, sp_lib.rid("noise_gaussian_noise/gaussian_noise", "u:procedural"))
                f.set_blending_mode(L.BlendingMode.Overlay, c)
                f.set_opacity(o, c)
            sp_lib.triplanar(f, scene_mm / (sp_finish.GAUSS_CELLS * cell))
        except Exception as e:      # noqa: BLE001
            print("муть съёма не легла:", e)


def _hard_pos(pos, strength):
    """Порог съёма: сила 1 — pos, слабее — меньше следа (доля, а не прозрачность)."""
    return max(0.03, min(0.95, pos * (0.4 + 0.6 * min(strength, 1.5))))


def hands(group, set_name, meshes, surf, where, scene_mm, k, tag, masks=(("finger print", 1.0), ("stain roughness", 1.0))):
    """Жир рук в месте where: «finger print» — отпечатки (с порогом), «stain roughness» / «dirt roughness» — жирные
    разводы блеска; вес — множитель непрозрачности."""
    import sp_lib
    pr = PRINT[surf]
    for mask, w in masks:
        if mask not in APPROVED:
            raise RuntimeError("маска не одобрена владельцем: " + mask)
        if mask == "finger print":
            ch = {"rough": pr["rough"]}
            if pr.get("color"):
                ch["color"] = pr["color"]
            lay = sp_lib.fill(f"{tag} · отпечатки пальцев", L.InsertPosition.inside_node(group, L.NodeStack.Substack),
                              **ch)
            if pr.get("color"):
                if not pr.get("normal_color"):
                    lay.set_blending_mode(L.BlendingMode.Multiply, sp_lib.CH.BaseColor)
                lay.set_opacity(min(1.0, pr["color_op"] * k * w), sp_lib.CH.BaseColor)
            lay.set_opacity(min(1.0, pr["rough_op"] * k * w), sp_lib.CH.SpecularRoughness)
        else:
            lay = sp_lib.fill(f"{tag} · жирные разводы ({mask})", L.InsertPosition.inside_node(group, L.NodeStack.Substack),
                              rough=pr["stain_rough"])
            lay.set_opacity(min(1.0, pr["stain_op"] * k * w), sp_lib.CH.SpecularRoughness)
        sp_lib.only_meshes(lay, meshes)
        lay.add_mask(L.MaskBackground.Black)
        L.insert_smart_mask(L.InsertPosition.inside_node(lay, L.NodeStack.Mask), smart_mask(mask))
        to_triplanar(lay, scene_mm)
        if mask == "finger print":
            scan(lay, GREASE_POS)
        place(lay, where, set_name)


def load_places():
    with open(PLACES, encoding="utf-8") as f:
        return json.load(f)["places"]


def _groups(set_name):
    """Группа износа над заводской (прежняя удаляется; группа кисти владельца не трогается) и подгруппы по причине."""
    import sp_lib
    st = sp_lib.stack_by_name(set_name)
    for n in L.get_root_layer_nodes(st):
        if n.get_name() == GROUP:
            L.delete_node(n)
    top = [n for n in L.get_root_layer_nodes(st) if n.get_name() == sp_finish.GROUP][0]
    g = L.insert_group(L.InsertPosition.above_node(top))
    g.set_name(GROUP)
    chans = st.all_channels()
    for ch in chans:
        g.set_blending_mode(L.BlendingMode.Passthrough, ch)
    subs = {}
    last = None
    for key, title in SUB:
        s = L.insert_group(L.InsertPosition.inside_node(g, L.NodeStack.Substack) if last is None
                           else L.InsertPosition.above_node(last))
        s.set_name(title)
        for ch in chans:
            s.set_blending_mode(L.BlendingMode.Passthrough, ch)
        subs[key] = s
        last = s
    if not RUST_ON:
        subs["rust"].set_visible(False)
    hand_group(set_name)
    return g, subs


def hand_group(set_name):
    """Пустая группа для кисти владельца над износом (если её нет); скриптом не пересобирается."""
    import sp_lib
    st = sp_lib.stack_by_name(set_name)
    roots = L.get_root_layer_nodes(st)
    if any(n.get_name() == HAND_GROUP for n in roots):
        return
    top = next(n for n in roots if n.get_name() == GROUP)
    g = L.insert_group(L.InsertPosition.above_node(top))
    g.set_name(HAND_GROUP)
    for c in st.all_channels():
        g.set_blending_mode(L.BlendingMode.Passthrough, c)


def _class_of(meshes_json, spec):
    """Род износа каждой сетки — по слоту отделки её детали."""
    cls = {}
    for slot in spec["slots"]:
        c = CLASS.get(slot["id"])
        if not c:
            continue
        for n, r in meshes_json.items():
            if r["obj"] in slot["parts"]:
                cls[n] = c
    return cls


def build_set(set_name, meshes_json, spec, scene_mm, k, kg):
    cls_of = _class_of(meshes_json, spec)
    set_meshes = sorted(n for n, r in meshes_json.items() if r["set"] == set_name)
    by = {}
    for n in set_meshes:
        if n in cls_of:
            by.setdefault(cls_of[n], []).append(n)
    g, subs = _groups(set_name)
    log = []

    def kk(group):
        return k * kg.get(group, 1.0)
    for cls in BASE:
        ms = by.get(cls)
        if not ms:
            continue
        for grp, name, mask, ch, op, where, pos in recipes(cls):
            assert mask in APPROVED, mask
            hard = op * kk(grp) if "height" in ch and ch["height"] < FLAT else None
            wear_layer(subs[grp], f"{cls} · {name}", mask, ch, op * kk(grp), ms, scene_mm, set_name, where, pos,
                       hard=hard)
        log.append(f"{cls}:{len(ms)}")
    # места владельца (пункты 1–7) и «на усмотрение» (8) — данные wear_places.json
    for pl in load_places():
        if pl["set"] != set_name or pl.get("off"):
            continue
        where = "z_" + pl["id"]
        if not os.path.exists(f"{WEAR_DIR}/{set_name}_{where}.png"):
            log.append(f"нет карты {where}")
            continue
        ms = [n for n in set_meshes if meshes_json[n]["obj"] in pl["parts"]]
        if not ms:
            log.append(f"нет сеток {pl['id']}")
            continue
        st = pl.get("strength", 1.0)
        tag = f"{pl['owner']} · {pl['id']}" if pl.get("owner") else pl["id"]
        if pl["kind"] == "grease":
            surfs = {}
            for n in ms:
                surfs.setdefault(SURF.get(cls_of.get(n, "paint"), "metal"), []).append(n)
            for surf, sm in surfs.items():
                hands(subs["grease"], set_name, sm, surf, where, scene_mm, kk("grease") * st, tag,
                      [tuple(x) for x in pl.get("masks", [["finger print", 1.0], ["stain roughness", 1.0]])])
            log.append(pl["id"])
            continue
        groups = {}
        for n in ms:
            groups.setdefault(cls_of.get(n, "paint"), []).append(n)
        if pl["kind"] == "stamp_wear":
            # штамп владельца (растровая маска в мировых координатах, wear_place.stamp): рисунок уже в карте места —
            # маска слоя только она, без умной маски и размытия; съём «есть / нет» (порог 0,5 высокой контрастностью)
            for cls, sm in groups.items():
                ch = dict(base_ch(cls, pl.get("depth", 1.0)))
                if "rough" in pl:
                    ch["rough"] = pl["rough"]
                if "color" in pl:
                    ch["color"] = tuple(pl["color"])
                wear_layer(subs["use"], f"{tag} · {pl.get('note', '')[:60]}", None, ch, 1.0, sm, scene_mm, set_name,
                           where, None, hard=pl.get("strength", 1.0))
            log.append(pl["id"])
            continue
        for cls, sm in groups.items():
            grp, mask, ch, op, pos = kind_layer(pl["kind"], cls, pl.get("depth", 1.0))
            mask = pl.get("mask", mask)
            if mask not in APPROVED:
                raise RuntimeError(f"{pl['id']}: маска не одобрена владельцем: {mask}")
            ch = dict(ch)
            if "rough" in pl:
                ch["rough"] = pl["rough"]
            if "color" in pl:
                ch["color"] = tuple(pl["color"])
            pos = pl.get("scan", pos)
            # съём покрытия (высота ниже основы — edge_wear, scratch с глубиной) — порогом, не прозрачностью
            hard = op * st * kk(grp) if pl["kind"] in ("edge_wear", "scratch") and ch.get("height", FLAT) < FLAT else None
            wear_layer(subs[grp], f"{tag} · {pl.get('note', '')[:60]}", mask, ch, op * st * kk(grp), sm, scene_mm,
                       set_name, where, pos, {"stretch": pl.get("stretch", 1.0), "flat": pl.get("flat", False)},
                       hard=hard)
        log.append(pl["id"])
    return f"{set_name}: " + " ".join(log)


def build(only=None, k=None, kg=None):
    """Группа износа во всех наборах открытой копии; k, kg — сила (умолчания K, KG); итог — _wear_done.txt, проект
    сохраняется; сила записывается в метаданные проекта (ring_wear)."""
    import sp_lib
    proj = check_open()
    k = K if k is None else k
    kg = dict(KG, **(kg or {}))
    meshes = sp_veras._json(os.path.splitext(sp_veras.paths(proj)[0])[0] + "_meshes.json")
    spec = sp_veras._json(sp_veras.SPEC)
    scene = sp_veras._scene()
    log = []
    for t in TS.all_texture_sets():
        if only and t.name() not in only:
            continue
        log.append(build_set(t.name(), meshes, spec, scene, k, kg))
    try:
        P.Metadata("ring_wear").set("strength", json.dumps({"k": k, "kg": kg}))
    except Exception:      # noqa: BLE001
        pass

    def done():
        P.save()
        return " | ".join(log)
    sp_lib.when_idle(done, "_wear_done.txt")
    return " | ".join(log)


def show(on=True, only=None, sub=None):
    """Включить / выключить группу износа целиком (или подгруппу sub — ключ SUB) — сравнение с заводской."""
    import sp_lib
    titles = dict(SUB)
    for t in TS.all_texture_sets():
        if only and t.name() not in only:
            continue
        for n in L.get_root_layer_nodes(sp_lib.stack_by_name(t.name())):
            if n.get_name() == GROUP:
                if sub is None:
                    n.set_visible(on)
                else:
                    for s in n.sub_layers():
                        if s.get_name() == titles[sub]:
                            s.set_visible(on)
    return "ok"


def export(out_dir, only=None, size=None):
    """Карты наборов (glTF PBR: baseColor, ORM, normal; 8 бит со сглаживанием полос) в разрешении набора
    (tex_sets.SETS, не рабочем) → out_dir; итог — _export_done.txt."""
    import substance_painter.export as X
    import sp_lib
    check_open()
    os.makedirs(out_dir, exist_ok=True)
    names = [t.name() for t in TS.all_texture_sets() if not only or t.name() in only]
    pr = [p for p in X.list_predefined_export_presets() if p.name == "glTF PBR Metal Roughness"][0]

    def run():
        n = 0
        for nm in names:
            sz = (size or min(T.SETS[nm][0], T.WORK_RES)).bit_length() - 1
            cfg = {"exportShaderParams": False, "exportPath": out_dir, "defaultExportPreset": pr.url,
                   "exportList": [{"rootPath": nm}],
                   "exportParameters": [{"parameters": {"fileFormat": "png", "bitDepth": "8", "dithering": True,
                                                        "paddingAlgorithm": "infinite", "sizeLog2": sz}}]}
            r = X.export_project_textures(cfg)
            n += sum(len(v) for v in r.textures.values())
        for junk in os.listdir(out_dir):
            if junk.startswith("Untitled.") or junk.endswith((".gltf", ".glb", ".bin")):
                os.remove(os.path.join(out_dir, junk))
        return f"{n} карт → {out_dir}"
    sp_lib.when_idle(run, "_export_done.txt")
    return "export " + " ".join(names)


def restack_factory():
    """Заводская группа в открытой копии заново по спецификации (sp_veras.stack; набор чистится целиком — износ и группа
    кисти тоже, потом build). Итог — _stack_done.txt."""
    proj = check_open()
    orig = sp_veras.check_open
    sp_veras.check_open = lambda: None          # sp_veras сверяет путь с принятым _v1.spp — здесь копия
    try:
        CUR["proj"] = proj
        return sp_veras.stack()
    finally:
        sp_veras.check_open = orig
