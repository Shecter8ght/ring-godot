# Задание Painter: стек слоёв гаражей (наборы GarageBrick, Garage, GarageInt, GarageProps, Shell). Гаражи ГСК 1980-х:
# белый силикатный кирпич с серыми швами, по низу — грязь и зелень, с плит — потёки; плиты и цоколь — старый бетон;
# рубероид битумный, в пыли и мху; ворота — коричневая масляная краска по металлу, выгорела, в сколах до ржавчины;
# внутри — закопчённая кладка, пол в масляных пятнах. Ракушка — зелёная краска по оцинковке, выгорела, ржавчина снизу
# и по кромкам. Стек пересобирается с нуля (sp_lib.clear). Свои помощники — здесь, общие — cstacks.
import importlib

import substance_painter.layerstack as L

import cstacks
import sp_lib
from cstacks import DIRT, DRIP, EDGE, POS, WSN, MUL, above, inside, group, layer_proc, low, material_fill, up
from sp_lib import fill, lop, mask_generator, mask_proc

importlib.reload(cstacks)

BRICK = (0.84, 0.82, 0.76)            # силикатный кирпич, sRGB
AO = "mg_ambient_occlusion/mg_ambient_occlusion"
MORTAR = (0.56, 0.55, 0.51)


def brick_wall(st, meshes, name="Кладка", outside=True):
    """Кладка из белого силикатного кирпича: швы — по запечённым полостям (кирпич выступает на 8 мм)."""
    g = group(name, st, meshes)
    n = fill("00 Кирпич", inside(g), color=BRICK, rough=0.88)
    n = material_fill("01 Фактура кирпича", above(n), "concrete_coarse/concrete_coarse", 12.0,
                      {"Damage_intensity": 0.25, "damage_scale": 0.5}, chans=("height",))
    lop(n, 0.3)                                  # мелкий рельеф кирпича — слегка, иначе шумят нормали
    n = layer_proc("02 Разнотон", above(n), "noise_cells_2/cells_2", 9.0, 0.20, color=(0.72, 0.70, 0.64), rough=0.9)
    n = layer_proc("03 Пятна", above(n), "grunge_concrete_spots/grunge_concrete_spots", 4.0, 0.25,
                   color=(0.68, 0.66, 0.60), rough=0.9)
    n = fill("04 Раствор в швах", above(n), color=MORTAR, rough=0.95)
    mask_generator(n, AO, {"ao_invert": 1, "ao_balance": 0.62, "ao_contrast": 0.75})   # швы — затенённое
    n = fill("05 Сколы кирпичей", above(n), color=(0.86, 0.84, 0.79), rough=0.95)
    mask_generator(n, EDGE, {"Wear_Level": 0.02, "Wear_Contrast": 0.9, "Grunge_Amount": 1.0, "grunge_scale": 4,
                             "Use_Triplanar": 1, "Edges_Smoothness": 0.1})
    mask_proc(n, "noise_bnw_spots_2/bnw_spots_2", None, scale=6.0, blend=MUL)     # сколы редкими кусками, не обводкой
    lop(n, 0.3)
    if outside:
        n = fill("06 Потёки с плит", above(n), color=(0.46, 0.45, 0.41), rough=0.85)
        mask_generator(n, cstacks.POS, cstacks.high(0.72, 0.6))
        mask_proc(n, "grunge_leaks/grunge_leaks", None, scale=3.0, blend=MUL)
        lop(n, 0.7)
        n = fill("07 Грязь с земли", above(n), color=(0.33, 0.29, 0.23), rough=0.95)
        mask_generator(n, POS, low(0.18, 0.6))
        mask_proc(n, "grunge_dirt_splats/grunge_dirt_splats", None, scale=4.0, blend=MUL)
        lop(n, 0.9)
        n = fill("08 Зелень внизу", above(n), color=(0.30, 0.34, 0.22), rough=0.95)
        mask_generator(n, POS, low(0.10, 0.6))
        mask_proc(n, "grunge_concrete_moss_small/grunge_concrete_moss_small", None, scale=3.0, blend=MUL)
        lop(n, 0.55)
        n = layer_proc("09 Сырость", above(n), "grunge_humidity/grunge_humidity", 2.0, 0.25, color=(0.58, 0.57, 0.52),
                       rough=0.82)
    else:
        n = fill("06 Копоть и пыль", above(n), color=(0.42, 0.40, 0.36), rough=0.93)
        mask_proc(n, "grunge_dirt_large/grunge_dirt_large", None, scale=2.5)
        lop(n, 0.55)
        n = fill("07 Мазки у пола", above(n), color=(0.24, 0.22, 0.19), rough=0.85)
        mask_generator(n, POS, low(0.15, 0.5))
        mask_proc(n, "grunge_wipe_smudgy_heavy/grunge_wipe_smudgy_heavy", None, scale=3.0, blend=MUL)
        lop(n, 0.6)
    n = fill("10 Грязь в швах", above(n), color=(0.30, 0.28, 0.24), rough=0.95)
    mask_generator(n, DIRT, {"dirt_level": 0.55, "dirt_contrast": 0.7, "grunge_amount": 0.5, "Use_Triplanar": 1})
    lop(n, 0.35)
    return g


def roofing(st, meshes, name="Рубероид"):
    g = group(name, st, meshes)
    n = fill("01 Битум", inside(g), color=(0.11, 0.11, 0.11), rough=0.78)
    n = material_fill("02 Посыпка", above(n), "concrete_asphalt/concrete_asphalt", 10.0, None, chans=("height",))
    n = layer_proc("03 Выгорел", above(n), "grunge_wipe_dusty/grunge_wipe_dusty", 3.0, 0.6, color=(0.24, 0.23, 0.22),
                   rough=0.9)
    n = fill("04 Пыль и сор", above(n), color=(0.45, 0.42, 0.37), rough=0.97)
    mask_generator(n, WSN, up(0.5, 0.4))
    mask_proc(n, "grunge_dusty_powder_wide/grunge_dusty_powder_wide", None, scale=3.0, blend=MUL)
    lop(n, 0.75)
    n = layer_proc("05 Мох", above(n), "grunge_concrete_moss_medium/grunge_concrete_moss_medium", 3.0, 0.35,
                   color=(0.25, 0.29, 0.17), rough=0.97)
    n = fill("06 Потёки с кромки", above(n), color=(0.06, 0.06, 0.06), rough=0.6)
    mask_generator(n, DRIP, {"Rust_Spreading": 0.2, "Drips_Intensity": 0.8, "Drips_Samples_Amount": 16})
    lop(n, 0.5)
    return g


def floor_concrete(st, meshes, name="Пол"):
    g = group(name, st, meshes)
    n = fill("01 Бетон пола", inside(g), color=(0.50, 0.49, 0.46), rough=0.85)
    n = material_fill("02 Фактура", above(n), "concrete_cast/concrete_cast", 6.0, {"cracks_spread": 0.25}, chans=("height",))
    n = layer_proc("03 Затёртость", above(n), "grunge_wipe_brushed_large/grunge_wipe_brushed_large", 2.0, 0.4,
                   color=(0.42, 0.41, 0.38), rough=0.75)
    n = layer_proc("04 Масляные пятна", above(n), "grunge_stains_heavy/grunge_stains_heavy", 2.5, 0.75,
                   color=(0.13, 0.12, 0.11), rough=0.38)
    n = layer_proc("05 Пыль", above(n), "grunge_dusty_powder_soft/grunge_dusty_powder_soft", 3.0, 0.5,
                   color=(0.56, 0.53, 0.48), rough=0.95)
    n = fill("06 Грязь по углам", above(n), color=(0.22, 0.20, 0.17), rough=0.95)
    mask_generator(n, DIRT, {"dirt_level": 0.4, "dirt_contrast": 0.5, "Use_Triplanar": 1})
    lop(n, 0.7)
    return g


def simple(st, meshes, name, color, rough, metal=0.0, mat=None, scale=8.0, params=None, wear=0.6):
    """Вещь в гараже: основа (цвет или материал полки), грязь в полостях, пыль сверху, потёртые кромки."""
    g = group(name, st, meshes)
    if mat:
        n = material_fill("01 " + name, inside(g), mat, scale, params)
    else:
        n = fill("01 " + name, inside(g), color=color, rough=rough, metal=metal)
    n = layer_proc("02 Неровность", above(n), "grunge_wipe_smudgy_soft/grunge_wipe_smudgy_soft", 4.0, 0.35,
                   rough=min(1.0, rough + 0.15))
    n = fill("03 Потёрто по кромкам", above(n), color=tuple(min(1.0, c * 1.25 + 0.04) for c in color), rough=rough)
    mask_generator(n, EDGE, {"Wear_Level": 0.08, "Wear_Contrast": 0.8, "Grunge_Amount": 0.8, "Use_Triplanar": 1})
    lop(n, 0.5 * wear)
    n = fill("04 Грязь", above(n), color=(0.18, 0.16, 0.13), rough=0.95, metal=0.0)
    mask_generator(n, DIRT, {"dirt_level": 0.35, "dirt_contrast": 0.55, "Use_Triplanar": 1})
    lop(n, 0.6 * wear)
    n = fill("05 Пыль сверху", above(n), color=(0.55, 0.52, 0.47), rough=0.97, metal=0.0)
    mask_generator(n, WSN, up(0.55, 0.45))
    mask_proc(n, "grunge_dusty_powder_soft/grunge_dusty_powder_soft", None, scale=5.0, blend=MUL)
    lop(n, 0.7 * wear)
    return g


def stack_of(ts):
    return sp_lib.stack_by_name(ts)


# ---- кладка снаружи
st = stack_of("GarageBrick")
sp_lib.clear(st)
brick_wall(st, ["GarageBrick__brick"], outside=True)

# ---- плиты, цоколь, пандус, рубероид, ворота, петли
st = stack_of("Garage")
sp_lib.clear(st)
cstacks.concrete(st, ["Garage__concrete"], color=(0.56, 0.55, 0.52), moss=0.6)
roofing(st, ["Garage__roofing"])
cstacks.painted_steel(st, ["Garage__paint"], color=(0.34, 0.20, 0.13), rough=0.6, age=1.1, rust=1.2,
                      name="Ворота: коричневая краска")
cstacks.rusty_steel(st, ["Garage__steel"], name="Петли, замок, ригель", scale=14.0)

# ---- нутро открытого
st = stack_of("GarageInt")
sp_lib.clear(st)
brick_wall(st, ["GarageInt__brick"], name="Кладка изнутри", outside=False)
floor_concrete(st, ["GarageInt__floor"])

# ---- вещи — в том же наборе нутра (отдельный атлас заполнялся вполовину)
simple(st, ["GarageInt__plywood"], "Фанера", (0.58, 0.46, 0.30), 0.75, mat="wood_plain/wood_plain", scale=10.0)
simple(st, ["GarageInt__wood"], "Доски", (0.45, 0.34, 0.22), 0.8, mat="wood_rough/wood_rough", scale=10.0)
simple(st, ["GarageInt__cardboard"], "Картон", (0.55, 0.43, 0.29), 0.9, mat="paper_cardboard/paper_cardboard",
       scale=10.0)
simple(st, ["GarageInt__rubber"], "Резина", (0.05, 0.05, 0.05), 0.85, mat="rubber_raw/rubber_raw", scale=10.0,
       wear=1.2)
simple(st, ["GarageInt__steel"], "Сталь тёмная", (0.20, 0.20, 0.19), 0.6, metal=0.8)
simple(st, ["GarageInt__galv"], "Ведро", (0.6, 0.6, 0.6), 0.45, mat="metal_galvanized/metal_galvanized", scale=12.0)
simple(st, ["GarageInt__plastic"], "Пластик", (0.08, 0.08, 0.08), 0.5)
cstacks.painted_steel(st, ["GarageInt__paint_green"], color=(0.18, 0.30, 0.18), rough=0.5, age=0.8, name="Канистры")
cstacks.painted_steel(st, ["GarageInt__paint_grey"], color=(0.48, 0.49, 0.48), rough=0.5, age=0.8,
                      name="Банки и щиток")
cstacks.painted_steel(st, ["GarageInt__paint_blue"], color=(0.15, 0.24, 0.40), rough=0.5, age=0.9, name="Тиски")

# ---- ракушка
st = stack_of("Shell")
sp_lib.clear(st)
cstacks.painted_steel(st, ["Shell__paint"], color=(0.22, 0.36, 0.26), rough=0.55, age=1.2, rust=1.4,
                      name="Ракушка: зелёная краска")
cstacks.rusty_steel(st, ["Shell__steel"], name="Рама, петли, подпорки", scale=12.0)
print("стек гаражей собран")
