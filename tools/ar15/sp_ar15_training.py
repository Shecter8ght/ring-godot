# AR-15 «ГРАНЬ-15»: тренировочная копия проекта Painter для владельца (2026-10-30: «сделай копию… чтобы я тоже
# потренировался в текстурировании… металлические и полимерные предметы… кисточками»). Копия принятого проекта
# (этап 1 «песок» + пробный износ рукояти) лежит в папке модели «Тренировка_текстурирование» рядом с инструкцией;
# оригинал `_asset_src/ar15/tex/sp/AR15_tex_stage1_v3.spp` этим скриптом не открывается и не меняется.
# На каждом наборе металла и полимера сверху стека — группа «Тренировка — руками» (Passthrough, как группа износа в
# sp_ar15_wear.py: в группе Normal слои смешивались бы с пустой группой, а не с отделкой). В ней — заготовки по порядку
# работы снизу вверх: заливка с нужными каналами и режимами, маска чёрная (слой не виден, пока в маске ничего нет),
# в маске сверху пустой слой рисования «Кисть — рисуйте здесь»; у кромок, грязи и пыли под ним — выключенный
# генератор-помощник (Metal Edge Wear, Dirt, AO), который владелец включает глазом и дорисовывает или стирает кистью.
# Числа — по классу отделки набора (BASE / VARIANTS["B"] в sp_ar15.py) и по плану износа «рабочий, лёгкий, ЧВК, город»
# (asset-state.md модели): на матовых покрытиях следы рук глаже, пыль и грязь матовее и не металл.
#   python -X utf8 <runner> -c "import sp_ar15_training as Tr; print(Tr.build())"   — в открытой копии; сохраняет её
import substance_painter.layerstack as L
import substance_painter.project as P
import substance_painter.textureset as TS

import sp_lib
from sp_lib import CH, fill

GROUP = "Тренировка — руками"
BRUSH = "Кисть — рисуйте здесь"
# набор → класс отделки (вариант Б: коробки, цевьё и трубка — песочный Cerakote поверх чёрного анодирования; ствол и
# затворная рама — нитрированная сталь; рукоять — песочный полимер, приклад и магазин — чёрный полимер)
SETS = {"upper": "sand", "lower": "sand", "handguard": "sand", "tube": "sand", "barrel": "steel", "bolt": "steel",
        "grip": "poly_sand", "stock": "poly_black", "magazine": "poly_black"}
EDGE = ("mg_metal_edge_wear/mg_metal_edge_wear", {"Wear_Level": 0.35, "Wear_Contrast": 0.6, "Grunge_Amount": 0.4})
DIRT = ("mg_dirt/mg_dirt", {"dirt_level": 0.4, "dirt_contrast": 0.6, "grunge_amount": 0.4, "edges_masking": 0.8})
AO = ("mg_ambient_occlusion/mg_ambient_occlusion", {"ao_invert": 1, "global_balance": 0.45, "global_contrast": 0.4})
HELPER = {EDGE[0]: "Помощник: Metal Edge Wear (кромки) — включите глазом",
          DIRT[0]: "Помощник: Dirt (грязь в углах) — включите глазом",
          AO[0]: "Помощник: Ambient Occlusion (углубления) — включите глазом"}
SL, MU, NO = L.BlendingMode.SoftLight, L.BlendingMode.Multiply, L.BlendingMode.Normal

# заготовка: (имя, цвет, режим цвета, непрозрачность цвета, блеск ±, металл, непрозр. металла, высота, помощник)
# блеск < 0 — глаже (Subtract), > 0 — матовее (Linear Dodge); высота ("sub", d) — врезано на d, ("abs", h) — уровень h
# (основа этапа 1 стоит на 0,5; лазерные надписи врезаны на 0,06)
T = {
    "sand": [
        ("1 Кромки — светлее и глаже", 0.80, SL, 0.6, -0.10, None, 1.0, None, EDGE),
        ("2 Заполировано рукой — глаже, чуть темнее", 0.88, MU, 0.6, -0.15, None, 1.0, None, None),
        ("3 Царапины — светлее, чуть врезаны", 0.85, SL, 0.8, -0.06, None, 1.0, ("sub", 0.02), None),
        ("4 Скол песка — до чёрного анодирования (редко, на кромках)", (0.06, 0.06, 0.066), NO, 1.0, ("abs", 0.45),
         0.85, 1.0, ("abs", 0.47), None),
        ("5 Масло — темнее, глянец", 0.72, MU, 0.7, -0.30, None, 1.0, None, None),
        ("6 Отпечатки и жир — глаже, чуть темнее", 0.86, MU, 0.5, -0.20, None, 1.0, None, None),
        ("7 Грязь в углах — темнее, матовее", (0.55, 0.50, 0.44), MU, 0.75, 0.18, None, 1.0, None, DIRT),
        ("8 Пыль — светлее, матовее", (0.68, 0.64, 0.57), NO, 0.5, 0.20, None, 1.0, None, AO),
    ],
    "steel": [
        ("1 Кромки — до блеска стали", 0.85, SL, 0.7, -0.12, 1.0, 0.5, None, EDGE),
        ("2 Заполировано рукой — глаже", 0.75, SL, 0.4, -0.12, None, 1.0, None, None),
        ("3 Царапины — светлее, блестят", 0.90, SL, 0.8, -0.10, 1.0, 0.6, ("sub", 0.015), None),
        ("4 Вытерто до голой стали (полосы трения)", (0.56, 0.56, 0.57), NO, 1.0, ("abs", 0.25), 1.0, 1.0, None, None),
        ("5 Масло — темнее, глянец", 0.70, MU, 0.6, -0.22, None, 1.0, None, None),
        ("6 Отпечатки и жир — глаже", 0.90, MU, 0.5, -0.12, None, 1.0, None, None),
        ("7 Грязь в углах — бурая, матовая", (0.20, 0.18, 0.15), NO, 0.6, 0.25, 0.0, 0.6, None, DIRT),
        ("8 Пыль — светлее, матовая", (0.52, 0.50, 0.47), NO, 0.5, 0.25, 0.0, 0.5, None, AO),
    ],
    "poly_sand": [
        ("1 Кромки и выступы — заглажены", 0.78, SL, 0.5, -0.10, None, 1.0, None, EDGE),
        ("2 Заполировано ладонью — глаже, чуть темнее", 0.88, MU, 0.6, -0.15, None, 1.0, None, None),
        ("3 Царапины — светлее, матовее", 0.85, SL, 0.8, 0.05, None, 1.0, ("sub", 0.02), None),
        ("4 Задир пластика — белёсый, матовый", (0.70, 0.63, 0.53), NO, 0.8, 0.12, None, 1.0, ("sub", 0.01), None),
        ("5 Масло и жир — темнее, глянец", 0.78, MU, 0.6, -0.22, None, 1.0, None, None),
        ("6 Отпечатки — глаже, чуть темнее", 0.86, MU, 0.5, -0.20, None, 1.0, None, None),
        ("7 Грязь в углах — темнее, матовее", (0.55, 0.50, 0.44), MU, 0.75, 0.18, None, 1.0, None, DIRT),
        ("8 Пыль — светлее, матовее", (0.70, 0.66, 0.59), NO, 0.55, 0.15, None, 1.0, None, AO),
    ],
    "poly_black": [
        ("1 Кромки и выступы — светлее, глаже", (0.16, 0.16, 0.16), NO, 0.6, -0.12, None, 1.0, None, EDGE),
        ("2 Заполировано рукой (щека, хват) — глаже", 0.90, MU, 0.5, -0.15, None, 1.0, None, None),
        ("3 Царапины — серые, матовее", (0.22, 0.22, 0.22), NO, 0.8, 0.05, None, 1.0, ("sub", 0.02), None),
        ("4 Задир пластика — белёсый, матовый", (0.30, 0.30, 0.29), NO, 0.8, 0.12, None, 1.0, ("sub", 0.01), None),
        ("5 Масло и жир — глянец", 0.80, MU, 0.6, -0.25, None, 1.0, None, None),
        ("6 Отпечатки — глаже", 0.90, MU, 0.4, -0.20, None, 1.0, None, None),
        ("7 Грязь в углах — бурая, матовая", (0.20, 0.18, 0.15), NO, 0.6, 0.20, None, 1.0, None, DIRT),
        ("8 Пыль — светлее, матовее", (0.45, 0.43, 0.40), NO, 0.5, 0.20, None, 1.0, None, AO),
    ],
}


def _template(pos, spec):
    name, color, cmode, cop, rough, metal, mop, height, helper = spec
    ch = {"color": color}
    absolute_rough = isinstance(rough, tuple)
    ch["rough"] = rough[1] if absolute_rough else abs(rough)
    if metal is not None:
        ch["metal"] = metal
    if height is not None:
        ch["height"] = height[1]
    f = fill(name, pos, **ch)
    f.set_blending_mode(cmode, CH.BaseColor)
    f.set_opacity(cop, CH.BaseColor)
    if not absolute_rough:
        f.set_blending_mode(L.BlendingMode.Subtract if rough < 0 else L.BlendingMode.LinearDodge, CH.SpecularRoughness)
    if metal is not None:
        f.set_opacity(mop, CH.BaseMetalness)
    if height is not None and height[0] == "sub":
        f.set_blending_mode(L.BlendingMode.Subtract, CH.Height)
    # маска: чёрная — слоя не видно, пока в маске ничего не нарисовано
    f.add_mask(L.MaskBackground.Black)
    under = None
    if helper is not None:
        g = sp_lib.mask_generator(f, helper[0], helper[1])
        g.set_name(HELPER[helper[0]])
        g.set_visible(False)
        under = g
    brush = L.insert_paint(L.InsertPosition.above_node(under) if under is not None
                           else L.InsertPosition.inside_node(f, L.NodeStack.Mask))
    brush.set_name(BRUSH)
    return f, brush


def build(sets=None):
    """Группа «Тренировка — руками» на наборах SETS (повторный вызов пересобирает её — нарисованное в ней пропадёт,
    поэтому набор с непустой группой пропускается)."""
    if "AR15_tex_stage1" in (P.file_path() or ""):
        raise RuntimeError("открыт оригинальный проект, а не тренировочная копия")
    out = []
    first_brush = None
    for name, cls in SETS.items():
        if sets and name not in sets:
            continue
        st = sp_lib.stack_by_name(name)
        old = [n for n in L.get_root_layer_nodes(st) if n.get_name() == GROUP]
        if old:
            out.append(f"{name}: группа уже есть — не трогаю")
            continue
        grp = L.insert_group(L.InsertPosition.from_textureset_stack(st))
        grp.set_name(GROUP)
        for ch in st.all_channels():
            grp.set_blending_mode(L.BlendingMode.Passthrough, ch)
        pos = L.InsertPosition.inside_node(grp, L.NodeStack.Substack)
        for spec in T[cls]:
            f, brush = _template(pos, spec)
            pos = L.InsertPosition.above_node(f)
            if name == "grip" and spec[0].startswith("6 "):
                first_brush = brush
        out.append(f"{name}: {cls}, {len(T[cls])} заготовок")
    md = P.Metadata("ring")
    md.set("training_copy", "AR-15: тренировочная копия владельца (sp_ar15_training.py), скриптами не пересобирать")
    if first_brush is not None:
        TS.set_active_stack(sp_lib.stack_by_name("grip"))
        L.set_selected_nodes([first_brush])

    def _save():
        P.save()
        return "saved " + P.file_path()
    sp_lib.when_idle(_save, "_training_saved.txt")
    return "\n".join(out)
