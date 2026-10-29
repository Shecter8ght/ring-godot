"""Транспорт «Проспекта»: стеки слоёв Substance Painter для машин (выполняются внутри Painter через мост).

Машина брошена года два назад: краска не новая, но целая — выгорела сверху, в мелких сколах по кромкам, в редких
царапинах; снизу и за колёсами грязь, по порогам и кромкам дверей рыжие точки, сверху пыль, с кромок крыши и стёкол —
подтёки. Пластик посерел на солнце, резина в пыли, хром в налёте. Слои — заливки (sp_lib), маски — генераторы по
положению, нормали мира, кривизне и процедурные пятна; по детали — маски геометрии (сетки «Набор__материал»).
Цвета — sRGB (sp_lib переводит), шероховатость и металл — как есть.
"""
import substance_painter.layerstack as L

import sp_lib
from sp_lib import fill, lop, mask_generator, mask_proc, only_meshes, triplanar

EDGE = "mg_metal_edge_wear/mg_metal_edge_wear"
DIRT = "mg_dirt/mg_dirt"
POS = "mg_position/mg_position"
WSN = "mg_world_space_normals/mg_world_space_normals"
RUSTDRIP = "mg_dripping_rust/mg_dripping_rust"

# масштаб трёхпроекционных процедурных масок: подобран на машине в метрах (см. probe в STATUS)
S_FINE, S_MID, S_WIDE = 6.0, 2.5, 1.0


def up(balance=0.5, contrast=0.4):
    """Маска «обращено вверх» (генератор нормали мира, ось верх-низ)."""
    return {"ws_direction_topbottom_opacity": 1.0, "ws_direction_rightleft_opacity": 0.0,
            "ws_direction_frontback_opacity": 0.0, "ws_balance": balance, "ws_contrast": contrast}


def low(balance=0.3, contrast=0.5):
    """Маска «низ машины» (генератор положения, ось верх-низ, белое внизу)."""
    return {"position_direction_topbottom_opacity": 1.0, "position_direction_rightleft_opacity": 0.0,
            "position_direction_frontback_opacity": 0.0, "position_invert": 1, "position_balance": balance,
            "position_contrast": contrast}


def _above(n):
    return L.InsertPosition.above_node(n)


def _top(st):
    return L.InsertPosition.from_textureset_stack(st)


def _meshes(st, mats):
    """Имена сеток набора по материалам деталей (только те, что есть в проекте)."""
    import substance_painter.project as P
    tset = st.material().name() if hasattr(st, "material") else None
    return mats


def pick(have, ts, *mats):
    """Сетки набора ts из материалов mats: «Набор__материал» и панели «Набор__материал__Деталь» (у краски кузова
    каждая панель — своя сетка, чтобы разводить их оттенком и блеском)."""
    out = []
    for x in mats:
        base = f"{ts}__{x}"
        out += sorted(h for h in have if h == base or h.startswith(base + "__"))
    return out


def bitmap(path):
    """Картинка из Blender (ливрея, маска мест — livery.py) → ресурс проекта Painter; источник заливки по развёртке."""
    import substance_painter.resource as R
    return R.import_project_resource(path, R.Usage.TEXTURE).identifier()


def subset(names, k, salt):
    """k имён из names — всегда одних и тех же для машины (по контрольной сумме), без случайности между прогонами."""
    import zlib
    return sorted(names, key=lambda n: zlib.crc32((salt + n).encode()))[:k]


def _mfilter(above, name, params):
    """Фильтр в маске над узлом: histogram_scan — порог и контраст (пятно читается издали), warp — рваный край, blur."""
    e = L.insert_filter_effect(L.InsertPosition.above_node(above), sp_lib.rid(name + "/" + name, "u:filter"))
    try:
        e.get_source().set_parameters(params)
    except Exception as err:                    # имя параметра у фильтра другое — показать, какие есть
        print("  фильтр", name, "параметры:", sorted(e.get_source().get_parameters().keys()), err)
    return e


def _sharpen(grp, amount=0.3):
    """Слабая резкость в конце (справка навыка) — эффектом группы: поверх слоёв фильтр API Painter не вставляет."""
    sh = L.insert_filter_effect(L.InsertPosition.inside_node(grp, L.NodeStack.Content),
                                sp_lib.rid("sharpen/sharpen", "u:filter"))
    sh.get_source().set_parameters({"intensity": amount})
    return sh


def _soft(layer):
    """Цвет слоя — режимом Soft Light: крупное пятно света/тени не съедает мелкую вариацию под собой."""
    layer.set_blending_mode(L.BlendingMode.SoftLight, sp_lib.CH.BaseColor)
    return layer


def group(name, pos, meshes):
    g = L.insert_group(pos)
    g.set_name(name)
    only_meshes(g, meshes)
    return g


def _proc(layer_name, pos, proc, scale, opacity, params=None, **ch):
    lay = fill(layer_name, pos, **ch)
    mask_proc(lay, proc, params, scale=scale, opacity=1.0)
    lop(lay, opacity)
    return lay


def _gen_mask(layer, gen, params=None):
    return mask_generator(layer, gen, params)


def _gen_mul(layer, gen, params=None):
    """Генератор поверх уже лежащей маски — умножением (обычный режим Normal её бы перекрыл)."""
    g = mask_generator(layer, gen, params)
    g.set_blending_mode(L.BlendingMode.Multiply)
    return g


def _mul_proc(layer, proc, scale, params=None, opacity=1.0):
    """Процедурное пятно поверх уже лежащей в маске основы — умножением (пятна внутри зоны генератора)."""
    stack = L.get_mask_nodes(layer) if hasattr(L, "get_mask_nodes") else None
    f = mask_proc(layer, proc, params, scale=scale, blend=L.BlendingMode.Multiply, opacity=opacity)
    return f


# --- краска кузова --------------------------------------------------------------------------------

def smart_mask(layer, name):
    """Умная маска полки Painter (грязь с земли, пыль, подтёки, ржавчина по кромкам) в маску слоя."""
    sp_lib.mask_black(layer)
    pos = L.InsertPosition.inside_node(layer, L.NodeStack.Mask)
    return L.insert_smart_mask(pos, sp_lib.rid(name, "u:smartmask"))


def paint(st, meshes, color, rough=0.24, metal=0.0, age=1.0, panels=None, salt="", livery=None):
    """Автоэмаль под лаком, брошенная машина (v2, порядок слоёв — справка навыка «Дерево и крашеный металл»):
    основа → свой тон и блеск у отдельных панелей → крупные пятна тона Soft Light (пара в шероховатости) → выгорание
    сверху → рельеф краски → шумы крупного плана → сколы отдельным материалом (грунт, металл, ржавчина; край скола
    приподнят, вокруг — потемнение) → подтёки и ржавчина по кромкам внизу → вариации блеска → резкость. Грязь и пыль —
    общей «историей» поверх всех материалов кузова (history). panels — сетки панелей для разнотона; age — сила
    старения; salt — чтобы у разных машин перекрашенные панели были разными; livery — ресурс картинки ливреи (такси,
    полиция, скорая): цвет эмали — из неё по развёртке, у перекрашенных панелей меняется только блеск (иначе однотонная
    заливка закрыла бы полосы и надписи); color — основной цвет ливреи (для выгорания и мелкого тона)."""
    CH = sp_lib.CH
    g = group("Краска", _top(st), meshes)
    pos = L.InsertPosition.inside_node(g, L.NodeStack.Substack)
    n = fill("01 Эмаль", pos, color=color, rough=rough, metal=metal)
    if livery is not None:
        n.set_source(CH.BaseColor, livery)
    # детали одного цвета разводятся оттенком и блеском (одна заливка на всё — «пластмасса»): одна-две панели
    # перекрашены (чуть другой оттенок, новее и глянцевее), две выгорели сильнее соседних
    panels = [p for p in (panels or []) if p.count("__") >= 2]
    for k, p in enumerate(subset(panels, 2 if len(panels) > 6 else 1, salt + "repaint")):
        sh = (0.95, 0.985, 1.03) if k == 0 else (1.03, 1.0, 0.96)
        if livery is None:
            n = fill(f"02 Перекрашена: {p.split('__')[-1]}", _above(n),
                     color=tuple(min(1.0, c * q) for c, q in zip(color, sh)), rough=max(0.12, rough - 0.07))
        else:
            n = fill(f"02 Перекрашена: {p.split('__')[-1]}", _above(n), rough=max(0.12, rough - 0.07))
        only_meshes(n, [p])
    for p in subset([p for p in panels if p not in subset(panels, 2, salt + "repaint")], 2, salt + "fade"):
        n = _soft(fill(f"03 Выгорела сильнее: {p.split('__')[-1]}", _above(n), color=(0.66, 0.66, 0.66), rough=rough + 0.12))
        only_meshes(n, [p])
        lop(n, 0.35)
    # крупные пятна света и тени — для вида издали; каждое пятно в цвете с парой в шероховатости
    n = _soft(fill("04 Пятна тона светлее", _above(n), color=(0.64, 0.64, 0.64), rough=rough + 0.10))
    mk = mask_proc(n, "3D_perlin_noise_fractal/3D_perlin_noise_fractal", None, scale=0.45)
    _mfilter(mk, "histogram_scan", {"Position": 0.56, "Contrast": 0.45})
    n.set_opacity(0.3, CH.BaseColor)          # на насыщенной краске (вишня, олива) сильнее — пятна читались заплатами
    n.set_opacity(0.4, CH.SpecularRoughness)
    n = _soft(fill("05 Пятна тона темнее", _above(n), color=(0.38, 0.38, 0.38), rough=max(0.1, rough - 0.04)))
    mk = mask_proc(n, "3D_perlin_noise_fractal/3D_perlin_noise_fractal", None, scale=0.7, rot=37.0)
    _mfilter(mk, "histogram_scan", {"Position": 0.6, "Contrast": 0.4})
    n.set_opacity(0.3, CH.BaseColor)
    n.set_opacity(0.35, CH.SpecularRoughness)
    lighter = tuple(min(1.0, c * 1.06 + 0.04) for c in color)
    if livery is None:
        n = fill("06 Выгорание сверху", _above(n), color=lighter, rough=rough + 0.25)
    else:                                       # по ливрее — светлее мягким светом: чёрные шашки и надписи не желтеют
        n = _soft(fill("06 Выгорание сверху", _above(n), color=(0.72, 0.72, 0.72), rough=rough + 0.25))
    _gen_mask(n, WSN, up(0.55, 0.45))
    mk = mask_proc(n, "3D_perlin_noise_fractal/3D_perlin_noise_fractal", None, scale=S_MID, blend=L.BlendingMode.Multiply)
    _mfilter(mk, "warp", {"intensity": 0.3})
    lop(n, 0.5 * age)
    # рельеф краски: апельсиновая корка и неровность слоя — гладкая краска выглядит новой и фальшивой
    n = fill("07 Апельсиновая корка", _above(n), rough="noise_clouds_2/clouds_2", height="noise_clouds_2/clouds_2")
    triplanar(n, 120.0)
    n.set_blending_mode(L.BlendingMode.Overlay, CH.SpecularRoughness)
    n.set_opacity(0.10, CH.SpecularRoughness)
    n.set_opacity(0.0006, CH.Height)
    n = fill("08 Неровность слоя", _above(n), height="3D_perlin_noise_fractal/3D_perlin_noise_fractal")
    triplanar(n, 1.6)
    n.set_opacity(0.0015, CH.Height)
    # шумы крупного плана — несколько разных, не один
    n = _proc("09 Шагрень лака", _above(n), "noise_gaussian_noise/gaussian_noise", 40.0, 0.25, rough=rough + 0.10)
    n = _proc("10 Разводы блеска", _above(n), "grunge_wipe_smudgy_soft/grunge_wipe_smudgy_soft", 1.2, 0.35,
              {"Balance": 0.55, "Contrast": 0.3}, rough=rough + 0.18)
    n = _proc("11 Мелкий тон", _above(n), "grunge_dusty_powder_soft/grunge_dusty_powder_soft", S_FINE, 0.12,
              None, color=tuple(c * 0.9 for c in color) if livery is None else (0.40, 0.40, 0.40))
    if livery is not None:
        _soft(n)
    n = _proc("12 Царапины лака", _above(n), "grunge_scratches_fine/grunge_scratches_fine", S_FINE, 0.35 * age,
              {"invert": 0, "balance": 0.36, "contrast": 0.55}, rough=rough + 0.25)
    # сколы — только на панелях: тонкие рамки дверей, стойки и проёмы генератор износа целиком считает кромкой
    chip_on = [p for p in meshes if not any(k in p for k in ("Frame", "Pillar", "Jamb", "Inner", "Cowl", "paint_inner"))]
    n = _chips(_above(n), age, chip_on)
    n = fill("17 Подтёки воды", _above(n), color=(0.42, 0.39, 0.34), rough=0.7)
    smart_mask(n, "Water Drips")
    lop(n, 0.45 * age)
    n = fill("18 Ржавчина по кромкам внизу", _above(n), color=(0.34, 0.15, 0.06), rough=0.9)
    smart_mask(n, "Edge Rust")
    _gen_mul(n, POS, low(0.42, 0.35))
    lop(n, 0.9 * age)
    n = fill("19 Ржавые подтёки", _above(n), color=(0.38, 0.20, 0.09), rough=0.85)
    smart_mask(n, "Rust Drips")
    lop(n, 0.3 * age)
    # вариации блеска разнообразнее цвета: пятна от высохших капель, матовые разводы
    n = _proc("20 Пятна от капель", _above(n), "grunge_spots_dirty/grunge_spots_dirty", S_MID, 0.4, None, rough=0.55)
    _sharpen(g, 0.3)
    return g


def _chips(pos, age, on=None):
    """Сколы краски — отдельный материал внутри краски: грунт, в середине голый металл с ржавчиной; край скола
    приподнят (толщина краски), вокруг — потемнение. «Крупное — среднее — мелкое»: по кромкам (генератор износа ×
    фото-гранж, порог и рваный край), мелкие точки от камней спереди. Одна маска скола повторяется в каждом слое
    теми же параметрами генератора — как якорь в Painter."""
    CH = sp_lib.CH
    edge = {"Wear_Level": 0.08 + 0.06 * age, "Wear_Contrast": 0.8, "Grunge_Amount": 0.85, "grunge_scale": 6,
            "Use_Triplanar": 1, "Edges_Smoothness": 0.3, "Ambient_Occlusion_Masking": 0.4, "Curvature_Weight": 1.0}

    def chip_mask(layer, shrink=0.0):
        gm = mask_generator(layer, EDGE, edge)
        mk = mask_proc(layer, "grunge_paint_scraped/grunge_paint_scraped", None, scale=S_MID,
                       blend=L.BlendingMode.Multiply, above=gm)
        mk = _mfilter(mk, "warp", {"intensity": 0.25})
        return _mfilter(mk, "histogram_scan", {"Position": 0.5 + shrink, "Contrast": 0.8})

    def stone_mask(layer, shrink=0.0):
        gm = mask_generator(layer, POS, {"position_direction_topbottom_opacity": 0.0,
                                         "position_direction_frontback_opacity": 1.0,
                                         "position_direction_rightleft_opacity": 0.0, "position_balance": 0.78,
                                         "position_contrast": 0.6, "position_invert": 0})
        mk = mask_proc(layer, "grunge_spots_dirty/grunge_spots_dirty", None, scale=S_FINE * 2,
                       blend=L.BlendingMode.Multiply, above=gm)
        return _mfilter(mk, "histogram_scan", {"Position": 0.78 + shrink, "Contrast": 0.9})

    n = fill("13 Край скола: краска приподнята", pos, color=(0.5, 0.5, 0.5), rough=0.5, height=0.0005)
    n.active_channels = {CH.Height, CH.SpecularRoughness}
    m = chip_mask(n)
    _mfilter(m, "blur", {"intensity": 1.5})
    lop(n, 0.6)
    layers = [n]
    n = _soft(fill("14 Потемнение вокруг скола", _above(n), color=(0.3, 0.26, 0.22)))
    m = chip_mask(n)
    m = _mfilter(m, "blur", {"intensity": 3.0})
    _mfilter(m, "warp", {"intensity": 0.4})
    lop(n, 0.35 * age)
    layers.append(n)
    n = fill("15 Сколы до грунта", _above(n), color=(0.45, 0.45, 0.43), rough=0.72, height=0.0)
    chip_mask(n)
    layers.append(n)
    n2 = fill("15б Сколы от камней", _above(n), color=(0.45, 0.45, 0.43), rough=0.72)
    stone_mask(n2)
    lop(n2, 0.5 * age)
    n = fill("16 Металл в сколе, ржавый", _above(n2), color=(0.24, 0.2, 0.17), rough=0.55, metal=0.9)
    m = chip_mask(n, 0.2)
    mask_proc(n, "grunge_rust_fine/grunge_rust_fine", None, scale=S_MID, blend=L.BlendingMode.Multiply, above=m,
              opacity=0.6)
    if on:                                      # каждой заливке сколов — только панели
        for lay in layers + [n2, n]:
            only_meshes(lay, on)
    return n


def history(st, meshes, age=1.0):
    """История поверх всех материалов кузова (грязь и пыль после резкости, один слой на всё — детали «побывали в одном
    месте»): грязь с земли, грязь в щелях, пыль на горизонталях и общая лёгкая пыль."""
    g = group("История: грязь и пыль", _top(st), meshes)
    pos = L.InsertPosition.inside_node(g, L.NodeStack.Substack)
    n = fill("01 Грязь с земли", pos, color=(0.27, 0.23, 0.18), rough=0.92)
    m = smart_mask(n, "Dirt Ground")
    lop(n, 1.0 * age)
    n = fill("02 Грязь в щелях", _above(n), color=(0.12, 0.11, 0.09), rough=0.9)
    _gen_mask(n, DIRT, {"dirt_level": 0.30, "dirt_contrast": 0.7, "grunge_amount": 0.2, "Grunge_Scale": 6, "Use_Triplanar": 1})
    lop(n, 0.7 * age)
    # узкие рамки окон между стеклом и уплотнителем по AO — целиком «щель»: без этой грязи они тёмные целиком
    only_meshes(n, [x for x in meshes if "Frame" not in x and "sign_plastic" not in x])
    n = fill("03 Пыль сверху", _above(n), color=(0.62, 0.58, 0.52), rough=0.95)
    smart_mask(n, "Dust Surface")
    # умная маска пыли ложится и на борта — только на горизонтали; на вишне и оливе давала главные «заплаты»
    # (замер разброса яркости краски хэтчбека: 12,1 → 8,8 без неё)
    _gen_mul(n, WSN, up(0.66, 0.8))
    lop(n, 0.55 * age)
    # мелкой дымкой: крупный порошковый гранж на насыщенной краске (вишня) читался бледными заплатами по дверям
    n = _proc("04 Общая лёгкая пыль", _above(n), "grunge_dusty_powder_soft/grunge_dusty_powder_soft", S_FINE, 0.08 * age,
              None, color=(0.55, 0.52, 0.47), rough=0.9)
    return g


# --- прочее снаружи --------------------------------------------------------------------------------

def plastic(st, meshes, color=(0.035, 0.035, 0.037), rough=0.55, name="Пластик чёрный", fade=0.6):
    g = group(name, _top(st), meshes)
    pos = L.InsertPosition.inside_node(g, L.NodeStack.Substack)
    n = fill("01 Пластик", pos, color=color, rough=rough)
    n = _proc("02 Фактура", _above(n), "noise_gaussian_noise/gaussian_noise", 60.0, 0.4, rough=rough + 0.15)
    n = fill("03 Посерел на солнце", _above(n), color=(0.20, 0.20, 0.20), rough=0.78)
    _gen_mask(n, WSN, up(0.55, 0.3))
    mask_proc(n, "grunge_dusty_powder_soft/grunge_dusty_powder_soft", None, scale=S_MID, blend=L.BlendingMode.Multiply)
    lop(n, fade)
    n = fill("04 Грязь", _above(n), color=(0.20, 0.18, 0.15), rough=0.9)
    _gen_mask(n, DIRT, {"dirt_level": 0.4, "dirt_contrast": 0.6, "grunge_amount": 0.6, "Grunge_Scale": 6, "Use_Triplanar": 1})
    lop(n, 0.7)
    _sharpen(g, 0.25)
    return g


def chrome(st, meshes):
    g = group("Хром", _top(st), meshes)
    pos = L.InsertPosition.inside_node(g, L.NodeStack.Substack)
    n = fill("01 Хром", pos, color=(0.78, 0.78, 0.78), rough=0.12, metal=1.0)
    n = _proc("02 Налёт", _above(n), "grunge_spots_dirty/grunge_spots_dirty", S_FINE, 0.5, None,
              color=(0.45, 0.43, 0.40), rough=0.45, metal=0.6)
    n = fill("03 Грязь", _above(n), color=(0.14, 0.12, 0.10), rough=0.9, metal=0.0)
    _gen_mask(n, DIRT, {"dirt_level": 0.45, "dirt_contrast": 0.7, "grunge_amount": 0.5, "Grunge_Scale": 6, "Use_Triplanar": 1})
    _sharpen(g, 0.25)
    return g


def rubber(st, meshes, dust=0.6):
    g = group("Резина", _top(st), meshes)
    pos = L.InsertPosition.inside_node(g, L.NodeStack.Substack)
    n = fill("01 Резина", pos, color=(0.035, 0.035, 0.035), rough=0.85)
    n = fill("02 Пыль", _above(n), color=(0.45, 0.42, 0.38), rough=0.95)
    _gen_mask(n, WSN, up(0.55, 0.4))
    mask_proc(n, "grunge_dust_small/grunge_dust_small", None, scale=S_MID, blend=L.BlendingMode.Multiply)
    lop(n, dust)
    return g


def flat(st, meshes, name, color, rough, metal=0.0, dirt=0.5):
    g = group(name, _top(st), meshes)
    pos = L.InsertPosition.inside_node(g, L.NodeStack.Substack)
    n = fill("01 Основа", pos, color=color, rough=rough, metal=metal)
    n = fill("02 Грязь", _above(n), color=(0.15, 0.13, 0.10), rough=0.9, metal=0.0)
    _gen_mask(n, DIRT, {"dirt_level": 0.4, "dirt_contrast": 0.6, "grunge_amount": 0.6, "Grunge_Scale": 6, "Use_Triplanar": 1})
    lop(n, dirt)
    return g


def rusty_steel(st, meshes, name="Сталь в ржавчине", base=(0.20, 0.19, 0.18), rust=0.6):
    g = group(name, _top(st), meshes)
    pos = L.InsertPosition.inside_node(g, L.NodeStack.Substack)
    n = fill("01 Сталь", pos, color=base, rough=0.55, metal=0.85)
    n = _proc("02 Ржавчина", _above(n), "grunge_rust_fine/grunge_rust_fine", S_MID, rust, None,
              color=(0.32, 0.14, 0.05), rough=0.9, metal=0.0)
    n = fill("03 Грязь", _above(n), color=(0.14, 0.12, 0.09), rough=0.92, metal=0.0)
    _gen_mask(n, DIRT, {"dirt_level": 0.5, "dirt_contrast": 0.6, "grunge_amount": 0.6, "Grunge_Scale": 6, "Use_Triplanar": 1})
    lop(n, 0.8)
    return g


def fabric(st, meshes, color=(0.09, 0.09, 0.095), name="Ткань сидений"):
    g = group(name, _top(st), meshes)
    pos = L.InsertPosition.inside_node(g, L.NodeStack.Substack)
    n = fill("01 Ткань", pos, color=color, rough=0.92)
    n = _proc("02 Переплетение", _above(n), "weave_1/ratio_weave_1", 60.0, 0.5, None,
              color=tuple(c * 0.7 for c in color), rough=0.95)
    n = fill("03 Пыль", _above(n), color=(0.40, 0.38, 0.34), rough=0.95)
    _gen_mask(n, WSN, up(0.55, 0.4))
    mask_proc(n, "grunge_dust_spread/grunge_dust_spread", None, scale=S_MID, blend=L.BlendingMode.Multiply)
    lop(n, 0.6)
    n = _proc("04 Пятна", _above(n), "grunge_stains_small_hollow/grunge_stains_small_hollow", S_MID, 0.35, None,
              color=(0.16, 0.13, 0.10), rough=0.9)
    return g


# --- наборы ---------------------------------------------------------------------------------------

def scrapes(st, meshes, where):
    """Перевёрнутый автобус: где лёг на асфальт и смялся (where — маска мест из Blender, livery.py) — лак стёрт и
    поцарапан полосами, местами краска содрана до металла, в ссадинах грязь с асфальта. Над краской, под «историей»."""
    def by_place(layer, proc, scale, params=None):
        sp_lib.mask_black(layer)
        f = L.insert_fill(L.InsertPosition.inside_node(layer, L.NodeStack.Mask))
        f.set_source(None, where)
        mask_proc(layer, proc, params, scale=scale, blend=L.BlendingMode.Multiply, above=f)
    g = group("Ссадины об асфальт", _top(st), meshes)
    pos = L.InsertPosition.inside_node(g, L.NodeStack.Substack)
    n = fill("01 Лак стёрт", pos, color=(0.70, 0.62, 0.42), rough=0.72)
    by_place(n, "grunge_wipe_smudgy_soft/grunge_wipe_smudgy_soft", 1.2, {"Balance": 0.45, "Contrast": 0.4})
    lop(n, 0.8)
    n = fill("02 Царапины полосами", _above(n), color=(0.52, 0.50, 0.46), rough=0.5, metal=0.4)
    by_place(n, "grunge_scratches_fine/grunge_scratches_fine", S_MID, {"invert": 0, "balance": 0.42, "contrast": 0.7})
    n = fill("03 Содрано до металла", _above(n), color=(0.40, 0.39, 0.37), rough=0.42, metal=0.9)
    by_place(n, "3D_perlin_noise_fractal/3D_perlin_noise_fractal", 3.0)
    lop(n, 0.85)
    n = fill("04 Грязь с асфальта в ссадинах", _above(n), color=(0.16, 0.15, 0.14), rough=0.92)
    by_place(n, "grunge_dusty_powder_soft/grunge_dusty_powder_soft", S_MID)
    lop(n, 0.7)
    return g


def livery_plastic(st, meshes, livery, name="Плафон такси"):
    """Пластик с печатью (плафон «шашечки»): цвет — из ливреи по развёртке, глянец пластика, пыль и грязь."""
    g = group(name, _top(st), meshes)
    pos = L.InsertPosition.inside_node(g, L.NodeStack.Substack)
    n = fill("01 Пластик с печатью", pos, color=(0.86, 0.80, 0.42), rough=0.35)
    if livery is not None:
        n.set_source(sp_lib.CH.BaseColor, livery)
    n = _proc("02 Фактура", _above(n), "noise_gaussian_noise/gaussian_noise", 60.0, 0.3, rough=0.5)
    n = _proc("03 Помутнел", _above(n), "grunge_dusty_powder_soft/grunge_dusty_powder_soft", S_MID, 0.25,
              None, color=(0.75, 0.73, 0.68), rough=0.6)
    # грязи по затенённости нет: плафон стоит на широкой крыше, бока затенены на 0,4 — грязь заливала его бурым
    n = _proc("04 Пыль", _above(n), "grunge_dusty_powder_soft/grunge_dusty_powder_soft", S_FINE, 0.2,
              None, color=(0.60, 0.57, 0.50), rough=0.8)
    return g


def body_clean(st, paint_color, have, ts="Body", livery=None, where=None):
    """Набор кузова (Body или половина длинного — BodyA / BodyB): have — имена сеток проекта (только существующие);
    livery — ресурс картинки ливреи набора, where — маска мест ссадин (перевёрнутый автобус)."""
    def m(*mats):
        return pick(have, ts, *mats)
    if m("paint", "bumper", "paint_inner"):
        paint(st, m("paint", "bumper", "paint_inner"), paint_color, panels=m("paint"), salt=ts + str(paint_color),
              livery=livery)
    if where is not None and m("paint", "bumper"):
        scrapes(st, m("paint", "bumper"), where)
    if m("sign_plastic"):
        livery_plastic(st, m("sign_plastic"), livery)
    if m("trim_black", "bumper_plastic", "liner"):
        plastic(st, m("trim_black", "bumper_plastic", "liner"))
    if m("trim_gloss_black"):
        plastic(st, m("trim_gloss_black"), color=(0.02, 0.02, 0.022), rough=0.25, name="Пластик глянцевый", fade=0.4)
    if m("mesh_black"):
        plastic(st, m("mesh_black"), color=(0.015, 0.015, 0.015), rough=0.7, name="Сетки решёток", fade=0.3)
    if m("chrome"):
        chrome(st, m("chrome"))
    if m("rubber"):
        rubber(st, m("rubber"))
    if m("lamp_inner"):
        flat(st, m("lamp_inner"), "Отражатели", (0.70, 0.70, 0.70), 0.25, metal=0.9, dirt=0.3)
    if m("lamp_red_inner"):
        flat(st, m("lamp_red_inner"), "Фонари изнутри", (0.30, 0.03, 0.02), 0.35, dirt=0.2)
    if m("lamp_amber"):
        flat(st, m("lamp_amber"), "Поворотники", (0.85, 0.42, 0.05), 0.3, dirt=0.2)
    if m("plate"):
        flat(st, m("plate"), "Номера", (0.86, 0.86, 0.84), 0.5, dirt=0.7)
    if m("steel_dark", "brake", "rust"):
        rusty_steel(st, m("steel_dark", "brake", "rust"))
    if m("hubcap"):
        flat(st, m("hubcap"), "Колпаки", (0.62, 0.63, 0.64), 0.35, metal=0.4)
    if m("seat"):
        plastic(st, m("seat"), color=(0.045, 0.045, 0.045), rough=0.6, name="Чехол запаски", fade=0.7)
    if m("rim_steel"):
        rusty_steel(st, m("rim_steel"), "Диск запаски", base=(0.30, 0.30, 0.31), rust=0.35)
    # плафон такси — без общей истории: «грязь с земли» по затенённости заливала его бурым (у него своя пыль)
    history(st, sorted(h for h in have if h.startswith(ts + "__") and "sign_plastic" not in h))


def interior_clean(st, have, seat_plastic=(0.20, 0.05, 0.04)):
    def m(*mats):
        return pick(have, "Interior", *mats)
    if m("interior", "trim_gloss_black", "trim_black"):
        plastic(st, m("interior", "trim_gloss_black", "trim_black"), color=(0.06, 0.06, 0.065), rough=0.6,
                name="Пластик салона", fade=0.3)
    if m("seat"):
        fabric(st, m("seat"))
    if m("carpet"):
        fabric(st, m("carpet"), color=(0.035, 0.035, 0.035), name="Ковролин")
    if m("headliner"):
        fabric(st, m("headliner"), color=(0.42, 0.41, 0.38), name="Потолок")
    if m("floor_rubber"):
        rubber(st, m("floor_rubber"), dust=0.9)
    if m("seat_plastic"):
        plastic(st, m("seat_plastic"), color=seat_plastic, rough=0.45, name="Сиденья пластик", fade=0.5)
    if m("rail_yellow"):
        flat(st, m("rail_yellow"), "Поручни", (0.80, 0.58, 0.08), 0.4, dirt=0.4)
    if m("rubber"):
        rubber(st, m("rubber"))
    if m("steel_dark"):
        rusty_steel(st, m("steel_dark"), "Каркасы", rust=0.3)
    if m("paint_inner", "paint"):
        flat(st, m("paint_inner", "paint"), "Окрашенный металл салона", (0.5, 0.5, 0.5), 0.5)


def wheel_clean(st, have, alloy=False):
    """Набор Wheel машины — колесо v2 (wheel); стиль диска — по материалам набора."""
    wheel(st, have, "Wheel", "alloy" if pick(have, "Wheel", "rim_alloy") else "steel")


# --- колесо v2 --------------------------------------------------------------------------------------
# Владелец 2026-10-29: «резина не имеет какого-либо рельефа, диски не имеют металлического материала с различной
# текстурой». Рельеф шины — запечённая подробная шина (vwheels.tire_high), здесь — материалы: резина протектора и
# боковины по-разному, металл дисков — краска-металлик и лак с зерном, разводами, царапинами, сколами и коррозией;
# машина брошена года два назад — тормозной диск в ржавчине, в углах дисков тормозная пыль. Масштаб масок (S_*) — тот же,
# что на кузове: сцена колёс в Painter размером с машину (wheels_kit.GAP).

WEAR = {"Wear_Contrast": 0.8, "Grunge_Amount": 0.85, "grunge_scale": 6, "Use_Triplanar": 1, "Edges_Smoothness": 0.3,
        "Ambient_Occlusion_Masking": 0.4, "Curvature_Weight": 1.0}


def _edge(layer, level, above=None):
    return mask_generator(layer, EDGE, dict(WEAR, Wear_Level=level), above=above)


def _dirt(layer, level, contrast=0.6, grunge=0.6):
    return _gen_mask(layer, DIRT, {"dirt_level": level, "dirt_contrast": contrast, "grunge_amount": grunge,
                                   "Grunge_Scale": 6, "Use_Triplanar": 1})


def _patches(layer, level, scale=S_MID, cut=0.5):
    """Кромка × рваные пятна: сколы и задиры кусками, а не ровной каймой по всей кромке."""
    gm = _edge(layer, level)
    mk = mask_proc(layer, "grunge_paint_scraped/grunge_paint_scraped", None, scale=scale,
                   blend=L.BlendingMode.Multiply, above=gm)
    mk = _mfilter(mk, "warp", {"intensity": 0.25})
    return _mfilter(mk, "histogram_scan", {"Position": cut, "Contrast": 0.8})


def _scratch(color):
    """Цвет царапины по краске: светлее основы (на чёрном — серая, на серебре — почти то же серебро)."""
    return tuple(min(1.0, 0.6 * c + 0.24) for c in color)


def tire(st, tread, side, age=1.0):
    """Шина: протектор вытерт и в пыли по канавкам, боковина матовая и побуревшая, надписи и насечка — по пыли в
    углублениях и вытертым кромкам (так их и видно на настоящей шине). age — сколько пыли и побурения (0,4 — у новых
    литых: шина ездила, но машину мыли)."""
    if tread:
        g = group("Шина: протектор", _top(st), tread)
        pos = L.InsertPosition.inside_node(g, L.NodeStack.Substack)
        n = fill("01 Резина протектора", pos, color=(0.034, 0.034, 0.035), rough=0.86)
        n = _proc("02 Тон резины", _above(n), "3D_perlin_noise_fractal/3D_perlin_noise_fractal", S_MID, 0.35,
                  color=(0.05, 0.048, 0.046), rough=0.9)
        # канавки темнее блоков (в них тень), пыль — только намёком: светлые канавки читались «наоборот»
        n = fill("03 Пыль и песок в канавках", _above(n), color=(0.20, 0.19, 0.17), rough=0.95)
        _dirt(n, 0.55, 0.75, 0.4)
        lop(n, 0.4 * age)
        n = _proc("04 Дорожная пыль", _above(n), "grunge_dusty_powder_soft/grunge_dusty_powder_soft", S_MID, 0.3 * age,
                  color=(0.26, 0.24, 0.21), rough=0.9)
        n = _proc("05 Песчинки", _above(n), "grunge_spots_dirty/grunge_spots_dirty", S_FINE * 2, 0.3 * age,
                  {"invert": 0}, color=(0.36, 0.34, 0.30), rough=0.92)
        _sharpen(g, 0.2)
    if side:
        g = group("Шина: боковина", _top(st), side)
        pos = L.InsertPosition.inside_node(g, L.NodeStack.Substack)
        n = fill("01 Резина боковины", pos, color=(0.040, 0.040, 0.041), rough=0.87)
        n = fill("02 Побурела от солнца", _above(n), color=(0.085, 0.072, 0.060), rough=0.86)
        mk = mask_proc(n, "3D_perlin_noise_fractal/3D_perlin_noise_fractal", None, scale=S_FINE)
        _mfilter(mk, "histogram_scan", {"Position": 0.45, "Contrast": 0.35})
        lop(n, 0.3 * age)
        n = fill("03 Пыль в надписях и насечке", _above(n), color=(0.40, 0.38, 0.35), rough=0.95)
        _dirt(n, 0.62, 0.8, 0.3)
        lop(n, 0.35 + 0.35 * age)
        n = fill("04 Вытертые кромки надписей", _above(n), color=(0.13, 0.13, 0.13), rough=0.9)
        _edge(n, 0.25)
        lop(n, 0.7)
        n = _proc("05 Потёртости о бордюр", _above(n), "grunge_scratches_rough/grunge_scratches_rough", S_FINE,
                  0.35 * age, None, color=(0.11, 0.11, 0.11), rough=0.9)
        n = _proc("06 Общая пыль", _above(n), "grunge_dusty_powder_soft/grunge_dusty_powder_soft", S_MID, 0.25 * age,
                  color=(0.45, 0.43, 0.40), rough=0.95)
        _sharpen(g, 0.2)


def steel_paint(st, meshes, lip, lk):
    """Штамповка в краске (вариант lk — wheel_looks: серебро-металлик, чёрная эмаль, коричневая …): зерно металлика
    (если есть), пятна тона, разводы блеска, царапины, сколы до металла кусками по кромкам (у закраины — от бордюров и
    шиномонтажа), ржавчина в сколах, тормозная пыль в углах и плёнкой — всё по износу age."""
    color, rough, metal, age = lk["color"], lk["rough"], lk["metal"], lk["age"]
    g = group(f"Штамповка: {lk['name']}", _top(st), meshes)
    pos = L.InsertPosition.inside_node(g, L.NodeStack.Substack)
    n = fill("01 Краска", pos, color=color, rough=rough, metal=metal)
    if lk["flakes"]:
        n = _proc("02 Зерно металлика", _above(n), "noise_gaussian_noise/gaussian_noise", 90.0, lk["flakes"],
                  color=tuple(min(1.0, c * 1.12) for c in color), rough=max(0.05, rough - 0.08))
    n = _soft(fill("03 Пятна тона", _above(n), color=(0.62, 0.62, 0.62), rough=rough + 0.09))
    mk = mask_proc(n, "3D_perlin_noise_fractal/3D_perlin_noise_fractal", None, scale=S_MID)
    _mfilter(mk, "histogram_scan", {"Position": 0.55, "Contrast": 0.4})
    lop(n, 0.35)
    n = _proc("04 Разводы блеска", _above(n), "grunge_wipe_smudgy_soft/grunge_wipe_smudgy_soft", 2.0,
              0.15 + 0.25 * age, {"Balance": 0.55, "Contrast": 0.3}, rough=rough + 0.19)
    n = _proc("05 Царапины", _above(n), "grunge_scratches_fine/grunge_scratches_fine", S_FINE * 2, 0.45 * age,
              {"invert": 0, "balance": 0.36, "contrast": 0.55}, color=_scratch(color), rough=rough + 0.14)
    if age > 0.05:
        n = fill("06 Сколы до металла", _above(n), color=(0.48, 0.48, 0.47), rough=0.42, metal=1.0)
        _patches(n, 0.16 * min(age, 1.2))
        n = fill("07 Ржавчина в сколах", _above(n), color=(0.33, 0.15, 0.06), rough=0.88, metal=0.0)
        m = _patches(n, 0.16 * min(age, 1.2), cut=0.62)
        mask_proc(n, "grunge_rust_fine/grunge_rust_fine", None, scale=S_MID, blend=L.BlendingMode.Multiply, above=m)
        lop(n, 0.85)
        if lip:
            n = fill("08 Задиры на закраине", _above(n), color=(0.62, 0.62, 0.61), rough=0.45, metal=1.0)
            _patches(n, 0.22 * min(age, 1.2), scale=S_FINE, cut=0.52)
            only_meshes(n, lip)
    n = fill("09 Тормозная пыль в углах", _above(n), color=(0.19, 0.155, 0.12), rough=0.85, metal=0.0)
    _dirt(n, 0.5)
    lop(n, 0.85 * age)
    n = _proc("10 Тормозная пыль плёнкой", _above(n), "grunge_dusty_powder_soft/grunge_dusty_powder_soft", S_MID,
              0.35 * age, color=(0.30, 0.26, 0.21), rough=0.7, metal=0.2)
    _sharpen(g, 0.25)
    return g


def alloy_paint(st, meshes, lip, lk):
    """Литой диск (вариант lk): краска под лаком — серебро, чёрный глянец, бронза, графит; зерно краски, разводы и пятна
    от капель, мелкие царапины лака, коррозия под лаком белёсыми нитями у кромок, задиры о бордюр на закраине (голый
    алюминий), тормозная пыль — всё по износу age; новые (age 0) — чистый лак с зерном и блеском."""
    color, rough, metal, age = lk["color"], lk["rough"], lk["metal"], lk["age"]
    g = group(f"Литой диск: {lk['name']}", _top(st), meshes)
    pos = L.InsertPosition.inside_node(g, L.NodeStack.Substack)
    n = fill("01 Краска под лаком", pos, color=color, rough=rough, metal=metal)
    if lk["flakes"]:
        n = _proc("02 Зерно краски", _above(n), "noise_gaussian_noise/gaussian_noise", 120.0, lk["flakes"],
                  color=tuple(min(1.0, c * 1.08) for c in color), rough=max(0.05, rough - 0.06))
    n = _soft(fill("03 Пятна тона", _above(n), color=(0.46, 0.46, 0.46), rough=rough + 0.06))
    mk = mask_proc(n, "3D_perlin_noise_fractal/3D_perlin_noise_fractal", None, scale=S_MID)
    _mfilter(mk, "histogram_scan", {"Position": 0.58, "Contrast": 0.4})
    lop(n, 0.1 + 0.1 * age)
    n = _proc("04 Разводы после мойки", _above(n), "grunge_wipe_smudgy_soft/grunge_wipe_smudgy_soft", 2.0,
              0.12 + 0.38 * age, {"Balance": 0.55, "Contrast": 0.3}, rough=rough + 0.12)
    n = _proc("05 Пятна от капель", _above(n), "grunge_spots_dirty/grunge_spots_dirty", S_FINE, 0.45 * age, None,
              rough=rough + 0.2)
    n = _proc("06 Царапины лака", _above(n), "grunge_scratches_fine/grunge_scratches_fine", S_FINE * 2,
              0.08 + 0.42 * age, {"invert": 0, "balance": 0.36, "contrast": 0.55}, color=_scratch(color),
              rough=rough + 0.15)
    if age > 0.05:
        n = fill("07 Коррозия под лаком", _above(n), color=(0.84, 0.83, 0.80), rough=0.75, metal=0.2)
        m = _edge(n, 0.12)
        mask_proc(n, "grunge_rust_fine/grunge_rust_fine", None, scale=S_FINE, blend=L.BlendingMode.Multiply, above=m)
        lop(n, 0.3 * age)
        if lip:
            n = fill("08 Задиры о бордюр", _above(n), color=(0.80, 0.80, 0.80), rough=0.5, metal=1.0)
            m = _patches(n, 0.25 * min(age, 1.2), scale=S_FINE, cut=0.5)
            mask_proc(n, "grunge_scratches_rough/grunge_scratches_rough", None, scale=S_FINE * 2,
                      blend=L.BlendingMode.Multiply, above=m)
            only_meshes(n, lip)
    # пыль в углах — без крупного гранжа: с ним по граням спиц шли чёрные пятна
    n = fill("09 Тормозная пыль в углах", _above(n), color=(0.22, 0.19, 0.15), rough=0.85, metal=0.0)
    _dirt(n, 0.45, 0.6, 0.25)
    lop(n, 0.65 * age)
    n = _proc("10 Тормозная пыль плёнкой", _above(n), "grunge_dusty_powder_soft/grunge_dusty_powder_soft", S_MID,
              0.4 * age, color=(0.28, 0.24, 0.19), rough=0.6, metal=0.3)
    _sharpen(g, 0.25)
    return g


def hubcap_plastic(st, meshes, lk):
    """Колпак (и колпачок литого): пластик в краске (вариант lk — серебрянка, графит) или голый чёрный; по кромкам
    краска стёрта до чёрного пластика, царапины, помутнел от солнца, грязь в углах и тормозная пыль — по износу age."""
    color, rough, metal, age = lk["color"], lk["rough"], lk["metal"], lk["age"]
    g = group(f"Колпак: {lk['name']}", _top(st), meshes)
    pos = L.InsertPosition.inside_node(g, L.NodeStack.Substack)
    n = fill("01 Краска по пластику", pos, color=color, rough=rough, metal=metal)
    if lk["flakes"]:
        n = _proc("02 Зерно краски", _above(n), "noise_gaussian_noise/gaussian_noise", 90.0, lk["flakes"],
                  color=tuple(min(1.0, c * 1.09) for c in color), rough=max(0.05, rough - 0.06))
    n = _proc("03 Помутнел", _above(n), "grunge_dusty_powder_soft/grunge_dusty_powder_soft", S_MID, 0.35 * age,
              color=tuple(min(1.0, c * 1.06 + 0.04) for c in color), rough=rough + 0.25, metal=metal * 0.5)
    n = _proc("04 Царапины", _above(n), "grunge_scratches_rough/grunge_scratches_rough", S_FINE * 2, 0.45 * age, None,
              color=_scratch(color), rough=rough + 0.3, metal=metal * 0.5)
    if age > 0.05 and metal > 0.0:                # краска стирается до чёрного пластика; у голого пластика — нечему
        n = fill("05 Стёрто до пластика", _above(n), color=(0.05, 0.05, 0.05), rough=0.6, metal=0.0)
        _patches(n, 0.22 * min(age, 1.2), scale=S_FINE)
    n = fill("06 Грязь в углах", _above(n), color=(0.20, 0.17, 0.13), rough=0.9, metal=0.0)
    _dirt(n, 0.5)
    lop(n, 0.8 * age)
    n = _proc("07 Тормозная пыль", _above(n), "grunge_dusty_powder_soft/grunge_dusty_powder_soft", S_MID, 0.3 * age,
              color=(0.30, 0.26, 0.21), rough=0.75, metal=0.1)
    _sharpen(g, 0.25)
    return g


def zinc(st, meshes):
    """Гайки и колпачок ступицы — оцинковка с радужным налётом, точки ржавчины, грязь в гранях."""
    g = group("Гайки: оцинковка", _top(st), meshes)
    pos = L.InsertPosition.inside_node(g, L.NodeStack.Substack)
    n = fill("01 Цинк", pos, color=(0.66, 0.66, 0.63), rough=0.38, metal=1.0)
    n = _soft(fill("02 Радужный налёт", _above(n), color=(0.72, 0.68, 0.48), rough=0.4))
    mask_proc(n, "3D_perlin_noise_fractal/3D_perlin_noise_fractal", None, scale=S_FINE)
    lop(n, 0.35)
    n = _proc("03 Точки ржавчины", _above(n), "grunge_rust_fine/grunge_rust_fine", S_FINE, 0.35, None,
              color=(0.34, 0.16, 0.06), rough=0.85, metal=0.0)
    n = fill("04 Грязь в гранях", _above(n), color=(0.15, 0.13, 0.10), rough=0.9, metal=0.0)
    _dirt(n, 0.5)
    lop(n, 0.75)
    return g


def brake_disc(st, meshes):
    """Тормозной диск брошенной машины: рабочее кольцо было натёрто колодками до блеска, за два года покрылось
    ржавым налётом пятнами; кромки и вентиляция — в ржавчине сплошь."""
    g = group("Тормозной диск", _top(st), meshes)
    pos = L.InsertPosition.inside_node(g, L.NodeStack.Substack)
    n = fill("01 Чугун натёртый", pos, color=(0.52, 0.52, 0.51), rough=0.32, metal=1.0)
    n = _proc("02 Риски от колодок", _above(n), "grunge_scratches_fine/grunge_scratches_fine", S_FINE * 2, 0.5,
              {"invert": 0, "balance": 0.36, "contrast": 0.55}, color=(0.62, 0.62, 0.61), rough=0.25)
    n = fill("03 Ржавый налёт", _above(n), color=(0.42, 0.21, 0.10), rough=0.85, metal=0.0)
    mk = mask_proc(n, "3D_perlin_noise_fractal/3D_perlin_noise_fractal", None, scale=S_FINE)
    _mfilter(mk, "histogram_scan", {"Position": 0.42, "Contrast": 0.5})
    lop(n, 0.75)
    n = fill("04 Ржавчина по кромкам", _above(n), color=(0.30, 0.13, 0.05), rough=0.92, metal=0.0)
    _edge(n, 0.35)
    n = fill("05 Грязь", _above(n), color=(0.15, 0.13, 0.10), rough=0.92, metal=0.0)
    _dirt(n, 0.5)
    lop(n, 0.6)
    return g


def wheel(st, have, ts="Wheel", style="steel", key=None):
    """Колесо v2 (набор ts): style — steel (штамповка), cap (колпак на штамповке), alloy (литой); key — вариант отделки
    (wheel_looks: цвет, глянец, износ). Обод (rim_barrel) — в одной краске с лицом диска, задиры от бордюров — только на
    нём (наружная закраина). Под колпаком — чёрная штамповка; колпачок литого — в цвет диска."""
    import importlib
    import wheel_looks
    importlib.reload(wheel_looks)
    lk = wheel_looks.look(style, key)

    def m(*mats):
        return pick(have, ts, *mats)
    tire(st, m("tire_tread"), m("rubber"), age=0.4 + 0.6 * lk["age"])
    lip = m("rim_barrel")
    if style == "alloy":
        if m("rim_alloy", "rim_barrel"):
            alloy_paint(st, m("rim_alloy", "rim_barrel"), lip, lk)
    elif m("rim_steel", "rim_barrel", "rim_alloy"):
        steel_paint(st, m("rim_steel", "rim_barrel", "rim_alloy"), lip,
                    wheel_looks.look("steel", "black") if style == "cap" else lk)
    if m("hubcap"):
        hubcap_plastic(st, m("hubcap"), lk)
    if m("lug_nut"):
        zinc(st, m("lug_nut"))
    if m("brake"):
        brake_disc(st, m("brake"))
    if m("brake_hat", "steel_dark"):
        rusty_steel(st, m("brake_hat", "steel_dark"), "Колокол и суппорт", base=(0.22, 0.21, 0.20), rust=0.8)
    if m("mesh_black"):
        plastic(st, m("mesh_black"), color=(0.02, 0.02, 0.02), rough=0.6, name="Чёрный пластик", fade=0.2)


def under_clean(st, have):
    def m(*mats):
        return pick(have, "Under", *mats)
    if m("liner"):
        plastic(st, m("liner"), color=(0.03, 0.03, 0.03), rough=0.8, name="Подкрылки", fade=0.1)
    if m("steel_dark", "rust"):
        rusty_steel(st, m("steel_dark", "rust"), "Низ — сталь", rust=0.8)
    if m("rubber"):
        rubber(st, m("rubber"), dust=0.8)
    if m("trim_black", "bumper_plastic", "mesh_black"):
        plastic(st, m("trim_black", "bumper_plastic", "mesh_black"), color=(0.03, 0.03, 0.03), rough=0.75,
                name="Пластик низа", fade=0.2)
    if m("chrome"):
        chrome(st, m("chrome"))


def uncovered(st, have):
    """Сетки набора, которых не коснулся ни один слой (в Painter остались бы белыми): список имён."""
    done = set()
    for n in L.get_root_layer_nodes(st):
        try:
            done |= set(n.get_geometry_mask_enabled_meshes())
        except Exception:
            pass
    return sorted(have - done)


# --- битая: удар спереди слева ---------------------------------------------------------------------

def crash_zone(layer, front=0.62, left=0.55):
    """Маска зоны удара: перёд машины и левый борт (генератор положения по двум осям)."""
    return _gen_mask(layer, POS, {"position_direction_topbottom_opacity": 0.0, "position_direction_frontback_opacity": 1.0,
                                  "position_direction_rightleft_opacity": 0.6, "position_balance": front,
                                  "position_contrast": 0.65, "position_invert": 0})


def body_wreck_damage(st, have, invert_front=0, invert_left=0, zone=0.73):
    """Поверх обычной краски — у носа слева (zone — граница зоны по длине, выше — уже): сдиры до грунта и до
    металла пятнами, свежие царапины, трещины краски по складкам смятия, брызги грязи от удара."""
    def m(*mats):
        return pick(have, "Body", *mats)
    g = group("Удар", _top(st), m("paint", "bumper", "trim_black", "chrome", "plate"))
    pos = L.InsertPosition.inside_node(g, L.NodeStack.Substack)

    def zoned(layer, shift=0.0, mul=False):
        p = crash_zone(layer, zone + shift)
        p.get_source().set_parameters({"position_invert": invert_front})
        if mul:
            p.set_blending_mode(L.BlendingMode.Multiply)
        return p
    n = fill("01 Сдиры до грунта", pos, color=(0.52, 0.52, 0.50), rough=0.72)
    zoned(n)
    mk = mask_proc(n, "grunge_paint_scraped/grunge_paint_scraped", None, scale=S_MID, blend=L.BlendingMode.Multiply)
    mk = _mfilter(mk, "warp", {"intensity": 0.3})
    _mfilter(mk, "histogram_scan", {"Position": 0.45, "Contrast": 0.7})
    lop(n, 0.85)
    n = fill("02 Сдиры до металла", _above(n), color=(0.55, 0.55, 0.55), rough=0.35, metal=0.95)
    zoned(n, 0.04)
    mask_proc(n, "grunge_scratches_rough/grunge_scratches_rough", None, scale=S_FINE, blend=L.BlendingMode.Multiply)
    n = fill("03 Трещины краски по складкам", _above(n), color=(0.12, 0.11, 0.10), rough=0.85)
    _gen_mask(n, "mg_curvature/mg_curvature")
    zoned(n, mul=True)
    lop(n, 0.65)
    n = fill("04 Брызги грязи", _above(n), color=(0.24, 0.21, 0.17), rough=0.92)
    zoned(n, -0.04)
    mask_proc(n, "grunge_dirt_splats/grunge_dirt_splats", None, scale=S_MID, blend=L.BlendingMode.Multiply)
    lop(n, 0.5)
    _sharpen(g, 0.25)
    return g


# --- сгоревшая -------------------------------------------------------------------------------------

def burnt_metal(st, meshes, paint_color=(0.8, 0.8, 0.8), name="Металл после пожара", ash=0.6, leftover=True):
    """Лист после пожара: окалина бурая, ржавчина пятнами, сажа по кромкам и в углах, пепел на горизонталях,
    белёсые разводы, внизу — остатки краски, вздувшейся пузырями."""
    g = group(name, _top(st), meshes)
    pos = L.InsertPosition.inside_node(g, L.NodeStack.Substack)
    n = fill("01 Окалина", pos, color=(0.16, 0.09, 0.055), rough=0.88, metal=0.25)
    n = _proc("02 Пятна тона", _above(n), "3D_perlin_noise_fractal/3D_perlin_noise_fractal", S_MID, 0.6, None,
              color=(0.10, 0.07, 0.05), rough=0.9)
    n = _proc("03 Ржавчина", _above(n), "grunge_rust_fine/grunge_rust_fine", S_MID, 0.6, None,
              color=(0.36, 0.17, 0.07), rough=0.92, metal=0.0)
    n = fill("04 Сажа", _above(n), color=(0.03, 0.03, 0.03), rough=0.95, metal=0.0)
    _gen_mask(n, DIRT, {"dirt_level": 0.6, "dirt_contrast": 0.5, "grunge_amount": 0.7, "Grunge_Scale": 5, "Use_Triplanar": 1})
    mask_proc(n, "grunge_charcoal/grunge_charcoal", None, scale=S_MID, blend=L.BlendingMode.Multiply)
    lop(n, 0.85)
    n = fill("05 Белёсые разводы", _above(n), color=(0.55, 0.52, 0.48), rough=0.9)
    smart_mask(n, "Water Drips")
    lop(n, 0.15)
    if leftover:
        n = fill("06 Остатки краски внизу", _above(n), color=tuple(c * 0.75 for c in paint_color), rough=0.75)
        _gen_mask(n, POS, low(0.18, 0.55))
        mask_proc(n, "grunge_paint_peeled/grunge_paint_peeled", None, scale=S_MID, blend=L.BlendingMode.Multiply)
        lop(n, 0.8)
    n = _soft(fill("06б Пятна: окалина темнее и светлее", _above(n), color=(0.36, 0.36, 0.36), rough=0.8))
    mk = mask_proc(n, "3D_perlin_noise_fractal/3D_perlin_noise_fractal", None, scale=0.6)
    _mfilter(mk, "histogram_scan", {"Position": 0.5, "Contrast": 0.5})
    n.set_opacity(0.6, sp_lib.CH.BaseColor)
    n.set_opacity(0.3, sp_lib.CH.SpecularRoughness)
    n = fill("07 Пепел", _above(n), color=(0.52, 0.50, 0.47), rough=0.97)
    _gen_mask(n, WSN, up(0.62, 0.8))
    mask_proc(n, "grunge_dusty_powder_wide/grunge_dusty_powder_wide", None, scale=S_MID, blend=L.BlendingMode.Multiply)
    lop(n, ash)
    _sharpen(g, 0.25)
    return g


def body_burnt(st, paint_color, have):
    def m(*mats):
        return pick(have, "Body", *mats)
    if m("burnt", "burnt_light"):
        burnt_metal(st, m("burnt", "burnt_light"), paint_color)
    if m("rust"):
        rusty_steel(st, m("rust"), "Брус и железо", base=(0.22, 0.12, 0.07), rust=0.9)
    if m("plate"):
        burnt_metal(st, m("plate"), (0.8, 0.8, 0.8), "Номера", leftover=False)


def any_burnt(st, prefix, have, name="После пожара"):
    mm = [x for x in have if x.startswith(prefix + "__")]
    if mm:
        burnt_metal(st, mm, name=name, leftover=False, ash=0.4)
