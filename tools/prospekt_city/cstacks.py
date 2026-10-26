"""«Проспект», ограждения и город: стеки слоёв Substance Painter для городских материалов (внутри Painter через мост).

Город брошен года два назад, а сами вещи старые: бетону и железу по 20–40 лет. Слои — заливки (sp_lib) с материалами
полки Painter (литой бетон, оцинковка, ржавчина) и процедурными масками; генераторы по положению (низ — грязь с земли),
нормалям мира (верх — пыль, мох), кривизне (сколы кромок), стекающим подтёкам (сырость, ржавчина) и полостям (грязь).
По детали — маски геометрии: сетки FBX «<набор>__<материал>» (game.py). Цвета — sRGB (sp_lib переводит).
Масштаб трёхпроекционных масок — множитель к размеру сцены проекта (сцена ПО-2 ≈ 6 м: 4 — пятна ≈ 1,5 м).
"""
import substance_painter.layerstack as L

import sp_lib
from sp_lib import fill, lop, mask_generator, mask_proc, only_meshes, triplanar

EDGE = "mg_metal_edge_wear/mg_metal_edge_wear"
DIRT = "mg_dirt/mg_dirt"
POS = "mg_position/mg_position"
WSN = "mg_world_space_normals/mg_world_space_normals"
DRIP = "mg_dripping_rust/mg_dripping_rust"
MUL = L.BlendingMode.Multiply


def above(n):
    return L.InsertPosition.above_node(n)


def top(st):
    return L.InsertPosition.from_textureset_stack(st)


def inside(g):
    return L.InsertPosition.inside_node(g, L.NodeStack.Substack)


def group(name, st, meshes):
    g = L.insert_group(top(st))
    g.set_name(name)
    only_meshes(g, meshes)
    return g


def material_fill(name, pos, mat, scale, params=None, chans=("color", "rough", "metal", "height")):
    """Заливка материалом полки Painter (трёхпроекционно); params — его параметры (цвета — кортежем sRGB)."""
    f = L.insert_fill(pos)
    f.set_name(name)
    f.active_channels = {sp_lib.CHAN[c] for c in chans}
    src = f.set_material_source(sp_lib.rid(mat, "u:material"))
    if params:
        p = {}
        for k, v in params.items():
            p[k] = sp_lib._val(v) if isinstance(v, tuple) else v
        src.set_parameters(p)
    triplanar(f, scale)
    return f


def up(balance=0.5, contrast=0.4):
    """Генератор нормали мира: белое на гранях, обращённых вверх."""
    return {"ws_direction_topbottom_opacity": 1.0, "ws_direction_rightleft_opacity": 0.0,
            "ws_direction_frontback_opacity": 0.0, "ws_balance": balance, "ws_contrast": contrast}


def low(balance=0.3, contrast=0.5):
    """Генератор положения: белое внизу предмета."""
    return {"position_direction_topbottom_opacity": 1.0, "position_direction_rightleft_opacity": 0.0,
            "position_direction_frontback_opacity": 0.0, "position_invert": 1, "position_balance": balance,
            "position_contrast": contrast}


def high(balance=0.7, contrast=0.5):
    """Генератор положения: белое вверху предмета."""
    p = low(balance, contrast)
    p["position_invert"] = 0
    return p


def layer_proc(name, pos, proc, scale, opacity, params=None, **ch):
    lay = fill(name, pos, **ch)
    mask_proc(lay, proc, params, scale=scale)
    lop(lay, opacity)
    return lay


# ---------------------------------------------------------------------------------------------- бетон

def concrete(st, meshes, color=(0.60, 0.59, 0.56), age=1.0, moss=1.0, name="Бетон"):
    """Старый литой бетон на улице: тон пятнами, сырость, потёки с верхних кромок, грязь в ложбинах, брызги грязи
    снизу, мох внизу и на верхних гранях, сколы кромок, пыль сверху, высолы."""
    g = group(name, st, meshes)
    n = fill("00 Цвет бетона", inside(g), color=color, rough=0.88, metal=0.0)
    n = material_fill("01 Литой бетон: поры и каверны", above(n), "concrete_cast/concrete_cast", 4.0,
                      {"concrete_roughness": 0.86, "concrete_roughness_variation": 0.4, "cracks_spread": 0.12,
                       "cracks_scale": 0.9}, chans=("height",))
    n = layer_proc("01б Зерно", above(n), "noise_gaussian_noise/gaussian_noise", 30.0, 0.25,
                   color=tuple(c * 0.9 for c in color), rough=0.92)
    n = noises(above(n), color, 0.88, [("noise_clouds_2/clouds_2", 6.0, -0.08, 0.05, 0.35),
                                        ("grunge_concrete_spots/grunge_concrete_spots", 5.0, -0.12, -0.04, 0.3),
                                        ("noise_bnw_spots_2/bnw_spots_2", 12.0, 0.06, 0.04, 0.2)])
    n = layer_proc("02 Тон пятнами", above(n), "grunge_concrete_old/grunge_concrete_old", 3.0, 0.30,
                   color=tuple(c * 0.86 for c in color), rough=0.9)
    n = layer_proc("03 Сырость", above(n), "grunge_humidity/grunge_humidity", 2.0, 0.22 * age,
                   color=tuple(c * 0.74 for c in color), rough=0.8)
    n = fill("04 Потёки с верха", above(n), color=tuple(c * 0.62 for c in color), rough=0.8)
    mask_generator(n, DRIP, {"Rust_Spreading": 0.2, "Rust_Contrast": 0.65, "Drips_Intensity": 1.0,
                             "Drips_Smoothness": 0.2, "Drips_Samples_Amount": 24})
    mask_proc(n, "grunge_leaks/grunge_leaks", None, scale=2.5, blend=L.BlendingMode.Screen, opacity=0.5)
    lop(n, 0.7 * age)
    n = fill("05 Грязь в ложбинах", above(n), color=(0.24, 0.23, 0.20), rough=0.92)
    mask_generator(n, DIRT, {"dirt_level": 0.22, "dirt_contrast": 0.75, "grunge_amount": 0.5, "Grunge_Scale": 6,
                             "Use_Triplanar": 1})
    lop(n, 0.5 * age)
    n = fill("06 Грязь с земли", above(n), color=(0.27, 0.23, 0.18), rough=0.95)
    mask_generator(n, POS, low(0.28, 0.55))
    mask_proc(n, "grunge_dirt_splats/grunge_dirt_splats", None, scale=4.0, blend=MUL)
    lop(n, 0.9 * age)
    n = fill("07 Мох внизу", above(n), color=(0.20, 0.23, 0.13), rough=0.97)
    mask_generator(n, POS, low(0.12, 0.6))
    mask_proc(n, "grunge_concrete_moss_small/grunge_concrete_moss_small", None, scale=3.0, blend=MUL)
    lop(n, 0.6 * moss)
    n = fill("08 Мох и лишайник сверху", above(n), color=(0.24, 0.26, 0.16), rough=0.97)
    mask_generator(n, WSN, up(0.62, 0.55))
    mask_proc(n, "grunge_concrete_moss_medium/grunge_concrete_moss_medium", None, scale=4.0, blend=MUL)
    lop(n, 0.55 * moss)
    n = fill("09 Сколы кромок", above(n), color=tuple(min(1.0, c * 1.14) for c in color), rough=0.97)
    mask_generator(n, EDGE, {"Wear_Level": 0.12 + 0.08 * age, "Wear_Contrast": 0.75, "Grunge_Amount": 0.9,
                             "grunge_scale": 5, "Use_Triplanar": 1, "Edges_Smoothness": 0.2,
                             "Ambient_Occlusion_Masking": 0.3, "Curvature_Weight": 1.0})
    n = soft_light("09б Пятна светлее (Soft Light)", above(n), (0.72, 0.72, 0.72), 1.0, 0.35, rough=0.95)
    n = soft_light("09в Пятна темнее (Soft Light)", above(n), (0.30, 0.30, 0.30), 1.4, 0.3, rough=0.8)
    n = fill("10 Пыль сверху", above(n), color=(0.60, 0.57, 0.52), rough=0.97)
    mask_generator(n, WSN, up(0.58, 0.5))
    mask_proc(n, "grunge_dusty_powder_soft/grunge_dusty_powder_soft", None, scale=4.0, blend=MUL)
    lop(n, 0.6 * age)
    n = layer_proc("11 Высолы", above(n), "grunge_leak_spots/grunge_leak_spots", 3.0, 0.22 * age,
                   color=(0.74, 0.73, 0.69), rough=0.97)
    return g


# ---------------------------------------------------------------------------------------------- металл

def galvanized(st, meshes, age=1.0, name="Оцинковка"):
    """Оцинкованная сталь годами на улице: тусклый цинк пятнами белой ржавчины, рыжие точки и кромки, подтёки, грязь."""
    g = group(name, st, meshes)
    n = material_fill("01 Оцинковка", inside(g), "metal_galvanized/metal_galvanized", 6.0,
                      {"metal_color": (0.66, 0.67, 0.66), "metal_roughness": 0.5})
    # старый цинк — матовый, почти не зеркалит: без неба в отражениях (двор, тень) «чистый металл» выходит чёрным
    n = fill("02 Матовый цинк", above(n), color=(0.60, 0.61, 0.60), rough=0.62, metal=0.55)
    lop(n, 0.85)
    n = layer_proc("02б Тусклый налёт", above(n), "grunge_galvanic_small/grunge_galvanic_small", 6.0, 0.6,
                   color=(0.55, 0.56, 0.55), rough=0.7, metal=0.45)
    n = layer_proc("03 Белая ржавчина", above(n), "grunge_spots_dirty/grunge_spots_dirty", 5.0, 0.35 * age,
                   color=(0.72, 0.72, 0.69), rough=0.85, metal=0.2)
    n = fill("04 Ржавчина по кромкам", above(n), color=(0.34, 0.17, 0.08), rough=0.9, metal=0.15)
    mask_generator(n, EDGE, {"Wear_Level": 0.10 * age, "Wear_Contrast": 0.8, "Grunge_Amount": 0.85, "grunge_scale": 8,
                             "Use_Triplanar": 1, "Edges_Smoothness": 0.25})
    mask_proc(n, "grunge_rust_fine/grunge_rust_fine", None, scale=8.0, blend=MUL)
    n = fill("05 Ржавые подтёки", above(n), color=(0.38, 0.20, 0.09), rough=0.85, metal=0.1)
    mask_generator(n, DRIP, {"Rust_Spreading": 0.2, "Drips_Intensity": 0.7, "Drips_Samples_Amount": 12})
    lop(n, 0.45 * age)
    n = fill("06 Грязь", above(n), color=(0.22, 0.20, 0.16), rough=0.9, metal=0.0)
    mask_generator(n, DIRT, {"dirt_level": 0.35, "dirt_contrast": 0.6, "grunge_amount": 0.5, "Use_Triplanar": 1})
    lop(n, 0.6 * age)
    return g


def rusty_steel(st, meshes, name="Ржавая сталь", scale=10.0):
    """Сталь без покрытия, давно ржавая (арматура, петли): ржавчина с тёмными и рыжими пятнами, грязь."""
    g = group(name, st, meshes)
    n = material_fill("01 Ржавчина", inside(g), "metal_rust/metal_rust", scale,
                      {"rust_color": (0.32, 0.17, 0.09), "rust_roughness": 0.8})
    n = layer_proc("02 Тёмная окалина", above(n), "grunge_rust_fine/grunge_rust_fine", scale, 0.5,
                   color=(0.15, 0.10, 0.07), rough=0.75, metal=0.3)
    n = fill("03 Грязь", above(n), color=(0.20, 0.18, 0.15), rough=0.95, metal=0.0)
    mask_generator(n, DIRT, {"dirt_level": 0.4, "dirt_contrast": 0.5, "Use_Triplanar": 1})
    lop(n, 0.5)
    return g


FILTER_SHARPEN = "sharpen/sharpen"
FILTER_WARP = "warp/warp"
FILTER_SCAN = "histogram_scan/histogram_scan"
FILTER_BLUR = "blur/blur"


def mask_filter(layer, flt, params=None):
    """Фильтр в маске слоя поверх того, что в ней уже есть (Warp, Blur, Histogram Scan — маска читается издали)."""
    f = L.insert_filter_effect(L.InsertPosition.inside_node(layer, L.NodeStack.Mask), sp_lib.rid(flt, "u:filter"))
    if params:
        f.get_source().set_parameters(params)
    return f


def soft_light(name, pos, color, scale, opacity, rough=None):
    """Крупные пятна света и тени режимом Soft Light (навык: Normal съедает мелкую вариацию под пятном); каналы
    связаны — у пятна в цвете пара в шероховатости (rough — её значение, Normal по той же маске, слабее)."""
    ch = {"color": color}
    if rough is not None:
        ch["rough"] = rough
    n = fill(name, pos, **ch)
    n.set_blending_mode(L.BlendingMode.SoftLight, sp_lib.CHAN["color"])
    mask_proc(n, "3D_perlin_noise_fractal/3D_perlin_noise_fractal", None, scale=scale)
    lop(n, opacity)
    if rough is not None:
        n.set_opacity(opacity * 0.5, sp_lib.CHAN["rough"])
    return n


def noises(pos, base_color, base_rough, specs):
    """Шумы для крупного плана — несколько разных (навык: 3–5, а не один); каждый сдвигает цвет и шероховатость
    вместе. specs — [(процедура, масштаб, сдвиг тона, сдвиг шероховатости, непрозрачность)]."""
    n = None
    for i, (proc, scale, dc, dr, op) in enumerate(specs):
        col = tuple(min(1.0, max(0.0, c * (1.0 + dc))) for c in base_color)
        n = layer_proc(f"Шум {i + 1}: {proc.split('/')[0]}", pos if n is None else above(n), proc, scale, op,
                       color=col, rough=min(1.0, max(0.0, base_rough + dr)))
    return n


# Высота краски — уровень: без слоя канал высоты 0, поэтому основа краски задаёт уровень 0,5 (как coat у принятого
# стека ВСС-М), полосы кисти чуть выше, сколы — грунт и металл — на тысячные ниже. Без основы сколы 0,45 стояли на
# 0,45 над листом — «корой» на гофре контейнера.
PAINT_LEVEL = 0.5
PAINT_RELIEF = 0.508
CHIP_PRIMER = 0.49
CHIP_METAL = 0.482


def painted_steel(st, meshes, color, name="Краска", age=1.0, rough=0.55, rust=1.0):
    """Крашеная сталь (ворота, контейнеры, будки) по приёмам навыка «дерево и крашеный металл»: краска с вариациями
    и рельефом (неровный слой, полосы кисти), крупные пятна Soft Light, светлые выгоревшие кромки, сколы «крупное —
    среднее — мелкое» с ободком грунта, под краской — окисленный металл (Metallic ≈ 0,9, не чистый), ржавчина местами
    и обесцвеченная, подтёки, грязь снизу, грязь в щелях, матовая пыль. Лёгкая резкость — после выгрузки
    (sharpen_maps.py: в API Painter фильтр поверх слоёв не ставится)."""
    g = group(name, st, meshes)
    lighter = tuple(min(1.0, c * 1.12 + 0.05) for c in color)
    darker = tuple(c * 0.82 for c in color)
    n = fill("01 Краска", inside(g), color=color, rough=rough, metal=0.0, height=PAINT_LEVEL)
    n = layer_proc("02 Вариация краски: тон", above(n), "grunge_wipe_smudgy_soft/grunge_wipe_smudgy_soft", 3.0, 0.45,
                   color=darker, rough=min(1.0, rough + 0.08))
    n = layer_proc("03 Вариация краски: глянец", above(n), "grunge_wipe_brushed/grunge_wipe_brushed", 4.0, 0.5,
                   rough=max(0.0, rough - 0.12))
    n = fill("04 Рельеф краски: полосы кисти и наплывы", above(n), rough=min(1.0, rough + 0.06), height=PAINT_RELIEF)
    mask_proc(n, "grunge_brushed/grunge_brushed", None, scale=5.0)
    mask_filter(n, FILTER_BLUR, {"intensity": 0.3})
    mask_filter(n, FILTER_WARP, {"intensity": 0.15})
    mask_filter(n, FILTER_SCAN, {"Position": 0.45, "Contrast": 0.55})
    lop(n, 0.6)
    n = soft_light("05 Пятна светлее (Soft Light)", above(n), (0.75, 0.75, 0.75), 1.2, 0.5, rough=min(1.0, rough + 0.15))
    n = soft_light("06 Пятна темнее (Soft Light)", above(n), (0.25, 0.25, 0.25), 1.6, 0.45, rough=max(0.0, rough - 0.1))
    n = noises(above(n), color, rough, [("noise_clouds_2/clouds_2", 6.0, -0.06, 0.06, 0.3),
                                        ("grunge_spots_dirty/grunge_spots_dirty", 6.0, -0.1, 0.1, 0.25),
                                        ("blue_noise/blue_noise_fast", 20.0, 0.04, 0.05, 0.15)])
    n = fill("07 Выгорела сверху", above(n), color=lighter, rough=min(1.0, rough + 0.25))
    mask_generator(n, WSN, up(0.5, 0.4))
    mask_proc(n, "3D_perlin_noise_fractal/3D_perlin_noise_fractal", None, scale=2.5, blend=MUL)
    lop(n, 0.5 * age)
    n = fill("08 Светлые кромки: краска стёрта и выгорела", above(n), color=lighter, rough=min(1.0, rough + 0.2))
    mask_generator(n, EDGE, {"Wear_Level": 0.22 * age, "Wear_Contrast": 0.5, "Grunge_Amount": 0.7, "grunge_scale": 4,
                             "Use_Triplanar": 1, "Edges_Smoothness": 0.5})
    lop(n, 0.7)
    # сколы: грунт шире (ободок отслаивания), металл внутри уже; крупные пятна — от отслоившейся краски, средние и
    # мелкие — по кромкам
    for tag, lvl, scale in (("крупные", 0.16, 2.5), ("средние", 0.12, 5.0), ("мелкие", 0.09, 9.0)):
        n = fill(f"09 Сколы {tag}: грунт", above(n), color=(0.47, 0.44, 0.40), rough=0.82, height=CHIP_PRIMER)
        mask_generator(n, EDGE, {"Wear_Level": lvl * age, "Wear_Contrast": 0.85, "Grunge_Amount": 0.9,
                                 "grunge_scale": int(scale), "Use_Triplanar": 1, "Edges_Smoothness": 0.25})
        mask_proc(n, "grunge_paint_peeled/grunge_paint_peeled", None, scale=scale, blend=MUL)
        mask_filter(n, FILTER_SCAN, {"Position": 0.5, "Contrast": 0.7})
        n = fill(f"10 Сколы {tag}: окисленный металл", above(n), color=(0.23, 0.21, 0.19), rough=0.6, metal=0.88,
                 height=CHIP_METAL)
        mask_generator(n, EDGE, {"Wear_Level": lvl * 0.7 * age, "Wear_Contrast": 0.9, "Grunge_Amount": 0.9,
                                 "grunge_scale": int(scale), "Use_Triplanar": 1, "Edges_Smoothness": 0.2})
        mask_proc(n, "grunge_paint_peeled/grunge_paint_peeled", None, scale=scale, blend=MUL)
    n = fill("11 Ржавчина местами, обесцвеченная", above(n), color=(0.36, 0.20, 0.11), rough=0.88, metal=0.25)
    mask_generator(n, EDGE, {"Wear_Level": 0.07 * age * rust, "Wear_Contrast": 0.9, "Grunge_Amount": 0.95,
                             "grunge_scale": 7, "Use_Triplanar": 1, "Edges_Smoothness": 0.2})
    mask_proc(n, "grunge_rust_fine/grunge_rust_fine", None, scale=8.0, blend=MUL)
    n = layer_proc("12 Царапины", above(n), "grunge_scratches_rough/grunge_scratches_rough", 5.0, 0.3 * age,
                   {"invert": 0}, color=(0.42, 0.40, 0.36), rough=0.75)
    n = fill("13 Ржавые подтёки", above(n), color=(0.36, 0.18, 0.08), rough=0.85)
    mask_generator(n, DRIP, {"Rust_Spreading": 0.25, "Drips_Intensity": 0.8, "Drips_Samples_Amount": 14})
    lop(n, 0.4 * age * rust)
    n = fill("14 Грязь снизу", above(n), color=(0.25, 0.22, 0.17), rough=0.95)
    mask_generator(n, POS, low(0.25, 0.5))
    mask_proc(n, "grunge_dirt_splats/grunge_dirt_splats", None, scale=4.0, blend=MUL)
    lop(n, 0.8 * age)
    n = fill("15 Грязь в щелях", above(n), color=(0.15, 0.13, 0.11), rough=0.92)
    mask_generator(n, DIRT, {"dirt_level": 0.3, "dirt_contrast": 0.65, "grunge_amount": 0.4, "Use_Triplanar": 1})
    lop(n, 0.6 * age)
    n = fill("16 Пыль сверху: матовая, без рельефа", above(n), color=(0.58, 0.55, 0.50), rough=0.97)
    mask_generator(n, WSN, up(0.58, 0.5))
    mask_proc(n, "grunge_dusty_powder_soft/grunge_dusty_powder_soft", None, scale=4.0, blend=MUL)
    lop(n, 0.5 * age)
    return g


def mortar(st, meshes, name="Раствор"):
    g = group(name, st, meshes)
    n = material_fill("01 Раствор", inside(g), "concrete_coarse/concrete_coarse", 8.0,
                      {"concrete_color": (0.60, 0.59, 0.55), "concrete_roughness": 0.92, "Damage_intensity": 0.35})
    n = fill("02 Грязь", above(n), color=(0.24, 0.21, 0.17), rough=0.95)
    mask_generator(n, DIRT, {"dirt_level": 0.45, "dirt_contrast": 0.5, "Use_Triplanar": 1})
    lop(n, 0.7)
    return g
