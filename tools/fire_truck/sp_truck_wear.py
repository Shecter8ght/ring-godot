"""Пожарная АЦ в Substance Painter, этап 2 — износ «2 года брошена» (навык weapon-asset-wear).

История (интервью 2026-11-08, finish-spec.json → wear): 10 лет в пожарной части (сколы, натоптанные ступени, затёртые
ручки и кромки, царапины у отсеков), затем два года на улице под деревьями: выгорание эмали и пожелтение белой,
разрушенный лак (матовее), пыль и налёт, потёки с кромок, засохшая дорожная грязь снизу, ржавчина по порогам, низу
дверей и кромкам арок, ржавые подтёки, окисленный алюминий, выцветший пластик и резина, мутные стёкла, прошлогодняя
листва в углах и ковром, птичий помёт под насестами, граффити баллончиком, надписи пальцем по пыли и ладони.

Группа «Этап 2 — износ» (Passthrough) — над «Ливреей» и «Этапом 1» того же набора; они не меняются. Места — карты
в развёртке wear_zones.py (по картам геометрии wear_maps.py), рисунок следов — фото CC0 (wear_masks.py: пыль,
разводы, подтёки, царапины, ржавчина, грязь, листва) трёхпроекционно, кромки и углубления — генераторы Painter по
запечённым кривизне и затенённости (место, а не рисунок). Наклейки (листья, помёт, граффити, ладони, надписи) — уже
готовые картинки в развёртке. Каждый след меняет и цвет, и блеск.

    sp_run.py -c "import sys; sys.path.insert(0, r'E:/Games/RING-godot/tools/fire_truck'); import sp_truck_wear as W;
                  print(W.build('body_L'))"
"""
from __future__ import annotations

import importlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
for _p in (HERE, os.path.join(ROOT, "tools", "asset_kit", "finish"), os.path.join(ROOT, "tools", "vss_m_v8")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import substance_painter.layerstack as L  # noqa: E402
import substance_painter.textureset as TS  # noqa: E402

import sp_finish  # noqa: E402
import sp_lib  # noqa: E402
import tex_sets as T  # noqa: E402
from sp_lib import CH  # noqa: E402

importlib.reload(T)
GROUP = "Этап 2 — износ"
WEAR = T.WORK + "/wear"
ZON = WEAR + "/zones"
DEC = WEAR + "/decals"
MK = WEAR + "/masks"

PAINT = {"paint_red", "paint_white", "signal_yellow"}
STEEL_PAINT = PAINT | {"chassis_black"}
ALU = {"shutter_alu", "sheet_alu", "fixtures"}
PLASTIC = {"plastic_black", "interior_plastic"}
RUBBER = {"tyre", "rubber", "hose_red"}
FABRIC = {"seat_fabric", "headliner", "straps"}
GLASS = {"glass_auto", "mirror", "lens_blue", "lens_amber", "lens_red", "lens_clear"}
METAL = {"chrome", "steel_bright"}
SOLID = STEEL_PAINT | ALU | PLASTIC | RUBBER | METAL
INSIDE = {"cab_interior", "crew_interior", "lockers"}
NO_RUST = {"shutters", "lockers"}       # рольставни и облицовка отсеков — алюминий (крашеный): не ржавеет, белеет

# сила следов — одно место правки (доля непрозрачности слоя)
K = {"fade_red": 0.62, "fade_white": 0.55, "fade_yellow": 0.5, "alu_ox": 0.7, "plastic_fade": 0.55, "rust_sill": 1.0,
     "rust_edge": 0.9, "chassis_rust": 0.85, "chips": 1.0, "streak_dirt": 0.55, "rust_runs": 0.7, "mud": 1.0,
     "mud_dust": 0.55, "leafmat": 1.0, "dust": 0.85, "film": 0.5, "scratches": 0.45, "glass_dirt": 0.75,
     "worn_steps": 0.8}


# доля рельефа фото-слоёв: высота снимка растянута на 0…1 и кладётся уровнем — при 0,5 шасси вышло «корой»
# (самопроверка 2026-11-08: среднее z нормали 0,59)
HEIGHT = {"rust": 0.12, "mud": 0.12, "leafmat": 0.2}


# ------------------------------------------------------------------------------------------------ помощники стека
def _meshes(set_name: str, slots: set) -> list:
    import sp_truck
    proj = sp_truck._proj_of(set_name)
    inf = sp_truck.info()[proj]["sets"][set_name]
    have = set(sp_truck.meshes_of(set_name))
    return [m for m, s in inf.items() if s in slots and (not have or m in have)]


def _scope(layer, meshes, all_meshes):
    if len(meshes) < len(all_meshes):
        sp_lib.only_meshes(layer, meshes)


def _layer(name, pos, color=None, cmode=L.BlendingMode.Normal, cop=1.0, rough=None, rmode=None, rop=1.0, metal=None,
           mop=None, height=None, hop=1.0):
    """Слой износа: цвет режимом наложения, блеск — числом (Normal) или прибавкой (rmode «add», знак — направление)."""
    ch = {}
    if color is not None:
        ch["color"] = color
    if rough is not None:
        ch["rough"] = abs(rough)
    if metal is not None:
        ch["metal"] = metal
    if height is not None:
        ch["height"] = height
    f = sp_lib.fill(name, pos, **ch)
    if color is not None:
        f.set_blending_mode(cmode, CH.BaseColor)
        f.set_opacity(cop, CH.BaseColor)
    if rough is not None:
        if rmode == "add":
            f.set_blending_mode(L.BlendingMode.Subtract if rough < 0 else L.BlendingMode.LinearDodge,
                                CH.SpecularRoughness)
        f.set_opacity(rop, CH.SpecularRoughness)
    if metal is not None:
        f.set_opacity(cop if mop is None else mop, CH.BaseMetalness)
    if height is not None:
        f.set_opacity(hop, CH.Height)
    return f


def _bitmap(path):
    return sp_finish._bitmap(path.replace("\\", "/"))


def _tri_source(f, channel_key, path, scale, rot=0.0):
    f.set_source(sp_lib.CHAN[channel_key], _bitmap(path))
    sp_lib.triplanar(f, scale, rot)


def _mfill(layer, path, above=None, blend=None, opacity=1.0, tri=None, rot=0.0):
    """Карта в маске слоя: по развёртке (tri=None) или трёхпроекционно с масштабом tri; blend — смешение с тем, что
    ниже в маске."""
    if not layer.has_mask():
        layer.add_mask(L.MaskBackground.Black)
    pos = L.InsertPosition.above_node(above) if above else L.InsertPosition.inside_node(layer, L.NodeStack.Mask)
    m = L.insert_fill(pos)
    m.set_source(None, _bitmap(path))
    if tri is None:
        m.set_projection_mode(L.ProjectionMode.UV)
    else:
        sp_lib.triplanar(m, tri, rot)
    if blend is not None:
        m.set_blending_mode(blend)
    m.set_opacity(opacity)
    return m


def _mgen(layer, gen, params, above=None, blend=None, opacity=1.0):
    g = sp_lib.mask_generator(layer, gen, params, above=above)
    if blend is not None:
        g.set_blending_mode(blend)
    g.set_opacity(opacity)
    return g


def _scan(above, pos, contrast):
    """Порог маски (histogram scan): рисунок фото → чёткие пятна нужной доли."""
    e = L.insert_filter_effect(L.InsertPosition.above_node(above), sp_lib.rid("histogram_scan/histogram_scan", "u:filter"))
    e.get_source().set_parameters({"Position": pos, "Contrast": contrast})
    return e


def _zone(st, key):
    p = f"{ZON}/{st}_{key}.png"
    return p if os.path.exists(p) else None


def _decal(st, key):
    p = f"{DEC}/{st}_{key}.png"
    return p if os.path.exists(p) else None


MUL = L.BlendingMode.Multiply
SUB = L.BlendingMode.Subtract
ADD = L.BlendingMode.LinearDodge


# ------------------------------------------------------------------------------------------------------------ стек
def _new_group(set_name):
    import sp_truck
    st = sp_lib.stack_by_name(sp_truck.theirs(set_name))
    for n in L.get_root_layer_nodes(st):
        if n.get_name() == GROUP:
            L.delete_node(n)
    top = [n for n in L.get_root_layer_nodes(st)][0]
    grp = L.insert_group(L.InsertPosition.above_node(top))
    grp.set_name(GROUP)
    for ch in st.all_channels():
        grp.set_blending_mode(L.BlendingMode.Passthrough, ch)
    return L.InsertPosition.inside_node(grp, L.NodeStack.Substack)


def build(set_name: str):
    import sp_truck
    proj = sp_truck._proj_of(set_name)
    bbox = float(sp_truck.info()[proj]["bbox_mm"])
    allm = _meshes(set_name, set().union(*[PAINT, STEEL_PAINT, ALU, PLASTIC, RUBBER, FABRIC, GLASS, METAL]))
    tri = lambda period_mm: bbox / period_mm  # noqa: E731
    st = set_name
    pos = _new_group(st)
    made = []
    last = [None]

    def add(layer, slots):
        ms = _meshes(st, slots)
        _scope(layer, ms, allm)
        made.append(layer.get_name())
        last[0] = layer
        return L.InsertPosition.above_node(layer)

    def has(slots):
        return bool(_meshes(st, slots))

    def nxt():
        return L.InsertPosition.above_node(last[0]) if last[0] else pos

    inside = st in INSIDE
    sun = st != "lockers"                     # в закрытых отсеках солнца нет — выгорания тоже
    # внутри кабины и отсеков нет погоды: ни потёков, ни дорожной грязи, ни ржавчины порогов, ни листьев и помёта
    z = lambda k: None if inside and k in ("sill", "rust_runs", "streak_dirt", "low", "leafmat") else _zone(st, k)  # noqa: E731
    d = lambda k: None if inside and k in ("graffiti", "leaves", "drops", "drops_etch") else _decal(st, k)  # noqa: E731
    zf = lambda k: _zone(st, k) if sun else None  # noqa: E731

    # 1. выгорание эмали: красная — розовеет и мелеет, белая желтеет, жёлтая бледнеет; лак разрушен — матовее
    for slot, key, col, rgh in (("paint_red", "fade_red", (0.68, 0.30, 0.26), 0.52),
                                ("paint_white", "fade_white", (0.82, 0.79, 0.70), 0.48),
                                ("signal_yellow", "fade_yellow", (0.88, 0.78, 0.48), 0.5)):
        if has({slot}) and zf("fade"):
            lay = _layer(f"Выгорание — {slot}", nxt(), color=col, cop=K[key], rough=rgh, rop=0.85)
            m = _mfill(lay, z("fade"))
            _mfill(lay, f"{MK}/smear.png", above=m, blend=MUL, opacity=0.45, tri=tri(900), rot=0.3)
            add(lay, {slot})
    # 2. окисление алюминия — белёсый налёт пятнами, матовее, металл слабее
    if has(ALU) and z("fade"):
        lay = _layer("Окисление алюминия", nxt(), color=(0.70, 0.70, 0.68), cop=K["alu_ox"], rough=0.62, rop=0.8,
                     metal=0.55, mop=0.6)
        m = _mfill(lay, z("fade"))
        m = _mfill(lay, f"{MK}/dust.png", above=m, blend=MUL, tri=tri(600), rot=0.9)
        _scan(m, 0.45, 0.35)
        add(lay, ALU)
    # 3. выцветание пластика и резины — серее, матовее
    if has(PLASTIC | RUBBER | FABRIC) and zf("fade"):
        lay = _layer("Выцветание пластика, резины, ткани", nxt(), color=(0.36, 0.35, 0.33), cop=K["plastic_fade"],
                     rough=0.15, rmode="add", rop=0.8)
        m = _mfill(lay, z("fade"))
        _mfill(lay, f"{MK}/smear.png", above=m, blend=MUL, opacity=0.5, tri=tri(700), rot=1.2)
        add(lay, PLASTIC | RUBBER | FABRIC)
    # 4. сколы краски (10 лет службы): грунт по кромкам, внутри — ржавая сталь
    if has(PAINT) and z("chips"):
        lay = _layer("Сколы — грунт", nxt(), color=(0.33, 0.31, 0.29), cop=K["chips"], rough=0.72, metal=0.0)
        g = _mgen(lay, "mg_curvature/mg_curvature", {"global_balance": 0.62, "global_contrast": 0.8})
        m = _mfill(lay, z("chips"), above=g, blend=MUL)
        m = _mfill(lay, f"{MK}/dust.png", above=m, blend=MUL, tri=tri(300), rot=1.7)
        _scan(m, 0.72, 0.55)
        add(lay, PAINT)
        lay = _layer("Сколы — ржавая сталь", nxt(), color=(0.22, 0.11, 0.05), cop=K["chips"], rough=0.85, metal=0.0,
                     height=0.47, hop=0.5)
        g = _mgen(lay, "mg_curvature/mg_curvature", {"global_balance": 0.72, "global_contrast": 0.85})
        m = _mfill(lay, z("chips"), above=g, blend=MUL)
        m = _mfill(lay, f"{MK}/dust.png", above=m, blend=MUL, tri=tri(300), rot=1.7)
        _scan(m, 0.76, 0.6)
        add(lay, PAINT)
    # 5. ржавчина: пороги, низ дверей, кромки арок — фото ржавчины (цвет, блеск, рельеф), пятнами
    if has(STEEL_PAINT | METAL) and z("sill") and st not in NO_RUST:
        lay = _layer("Ржавчина — пороги и низ", nxt(), color=(0.3, 0.14, 0.06), rough=0.9, metal=0.0, height=0.5)
        _tri_source(lay, "color", f"{MK}/rust_color.png", tri(450), 0.2)
        _tri_source(lay, "rough", f"{MK}/rust_rough.png", tri(450), 0.2)
        _tri_source(lay, "height", f"{MK}/rust_height.png", tri(450), 0.2)
        lay.set_opacity(HEIGHT["rust"], CH.Height)
        m = _mfill(lay, z("sill"))
        m = _mfill(lay, f"{MK}/rustpatch.png", above=m, blend=MUL, tri=tri(700), rot=0.6)
        _scan(m, 0.55, 0.45)
        add(lay, STEEL_PAINT | METAL)
        # по кромкам и в углах — ржавчина выходит из-под краски
        lay = _layer("Ржавчина — кромки и углы", nxt(), color=(0.3, 0.14, 0.06), cop=K["rust_edge"], rough=0.88,
                     metal=0.0, height=0.5)
        _tri_source(lay, "color", f"{MK}/rust_color.png", tri(450), 1.1)
        _tri_source(lay, "rough", f"{MK}/rust_rough.png", tri(450), 1.1)
        _tri_source(lay, "height", f"{MK}/rust_height.png", tri(450), 1.1)
        lay.set_opacity(HEIGHT["rust"], CH.Height)
        g = _mgen(lay, "mg_dirt/mg_dirt", {"dirt_level": 0.4, "dirt_contrast": 0.6, "grunge_amount": 0.0})
        m = _mfill(lay, z("sill"), above=g, blend=MUL)
        m = _mfill(lay, f"{MK}/rustpatch.png", above=m, blend=MUL, tri=tri(400), rot=2.1)
        _scan(m, 0.6, 0.5)
        add(lay, STEEL_PAINT | METAL)
    # 6. шасси — ржавчина сильнее: углы, кромки, пятна по всему
    if has({"chassis_black"}) and not inside:
        lay = _layer("Ржавчина шасси", nxt(), color=(0.3, 0.14, 0.06), cop=K["chassis_rust"], rough=0.9, metal=0.0,
                     height=0.5)
        _tri_source(lay, "color", f"{MK}/rust_color.png", tri(500), 0.7)
        _tri_source(lay, "rough", f"{MK}/rust_rough.png", tri(500), 0.7)
        _tri_source(lay, "height", f"{MK}/rust_height.png", tri(500), 0.7)
        lay.set_opacity(HEIGHT["rust"], CH.Height)
        g = _mgen(lay, "mg_dirt/mg_dirt", {"dirt_level": 0.55, "dirt_contrast": 0.45, "grunge_amount": 0.0})
        m = _mfill(lay, f"{MK}/rustpatch.png", above=g, blend=L.BlendingMode.Lighten, tri=tri(800), rot=0.3,
                   opacity=0.8)
        _scan(m, 0.5, 0.4)
        add(lay, {"chassis_black"})
    # 7. ржавые подтёки по бортам — снизу и от кромок
    if has(PAINT | ALU) and z("rust_runs"):
        lay = _layer("Ржавые подтёки", nxt(), color=(0.36, 0.17, 0.07), cop=K["rust_runs"], rough=0.15, rmode="add",
                     rop=0.6)
        m = _mfill(lay, z("rust_runs"))
        _scan(m, 0.42, 0.35)
        add(lay, PAINT | ALU)
    # 8. потёки грязи с кромок крыши, окон и панелей
    if has(SOLID) and z("streak_dirt"):
        lay = _layer("Потёки грязи", nxt(), color=(0.24, 0.21, 0.17), cop=K["streak_dirt"], rough=0.2, rmode="add",
                     rop=0.7)
        _mfill(lay, z("streak_dirt"))
        add(lay, SOLID)
    # 9. граффити баллончиком — до пыли (пыль за два года легла и на него)
    if d("graffiti"):
        lay = _layer("Граффити", nxt(), color=(0.5, 0.5, 0.5), rough=0.5, metal=0.0)
        lay.set_source(CH.BaseColor, _bitmap(d("graffiti")))
        lay.set_source(CH.BaseMetalness, _bitmap(d("graffiti_metal")))
        lay.set_projection_mode(L.ProjectionMode.UV)
        _mfill(lay, d("graffiti_a"))
        add(lay, SOLID)
    # 10. засохшая дорожная грязь: снизу, у арок, брызги назад — фото засохшей грязи, комьями
    if has(SOLID) and z("low"):
        lay = _layer("Засохшая грязь", nxt(), color=(0.4, 0.33, 0.25), rough=0.88, metal=0.0, height=0.5)
        _tri_source(lay, "color", f"{MK}/mud_color.png", tri(600), 0.4)
        _tri_source(lay, "rough", f"{MK}/mud_rough.png", tri(600), 0.4)
        _tri_source(lay, "height", f"{MK}/mud_height.png", tri(600), 0.4)
        lay.set_opacity(HEIGHT["mud"], CH.Height)
        m = _mfill(lay, z("low"))
        m = _mfill(lay, f"{MK}/mud_clumps.png", above=m, blend=MUL, tri=tri(500), rot=0.8)
        _scan(m, 0.42, 0.45)
        add(lay, SOLID)
        lay = _layer("Пыльная корка грязи", nxt(), color=(0.52, 0.46, 0.37), cop=K["mud_dust"], rough=0.9, rop=0.8,
                     metal=0.0)
        m = _mfill(lay, z("low"))
        _mfill(lay, f"{MK}/dust.png", above=m, blend=MUL, tri=tri(450), rot=2.4)
        add(lay, SOLID)
    # 11. прелая листва ковром в углах — фото слоя сухой листвы
    if z("leafmat"):
        lay = _layer("Прелая листва", nxt(), color=(0.25, 0.18, 0.11), rough=0.8, metal=0.0, height=0.55)
        _tri_source(lay, "color", f"{MK}/leafmat_color.png", tri(700), 0.0)
        _tri_source(lay, "rough", f"{MK}/leafmat_rough.png", tri(700), 0.0)
        _tri_source(lay, "height", f"{MK}/leafmat_height.png", tri(700), 0.0)
        lay.set_opacity(HEIGHT["leafmat"], CH.Height)
        m = _mfill(lay, z("leafmat"))
        m = _mfill(lay, f"{MK}/leafmat_height.png", above=m, blend=MUL, tri=tri(700))
        _scan(m, 0.35, 0.4)
        add(lay, SOLID)
    # 11б. пятна от прелой листвы: дубильные бурые разводы вокруг ковров и под листьями на горизонталях
    if z("leafmat") and has(SOLID):
        lay = _layer("Пятна от прелой листвы", nxt(), color=(0.30, 0.24, 0.17), cop=0.55, rough=0.12, rmode="add",
                     rop=0.6)
        m = _mfill(lay, z("leafmat"))
        blur = L.insert_filter_effect(L.InsertPosition.above_node(m), sp_lib.rid("blur/blur", "u:filter"))
        blur.get_source().set_parameters({"intensity": 0.35})
        _mfill(lay, f"{MK}/dust.png", above=m, blend=MUL, tri=tri(500), rot=1.9, opacity=0.6)
        add(lay, SOLID)
    # 12. пыль: горизонтали, углубления; стёрта пальцем и ладонью, валик по краю надписи
    if z("dust"):
        lay = _layer("Пыль", nxt(), color=(0.58, 0.54, 0.47), cop=K["dust"], rough=0.92, rop=K["dust"], metal=0.0,
                     mop=K["dust"])
        m = _mfill(lay, z("dust"))
        m = _mfill(lay, f"{MK}/dust.png", above=m, blend=MUL, tri=tri(400), rot=0.5, opacity=0.55)
        g = _mgen(lay, "mg_dirt/mg_dirt", {"dirt_level": 0.3, "dirt_contrast": 0.5, "grunge_amount": 0.0}, above=m,
                  blend=L.BlendingMode.Screen, opacity=0.5)
        m = g
        if d("ridge"):
            m = _mfill(lay, d("ridge"), above=m, blend=ADD, opacity=0.5)
        if d("clean"):
            _mfill(lay, d("clean"), above=m, blend=SUB)
        add(lay, SOLID | FABRIC)
    # 13. налёт — общий тусклый слой немытой два года машины (матовее и чуть серее), тоже стёрт надписями
    if z("film") and has(SOLID):
        # налёт под деревьями: серый с зеленцой (пыльца, водоросли), матовее
        lay = _layer("Налёт", nxt(), color=(0.43, 0.43, 0.37), cop=K["film"], rough=0.18, rmode="add", rop=0.9)
        m = _mfill(lay, z("film"))
        m = _mfill(lay, f"{MK}/smear.png", above=m, blend=MUL, tri=tri(800), rot=1.6, opacity=0.6)
        if d("clean"):
            _mfill(lay, d("clean"), above=m, blend=SUB)
        add(lay, SOLID)
    # 14. царапины службы — у ручек, ступеней, передка; светлее и матовее
    if has(PAINT | ALU | PLASTIC) and z("service"):
        lay = _layer("Царапины", nxt(), color=(0.82, 0.82, 0.82), cmode=L.BlendingMode.Screen, cop=K["scratches"] * 0.5,
                     rough=0.1, rmode="add", rop=K["scratches"])
        m = _mfill(lay, f"{MK}/scratches.png", tri=tri(350), rot=0.7)
        _mfill(lay, z("service"), above=m, blend=MUL)
        add(lay, PAINT | ALU | PLASTIC)
    # 15. натоптано и затёрто: ступени, поручни, ручки — грязь сапог и металл до блеска на кромках
    if z("traffic"):
        lay = _layer("Натоптано", nxt(), color=(0.30, 0.26, 0.21), cop=K["worn_steps"], rough=0.85, rop=0.7, metal=0.0,
                     mop=0.6)
        m = _mfill(lay, z("traffic"))
        m = _mfill(lay, f"{MK}/mud_clumps.png", above=m, blend=MUL, tri=tri(300), rot=1.3)
        _mfill(lay, z("up"), above=m, blend=MUL)
        add(lay, SOLID)
        lay = _layer("Затёрто до металла", nxt(), color=(0.55, 0.55, 0.54), rough=0.38, metal=1.0)
        g = _mgen(lay, "mg_curvature/mg_curvature", {"global_balance": 0.7, "global_contrast": 0.85})
        _mfill(lay, z("traffic"), above=g, blend=MUL)
        add(lay, PAINT | ALU | {"chassis_black"})
    # 16. стёкла и линзы: ровная дымка пыли и налёта, пятна гуще, отвесные дорожки дождя; надписи пальцем её стёрли
    if has(GLASS) and z("film"):
        lay = _layer("Грязное стекло", nxt(), color=(0.50, 0.47, 0.42), cop=K["glass_dirt"], rough=0.6, rop=0.9,
                     metal=0.0)
        m = _mfill(lay, z("film"))
        m = _mfill(lay, f"{MK}/dust.png", above=m, blend=MUL, tri=tri(500), rot=0.2, opacity=0.4)
        if z("streak_dirt"):
            m = _mfill(lay, z("streak_dirt"), above=m, blend=L.BlendingMode.Screen, opacity=0.35)
        if d("clean"):
            _mfill(lay, d("clean"), above=m, blend=SUB)
        add(lay, GLASS)
    # 17. листья и помёт поверх всего
    if d("leaves"):
        lay = _layer("Листья", nxt(), color=(0.3, 0.2, 0.1), rough=0.75, metal=0.0, height=0.53)
        lay.set_source(CH.BaseColor, _bitmap(d("leaves")))
        lay.set_source(CH.SpecularRoughness, _bitmap(d("leaves_rough")))
        lay.set_projection_mode(L.ProjectionMode.UV)
        _mfill(lay, d("leaves_a"))
        add(lay, SOLID)
    if d("drops"):
        if d("drops_etch") and has(PAINT):
            lay = _layer("Эмаль под помётом выедена", nxt(), rough=0.3, rmode="add", rop=1.0, color=(0.9, 0.9, 0.9),
                         cmode=L.BlendingMode.Screen, cop=0.15)
            _mfill(lay, d("drops_etch"))
            add(lay, PAINT)
        lay = _layer("Птичий помёт", nxt(), color=(0.8, 0.8, 0.75), rough=0.85, metal=0.0, height=0.52)
        lay.set_source(CH.BaseColor, _bitmap(d("drops")))
        lay.set_projection_mode(L.ProjectionMode.UV)
        _mfill(lay, d("drops_a"))
        add(lay, SOLID | GLASS)
    if d("hands"):
        # руками в грязных перчатках и ладонями: след темнее и жирнее (пыль стёрта слабо — layer «Пыль»)
        lay = _layer("Ладони — грязный след", nxt(), color=(0.26, 0.23, 0.20), cop=0.45, rough=-0.12, rmode="add",
                     rop=0.6)
        _mfill(lay, d("hands"))
        add(lay, SOLID | GLASS)
    return f"{st}: {len(made)} слоёв износа — " + ", ".join(made)
