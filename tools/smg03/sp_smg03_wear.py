# ИЗЛОМ-45 (wpn_smg_03), этап 2 — износ (навык weapon-asset-wear) в Substance Painter через мост, поверх принятой
# заводской отделки v4 («Этап 1 — заводская отделка» не меняется; износ — группа «Этап 2 — износ» над ней, выключается
# целиком). План — asset-state.md модели.
#
# v2 (владелец 05.11: «износа очень много», 10 пунктов мест): износ только в названных местах — маски мест считает
# tools/smg03/wear_zones.py по картам положения (_asset_src/smg03/tex/wear/<набор>_<место>.png), рисунок кромок в них —
# генератор Metal Edge Wear; детали стали (рукоятка заряжания, кнопки сброса магазина, рычаг задержки) — сетками. Общий
# износ корпуса — реже и слабее, на планки не заходит; базовый тон чуть светлее и теплее; Edge Damage по корпусу убран
# (его маска давала пятна с ровной стороной не от ребра).
#
#   … sp_run.py -c "import sys; sys.path.insert(0, r'E:/Games/RING-godot/tools/smg03'); import sp_smg03_wear;
#                   print(sp_smg03_wear.build())"            → метка _wear_done.txt, проект сохраняется
#
# Масштабы: трёхпроекционная проекция Painter считает плитки на габарит всей сцены (scene.json), поэтому масштаб =
# сцена / период узора в мм. Гранж генераторов — тоже трёхпроекционный (Use_Triplanar): по развёртке он рвётся на швах
# островов игровой сетки.
import os

import substance_painter.layerstack as L
import substance_painter.project as P
import substance_painter.textureset as TS

import sp_finish
import sp_lib
import sp_smg03
from sp_lib import CH, fill, mask_generator, mask_proc, only_meshes

GROUP = "Этап 2 — износ"
MASKS = sp_smg03.TEX + "/masks"
ZONES = sp_smg03.TEX + "/wear"
# класс материала по коду отделки слота: что открывается под износом
MAT = {"AN": "alu", "NT": "steel", "PH": "steel", "PL": "poly", "RB": "rubber", "BR": "round", "CU": "round"}
# оголённое основание / потёртая кромка: цвет sRGB, шероховатость, металличность
BARE = {
    "alu": ((0.70, 0.70, 0.71), 0.32, 1.0),       # анодирование стёрто до алюминия
    "steel": ((0.52, 0.52, 0.53), 0.28, 1.0),     # фосфат и нитрид стёрты до стали
    "poly": ((0.25, 0.25, 0.25), 0.40, 0.0),      # полимер: светлее и глаже, металла нет
    "rubber": ((0.20, 0.20, 0.20), 0.60, 0.0),
}
DUST = (0.40, 0.39, 0.37)          # городская серая пыль на чёрном
PAINT = (0.72, 0.72, 0.70)         # белая краска в гравировке (не свежая)
WARM = (0.15, 0.14, 0.125)         # базовый тон чуть светлее и теплее (владелец, пункт 10: «совсем чуть-чуть»)
# периоды узоров, мм
P_DUST_PATCH = 60.0
P_SCRATCH = 80.0
P_PRINTS = 45.0
P_SPARSE = 260.0                   # крупное «где-то есть, где-то нет» для царапин и отпечатков
P_PAINT_WEAR = 25.0
P_TONE = 140.0                     # крупные зоны тона: где светлее (вытерто, выгорело), где темнее (масло, чистили)
GRUNGE_TILES = 20                  # гранж генераторов: плиток на сцену (~55 мм)
SCR = {"invert": 0, "balance": 0.36, "contrast": 0.55}    # grunge_scratches_fine без серого фона (ВСС-М, 25.10)
# детали стали по местам владельца
CHARGING = ["ChargingHandle_Steel__small_steel_low", "ChargingSlider_Steel__small_steel_low"]
MAG_RELEASE = ["MagReleaseL_Steel__polymer_small_low", "MagReleaseR_Steel__polymer_small_low"]
BOLT_CATCH = ["BoltCatch_Steel__small_steel_low"]


def _set_params(src, params):
    """Только те параметры, что есть у ресурса (имена у генераторов разного регистра)."""
    have = src.get_parameters()
    src.set_parameters({k: v for k, v in params.items() if k in have})


def _new_group(setname):
    """Группа «Этап 2 — износ» набора заново, поверх заводской; Passthrough по всем каналам (по умолчанию Normal —
    Multiply / Subtract внутри смешивались бы с пустой группой, AR-15 30.10). Возврат — позиция первого слоя."""
    st = sp_lib.stack_by_name(setname)
    for n in L.get_root_layer_nodes(st):
        if n.get_name() == GROUP:
            L.delete_node(n)
    grp = L.insert_group(L.InsertPosition.from_textureset_stack(st))
    grp.set_name(GROUP)
    for ch in st.all_channels():
        grp.set_blending_mode(L.BlendingMode.Passthrough, ch)
    return L.InsertPosition.inside_node(grp, L.NodeStack.Substack)


def _last_mask(layer):
    eff = layer.mask_effects()
    return eff[0] if eff else None


def _sparse(layer, scene, period=P_SPARSE, rot=0.0):
    """Крупные облака умножением в маске слоя: след есть не везде."""
    return mask_proc(layer, "noise_clouds_1/clouds_1", scale=scene / period, blend=L.BlendingMode.Multiply,
                     above=_last_mask(layer), rot=rot)


def _zone(layer, setname, name, blend=None):
    """Маска места (wear_zones.py) в маске слоя: первой — как есть, поверх — режимом blend (Multiply — ограничить
    рисунок местом, Subtract — вычесть место). Нет файла — False."""
    path = f"{ZONES}/{setname}_{name}.png"
    if not os.path.exists(path):
        return False
    sp_lib.mask_black(layer)
    top = _last_mask(layer)
    pos = L.InsertPosition.above_node(top) if top else L.InsertPosition.inside_node(layer, L.NodeStack.Mask)
    m = L.insert_fill(pos)
    m.set_source(None, sp_finish._bitmap(path))
    m.set_projection_mode(L.ProjectionMode.UV)
    if blend is not None:
        m.set_blending_mode(blend)
    return True


def _edge_wear(layer, level, contrast=0.85, hard=True):
    g = mask_generator(layer, "mg_metal_edge_wear/mg_metal_edge_wear")
    _set_params(g.get_source(), {"Use_Triplanar": 1, "Wear_Level": level, "Wear_Contrast": contrast,
                                 "Grunge_Amount": 0.65, "grunge_scale": GRUNGE_TILES, "Ambient_Occlusion_Masking": 0.6})
    if hard:
        # металл — жёсткой маской: при неполной непрозрачности металличность выходила 0.15–0.5 (самопроверка v1)
        sp_finish._mfilter(g, "histogram_scan", {"Position": 0.5, "Contrast": 0.9})
    return g


def _classes(setname):
    """Сетки набора по классу материала (по отделке слота)."""
    spec = {s["id"]: s for s in sp_smg03._spec()["slots"]}
    out = {}
    for sid, rec in sp_smg03._meshes().get(setname, {}).items():
        cls = MAT.get(spec[sid]["finish"][:2])
        if cls:
            out.setdefault(cls, []).extend(rec["meshes"])
    return out


def build_set(setname, scene):
    cls = _classes(setname)
    allm = [m for v in cls.values() for m in v]
    if not allm:
        return f"{setname}: нет слотов"
    pos = _new_group(setname)
    log = []
    st = {"last": None}

    def add(name, **ch):
        lay = fill(name, L.InsertPosition.above_node(st["last"]) if st["last"] else pos, **ch)
        st["last"] = lay
        return lay

    has_rails = os.path.exists(f"{ZONES}/{setname}_rails.png")

    # 0. белая краска в гравировке надписей и знаков, местами вытерта
    wpath = f"{MASKS}/{setname}_white.png"
    if os.path.exists(wpath):
        lay = add("краска в гравировке — белая", color=PAINT, rough=0.75, metal=0.0)
        sp_finish.bitmap_mask(lay, wpath)
        mask_proc(lay, "grunge_wipe_smudgy_soft/grunge_wipe_smudgy_soft", scale=scene / P_PAINT_WEAR,
                  blend=L.BlendingMode.Subtract, opacity=0.7, above=_last_mask(lay))
        log.append("краска")

    # 1. базовый тон чуть светлее и теплее, и два тона крупными зонами — слабо (пункт 10)
    lay = add("тон — чуть светлее и теплее", color=WARM)
    sp_lib.lop(lay, 0.18)
    only_meshes(lay, allm)
    for nm, col, rot, op in (("тон — светлее местами", (0.20, 0.20, 0.19), 0.0, 0.35),
                             ("тон — темнее местами", (0.055, 0.055, 0.06), 1.3, 0.30)):
        lay = add(nm, color=col)
        mask_proc(lay, "grunge_wipe_smudgy_soft/grunge_wipe_smudgy_soft", {"Balance": 0.55, "Contrast": 0.3},
                  scale=scene / P_TONE, rot=rot)
        sp_lib.lop(lay, op)
        only_meshes(lay, allm)
    log.append("тон")

    # 2. пыль в углублениях (и в пазах планок — «немного пыли и всякой грязьки»), без металличности
    lay = add("пыль в углублениях (Dirt)", color=DUST, rough=0.92)
    g = mask_generator(lay, "mg_dirt/mg_dirt")
    _set_params(g.get_source(), {"Use_Triplanar": 1, "dirt_level": 0.22, "dirt_contrast": 0.7, "grunge_amount": 0.55,
                                 "Grunge_Scale": GRUNGE_TILES, "edges_masking": 0.7})
    sp_lib.lop(lay, 0.6)
    only_meshes(lay, allm)
    lay = add("пятна пыли", color=(0.31, 0.30, 0.28), rough=0.82)
    mask_proc(lay, "grunge_wipe_smudgy_soft/grunge_wipe_smudgy_soft", {"Balance": 0.45, "Contrast": 0.4},
              scale=scene / P_DUST_PATCH)
    sp_lib.lop(lay, 0.14)
    only_meshes(lay, allm)
    lay = add("мелкие пятна пыли", color=(0.30, 0.29, 0.28), rough=0.8)
    mask_proc(lay, "grunge_wipe_smudgy_soft/grunge_wipe_smudgy_soft", {"Balance": 0.5, "Contrast": 0.35},
              scale=scene / 18.0, rot=0.9)
    sp_lib.lop(lay, 0.12)
    only_meshes(lay, allm)
    log.append("пыль")

    # 3. общий износ кромок — только полимеру и резине, слабо и местами (пункт 10); металл — только в местах владельца:
    # общий Metal Edge Wear даже на уровне 0.07 сыпал крапом по всей верхней кромке бортов и по боковым планкам (v2,
    # проба 1); планки чистые (пункт 2), царапины — только по корпусу верха, редкие
    for c, names in cls.items():
        if c in ("round", "alu", "steel"):
            if not (c == "alu" and setname == "Upper"):
                continue
        col, rough, metal = BARE[c]
        if c in ("poly", "rubber"):
            lay = add(f"кромки — {c}, редко", color=col, rough=rough, metal=metal)
            _edge_wear(lay, 0.07, hard=False)
            _sparse(lay, scene, period=180.0, rot=0.6)
            only_meshes(lay, names)
        if c in ("alu", "poly"):
            lay = add(f"царапины — {c}, редкие", color=col, rough=rough, metal=metal)
            mf = mask_proc(lay, "grunge_scratches_fine/grunge_scratches_fine", SCR, scale=scene / P_SCRATCH)
            sp_finish._mfilter(mf, "histogram_scan", {"Position": 0.03, "Contrast": 0.9})
            _sparse(lay, scene, period=200.0)
            if has_rails:
                _zone(lay, setname, "rails", L.BlendingMode.Subtract)
            sp_lib.lop(lay, 0.4 if metal else 0.3)
            only_meshes(lay, names)
    log.append("кромки редко")

    # 4. места владельца — корпус (верх)
    if setname == "Upper":
        a_col, a_rough, a_metal = BARE["alu"]
        # 2: три участка износа на верхней планке
        # кромки зубьев — рвано и не все: сплошной генератор обводил вершины зубьев светлыми «рамками» (v2, проба 1)
        lay = add("планка — три участка износа", color=a_col, rough=a_rough, metal=a_metal)
        g = mask_generator(lay, "mg_metal_edge_wear/mg_metal_edge_wear")
        _set_params(g.get_source(), {"Use_Triplanar": 1, "Wear_Level": 0.32, "Wear_Contrast": 0.7, "Grunge_Amount": 0.9,
                                     "grunge_scale": GRUNGE_TILES * 2, "Ambient_Occlusion_Masking": 0.6})
        sp_finish._mfilter(g, "histogram_scan", {"Position": 0.45, "Contrast": 0.85})
        _zone(lay, setname, "rail_spots", L.BlendingMode.Multiply)
        _sparse(lay, scene, period=60.0, rot=0.3)
        # 1: вдоль паза рукоятки заряжания — вытерто глаже и светлее, по ходу
        lay = add("паз рукоятки заряжания — по ходу", color=(0.26, 0.26, 0.26), rough=0.36)
        _zone(lay, setname, "slot")
        sp_lib.lop(lay, 0.85)
        # 3: передний торец — правое ребро; слева только верхний угол
        lay = add("передний торец — правое ребро", color=a_col, rough=a_rough, metal=a_metal)
        _edge_wear(lay, 0.6)
        _zone(lay, setname, "front_r", L.BlendingMode.Multiply)
        lay = add("передний торец — левый верхний угол", color=a_col, rough=a_rough, metal=a_metal)
        _edge_wear(lay, 0.45)
        _zone(lay, setname, "front_tl", L.BlendingMode.Multiply)
        # 8: задний торец, левое ребро — до металла, как о бетонную стену
        lay = add("задний торец — ссадина о бетон", color=(0.66, 0.66, 0.67), rough=0.42, metal=1.0)
        _zone(lay, setname, "rear_scrape")
        sp_finish._mfilter(_last_mask(lay), "histogram_scan", {"Position": 0.55, "Contrast": 0.8})
        # 9: бороздки по ходу лепестков переводчика и предохранителя
        lay = add("бороздки по ходу флажков", color=(0.55, 0.55, 0.56), rough=0.3, metal=1.0)
        _zone(lay, setname, "arcs")
        sp_finish._mfilter(_last_mask(lay), "histogram_scan", {"Position": 0.5, "Contrast": 0.85})
        # 5: цевьё, где держат — светлее тоном и разводы ладони, отпечатки
        lay = add("цевьё — вытерто светлее", color=(0.19, 0.185, 0.175), rough=0.5)
        _zone(lay, setname, "hand_tone")
        sp_lib.lop(lay, 0.55)
        lay = add("цевьё — разводы ладони и отпечатки", color=(0.85, 0.85, 0.85), rough=0.16)
        lay.set_blending_mode(L.BlendingMode.Multiply, CH.BaseColor)
        lay.set_blending_mode(L.BlendingMode.Subtract, CH.SpecularRoughness)
        _zone(lay, setname, "hand_prints")
        log.append("места верха")

    # 4. места владельца — низ (рукоять)
    if setname == "Lower":
        # 6: спинка, перёд и правая щёчка — глаже от ладони и светлее градиентом
        lay = add("рукоять — глаже и светлее от ладони", color=(0.20, 0.195, 0.185), rough=0.34)
        _zone(lay, setname, "grip")
        sp_lib.lop(lay, 0.75)
        log.append("рукоять")

    # 4. места владельца — детали стали
    if setname == "Steel":
        s_col, s_rough, s_metal = BARE["steel"]
        p_col, p_rough, _ = BARE["poly"]
        # 1: рукоятка заряжания — чуть-чуть
        lay = add("рукоятка заряжания — чуть-чуть", color=s_col, rough=s_rough, metal=s_metal)
        _edge_wear(lay, 0.22)
        only_meshes(lay, CHARGING)
        # 4: кнопки сброса магазина — следы пальца и отпечатки
        lay = add("сброс магазина — потёрто", color=p_col, rough=p_rough)
        _edge_wear(lay, 0.4, hard=False)
        only_meshes(lay, MAG_RELEASE)
        lay = add("сброс магазина — отпечатки", color=(0.85, 0.85, 0.85), rough=0.15)
        lay.set_blending_mode(L.BlendingMode.Multiply, CH.BaseColor)
        lay.set_blending_mode(L.BlendingMode.Subtract, CH.SpecularRoughness)
        mask_proc(lay, "grunge_fingerprints_dirty/grunge_fingerprints_dirty", scale=scene / 20.0)
        only_meshes(lay, MAG_RELEASE)
        # 7: кнопки затворной задержки — небольшие вытертости
        lay = add("задержка — вытертости", color=s_col, rough=s_rough, metal=s_metal)
        _edge_wear(lay, 0.3)
        only_meshes(lay, BOLT_CATCH)
        log.append("детали")
    return f"{setname}: " + " ".join(log)


def build(only=None):
    """Группа износа во всех наборах (или only); итог — _wear_done.txt, проект сохраняется."""
    scene = sp_smg03._scene_mm()
    log = []
    for t in TS.all_texture_sets():
        if only and t.name() not in only:
            continue
        log.append(build_set(t.name(), scene))

    def done():
        P.save()
        return " | ".join(log)
    sp_lib.when_idle(done, "_wear_done.txt")
    return " | ".join(log)
