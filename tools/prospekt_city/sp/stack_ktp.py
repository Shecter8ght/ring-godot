# Задание Painter: стек слоёв трансформаторной КТП (наборы KTP и KTPInside). Корпус — оцинковка пятнами белой
# ржавчины, рыжие подтёки с крыши и от петель, грязь и следы травы снизу, немного граффити на торце; рама из швеллера
# крашена чёрным и ржавеет; цоколь — старый бетон; знаки «молния» — выгоревшая жёлтая краска; таблички белые, надписи
# чёрные. Внутри (видно при открытых дверях): бак трансформатора и щит — серая эмаль в пыли, фарфор вводов коричневый
# глазурованный, медные шины потемнели и позеленели, пластик и автоматы в пыли. Стек пересобирается с нуля.
import importlib

import substance_painter.layerstack as L

import cstacks
import sp_lib
from cstacks import above, inside, group, layer_proc, up, low, DIRT, WSN, POS, MUL
from sp_lib import fill, lop, mask_generator, mask_proc, only_meshes

importlib.reload(cstacks)


def ktp_shell(st, meshes):
    """Оцинковка корпуса (cstacks.galvanized) и поверх — грязь и зелень травы снизу, граффити на правом торце."""
    g = cstacks.galvanized(st, meshes, age=1.2, name="Оцинковка корпуса")
    n = fill("Грязь и трава снизу", above(g), color=(0.24, 0.24, 0.17), rough=0.95, metal=0.0)
    only_meshes(n, meshes)
    mask_generator(n, POS, low(0.18, 0.6))
    mask_proc(n, "grunge_dirt_splats/grunge_dirt_splats", None, scale=4.0, blend=MUL)
    lop(n, 0.85)
    try:
        t = L.insert_fill(above(n))
        t.set_name("Граффити на торце")
        t.active_channels = {sp_lib.CHAN["color"], sp_lib.CHAN["rough"], sp_lib.CHAN["metal"]}
        t.set_material_source(sp_lib.rid("spray_paint_tag/spray_paint_tag", "u:material"))
        sp_lib.triplanar(t, 2.0)
        only_meshes(t, meshes)
        mask_generator(t, POS, {"position_direction_topbottom_opacity": 0.0, "position_direction_rightleft_opacity": 1.0,
                                "position_direction_frontback_opacity": 0.0, "position_invert": 0,
                                "position_balance": 0.72, "position_contrast": 0.9})
        mask_proc(t, "grunge_paint_peeled/grunge_paint_peeled", None, scale=3.0, blend=MUL)
        lop(t, 0.75)
    except Exception as e:                      # нет материала тега на полке — без граффити
        print("граффити пропущено:", e)
    return g


def glazed(st, meshes, color, name, rough=0.12):
    """Глазурь (фарфор вводов) в пыли."""
    g = group(name, st, meshes)
    n = fill("01 Глазурь", inside(g), color=color, rough=rough)
    n = fill("02 Пыль сверху", above(n), color=(0.55, 0.52, 0.47), rough=0.95)
    mask_generator(n, WSN, up(0.5, 0.4))
    mask_proc(n, "grunge_dusty_powder_soft/grunge_dusty_powder_soft", None, scale=6.0, blend=MUL)
    lop(n, 0.7)
    n = fill("03 Грязь", above(n), color=(0.20, 0.18, 0.15), rough=0.9)
    mask_generator(n, DIRT, {"dirt_level": 0.35, "dirt_contrast": 0.6, "Use_Triplanar": 1})
    lop(n, 0.5)
    return g


def plastic(st, meshes, color, name, rough=0.5):
    g = group(name, st, meshes)
    n = fill("01 Пластик", inside(g), color=color, rough=rough)
    n = layer_proc("02 Фактура", above(n), "noise_gaussian_noise/gaussian_noise", 40.0, 0.3, rough=min(1.0, rough + 0.15))
    n = fill("03 Пыль", above(n), color=(0.52, 0.50, 0.46), rough=0.95)
    mask_generator(n, WSN, up(0.5, 0.4))
    mask_proc(n, "grunge_dusty_powder_soft/grunge_dusty_powder_soft", None, scale=6.0, blend=MUL)
    lop(n, 0.65)
    n = fill("04 Грязь", above(n), color=(0.18, 0.16, 0.13), rough=0.9)
    mask_generator(n, DIRT, {"dirt_level": 0.35, "dirt_contrast": 0.6, "Use_Triplanar": 1})
    lop(n, 0.5)
    return g


def copper(st, meshes, name="Медь шин"):
    g = group(name, st, meshes)
    n = fill("01 Медь", inside(g), color=(0.66, 0.40, 0.25), rough=0.4, metal=1.0)
    n = layer_proc("02 Потемнела", above(n), "grunge_galvanic_small/grunge_galvanic_small", 6.0, 0.65,
                   color=(0.34, 0.21, 0.14), rough=0.6, metal=0.7)
    n = layer_proc("03 Патина", above(n), "grunge_spots_dirty/grunge_spots_dirty", 6.0, 0.3,
                   color=(0.32, 0.46, 0.40), rough=0.85, metal=0.0)
    n = fill("04 Пыль", above(n), color=(0.50, 0.47, 0.42), rough=0.95, metal=0.0)
    mask_generator(n, WSN, up(0.5, 0.4))
    lop(n, 0.5)
    return g


def rubber(st, meshes, name="Резина и пластик кабелей"):
    return plastic(st, meshes, (0.05, 0.05, 0.05), name, rough=0.75)


for ts in ("KTP", "KTPInside"):
    st = sp_lib.stack_by_name(ts)
    sp_lib.clear(st)
    if ts == "KTP":
        m = {k: [f"KTP__{k}"] for k in ("concrete", "frame", "galv", "sign", "bolt", "plate", "lettering", "handle", "rubber")}
        cstacks.concrete(st, m["concrete"], age=1.0, moss=0.7, name="Бетон цоколя")
        cstacks.painted_steel(st, m["frame"], (0.10, 0.10, 0.10), name="Рама из швеллера", age=1.1, rough=0.55, rust=1.4)
        ktp_shell(st, m["galv"])
        cstacks.painted_steel(st, m["sign"], (0.86, 0.68, 0.14), name="Знаки: жёлтое", age=0.9, rough=0.5, rust=0.4)
        cstacks.painted_steel(st, m["bolt"], (0.05, 0.05, 0.05), name="Знаки: молния", age=0.6, rough=0.45, rust=0.2)
        cstacks.painted_steel(st, m["plate"], (0.84, 0.84, 0.80), name="Таблички", age=0.8, rough=0.45, rust=0.5)
        cstacks.painted_steel(st, m["lettering"], (0.05, 0.05, 0.05), name="Надписи", age=0.5, rough=0.4, rust=0.0)
        cstacks.painted_steel(st, m["handle"], (0.12, 0.12, 0.12), name="Ручки-замки", age=0.9, rough=0.4, rust=1.0)
        rubber(st, m["rubber"], name="Кабельные трубы")
    else:
        m = {k: [f"KTPInside__{k}"] for k in ("paint", "steel", "porcelain", "copper", "galv", "plastic", "red", "white",
                                              "rubber")}
        cstacks.painted_steel(st, m["paint"], (0.45, 0.47, 0.46), name="Эмаль бака и щита", age=0.5, rough=0.5, rust=0.4)
        cstacks.painted_steel(st, m["steel"], (0.14, 0.14, 0.14), name="Сталь тёмная", age=0.6, rough=0.5, rust=0.8)
        glazed(st, m["porcelain"], (0.36, 0.18, 0.10), "Фарфор вводов")
        copper(st, m["copper"])
        cstacks.galvanized(st, m["galv"], age=0.6, name="Перегородка")
        plastic(st, m["plastic"], (0.06, 0.06, 0.06), "Пластик чёрный")
        plastic(st, m["red"], (0.55, 0.08, 0.06), "Пластик красный", rough=0.4)
        plastic(st, m["white"], (0.80, 0.79, 0.74), "Автоматы и счётчик", rough=0.45)
        rubber(st, m["rubber"])
print("стек КТП собран")
