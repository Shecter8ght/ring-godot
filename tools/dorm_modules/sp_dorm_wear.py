"""Мусор и оставленный свет общежития, этап 2 — износ (навык weapon-asset-wear) в Substance Painter через мост.
Работает внутри Painter (задание sp_run.py; путь tools/dorm_modules добавляет found_lights_sp.wear).

Над группой «Этап 1 — заводская отделка» (не меняется) кладутся слой «Печать» (этап 1, принят владельцем: макеты
print_designs.py, слой в развёртке print_apply.py --layers) и группа «Этап 2 — износ» (Passthrough — иначе Multiply
и Subtract внутри смешиваются с пустой группой, а не с отделкой: урок AR-15 30.10). Места — карты в развёртке
wear_zones.py (верх — пыль, у пола — грязь, подтёк, сырость, кровь), рисунок — фото-маски CC0 ambientCG
(_asset_src/dorm_clutter/wear/masks, license.txt), кровь — маски владельца 22_Кровь, гранжи и генераторы полки
Painter (в игру — только запечённым). Сила — по возрасту вещи (интервью 2026-10-31): мусор вперемешку, свет — недавно
в руках, мигалка — старая с дороги, грязь как в Таркове. Каждая вариация меняет и цвет, и блеск.
"""
import json
import os

import substance_painter.layerstack as L
import substance_painter.textureset as TS

import sp_lib
import sp_stacks as S
from sp_lib import CH, fill, triplanar

ROOT = "E:/Games/RING-godot/_asset_src"
MK = ROOT + "/dorm_clutter/wear/masks"
GROUP = "Этап 2 — износ"
PRINT = "Печать (этап 1)"

# возраст → (пыль, грязь в углублениях, грязь у пола, потёртости, царапины, выцветание печати)
AGE = {"fresh": (0.30, 0.35, 0.45, 0.45, 0.25, 0.0), "old": (0.80, 0.60, 0.70, 0.65, 0.45, 0.35),
       "used": (0.12, 0.25, 0.30, 0.30, 0.15, 0.0), "road": (0.45, 0.70, 0.85, 0.55, 0.40, 0.25)}
# у света (used) потёртости и царапины слабее: широкие светлые пятна по гладким цилиндрам читались как старая вещь
# (проба 2026-10-31 — фонарь, оправа мигалки, корпус лампы)

# вещь: возраст, кромки (metal_print — печать стёрта до алюминия, plastic, glass, film, steel), отпечатки (сетки или
# «all»), ржавчина (сетки), подтёк, сырость, кровь (рисунок: drops/smear/prints), смола окурков
PROFILES = {
    "clutter_can": dict(age="fresh", edge="metal_print", prints="all", drip=True),
    "clutter_can_dented": dict(age="fresh", edge="metal_print", prints="all", drip=True),
    "clutter_can_crushed": dict(age="old", edge="metal_print"),
    "clutter_bottle_vodka": dict(age="fresh", edge="glass", prints=["Стекло_бутылка_прозрачное"]),
    "clutter_bottle_vodka_worn": dict(age="old", edge="glass", damp=True, blood="drops"),
    "clutter_bottle_beer": dict(age="fresh", edge="glass", prints=["Стекло_бутылка_коричневое"], damp=True,
                                rust=["Пробка_кроненпробка"]),
    "clutter_bottle_broken": dict(age="old", edge="glass"),
    "clutter_butts": dict(age="old", edge="plastic", damp=True, tar=True),
    "clutter_casings": dict(age="old", edge="steel", rust=["Гильза_сталь_лак"]),
    "clutter_bag_full": dict(age="fresh", edge="film"),
    "clutter_bag_lying": dict(age="fresh", edge="film", blood="smear"),
    "clutter_bag_half": dict(age="old", edge="film"),
    "found_flashlight": dict(age="used", edge="plastic", prints="all", blood="prints"),
    "found_headlamp": dict(age="used", edge="plastic", prints=["Налобник_корпус"], sweat=["Налобник_ремень"]),
    "found_chemlight": dict(age="used", edge="plastic", prints="all"),
    "found_lantern": dict(age="used", edge="plastic", prints=["Лампа_корпус", "Лампа_ручка"], rust=["Лампа_ручка"]),
    "found_candles": dict(age="used", edge="steel", rust=["Банка_жесть"]),
    "found_beacon": dict(age="road", edge="plastic"),
}


def _meshes(setname, names):
    """Имена сеток набора по базовым именам (у копий в Painter — суффиксы .001)."""
    ts = next(t for t in TS.all_texture_sets() if t.name() == setname)
    have = ts.all_mesh_names()
    return [m for m in have if m.split(".")[0] in names]


def _scope(layer, setname, names):
    if names and names != "all":
        ms = _meshes(setname, names)
        if ms:
            sp_lib.only_meshes(layer, ms)


def _layer(name, pos, color=None, cmode=L.BlendingMode.Normal, cop=1.0, rough=None, rmode=None, rop=1.0, metal=None):
    """Слой износа: цвет режимом наложения, блеск — числом (Normal) или прибавкой/вычитанием (по знаку rmode)."""
    ch = {}
    if color is not None:
        ch["color"] = color
    if rough is not None:
        ch["rough"] = abs(rough)
    if metal is not None:
        ch["metal"] = metal
    f = fill(name, pos, **ch)
    if color is not None:
        f.set_blending_mode(cmode, CH.BaseColor)
        f.set_opacity(cop, CH.BaseColor)
    if rough is not None:
        if rmode == "add":
            f.set_blending_mode(L.BlendingMode.Subtract if rough < 0 else L.BlendingMode.LinearDodge, CH.SpecularRoughness)
        f.set_opacity(rop, CH.SpecularRoughness)
    if metal is not None:
        f.set_opacity(cop, CH.BaseMetalness)
    return f


def _tri(above, path_or_proc, period_mm, bbox_mm, rot=0.0, blend=L.BlendingMode.Multiply, opacity=1.0, proc=False):
    """Рисунок в маске над узлом (умножением по умолчанию), трёхпроекционно, плитка — period_mm."""
    m = L.insert_fill(L.InsertPosition.above_node(above))
    if proc:
        m.set_source(None, sp_lib.rid(path_or_proc, "u:procedural"))
    else:
        m.set_source(None, S._bitmap(path_or_proc))
    triplanar(m, bbox_mm / period_mm, rot)
    m.set_blending_mode(blend)
    m.set_opacity(opacity)
    return m


def _first_tri(layer, path_or_proc, period_mm, bbox_mm, rot=0.0, proc=False):
    """Рисунок первым в маске слоя."""
    if not layer.has_mask():
        layer.add_mask(L.MaskBackground.Black)
    m = L.insert_fill(L.InsertPosition.inside_node(layer, L.NodeStack.Mask))
    if proc:
        m.set_source(None, sp_lib.rid(path_or_proc, "u:procedural"))
    else:
        m.set_source(None, S._bitmap(path_or_proc))
    triplanar(m, bbox_mm / period_mm, rot)
    return m


def _zone(layer, base, game, zone, above=None, blend=L.BlendingMode.Multiply):
    path = f"{base}/wear/{game}_{zone}.png"
    if not os.path.exists(path):
        return above
    return S._bmask(layer, path, blend=blend if above else None, above=above)


def _print_layer(setname, base, game, pos):
    """Печать этапа 1 слоем: цвет — карта в развёртке, маска — её прозрачность, блеск и металл краски — числом."""
    js = f"{base}/prints/uv/{game}_print.json"
    if not os.path.exists(js):
        return pos
    info = json.loads(open(js, encoding="utf-8").read())
    ch = {"color": (0.5, 0.5, 0.5)}
    if info.get("rough") is not None:
        ch["rough"] = info["rough"]
    if info.get("metal") is not None:
        ch["metal"] = info["metal"]
    if info.get("rough_map"):
        ch["rough"] = 0.9
    if info.get("normal_map"):
        ch["height"] = 0.5  # рельеф отделки под печатью гасится: нормаль печати — целиком (ворс ковра)
    f = fill(PRINT, pos, **ch)
    f.set_source(CH.BaseColor, S._bitmap(f"{base}/prints/uv/{game}_print_color.png"))
    if info.get("rough_map"):
        f.set_source(CH.SpecularRoughness, S._bitmap(f"{base}/prints/uv/{info['rough_map']}"))
    if info.get("normal_map"):
        f.active_channels = set(f.active_channels) | {CH.Normal}
        f.set_source(CH.Normal, S._bitmap(f"{base}/prints/uv/{info['normal_map']}"))
        f.set_blending_mode(L.BlendingMode.Normal, CH.Normal)
    S._uv(f)
    S._bmask(f, f"{base}/prints/uv/{game}_print_alpha.png")
    return L.InsertPosition.above_node(f)


def _new_group(setname, base, game):
    """Заводская отделка — как была; прежние печать и износ удаляются; печать и новая группа — над ней."""
    st = sp_lib.stack_by_name(setname)
    for n in L.get_root_layer_nodes(st):
        if n.get_name() in (GROUP, PRINT):
            L.delete_node(n)
    pos = _print_layer(setname, base, game, L.InsertPosition.from_textureset_stack(st))
    grp = L.insert_group(pos)
    grp.set_name(GROUP)
    for ch in st.all_channels():
        grp.set_blending_mode(L.BlendingMode.Passthrough, ch)
    return L.InsertPosition.inside_node(grp, L.NodeStack.Substack)


def build(setname, base, game, bbox_mm):
    p = PROFILES[game]
    dust, cav, floor, edges, scratch, fade = AGE[p["age"]]
    pos = _new_group(setname, base, game)
    made = []

    # 1. грязь в углублениях — генератор Dirt: темнее и матовее
    l1 = _layer("Грязь в углублениях", pos, color=(0.20, 0.16, 0.12), cop=cav, rough=0.85, rop=cav * 0.8, metal=0.0)
    g = sp_lib.mask_generator(l1, "mg_dirt/mg_dirt", {"dirt_level": 0.35, "dirt_contrast": 0.6, "grunge_amount": 0.4,
                                                      "Grunge_Scale": 5, "Use_Triplanar": 1})
    _tri(g, f"{MK}/grime.png", 60, bbox_mm, rot=0.4, opacity=0.6)
    made.append(l1)
    # 2. пыль сверху — светлая, матовая, гуще в неровностях; металл под пылью не блестит
    l2 = _layer("Пыль сверху", L.InsertPosition.above_node(l1), color=(0.60, 0.57, 0.51), cop=dust, rough=0.9, rop=dust,
                metal=0.0)
    m = _first_tri(l2, "grunge_dust_spread/grunge_dust_spread", 160, bbox_mm, rot=0.7, proc=True)
    m = _tri(m, f"{MK}/dust_specks.png", 40, bbox_mm, rot=1.3, blend=L.BlendingMode.Lighten, opacity=0.6)
    _zone(l2, base, game, "up", above=m)
    made.append(l2)
    # 3. грязь у пола — брызги и разводы снизу
    l3 = _layer("Грязь у пола", L.InsertPosition.above_node(l2), color=(0.17, 0.13, 0.10), cop=floor, rough=0.8,
                rop=floor * 0.8, metal=0.0)
    m = _first_tri(l3, "grunge_dirt_splats/grunge_dirt_splats", 120, bbox_mm, rot=0.2, proc=True)
    _zone(l3, base, game, "floor", above=m)
    made.append(l3)
    last = l3
    # 4. потёртости кромок — по выпуклости, рваным рисунком
    e = p["edge"]
    if e == "metal_print":
        l4 = _layer("Печать стёрта до алюминия", L.InsertPosition.above_node(last), color=(0.74, 0.74, 0.76), cop=edges,
                    rough=0.28, rop=edges, metal=1.0)
    elif e in ("plastic", "steel"):
        l4 = _layer("Потёртости кромок", L.InsertPosition.above_node(last), color=(0.70, 0.70, 0.70),
                    cmode=L.BlendingMode.Screen, cop=edges * 0.35, rough=-0.10, rmode="add", rop=edges)
    else:  # стекло и плёнка — кромки только матовее (затёрты)
        l4 = _layer("Затёртые кромки", L.InsertPosition.above_node(last), rough=0.15, rmode="add", rop=edges)
    # только настоящие кромки: строгий баланс и контраст (при 0,6 / 0,6 гладкие цилиндры давали широкие поля)
    g = sp_lib.mask_generator(l4, "mg_curvature/mg_curvature", {"global_balance": 0.72, "global_contrast": 0.85})
    _tri(g, f"{MK}/chips.png", 50, bbox_mm, rot=0.9)
    made.append(l4)
    last = l4
    # 5. царапины — тонкие, во все стороны: светлее и чуть матовее
    l5 = _layer("Царапины", L.InsertPosition.above_node(last), color=(0.80, 0.80, 0.80), cmode=L.BlendingMode.Screen,
                cop=scratch * 0.3, rough=0.08, rmode="add", rop=scratch)
    _first_tri(l5, f"{MK}/scratches.png", 90, bbox_mm, rot=0.3)
    made.append(l5)
    last = l5
    # 6. отпечатки и жир — где берут руками: глаже и чуть темнее
    if p.get("prints"):
        l6 = _layer("Отпечатки и жир", L.InsertPosition.above_node(last), color=(0.86, 0.86, 0.86),
                    cmode=L.BlendingMode.Multiply, cop=0.5, rough=-0.18, rmode="add", rop=0.8)
        m = _first_tri(l6, f"{MK}/prints_a.png", 55, bbox_mm, rot=0.6)
        _tri(m, f"{MK}/prints_b.png", 45, bbox_mm, rot=2.0, blend=L.BlendingMode.Lighten, opacity=0.6)
        _scope(l6, setname, p["prints"])
        made.append(l6)
        last = l6
    if p.get("sweat"):  # резинка налобника засалена: темнее и глаже пятнами
        l7 = _layer("Засалено", L.InsertPosition.above_node(last), color=(0.75, 0.73, 0.70), cmode=L.BlendingMode.Multiply,
                    cop=0.7, rough=-0.12, rmode="add", rop=0.7)
        _first_tri(l7, f"{MK}/smear_oil.png", 70, bbox_mm, rot=0.2)
        _scope(l7, setname, p["sweat"])
        made.append(l7)
        last = l7
    # 7. подтёк пива от отверстия — янтарный, липкий (глаже)
    if p.get("drip"):
        l8 = _layer("Подтёк пива", L.InsertPosition.above_node(last), color=(0.86, 0.72, 0.42), cmode=L.BlendingMode.Multiply,
                    cop=0.8, rough=-0.12, rmode="add", rop=0.8)
        m = _first_tri(l8, f"{MK}/smear_oil.png", 60, bbox_mm, rot=1.5)
        _zone(l8, base, game, "drip", above=m)
        made.append(l8)
        last = l8
    # 8. пятно сырости с ободком — на бумаге
    if p.get("damp"):
        l9 = _layer("Пятно сырости", L.InsertPosition.above_node(last), color=(0.80, 0.70, 0.52), cmode=L.BlendingMode.Multiply,
                    cop=0.85, rough=0.05, rmode="add", rop=0.6)
        m = _first_tri(l9, f"{MK}/cloudy.png", 80, bbox_mm, rot=0.8)
        _zone(l9, base, game, "damp", above=m)
        made.append(l9)
        last = l9
    # 9. смола на фильтрах окурков — бурая, к торцу
    if p.get("tar"):
        lt = _layer("Смола на фильтрах", L.InsertPosition.above_node(last), color=(0.72, 0.50, 0.28),
                    cmode=L.BlendingMode.Multiply, cop=0.8)
        _first_tri(lt, "grunge_spots/grunge_spots", 30, bbox_mm, rot=0.4, proc=True)
        _scope(lt, setname, ["Окурок_фильтр", "Окурок_ободок"])
        made.append(lt)
        last = lt
    # 10. ржавчина на жести — рыжая, матовая, металл пропадает; по кромкам и в углублениях
    if p.get("rust"):
        lr = _layer("Ржавчина", L.InsertPosition.above_node(last), color=(0.33, 0.15, 0.06), cop=1.0, rough=0.88, rop=1.0,
                    metal=0.0)
        g = sp_lib.mask_generator(lr, "mg_dirt/mg_dirt", {"dirt_level": 0.45, "dirt_contrast": 0.5, "grunge_amount": 0.6,
                                                          "Grunge_Scale": 4, "Use_Triplanar": 1})
        _tri(g, "grunge_rust_fine/grunge_rust_fine", 40, bbox_mm, rot=0.5, proc=True)
        _scope(lr, setname, p["rust"])
        made.append(lr)
        last = lr
    # 11. кровь — старая, бурая, засохшая с лёгким блеском корки
    if p.get("blood"):
        lb = _layer("Кровь", L.InsertPosition.above_node(last), color=(0.16, 0.025, 0.02), cop=1.0, rough=0.45, rop=1.0,
                    metal=0.0)
        pat = {"drops": (f"{MK}/blood_drops.png", 90), "smear": (f"{MK}/blood_smear.png", 260),
               "prints": (f"{MK}/prints_a.png", 50)}[p["blood"]]
        m = _first_tri(lb, pat[0], pat[1], bbox_mm, rot=0.3)
        if p["blood"] != "prints":
            m = _tri(m, f"{MK}/blood_spatter.png", 70, bbox_mm, rot=1.1, blend=L.BlendingMode.Lighten, opacity=0.7)
        _zone(lb, base, game, "blood", above=m)
        made.append(lb)
        last = lb
    # 12. выцветание печати у давних вещей — светлее и тусклее по пятнам
    if fade and os.path.exists(f"{base}/prints/uv/{game}_print_alpha.png"):
        lf = _layer("Печать выцвела", L.InsertPosition.above_node(last), color=(0.86, 0.84, 0.78), cop=fade, rough=0.1,
                    rmode="add", rop=fade)
        m = _first_tri(lf, f"{MK}/cloudy.png", 120, bbox_mm, rot=0.2)
        S._bmask(lf, f"{base}/prints/uv/{game}_print_alpha.png", blend=L.BlendingMode.Multiply, above=m)
        made.append(lf)
    return f"{game}: {len(made)} слоёв износа (возраст {p['age']})"
