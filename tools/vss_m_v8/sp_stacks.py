# Стеки слоёв Substance Painter для ВСС-М v8 по материалам (выполняются внутри Painter через мост).
# Цвета — sRGB (sp_lib переводит в рабочее линейное пространство), шероховатость и металличность — как есть.
# Масштабы трёхпроекционных масок подобраны на модели в миллиметрах (крышка коробки ~200 мм):
# 3–4 — потёртости и пятна в несколько миллиметров, 6–10 — пыль, 50 — шагрень полимера, 170 — зерно покрытия.
# Разбор 25.10 (замечания владельца и образцы Fab / Sketchfab «VSS Vintorez», Artem Goyko): металл должен быть почти
# чёрным и с лёгким блеском (шероховатость ~0.4), живость дают пятна матового налёта и масляного блеска, а не
# царапины; царапины — редкие и в основном в блеске; износ — тонко по самым кромкам.
import substance_painter.layerstack as L
import sp_lib
from sp_lib import fill, mask_generator, mask_proc, only_meshes, triplanar

EDGE = "mg_metal_edge_wear/mg_metal_edge_wear"
# grunge_scratches_fine при balance 0.5 даёт серый фон ~0.5 по всей площади — слой ложится на всю поверхность;
# balance 0.36 и contrast 0.55 уводят фон в чёрное, остаются царапины (подбор на глушителе 25.10)
SCR = {"invert": 0, "balance": 0.36, "contrast": 0.55}
DIRT = "mg_dirt/mg_dirt"
PARTS = "E:/Games/RING-godot/_asset_src/vss_m_v8/sp_parts"
WOOD_BASE = PARTS + "/wood_laminate_v2.png"              # wood_laminate_bake.py: шпон и полосы слоёв фанеры
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


def steel(st, rail_meshes=None, base=((0.16, 0.16, 0.17), 0.42, 0.95), dust=0.35, scratches=0.35):
    """Воронёная/фосфатированная сталь (коробка, рама, органы управления, глушитель): почти чёрная с лёгким блеском;
    оттенок пятнами, матовый серый налёт пятнами, масляный блеск, редкие царапины в блеске, тонкий износ кромок,
    грязь и светлая пыль в углах, отпечатки."""
    top = L.InsertPosition.from_textureset_stack(st)
    n = fill("01 Сталь", top, color=base[0], rough=base[1], metal=base[2])
    n = _grain(_above(n), 0.25, 0.0012)
    n.set_name("02 Зерно")
    n = _proc_layer("03 Пятна тона", _above(n), "3D_perlin_noise_fractal/3D_perlin_noise_fractal", 4.0, 0.4,
                    color=(base[0][0] * 0.75, base[0][1] * 0.74, base[0][2] * 0.72), rough=base[1] + 0.08)
    n = _proc_layer("04 Матовый налёт", _above(n), "grunge_dust_wide/grunge_dust_wide", 3.0, dust,
                    color=(0.16, 0.155, 0.15), rough=0.66, metal=0.4)
    n = _proc_layer("05 Масляный блеск", _above(n), "grunge_fingerprints_smeared_wide/grunge_fingerprints_smeared_wide",
                    3.0, 0.35, rough=0.25)
    n = _proc_layer("06 Микроцарапины", _above(n), "grunge_scratches_fine/grunge_scratches_fine", 8.0, scratches,
                    dict(SCR, scratches_amount=0.5), color=(0.22, 0.22, 0.23), rough=0.25, metal=1.0)
    n = _proc_layer("07 Потёртости", _above(n), "grunge_scratches_rough/grunge_scratches_rough", 4.0, 0.2,
                    color=(0.28, 0.28, 0.29), rough=0.3, metal=1.0)
    n = _edge("08 Износ кромок", _above(n), (0.38, 0.38, 0.39), 0.3, 0.2, contrast=0.6, grunge=0.75)
    if rail_meshes:
        n = _edge("09 Износ планки", _above(n), (0.56, 0.56, 0.57), 0.26, 0.42, contrast=0.8, grunge=0.4, meshes=rail_meshes)
    n = _dirt(_above(n), color=(0.04, 0.035, 0.03), level=0.35, opacity=0.85, name="10 Грязь в углах")
    n = _dirt(_above(n), color=(0.32, 0.30, 0.27), rough=0.95, level=0.22, opacity=0.35, name="11 Пыль в углах",
              contrast=0.9)
    n = _proc_layer("12 Отпечатки", _above(n), "grunge_fingerprints_smeared/grunge_fingerprints_smeared", 6.0, 0.25,
                    rough=0.22)
    return n


def phosphate(st, rail_meshes=None, dust=0.35, base=((0.16, 0.16, 0.17), 0.42, 0.95)):
    """Совместимость: прежнее имя стека стали."""
    return steel(st, rail_meshes=rail_meshes, base=base, dust=dust)


def suppressor(st):
    """Глушитель: та же сталь чуть матовее; рифлёная часть — накатка картой высот, вершины ромбов затёрты светлее."""
    n = steel(st, base=((0.15, 0.15, 0.16), 0.5, 0.9), dust=0.25, scratches=0.2)
    k = L.insert_fill(_above(n))
    k.set_name("13 Накатка")
    k.active_channels = {sp_lib.CH.Height}
    k.set_source(sp_lib.CH.Height, _bitmap(KNURL))
    _uv(k)
    k.set_opacity(0.45, sp_lib.CH.Height)
    only_meshes(k, ["Suppressor_knurl__sp"])
    w = fill("14 Затёртые вершины накатки", _above(k), color=(0.4, 0.4, 0.41), rough=0.32, metal=1.0)
    sp_lib.mask_black(w)
    m = L.insert_fill(L.InsertPosition.inside_node(w, L.NodeStack.Mask))
    m.set_source(None, _bitmap(KNURL))
    _uv(m)
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


def polymer(st, base=(0.03, 0.03, 0.032), rough=0.72, stipple=0.03, stipple_scale=50.0):
    """Полиамид (цевьё, магазины): тёмная основа с шагренью (пупырчатая фактура литья), пятна шероховатости,
    потёртости и затёртые до блеска кромки, грязь, пыль, отпечатки."""
    top = L.InsertPosition.from_textureset_stack(st)
    n = fill("01 Полимер", top, color=base, rough=rough, metal=0.0)
    s = fill("02 Шагрень", _above(n), height="noise_bnw_spots_2/bnw_spots_2", rough="noise_bnw_spots_2/bnw_spots_2")
    triplanar(s, stipple_scale)
    s.set_opacity(stipple, sp_lib.CH.Height)
    s.set_blending_mode(L.BlendingMode.Overlay, sp_lib.CH.SpecularRoughness)
    s.set_opacity(0.2, sp_lib.CH.SpecularRoughness)
    n = _grain(_above(s), 0.2, 0.0015)
    n = _proc_layer("04 Пятна шероховатости", _above(n), "grunge_rough_dirty/grunge_rough_dirty", 3.0, 0.25,
                    rough=rough - 0.12)
    n = _proc_layer("05 Потёртости", _above(n), "grunge_scratches_rough/grunge_scratches_rough", 4.0, 0.3,
                    color=(0.09, 0.09, 0.095), rough=rough - 0.2)
    n = _proc_layer("06 Царапины", _above(n), "grunge_scratches_fine/grunge_scratches_fine", 8.0, 0.3,
                    dict(SCR, scratches_amount=0.4), color=(0.11, 0.11, 0.115), rough=rough - 0.22)
    n = _edge("07 Затёртые кромки", _above(n), (0.09, 0.09, 0.095), rough - 0.25, 0.32, contrast=0.8, metal=0.0)
    n = _dirt(_above(n), level=0.35)
    n = _dirt(_above(n), color=(0.32, 0.30, 0.27), rough=0.95, level=0.22, opacity=0.35, name="09 Пыль в углах",
              contrast=0.9)
    n = _proc_layer("10 Отпечатки", _above(n), "grunge_fingerprints_smeared/grunge_fingerprints_smeared", 6.0, 0.25,
                    rough=rough - 0.3)
    return n


def anodized(st):
    """Чёрное анодирование муфты: полуматовый тёмный металл, налёт пятнами, царапины редкие и в блеске, кромки
    тонко до светлого алюминия."""
    top = L.InsertPosition.from_textureset_stack(st)
    n = fill("01 Анодирование", top, color=(0.14, 0.14, 0.15), rough=0.45, metal=0.7)
    n = _grain(_above(n), 0.3, 0.0012)
    n = _proc_layer("03 Пятна тона", _above(n), "3D_perlin_noise_fractal/3D_perlin_noise_fractal", 4.0, 0.3,
                    color=(0.11, 0.11, 0.115), rough=0.52)
    n = _proc_layer("04 Матовый налёт", _above(n), "grunge_dust_wide/grunge_dust_wide", 3.0, 0.3,
                    color=(0.13, 0.125, 0.12), rough=0.62, metal=0.45)
    n = _proc_layer("05 Микроцарапины", _above(n), "grunge_scratches_fine/grunge_scratches_fine", 8.0, 0.25,
                    dict(SCR, scratches_amount=0.4), color=(0.25, 0.25, 0.26), rough=0.28, metal=1.0)
    n = _edge("06 Кромки до алюминия", _above(n), (0.55, 0.55, 0.57), 0.28, 0.22, contrast=0.8, grunge=0.75)
    n = _dirt(_above(n), color=(0.04, 0.035, 0.03), level=0.35, opacity=0.85)
    n = _dirt(_above(n), color=(0.32, 0.30, 0.27), rough=0.95, level=0.22, opacity=0.35, name="08 Пыль в углах",
              contrast=0.9)
    n = _proc_layer("09 Отпечатки", _above(n), "grunge_fingerprints_smeared/grunge_fingerprints_smeared", 6.0, 0.22, rough=0.22)
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


def wood(st):
    """Приклад — клеёная берёзовая фанера под лаком, состаренная (замечание владельца 25.10: «слишком свежее»):
    основа — запечённые шпон и полосы слоёв (wood_laminate_bake.py); лак потемнел в янтарь пятнами, в углублениях
    наплывы — толще, темнее и глянцевее; блеск лака неровный; на кромках и в местах хвата лак протёрт (светлее
    и матовее, волокна видны); мелкие царапины лака; грязь в углах; засаленность."""
    top = L.InsertPosition.from_textureset_stack(st)
    n = L.insert_fill(top)
    n.set_name("01 Фанера")
    n.active_channels = {sp_lib.CH.BaseColor, sp_lib.CH.SpecularRoughness, sp_lib.CH.BaseMetalness}
    n.set_source(sp_lib.CH.BaseColor, _bitmap(WOOD_BASE))
    n.set_source(sp_lib.CH.SpecularRoughness, sp_lib._val(0.3, data=True))
    n.set_source(sp_lib.CH.BaseMetalness, sp_lib._val(0.0, data=True))
    _uv(n)
    t = fill("02 Лак потемнел", _above(n), color=(0.82, 0.72, 0.6))
    t.set_blending_mode(L.BlendingMode.Multiply, sp_lib.CH.BaseColor)
    n = _proc_layer("03 Пятна тона лака", _above(t), "grunge_rough_dirty/grunge_rough_dirty", 2.0, 0.5,
                    color=(0.7, 0.58, 0.46))
    n.set_blending_mode(L.BlendingMode.Multiply, sp_lib.CH.BaseColor)
    n = _dirt(_above(n), color=(0.62, 0.42, 0.24), rough=0.16, level=0.45, opacity=0.65, name="04 Наплывы лака",
              contrast=0.6)
    n.set_blending_mode(L.BlendingMode.Multiply, sp_lib.CH.BaseColor)
    n = _proc_layer("05 Неровный блеск лака", _above(n), "grunge_rough_dirty/grunge_rough_dirty", 3.5, 0.45, rough=0.48)
    n = _edge("06 Протёртый лак на кромках", _above(n), (0.7, 0.58, 0.44), 0.62, 0.38, metal=0.0, grunge=0.75)
    n.set_blending_mode(L.BlendingMode.Overlay, sp_lib.CH.BaseColor)
    sp_lib.lop(n, 0.6)
    n = _proc_layer("07 Протёрто в местах хвата", _above(n),
                    "grunge_fingerprints_smeared_wide/grunge_fingerprints_smeared_wide", 1.6, 0.35,
                    color=(0.74, 0.62, 0.48), rough=0.62)
    n.set_blending_mode(L.BlendingMode.Overlay, sp_lib.CH.BaseColor)
    n = _proc_layer("08 Царапины лака", _above(n), "grunge_scratches_fine/grunge_scratches_fine", 6.0, 0.45,
                    dict(SCR, scratches_amount=0.45), color=(0.78, 0.64, 0.48), rough=0.6)
    n.set_blending_mode(L.BlendingMode.Overlay, sp_lib.CH.BaseColor)
    n = _dirt(_above(n), color=(0.14, 0.08, 0.045), rough=0.8, level=0.35, opacity=0.6, name="09 Грязь в углах")
    n = _proc_layer("10 Засаленность", _above(n), "grunge_fingerprints_smeared_wide/grunge_fingerprints_smeared_wide", 2.5,
                    0.3, color=(0.66, 0.54, 0.44), rough=0.36)
    n.set_blending_mode(L.BlendingMode.Multiply, sp_lib.CH.BaseColor)
    return n
