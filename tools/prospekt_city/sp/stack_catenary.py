# Задание Painter: стек слоёв жёсткой поперечины «Проспекта» (один набор Cat). Стек пересобирается с нуля.
# Оцинкованная решётка мачт и ригеля, плиты, оголовки и подвесы годами под дождём: цинк пятнами, белая ржавчина,
# рыжие кромки и подтёки, грязь на узлах; бетонные фундаменты; гирлянды — зеленоватое закалённое стекло в пыли
# и копоти, шапки оцинкованные; полимерные изоляторы фиксаторов тёмные; изоляторы фидеров — белый фарфор; табличка —
# эмаль. Фиксирующий трос, струны и заземляющие спуски — плиточный ржавый пруток Rebar, не здесь.
# Масштаб трёхпроекционных масок cstacks подобран на сцене ПО-2 (≈ 6 м); сцена поперечины ≈ 28 м — множитель K.
import importlib

import substance_painter.layerstack as L

import cstacks
import sp_lib

importlib.reload(cstacks)
from cstacks import DIRT, DRIP, WSN, above, fill, group, inside, lop, mask_generator, mask_proc, up  # noqa: E402

K = float(ARGS.get("k", "4.5"))
MUL = L.BlendingMode.Multiply
_tri_sp, _tri_cs = sp_lib.triplanar, cstacks.triplanar


def _tri(layer, scale, rot=0.0, hardness=0.6):
    _tri_sp(layer, scale * K, rot, hardness)


def glass_insulator(st, meshes, name="Стекло гирлянд"):
    """Закалённое стекло тарелок ПС: зеленоватое, глянцевое; пыль и копоть сверху, грязь в рёбрах снизу."""
    g = group(name, st, meshes)
    n = fill("01 Стекло", inside(g), color=(0.20, 0.31, 0.27), rough=0.06, metal=0.0)
    n = fill("02 Пыль и копоть сверху", above(n), color=(0.33, 0.32, 0.29), rough=0.8)
    mask_generator(n, WSN, up(0.45, 0.5))
    mask_proc(n, "grunge_dusty_powder_soft/grunge_dusty_powder_soft", None, scale=6.0, blend=MUL)
    lop(n, 0.7)
    n = fill("03 Грязь в рёбрах", above(n), color=(0.14, 0.13, 0.11), rough=0.8)
    mask_generator(n, DIRT, {"dirt_level": 0.35, "dirt_contrast": 0.7, "Use_Triplanar": 1})
    lop(n, 0.65)
    return g


def porcelain(st, meshes, color, name="Фарфор"):
    g = group(name, st, meshes)
    n = fill("01 Глазурь", inside(g), color=color, rough=0.14, metal=0.0)
    n = fill("02 Пыль и копоть сверху", above(n), color=(0.40, 0.38, 0.35), rough=0.85)
    mask_generator(n, WSN, up(0.5, 0.5))
    mask_proc(n, "grunge_dusty_powder_soft/grunge_dusty_powder_soft", None, scale=6.0, blend=MUL)
    lop(n, 0.7)
    n = fill("03 Грязь в желобках", above(n), color=(0.16, 0.14, 0.12), rough=0.8)
    mask_generator(n, DIRT, {"dirt_level": 0.35, "dirt_contrast": 0.7, "Use_Triplanar": 1})
    lop(n, 0.6)
    return g


def polymer(st, meshes, name="Полимер"):
    g = group(name, st, meshes)
    n = fill("01 Силикон", inside(g), color=(0.11, 0.11, 0.11), rough=0.5, metal=0.0)
    n = fill("02 Посерел сверху", above(n), color=(0.26, 0.26, 0.25), rough=0.8)
    mask_generator(n, WSN, up(0.5, 0.4))
    lop(n, 0.5)
    n = fill("03 Грязь", above(n), color=(0.16, 0.14, 0.12), rough=0.9)
    mask_generator(n, DIRT, {"dirt_level": 0.35, "dirt_contrast": 0.6, "Use_Triplanar": 1})
    lop(n, 0.6)
    return g


def run():
    st = sp_lib.stack_by_name("Cat")
    sp_lib.clear(st)
    g = cstacks.galvanized(st, ["Cat__galv"], age=1.3, name="Решётка, плиты, оголовки, подвесы")
    pos = L.InsertPosition.inside_node(g, L.NodeStack.Substack)
    n = fill("07 Грязь на узлах", pos, color=(0.20, 0.18, 0.15), rough=0.9, metal=0.0)
    mask_generator(n, DIRT, {"dirt_level": 0.45, "dirt_contrast": 0.6, "grunge_amount": 0.6, "Use_Triplanar": 1})
    lop(n, 0.5)
    cstacks.concrete(st, ["Cat__concrete"], color=(0.55, 0.54, 0.51), age=1.0, moss=1.0, name="Фундаменты")
    glass_insulator(st, ["Cat__glass"])
    polymer(st, ["Cat__polymer"], name="Изоляторы фиксаторов")
    porcelain(st, ["Cat__porcelain"], (0.84, 0.83, 0.79), name="Изоляторы фидеров")
    cstacks.painted_steel(st, ["Cat__sign"], (0.86, 0.86, 0.83), name="Табличка", age=0.8, rough=0.4, rust=0.7)


sp_lib.triplanar = cstacks.triplanar = _tri
try:
    run()
finally:
    sp_lib.triplanar, cstacks.triplanar = _tri_sp, _tri_cs
print("стек поперечины собран, K =", K)
