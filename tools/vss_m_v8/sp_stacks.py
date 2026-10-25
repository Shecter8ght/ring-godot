# Стеки слоёв Substance Painter для ВСС-М v8 по материалам (выполняются внутри Painter через мост).
# Цвета — sRGB (sp_lib переводит в рабочее линейное пространство), шероховатость и металличность — как есть.
# Масштабы трёхпроекционных масок подобраны на модели в миллиметрах (крышка коробки ~200 мм):
# 3–4 — потёртости и пятна в несколько миллиметров, 6–10 — пыль, 50 — шагрень полимера, 170 — зерно покрытия.
# Разбор 25.10 (замечания владельца и образцы Fab / Sketchfab «VSS Vintorez», Artem Goyko): металл — заводское
# покрытие со сдержанным глянцем (шероховатость ~0.3), местами вытертое до матового металла; живость даёт контраст
# глянца и вытертых мест, а не шумовые пятна (объёмный шум и широкая пыль читались «мылом»). Маски износа — фото-маски
# Painter grunge map 008/012/013, протирки wipe smudgy/directional, отпечатки fingerprints dirty/dusty (подбор
# превью масок на глушителе 25.10). Полимер цевья — лакированный, шагрень бликует.
import substance_painter.layerstack as L
import sp_lib
from sp_lib import fill, mask_generator, mask_proc, only_meshes, triplanar

EDGE = "mg_metal_edge_wear/mg_metal_edge_wear"
# grunge_scratches_fine при balance 0.5 даёт серый фон ~0.5 по всей площади — слой ложится на всю поверхность;
# balance 0.36 и contrast 0.55 уводят фон в чёрное, остаются царапины (подбор на глушителе 25.10)
SCR = {"invert": 0, "balance": 0.36, "contrast": 0.55}
DIRT = "mg_dirt/mg_dirt"
PARTS = "E:/Games/RING-godot/_asset_src/vss_m_v8/sp_parts"
WOOD_V6 = PARTS + "/wood_v6"                             # wood_veneer_bake.py: основа из фото шпона и маски
WOOD_BASE = WOOD_V6 + "/C_krasnyi_dub_color.png"         # вариант C — красный дуб (выбор владельца 26.10)
WOOD_HEIGHT = WOOD_V6 + "/C_krasnyi_dub_height.png"      # там же: поры и волокно, швы слоёв
KNURL = PARTS + "/suppressor_knurl_height.png"        # knurl_bake.py: накатка рифлёной части глушителя
KNURL_AREA = PARTS + "/suppressor_knurl_area.png"     # там же: где лежит накатка (маска области)


def _grain(pos, rough_op=0.35, height_op=0.0025):
    g = fill("Зерно", pos, rough="noise_gaussian_noise/gaussian_noise", height="noise_gaussian_noise/gaussian_noise")
    triplanar(g, 170.0)
    g.set_blending_mode(L.BlendingMode.Overlay, sp_lib.CH.SpecularRoughness)
    g.set_opacity(rough_op, sp_lib.CH.SpecularRoughness)
    g.set_opacity(height_op, sp_lib.CH.Height)
    return g


def _edge(name, pos, color, rough, level, contrast=0.65, grunge=0.6, metal=1.0, meshes=None):
    e = fill(name, pos, color=color, rough=rough, metal=metal)
    mask_generator(e, EDGE, {"Wear_Level": level, "Wear_Contrast": contrast, "Grunge_Amount": grunge, "grunge_scale": 4,
                             "Use_Triplanar": 1, "Edges_Smoothness": 0.6, "Ambient_Occlusion_Masking": 0.6,
                             "Curvature_Weight": 1.0})
    if meshes:
        only_meshes(e, meshes)
    return e


def _dirt(pos, color=(0.045, 0.04, 0.035), rough=0.85, level=0.3, opacity=0.7, metal=0.0, name="Грязь в углах",
          contrast=0.8):
    d = fill(name, pos, color=color, rough=rough, metal=metal)
    mask_generator(d, DIRT, {"dirt_level": level, "dirt_contrast": contrast, "grunge_amount": 0.4, "Grunge_Scale": 6,
                             "Use_Triplanar": 1, "edges_masking": 0.8})
    sp_lib.lop(d, opacity)
    return d


def _proc_layer(name, pos, proc, scale, opacity, params=None, **ch):
    lay = fill(name, pos, **ch)
    mask_proc(lay, proc, params, scale=scale, opacity=1.0)
    sp_lib.lop(lay, opacity)
    return lay


def _above(n):
    return L.InsertPosition.above_node(n)


def _bitmap(path):
    import substance_painter.resource as R
    stem = path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    for r in R.search("u:texture"):
        if r.identifier().name == stem:
            return r.identifier()
    return R.import_project_resource(path, R.Usage.TEXTURE).identifier()


def _uv(layer):
    layer.set_projection_mode(L.ProjectionMode.UV)


def _gm(i):
    return "noise_grunge_map_%03d/grunge_map_%03d" % (i, i)


def _mix(a, b, t):
    return tuple(x + (y - x) * t for x, y in zip(a, b))


def coated(st, coat, bare, wear=0.1, patch_bal=0.8, thin=0.45, scratches=0.35, prints=1.0, rail_meshes=None):
    """Изделие с заводским покрытием (воронение / анодирование): coat и bare — (цвет, шероховатость, металл)
    покрытия и металла под ним. Износ читается блеском и рельефом (замечание владельца 25.10: у пятен был тот же
    блеск, что у покрытия): покрытие глянцевое с лёгкими пятнами блеска и протирками; вокруг вытертых мест — рваная
    полоса истончившегося, полуматового покрытия; вытертое до металла — полностью матовое (площадь задаёт порог маски
    patch_bal — яркость обратной фото-маски: у grunge map обращение идёт после яркости, поэтому чем БОЛЬШЕ patch_bal,
    тем МЕНЬШЕ вытертых пятен (замер на steel_parts: 0.6 → 31 %, 0.78 → 12 %, 0.85 → 8 %); wear — уровень генератора
    износа кромок (0.08 → 17 % площади развёртки мелких деталей, 0.2 → 30 %), а не прозрачность — частичная прозрачность смешивала шероховатость и съедала разницу) и ниже покрытия на
    его толщину (ступенька по краю ловит свет; высоты в долях тысячной — единица высоты Painter огромна, ступенька
    0.007 по шумной маске дала «кору»); острые кромки заполированы до блеска; царапины — бороздки; грязь и пыль
    в углах, масло, отпечатки."""
    top = L.InsertPosition.from_textureset_stack(st)
    n = fill("01 Покрытие", top, color=coat[0], rough=coat[1], metal=coat[2], height=0.5)
    n = _grain(_above(n), 0.12, 0.0006)
    n.set_name("02 Зерно")
    n = _proc_layer("03 Блеск пятнами", _above(n), _gm(13), 1.2, 0.5, {"balance": 0.5, "contrast": 0.2},
                    rough=coat[1] + 0.07)
    n = _proc_layer("04 Протёрто до блеска", _above(n), "grunge_wipe_directional_heavy/grunge_wipe_directional_heavy", 1.8,
                    0.35, rough=max(0.12, coat[1] - 0.08))
    edge_p = {"Wear_Contrast": 0.6, "Grunge_Amount": 0.75, "grunge_scale": 6, "Use_Triplanar": 1, "Edges_Smoothness": 0.45,
              "Ambient_Occlusion_Masking": 0.6, "Curvature_Weight": 1.0}
    t = fill("05 Покрытие истончилось", _above(n), color=_mix(coat[0], bare[0], 0.4), rough=(coat[1] + bare[1]) / 2,
             metal=(coat[2] + bare[2]) / 2, height=0.4995)
    g = mask_generator(t, EDGE, dict(edge_p, Wear_Level=min(0.95, wear * 1.8), Wear_Contrast=0.35, Grunge_Amount=0.85))
    pm = mask_proc(t, _gm(8), {"invert": 1, "balance": patch_bal - 0.08, "contrast": 0.35}, scale=1.5, above=g,
                   blend=L.BlendingMode.Lighten)
    mask_proc(t, _gm(13), {"balance": 0.6, "contrast": 0.3}, scale=2.2, above=pm, blend=L.BlendingMode.Multiply)
    sp_lib.lop(t, thin)
    w = fill("06 Вытерто до металла", _above(t), color=bare[0], rough=bare[1], metal=bare[2], height=0.499)
    g = mask_generator(w, EDGE, dict(edge_p, Wear_Level=wear))
    mask_proc(w, _gm(8), {"invert": 1, "balance": patch_bal, "contrast": 0.75}, scale=1.5, above=g,
              blend=L.BlendingMode.Lighten)
    n = _grain(_above(w), 0.16, 0.0)
    n.set_name("07 Неровная матовость")
    n = _edge("08 Кромки до блеска", _above(n), _mix(bare[0], (0.75, 0.75, 0.76), 0.5), 0.24, wear * 0.6,
              contrast=0.85, grunge=0.6)
    if rail_meshes:
        n = _edge("09 Износ планки", _above(n), _mix(bare[0], (0.75, 0.75, 0.76), 0.4), 0.26, 0.5, contrast=0.8,
                  grunge=0.4, meshes=rail_meshes)
    n = _proc_layer("10 Царапины", _above(n), _gm(12), 2.5, scratches, {"invert": 1, "balance": 0.74, "contrast": 0.55},
                    color=_mix(coat[0], bare[0], 0.6), rough=0.42, metal=1.0, height=0.4993)
    n = _dirt(_above(n), color=(0.035, 0.03, 0.026), level=0.38, opacity=0.9, name="11 Грязь в углах")
    n = _dirt(_above(n), color=(0.3, 0.28, 0.25), rough=0.95, level=0.24, opacity=0.4, name="12 Пыль в углах", contrast=0.9)
    n = _proc_layer("13 Масло", _above(n), _gm(15), 1.8, 0.3, {"invert": 1, "balance": 0.72, "contrast": 0.4},
                    color=_mix(coat[0], (0.0, 0.0, 0.0), 0.3), rough=0.18)
    n = _proc_layer("14 Отпечатки жирные", _above(n), "grunge_fingerprints_dirty/grunge_fingerprints_dirty", 3.0,
                    0.4 * prints, {"Balance": 0.45, "Contrast": 0.35}, color=_mix(coat[0], (0.2, 0.19, 0.18), 0.4), rough=0.45)
    n = _proc_layer("15 Отпечатки пыльные", _above(n), "grunge_fingerprints_dusty/grunge_fingerprints_dusty", 3.0,
                    0.25 * prints, {"Balance": 0.45, "Contrast": 0.35}, color=(0.24, 0.23, 0.21), rough=0.7, metal=0.0)
    return n


# воронёная сталь: глянцевое тёмное покрытие, под ним матовая серая сталь с тёплым оттенком
STEEL_COAT = ((0.085, 0.085, 0.09), 0.22, 0.75)
STEEL_BARE = ((0.17, 0.165, 0.16), 0.62, 1.0)


def steel(st, rail_meshes=None, wear=0.1, patch_bal=0.8, scratches=0.35):
    """Сталь коробки, рамы, органов управления, прицельных: воронение, местами вытертое (см. coated)."""
    return coated(st, STEEL_COAT, STEEL_BARE, wear=wear, patch_bal=patch_bal, scratches=scratches, rail_meshes=rail_meshes)


def phosphate(st, rail_meshes=None, **kw):
    """Совместимость: прежнее имя стека стали."""
    return steel(st, rail_meshes=rail_meshes)


def suppressor(st):
    """Глушитель: то же покрытие чуть матовее; рифлёная часть — накатка картой высот: в канавках грязь и пыль
    (пятнами), вершины ромбов затёрты до металла; масло и отпечатки там, где за него берутся."""
    n = coated(st, ((0.08, 0.08, 0.085), 0.28, 0.7), STEEL_BARE, wear=0.1, patch_bal=0.78, scratches=0.3, prints=1.3)
    k = L.insert_fill(_above(n))
    k.set_name("16 Накатка")
    k.active_channels = {sp_lib.CH.Height}
    k.set_source(sp_lib.CH.Height, _bitmap(KNURL))
    _uv(k)
    k.set_opacity(0.45, sp_lib.CH.Height)
    only_meshes(k, ["Suppressor_knurl__sp"])

    def knurl_mask(layer, grooves):
        """Маска по накатке: grooves — в канавках (область накатки минус карта высот), иначе — по вершинам.
        Область — отдельной картой: маска «белое минус высота» без неё заливала весь глушитель."""
        layer.add_mask(L.MaskBackground.Black)
        m = L.insert_fill(L.InsertPosition.inside_node(layer, L.NodeStack.Mask))
        m.set_source(None, _bitmap(KNURL_AREA if grooves else KNURL))
        _uv(m)
        if grooves:
            m = L.insert_fill(L.InsertPosition.above_node(m))
            m.set_source(None, _bitmap(KNURL))
            _uv(m)
            m.set_blending_mode(L.BlendingMode.Subtract)
        return m
    d = fill("17 Грязь в канавках накатки", _above(k), color=(0.03, 0.027, 0.024), rough=0.85, metal=0.0)
    knurl_mask(d, True)
    sp_lib.lop(d, 0.65)
    only_meshes(d, ["Suppressor_knurl__sp"])
    u = fill("18 Пыль в канавках", _above(d), color=(0.26, 0.245, 0.22), rough=0.92, metal=0.0)
    m = knurl_mask(u, True)
    patch = L.insert_fill(L.InsertPosition.above_node(m))
    patch.set_source(None, sp_lib.rid(_gm(13), "u:procedural"))
    triplanar(patch, 1.4)
    patch.set_blending_mode(L.BlendingMode.Multiply)
    sp_lib.lop(u, 0.3)
    only_meshes(u, ["Suppressor_knurl__sp"])
    w = fill("19 Затёртые вершины накатки", _above(u), color=(0.2, 0.195, 0.19), rough=0.34, metal=1.0)
    knurl_mask(w, False)
    sp_lib.lop(w, 0.25)
    only_meshes(w, ["Suppressor_knurl__sp"])
    return w


def bare_steel(st):
    """Светлая сталь затвора и пружин: тонкая масляная плёнка (пятна блеска), нагар в углах, царапины,
    заполированные кромки."""
    top = L.InsertPosition.from_textureset_stack(st)
    n = fill("01 Сталь", top, color=(0.55, 0.55, 0.57), rough=0.34, metal=1.0)
    n = _grain(_above(n), 0.3, 0.0015)
    n = _proc_layer("03 Тусклые пятна", _above(n), "grunge_rough_dirty/grunge_rough_dirty", 3.0, 0.35,
                    color=(0.44, 0.44, 0.45), rough=0.46)
    n = _proc_layer("04 Масло", _above(n), "grunge_fingerprints_smeared_wide/grunge_fingerprints_smeared_wide", 4.0, 0.45,
                    color=(0.46, 0.45, 0.43), rough=0.16)
    n = _proc_layer("05 Царапины", _above(n), "grunge_scratches_fine/grunge_scratches_fine", 8.0, 0.5,
                    dict(SCR, scratches_amount=0.5), color=(0.72, 0.72, 0.74), rough=0.2)
    n = _edge("06 Заполированные кромки", _above(n), (0.78, 0.78, 0.8), 0.17, 0.42)
    n = _dirt(_above(n), color=(0.07, 0.065, 0.06), rough=0.7, level=0.38, opacity=0.85, metal=0.2, name="07 Нагар")
    return n


def polymer(st, base=(0.03, 0.03, 0.032), rough=0.3, stipple=0.038, stipple_scale=32.0, pores=0.2,
            spots="noise_cells_1/cells_1", matte=0.2):
    """Полиамид (цевьё, магазины), образец владельца: лакированный пластик с шагренью. Лак глянцевый (0.2), бугорки
    шагрени ещё глаже (0.1) — ловят блики искрами, в порах лак тусклее (0.55) и пыль; поэтому в полосе блика шагрень
    искрит, а вне её цевьё чёрное (при шероховатости ~0.4 отражение софтбокса растекалось по всей грани — «серое»).
    Местами лак матовее, на выступах и кромках затёрт до блеска; редкие царапины, грязь и пыль в углах, отпечатки
    (на глянце — мутные). Шагрень цевья — купола ячеистого шума (noise_cells_1): у пятнистых шумов половина площади
    уходила в «поры» с тусклым лаком и пылью, и цевьё читалось серым (подбор вариантов 25.10)."""
    top = L.InsertPosition.from_textureset_stack(st)
    n = fill("01 Полимер", top, color=base, rough=rough, metal=0.0)
    s_ = fill("02 Шагрень", _above(n), height=spots)
    triplanar(s_, stipple_scale)
    s_.set_opacity(stipple, sp_lib.CH.Height)
    gl = fill("02б Блеск бугорков", _above(s_), rough=0.1)
    gl.add_mask(L.MaskBackground.Black)
    gm_ = L.insert_fill(L.InsertPosition.inside_node(gl, L.NodeStack.Mask))
    gm_.set_source(None, sp_lib.rid(spots, "u:procedural"))
    triplanar(gm_, stipple_scale)
    sp_lib.lop(gl, 0.9)

    def pores_mask(layer):
        layer.add_mask(L.MaskBackground.White)
        m = L.insert_fill(L.InsertPosition.inside_node(layer, L.NodeStack.Mask))
        m.set_source(None, sp_lib.rid(spots, "u:procedural"))
        triplanar(m, stipple_scale)
        m.set_blending_mode(L.BlendingMode.Subtract)
    pt = fill("03 Лак тусклее в порах", _above(gl), rough=0.55)
    pores_mask(pt)
    sp_lib.lop(pt, 0.8)
    pr = fill("03б Пыль в порах шагрени", _above(pt), color=(0.13, 0.125, 0.12), rough=0.8)
    pores_mask(pr)
    sp_lib.lop(pr, pores)
    n = _proc_layer("04 Матовее пятнами", _above(pr), "grunge_wipe_smudgy_soft/grunge_wipe_smudgy_soft", 1.6, matte,
                    {"Balance": 0.55, "Contrast": 0.3}, rough=rough + 0.18)
    n = _proc_layer("05 Затёрто до блеска", _above(n), "grunge_wipe_directional_heavy/grunge_wipe_directional_heavy", 1.8,
                    0.35, rough=0.08)
    n = _proc_layer("06 Царапины", _above(n), _gm(12), 2.5, 0.35, {"invert": 1, "balance": 0.74, "contrast": 0.55},
                    color=(0.1, 0.1, 0.105), rough=rough + 0.2)
    n = _edge("07 Затёртые кромки", _above(n), (0.07, 0.07, 0.075), 0.08, 0.3, contrast=0.8, metal=0.0)
    n = _dirt(_above(n), color=(0.03, 0.027, 0.024), level=0.38, opacity=0.85, name="08 Грязь в углах")
    n = _dirt(_above(n), color=(0.3, 0.28, 0.25), rough=0.95, level=0.24, opacity=0.4, name="09 Пыль в углах", contrast=0.9)
    n = _proc_layer("10 Отпечатки жирные", _above(n), "grunge_fingerprints_dirty/grunge_fingerprints_dirty", 3.0, 0.45,
                    {"Balance": 0.45, "Contrast": 0.35}, color=(0.07, 0.068, 0.065), rough=rough + 0.22)
    return n


MAG_LIPS = PARTS + "/mag_lips.png"      # mag_masks_bake.py: губки и передний упор (затвор трёт до блеска)


def magazine(st):
    """Магазин — литой полиамид ТОЗ (фото владельца 26.10): тёмно-графитовый, матовый, без лака, литьё слегка
    пятнистое; губки и передний упор затвор затёр до блеска; на кромках белёсые потёртости пластика (не краска — светлее
    и матовее), редкие светлые царапины, засаленные места, грязь в углах и пыль в рёбрах. Порядок по справке навыка:
    основа → рельеф → блеск → повреждения → резкость (эффект группы) → грязь и пыль."""
    CH = sp_lib.CH
    grp = L.insert_group(L.InsertPosition.from_textureset_stack(st))
    grp.set_name("Полиамид")
    ins = L.InsertPosition.inside_node(grp, L.NodeStack.Substack)
    n = fill("01 Полиамид", ins, color=(0.07, 0.07, 0.074), rough=0.55, metal=0.0)
    n = fill("02 Литьё: зерно", _above(n), rough="noise_gaussian_noise/gaussian_noise",
             height="noise_gaussian_noise/gaussian_noise")
    triplanar(n, 120.0)
    n.set_blending_mode(L.BlendingMode.Overlay, CH.SpecularRoughness)
    n.set_opacity(0.2, CH.SpecularRoughness)
    n.set_opacity(0.0008, CH.Height)
    n = fill("03 Литьё: пятна тона", _above(n), color=(0.7, 0.7, 0.7))
    n.set_blending_mode(L.BlendingMode.SoftLight, CH.BaseColor)
    mask_proc(n, "noise_clouds_2/clouds_2", None, scale=1.2)
    sp_lib.lop(n, 0.25)
    n = _proc_layer("04 Засаленные места — глаже", _above(n), "grunge_wipe_smudgy_soft/grunge_wipe_smudgy_soft", 1.6,
                    0.45, {"Balance": 0.55, "Contrast": 0.3}, rough=0.42)
    n = fill("05 Губки и упор затёрты до блеска", _above(n), color=(0.2, 0.2, 0.205), rough=0.26)
    g = mask_generator(n, EDGE, {"Wear_Level": 0.45, "Wear_Contrast": 0.6, "Grunge_Amount": 0.5, "grunge_scale": 4,
                                 "Use_Triplanar": 1, "Edges_Smoothness": 0.6, "Ambient_Occlusion_Masking": 0.5,
                                 "Curvature_Weight": 1.0})
    _bmask(n, MAG_LIPS, blend=L.BlendingMode.Multiply, above=g)
    n = fill("06 Белёсые потёртости кромок", _above(n), color=(0.36, 0.355, 0.35), rough=0.78)
    # узко по кромкам: с histogram scan и уровнем 0.16 потёртости ложились на большую часть магазина (замер 26.10)
    mask_generator(n, EDGE, {"Wear_Level": 0.06, "Wear_Contrast": 0.9, "Grunge_Amount": 0.85, "grunge_scale": 3,
                             "Use_Triplanar": 1, "Edges_Smoothness": 0.3, "Ambient_Occlusion_Masking": 0.5,
                             "Curvature_Weight": 1.0})
    sp_lib.lop(n, 0.5)
    n = fill("07 Царапины", _above(n), color=(0.24, 0.24, 0.24), rough=0.66)
    mask_proc(n, _gm(12), {"invert": 1, "balance": 0.78, "contrast": 0.55}, scale=2.5)
    sp_lib.lop(n, 0.3)
    sh = L.insert_filter_effect(L.InsertPosition.inside_node(grp, L.NodeStack.Content),
                                sp_lib.rid("sharpen/sharpen", "u:filter"))
    sh.get_source().set_parameters({"intensity": 0.3})
    n = _dirt(_above(grp), color=(0.035, 0.032, 0.03), level=0.36, opacity=0.8, name="08 Грязь в углах")
    n = _dirt(_above(n), color=(0.42, 0.4, 0.37), rough=0.95, level=0.12, opacity=0.3, name="09 Пыль в рёбрах",
              contrast=0.9)
    return n


def anodized(st):
    """Муфта: чёрное анодирование со сдержанным глянцем поверх алюминия, вытертое на кромках и пятнами (coated)."""
    return coated(st, ((0.07, 0.07, 0.075), 0.3, 0.6), ((0.55, 0.55, 0.57), 0.5, 1.0), wear=0.06, patch_bal=0.9,
                  thin=0.3, scratches=0.15)


def optic_body(st):
    """Корпус прицела: чёрное анодирование, матовее муфты; вытерто до алюминия только узко по острым кромкам (стек
    coated с пятнами на мелких круглых деталях прицелов уводил до алюминия 17–20 % площади — белые проплешины),
    редкие царапины, грязь в углах, отпечатки."""
    top = L.InsertPosition.from_textureset_stack(st)
    n = fill("01 Анодирование", top, color=(0.07, 0.07, 0.075), rough=0.42, metal=0.4)
    n = _grain(_above(n), 0.15, 0.0005)
    n = _proc_layer("03 Блеск пятнами", _above(n), _gm(13), 1.2, 0.4, {"balance": 0.5, "contrast": 0.2}, rough=0.5)
    n = _edge("04 Кромки до алюминия", _above(n), (0.55, 0.55, 0.57), 0.4, 0.035, contrast=0.92, grunge=0.7)
    n = _proc_layer("05 Царапины", _above(n), _gm(12), 2.5, 0.25, {"invert": 1, "balance": 0.8, "contrast": 0.55},
                    color=(0.3, 0.3, 0.31), rough=0.45, metal=1.0)
    n = _dirt(_above(n), color=(0.035, 0.03, 0.026), level=0.38, opacity=0.8, name="06 Грязь в углах")
    n = _dirt(_above(n), color=(0.3, 0.28, 0.25), rough=0.95, level=0.22, opacity=0.3, name="07 Пыль в углах", contrast=0.9)
    n = _proc_layer("08 Отпечатки", _above(n), "grunge_fingerprints_dirty/grunge_fingerprints_dirty", 3.0, 0.3,
                    {"Balance": 0.45, "Contrast": 0.35}, color=(0.11, 0.105, 0.1), rough=0.55)
    return n


def optic_rim(st):
    """Ободки и проточки: точёный алюминий — светлый, сдержанный блеск, тонкое зерно; грязь в углах, налёт пятнами."""
    top = L.InsertPosition.from_textureset_stack(st)
    n = fill("01 Точёный алюминий", top, color=(0.62, 0.62, 0.64), rough=0.32, metal=1.0)
    n = _grain(_above(n), 0.25, 0.0)
    n = _proc_layer("03 Налёт пятнами", _above(n), _gm(13), 1.4, 0.35, {"balance": 0.5, "contrast": 0.25},
                    color=(0.45, 0.45, 0.46), rough=0.45)
    n = _dirt(_above(n), color=(0.05, 0.045, 0.04), level=0.4, opacity=0.8, name="04 Грязь в углах")
    n = _proc_layer("05 Отпечатки", _above(n), "grunge_fingerprints_dirty/grunge_fingerprints_dirty", 3.0, 0.3,
                    {"Balance": 0.45, "Contrast": 0.35}, color=(0.5, 0.5, 0.5), rough=0.5)
    return n


def optic_engraving(st):
    """Гравировка: заливка краской (светлая, матовая), в углублениях потемнела от грязи, местами выкрошилась."""
    top = L.InsertPosition.from_textureset_stack(st)
    n = fill("01 Краска гравировки", top, color=(0.84, 0.82, 0.74), rough=0.72, metal=0.0)
    n = _proc_layer("02 Выкрошилась", _above(n), _gm(8), 1.5, 1.0, {"invert": 1, "balance": 0.82, "contrast": 0.6},
                    color=(0.07, 0.07, 0.075), rough=0.42, metal=0.5)
    n = _dirt(_above(n), color=(0.35, 0.32, 0.27), level=0.45, opacity=0.6, name="03 Грязь в краске")
    return n


def optic_inner(st):
    """Внутренняя чернь (бленды, оправы стёкол): матовая чёрная краска, пыль."""
    top = L.InsertPosition.from_textureset_stack(st)
    n = fill("01 Чернь", top, color=(0.035, 0.035, 0.037), rough=0.9, metal=0.0)
    n = _dirt(_above(n), color=(0.25, 0.24, 0.22), rough=0.95, level=0.3, opacity=0.35, name="02 Пыль")
    return n


def rubber(st):
    top = L.InsertPosition.from_textureset_stack(st)
    n = fill("01 Резина", top, color=(0.05, 0.05, 0.05), rough=0.86, metal=0.0)
    n = _grain(_above(n), 0.25, 0.003)
    n = _proc_layer("03 Потёртости", _above(n), "grunge_scratches_rough/grunge_scratches_rough", 3.0, 0.35,
                    color=(0.09, 0.09, 0.09), rough=0.7)
    n = _edge("04 Затёртые кромки", _above(n), (0.085, 0.085, 0.085), 0.62, 0.38, metal=0.0)
    n = _dirt(_above(n), color=(0.2, 0.19, 0.17), rough=0.95, level=0.4, opacity=0.5, name="05 Пыль в углублениях")
    return n


def rounds(st):
    """Патрон 9×39: лакированная стальная гильза (оливково-бурый лак, на кромках сталь) и пуля в томпаковой оболочке."""
    top = L.InsertPosition.from_textureset_stack(st)
    n = fill("01 Лак гильзы", top, color=(0.44, 0.38, 0.25), rough=0.38, metal=0.55)
    only_meshes(n, ["Round_case__sp"])
    n2 = fill("02 Томпак пули", _above(n), color=(0.80, 0.56, 0.42), rough=0.3, metal=1.0)
    only_meshes(n2, ["Round_bullet__sp"])
    n = _grain(_above(n2), 0.25, 0.001)
    n = _proc_layer("04 Пятна лака", _above(n), "grunge_rough_dirty/grunge_rough_dirty", 3.0, 0.3,
                    color=(0.40, 0.34, 0.22), rough=0.5)
    n = _proc_layer("05 Царапины", _above(n), "grunge_scratches_fine/grunge_scratches_fine", 8.0, 0.4,
                    dict(SCR, scratches_amount=0.5), color=(0.62, 0.6, 0.56), rough=0.25, metal=1.0)
    n = _edge("06 Кромки", _above(n), (0.66, 0.64, 0.6), 0.22, 0.42)
    n = _proc_layer("07 Окисление пули", _above(n), "grunge_rough_dirty/grunge_rough_dirty", 2.5, 0.35,
                    color=(0.5, 0.33, 0.22), rough=0.5)
    only_meshes(n, ["Round_bullet__sp"])
    return n


def _wmask(kind):
    return f"{WOOD_V6}/mask_{kind}.png"


def _uv_bitmap_fill(name, pos, color=None, height=None, rough=None, metal=None):
    """Заливка с картами из файлов по развёртке (цвет/высота) и числами для остальных каналов."""
    f = L.insert_fill(pos)
    f.set_name(name)
    ch = {}
    if color is not None:
        ch[sp_lib.CH.BaseColor] = _bitmap(color) if isinstance(color, str) else sp_lib._val(color)
    if height is not None:
        ch[sp_lib.CH.Height] = _bitmap(height)
    if rough is not None:
        ch[sp_lib.CH.SpecularRoughness] = _bitmap(rough) if isinstance(rough, str) else sp_lib._val(rough, data=True)
    if metal is not None:
        ch[sp_lib.CH.BaseMetalness] = sp_lib._val(metal, data=True)
    f.active_channels = set(ch)
    for c, v in ch.items():
        f.set_source(c, v)
    _uv(f)
    return f


def _bmask(layer, path, blend=None, above=None, opacity=1.0, background=None):
    """Запечённая ч/б карта (по развёртке) в маске слоя или группы; blend — смешение с тем, что ниже в маске."""
    if not layer.has_mask():
        layer.add_mask(background or L.MaskBackground.Black)
    pos = L.InsertPosition.above_node(above) if above else L.InsertPosition.inside_node(layer, L.NodeStack.Mask)
    m = L.insert_fill(pos)
    m.set_source(None, _bitmap(path))
    _uv(m)
    if blend is not None:
        m.set_blending_mode(blend)
    m.set_opacity(opacity)
    return m


def _mfilter(above, name, params):
    """Фильтр в маске над узлом: histogram_scan — порог и контраст (читается издали), warp — рваный край, blur."""
    e = L.insert_filter_effect(L.InsertPosition.above_node(above), sp_lib.rid(name + "/" + name, "u:filter"))
    e.get_source().set_parameters(params)
    return e


def _raw_wood(name, pos, rough=0.82, lift=0.0006):
    """Группа «лак снят до сырой древесины»: светлее (Screen — волокно основы остаётся), бледнее (Saturation),
    самое матовое и ниже лака на его толщину. Маску задаёт вызывающий."""
    g = L.insert_group(pos)
    g.set_name(name)
    a = fill("Светлее", L.InsertPosition.inside_node(g, L.NodeStack.Substack), color=(0.42, 0.36, 0.27))
    a.set_blending_mode(L.BlendingMode.Screen, sp_lib.CH.BaseColor)
    b = fill("Бледнее", _above(a), color=(0.5, 0.5, 0.5))
    b.set_blending_mode(L.BlendingMode.Saturation, sp_lib.CH.BaseColor)
    sp_lib.lop(b, 0.25)
    c = fill("Матовое, без лака", _above(b), rough=rough, height=lift)
    c.set_blending_mode(L.BlendingMode.Subtract, sp_lib.CH.Height)
    return g


def wood(st):
    """Приклад — клеёная фанера под лаком (26.10: «скучная и ненастоящая»; разбор по справке навыка
    wood-and-paint-layers.md и образцам владельца с Fab). Порядок: дерево → рельеф → крупные пятна → лак → тона →
    повреждения → резкость → грязь, пыль, следы рук. Основа — фото шпона, вариант C (wood_veneer_bake.py): само дерево
    матовое, блеск даёт лак. Три тона: средний — древесина; тёмный — стыки и поры по AO и к концам приклада (чуть
    глянцевее, как лак); светлый — лак протёрт до сырой древесины на кромках и в местах хвата (светлее, бледнее, самый
    матовый). Крупные пятна света и тени — Soft Light (Normal съел бы волокно), полосами вдоль волокна. Повреждения «крупное — среднее —
    мелкое»: сколы лака по кромкам, редкие вмятины, царапины. Слабая резкость — эффектом на группу дерева и лака
    (поверх слоёв фильтр Painter API не вставляет), грязь и пыль — после неё. Маски мест — wood_veneer_bake.py masks."""
    CH = sp_lib.CH
    grp = L.insert_group(L.InsertPosition.from_textureset_stack(st))
    grp.set_name("Дерево и лак")
    n = _uv_bitmap_fill("01 Дерево", L.InsertPosition.inside_node(grp, L.NodeStack.Substack), color=WOOD_BASE,
                        rough=0.78, metal=0.0)
    h = _uv_bitmap_fill("02 Поры и волокно", _above(n), height=WOOD_HEIGHT)
    h.set_opacity(0.045, CH.Height)
    # тон гуляет полосами вдоль волокна, как у настоящей древесины (круглые пятна шума читались плесенью — владелец 26.10)
    n = fill("03 Тон вдоль волокна светлее", _above(h), color=(0.78, 0.75, 0.7))
    n.set_blending_mode(L.BlendingMode.SoftLight, CH.BaseColor)
    _bmask(n, _wmask("streaks"))
    sp_lib.lop(n, 0.22)
    n = fill("04 Тон вдоль волокна темнее", _above(n), color=(0.3, 0.24, 0.19))
    n.set_blending_mode(L.BlendingMode.SoftLight, CH.BaseColor)
    _bmask(n, _wmask("streaks"), blend=L.BlendingMode.Subtract, background=L.MaskBackground.White)
    sp_lib.lop(n, 0.15)
    n = fill("05 Темнее к концам", _above(n), color=(0.3, 0.25, 0.2))
    n.set_blending_mode(L.BlendingMode.SoftLight, CH.BaseColor)
    _bmask(n, _wmask("ends"))
    sp_lib.lop(n, 0.35)
    # лак: тёплый тон тонким слоем и полуматовый блеск; в порах проседает и тусклее
    n = fill("06 Лак", _above(n), color=(0.95, 0.9, 0.8), rough=0.4)
    n.set_blending_mode(L.BlendingMode.Multiply, CH.BaseColor)
    n.set_opacity(0.3, CH.BaseColor)
    n = fill("07 Лак в порах тусклее", _above(n), rough=0.56)
    m = _bmask(n, WOOD_HEIGHT, blend=L.BlendingMode.Subtract, background=L.MaskBackground.White)
    _mfilter(m, "histogram_scan", {"Position": 0.42, "Contrast": 0.55})
    sp_lib.lop(n, 0.6)
    n = fill("08 Апельсиновая корка", _above(n), rough="noise_clouds_2/clouds_2", height="noise_clouds_2/clouds_2")
    triplanar(n, 60.0)
    n.set_blending_mode(L.BlendingMode.Overlay, CH.SpecularRoughness)
    n.set_opacity(0.12, CH.SpecularRoughness)
    n.set_opacity(0.0012, CH.Height)
    n = _proc_layer("09 Неровный блеск лака", _above(n), "grunge_wipe_smudgy_soft/grunge_wipe_smudgy_soft", 1.6, 0.5,
                    {"Balance": 0.55, "Contrast": 0.3}, rough=0.5)
    n = fill("10 Натёрто руками до блеска", _above(n), color=(0.9, 0.86, 0.8), rough=0.27)
    n.set_blending_mode(L.BlendingMode.Multiply, CH.BaseColor)
    m = _bmask(n, _wmask("hold"))
    mask_proc(n, "grunge_wipe_smudgy_soft/grunge_wipe_smudgy_soft", {"Balance": 0.62, "Contrast": 0.3}, scale=1.6,
              blend=L.BlendingMode.Multiply, above=m)
    sp_lib.lop(n, 0.8)
    # тёмный тон: стыки и поры по AO и к концам — темнее и чуть глянцевее, рельеф волокна не трогает
    n = fill("11 Тёмный тон: стыки, поры, концы", _above(n), color=(0.62, 0.55, 0.48), rough=0.36)
    n.set_blending_mode(L.BlendingMode.Multiply, CH.BaseColor)
    g = mask_generator(n, DIRT, {"dirt_level": 0.35, "dirt_contrast": 0.6, "grunge_amount": 0.0, "Grunge_Scale": 5,
                                 "Use_Triplanar": 1, "edges_masking": 0.8})
    _bmask(n, _wmask("ends"), blend=L.BlendingMode.Lighten, above=g, opacity=0.4)
    sp_lib.lop(n, 0.38)
    # светлый тон: лак протёрт до дерева — по кромкам (рвёт grunge) и в местах хвата, порог контрастный
    w = _raw_wood("12 Светлый тон: протёрто до дерева", _above(n))
    m = _bmask(w, _wmask("hold"))
    m = mask_proc(w, "grunge_wipe_brushed/grunge_wipe_brushed", None, scale=1.4, blend=L.BlendingMode.Multiply, above=m)
    g = mask_generator(w, EDGE, {"Wear_Level": 0.2, "Wear_Contrast": 0.7, "Grunge_Amount": 0.85, "grunge_scale": 4,
                                 "Use_Triplanar": 1, "Edges_Smoothness": 0.5, "Ambient_Occlusion_Masking": 0.6,
                                 "Curvature_Weight": 1.0}, above=m)
    g.set_blending_mode(L.BlendingMode.Lighten)
    _mfilter(g, "histogram_scan", {"Position": 0.5, "Contrast": 0.35})
    # сколы лака: редкие, крупнее и резче протёртого — по кромкам окон, затыльника и низа
    c = _raw_wood("13 Сколы лака", _above(w), rough=0.86, lift=0.0012)
    g = mask_generator(c, EDGE, {"Wear_Level": 0.07, "Wear_Contrast": 0.95, "Grunge_Amount": 0.95, "grunge_scale": 2,
                                 "Use_Triplanar": 1, "Edges_Smoothness": 0.2, "Ambient_Occlusion_Masking": 0.4,
                                 "Curvature_Weight": 1.0})
    m = mask_proc(c, "grunge_paint_scraped/grunge_paint_scraped", None, scale=1.2, blend=L.BlendingMode.Multiply, above=g)
    _mfilter(m, "histogram_scan", {"Position": 0.62, "Contrast": 0.8})
    # вмятины по месту (wood_veneer_bake.py DENTS): одна крупная, три средних, мелкие по кромкам — примятое волокно
    # темнее; процедурные пятна закрывали четверть приклада и читались плесенью
    n = fill("14 Вмятины", _above(c), color=(0.82, 0.76, 0.7), rough=0.55, height=0.0009)
    n.set_blending_mode(L.BlendingMode.Multiply, CH.BaseColor)
    n.set_blending_mode(L.BlendingMode.Subtract, CH.Height)
    _bmask(n, _wmask("dents"))
    n = fill("15 Царапины лака", _above(n), color=(0.3, 0.28, 0.26), rough=0.62)
    n.set_blending_mode(L.BlendingMode.Screen, CH.BaseColor)
    mask_proc(n, _gm(12), {"invert": 1, "balance": 0.76, "contrast": 0.55}, scale=2.5)
    sp_lib.lop(n, 0.5)
    sh = L.insert_filter_effect(L.InsertPosition.inside_node(grp, L.NodeStack.Content),
                                sp_lib.rid("sharpen/sharpen", "u:filter"))
    sh.get_source().set_parameters({"intensity": 0.35})
    # после резкости: грязь в углах, пыль (где руками не трут), засаленность
    n = _dirt(_above(grp), color=(0.14, 0.09, 0.055), rough=0.8, level=0.32, opacity=0.35, name="16 Грязь в углах")
    n = fill("17 Пыль", _above(n), color=(0.55, 0.52, 0.47), rough=0.92)
    g = mask_generator(n, DIRT, {"dirt_level": 0.22, "dirt_contrast": 0.85, "grunge_amount": 0.6, "Grunge_Scale": 8,
                                 "Use_Triplanar": 1, "edges_masking": 0.9})
    _bmask(n, _wmask("hold"), blend=L.BlendingMode.Subtract, above=g)
    sp_lib.lop(n, 0.35)
    n = _proc_layer("18 Засаленность", _above(n), "grunge_fingerprints_dirty/grunge_fingerprints_dirty", 2.5, 0.2,
                    {"Balance": 0.45, "Contrast": 0.35}, color=(0.8, 0.72, 0.62), rough=0.36)
    n.set_blending_mode(L.BlendingMode.Multiply, CH.BaseColor)
    return n


MARKS_DIR = "E:/Games/RING-godot/_asset_src/vss_m_v8/sp_marks"     # contact_marks.py: следы рук и жизни по местам
MARK_BASE_ROUGH = {"receiver": 0.22, "steel_parts": 0.22, "suppressor": 0.28, "sleeve": 0.3, "handguard": 0.36,
                   "magazine": 0.5, "wood": 0.32, "bare_steel": 0.34, "rubber": 0.86}


def _mark_layer(name, pos, path, opacity, **ch):
    lay = fill(name, pos, **ch)
    lay.add_mask(L.MaskBackground.Black)
    m = L.insert_fill(L.InsertPosition.inside_node(lay, L.NodeStack.Mask))
    m.set_source(None, _bitmap(path))
    _uv(m)
    sp_lib.lop(lay, opacity)
    return lay


def contact_marks(st, set_name):
    """Следы по местам поверх стека набора (маски владельца, запечённые contact_marks.py): протирки — полосы блеска,
    копоть — матовая чёрная, масло — тёмное и глянцевое, ладони и пальцы — жир: на глянце мутные пятна, на матовом —
    блестящие."""
    import os

    def path(kind):
        return f"{MARKS_DIR}/{set_name}_{kind}.png"
    r = MARK_BASE_ROUGH.get(set_name, 0.3)
    greasy = r + 0.18 if r < 0.4 else r - 0.16
    pos = _above(L.get_root_layer_nodes(st)[0])
    if os.path.exists(path("wipe")):
        n = _mark_layer("М1 Протирки", pos, path("wipe"), 0.5, rough=max(0.1, r - 0.1))
        pos = _above(n)
    if os.path.exists(path("soot")):
        n = _mark_layer("М2 Копоть", pos, path("soot"), 0.85, color=(0.03, 0.028, 0.026), rough=0.8, metal=0.0)
        pos = _above(n)
    if os.path.exists(path("oil")):
        n = _mark_layer("М3 Масло", pos, path("oil"), 0.85, color=(0.5, 0.46, 0.4), rough=0.12)
        n.set_blending_mode(L.BlendingMode.Multiply, sp_lib.CH.BaseColor)
        pos = _above(n)
    if os.path.exists(path("palms")):
        n = _mark_layer("М4 Ладони", pos, path("palms"), 0.55, color=(0.82, 0.8, 0.78), rough=greasy)
        n.set_blending_mode(L.BlendingMode.Multiply, sp_lib.CH.BaseColor)
        pos = _above(n)
    if os.path.exists(path("prints")):
        n = _mark_layer("М5 Отпечатки пальцев", pos, path("prints"), 0.75, color=(0.78, 0.76, 0.74), rough=greasy)
        n.set_blending_mode(L.BlendingMode.Multiply, sp_lib.CH.BaseColor)
