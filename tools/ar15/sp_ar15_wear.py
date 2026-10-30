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
GRIME_SCALE = 20.0          # рваный гранж грязи в углах у рёбрышек — пятна долями миллиметра
GRAIN_SCALE = 10.0          # частицы пыли там же


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


def _new_group(setname):
    """Группа «Этап 2 — износ» набора заново (прежняя удаляется) — поверх заводской отделки; позиция для первого слоя."""
    st = sp_lib.stack_by_name(setname)
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
    return L.InsertPosition.inside_node(grp, L.NodeStack.Substack)


def _zs(layer, setname, zone, above=None, blend=None):
    """Зона набора (tools/ar15/wear_lower.py и следующие: <набор>_zone_<зона>_L.png) в маске слоя."""
    return S._bmask(layer, f"{W}/{setname}_zone_{zone}_L.png", blend=blend, above=above)


def _plain(name, pos, color, rough, metal=None, cop=1.0):
    """Слой, заменяющий цвет и блеск (Normal): то, что лежит поверх покрытия или проступает из-под него."""
    ch = {"color": color, "rough": rough}
    if metal is not None:
        ch["metal"] = metal
    f = fill(name, pos, **ch)
    f.set_opacity(cop, CH.BaseColor)
    return f


def build_grip():
    inside = _new_group("grip")

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
    _zone(l4, "hand_edges", above=g, blend=L.BlendingMode.Multiply)   # без площадок насечки — у них слои 10–11
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
    # 7–9. рёбрышки в выемках под пальцы (владелец 30.10): сами заглажены пальцами и перчаткой — глянец; в углах стыка
    # с телом — грязь (тёмная, у самого края) и пыль (светлая, полосой чуть шире). Маски — wear_zones.py (ribs,
    # rib_dirt, rib_dust); грязь поверх глянца: низ боков рёбрышка в углу — матовый
    l7 = _layer("Рёбрышки — заглажены пальцами", L.InsertPosition.above_node(l6), rough=-0.28, color=(0.92, 0.92, 0.92),
                cop=0.5)
    p = _mask_pattern(l7, f"{MK}/polish_var.png", SMEAR_SCALE, rot=2.0)
    _zone(l7, "ribs", above=p, blend=L.BlendingMode.Multiply)
    # грязь — затемняет родной цвет пластика (Multiply), а не закрашивает ровным тоном: ровная заливка читалась
    # обводкой тушью вокруг рёбрышек (проба 30.10); рисунок — рваный гранж с фото (ShareTextures dirt_5)
    l8 = _layer("Углы у рёбрышек — грязь", L.InsertPosition.above_node(l7), rough=0.18, color=(0.55, 0.50, 0.44),
                cop=0.75)
    p = _mask_pattern(l8, f"{MK}/grime.png", GRIME_SCALE, rot=0.6)
    _zone(l8, "rib_dirt", above=p, blend=L.BlendingMode.Multiply)
    # пыль — светлая, частицами (ShareTextures dirt_1); в верхнем углу гуще (маска rib_dust)
    l9 = _layer("Углы у рёбрышек — пыль", L.InsertPosition.above_node(l8), rough=0.15, color=(0.70, 0.66, 0.59),
                cmode=L.BlendingMode.Normal, cop=0.55)
    p = _mask_pattern(l9, f"{MK}/dust_grain.png", GRAIN_SCALE, rot=1.4)
    _zone(l9, "rib_dust", above=p, blend=L.BlendingMode.Multiply)
    # 10–11. пупырышки боковых площадок (владелец 30.10): так же, как рёбрышки, но без пыли — вершины заглажены, в углах
    # у основания грязь; справа (ладонь) — вся площадка, слева — только место большого пальца (маски stip_gloss, stip_dirt)
    l10 = _layer("Пупырышки — заглажены ладонью и большим пальцем", L.InsertPosition.above_node(l9), rough=-0.22,
                 color=(0.93, 0.93, 0.93), cop=0.5)
    p = _mask_pattern(l10, f"{MK}/polish_var.png", SMEAR_SCALE, rot=2.6)
    _zone(l10, "stip_gloss", above=p, blend=L.BlendingMode.Multiply)
    l11 = _layer("Углы у пупырышек — грязь", L.InsertPosition.above_node(l10), rough=0.15, color=(0.55, 0.50, 0.44),
                 cop=0.7)
    p = _mask_pattern(l11, f"{MK}/grime.png", GRIME_SCALE, rot=1.9)
    _zone(l11, "stip_dirt", above=p, blend=L.BlendingMode.Multiply)
    # резкости на группе нет: эффект на группе делает её отдельным слоем, и Subtract / Multiply / SoftLight внутри
    # смешивались с пустотой, а не с заводской отделкой — рукоять целиком белёсая и зеркальная (проба 30.10, блеск −0,25
    # и цвет +0,13 по всей рукояти); резкость кадра — уже у группы этапа 1
    return "grip: группа износа — 11 слоёв"


# ── нижний ресивер (Cerakote FDE) с органами управления (фосфат) и видимые части УСМ ─────────────────────────────────
# Решения владельца 30.10: протёртый FDE — глаже и темнее (заглажено, жир), не светлее; сквозь — только точки чёрного
# анодирования на местах удара (угол раструба, удар крышки окна); фосфат под пальцем — гладкий тёмный сатин с лёгким
# блеском; на матовом FDE отпечатки — тёмные гладкие пятна без узора, на фосфате — с узором. Места — wear_lower.py.
def build_lower():
    inside = _new_group("lower")
    z = lambda lay, zone, above=None: _zs(lay, "lower", zone, above=above, blend=L.BlendingMode.Multiply if above else None)
    # 1–2. шахта — хват левой рукой: заглажено и темнее, пятна жира без узора
    l1 = _layer("Шахта — заглажена хватом", inside, rough=-0.10, color=(0.90, 0.90, 0.90), cop=0.6)
    z(l1, "hold", _mask_pattern(l1, f"{MK}/polish_var.png", SMEAR_SCALE, rot=0.9))
    l2 = _layer("Шахта — жирные пятна", L.InsertPosition.above_node(l1), rough=-0.10, color=(0.88, 0.88, 0.88), cop=0.4)
    z(l2, "hold", _mask_pattern(l2, f"{MK}/prints_a.png", PRINT_SCALE * 0.6, rot=1.7))
    # 3. кромки раструба, скобы и низа — заглажены прерывисто (кривизна × место × разрыв), не все рёбра одинаково
    l3 = _layer("Раструб, скоба, рёбра низа — заглажены", L.InsertPosition.above_node(l2), rough=-0.12,
                color=(0.88, 0.88, 0.88), cop=0.6)
    g = sp_lib.mask_generator(l3, "mg_curvature/mg_curvature", {"global_balance": 0.62, "global_contrast": 0.5})
    e = _zs(l3, "lower", "edgewear", above=g, blend=L.BlendingMode.Multiply)
    _pattern(e, f"{MK}/grime.png", GRIME_SCALE * 0.5, rot=0.4)
    # 4. раструб изнутри — мелкие риски от магазина
    l4 = _layer("Раструб — риски от магазина", L.InsertPosition.above_node(l3), rough=-0.06, color=(0.90, 0.90, 0.90),
                cop=0.5)
    z(l4, "flare", _mask_pattern(l4, f"{MK}/scratches.png", SCRATCH_SCALE, rot=1.57))
    # 5–8. удар крышки окна, полоса от рукоятки заряжания, дуга переводчика, кольца у осей
    l5 = _layer("Удар крышки окна", L.InsertPosition.above_node(l4), rough=-0.10, color=(0.86, 0.86, 0.86), cop=0.6)
    z(l5, "cover_hit", _mask_pattern(l5, f"{MK}/polish_var.png", SMEAR_SCALE * 2.0, rot=0.2))
    l6 = _layer("Полоса от рукоятки заряжания", L.InsertPosition.above_node(l5), rough=-0.12, color=(0.88, 0.88, 0.88),
                cop=0.6)
    z(l6, "ch_rub")
    l7 = _layer("Дуга под флажком переводчика", L.InsertPosition.above_node(l6), rough=-0.10,
                color=(0.88, 0.88, 0.88), cop=0.55)
    z(l7, "sel_arc", _mask_pattern(l7, f"{MK}/polish_var.png", SMEAR_SCALE * 2.0, rot=2.4))
    l8 = _layer("Кольца у осей — риски", L.InsertPosition.above_node(l7), rough=-0.06, color=(0.88, 0.88, 0.88),
                cop=0.5)
    z(l8, "pin_rings", _mask_pattern(l8, f"{MK}/scratches.png", SCRATCH_SCALE * 2.0, rot=0.8))
    # 9. сквозь — точки чёрного анодирования (рваные по гранжу)
    l9 = _plain("Сквозь — чёрное анодирование", L.InsertPosition.above_node(l8), (0.06, 0.06, 0.065), 0.5)
    z(l9, "through", _mask_pattern(l9, f"{MK}/grime.png", GRIME_SCALE, rot=1.1))
    # 10. масло у осей УСМ и переводчика — венчики
    l10 = _layer("Масло у осей УСМ и переводчика", L.InsertPosition.above_node(l9), rough=-0.18,
                 color=(0.82, 0.82, 0.82), cop=0.5)
    z(l10, "oil", _mask_pattern(l10, f"{MK}/polish_var.png", SMEAR_SCALE * 3.0, rot=1.3))
    # 11–12. органы управления (фосфат): заглажены пальцем — гладкий тёмный сатин, отпечатки с узором
    l11 = _layer("Органы — заглажены пальцем", L.InsertPosition.above_node(l10), rough=-0.22,
                 color=(0.62, 0.62, 0.62), cmode=L.BlendingMode.SoftLight, cop=0.2)
    z(l11, "controls", _mask_pattern(l11, f"{MK}/polish_var.png", SMEAR_SCALE * 2.0, rot=0.6))
    l12 = _layer("Органы — отпечатки", L.InsertPosition.above_node(l11), rough=-0.15, color=(0.85, 0.85, 0.85),
                 cop=0.35)
    p = _mask_pattern(l12, f"{MK}/prints_a.png", PRINT_SCALE * 1.6, rot=2.1)
    z(l12, "controls", _pattern(p, f"{MK}/prints_b.png", PRINT_SCALE * 1.3, rot=0.3, blend=L.BlendingMode.Lighten,
                                opacity=0.6))
    # 13. пыль в карманах (ниша задержки, у кнопок магазина, у оси переводчика, внутри скобы)
    l13 = _layer("Пыль в карманах", L.InsertPosition.above_node(l12), rough=0.15, color=(0.66, 0.62, 0.55),
                 cmode=L.BlendingMode.Normal, cop=0.45)
    g = sp_lib.mask_generator(l13, "mg_dirt/mg_dirt", {"dirt_level": 0.3, "dirt_contrast": 0.7, "grunge_amount": 0.3,
                                                       "Grunge_Scale": 6, "Use_Triplanar": 1, "edges_masking": 0.9})
    pz = _zs(l13, "lower", "pockets", above=g, blend=L.BlendingMode.Multiply)
    _pattern(pz, f"{MK}/dust_grain.png", GRAIN_SCALE, rot=0.7, opacity=0.5)
    # 14. ворсинки (синтетика — нити кодом в wear_lower.py): светлые, хлопковая ветошь
    l14 = _plain("Ворсинки", L.InsertPosition.above_node(l13), (0.86, 0.85, 0.82), 0.85, cop=0.9)
    z(l14, "lint")
    n_lower = 14

    inside = _new_group("internals")
    zi = lambda lay, zone, above=None: _zs(lay, "internals", zone, above=above, blend=L.BlendingMode.Multiply if above else None)
    i1 = _layer("Спуск — заглажен пальцем", inside, rough=-0.25, color=(0.62, 0.62, 0.62),
                cmode=L.BlendingMode.SoftLight, cop=0.2)
    zi(i1, "trigger_face", _mask_pattern(i1, f"{MK}/polish_var.png", SMEAR_SCALE * 2.0, rot=1.0))
    i2 = _layer("Спуск — отпечаток", L.InsertPosition.above_node(i1), rough=-0.15, color=(0.85, 0.85, 0.85), cop=0.35)
    zi(i2, "trigger_face", _mask_pattern(i2, f"{MK}/prints_a.png", PRINT_SCALE * 1.6, rot=0.5))
    i3 = _layer("Торцы осей — промаслены", L.InsertPosition.above_node(i2), rough=-0.15, color=(0.75, 0.75, 0.75),
                cop=0.6)
    zi(i3, "pin_ends")
    return f"lower: группа износа — {n_lower} слоёв; internals — 3"
