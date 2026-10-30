# AR-15 «ГРАНЬ-15», этап 2 — износ (навык weapon-asset-wear) в Substance Painter через мост (tools/ar15/sp_run.py).
# Группа «Этап 2 — износ» над принятой заводской отделкой («Этап 1 — заводская отделка» не меняется, износ
# выключается целиком). План — asset-state.md модели: рабочий лёгкий, ЧВК, город. Места — маски зон хвата, запечённые
# в развёртку набора (tools/ar15/wear_zones.py), рисунок следа — фото-маски CC0 ambientCG из
# `E:/Models Blender/Маски_АЛЬФА/50_Скачанные_CC0_ambientCG_ShareTextures`, подготовленные tools/ar15/wear_masks.py
# (уровни, порог, размытие; латинский путь — `wear/masks`).
# Сумма «глаже» в самом захватанном месте — до ≈ 0,3 от заводских 0,6. Группа — Passthrough (см. build_grip). Каждая
# вариация меняет и цвет, и блеск: где захватали — глаже и чуть темнее, вершины насечки — светлее,
# пыль — светлее и матовее (противовес).
import substance_painter.layerstack as L
import substance_painter.textureset as TS

import sp_lib
import sp_stacks as S
import tex_sets as T
from sp_lib import CH, fill, triplanar

W = T.WORK + "/wear"
MK = W + "/masks"
GROUP = "Этап 2 — износ"
# масштаб рисунка фото-масок (трёхпроекционно): отпечатки ~15 мм, разводы — ладонь
PRINT_SCALE = 7.0
SMEAR_SCALE = 3.0
DUST_SCALE = 5.0
SCRATCH_SCALE = 4.0


def _layer(name, pos, rough=None, color=None, cmode=L.BlendingMode.Multiply, cop=1.0, rop=1.0):
    """Слой-поправка: блеск — вычитанием (глаже) или прибавкой (матовее), цвет — режимом наложения."""
    ch = {}
    if rough is not None:
        ch["rough"] = abs(rough)
    if color is not None:
        ch["color"] = color
    f = fill(name, pos, **ch)
    if rough is not None:
        f.set_blending_mode(L.BlendingMode.Subtract if rough < 0 else L.BlendingMode.LinearDodge, CH.SpecularRoughness)
        f.set_opacity(rop, CH.SpecularRoughness)
    if color is not None:
        f.set_blending_mode(cmode, CH.BaseColor)
        f.set_opacity(cop, CH.BaseColor)
    return f


def _pattern(above, path, scale, rot=0.0, blend=L.BlendingMode.Multiply, opacity=1.0):
    """Рисунок фото-маски в маске слоя поверх зоны (умножением)."""
    m = L.insert_fill(L.InsertPosition.above_node(above))
    m.set_source(None, S._bitmap(path))
    triplanar(m, scale, rot)
    m.set_blending_mode(blend)
    m.set_opacity(opacity)
    return m


def _zone(layer, zone, above=None, blend=None):
    """Зона в маске слоя; объединения зон (prints = пальцы + большой, polish = ладонь + большой, hand — все) запечены
    отдельными картами: рисунок кладётся первым, зона умножением последней — иначе Lighten рисунка выходил за зону."""
    return S._bmask(layer, f"{W}/grip_zone_{zone}_L.png", blend=blend, above=above)


def _mask_pattern(layer, path, scale, rot=0.0):
    """Рисунок фото-маски первым в маске слоя."""
    if not layer.has_mask():
        layer.add_mask(L.MaskBackground.Black)
    m = L.insert_fill(L.InsertPosition.inside_node(layer, L.NodeStack.Mask))
    m.set_source(None, S._bitmap(path))
    triplanar(m, scale, rot)
    return m


def build_grip():
    st = sp_lib.stack_by_name("grip")
    for n in L.get_root_layer_nodes(st):
        if n.get_name() == GROUP:
            L.delete_node(n)
    grp = L.insert_group(L.InsertPosition.from_textureset_stack(st))
    grp.set_name(GROUP)
    # группа — «насквозь» (Passthrough): по умолчанию Normal, и слои внутри смешивались с пустой группой, а не с
    # заводской отделкой — Multiply / Subtract работали как Normal: цвет к серому 0,9, блеск заменялся числом слоя
    # (проба 30.10: рукоять белёсая и зеркальная, блеск −0,25 и цвет +0,13 по всей рукояти)
    for ch in st.all_channels():
        grp.set_blending_mode(L.BlendingMode.Passthrough, ch)
    inside = L.InsertPosition.inside_node(grp, L.NodeStack.Substack)

    # 1. ладонь и большой палец — заполировано хватом: глаже, чуть темнее, неровно (разводы)
    l1 = _layer("Ладонь — заполировано хватом", inside, rough=-0.14, color=(0.86, 0.86, 0.86), cop=0.6)
    p = _mask_pattern(l1, f"{MK}/polish_var.png", SMEAR_SCALE, rot=0.4)
    _zone(l1, "polish", above=p, blend=L.BlendingMode.Multiply)
    # 2. ладонь — жирные разводы: глаже и темнее, пятнами
    l2 = _layer("Ладонь — жир", L.InsertPosition.above_node(l1), rough=-0.12, color=(0.84, 0.84, 0.84), cop=0.5)
    p = _mask_pattern(l2, f"{MK}/smear_oil.png", SMEAR_SCALE * 1.3, rot=1.1)
    _zone(l2, "palm", above=p, blend=L.BlendingMode.Multiply)
    # 3. пальцы и большой палец — отпечатки
    l3 = _layer("Пальцы — отпечатки", L.InsertPosition.above_node(l2), rough=-0.20, color=(0.84, 0.84, 0.84), cop=0.5)
    p = _mask_pattern(l3, f"{MK}/prints_a.png", PRINT_SCALE, rot=0.7)
    p = _pattern(p, f"{MK}/prints_b.png", PRINT_SCALE * 0.8, rot=2.2, blend=L.BlendingMode.Lighten,
                 opacity=0.6)
    _zone(l3, "prints", above=p, blend=L.BlendingMode.Multiply)
    # 4. вершины насечки и рёбра в местах хвата — затёрты: светлее и глаже
    l4 = _layer("Насечка и рёбра в хвате — затёрты", L.InsertPosition.above_node(l3), rough=-0.08,
                color=(0.78, 0.78, 0.78), cmode=L.BlendingMode.SoftLight, cop=0.4)
    g = sp_lib.mask_generator(l4, "mg_curvature/mg_curvature", {"global_balance": 0.62, "global_contrast": 0.5})
    _zone(l4, "hand", above=g, blend=L.BlendingMode.Multiply)
    # 5. пыль — светлая, матовая, в углублениях насечки и выемках (противовес жиру)
    l5 = _layer("Пыль в углублениях", L.InsertPosition.above_node(l4), rough=0.15, color=(0.66, 0.62, 0.55),
                cmode=L.BlendingMode.Normal, cop=0.5)
    # щели насечки и выемки — генератор Dirt (AO по запечённой карте брал крупные затенения у ствольной коробки, а
    # не щели между пирамидками; проба 30.10) × крапинки: во впадине пыль сплошь, крапинки гуще
    g = sp_lib.mask_generator(l5, "mg_dirt/mg_dirt", {"dirt_level": 0.3, "dirt_contrast": 0.7, "grunge_amount": 0.3,
                                                      "Grunge_Scale": 6, "Use_Triplanar": 1, "edges_masking": 0.9})
    _pattern(g, f"{MK}/dust_specks.png", DUST_SCALE, rot=0.3, opacity=0.5)
    # 6. торец — потёртости о поверхности (рукоять ставят на стол): светлее, мелкие царапины
    l6 = _layer("Торец — потёртости", L.InsertPosition.above_node(l5), rough=-0.06, color=(0.80, 0.80, 0.80),
                cmode=L.BlendingMode.SoftLight, cop=0.5)
    p = _mask_pattern(l6, f"{MK}/scratches.png", SCRATCH_SCALE, rot=0.9)
    _zone(l6, "base", above=p, blend=L.BlendingMode.Multiply)
    # резкости на группе нет: эффект на группе делает её отдельным слоем, и Subtract / Multiply / SoftLight внутри
    # смешивались с пустотой, а не с заводской отделкой — рукоять целиком белёсая и зеркальная (проба 30.10, блеск −0,25
    # и цвет +0,13 по всей рукояти); резкость кадра — уже у группы этапа 1
    return "grip: группа износа — 6 слоёв"
