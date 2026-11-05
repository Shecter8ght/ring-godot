# ИЗЛОМ-45 (wpn_smg_03), этап 2 — износ (навык weapon-asset-wear) в Substance Painter через мост, поверх принятой
# заводской отделки v4 («Этап 1 — заводская отделка» не меняется; износ — группа «Этап 2 — износ» над ней, выключается
# целиком). План — asset-state.md модели.
#
# v2 (владелец 05.11: «износа очень много», 10 пунктов мест): износ только в названных местах — маски мест считает
# tools/smg03/wear_zones.py по картам положения (_asset_src/smg03/tex/wear/<набор>_<место>.png), рисунок кромок в них —
# генератор Metal Edge Wear; детали стали (рукоятка заряжания, кнопки сброса магазина, рычаг задержки) — сетками. Общий
# износ металла и Edge Damage по корпусу убраны (его маска давала пятна с ровной стороной не от ребра).
# v3 (владелец 05.11: «сделаем всё, но аккуратно и дозированно; очень нужны вариации base color — тёплое и холодное,
# светлое и тёмное»): тона материалов и четыре вариации цвета разного масштаба, крупный градиент по высоте, блеск
# разводами (протёрто тряпкой, матовее пятнами), пыль с причиной (кольца у крепежа, насечка рукояти, рёбра затыльника,
# налёт на верхних гранях, меньше там, где трут), стёртое живее (тёмные мазки внутри, ободок покрытия, проваливается в
# нормали), масло у окна выброса и затвора, латунь от гильз, нагар у дула, краска маркировки неровная, знак серее,
# ручные акценты (длинная царапина, ссадины шахты и приклада, кончики флажков), микрорельеф царапин и забоин, следы
# ключа на шлицах.
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
# оттенок материала (пункт 2 v3): полимер чуть тёплый, анодирование холодное, фосфат серо-зелёный; (цвет, непрозрачность)
TINT = {
    "poly": ((0.125, 0.112, 0.098), 0.35),
    "alu": ((0.090, 0.097, 0.112), 0.35),
    "steel": ((0.100, 0.106, 0.094), 0.30),
    "rubber": ((0.110, 0.102, 0.095), 0.25),
}
# вариации цвета (владелец: «тёплое и холодное, светлое и тёмное»): (имя, цвет, период мм, поворот, непрозрачность)
VARIATIONS = (
    ("тёплое светлое", (0.20, 0.18, 0.15), 110.0, 0.0, 0.28),
    ("холодное тёмное", (0.060, 0.065, 0.078), 150.0, 1.3, 0.28),
    ("холодное светлое", (0.19, 0.20, 0.215), 45.0, 2.1, 0.16),
    ("тёплое тёмное", (0.075, 0.060, 0.045), 30.0, 0.7, 0.18),
)
DUST = (0.40, 0.39, 0.37)          # городская серая пыль на чёрном
GRIME = (0.22, 0.205, 0.18)        # грязь у крепежа — серо-бурая
PAINT = (0.72, 0.72, 0.70)         # белая краска надписей (не свежая)
PAINT_EMBLEM = (0.56, 0.56, 0.55)  # знак — серее надписей
WARM = (0.15, 0.14, 0.125)         # базовый тон чуть светлее и теплее (v2, пункт 10: «совсем чуть-чуть»)
H_SINK = 0.4975                    # стёртое и царапины — чуть ниже основы (основа заводской — 0.5)
# периоды узоров, мм
P_DUST_PATCH = 60.0
P_SCRATCH = 80.0
P_SPARSE = 260.0                   # крупное «где-то есть, где-то нет» для царапин и отпечатков
P_PAINT_WEAR = 25.0
GRUNGE_TILES = 20                  # гранж генераторов: плиток на сцену (~55 мм)
SCR = {"invert": 0, "balance": 0.36, "contrast": 0.55}    # grunge_scratches_fine без серого фона (ВСС-М, 25.10)
SMUDGE = "grunge_wipe_smudgy_soft/grunge_wipe_smudgy_soft"
# детали стали по местам владельца
CHARGING = ["ChargingHandle_Steel__small_steel_low", "ChargingSlider_Steel__small_steel_low"]
MAG_RELEASE = ["MagReleaseL_Steel__polymer_small_low", "MagReleaseR_Steel__polymer_small_low"]
BOLT_CATCH = ["BoltCatch_Steel__small_steel_low"]
LEVERS = ["SafetyL_Steel__small_steel_low", "SafetyR_Steel__small_steel_low", "SelectorL_Steel__small_steel_low",
          "SelectorR_Steel__small_steel_low"]
SCREWS = {"Steel": ["Receiver_Steel__small_steel_low"], "Stock": ["Receiver_Stock__small_steel_low",
                                                                   "Stock_Stock__small_steel_low"]}
BOLT = ["Bolt_Steel__barrel_bolt_low"]


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


def _zone(layer, setname, name, blend=None, white=False):
    """Маска места (wear_zones.py) в маске слоя: первой — как есть (white — поверх белой маски), поверх — режимом
    blend (Multiply — ограничить рисунок местом, Subtract — вычесть место). Нет файла — False."""
    path = f"{ZONES}/{setname}_{name}.png"
    if not os.path.exists(path):
        return False
    if not layer.has_mask():
        layer.add_mask(L.MaskBackground.White if white else L.MaskBackground.Black)
    top = _last_mask(layer)
    pos = L.InsertPosition.above_node(top) if top else L.InsertPosition.inside_node(layer, L.NodeStack.Mask)
    m = L.insert_fill(pos)
    m.set_source(None, sp_finish._bitmap(path))
    m.set_projection_mode(L.ProjectionMode.UV)
    if blend is not None:
        m.set_blending_mode(blend)
    return True


def _edge_wear(layer, level, contrast=0.85, hard=True, grunge=0.65):
    g = mask_generator(layer, "mg_metal_edge_wear/mg_metal_edge_wear", above=_last_mask(layer))
    _set_params(g.get_source(), {"Use_Triplanar": 1, "Wear_Level": level, "Wear_Contrast": contrast,
                                 "Grunge_Amount": grunge, "grunge_scale": GRUNGE_TILES,
                                 "Ambient_Occlusion_Masking": 0.6})
    if hard:
        # металл — жёсткой маской: при неполной непрозрачности металличность выходила 0.15–0.5 (самопроверка v1)
        sp_finish._mfilter(g, "histogram_scan", {"Position": 0.5, "Contrast": 0.9})
    return g


def _rough(lay, delta):
    """Шероховатость слоя — поправкой: меньше нуля — глаже (вычитание), больше — матовее (прибавка)."""
    lay.set_blending_mode(L.BlendingMode.Subtract if delta < 0 else L.BlendingMode.LinearDodge, CH.SpecularRoughness)


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
    body = [m for c, v in cls.items() if c != "round" for m in v]
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

    def has(zone):
        """Есть ли маска места у набора: слой без неё лёг бы на весь набор (v3, проба 1: «кольца» на всей стали)."""
        return os.path.exists(f"{ZONES}/{setname}_{zone}.png")

    # 1. оттенки материалов и вариации цвета — тёплое и холодное, светлое и тёмное (v3, пункты 2 и владельца)
    lay = add("тон — чуть светлее и теплее", color=WARM)
    sp_lib.lop(lay, 0.18)
    only_meshes(lay, allm)
    for c, names in cls.items():
        if c in TINT:
            col, op = TINT[c]
            lay = add(f"оттенок материала — {c}", color=col)
            sp_lib.lop(lay, op)
            only_meshes(lay, names)
    for nm, col, period, rot, op in VARIATIONS:
        lay = add(f"цвет — {nm}", color=col)
        mask_proc(lay, SMUDGE, {"Balance": 0.5, "Contrast": 0.35}, scale=scene / period, rot=rot)
        if period < 60.0:
            _sparse(lay, scene, period=220.0, rot=rot + 0.5)
        sp_lib.lop(lay, op)
        only_meshes(lay, allm)
    # крупный градиент по высоте (10–20 см): верх чуть светлее и пыльнее, низ темнее (пункт 6)
    if has("zgrad"):
        _zone(add("градиент — верх светлее", color=(0.19, 0.185, 0.175)), setname, "zgrad")
        sp_lib.lop(st["last"], 0.16)
        only_meshes(st["last"], body)
        lay = add("градиент — низ темнее", color=(0.060, 0.060, 0.066))
        _zone(lay, setname, "zgrad", L.BlendingMode.Subtract, white=True)
        sp_lib.lop(lay, 0.14)
        only_meshes(lay, body)
    log.append("цвет")

    # 2. блеск разводами (пункт 1): протёрто тряпкой — глаже полосами, матовее пятнами; редко
    lay = add("блеск — протёрто тряпкой", rough=0.07)
    _rough(lay, -1)
    mask_proc(lay, "grunge_wipe_directional_heavy/grunge_wipe_directional_heavy", scale=scene / 70.0, rot=0.3)
    _sparse(lay, scene, period=200.0, rot=1.1)
    sp_lib.lop(lay, 0.8)
    only_meshes(lay, body)
    lay = add("блеск — матовее пятнами", rough=0.07)
    _rough(lay, 1)
    mask_proc(lay, SMUDGE, {"Balance": 0.45, "Contrast": 0.45}, scale=scene / 50.0, rot=0.5)
    sp_lib.lop(lay, 0.7)
    only_meshes(lay, body)
    log.append("блеск")

    # 3. краска маркировки — неровной толщины, местами осыпалась; знак серее и вытертее (пункт 7)
    for kind, col, wear in (("text", PAINT, 0.65), ("emblem", PAINT_EMBLEM, 0.85)):
        path = f"{MASKS}/{setname}_white_{kind}.png"
        if not os.path.exists(path):
            continue
        lay = add(f"краска в гравировке — {'надписи' if kind == 'text' else 'знак'}", color=col, rough=0.75, metal=0.0)
        sp_finish.bitmap_mask(lay, path)
        mask_proc(lay, SMUDGE, scale=scene / P_PAINT_WEAR, blend=L.BlendingMode.Subtract, opacity=wear,
                  above=_last_mask(lay))
        mask_proc(lay, "grunge_scratches_fine/grunge_scratches_fine", SCR, scale=scene / 12.0,
                  blend=L.BlendingMode.Subtract, opacity=0.5, above=_last_mask(lay))
        # толщина краски неровная — тон пятнами
        tone = add(f"краска — неровный тон ({kind})", color=(0.62, 0.61, 0.58))
        sp_finish.bitmap_mask(tone, path)
        mask_proc(tone, SMUDGE, scale=scene / 8.0, blend=L.BlendingMode.Multiply, above=_last_mask(tone))
        sp_lib.lop(tone, 0.5)
    log.append("краска")

    # 4. пыль и грязь с причиной (пункт 3)
    lay = add("пыль в углублениях (Dirt)", color=DUST, rough=0.92)
    g = mask_generator(lay, "mg_dirt/mg_dirt")
    _set_params(g.get_source(), {"Use_Triplanar": 1, "dirt_level": 0.22, "dirt_contrast": 0.7, "grunge_amount": 0.55,
                                 "Grunge_Scale": GRUNGE_TILES, "edges_masking": 0.7})
    for z in ("hand_tone", "grip"):          # где трут руками — пыли меньше
        _zone(lay, setname, z, L.BlendingMode.Subtract)
    sp_lib.lop(lay, 0.6)
    only_meshes(lay, body)
    if has("up"):
        _zone(add("налёт на верхних гранях", color=(0.33, 0.32, 0.30), rough=0.86), setname, "up")
        mask_proc(st["last"], SMUDGE, {"Balance": 0.5, "Contrast": 0.4}, scale=scene / 35.0, rot=0.2,
                  blend=L.BlendingMode.Multiply, above=_last_mask(st["last"]))
        for z in ("hand_tone", "grip", "rails"):
            _zone(st["last"], setname, z, L.BlendingMode.Subtract)
        sp_lib.lop(st["last"], 0.22)
        only_meshes(st["last"], body)
    if has("rings"):
        _zone(add("грязь у крепежа — кольца", color=GRIME, rough=0.9), setname, "rings")
        sp_lib.lop(st["last"], 0.6)
    lay = add("пятна пыли", color=(0.31, 0.30, 0.28), rough=0.82)
    mask_proc(lay, SMUDGE, {"Balance": 0.45, "Contrast": 0.4}, scale=scene / P_DUST_PATCH)
    sp_lib.lop(lay, 0.12)
    only_meshes(lay, body)
    if setname == "Lower":
        lay = add("пыль в насечке рукояти", color=DUST, rough=0.92)
        g = mask_generator(lay, "mg_dirt/mg_dirt")
        _set_params(g.get_source(), {"Use_Triplanar": 1, "dirt_level": 0.5, "dirt_contrast": 0.6,
                                     "grunge_amount": 0.4, "Grunge_Scale": GRUNGE_TILES * 2, "edges_masking": 0.5})
        _zone(lay, setname, "grip", L.BlendingMode.Multiply)
        sp_lib.lop(lay, 0.45)
    if "rubber" in cls:
        lay = add("пыль в рёбрах затыльника", color=DUST, rough=0.95)
        g = mask_generator(lay, "mg_dirt/mg_dirt")
        _set_params(g.get_source(), {"Use_Triplanar": 1, "dirt_level": 0.5, "dirt_contrast": 0.6,
                                     "grunge_amount": 0.4, "Grunge_Scale": GRUNGE_TILES * 2})
        sp_lib.lop(lay, 0.5)
        only_meshes(lay, cls["rubber"])
    log.append("пыль")

    # 5. общий износ кромок — только полимеру и резине, слабо и местами (v2 пункт 10); металл — только в местах
    # владельца; царапины — только по корпусу верха и полимеру, редкие, с рельефом (пункт 9)
    for c, names in cls.items():
        if c in ("round", "steel") or (c == "alu" and setname != "Upper"):
            continue
        col, rough, metal = BARE[c]
        if c in ("poly", "rubber"):
            lay = add(f"кромки — {c}, редко", color=col, rough=rough, metal=metal)
            _edge_wear(lay, 0.07, hard=False)
            _sparse(lay, scene, period=180.0, rot=0.6)
            only_meshes(lay, names)
        if c in ("alu", "poly"):
            lay = add(f"царапины — {c}, редкие", color=col, rough=rough, metal=metal, height=H_SINK)
            mf = mask_proc(lay, "grunge_scratches_fine/grunge_scratches_fine", SCR, scale=scene / P_SCRATCH)
            sp_finish._mfilter(mf, "histogram_scan", {"Position": 0.03, "Contrast": 0.9})
            _sparse(lay, scene, period=200.0)
            if has_rails:
                _zone(lay, setname, "rails", L.BlendingMode.Subtract)
            sp_lib.lop(lay, 0.4 if metal else 0.3)
            only_meshes(lay, names)
        if c == "alu":
            # забоины на кромках — только рельефом, редко (пункт 9)
            lay = add("забоины на кромках — рельеф", height=0.497)
            _edge_wear(lay, 0.05, grunge=0.9)
            _sparse(lay, scene, period=120.0, rot=0.2)
            if has_rails:
                _zone(lay, setname, "rails", L.BlendingMode.Subtract)
            only_meshes(lay, names)
    log.append("кромки редко")

    # 6. места владельца — корпус (верх): v2 + живее стёртое (пункт 4)
    if setname == "Upper":
        a_col, a_rough, a_metal = BARE["alu"]

        def worn(name, zone, level, grunge=0.65, scr=False):
            """Стёртое до алюминия в месте zone: основа, тёмные мазки внутри, тонкий тёмный ободок покрытия, рельефом
            чуть ниже. Генератор с теми же числами даёт ту же маску — мазки и ободок ложатся точно по стёртому."""
            lay = add(f"{name} — до металла", color=a_col, rough=a_rough, metal=a_metal, height=H_SINK)
            _edge_wear(lay, level, grunge=grunge)
            _zone(lay, setname, zone, L.BlendingMode.Multiply)
            lay = add(f"{name} — тёмные мазки по металлу", color=(0.36, 0.36, 0.37), rough=0.45, metal=1.0)
            _edge_wear(lay, level, grunge=grunge)
            _zone(lay, setname, zone, L.BlendingMode.Multiply)
            mask_proc(lay, SMUDGE, {"Balance": 0.45, "Contrast": 0.5}, scale=scene / 10.0,
                      blend=L.BlendingMode.Multiply, above=_last_mask(lay))
            sp_lib.lop(lay, 0.7)
            lay = add(f"{name} — ободок покрытия", color=(0.05, 0.05, 0.055), rough=0.3)
            _edge_wear(lay, level + 0.06, contrast=1.0, hard=False, grunge=grunge)
            g2 = mask_generator(lay, "mg_metal_edge_wear/mg_metal_edge_wear", above=_last_mask(lay))
            _set_params(g2.get_source(), {"Use_Triplanar": 1, "Wear_Level": level, "Wear_Contrast": 1.0,
                                          "Grunge_Amount": grunge, "grunge_scale": GRUNGE_TILES,
                                          "Ambient_Occlusion_Masking": 0.6})
            g2.set_blending_mode(L.BlendingMode.Subtract)
            _zone(lay, setname, zone, L.BlendingMode.Multiply)
            sp_lib.lop(lay, 0.6)

        # v2 п.2: три участка на верхней планке (рвано, не все зубья)
        # алюминий на зубьях — темнее голого (0.56 против 0.70) и уже: белые рамки на каждом зубе спорили с корпусом
        lay = add("планка — три участка износа", color=(0.56, 0.56, 0.57), rough=0.36, metal=a_metal, height=H_SINK)
        g = mask_generator(lay, "mg_metal_edge_wear/mg_metal_edge_wear")
        _set_params(g.get_source(), {"Use_Triplanar": 1, "Wear_Level": 0.26, "Wear_Contrast": 0.7, "Grunge_Amount": 0.9,
                                     "grunge_scale": GRUNGE_TILES * 2, "Ambient_Occlusion_Masking": 0.6})
        sp_finish._mfilter(g, "histogram_scan", {"Position": 0.5, "Contrast": 0.85})
        _zone(lay, setname, "rail_spots", L.BlendingMode.Multiply)
        _sparse(lay, scene, period=60.0, rot=0.3)
        # v2 п.1: вдоль паза рукоятки заряжания — вытерто глаже и светлее, по ходу
        lay = add("паз рукоятки заряжания — по ходу", color=(0.26, 0.26, 0.26), rough=0.36)
        _zone(lay, setname, "slot")
        sp_lib.lop(lay, 0.85)
        # v2 п.3: передний торец — правое ребро; слева только верхний угол
        worn("передний торец, правое ребро", "front_r", 0.6)
        worn("передний торец, левый верхний угол", "front_tl", 0.45)
        # v2 п.8: задний торец, левое ребро — до металла, как о бетонную стену
        lay = add("задний торец — ссадина о бетон", color=(0.66, 0.66, 0.67), rough=0.42, metal=1.0, height=H_SINK)
        _zone(lay, setname, "rear_scrape")
        sp_finish._mfilter(_last_mask(lay), "histogram_scan", {"Position": 0.55, "Contrast": 0.8})
        lay = add("задний торец — тёмное в ссадине", color=(0.34, 0.34, 0.35), rough=0.5, metal=1.0)
        _zone(lay, setname, "rear_scrape")
        sp_finish._mfilter(_last_mask(lay), "histogram_scan", {"Position": 0.55, "Contrast": 0.8})
        mask_proc(lay, SMUDGE, {"Balance": 0.45, "Contrast": 0.5}, scale=scene / 8.0, blend=L.BlendingMode.Multiply,
                  above=_last_mask(lay))
        sp_lib.lop(lay, 0.6)
        # v2 п.9: бороздки по ходу лепестков переводчика и предохранителя
        lay = add("бороздки по ходу флажков", color=(0.55, 0.55, 0.56), rough=0.3, metal=1.0, height=H_SINK)
        _zone(lay, setname, "arcs")
        sp_finish._mfilter(_last_mask(lay), "histogram_scan", {"Position": 0.5, "Contrast": 0.85})
        # акцент (пункт 8): одна длинная царапина на левом борту
        lay = add("акцент — длинная царапина", color=(0.62, 0.62, 0.63), rough=0.33, metal=1.0, height=0.497)
        _zone(lay, setname, "accent")
        sp_finish._mfilter(_last_mask(lay), "histogram_scan", {"Position": 0.5, "Contrast": 0.8})
        # v2 п.5: цевьё, где держат — светлее тоном и разводы ладони, отпечатки
        lay = add("цевьё — вытерто светлее", color=(0.19, 0.185, 0.175), rough=0.5)
        _zone(lay, setname, "hand_tone")
        sp_lib.lop(lay, 0.55)
        lay = add("цевьё — разводы ладони и отпечатки", color=(0.85, 0.85, 0.85), rough=0.16)
        lay.set_blending_mode(L.BlendingMode.Multiply, CH.BaseColor)
        _rough(lay, -1)
        _zone(lay, setname, "hand_prints")
        # масло и следы работы (пункт 5): плёнка у окна выброса, латунь от гильз
        lay = add("масло у окна выброса", color=(0.80, 0.80, 0.80), rough=0.22)
        lay.set_blending_mode(L.BlendingMode.Multiply, CH.BaseColor)
        _rough(lay, -1)
        _zone(lay, setname, "port_oil")
        sp_lib.lop(lay, 0.7)
        lay = add("латунь от гильз", color=(0.52, 0.40, 0.21), rough=0.38, metal=0.0)
        _zone(lay, setname, "port_brass")
        sp_lib.lop(lay, 0.75)
        log.append("места верха")

    # 6. места владельца — низ (рукоять) и акцент шахты
    if setname == "Lower":
        lay = add("рукоять — глаже и светлее от ладони", color=(0.20, 0.195, 0.185), rough=0.34)
        _zone(lay, setname, "grip")
        sp_lib.lop(lay, 0.75)
        lay = add("акцент — ссадина на углу шахты", color=(0.28, 0.275, 0.265), rough=0.45, height=0.4985)
        _zone(lay, setname, "accent")
        sp_finish._mfilter(_last_mask(lay), "histogram_scan", {"Position": 0.45, "Contrast": 0.8})
        log.append("рукоять")

    if setname == "Stock":
        lay = add("акцент — потёрт угол приклада", color=(0.27, 0.265, 0.255), rough=0.45, height=0.4985)
        _zone(lay, setname, "accent")
        sp_finish._mfilter(_last_mask(lay), "histogram_scan", {"Position": 0.45, "Contrast": 0.8})
        log.append("акцент")

    # 6. места владельца — детали стали; масло затвора, нагар у дула, кончики флажков
    if setname == "Steel":
        s_col, s_rough, s_metal = BARE["steel"]
        p_col, p_rough, _ = BARE["poly"]
        lay = add("рукоятка заряжания — чуть-чуть", color=s_col, rough=s_rough, metal=s_metal)
        _edge_wear(lay, 0.22)
        only_meshes(lay, CHARGING)
        lay = add("сброс магазина — потёрто", color=p_col, rough=p_rough)
        _edge_wear(lay, 0.4, hard=False)
        only_meshes(lay, MAG_RELEASE)
        lay = add("сброс магазина — отпечатки", color=(0.85, 0.85, 0.85), rough=0.15)
        lay.set_blending_mode(L.BlendingMode.Multiply, CH.BaseColor)
        _rough(lay, -1)
        mask_proc(lay, "grunge_fingerprints_dirty/grunge_fingerprints_dirty", scale=scene / 20.0)
        only_meshes(lay, MAG_RELEASE)
        lay = add("задержка — вытертости", color=s_col, rough=s_rough, metal=s_metal)
        _edge_wear(lay, 0.3)
        only_meshes(lay, BOLT_CATCH)
        lay = add("акцент — кончики флажков", color=s_col, rough=s_rough, metal=s_metal)
        _edge_wear(lay, 0.25)
        only_meshes(lay, LEVERS)
        lay = add("масло на затворе", color=(0.85, 0.85, 0.85), rough=0.2)
        lay.set_blending_mode(L.BlendingMode.Multiply, CH.BaseColor)
        _rough(lay, -1)
        mask_proc(lay, SMUDGE, {"Balance": 0.5, "Contrast": 0.4}, scale=scene / 25.0)
        sp_lib.lop(lay, 0.6)
        only_meshes(lay, BOLT)
        if has("muzzle"):
            _zone(add("нагар у дула", color=(0.035, 0.033, 0.030), rough=0.75, metal=0.0), setname, "muzzle")
            sp_lib.lop(st["last"], 0.75)
        log.append("детали")
    if setname in SCREWS:
        s_col, s_rough, s_metal = BARE["steel"]
        lay = add("следы ключа на шлицах", color=s_col, rough=s_rough, metal=s_metal)
        _edge_wear(lay, 0.16, grunge=0.85)
        only_meshes(lay, SCREWS[setname])
        log.append("шлицы")
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
