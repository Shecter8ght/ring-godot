# Стеки слоёв Substance Painter для ВСС-М v8 по материалам (выполняются внутри Painter через мост).
# Цвета — sRGB (sp_lib переводит в рабочее линейное пространство), шероховатость и металличность — как есть.
# Масштабы трёхпроекционных масок подобраны на модели в миллиметрах (крышка коробки ~200 мм):
# 3–4 — потёртости и пятна в несколько миллиметров, 6–10 — пыль, 50 — шагрень полимера, 170 — зерно покрытия.
# Разбор 25.10 (замечания владельца и образцы Fab / Sketchfab «VSS Vintorez», Artem Goyko): металл — заводское
# покрытие со сдержанным глянцем (шероховатость ~0.3), местами вытертое до матового металла; живость даёт контраст
# глянца и вытертых мест, а не шумовые пятна (объёмный шум и широкая пыль читались «мылом»). Маски износа — фото-маски
# Painter grunge map 008/012/013, протирки wipe smudgy/directional, отпечатки fingerprints dirty/dusty (подбор
# превью масок на глушителе 25.10). Полимер цевья — лакированный, шагрень бликует.
import os
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
SLEEVE_RAIL = PARTS + "/sleeve_rail.png"          # sleeve_masks_bake.py: планки муфты (1) и корпус (0)
SLEEVE_STREAKS = PARTS + "/sleeve_streaks.png"    # там же: шум, вытянутый вдоль оси, — продольные сколы на планках
REAR_SIGHT = ["Rear_sight_base", "Rear_sight_leaf", "Rear_sight_slider", "Rear_sight_weld"]   # Cerakote, как муфта
REAR_SIGHT_IDS = PARTS + "/rear_sight_ids.png"   # sleeve_masks_bake.py: острова прицела с полями в развёртке мелкой стали


def _grain(pos, rough_op=0.35, height_op=0.0025):
    g = fill("Зерно", pos, rough="noise_gaussian_noise/gaussian_noise", height="noise_gaussian_noise/gaussian_noise")
    triplanar(g, 170.0)
    g.set_blending_mode(L.BlendingMode.Overlay, sp_lib.CH.SpecularRoughness)
    g.set_opacity(rough_op, sp_lib.CH.SpecularRoughness)
    g.set_opacity(height_op, sp_lib.CH.Height)
    return g


def _edge(name, pos, color, rough, level, contrast=0.65, grunge=0.6, metal=1.0, meshes=None, step=0.0):
    """Износ по кромкам. step — покрытие стёрто: место ниже на толщину слоя, у границы ступенька в рельефе (без неё
    потёртости читались нарисованными, владелец 26.10 — «как у замка: слои при перепадах краски»)."""
    e = fill(name, pos, color=color, rough=rough, metal=metal, **({"height": step} if step else {}))
    if step:
        e.set_blending_mode(L.BlendingMode.Subtract, sp_lib.CH.Height)
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
    """Карта из файла ресурсом проекта. Имя — с отметкой времени файла: по одному имени файла перепечённая карта
    бралась из проекта прежней (основа приклада 26.10 оставалась светлой после перепекания)."""
    import substance_painter.resource as R
    stem = path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    name = f"{stem}_{int(os.path.getmtime(path))}"
    for r in R.search("u:texture"):
        if r.identifier().name == name:
            return r.identifier()
    return R.import_project_resource(path, R.Usage.TEXTURE, name=name).identifier()


def _uv(layer):
    layer.set_projection_mode(L.ProjectionMode.UV)


def _gm(i):
    return "noise_grunge_map_%03d/grunge_map_%03d" % (i, i)


def _mix(a, b, t):
    return tuple(x + (y - x) * t for x, y in zip(a, b))


def _mesh_names(st, names):
    """Имена сеток набора в Painter по именам деталей или их началам (FBX: «<деталь>__sp»)."""
    try:
        have = list(st.material().all_mesh_names())
    except Exception:
        return [n + "__sp" for n in names]
    out = []
    for n in names:
        out += [m for m in have if m == n + "__sp" or (n.endswith("_") and m.startswith(n))]
    return out


def _sharpen(grp, amount=0.3):
    """Слабая резкость в конце (справка навыка): эффектом группы — поверх слоёв фильтр API Painter не вставляет."""
    sh = L.insert_filter_effect(L.InsertPosition.inside_node(grp, L.NodeStack.Content),
                                sp_lib.rid("sharpen/sharpen", "u:filter"))
    sh.get_source().set_parameters({"intensity": amount})
    # только цвет и блеск: по высоте резкость «звенела» на краях островов развёртки (поля рядом другие) — рваная
    # кайма рельефа вдоль каждого ребра, не зависящая от износа (найдено на заднем прицеле 26.10)
    try:
        sh.active_channels = {sp_lib.CH.BaseColor, sp_lib.CH.SpecularRoughness}
        print("sharpen channels", grp.get_name(), sorted(str(c) for c in sh.active_channels))
    except Exception as e:
        print("sharpen channels FAILED", grp.get_name(), e)
    return sh


def coated(st, coat, bare, wear=0.1, patch_bal=0.8, thin=0.45, scratches=0.35, prints=1.0, rail_meshes=None,
           parts=None, zones=None, wiped=0.35):
    """Изделие с заводским покрытием (воронение / анодирование): coat и bare — (цвет, шероховатость, металл)
    покрытия и металла под ним. Износ читается блеском и рельефом (замечание владельца 25.10: у пятен был тот же
    блеск, что у покрытия): покрытие глянцевое с лёгкими пятнами блеска и протирками; вокруг вытертых мест — рваная
    полоса истончившегося, полуматового покрытия; вытертое до металла — полностью матовое (площадь задаёт порог маски
    patch_bal — яркость обратной фото-маски: у grunge map обращение идёт после яркости, поэтому чем БОЛЬШЕ patch_bal,
    тем МЕНЬШЕ вытертых пятен (замер на steel_parts: 0.6 → 31 %, 0.78 → 12 %, 0.85 → 8 %); wear — уровень генератора
    износа кромок (0.08 → 17 % площади развёртки мелких деталей, 0.2 → 30 %), а не прозрачность — частичная прозрачность смешивала шероховатость и съедала разницу) и ниже покрытия на
    его толщину (ступенька по краю ловит свет; высоты в долях тысячной — единица высоты Painter огромна, ступенька
    0.007 по шумной маске дала «кору»); острые кромки заполированы до блеска; царапины — бороздки; грязь и пыль
    в углах, масло, отпечатки.
    По справке навыка (painter-workflow.md, 26.10): у деталей свои основы — parts = [(имя, [детали или начала
    имён], цвет, шероховатость, металл)], маской по сеткам: одна заливка на всё читается пластмассой; крупные пятна
    тона идут парой с пятнами блеска (каналы связаны); слои покрытия и износа — в группе со слабой резкостью на выходе,
    грязь, пыль, масло и отпечатки — после неё.
    zones — имя набора с картами мест износа (contact_marks.py: <набор>_wear — до металла, <набор>_rub — истончилось):
    тогда пятна износа только там и у кромок, фото-маски пятен по всей площади не кладутся (владелец 27.10: «с продольных
    боков убрать сильный износ пятнами до металла»). wiped — сила протирок до блеска."""
    wear_map = rub_map = None
    if zones:
        wear_map, rub_map = (f"{MARKS_DIR}/{zones}_{k}.png" for k in ("wear", "rub"))
        if not (os.path.exists(wear_map) and os.path.exists(rub_map)):
            print("NO WEAR ZONES", zones)
            wear_map = rub_map = None
    grp = L.insert_group(L.InsertPosition.from_textureset_stack(st))
    grp.set_name("Покрытие и износ")
    n = fill("01 Покрытие", L.InsertPosition.inside_node(grp, L.NodeStack.Substack), color=coat[0], rough=coat[1],
             metal=coat[2], height=0.5)
    for label, names, col, rough, metal in parts or ():
        meshes = _mesh_names(st, names)
        if not meshes:
            continue
        n = fill("01 Основа: " + label, _above(n), color=col, rough=rough, metal=metal)
        only_meshes(n, meshes)
    n = _grain(_above(n), 0.12, 0.0006)
    n.set_name("02 Зерно")
    n = _proc_layer("02б Пятна тона и блеска", _above(n), "noise_clouds_1/clouds_1", 0.7, 0.35,
                    color=_mix(coat[0], (0.22, 0.22, 0.22), 0.3), rough=coat[1] + 0.1)
    n = _proc_layer("03 Блеск пятнами", _above(n), _gm(13), 1.2, 0.5, {"balance": 0.5, "contrast": 0.2},
                    rough=coat[1] + 0.07)
    n = _proc_layer("04 Протёрто до блеска", _above(n), "grunge_wipe_directional_heavy/grunge_wipe_directional_heavy", 1.8,
                    wiped, rough=max(0.12, coat[1] - 0.08))
    edge_p = {"Wear_Contrast": 0.6, "Grunge_Amount": 0.75, "grunge_scale": 6, "Use_Triplanar": 1, "Edges_Smoothness": 0.45,
              "Ambient_Occlusion_Masking": 0.6, "Curvature_Weight": 1.0}
    t = fill("05 Покрытие истончилось", _above(n), color=_mix(coat[0], bare[0], 0.4), rough=(coat[1] + bare[1]) / 2,
             metal=(coat[2] + bare[2]) / 2, height=0.497)
    t_edge = dict(edge_p, Wear_Level=min(0.95, wear * 1.8), Wear_Contrast=0.35, Grunge_Amount=0.85)
    if rub_map:
        # места трения (истончилось) и вытертое до металла (вокруг него тоже истончилось) + кромки
        m = _bmask(t, rub_map)
        m = _bmask(t, wear_map, blend=L.BlendingMode.Lighten, above=m)
        g = mask_generator(t, EDGE, t_edge, above=m)
        g.set_blending_mode(L.BlendingMode.Lighten)
        pm = g
    else:
        g = mask_generator(t, EDGE, t_edge)
        pm = mask_proc(t, _gm(8), {"invert": 1, "balance": patch_bal - 0.08, "contrast": 0.35}, scale=1.5, above=g,
                       blend=L.BlendingMode.Lighten)
    mask_proc(t, _gm(13), {"balance": 0.6, "contrast": 0.3}, scale=2.2, above=pm, blend=L.BlendingMode.Multiply)
    sp_lib.lop(t, thin)
    w = fill("06 Вытерто до металла", _above(t), color=bare[0], rough=bare[1], metal=bare[2], height=0.475)  # ступенька 0.025
    if wear_map:
        # до металла — только кромки, о которые трутся детали; порог делает край рваным и резким
        m = _bmask(w, wear_map)
        m = _mfilter(m, "histogram_scan", {"Position": 0.45, "Contrast": 0.6})
        g = mask_generator(w, EDGE, dict(edge_p, Wear_Level=wear), above=m)
        g.set_blending_mode(L.BlendingMode.Lighten)
    else:
        g = mask_generator(w, EDGE, dict(edge_p, Wear_Level=wear))
        mask_proc(w, _gm(8), {"invert": 1, "balance": patch_bal, "contrast": 0.75}, scale=1.5, above=g,
                  blend=L.BlendingMode.Lighten)
    n = _grain(_above(w), 0.16, 0.0)
    n.set_name("07 Неровная матовость")
    n = _edge("08 Кромки до блеска", _above(n), _mix(bare[0], (0.75, 0.75, 0.76), 0.5), 0.24, wear * 0.6,
              contrast=0.85, grunge=0.6, step=0.025)
    if rail_meshes:
        # заметно, но не обширно (замечание владельца 26.10: уровень 0.5 давал «потрёпанную» планку)
        n = _edge("09 Износ планки", _above(n), _mix(bare[0], (0.75, 0.75, 0.76), 0.4), 0.26, 0.18, contrast=0.88,
                  grunge=0.6, meshes=rail_meshes, step=0.02)
    n = _proc_layer("10 Царапины", _above(n), _gm(12), 2.5, scratches, {"invert": 1, "balance": 0.74, "contrast": 0.55},
                    color=_mix(coat[0], bare[0], 0.8), rough=0.28, metal=1.0, height=0.49)
    _sharpen(grp, 0.3)
    n = _dirt(_above(grp), color=(0.035, 0.03, 0.026), level=0.38, opacity=0.9, name="11 Грязь в углах")
    n = _dirt(_above(n), color=(0.3, 0.28, 0.25), rough=0.95, level=0.24, opacity=0.4, name="12 Пыль в углах", contrast=0.9)
    n = _proc_layer("13 Масло", _above(n), _gm(15), 1.8, 0.3, {"invert": 1, "balance": 0.72, "contrast": 0.4},
                    color=_mix(coat[0], (0.0, 0.0, 0.0), 0.3), rough=0.18)
    n = _proc_layer("14 Отпечатки жирные", _above(n), "grunge_fingerprints_dirty/grunge_fingerprints_dirty", 3.0,
                    0.4 * prints, {"Balance": 0.45, "Contrast": 0.35}, color=_mix(coat[0], (0.2, 0.19, 0.18), 0.4), rough=0.45)
    n = _proc_layer("15 Отпечатки пыльные", _above(n), "grunge_fingerprints_dusty/grunge_fingerprints_dusty", 3.0,
                    0.25 * prints, {"Balance": 0.45, "Contrast": 0.35}, color=(0.24, 0.23, 0.21), rough=0.7, metal=0.0)
    return n


# воронёная сталь: тёмно-серое покрытие с сатиновым блеском, под ним матовая серая сталь с тёплым оттенком.
# 27.10 (владелец выбрал пробу A после сравнения с Fab): цвет 0.085 при металле 0.75 отражал меньше чёрного пластика
# (F0 ~1,6 %) — «чёрная дыра» без формы; по правилу PBR тёмная сталь 0.15–0.22 sRGB при металле ~0.9. Блеск
# сатиновый (было 0.22 — лаковый, «глянец потише», 27.10).
STEEL_COAT = ((0.22, 0.22, 0.23), 0.32, 0.9)
SUPPRESSOR_COAT = ((0.2, 0.2, 0.21), 0.28, 0.85)    # глушитель чуть матовее и темнее коробки (было 0.08 / 0.7)
STEEL_BARE = ((0.42, 0.415, 0.41), 0.3, 1.0)   # стёртое до металла блестит (0.17 / 0.62 читалось матовой краской, 26.10)
# свои основы деталей (справка навыка: 4–5 основ на предмет; тёмные — с лёгким оттенком, крепёж — светлее)
RECEIVER_PARTS = [
    ("крышка", ["Receiver_cover"], (0.245, 0.237, 0.237), 0.3, 0.93),
    ("планка Пикатинни", ["Cover_picatinny"], (0.284, 0.284, 0.309), 0.42, 0.6),
    ("спусковая скоба", ["Trigger_guard"], (0.193, 0.191, 0.193), 0.36, 0.85),
    ("боковой кронштейн", ["Side_mount_dovetail"], (0.193, 0.206, 0.245), 0.34, 0.95),
    ("ствольная накладка", ["Receiver_trunnion"], (0.18, 0.18, 0.186), 0.34, 0.9),
    ("штифты и заклёпки", ["Receiver_pin_", "Side_mount_rivet_", "Safety_axis_end_L"], (0.361, 0.348, 0.335), 0.38, 1.0),
]
STEEL_PARTS_PARTS = [
    ("рама и рукоятка", ["Bolt_carrier", "Bolt_carrier_plate", "Bolt_carrier_web", "Charging_handle"],
     (0.232, 0.227, 0.227), 0.32, 0.95),
    ("спуск", ["Trigger"], (0.309, 0.304, 0.296), 0.34, 1.0),
    ("прицельные", ["Rear_sight_base", "Rear_sight_leaf", "Rear_sight_slider", "Front_sight_base", "Front_sight_post"],
     (0.206, 0.206, 0.219), 0.34, 0.9),
    ("антабки, винты, заклёпки", ["Front_sling_swivel", "Stock_sling_swivel", "Stock_sling_rivet_0", "Stock_sling_rivet_1",
                                  "Stock_screw_L", "Stock_screw_R", "Rail_sleeve_screws"], (0.335, 0.33, 0.322), 0.38, 1.0),
]


def steel(st, rail_meshes=None, wear=0.06, patch_bal=0.9, scratches=0.16, parts=None, zones=None, wiped=0.35):
    """Сталь коробки, рамы, органов управления, прицельных: воронение, местами вытертое (см. coated). Износа меньше
    прежнего (0.1 / 0.8 / 0.35): стёртое до металла стало светлым и блестящим, и каждое повреждение читается
    (владелец 26.10 — «количество повреждений уменьшить»). zones — износ только по местам (коробка, 27.10)."""
    return coated(st, STEEL_COAT, STEEL_BARE, wear=wear, patch_bal=patch_bal, thin=0.3, scratches=scratches,
                  rail_meshes=rail_meshes, parts=parts, zones=zones, wiped=wiped)


def phosphate(st, rail_meshes=None, **kw):
    """Совместимость: прежнее имя стека стали."""
    return steel(st, rail_meshes=rail_meshes)


def suppressor(st):
    """Глушитель: то же покрытие чуть матовее; рифлёная часть — накатка картой высот: в канавках грязь и пыль
    (пятнами), вершины ромбов затёрты до металла; масло и отпечатки там, где за него берутся."""
    # пыльные отпечатки (prints) давали на торце светлые точки — слабее
    n = coated(st, SUPPRESSOR_COAT, STEEL_BARE, wear=0.05, patch_bal=0.93, thin=0.3, scratches=0.1, prints=0.6)
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


# чёрные неметаллы по правилу PBR (27.10, вместе с пробой A стали): чёрный пластик, резина, керамика — около
# 0.15–0.2 sRGB, а не 0.03–0.07 (темнее угля — «провалы» рядом с посветлевшим металлом). Производные цвета
# (царапины, пыль, потёртости) — светлее основы, грязь — темнее.
POLY = {"base": (0.17, 0.17, 0.175), "scratch": (0.26, 0.26, 0.27), "edge": (0.21, 0.21, 0.22),
        "prints": (0.14, 0.137, 0.13), "pore_dust": (0.3, 0.29, 0.27), "dirt": (0.05, 0.045, 0.04),
        "dust": (0.4, 0.38, 0.34)}
MAG = {"base": (0.2, 0.2, 0.21), "lips": (0.26, 0.26, 0.265), "scuff": (0.42, 0.415, 0.41), "scratch": (0.3, 0.3, 0.3),
       "dirt": (0.06, 0.055, 0.05), "dust": (0.48, 0.46, 0.43)}
RUBBER = {"base": (0.14, 0.14, 0.14), "scuff": (0.2, 0.2, 0.2), "edge": (0.17, 0.17, 0.17), "dust": (0.3, 0.29, 0.27)}


def polymer(st, base=POLY["base"], rough=0.3, stipple=0.038, stipple_scale=32.0, pores=0.2,
            spots="noise_cells_1/cells_1", matte=0.2):
    """Полиамид (цевьё, магазины), образец владельца: лакированный пластик с шагренью. Лак глянцевый (0.2), бугорки
    шагрени ещё глаже (0.1) — ловят блики искрами, в порах лак тусклее (0.55) и пыль; поэтому в полосе блика шагрень
    искрит, а вне её цевьё чёрное (при шероховатости ~0.4 отражение софтбокса растекалось по всей грани — «серое»).
    Местами лак матовее, на выступах и кромках затёрт до блеска; редкие царапины, грязь и пыль в углах, отпечатки
    (на глянце — мутные). Шагрень цевья — купола ячеистого шума (noise_cells_1): у пятнистых шумов половина площади
    уходила в «поры» с тусклым лаком и пылью, и цевьё читалось серым (подбор вариантов 25.10)."""
    grp = L.insert_group(L.InsertPosition.from_textureset_stack(st))
    grp.set_name("Полимер")
    n = fill("01 Полимер", L.InsertPosition.inside_node(grp, L.NodeStack.Substack), color=base, rough=rough, metal=0.0)
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
    pr = fill("03б Пыль в порах шагрени", _above(pt), color=POLY["pore_dust"], rough=0.8)
    pores_mask(pr)
    sp_lib.lop(pr, pores)
    n = _proc_layer("04 Матовее пятнами", _above(pr), "grunge_wipe_smudgy_soft/grunge_wipe_smudgy_soft", 1.6, matte,
                    {"Balance": 0.55, "Contrast": 0.3}, rough=rough + 0.18)
    n = _proc_layer("05 Затёрто до блеска", _above(n), "grunge_wipe_directional_heavy/grunge_wipe_directional_heavy", 1.8,
                    0.35, rough=0.08)
    n = _proc_layer("06 Царапины", _above(n), _gm(12), 2.5, 0.35, {"invert": 1, "balance": 0.74, "contrast": 0.55},
                    color=POLY["scratch"], rough=rough + 0.2)
    n = _edge("07 Затёртые кромки", _above(n), POLY["edge"], 0.08, 0.3, contrast=0.8, metal=0.0)
    _sharpen(grp, 0.3)
    n = _dirt(_above(grp), color=POLY["dirt"], level=0.38, opacity=0.85, name="08 Грязь в углах")
    n = _dirt(_above(n), color=POLY["dust"], rough=0.95, level=0.24, opacity=0.4, name="09 Пыль в углах", contrast=0.9)
    n = _proc_layer("10 Отпечатки жирные", _above(n), "grunge_fingerprints_dirty/grunge_fingerprints_dirty", 3.0, 0.45,
                    {"Balance": 0.45, "Contrast": 0.35}, color=POLY["prints"], rough=rough + 0.22)
    return n


MAG_LIPS = PARTS + "/mag_lips.png"      # mag_masks_bake.py: губки и передний упор (затвор трёт до блеска)
MAG_LIPS_30 = PARTS + "/mag_lips_30.png"   # то же для набора magazine_30 (магазин на 30 — свой атлас)


def magazine(st, lips=MAG_LIPS):
    """Магазин — литой полиамид ТОЗ (фото владельца 26.10): тёмно-графитовый, матовый, без лака, литьё слегка
    пятнистое; губки и передний упор затвор затёр до блеска; на кромках белёсые потёртости пластика (не краска — светлее
    и матовее), редкие светлые царапины, засаленные места, грязь в углах и пыль в рёбрах. Порядок по справке навыка:
    основа → рельеф → блеск → повреждения → резкость (эффект группы) → грязь и пыль."""
    CH = sp_lib.CH
    grp = L.insert_group(L.InsertPosition.from_textureset_stack(st))
    grp.set_name("Полиамид")
    ins = L.InsertPosition.inside_node(grp, L.NodeStack.Substack)
    n = fill("01 Полиамид", ins, color=MAG["base"], rough=0.55, metal=0.0)
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
    n = fill("05 Губки и упор затёрты до блеска", _above(n), color=MAG["lips"], rough=0.26)
    g = mask_generator(n, EDGE, {"Wear_Level": 0.45, "Wear_Contrast": 0.6, "Grunge_Amount": 0.5, "grunge_scale": 4,
                                 "Use_Triplanar": 1, "Edges_Smoothness": 0.6, "Ambient_Occlusion_Masking": 0.5,
                                 "Curvature_Weight": 1.0})
    _bmask(n, lips, blend=L.BlendingMode.Multiply, above=g)
    n = fill("06 Белёсые потёртости кромок", _above(n), color=MAG["scuff"], rough=0.78)
    # узко по кромкам: с histogram scan и уровнем 0.16 потёртости ложились на большую часть магазина (замер 26.10)
    mask_generator(n, EDGE, {"Wear_Level": 0.06, "Wear_Contrast": 0.9, "Grunge_Amount": 0.85, "grunge_scale": 3,
                             "Use_Triplanar": 1, "Edges_Smoothness": 0.3, "Ambient_Occlusion_Masking": 0.5,
                             "Curvature_Weight": 1.0})
    sp_lib.lop(n, 0.3)
    n = fill("07 Царапины", _above(n), color=MAG["scratch"], rough=0.66)
    mask_proc(n, _gm(12), {"invert": 1, "balance": 0.8, "contrast": 0.55}, scale=2.5)
    sp_lib.lop(n, 0.12)
    sh = L.insert_filter_effect(L.InsertPosition.inside_node(grp, L.NodeStack.Content),
                                sp_lib.rid("sharpen/sharpen", "u:filter"))
    sh.get_source().set_parameters({"intensity": 0.3})
    n = _dirt(_above(grp), color=MAG["dirt"], level=0.36, opacity=0.8, name="08 Грязь в углах")
    n = _dirt(_above(n), color=MAG["dust"], rough=0.95, level=0.12, opacity=0.2, name="09 Пыль в рёбрах",
              contrast=0.9)
    return n


def anodized(st, rail=True, tile=1.0, rough=0.42):
    """Твёрдое анодирование алюминия (муфта с планками, корпуса прицелов) — по справке навыка (painter-workflow.md,
    26.10): не краска, а оксид — тёмно-серый с лёгкой синевой, не чёрный, матово-полуглянцевый (шероховатость ~0.6),
    с мелким зерном. Цвет почти ровный — главный канал блеск: мягкие вариации блеска (глаже — темнее), затем мелкие
    контрастные глянцевые и матовые пятна; светлые глянцевые кромки, износ планки от обвеса (rail), царапины только
    в блеске; слабая резкость на группу. После: пыль в углах, ровная лёгкая пыль (вычищена с выступов), засохшее
    масло (матовое, тёмное), мелкие точки пыли.
    tile — множитель масштаба процедур: они в координатах развёртки, и при меньшей плотности текселей (прицелы) пятна
    физически крупнее, чем на муфте; rough — шероховатость основы, пятна и кромки — от неё."""
    CH = sp_lib.CH
    # основа 0.13 при металличности 0.35 и пыли сверху рендерилась светло-серой, как сырой алюминий (замер 26.10:
    # медиана 59 из 255 против 28 у воронёной стали) — темнее, почти без металла, пыли втрое меньше
    # почти диэлектрик с матовым бликом «серел» под студийным светом рядом с чёрной сталью — анодирование как металл
    # с тёмным окрашенным оксидом: тёмно-серое с атласным блеском
    base = (0.06, 0.062, 0.07)
    grp = L.insert_group(L.InsertPosition.from_textureset_stack(st))
    grp.set_name("Анодирование")
    n = fill("01 Анодированный алюминий", L.InsertPosition.inside_node(grp, L.NodeStack.Substack), color=base,
             rough=rough, metal=0.85)
    n = fill("02 Зерно оксида", _above(n), color="noise_gaussian_noise/gaussian_noise",
             rough="noise_gaussian_noise/gaussian_noise", height="noise_gaussian_noise/gaussian_noise")
    # шум в развёртке на два текселя: «блестящая шершавость» — искры в блике (трипланар 200 давал шум мельче пикселя,
    # он усреднялся в гладкое «мыло», владелец 26.10)
    sp_lib.uvscale(n, 0.5)
    n.set_blending_mode(L.BlendingMode.Overlay, CH.BaseColor)
    n.set_opacity(0.05, CH.BaseColor)
    n.set_blending_mode(L.BlendingMode.Overlay, CH.SpecularRoughness)
    n.set_opacity(0.4, CH.SpecularRoughness)
    n.set_opacity(0.012, CH.Height)
    # мельче и слабее: крупные мягкие разводы на мелких деталях прицелов читались «мылом» (владелец 26.10)
    n = _proc_layer("03 Мягкие вариации блеска", _above(n), "grunge_wipe_smudgy_soft/grunge_wipe_smudgy_soft", 3.0 * tile,
                    0.15, {"Balance": 0.5, "Contrast": 0.3}, color=_mix(base, (0.0, 0.0, 0.0), 0.15), rough=rough - 0.08)
    n = _proc_layer("04 Пятна глянца", _above(n), "grunge_spots/grunge_spots", 4.0 * tile, 0.25, None,
                    color=_mix(base, (0.0, 0.0, 0.0), 0.2), rough=rough - 0.12)
    n = _proc_layer("05 Пятна матовые", _above(n), "noise_bnw_spots_1/bnw_spots_1", 5.0 * tile, 0.15, None,
                    color=_mix(base, (0.3, 0.3, 0.32), 0.1), rough=rough + 0.16)
    # стёрто до алюминия: светлый металл с бликом (серый при металле 0.6 читался белёсой краской, владелец 26.10)
    n = _edge("06 Кромки до алюминия", _above(n), (0.78, 0.785, 0.8), 0.2, 0.05, contrast=0.85,
              grunge=0.7, metal=1.0, step=0.025)
    if rail:
        n = _proc_layer("07 Износ от обвеса", _above(n), "grunge_wipe_directional_heavy/grunge_wipe_directional_heavy",
                        2.0, 0.3, None, color=_mix(base, (0.3, 0.3, 0.32), 0.2), rough=rough - 0.06)
    # царапины — только блеск: маска покрывает много площади, светлым металлом она ложилась широкими полосами (26.10);
    # до алюминия стёрты кромки (06)
    n = fill("08 Царапины в блеске", _above(n), rough=rough - 0.12)
    mask_proc(n, _gm(12), {"invert": 1, "balance": 0.8, "contrast": 0.55}, scale=2.5 * tile)
    sp_lib.lop(n, 0.5)
    _sharpen(grp, 0.3)
    n = _dirt(_above(grp), color=(0.3, 0.3, 0.31), rough=0.92, level=0.15, opacity=0.15, name="09 Пыль в углах",
              contrast=0.85)
    n = fill("10 Ровная лёгкая пыль", _above(n), color=(0.36, 0.34, 0.31), rough=0.9, metal=0.0)
    g = mask_generator(n, DIRT, {"dirt_level": 0.5, "dirt_contrast": 0.3, "grunge_amount": 0.6, "Grunge_Scale": 8,
                                 "Use_Triplanar": 1, "edges_masking": 1.0})
    sp_lib.lop(n, 0.0)
    # тёплая пыль и масло на мелких деталях прицела ложились широко — корпус выходил оливково-коричневым (26.10);
    # пыль и масло на анодировании — нейтральные: тёплый тон в цвете металла даёт бронзовый отлив
    n = _proc_layer("11 Засохшее масло", _above(n), _gm(15), 1.8 * tile, 0.15, {"invert": 1, "balance": 0.76, "contrast": 0.4},
                    color=_mix(base, (0.03, 0.03, 0.032), 0.5), rough=0.75, metal=0.0)
    n = _proc_layer("12 Точки пыли", _above(n), "noise_bnw_spots_3/bnw_spots_3", 6.0 * tile, 0.05, None,
                    color=(0.4, 0.4, 0.41), rough=0.85, metal=0.0)
    return n


def exclude(st, path):
    """Вырезать области карты path (белое) из всех слоёв стека, собранных до этого: под группой Cerakote прицела
    рельеф износа стали (ступеньки 0.025) проступал сквозь неё рваной каймой вдоль рёбер (26.10)."""
    for n in L.get_root_layer_nodes(st):
        _bmask(n, path, blend=L.BlendingMode.Subtract, background=L.MaskBackground.White)


CK_COLOR = (0.17, 0.172, 0.185)         # Cerakote H-146 чёрный: керамический полимер, не металл, чуть холодный (фото владельца);
                                        # 27.10 — по правилу PBR для чёрных неметаллов (было 0.033, темнее угля)
CK_INTER = (0.26, 0.255, 0.25)          # промежуточный слой: истёртое до грунта/оксида покрытие (было 0.085)
CK_DUST = (0.4, 0.4, 0.4)
CK_OIL = (0.09, 0.09, 0.095)
CK_BARE = (0.62, 0.62, 0.64)            # голый металл — светлый, с бликом


def _ck_wear(name, pos, color, rough, metal, height, level, chips, scale=1.5):
    """Износ покрытия по углам: генератор кромок × гранж (порог chips) — отдельные сколы, а не кайма вдоль каждого
    ребра (так шло без гранжа, 26.10). Тот же генератор и гранж с меньшими уровнем и порогом дают вложенное пятно."""
    n = fill(name, pos, color=color, rough=rough, metal=metal, height=height)
    g = mask_generator(n, EDGE, {"Wear_Level": level, "Wear_Contrast": 0.8, "Grunge_Amount": 0.6, "grunge_scale": 4,
                                 "Use_Triplanar": 1, "Edges_Smoothness": 0.35, "Ambient_Occlusion_Masking": 0.6,
                                 "Curvature_Weight": 1.0})
    mask_proc(n, _gm(8), {"balance": chips, "contrast": 0.85}, scale=scale, above=g, blend=L.BlendingMode.Multiply)
    return n


def _ck_rail(name, pos, color, rough, metal, height, edge_level, position):
    """Продольные сколы на планках: кромки зубьев и боков планки × полосы вдоль оси (порог position) × область планок."""
    n = fill(name, pos, color=color, rough=rough, metal=metal, height=height)
    g = mask_generator(n, EDGE, {"Wear_Level": edge_level, "Wear_Contrast": 0.55, "Grunge_Amount": 0.5,
                                 "grunge_scale": 4, "Use_Triplanar": 1, "Edges_Smoothness": 0.3,
                                 "Ambient_Occlusion_Masking": 0.4, "Curvature_Weight": 1.0})
    m = _bmask(n, SLEEVE_STREAKS, blend=L.BlendingMode.Multiply, above=g)
    f = _mfilter(m, "histogram_scan", {"Position": position, "Contrast": 0.8})
    _bmask(n, SLEEVE_RAIL, blend=L.BlendingMode.Multiply, above=f)
    return n


def cerakote(st, rails=True, mask=None, chip_scale=1.5):
    """Cerakote H-146 (чёрный) на муфте с планками и заднем прицеле (владелец 26.10): керамическое покрытие — шершавое,
    ровный атласный блеск (0.52, не металл), в блике мелкое искристое зерно, без пятен (фото владельца 26.10). Износ в три уровня высоты: покрытие (0.5) →
    промежуточный слой (тёмно-серый, 0.488) → голый металл (светлый, блестящий, 0.472); промежуточный всегда окаймляет
    металл — тем же генератором с большим уровнем. На планках — сдержанные продольные сколы (обвесы ездят вперёд-назад:
    кромки × полосы вдоль оси, маски sleeve_masks_bake.py), на прицеле (rails=False) — только углы. mask — группа
    только по этой карте островов (прицел внутри набора мелкой стали; по сеткам не закрывались края островов). chip_scale — масштаб гранжа сколов: трипланар
    считается по габариту набора, у мелкой стали он с винтовку (~1 м против 0.1 м муфты) — нужен в ~10 раз мельче."""
    CH = sp_lib.CH
    grp = L.insert_group(L.InsertPosition.from_textureset_stack(st))
    grp.set_name("Cerakote H-146")
    if mask:
        _bmask(grp, mask)
    n = fill("01 Cerakote", L.InsertPosition.inside_node(grp, L.NodeStack.Substack), color=CK_COLOR, rough=0.52,
             metal=0.0, height=0.5)
    # шершавость: шум в развёртке на два текселя — в рельефе и блеске
    n = fill("02 Шершавость", _above(n), color="noise_gaussian_noise/gaussian_noise",
             rough="noise_gaussian_noise/gaussian_noise", height="noise_gaussian_noise/gaussian_noise")
    sp_lib.uvscale(n, 0.5)
    n.set_blending_mode(L.BlendingMode.Overlay, CH.BaseColor)
    n.set_opacity(0.04, CH.BaseColor)
    n.set_blending_mode(L.BlendingMode.Overlay, CH.SpecularRoughness)
    n.set_opacity(0.3, CH.SpecularRoughness)
    n.set_opacity(0.012, CH.Height)
    n = _proc_layer("04 Блеск чуть неровно", _above(n), "grunge_spots/grunge_spots", 3.0, 0.1, None, rough=0.47)
    lv = 0.03 if rails else 0.015          # прицел — только углы: самые выпуклые места (0.032 шёл вдоль длинных кромок)          # на зубьях планок много выпуклых кромок — уровень ниже (0.06 давал скол у каждого зуба)
    n = _ck_wear("05 Промежуточный слой: углы", _above(n), CK_INTER, 0.42, 0.5, 0.488, lv, 0.45 if rails else 0.38, chip_scale)
    if rails:
        n = _ck_rail("05б Промежуточный слой: планки вдоль", _above(n), CK_INTER, 0.42, 0.5, 0.488, 0.22, 0.3)
    n = _ck_wear("06 До металла: углы", _above(n), CK_BARE, 0.18, 1.0, 0.472, lv * 0.5, 0.36 if rails else 0.3, chip_scale)
    if rails:
        n = _ck_rail("06б До металла: планки вдоль", _above(n), CK_BARE, 0.18, 1.0, 0.472, 0.22, 0.23)
    _sharpen(grp, 0.3)
    # керамика держит пыль в шершавости; немного засохшего масла
    d = _dirt(_above(grp), color=CK_DUST, rough=0.92, level=0.18, opacity=0.2, name="07 Пыль в углах")
    n = _proc_layer("08 Засохшее масло", _above(d), _gm(15), 1.8, 0.12, {"invert": 1, "balance": 0.76, "contrast": 0.4},
                    color=CK_OIL, rough=0.45, metal=0.0)
    if mask:
        for x in (d, n):
            _bmask(x, mask, blend=L.BlendingMode.Multiply)
    return n


def optic_body(st, tile=1.0):
    """Корпус прицела — твёрдое анодирование (anodized): вытерто только узко по кромкам (прежний стек coated с пятнами
    на мелких круглых деталях прицела уводил до алюминия 17–20 % площади — белые проплешины). Атласный глянец 0.32:
    при 0.5 корпус на трубе читался матовым и «мыльным» рядом с муфтой (владелец 26.10)."""
    return anodized(st, rail=False, tile=tile, rough=0.32)


def optic_rim(st):
    """Ободки и проточки: точёный алюминий — светлый, сдержанный блеск, тонкое зерно; грязь в углах, налёт пятнами."""
    top = L.InsertPosition.from_textureset_stack(st)
    n = fill("01 Точёный алюминий", top, color=(0.66, 0.66, 0.68), rough=0.2, metal=1.0)
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
    n = fill("01 Резина", top, color=RUBBER["base"], rough=0.86, metal=0.0)
    n = _grain(_above(n), 0.25, 0.003)
    n = _proc_layer("03 Потёртости", _above(n), "grunge_scratches_rough/grunge_scratches_rough", 3.0, 0.35,
                    color=RUBBER["scuff"], rough=0.7)
    # резина не скалывается, как краска: кромки слегка светлее и залоснены, переход плавный, без рваного края
    # (рваные светлые полосы на наглазнике ПСО читались облезшей краской, владелец 26.10)
    n = _edge("04 Залоснённые кромки", _above(n), RUBBER["edge"], 0.5, 0.26, contrast=0.35, grunge=0.15, metal=0.0)
    n = _dirt(_above(n), color=RUBBER["dust"], rough=0.95, level=0.4, opacity=0.5, name="05 Пыль в углублениях")
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


RAW_WOOD = (0.5, 0.38, 0.23)     # древесина фанеры без лака: жёлто-охристая (27.10; прежде Screen — белёсые сколы)


def _raw_wood(name, pos, rough=0.82, lift=0.0006, show=0.8, dirt=0.35):
    """Группа «лак снят до сырой древесины»: жёлто-охристая древесина (show — насколько закрывает лак; волокно основы
    проступает сквозь остаток), в сколе въелась грязь (dirt), самое матовое и ниже лака на его толщину. Маску задаёт
    вызывающий. Прежде было Screen + обесцвечивание — сколы и протёртости читались белыми (владелец 27.10)."""
    g = L.insert_group(pos)
    g.set_name(name)
    a = fill("Сырая древесина", L.InsertPosition.inside_node(g, L.NodeStack.Substack), color=RAW_WOOD)
    a.set_opacity(show, sp_lib.CH.BaseColor)
    b = fill("Въелась грязь", _above(a), color=(0.7, 0.6, 0.5))
    b.set_blending_mode(L.BlendingMode.Multiply, sp_lib.CH.BaseColor)
    mask_proc(b, "grunge_wipe_smudgy_soft/grunge_wipe_smudgy_soft", {"Balance": 0.5, "Contrast": 0.3}, scale=3.0)
    sp_lib.lop(b, dirt)
    c = fill("Матовое, без лака", _above(b), rough=rough, height=lift)
    c.set_blending_mode(L.BlendingMode.Subtract, sp_lib.CH.Height)
    return g


def wood(st):
    """Приклад — клеёная фанера под лаком (26.10: «скучная и ненастоящая»; разбор по справке навыка
    wood-and-paint-layers.md и образцам владельца с Fab). Порядок: дерево → рельеф → крупные пятна → лак → тона →
    повреждения → резкость → грязь, пыль, следы рук. Основа — фото шпона, вариант C (wood_veneer_bake.py): само дерево
    матовое, блеск даёт лак. Три тона: средний — древесина; тёмный — стыки и поры по AO и к концам приклада (чуть
    глянцевее, как лак); светлый — лак истёрт на кромках, сквозь него жёлтая древесина (27.10: в местах хвата руки
    темнят — засаленность, сколы — жёлтая древесина с грязью, не белые). Крупные пятна света и тени — Soft Light (Normal съел бы волокно), полосами вдоль волокна. Повреждения «крупное — среднее —
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
    # тон гуляет крупно (27.10, владелец: «тон»): лак лёг неровно — широкие места темнее и светлее вдоль приклада,
    # чтобы приклад не был ровно-рыжим (маска tone — wood_veneer_bake.py)
    n = fill("05б Тон крупно темнее", _above(n), color=(0.55, 0.45, 0.38))
    n.set_blending_mode(L.BlendingMode.Multiply, CH.BaseColor)
    _bmask(n, _wmask("tone"))
    sp_lib.lop(n, 0.75)
    n = fill("05в Тон крупно светлее", _above(n), color=(0.72, 0.62, 0.5))
    n.set_blending_mode(L.BlendingMode.SoftLight, CH.BaseColor)
    _bmask(n, _wmask("tone"), blend=L.BlendingMode.Subtract, background=L.MaskBackground.White)
    sp_lib.lop(n, 0.4)
    # морилка: коричневее и темнее в целом — приклад читался рыже-оранжевым
    n = fill("05г Морилка", _above(n), color=(0.64, 0.54, 0.47))
    n.set_blending_mode(L.BlendingMode.Multiply, CH.BaseColor)
    sp_lib.lop(n, 0.6)
    # лак: тёплый тон тонким слоем и полуматовый блеск; в порах проседает и тусклее. Янтарь бледнее прежнего
    # (0.8 / 0.5 / 0.32 на 55 % — приклад выходил оранжевым)
    n = fill("06 Лак", _above(n), color=(0.8, 0.6, 0.45), rough=0.42)
    n.set_blending_mode(L.BlendingMode.Multiply, CH.BaseColor)
    n.set_opacity(0.5, CH.BaseColor)
    # в углублениях волокна лака почти нет — матово (владелец 26.10); маска — нижняя пятая часть высоты (поры),
    # только на лицевом шпоне: на срезах фанеры тёмные слои ниже по высоте и шли матовыми полосами — под верхним
    # светом срезы белели «инеем» (27.10)
    n = fill("07 Лак в порах тусклее", _above(n), rough=0.85)
    m = _bmask(n, WOOD_HEIGHT, blend=L.BlendingMode.Subtract, background=L.MaskBackground.White)
    m = _mfilter(m, "histogram_scan", {"Position": 0.36, "Contrast": 0.75})
    _bmask(n, _wmask("face"), blend=L.BlendingMode.Multiply, above=m)
    sp_lib.lop(n, 1.0)
    # срезы фанеры: лак впитался в торцы ровно — полуматово, без полос
    n = fill("07б Лак на срезах", _above(n), rough=0.62)
    _bmask(n, _wmask("face"), blend=L.BlendingMode.Subtract, background=L.MaskBackground.White)
    n = fill("08 Апельсиновая корка", _above(n), rough="noise_clouds_2/clouds_2", height="noise_clouds_2/clouds_2")
    triplanar(n, 60.0)
    n.set_blending_mode(L.BlendingMode.Overlay, CH.SpecularRoughness)
    n.set_opacity(0.12, CH.SpecularRoughness)
    n.set_opacity(0.0012, CH.Height)
    n = _proc_layer("09 Неровный блеск лака", _above(n), "grunge_wipe_smudgy_soft/grunge_wipe_smudgy_soft", 1.6, 0.5,
                    {"Balance": 0.55, "Contrast": 0.3}, rough=0.5)
    # места хвата (шейка, щека на гребне): руки не светлят, а темнят — жир и грязь въедаются в лак, он лоснится
    # (27.10, владелец: «грязь от рук»)
    n = fill("10 Засалено руками", _above(n), color=(0.6, 0.5, 0.42), rough=0.3)
    n.set_blending_mode(L.BlendingMode.Multiply, CH.BaseColor)
    m = _bmask(n, _wmask("hold"))
    mask_proc(n, "grunge_wipe_smudgy_soft/grunge_wipe_smudgy_soft", {"Balance": 0.55, "Contrast": 0.3}, scale=1.6,
              blend=L.BlendingMode.Multiply, above=m)
    sp_lib.lop(n, 0.85)
    # тёмный тон: стыки и поры по AO и к концам — темнее и чуть глянцевее, рельеф волокна не трогает
    n = fill("11 Тёмный тон: стыки, поры, концы", _above(n), color=(0.62, 0.55, 0.48), rough=0.36)
    n.set_blending_mode(L.BlendingMode.Multiply, CH.BaseColor)
    g = mask_generator(n, DIRT, {"dirt_level": 0.35, "dirt_contrast": 0.6, "grunge_amount": 0.0, "Grunge_Scale": 5,
                                 "Use_Triplanar": 1, "edges_masking": 0.8})
    _bmask(n, _wmask("ends"), blend=L.BlendingMode.Lighten, above=g, opacity=0.4)
    sp_lib.lop(n, 0.38)
    # лак истёрт на кромках: сквозь остаток проступает древесина (не белое — show 0.35), только по кромкам; в местах
    # хвата — засаленность (слой 10), а не светлое
    w = _raw_wood("12 Лак истёрт на кромках", _above(n), rough=0.7, lift=0.0004, show=0.35, dirt=0.25)
    g = mask_generator(w, EDGE, {"Wear_Level": 0.14, "Wear_Contrast": 0.7, "Grunge_Amount": 0.85, "grunge_scale": 4,
                                 "Use_Triplanar": 1, "Edges_Smoothness": 0.5, "Ambient_Occlusion_Masking": 0.6,
                                 "Curvature_Weight": 1.0})
    m = mask_proc(w, "grunge_wipe_brushed/grunge_wipe_brushed", None, scale=1.4, blend=L.BlendingMode.Multiply, above=g)
    _mfilter(m, "histogram_scan", {"Position": 0.5, "Contrast": 0.35})
    # сколы лака: редкие, крупнее и резче протёртого — по кромкам окон, затыльника и низа; в сколе — жёлтая
    # древесина с въевшейся грязью
    c = _raw_wood("13 Сколы лака", _above(w), rough=0.86, lift=0.0012, show=0.85, dirt=0.45)
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
    n = fill("15 Царапины лака", _above(n), color=(0.12, 0.07, 0.035), rough=0.62)   # тёплые: серые на тёмном дереве — мелом
    n.set_blending_mode(L.BlendingMode.Screen, CH.BaseColor)
    mask_proc(n, _gm(12), {"invert": 1, "balance": 0.78, "contrast": 0.55}, scale=2.5)
    sp_lib.lop(n, 0.22)
    sh = L.insert_filter_effect(L.InsertPosition.inside_node(grp, L.NodeStack.Content),
                                sp_lib.rid("sharpen/sharpen", "u:filter"))
    sh.get_source().set_parameters({"intensity": 0.35})
    # после резкости: грязь в углах, пыль (где руками не трут), засаленность
    n = _dirt(_above(grp), color=(0.12, 0.08, 0.05), rough=0.8, level=0.34, opacity=0.42, name="16 Грязь в углах")
    n = fill("17 Пыль", _above(n), color=(0.34, 0.27, 0.2), rough=0.92)
    g = mask_generator(n, DIRT, {"dirt_level": 0.22, "dirt_contrast": 0.85, "grunge_amount": 0.6, "Grunge_Scale": 8,
                                 "Use_Triplanar": 1, "edges_masking": 0.9})
    _bmask(n, _wmask("hold"), blend=L.BlendingMode.Subtract, above=g)
    sp_lib.lop(n, 0.16)
    n = _proc_layer("18 Засаленность", _above(n), "grunge_fingerprints_dirty/grunge_fingerprints_dirty", 2.5, 0.2,
                    {"Balance": 0.45, "Contrast": 0.35}, color=(0.8, 0.72, 0.62), rough=0.36)
    n.set_blending_mode(L.BlendingMode.Multiply, CH.BaseColor)
    return n


MARKS_DIR = "E:/Games/RING-godot/_asset_src/vss_m_v8/sp_marks"     # contact_marks.py: следы рук и жизни по местам
MARK_BASE_ROUGH = {"receiver": 0.32, "steel_parts": 0.32, "suppressor": 0.28, "sleeve": 0.3, "handguard": 0.36,
                   "magazine": 0.5, "magazine_30": 0.5, "wood": 0.32, "bare_steel": 0.34, "rubber": 0.86}


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
