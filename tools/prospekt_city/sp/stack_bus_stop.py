# Задание Painter: стек слоёв остановочного павильона (один набор BusStop на «Целый» и «Разбит»). Город брошен два года назад:
# порошковая краска каркаса графитовая, выгорела сверху, сколы до металла и рыжие точки на кромках, грязь снизу, пыль;
# водосток — оцинковка; таблички — белая эмаль, надписи — тёмно-синяя краска; плакат в коробе — выгоревший лист
# с остатками печати и потёками; расписание — бумага с рядами строк; скамья — выгоревшее серое дерево; крошка
# закалённого стекла — зеленовато-серая, блестит. Стек пересобирается с нуля (sp_lib.clear).
import importlib

import substance_painter.layerstack as L

import cstacks
import sp_lib
from cstacks import above, inside, group, layer_proc, up, low, DIRT, WSN, POS, EDGE, MUL
from sp_lib import fill, lop, mask_generator, mask_proc

importlib.reload(cstacks)


def wood_grey(st, meshes, name="Дерево скамьи"):
    """Брусья скамьи по навыку «дерево и крашеный металл»: три тона — средний (сама древесина, выгоревшая до
    серого), тёмный (стыки, грязь по полостям — чуть глянцевее, без микрорельефа), светлый (сколы и вытертое до сырой
    древесины — светлее, менее насыщенный, самый матовый, по кромкам); остатки лака — своим слоем с блеском, не в
    сколах; волокно вдоль бруска; пыль — сверху, не в сколах."""
    g = group(name, st, meshes)
    n = fill("01 Средний тон: серое дерево", inside(g), color=(0.45, 0.42, 0.37), rough=0.84)
    n = layer_proc("02 Волокно", above(n), "wood_01/wood_01", 6.0, 0.55, color=(0.32, 0.29, 0.25), rough=0.86)
    n = layer_proc("03 Трещины и тёмные жилки", above(n), "grunge_wood_soft/grunge_wood_soft", 5.0, 0.4,
                   color=(0.22, 0.20, 0.17), rough=0.9)
    n = fill("04 Тёмный тон: стыки и грязь", above(n), color=(0.20, 0.18, 0.15), rough=0.7)
    mask_generator(n, DIRT, {"dirt_level": 0.35, "dirt_contrast": 0.65, "grunge_amount": 0.5, "Use_Triplanar": 1})
    lop(n, 0.6)
    n = fill("05 Светлый тон: сколы и вытертое до сырой древесины", above(n), color=(0.64, 0.60, 0.52), rough=0.97)
    mask_generator(n, EDGE, {"Wear_Level": 0.18, "Wear_Contrast": 0.8, "Grunge_Amount": 0.8, "grunge_scale": 6,
                             "Use_Triplanar": 1, "Edges_Smoothness": 0.3})
    n = layer_proc("06 Остатки лака", above(n), "grunge_wipe_brushed/grunge_wipe_brushed", 4.0, 0.35,
                   color=(0.47, 0.37, 0.26), rough=0.45)
    n = fill("07 Выбелено сверху", above(n), color=(0.62, 0.60, 0.56), rough=0.92)
    mask_generator(n, WSN, up(0.55, 0.45))
    mask_proc(n, "grunge_dusty_powder_soft/grunge_dusty_powder_soft", None, scale=4.0, blend=MUL)
    lop(n, 0.55)
    return g


def poster(st, meshes, name="Плакат"):
    """Лист в коробе: бумага выгорела, от печати остались бледные пятна, потёки и плесень по низу, грязь у кромок."""
    g = group(name, st, meshes)
    n = fill("01 Бумага", inside(g), color=(0.80, 0.78, 0.72), rough=0.85)
    n = layer_proc("02 Остатки печати: голубое", above(n), "noise_clouds_2/clouds_2", 1.5, 0.35,
                   color=(0.42, 0.58, 0.70), rough=0.8)
    n = layer_proc("03 Остатки печати: красное", above(n), "noise_clouds_3/clouds_3", 1.2, 0.22,
                   color=(0.72, 0.38, 0.34), rough=0.8)
    n = layer_proc("04 Выгорание пятнами", above(n), "grunge_humidity/grunge_humidity", 2.0, 0.45,
                   color=(0.86, 0.84, 0.78), rough=0.88)
    n = layer_proc("05 Потёки", above(n), "grunge_leaks/grunge_leaks", 2.0, 0.40, color=(0.58, 0.53, 0.44), rough=0.8)
    n = fill("06 Плесень по низу", above(n), color=(0.34, 0.36, 0.28), rough=0.9)
    mask_generator(n, POS, low(0.22, 0.6))
    mask_proc(n, "grunge_concrete_moss_small/grunge_concrete_moss_small", None, scale=4.0, blend=MUL)
    lop(n, 0.55)
    n = fill("07 Грязь у кромок", above(n), color=(0.30, 0.27, 0.22), rough=0.9)
    mask_generator(n, DIRT, {"dirt_level": 0.4, "dirt_contrast": 0.5, "Use_Triplanar": 1})
    lop(n, 0.6)
    return g


def schedule(st, meshes, name="Расписание"):
    """Лист расписания под стеклом: пожелтевшая бумага, ряды строк, выцветшие пятна."""
    g = group(name, st, meshes)
    n = fill("01 Бумага", inside(g), color=(0.83, 0.81, 0.74), rough=0.85)
    n = fill("02 Строки", above(n), color=(0.30, 0.30, 0.32), rough=0.85)
    mask_proc(n, "stripes/ratio_stripes", None, scale=18.0, rot=45.0)   # строки — по горизонтали листа
    lop(n, 0.35)
    n = layer_proc("03 Пожелтела", above(n), "grunge_humidity/grunge_humidity", 2.0, 0.45, color=(0.78, 0.70, 0.52),
                   rough=0.85)
    n = layer_proc("04 Пятна сырости", above(n), "grunge_leak_spots/grunge_leak_spots", 3.0, 0.3,
                   color=(0.60, 0.55, 0.45), rough=0.85)
    return g


def crumbs(st, meshes, name="Крошка стекла"):
    """Кучки закалённого стекла: зеленоватые кубики, блеск, пыль и грязь между ними."""
    g = group(name, st, meshes)
    n = fill("01 Стекло", inside(g), color=(0.60, 0.67, 0.65), rough=0.15)
    n = layer_proc("02 Грани блестят", above(n), "white_noise_fast/white_noise_fast", 40.0, 0.45,
                   color=(0.82, 0.88, 0.86), rough=0.05)
    n = fill("03 Пыль и грязь между", above(n), color=(0.36, 0.34, 0.30), rough=0.9)
    mask_generator(n, DIRT, {"dirt_level": 0.45, "dirt_contrast": 0.55, "Use_Triplanar": 1})
    mask_proc(n, "grunge_dirt/grunge_dirt", None, scale=6.0, blend=L.BlendingMode.Screen, opacity=0.5)
    lop(n, 0.7)
    return g


GRAPHITE = (0.24, 0.25, 0.26)
# один набор на «Целый» и «Разбит» (свои детали «Разбит» — в том же атласе)
st = sp_lib.stack_by_name("BusStop")
sp_lib.clear(st)
m = {k: [f"BusStop__{k}"] for k in ("paint", "galv", "sign", "lettering", "poster", "paper", "wood", "crumbs")}
cstacks.painted_steel(st, m["paint"], GRAPHITE, name="Порошковая краска", age=0.6, rough=0.5, rust=0.5)
wood_grey(st, m["wood"])
poster(st, m["poster"])
cstacks.galvanized(st, m["galv"])
cstacks.painted_steel(st, m["sign"], (0.86, 0.86, 0.83), name="Таблички", age=0.7, rough=0.45, rust=0.4)
cstacks.painted_steel(st, m["lettering"], (0.07, 0.10, 0.22), name="Надписи", age=0.5, rough=0.4, rust=0.0)
schedule(st, m["paper"])
crumbs(st, m["crumbs"])
print("стек остановки собран")
