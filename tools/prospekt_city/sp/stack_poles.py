# Задание Painter: стек слоёв опор «Проспекта» (наборы Pole04, Trolley). Стек пересобирается с нуля.
# Опора 0,4 кВ: бетон стойки СВ с ржавыми потёками от траверсы, грязь и мох у земли; оцинкованная траверса с белой и
# рыжей ржавчиной; коричневый глазурованный фарфор в пыли; эмалевая табличка с красной молнией; чёрный кабель;
# светильник (в наборе опоры) — серая литая краска. Заземляющий спуск — плиточный ржавый пруток Rebar, не здесь.
# Троллейбусная: серая краска по стали, выгоревшая, ржавая у фланца и стыков; бетонный фундамент; оцинкованные
# хомуты и талреп; тёмно-серый полимерный изолятор; табличка.
# Масштаб трёхпроекционных масок cstacks подобран на сцене ПО-2 (≈ 6 м); сцена опор ≈ 12 м — множитель K (масштабы
# масок умножаются на время задания и возвращаются после).
import importlib

import substance_painter.layerstack as L

import cstacks
import sp_lib

importlib.reload(cstacks)
from cstacks import DIRT, DRIP, POS, WSN, above, fill, group, high, inside, lop, low, mask_generator, mask_proc, up  # noqa: E402

K = float(ARGS.get("k", "2.0"))
MUL = L.BlendingMode.Multiply
_tri_sp, _tri_cs = sp_lib.triplanar, cstacks.triplanar


def _tri(layer, scale, rot=0.0, hardness=0.6):
    _tri_sp(layer, scale * K, rot, hardness)


def porcelain(st, meshes, color, name="Фарфор"):
    """Глазурованный фарфор изоляторов: глянец, тон пятнами, пыль и копоть сверху, грязь в желобках."""
    g = group(name, st, meshes)
    n = fill("01 Глазурь", inside(g), color=color, rough=0.14, metal=0.0)
    n = cstacks.layer_proc("02 Тон", above(n), "grunge_spots/grunge_spots", 6.0, 0.35,
                           color=tuple(c * 0.85 for c in color), rough=0.2)
    n = fill("03 Пыль и копоть сверху", above(n), color=(0.36, 0.34, 0.31), rough=0.85)
    mask_generator(n, WSN, up(0.5, 0.5))
    mask_proc(n, "grunge_dusty_powder_soft/grunge_dusty_powder_soft", None, scale=6.0, blend=MUL)
    lop(n, 0.75)
    n = fill("04 Грязь в желобках", above(n), color=(0.15, 0.13, 0.11), rough=0.8)
    mask_generator(n, DIRT, {"dirt_level": 0.35, "dirt_contrast": 0.7, "Use_Triplanar": 1})
    lop(n, 0.7)
    return g


def plastic(st, meshes, color, rough=0.55, name="Пластик"):
    """Пластик и полимер на улице: посерел сверху, пыль, грязь в рёбрах."""
    g = group(name, st, meshes)
    n = fill("01 Пластик", inside(g), color=color, rough=rough, metal=0.0)
    n = cstacks.layer_proc("02 Фактура", above(n), "noise_gaussian_noise/gaussian_noise", 40.0, 0.3, rough=rough + 0.15)
    n = fill("03 Посерел сверху", above(n), color=tuple(min(1.0, c + 0.12) for c in color), rough=0.8)
    mask_generator(n, WSN, up(0.5, 0.4))
    mask_proc(n, "grunge_dusty_powder_soft/grunge_dusty_powder_soft", None, scale=4.0, blend=MUL)
    lop(n, 0.6)
    n = fill("04 Грязь", above(n), color=(0.18, 0.16, 0.13), rough=0.9)
    mask_generator(n, DIRT, {"dirt_level": 0.35, "dirt_contrast": 0.6, "Use_Triplanar": 1})
    lop(n, 0.6)
    return g


def run():
    m = lambda ts, k: [f"{ts}__{k}"]  # noqa: E731
    # --- опора 0,4 кВ
    st = sp_lib.stack_by_name("Pole04")
    sp_lib.clear(st)
    g = cstacks.concrete(st, m("Pole04", "concrete"), color=(0.60, 0.59, 0.56), age=1.0, moss=0.9, name="Бетон стойки")
    pos = L.InsertPosition.inside_node(g, L.NodeStack.Substack)
    n = fill("12 Ржавые потёки от траверсы", pos, color=(0.34, 0.18, 0.08), rough=0.85)
    mask_generator(n, DRIP, {"Rust_Spreading": 0.15, "Rust_Contrast": 0.7, "Drips_Intensity": 1.0,
                             "Drips_Smoothness": 0.2, "Drips_Samples_Amount": 24})
    mask_generator(n, POS, high(0.62, 0.6))
    mask_proc(n, "grunge_rusty_leaks/grunge_rusty_leaks", None, scale=3.0, blend=MUL)
    lop(n, 0.7)
    cstacks.galvanized(st, m("Pole04", "galv"), age=1.2, name="Траверса и консоль")
    porcelain(st, m("Pole04", "porcelain"), (0.40, 0.20, 0.10))
    cstacks.painted_steel(st, m("Pole04", "lumpaint"), (0.44, 0.45, 0.44), name="Корпус светильника", age=0.8,
                          rough=0.5, rust=0.4)
    cstacks.painted_steel(st, m("Pole04", "sign"), (0.86, 0.86, 0.83), name="Табличка", age=0.8, rough=0.4, rust=0.7)
    cstacks.painted_steel(st, m("Pole04", "signred"), (0.66, 0.08, 0.06), name="Молния", age=0.6, rough=0.4, rust=0.3)
    plastic(st, m("Pole04", "cable"), (0.035, 0.035, 0.035), 0.5, name="Кабель")
    # --- троллейбусная
    st = sp_lib.stack_by_name("Trolley")
    sp_lib.clear(st)
    g = cstacks.painted_steel(st, m("Trolley", "paint"), (0.43, 0.46, 0.46), name="Краска опоры", age=1.0, rough=0.55)
    pos = L.InsertPosition.inside_node(g, L.NodeStack.Substack)
    n = fill("11 Ржавчина у фланца", pos, color=(0.33, 0.16, 0.07), rough=0.9, metal=0.1)
    mask_generator(n, POS, low(0.07, 0.65))
    mask_proc(n, "grunge_rust_fine/grunge_rust_fine", None, scale=6.0, blend=MUL)
    lop(n, 0.85)
    cstacks.concrete(st, m("Trolley", "concrete"), color=(0.55, 0.54, 0.51), age=1.0, moss=1.0, name="Фундамент")
    cstacks.galvanized(st, m("Trolley", "galv"), age=1.0, name="Хомуты и талреп")
    plastic(st, m("Trolley", "polymer"), (0.11, 0.11, 0.11), 0.5, name="Полимерный изолятор")
    cstacks.galvanized(st, m("Trolley", "rope"), age=1.5, name="Трос")
    cstacks.painted_steel(st, m("Trolley", "sign"), (0.86, 0.86, 0.83), name="Табличка", age=0.8, rough=0.4, rust=0.7)


sp_lib.triplanar = cstacks.triplanar = _tri
try:
    run()
finally:
    sp_lib.triplanar, cstacks.triplanar = _tri_sp, _tri_cs
print("стек опор собран, K =", K)
