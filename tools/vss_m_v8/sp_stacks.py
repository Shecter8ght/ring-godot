# Стеки слоёв Substance Painter для ВСС-М v8 по материалам (выполняются внутри Painter через мост).
# Цвета — sRGB (sp_lib переводит в рабочее линейное пространство), шероховатость и металличность — как есть.
# Масштабы трёхпроекционных масок подобраны на модели в миллиметрах (крышка коробки ~200 мм):
# 2.5–4 — царапины и потёртости в несколько миллиметров, 6–10 — пятна пыли, 170 — зерно покрытия.
import substance_painter.layerstack as L
import sp_lib
from sp_lib import fill, mask_generator, mask_proc, only_meshes, triplanar

EDGE = "mg_metal_edge_wear/mg_metal_edge_wear"
# grunge_scratches_fine при balance 0.5 даёт серый фон ~0.5 по всей площади — слой ложится на всю поверхность;
# balance 0.36 и contrast 0.55 уводят фон в чёрное, остаются царапины (подбор на глушителе 25.10)
SCR = {"invert": 0, "balance": 0.36, "contrast": 0.55}
DIRT = "mg_dirt/mg_dirt"


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


def _dirt(pos, color=(0.045, 0.04, 0.035), rough=0.85, level=0.3, opacity=0.7, metal=0.0, name="Грязь в углах"):
    d = fill(name, pos, color=color, rough=rough, metal=metal)
    mask_generator(d, DIRT, {"dirt_level": level, "dirt_contrast": 0.8, "grunge_amount": 0.4, "Grunge_Scale": 6,
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


def phosphate(st, rail_meshes=None, dust=0.08, base=((0.08, 0.08, 0.085), 0.62, 0.45)):
    """Фосфатированная сталь (коробка, рама, органы управления, глушитель): тёмная матовая основа с мелким зерном
    и пятнами, протирки, царапины и потёртости до металла, износ кромок, грязь в углах, пыль, отпечатки (блеск)."""
    top = L.InsertPosition.from_textureset_stack(st)
    n = fill("01 Фосфат основа", top, color=base[0], rough=base[1], metal=base[2])
    n = _grain(_above(n))
    n.set_name("02 Зерно фосфата")
    n = _proc_layer("03 Неровность покрытия", _above(n), "3D_perlin_noise_fractal/3D_perlin_noise_fractal", 4.0, 0.25,
                    color=(0.125, 0.123, 0.12), rough=0.7)
    n = _proc_layer("03б Пятна шероховатости", _above(n), "grunge_rough_dirty/grunge_rough_dirty", 3.0, 0.3, rough=0.48)
    n = _proc_layer("04 Протирки", _above(n), "grunge_wipe_directional/grunge_wipe_directional", 4.0, 0.3, rough=0.5)
    n = _proc_layer("05 Мелкие царапины", _above(n), "grunge_scratches_fine/grunge_scratches_fine", 5.0, 0.55,
                    dict(SCR, scratches_amount=0.6), color=(0.34, 0.34, 0.35), rough=0.3, metal=1.0)
    n = _proc_layer("05б Потёртости", _above(n), "grunge_scratches_rough/grunge_scratches_rough", 3.0, 0.5,
                    color=(0.24, 0.24, 0.245), rough=0.38, metal=0.92)
    n = _edge("06 Износ кромок", _above(n), (0.52, 0.52, 0.53), 0.28, 0.4)
    if rail_meshes:
        n = _edge("07 Износ планки", _above(n), (0.5, 0.5, 0.51), 0.28, 0.5, contrast=0.65, grunge=0.4, meshes=rail_meshes)
    n = _dirt(_above(n), name="08 Грязь в углах")
    n = _proc_layer("09 Пыль", _above(n), "grunge_dust_small/grunge_dust_small", 8.0, dust,
                    color=(0.30, 0.285, 0.26), rough=0.95, metal=0.0)
    n = _proc_layer("10 Отпечатки", _above(n), "grunge_fingerprints_smeared/grunge_fingerprints_smeared", 6.0, 0.22, rough=0.26)
    return n


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
    n = _proc_layer("05 Царапины", _above(n), "grunge_scratches_fine/grunge_scratches_fine", 5.0, 0.7,
                    dict(SCR, scratches_amount=0.6), color=(0.72, 0.72, 0.74), rough=0.2)
    n = _edge("06 Заполированные кромки", _above(n), (0.78, 0.78, 0.8), 0.17, 0.42)
    n = _dirt(_above(n), color=(0.07, 0.065, 0.06), rough=0.7, level=0.38, opacity=0.85, metal=0.2, name="07 Нагар")
    return n


def polymer(st, base=(0.045, 0.045, 0.047)):
    """Полиамид (цевьё, магазины): матовая основа с зерном, потёртости и царапины светлее и глаже,
    затёртые до блеска кромки, грязь, пыль, отпечатки."""
    top = L.InsertPosition.from_textureset_stack(st)
    n = fill("01 Полимер", top, color=base, rough=0.62, metal=0.0)
    n = _grain(_above(n), 0.3, 0.002)
    n = _proc_layer("03 Пятна шероховатости", _above(n), "grunge_rough_dirty/grunge_rough_dirty", 3.0, 0.25, rough=0.5)
    n = _proc_layer("04 Потёртости", _above(n), "grunge_scratches_rough/grunge_scratches_rough", 3.0, 0.45,
                    color=(0.11, 0.11, 0.115), rough=0.45)
    n = _proc_layer("05 Царапины", _above(n), "grunge_scratches_fine/grunge_scratches_fine", 5.0, 0.6,
                    dict(SCR, scratches_amount=0.5), color=(0.14, 0.14, 0.145), rough=0.4)
    n = _edge("06 Затёртые кромки", _above(n), (0.12, 0.12, 0.125), 0.36, 0.36, metal=0.0)
    n = _dirt(_above(n), level=0.35)
    n = _proc_layer("08 Пыль", _above(n), "grunge_dust_small/grunge_dust_small", 8.0, 0.12,
                    color=(0.32, 0.30, 0.27), rough=0.95)
    n = _proc_layer("09 Отпечатки", _above(n), "grunge_fingerprints_smeared/grunge_fingerprints_smeared", 6.0, 0.25, rough=0.32)
    return n


def anodized(st):
    """Чёрное анодирование муфты: полуматовый металл, потёртости, кромки до светлого алюминия."""
    top = L.InsertPosition.from_textureset_stack(st)
    n = fill("01 Анодирование", top, color=(0.045, 0.045, 0.05), rough=0.5, metal=0.55)
    n = _grain(_above(n), 0.3, 0.0015)
    n = _proc_layer("03 Пятна шероховатости", _above(n), "grunge_rough_dirty/grunge_rough_dirty", 3.0, 0.3, rough=0.32)
    n = _proc_layer("04 Потёртости", _above(n), "grunge_scratches_rough/grunge_scratches_rough", 3.0, 0.3,
                    color=(0.16, 0.16, 0.17), rough=0.38, metal=0.9)
    n = _proc_layer("05 Царапины", _above(n), "grunge_scratches_fine/grunge_scratches_fine", 5.0, 0.5,
                    dict(SCR, scratches_amount=0.5), color=(0.42, 0.42, 0.44), rough=0.28, metal=1.0)
    n = _edge("06 Кромки до алюминия", _above(n), (0.7, 0.7, 0.72), 0.26, 0.3, contrast=0.75)
    n = _dirt(_above(n))
    n = _proc_layer("08 Пыль", _above(n), "grunge_dust_small/grunge_dust_small", 8.0, 0.1,
                    color=(0.30, 0.285, 0.26), rough=0.95, metal=0.0)
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
    n = _proc_layer("05 Царапины", _above(n), "grunge_scratches_fine/grunge_scratches_fine", 2.0, 0.55,
                    dict(SCR, scratches_amount=0.5), color=(0.62, 0.6, 0.56), rough=0.25, metal=1.0)
    n = _edge("06 Кромки", _above(n), (0.66, 0.64, 0.6), 0.22, 0.42)
    n = _proc_layer("07 Окисление пули", _above(n), "grunge_rough_dirty/grunge_rough_dirty", 2.5, 0.35,
                    color=(0.5, 0.33, 0.22), rough=0.5)
    only_meshes(n, ["Round_bullet__sp"])
    return n


PLYWOOD = "E:/Games/RING-godot/assets/textures/plywood/albedo.jpg"   # Poly Haven «Plywood», CC0


def _bitmap(path):
    import substance_painter.resource as R
    for r in R.search("u:texture"):
        if r.identifier().name == path.rsplit("/", 1)[-1].rsplit(".", 1)[0]:
            return r.identifier()
    return R.import_project_resource(path, R.Usage.TEXTURE).identifier()


def _wood_projection(layer, sx, sy):
    layer.set_projection_mode(L.ProjectionMode.Triplanar)
    p = layer.get_projection_parameters()
    p.hardness = 0.35
    p.uv_transformation.scale_mode = L.ScaleMode.Factors
    p.uv_transformation.scale = [sx, sy]
    layer.set_projection_parameters(p)


def wood(st, sx=2.2, sy=4.6):
    """Приклад: берёзовая фанера под лаком (фото Poly Haven «Plywood», CC0) трёхпроекционно, волокна вдоль приклада;
    тон умножением в оранжево-бурый ВСС, лак полуглянцевый; протёртый на кромках лак светлее и матовее (наложением,
    волокна видны), грязь в углублениях, засаленность в местах хвата."""
    top = L.InsertPosition.from_textureset_stack(st)
    n = L.insert_fill(top)
    n.set_name("01 Фанера")
    n.active_channels = {sp_lib.CH.BaseColor, sp_lib.CH.SpecularRoughness, sp_lib.CH.BaseMetalness}
    n.set_source(sp_lib.CH.BaseColor, _bitmap(PLYWOOD))
    n.set_source(sp_lib.CH.SpecularRoughness, sp_lib._val(0.42, data=True))
    n.set_source(sp_lib.CH.BaseMetalness, sp_lib._val(0.0, data=True))
    _wood_projection(n, sx, sy)
    t = fill("02 Тон лака", _above(n), color=(0.73, 0.47, 0.32))
    t.set_blending_mode(L.BlendingMode.Multiply, sp_lib.CH.BaseColor)
    n = _proc_layer("03 Старение лака", _above(t), "grunge_rough_dirty/grunge_rough_dirty", 2.5, 0.35,
                    color=(0.72, 0.62, 0.55), rough=0.36)
    n.set_blending_mode(L.BlendingMode.Multiply, sp_lib.CH.BaseColor)
    n = _proc_layer("04 Царапины лака", _above(n), "grunge_scratches_fine/grunge_scratches_fine", 5.0, 0.5,
                    dict(SCR, scratches_amount=0.5), color=(0.75, 0.6, 0.45), rough=0.6)
    n.set_blending_mode(L.BlendingMode.Overlay, sp_lib.CH.BaseColor)
    n = _edge("05 Протёртый лак на кромках", _above(n), (0.82, 0.68, 0.5), 0.68, 0.42, metal=0.0, grunge=0.7)
    n.set_blending_mode(L.BlendingMode.Overlay, sp_lib.CH.BaseColor)
    n = _dirt(_above(n), color=(0.18, 0.11, 0.06), rough=0.8, level=0.35, opacity=0.55, name="06 Грязь в углах")
    n = _proc_layer("07 Засаленность", _above(n), "grunge_fingerprints_smeared_wide/grunge_fingerprints_smeared_wide", 3.0,
                    0.3, color=(0.62, 0.5, 0.42), rough=0.3)
    n.set_blending_mode(L.BlendingMode.Multiply, sp_lib.CH.BaseColor)
    return n
