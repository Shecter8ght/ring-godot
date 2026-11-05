# ИЗЛОМ-45 (wpn_smg_03), этап 2 — износ (навык weapon-asset-wear) в Substance Painter через мост, поверх принятой
# заводской отделки v4 («Этап 1 — заводская отделка» не меняется; износ — группа «Этап 2 — износ» над ней, выключается
# целиком). План — asset-state.md модели: заметный, как на образце владельца (refs/25_…: светлая пыль в углублениях,
# пятна тона, потёртые кромки, мелкие царапины), ЧВК, город; до металла — местами, на выступах; надписи и знаки залиты
# белой краской, слегка стёртой. Генераторы — по просьбе владельца: Metal Edge Wear, Dirt, Curvature, Edge Damage.
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
# периоды узоров, мм
P_DUST_PATCH = 60.0
P_SCRATCH = 80.0
P_PRINTS = 45.0
P_SPARSE = 260.0                   # крупное «где-то есть, где-то нет» для царапин и отпечатков
P_PAINT_WEAR = 25.0
P_TONE = 140.0                     # крупные зоны тона: где светлее (вытерто, выгорело), где темнее (масло, чистили)
GRUNGE_TILES = 20                  # гранж генераторов: плиток на сцену (~55 мм)
SCR = {"invert": 0, "balance": 0.36, "contrast": 0.55}    # grunge_scratches_fine без серого фона (ВСС-М, 25.10)


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


def _sparse(layer, scene, period=P_SPARSE, rot=0.0):
    """Крупные облака умножением в маске слоя: след есть не везде."""
    return mask_proc(layer, "noise_clouds_1/clouds_1", scale=scene / period, blend=L.BlendingMode.Multiply,
                     above=_last_mask(layer), rot=rot)


def _last_mask(layer):
    eff = layer.mask_effects()
    return eff[0] if eff else None


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
    last = None

    def nxt():
        return L.InsertPosition.above_node(last) if last else pos

    # 0. белая краска в гравировке надписей и знаков, местами вытерта
    wpath = f"{MASKS}/{setname}_white.png"
    if os.path.exists(wpath):
        lay = fill("краска в гравировке — белая", nxt(), color=PAINT, rough=0.75, metal=0.0)
        sp_finish.bitmap_mask(lay, wpath)
        mask_proc(lay, "grunge_wipe_smudgy_soft/grunge_wipe_smudgy_soft", scale=scene / P_PAINT_WEAR,
                  blend=L.BlendingMode.Subtract, opacity=0.7, above=_last_mask(lay))
        last = lay
        log.append("краска")

    # 0б. два-три тона в цвете вместо одного чёрного (владелец 05.11: «надо 2-3 цвета в base color»): крупные мягкие
    # зоны — светлее (вытерто, выгорело) и темнее (масло, чистили); у образца 25 корпус не однотонный
    for nm, col, rot, op in (("тон — светлее местами", (0.20, 0.20, 0.19), 0.0, 0.55),
                             ("тон — темнее местами", (0.055, 0.055, 0.06), 1.3, 0.45)):
        lay = fill(nm, nxt(), color=col)
        mf = mask_proc(lay, "grunge_wipe_smudgy_soft/grunge_wipe_smudgy_soft", {"Balance": 0.55, "Contrast": 0.3},
                       scale=scene / P_TONE, rot=rot)
        sp_lib.lop(lay, op)
        only_meshes(lay, allm)
        last = lay
    log.append("тона")

    # 1. пыль в углублениях — генератор Dirt
    # пыль — только цвет и блеск: полупрозрачный «металл 0» поверх стали давал металличность 0.15–0.5 на трети набора
    # (самопроверка проба 2); тонкая плёнка пыли на металле — светлее и матовее, металл под ней остаётся
    lay = fill("пыль в углублениях (Dirt)", nxt(), color=DUST, rough=0.92)
    g = mask_generator(lay, "mg_dirt/mg_dirt")
    _set_params(g.get_source(), {"Use_Triplanar": 1, "dirt_level": 0.25, "dirt_contrast": 0.7, "grunge_amount": 0.5,
                                 "Grunge_Scale": GRUNGE_TILES, "edges_masking": 0.7})
    sp_lib.lop(lay, 0.75)
    only_meshes(lay, allm)
    last = lay
    log.append("пыль")

    # 2. пятна пыли и тона на плоскостях
    lay = fill("пятна пыли на плоскостях", nxt(), color=(0.33, 0.32, 0.30), rough=0.85)
    mask_proc(lay, "grunge_wipe_smudgy_soft/grunge_wipe_smudgy_soft", {"Balance": 0.45, "Contrast": 0.4},
              scale=scene / P_DUST_PATCH)
    sp_lib.lop(lay, 0.30)
    only_meshes(lay, allm)
    last = lay
    # мелкие пятна (~1.8 см): без них гладкий полимер магазинов однотонный на сантиметровом масштабе (самопроверка)
    lay = fill("мелкие пятна пыли", nxt(), color=(0.30, 0.29, 0.28), rough=0.8)
    mask_proc(lay, "grunge_wipe_smudgy_soft/grunge_wipe_smudgy_soft", {"Balance": 0.5, "Contrast": 0.35},
              scale=scene / 18.0, rot=0.9)
    sp_lib.lop(lay, 0.18)
    only_meshes(lay, allm)
    last = lay
    log.append("пятна")

    # 3–5. по материалам: потёртые кромки (Metal Edge Wear), сколы на выступах (Edge Damage), царапины. Маски металла —
    # жёсткие (порогом): при неполной непрозрачности металл смешивался с покрытием — металличность 0.15–0.5 на трети
    # набора стали и «камуфляж» вытертого (самопроверка проба 1). Мелкая сталь (оси, флажки, спуск) — почти одни кромки:
    # ей только слабые кромки, без сколов и царапин.
    for c, names in cls.items():
        if c == "round":           # патронам — только тона и пыль (их в атласе магазина много: однотонность)
            continue
        col, rough, metal = BARE[c]
        level = {"alu": 0.14, "steel": 0.10, "poly": 0.22, "rubber": 0.22}[c]
        lay = fill(f"кромки потёрты — {c} (Metal Edge Wear)", nxt(), color=col, rough=rough, metal=metal)
        g = mask_generator(lay, "mg_metal_edge_wear/mg_metal_edge_wear")
        _set_params(g.get_source(), {"Use_Triplanar": 1, "Wear_Level": level, "Wear_Contrast": 0.85,
                                     "Grunge_Amount": 0.65, "grunge_scale": GRUNGE_TILES,
                                     "Ambient_Occlusion_Masking": 0.6})
        if metal:
            sp_finish._mfilter(g, "histogram_scan", {"Position": 0.5, "Contrast": 0.9})
        only_meshes(lay, names)
        last = lay
        if c == "steel":
            log.append(c)
            continue

        lay = fill(f"сколы на выступах — {c} (Edge Damage)", nxt(), color=col, rough=rough, metal=metal)
        sp_lib.mask_black(lay)
        L.insert_smart_mask(L.InsertPosition.inside_node(lay, L.NodeStack.Mask), sp_lib.rid("Edge Damage", "u:smartmask"))
        hs = sp_finish._mfilter(_last_mask(lay), "histogram_scan", {"Position": 0.5, "Contrast": 0.9})
        _sparse(lay, scene, period=180.0, rot=0.4)
        only_meshes(lay, names)
        last = lay

        lay = fill(f"царапины — {c}", nxt(), color=col, rough=rough, metal=metal)
        mf = mask_proc(lay, "grunge_scratches_fine/grunge_scratches_fine", SCR, scale=scene / P_SCRATCH)
        # у тонких рисок при трёхпроекционном смешении остаётся серая «подложка» (царапины давали +10 к цвету на 88 %
        # площади, проба 1) — порогом оставить только сами риски
        sp_finish._mfilter(mf, "histogram_scan", {"Position": 0.04, "Contrast": 0.9})
        _sparse(lay, scene)
        sp_lib.lop(lay, 1.0 if metal else 0.45)
        only_meshes(lay, names)
        last = lay
        log.append(c)

    # 6. отпечатки и жир — где берут руками: полимер и мелкая сталь (рукоять, магазины, флажки, рукоятка заряжания)
    hands = cls.get("poly", []) + cls.get("steel", [])
    if hands:
        lay = fill("отпечатки и жир", nxt(), color=(0.85, 0.85, 0.85), rough=0.15)
        lay.set_blending_mode(L.BlendingMode.Multiply, CH.BaseColor)
        lay.set_blending_mode(L.BlendingMode.Subtract, CH.SpecularRoughness)
        mask_proc(lay, "grunge_fingerprints_dirty/grunge_fingerprints_dirty", scale=scene / P_PRINTS)
        _sparse(lay, scene, rot=0.8)
        sp_lib.lop(lay, 0.7)
        only_meshes(lay, hands)
        last = lay
        log.append("отпечатки")
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
