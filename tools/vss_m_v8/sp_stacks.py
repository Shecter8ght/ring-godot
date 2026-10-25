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
WOOD_BASE = PARTS + "/wood_laminate_v5.png"              # wood_laminate_bake.py: шпон и полосы слоёв фанеры
WOOD_HEIGHT = PARTS + "/wood_height_v5.png"              # там же: рельеф волокна и клеевых швов
KNURL = PARTS + "/suppressor_knurl_height.png"        # knurl_bake.py: накатка рифлёной части глушителя


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


def coated(st, coat, bare, wear=0.3, patches=0.4, thin=0.3, scratches=0.2, prints=1.0, rail_meshes=None):
    """Изделие с заводским покрытием (воронение / анодирование): coat и bare — (цвет, шероховатость, металл)
    покрытия и металла под ним. Покрытие со сдержанным глянцем и неровным блеском (протирки), местами истончилось,
    на кромках и выступах и пятнами на плоскостях вытерто до матового металла, по самым острым кромкам металл
    заполирован до блеска; редкие царапины, грязь и пыль в углах, тонкий налёт грязи, масло, отпечатки."""
    top = L.InsertPosition.from_textureset_stack(st)
    n = fill("01 Покрытие", top, color=coat[0], rough=coat[1], metal=coat[2])
    n = _grain(_above(n), 0.18, 0.0008)
    n.set_name("02 Зерно")
    n = _proc_layer("03 Глянец неровный", _above(n), "grunge_wipe_smudgy_soft/grunge_wipe_smudgy_soft", 1.6, 0.6,
                    {"Balance": 0.55, "Contrast": 0.3}, rough=coat[1] + 0.16)
    n = _proc_layer("04 Протёрто до блеска", _above(n), "grunge_wipe_directional_heavy/grunge_wipe_directional_heavy", 1.8,
                    0.35, rough=max(0.12, coat[1] - 0.12))
    mid = _mix(coat[0], bare[0], 0.35)
    n = _proc_layer("05 Покрытие истончилось", _above(n), _gm(13), 1.4, thin, {"invert": 1, "balance": 0.35, "contrast": 0.5},
                    color=mid, rough=(coat[1] + bare[1]) / 2, metal=(coat[2] + bare[2]) / 2)
    w = fill("06 Вытерто до металла", _above(n), color=bare[0], rough=bare[1], metal=bare[2])
    g = mask_generator(w, EDGE, {"Wear_Level": wear, "Wear_Contrast": 0.55, "Grunge_Amount": 0.75, "grunge_scale": 6,
                                 "Use_Triplanar": 1, "Edges_Smoothness": 0.45, "Ambient_Occlusion_Masking": 0.6,
                                 "Curvature_Weight": 1.0})
    mask_proc(w, _gm(8), {"invert": 1, "balance": 0.32, "contrast": 0.6}, scale=1.5, above=g,
              blend=L.BlendingMode.Lighten, opacity=patches)
    n = _edge("07 Кромки до блеска", _above(w), _mix(bare[0], (0.75, 0.75, 0.76), 0.5), 0.24, wear * 0.55,
              contrast=0.85, grunge=0.6)
    if rail_meshes:
        n = _edge("08 Износ планки", _above(n), _mix(bare[0], (0.75, 0.75, 0.76), 0.4), 0.26, 0.5, contrast=0.8,
                  grunge=0.4, meshes=rail_meshes)
    n = _proc_layer("09 Царапины", _above(n), _gm(12), 2.5, scratches, {"invert": 1, "balance": 0.32, "contrast": 0.55},
                    color=_mix(coat[0], bare[0], 0.6), rough=0.3, metal=1.0)
    n = _dirt(_above(n), color=(0.035, 0.03, 0.026), level=0.38, opacity=0.9, name="10 Грязь в углах")
    n = _dirt(_above(n), color=(0.3, 0.28, 0.25), rough=0.95, level=0.24, opacity=0.4, name="11 Пыль в углах", contrast=0.9)
    n = _proc_layer("12 Налёт грязи", _above(n), "grunge_dirt_thin/grunge_dirt_thin", 2.0, 0.3,
                    color=(0.07, 0.064, 0.058), rough=0.62, metal=0.0)
    n = _proc_layer("13 Масло", _above(n), _gm(15), 1.8, 0.25, {"invert": 1, "balance": 0.4, "contrast": 0.4},
                    color=_mix(coat[0], (0.0, 0.0, 0.0), 0.3), rough=0.16)
    n = _proc_layer("14 Отпечатки жирные", _above(n), "grunge_fingerprints_dirty/grunge_fingerprints_dirty", 3.0,
                    0.45 * prints, {"Balance": 0.45, "Contrast": 0.35}, color=_mix(coat[0], (0.2, 0.19, 0.18), 0.4), rough=0.5)
    n = _proc_layer("15 Отпечатки пыльные", _above(n), "grunge_fingerprints_dusty/grunge_fingerprints_dusty", 3.0,
                    0.3 * prints, {"Balance": 0.45, "Contrast": 0.35}, color=(0.24, 0.23, 0.21), rough=0.7, metal=0.0)
    return n


# воронёная сталь: покрытие тёмное со сдержанным глянцем, под ним серая сталь с тёплым оттенком
STEEL_COAT = ((0.085, 0.085, 0.09), 0.3, 0.75)
STEEL_BARE = ((0.17, 0.165, 0.16), 0.58, 1.0)


def steel(st, rail_meshes=None, wear=0.3, patches=0.4, scratches=0.2):
    """Сталь коробки, рамы, органов управления, прицельных: воронение, местами вытертое (см. coated)."""
    return coated(st, STEEL_COAT, STEEL_BARE, wear=wear, patches=patches, scratches=scratches, rail_meshes=rail_meshes)


def phosphate(st, rail_meshes=None, **kw):
    """Совместимость: прежнее имя стека стали."""
    return steel(st, rail_meshes=rail_meshes)


def suppressor(st):
    """Глушитель: то же покрытие чуть матовее; рифлёная часть — накатка картой высот: в канавках грязь и пыль
    (пятнами), вершины ромбов затёрты до металла; масло и отпечатки там, где за него берутся."""
    n = coated(st, ((0.08, 0.08, 0.085), 0.36, 0.7), STEEL_BARE, wear=0.3, patches=0.4, scratches=0.18, prints=1.3)
    k = L.insert_fill(_above(n))
    k.set_name("16 Накатка")
    k.active_channels = {sp_lib.CH.Height}
    k.set_source(sp_lib.CH.Height, _bitmap(KNURL))
    _uv(k)
    k.set_opacity(0.45, sp_lib.CH.Height)
    only_meshes(k, ["Suppressor_knurl__sp"])

    def knurl_mask(layer, grooves):
        """Маска по накатке: grooves — в канавках (обратная карта высот), иначе — по вершинам."""
        layer.add_mask(L.MaskBackground.White if grooves else L.MaskBackground.Black)
        m = L.insert_fill(L.InsertPosition.inside_node(layer, L.NodeStack.Mask))
        m.set_source(None, _bitmap(KNURL))
        _uv(m)
        if grooves:
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
    sp_lib.lop(u, 0.5)
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


def polymer(st, base=(0.032, 0.032, 0.034), rough=0.36, stipple=0.06, stipple_scale=50.0, pores=0.4):
    """Полиамид (цевьё, магазины), образец владельца: лакированный пластик с шагренью — глянец сдержанный, бугорки
    шагрени ловят блики; в порах шагрени пыль (обратная той же маске), на выступах и кромках затёрто до блеска,
    местами матовее; редкие царапины, грязь и пыль в углах, отпечатки (на глянце — мутные)."""
    top = L.InsertPosition.from_textureset_stack(st)
    n = fill("01 Полимер", top, color=base, rough=rough, metal=0.0)
    spots = "noise_bnw_spots_2/bnw_spots_2"
    s_ = fill("02 Шагрень", _above(n), height=spots, rough=spots)
    triplanar(s_, stipple_scale)
    s_.set_opacity(stipple, sp_lib.CH.Height)
    s_.set_blending_mode(L.BlendingMode.Overlay, sp_lib.CH.SpecularRoughness)
    s_.set_opacity(0.25, sp_lib.CH.SpecularRoughness)
    pr = fill("03 Пыль в порах шагрени", _above(s_), color=(0.13, 0.125, 0.12), rough=0.85)
    pr.add_mask(L.MaskBackground.White)
    m = L.insert_fill(L.InsertPosition.inside_node(pr, L.NodeStack.Mask))
    m.set_source(None, sp_lib.rid(spots, "u:procedural"))
    triplanar(m, stipple_scale)
    m.set_blending_mode(L.BlendingMode.Subtract)
    sp_lib.lop(pr, pores)
    n = _proc_layer("04 Матовее пятнами", _above(pr), "grunge_wipe_smudgy_soft/grunge_wipe_smudgy_soft", 1.6, 0.5,
                    {"Balance": 0.55, "Contrast": 0.3}, rough=rough + 0.2)
    n = _proc_layer("05 Затёрто до блеска", _above(n), "grunge_wipe_directional_heavy/grunge_wipe_directional_heavy", 1.8,
                    0.3, rough=max(0.12, rough - 0.14))
    n = _proc_layer("06 Царапины", _above(n), _gm(12), 2.5, 0.35, {"invert": 1, "balance": 0.42, "contrast": 0.55},
                    color=(0.1, 0.1, 0.105), rough=rough + 0.1)
    n = _edge("07 Затёртые кромки", _above(n), (0.07, 0.07, 0.075), max(0.12, rough - 0.16), 0.3, contrast=0.8, metal=0.0)
    n = _dirt(_above(n), color=(0.03, 0.027, 0.024), level=0.38, opacity=0.85, name="08 Грязь в углах")
    n = _dirt(_above(n), color=(0.3, 0.28, 0.25), rough=0.95, level=0.24, opacity=0.4, name="09 Пыль в углах", contrast=0.9)
    n = _proc_layer("10 Отпечатки жирные", _above(n), "grunge_fingerprints_dirty/grunge_fingerprints_dirty", 3.0, 0.45,
                    {"Balance": 0.45, "Contrast": 0.35}, color=(0.07, 0.068, 0.065), rough=rough + 0.2)
    return n


def anodized(st):
    """Муфта: чёрное анодирование со сдержанным глянцем поверх алюминия, вытертое на кромках и пятнами (coated)."""
    return coated(st, ((0.07, 0.07, 0.075), 0.36, 0.6), ((0.55, 0.55, 0.57), 0.38, 1.0), wear=0.26, patches=0.2,
                  thin=0.18, scratches=0.15)


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


def wood(st):
    """Приклад — клеёная фанера под лаком, состаренная (образцы владельца: «как настоящее, с рельефом»): основа —
    запечённые шпон и полосы слоёв (wood_laminate_bake.py) с рельефом волокна; в порах волокна грязь, лак потемнел
    пятнами, в углублениях — наплывы (толще, темнее, глянцевее), блеск неровный; на кромках и в местах хвата лак
    протёрт до матового дерева (светлее), мелкие царапины лака, грязь в углах, засаленность."""
    top = L.InsertPosition.from_textureset_stack(st)
    n = _uv_bitmap_fill("01 Фанера", top, color=WOOD_BASE, rough=0.32, metal=0.0)
    h = _uv_bitmap_fill("02 Рельеф волокна", _above(n), height=WOOD_HEIGHT, rough=WOOD_HEIGHT)
    h.set_opacity(0.11, sp_lib.CH.Height)
    h.set_blending_mode(L.BlendingMode.Overlay, sp_lib.CH.SpecularRoughness)
    h.set_opacity(0.3, sp_lib.CH.SpecularRoughness)
    pores = fill("03 Грязь в порах волокна", _above(h), color=(0.16, 0.11, 0.07), rough=0.7)
    pores.add_mask(L.MaskBackground.White)
    m = L.insert_fill(L.InsertPosition.inside_node(pores, L.NodeStack.Mask))
    m.set_source(None, _bitmap(WOOD_HEIGHT))
    _uv(m)
    m.set_blending_mode(L.BlendingMode.Subtract)
    sp_lib.lop(pores, 0.35)
    t = fill("04 Лак потемнел", _above(pores), color=(0.92, 0.85, 0.66))
    t.set_blending_mode(L.BlendingMode.Multiply, sp_lib.CH.BaseColor)
    n = _proc_layer("05 Пятна тона лака", _above(t), _gm(13), 1.5, 0.45, {"balance": 0.5, "contrast": 0.3},
                    color=(0.82, 0.72, 0.52))
    n.set_blending_mode(L.BlendingMode.Multiply, sp_lib.CH.BaseColor)
    n = _dirt(_above(n), color=(0.62, 0.46, 0.22), rough=0.14, level=0.45, opacity=0.6, name="06 Наплывы лака",
              contrast=0.6)
    n.set_blending_mode(L.BlendingMode.Multiply, sp_lib.CH.BaseColor)
    n = _proc_layer("07 Неровный блеск лака", _above(n), "grunge_wipe_smudgy_soft/grunge_wipe_smudgy_soft", 1.6, 0.5,
                    {"Balance": 0.55, "Contrast": 0.3}, rough=0.5)
    n = _edge("08 Лак протёрт на кромках", _above(n), (0.84, 0.72, 0.54), 0.68, 0.4, metal=0.0, grunge=0.8)
    n.set_blending_mode(L.BlendingMode.Overlay, sp_lib.CH.BaseColor)
    sp_lib.lop(n, 0.45)
    n = _proc_layer("09 Протёрто в местах хвата", _above(n),
                    "grunge_fingerprints_smeared_wide/grunge_fingerprints_smeared_wide", 1.6, 0.35,
                    color=(0.78, 0.66, 0.5), rough=0.6)
    n.set_blending_mode(L.BlendingMode.Overlay, sp_lib.CH.BaseColor)
    n = _proc_layer("10 Царапины лака", _above(n), _gm(12), 2.5, 0.4, {"invert": 1, "balance": 0.34, "contrast": 0.55},
                    color=(0.86, 0.76, 0.6), rough=0.6)
    n.set_blending_mode(L.BlendingMode.Overlay, sp_lib.CH.BaseColor)
    n = _dirt(_above(n), color=(0.14, 0.08, 0.045), rough=0.8, level=0.35, opacity=0.6, name="11 Грязь в углах")
    n = _proc_layer("12 Засаленность", _above(n), "grunge_fingerprints_dirty/grunge_fingerprints_dirty", 2.5, 0.3,
                    {"Balance": 0.45, "Contrast": 0.35}, color=(0.7, 0.58, 0.46), rough=0.36)
    n.set_blending_mode(L.BlendingMode.Multiply, sp_lib.CH.BaseColor)
    return n
