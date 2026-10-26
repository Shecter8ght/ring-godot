# Задание Painter: стек слоёв морских контейнеров (наборы C20, C40 — снаружи, C20In, C40In — нутро открытых).
# ARGS: paint — цвет краски (red | blue | green | beige, по умолчанию red; тот же список — containers.PAINTS),
# sets — какие наборы пересобрать (через запятую; по умолчанию все). Стек пересобирается с нуля (sp_lib.clear).
# Контейнер лет двадцать в ходу и два года брошен: морская краска выгорела и меловеет сверху, крыша в пыли и рыжих
# пятнах, по рёбрам гофры и кромкам — сколы до грунта и ржавчина, внизу — ржавый пояс и грязь, с фитингов и кромок —
# ржавые подтёки; запоры оцинкованы; днище чёрное, ржавое; внутри светлая краска в потёртостях, фанерный пол в пятнах.
import importlib

import substance_painter.layerstack as L

import cstacks
import sp_lib

importlib.reload(cstacks)
from cstacks import DIRT, DRIP, EDGE, MUL, POS, WSN, above, group, inside, layer_proc, low, up  # noqa: E402
from sp_lib import fill, lop, mask_generator, mask_proc  # noqa: E402

PAINTS = {"red": (0.44, 0.17, 0.11), "blue": (0.15, 0.27, 0.44), "green": (0.20, 0.35, 0.25), "beige": (0.62, 0.55, 0.42)}
RUST = (0.30, 0.14, 0.06)


def marine_paint(st, meshes, color, name="Краска", rust=1.0, fade=1.0):
    """Морская краска на стали: основа — cstacks.painted_steel (вариации и рельеф краски, Soft Light, светлые кромки,
    сколы «крупное — среднее — мелкое» с ободком грунта, окисленный металл, ржавчина местами, подтёки, грязь, пыль);
    поверх — своё у контейнера: меление сверху, ржавый пояс по низу, рыжие точки, водяные потёки."""
    base = cstacks.painted_steel(st, meshes, color, name=name, age=1.0, rough=0.52, rust=rust)
    g = group(name + ": море", st, meshes)
    n = fill("01 Меление сверху", inside(g), color=tuple(min(1.0, c * 1.3 + 0.12) for c in color), rough=0.9)
    mask_generator(n, cstacks.WSN, up(0.55, 0.45))
    mask_proc(n, "grunge_dusty_powder_soft/grunge_dusty_powder_soft", None, scale=3.0, blend=MUL)
    lop(n, 0.6 * fade)
    n = fill("02 Ржавый пояс внизу", above(n), color=(0.33, 0.16, 0.07), rough=0.92, metal=0.05)
    mask_generator(n, POS, low(0.14, 0.6))
    mask_proc(n, "grunge_rust_fine/grunge_rust_fine", None, scale=5.0, blend=MUL)
    lop(n, 0.75 * rust)
    n = layer_proc("03 Рыжие точки", above(n), "grunge_spots_dirty/grunge_spots_dirty", 6.0, 0.3 * rust,
                   color=RUST, rough=0.9, metal=0.05)
    n = layer_proc("04 Водяные потёки", above(n), "grunge_leaks/grunge_leaks", 2.5, 0.22,
                   color=tuple(c * 0.7 for c in color), rough=0.6)
    return base


def interior(st, paint_meshes, floor_meshes):
    """Нутро: светлая краска в потёртостях и следах груза, грязь по низу; фанерный пол в пятнах масла и царапинах."""
    g = group("Нутро", st, paint_meshes)
    n = fill("01 Краска", inside(g), color=(0.60, 0.58, 0.53), rough=0.6, metal=0.0)
    n = layer_proc("02 Неровный глянец", above(n), "grunge_wipe_smudgy_soft/grunge_wipe_smudgy_soft", 4.0, 0.5, rough=0.78)
    n = layer_proc("03 Потёртости от груза", above(n), "grunge_dirt_scratchy/grunge_dirt_scratchy", 4.0, 0.45,
                   color=(0.40, 0.38, 0.34), rough=0.8)
    n = fill("04 Сколы и ржавчина", above(n), color=RUST, rough=0.9, metal=0.1)
    mask_generator(n, EDGE, {"Wear_Level": 0.08, "Wear_Contrast": 0.85, "Grunge_Amount": 0.9, "grunge_scale": 7,
                             "Use_Triplanar": 1})
    n = fill("05 Грязь по низу", above(n), color=(0.30, 0.27, 0.22), rough=0.95)
    mask_generator(n, POS, low(0.18, 0.5))
    mask_proc(n, "grunge_stains_leaky/grunge_stains_leaky", None, scale=3.0, blend=MUL)
    lop(n, 0.8)
    n = layer_proc("06 Пятна", above(n), "grunge_stains_spots/grunge_stains_spots", 3.0, 0.3, color=(0.35, 0.32, 0.27),
                   rough=0.85)
    n = fill("07 Грязь в рёбрах", above(n), color=(0.18, 0.16, 0.13), rough=0.95)
    mask_generator(n, DIRT, {"dirt_level": 0.35, "dirt_contrast": 0.6, "grunge_amount": 0.4, "Use_Triplanar": 1})
    lop(n, 0.6)
    f = group("Фанерный пол", st, floor_meshes)
    n = fill("01 Фанера", inside(f), color=(0.42, 0.31, 0.20), rough=0.8, metal=0.0)
    n = layer_proc("02 Волокно", above(n), "wood_01/wood_01", 3.0, 0.5, color=(0.33, 0.24, 0.15), rough=0.82)
    n = layer_proc("03 Потемнела", above(n), "grunge_wood_soft/grunge_wood_soft", 3.0, 0.5, color=(0.27, 0.20, 0.13),
                   rough=0.85)
    n = layer_proc("04 Масло и пятна", above(n), "grunge_stains_heavy/grunge_stains_heavy", 2.0, 0.55,
                   color=(0.13, 0.11, 0.09), rough=0.55)
    n = layer_proc("05 Царапины от груза", above(n), "grunge_scratches_dirty/grunge_scratches_dirty", 3.0, 0.4,
                   color=(0.55, 0.45, 0.32), rough=0.85)
    n = layer_proc("06 Пыль и песок", above(n), "grunge_dusty_powder_soft/grunge_dusty_powder_soft", 3.0, 0.45,
                   color=(0.55, 0.50, 0.42), rough=0.97)
    return g


color = PAINTS[ARGS.get("paint", "red")]
only = set(ARGS["sets"].split(",")) if ARGS.get("sets") else None
for ts in ("C20", "C40"):
    if only and ts not in only:
        continue
    st = sp_lib.stack_by_name(ts)
    sp_lib.clear(st)
    marine_paint(st, [f"{ts}__paint"], color)
    marine_paint(st, [f"{ts}__under"], (0.07, 0.07, 0.07), name="Днище", rust=1.6, fade=0.2)
    cstacks.galvanized(st, [f"{ts}__galv"])
for ts in ("C20In", "C40In"):
    if only and ts not in only:
        continue
    st = sp_lib.stack_by_name(ts)
    sp_lib.clear(st)
    interior(st, [f"{ts}__intpaint"], [f"{ts}__plywood"])
print("стек контейнеров собран, краска", ARGS.get("paint", "red"))
