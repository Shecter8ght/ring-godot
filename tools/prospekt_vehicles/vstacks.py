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


def paint(st, meshes, color, rough=0.22, metal=0.0, age=1.0, jambs=None):
    """Автоэмаль под лаком, брошенная машина: выгорание сверху, сколы до грунта, царапины, подтёки с кромок,
    рыжие точки и ржавые подтёки внизу, грязь с земли, грязь в щелях, пыль на горизонталях. age — сила старения."""
    g = group("Краска", _top(st), meshes)
    pos = L.InsertPosition.inside_node(g, L.NodeStack.Substack)
    n = fill("01 Эмаль", pos, color=color, rough=rough, metal=metal)
    n = _proc("02 Шагрень лака", _above(n), "noise_gaussian_noise/gaussian_noise", 40.0, 0.25, rough=rough + 0.10)
    lighter = tuple(min(1.0, c * 1.06 + 0.04) for c in color)
    n = fill("03 Выгорание", _above(n), color=lighter, rough=rough + 0.25)
    _gen_mask(n, WSN, up(0.55, 0.45))
    mask_proc(n, "3D_perlin_noise_fractal/3D_perlin_noise_fractal", None, scale=S_MID, blend=L.BlendingMode.Multiply)
    lop(n, 0.6 * age)
    n = fill("04 Сколы до грунта", _above(n), color=(0.42, 0.42, 0.40), rough=0.7)
    _gen_mask(n, EDGE, {"Wear_Level": 0.10 + 0.08 * age, "Wear_Contrast": 0.8, "Grunge_Amount": 0.85, "grunge_scale": 6,
                        "Use_Triplanar": 1, "Edges_Smoothness": 0.3, "Ambient_Occlusion_Masking": 0.4,
                        "Curvature_Weight": 1.0})
    n = _proc("05 Царапины лака", _above(n), "grunge_scratches_fine/grunge_scratches_fine", S_FINE, 0.35 * age,
              {"invert": 0, "balance": 0.36, "contrast": 0.55}, rough=rough + 0.25)
    n = fill("06 Подтёки воды", _above(n), color=(0.42, 0.39, 0.34), rough=0.7)
    smart_mask(n, "Water Drips")
    lop(n, 0.55 * age)
    n = fill("07 Ржавчина по кромкам", _above(n), color=(0.34, 0.15, 0.06), rough=0.9)
    smart_mask(n, "Edge Rust")
    _gen_mul(n, POS, low(0.42, 0.35))
    lop(n, 0.9 * age)
    n = fill("08 Ржавые подтёки", _above(n), color=(0.38, 0.20, 0.09), rough=0.85)
    smart_mask(n, "Rust Drips")
    lop(n, 0.35 * age)
    n = fill("09 Грязь с земли", _above(n), color=(0.27, 0.23, 0.18), rough=0.92)
    smart_mask(n, "Dirt Ground")
    lop(n, 1.0 * age)
    n = fill("10 Грязь в щелях", _above(n), color=(0.12, 0.11, 0.09), rough=0.9)
    _gen_mask(n, DIRT, {"dirt_level": 0.30, "dirt_contrast": 0.7, "grunge_amount": 0.2, "Grunge_Scale": 6, "Use_Triplanar": 1})
    lop(n, 0.7 * age)
    n = fill("11 Пыль сверху", _above(n), color=(0.62, 0.58, 0.52), rough=0.95)
    smart_mask(n, "Dust Surface")
    _gen_mul(n, WSN, up(0.62, 0.6))             # умная маска пыли ложится и на борта — только на горизонтали
    lop(n, 0.85 * age)
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
    return g


def chrome(st, meshes):
    g = group("Хром", _top(st), meshes)
    pos = L.InsertPosition.inside_node(g, L.NodeStack.Substack)
    n = fill("01 Хром", pos, color=(0.78, 0.78, 0.78), rough=0.12, metal=1.0)
    n = _proc("02 Налёт", _above(n), "grunge_spots_dirty/grunge_spots_dirty", S_FINE, 0.5, None,
              color=(0.45, 0.43, 0.40), rough=0.45, metal=0.6)
    n = fill("03 Грязь", _above(n), color=(0.14, 0.12, 0.10), rough=0.9, metal=0.0)
    _gen_mask(n, DIRT, {"dirt_level": 0.45, "dirt_contrast": 0.7, "grunge_amount": 0.5, "Grunge_Scale": 6, "Use_Triplanar": 1})
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

def body_clean(st, paint_color, have, ts="Body"):
    """Набор кузова (Body или половина длинного — BodyA / BodyB): have — имена сеток проекта (только существующие)."""
    def m(*mats):
        return [f"{ts}__{x}" for x in mats if f"{ts}__{x}" in have]
    if m("paint", "bumper", "paint_inner"):
        paint(st, m("paint", "bumper", "paint_inner"), paint_color)
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


def interior_clean(st, have):
    def m(*mats):
        return [f"Interior__{x}" for x in mats if f"Interior__{x}" in have]
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
        plastic(st, m("seat_plastic"), color=(0.20, 0.05, 0.04), rough=0.45, name="Сиденья пластик", fade=0.5)
    if m("rail_yellow"):
        flat(st, m("rail_yellow"), "Поручни", (0.80, 0.58, 0.08), 0.4, dirt=0.4)
    if m("rubber"):
        rubber(st, m("rubber"))
    if m("steel_dark"):
        rusty_steel(st, m("steel_dark"), "Каркасы", rust=0.3)
    if m("paint_inner", "paint"):
        flat(st, m("paint_inner", "paint"), "Окрашенный металл салона", (0.5, 0.5, 0.5), 0.5)


def wheel_clean(st, have, alloy=False):
    def m(*mats):
        return [f"Wheel__{x}" for x in mats if f"Wheel__{x}" in have]
    if m("rubber"):
        g = group("Шина", _top(st), m("rubber"))
        pos = L.InsertPosition.inside_node(g, L.NodeStack.Substack)
        n = fill("01 Резина", pos, color=(0.03, 0.03, 0.03), rough=0.82)
        n = fill("02 Пыль в рисунке протектора", _above(n), color=(0.22, 0.21, 0.19), rough=0.95)
        _gen_mask(n, DIRT, {"dirt_level": 0.30, "dirt_contrast": 0.7, "grunge_amount": 0.5, "Grunge_Scale": 6, "Use_Triplanar": 1})
        lop(n, 0.3)
        n = fill("03 Грязь снизу", _above(n), color=(0.20, 0.18, 0.15), rough=0.95)
        smart_mask(n, "Dirt Ground")
        lop(n, 0.3)
    if m("rim_steel"):
        rusty_steel(st, m("rim_steel"), "Диск штампованный", base=(0.30, 0.30, 0.31), rust=0.35)
    if m("rim_alloy"):
        g = flat(st, m("rim_alloy"), "Литой диск", (0.62, 0.63, 0.65), 0.3, metal=1.0, dirt=0.6)
        n = fill("03 Тормозная пыль", L.InsertPosition.inside_node(g, L.NodeStack.Substack), color=(0.30, 0.24, 0.18), rough=0.85, metal=0.0)
        _gen_mask(n, DIRT, {"dirt_level": 0.6, "dirt_contrast": 0.5, "grunge_amount": 0.6, "Grunge_Scale": 5, "Use_Triplanar": 1})
        lop(n, 0.75)
    if m("hubcap"):
        g = flat(st, m("hubcap"), "Колпак", (0.60, 0.61, 0.63), 0.35, metal=0.4, dirt=0.65)
        n = fill("03 Тормозная пыль", L.InsertPosition.inside_node(g, L.NodeStack.Substack), color=(0.30, 0.24, 0.18), rough=0.85)
        _gen_mask(n, DIRT, {"dirt_level": 0.55, "dirt_contrast": 0.5, "grunge_amount": 0.6, "Grunge_Scale": 5, "Use_Triplanar": 1})
        lop(n, 0.7)
    if m("mesh_black"):
        plastic(st, m("mesh_black"), color=(0.02, 0.02, 0.02), rough=0.7, name="Прорези", fade=0.2)
    if m("brake", "steel_dark"):
        rusty_steel(st, m("brake", "steel_dark"), "Тормоз", base=(0.25, 0.24, 0.23), rust=0.8)


def under_clean(st, have):
    def m(*mats):
        return [f"Under__{x}" for x in mats if f"Under__{x}" in have]
    if m("liner"):
        plastic(st, m("liner"), color=(0.03, 0.03, 0.03), rough=0.8, name="Подкрылки", fade=0.1)
    if m("steel_dark", "rust"):
        rusty_steel(st, m("steel_dark", "rust"), "Низ — сталь", rust=0.8)


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
        return [f"Body__{x}" for x in mats if f"Body__{x}" in have]
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
    mask_proc(n, "grunge_paint_scraped/grunge_paint_scraped", None, scale=S_MID, blend=L.BlendingMode.Multiply)
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
    n = fill("07 Пепел", _above(n), color=(0.52, 0.50, 0.47), rough=0.97)
    _gen_mask(n, WSN, up(0.62, 0.8))
    mask_proc(n, "grunge_dusty_powder_wide/grunge_dusty_powder_wide", None, scale=S_MID, blend=L.BlendingMode.Multiply)
    lop(n, ash)
    return g


def body_burnt(st, paint_color, have):
    def m(*mats):
        return [f"Body__{x}" for x in mats if f"Body__{x}" in have]
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
