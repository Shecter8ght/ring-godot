# АСТЕН-919, текстуры этап 2 — износ в Substance Painter: группа «Этап 2 — износ» над принятой заводской отделкой в
# каждом наборе (заводская группа не меняется, износ выключается целиком). Выполняется через мост:
#   python -X utf8 tools/asten919/sp_run.py -c "print(sp_asten_wear.build())"  → метка _wear_done.txt
# Слои — по причине следа; маска слоя — готовая карта следа в развёртке набора (tools/asten919/wear_marks.py: штампы
# фото-масок владельца по местам контакта). Генераторы Painter только там, где место задаёт сама форма: пыль в
# углублениях (запечённое затенение) и кромки стали (запечённая кривизна) — и те разбиты фото-масками владельца.
# Заказ владельца 2026-11-12: засаленные следы пальцев («градиентный блестящий след») на насечках затвора и на низу
# магазина, потёртости и царапины от шахты на верхней четверти магазина, остальное — на усмотрение, натурально,
# минимум процедурного.
import json
import os

import substance_painter.layerstack as L
import substance_painter.project as P
import substance_painter.textureset as TS

import sp_finish
import sp_lib
import tex_sets as T
from sp_lib import CH, fill, triplanar

GROUP = "Этап 2 — износ"
WEAR = T.WORK + "/wear"
LIB = "E:/Models Blender/Маски_АЛЬФА"
FBX = T.WORK + "/sp/ASTEN919_sp.fbx"
# фото-маски владельца, которыми разбиты пыль и кромки (плиткой, трёхпроекционно); период плитки — мм
DUST_TILE = (LIB + "/03_Пыль_и_частицы/Пыль_редкая_01.png", 70.0)
SPECK_TILE = (LIB + "/03_Пыль_и_частицы/Пыль_плотная_с_частицами_01.png", 55.0)
EDGE_TILE = (LIB + "/10_Сколы_и_потёртости_покрытия/Сколы_с_потёртостями_01.png", 45.0)
# числа слоёв (sRGB, шероховатость). Жир — плёнка: блеск почти зеркальный в середине следа и сходит на нет к краю
# (градиент — из самой фото-маски), цвет чуть темнее и теплее.
# Цвет почти не трогается: с затемнением след читался грязным пятном, а не блеском (первые кадры 12.11).
# Плёнка чуть белёсая (подсохший жир рассеивает свет): прибавка к цвету — иначе под ровным пасмурным небом след не
# виден вовсе, блик нужен только чтобы он «заиграл».
GREASE = {"rough": 0.14, "rop": 0.9, "color": (0.085, 0.085, 0.09), "cop": 0.14}
POLISH = {"rough": -0.17, "color": (0.72, 0.72, 0.72), "cop": 0.20}          # заполировано контактом: глаже, чуть светлее
SCUFF = {"rough": 0.14, "color": (0.30, 0.30, 0.30), "cop": 0.40}            # затёртый полимер: матовее и белёсый
SCRATCH = {"rough": 0.20, "color": (0.42, 0.42, 0.42), "cop": 0.75, "height": 0.004}   # царапина: светлая матовая риска
DUST = {"rough": 0.82, "rop": 0.35, "color": (0.47, 0.44, 0.39), "cop": 0.16}
EDGES = {"rough": -0.08, "color": (0.80, 0.80, 0.80), "cop": 0.20}
# сталь с покрытием, у которой кромки вытираются о кобуру и руки
# покрытие вытерто до стали: светлый металл с атласным блеском; латунь гильз — мазок металла; масло — тёмная
# глянцевая плёнка
BARE = {"color": (0.60, 0.60, 0.61), "rough": 0.37, "metal": 1.0, "cop": 0.9}
BRASS = {"color": (0.70, 0.57, 0.36), "rough": 0.38, "metal": 1.0, "cop": 0.5}
OIL = {"rough": 0.06, "rop": 0.92, "color": (0.50, 0.46, 0.38), "cop": 0.34}
EDGE_MESHES = {"slide": ["Slide__sp", "MOS_Cover_Plate__sp", "Extractor__sp"],
               "parts": ["Slide_Stop__sp", "Slide_Lock__sp"]}
DUST_SETS = ("slide", "frame", "parts", "magazine")


def _scene():
    with open(os.path.splitext(FBX)[0] + "_scene.json", encoding="utf-8") as f:
        return json.load(f)["size_mm"]


def _new_group(setname):
    """Группа износа набора заново (прежняя удаляется) — поверх заводской отделки. Группа — «насквозь» (Passthrough):
    с обычным смешением слои внутри смешивались бы с пустой группой, а не с заводской отделкой."""
    st = sp_lib.stack_by_name(setname)
    for n in L.get_root_layer_nodes(st):
        if n.get_name() == GROUP:
            L.delete_node(n)
    grp = L.insert_group(L.InsertPosition.from_textureset_stack(st))
    grp.set_name(GROUP)
    for ch in st.all_channels():
        grp.set_blending_mode(L.BlendingMode.Passthrough, ch)
    return grp


def _layer(name, pos, rough=None, rmode=None, rop=1.0, color=None, cmode=L.BlendingMode.Normal, cop=1.0, height=None,
           metal=None):
    """Слой следа: блеск — заменой (rmode Normal), вычитанием (отрицательное число) или прибавкой; цвет — наложением;
    высота — вычитанием (вдавлено)."""
    ch = {}
    if rough is not None:
        ch["rough"] = abs(rough)
    if color is not None:
        ch["color"] = color
    if height is not None:
        ch["height"] = height
    if metal is not None:
        ch["metal"] = metal
    f = fill(name, pos, **ch)
    if metal is not None:
        f.set_opacity(cop, CH.Metallic)
    if rough is not None:
        f.set_blending_mode(rmode or (L.BlendingMode.Subtract if rough < 0 else L.BlendingMode.LinearDodge),
                            CH.SpecularRoughness)
        f.set_opacity(rop, CH.SpecularRoughness)
    if color is not None:
        f.set_blending_mode(cmode, CH.BaseColor)
        f.set_opacity(cop, CH.BaseColor)
    if height is not None:
        f.set_blending_mode(L.BlendingMode.Subtract, CH.Height)
    return f


def _tile(above, tile, scene, rot=0.0):
    """Фото-маска плиткой в маске слоя поверх генератора — умножением: рисунок разбивает ровную полосу генератора."""
    path, period = tile
    m = L.insert_fill(L.InsertPosition.above_node(above))
    m.set_source(None, sp_finish._bitmap(path))
    triplanar(m, scene / period, rot)
    m.set_blending_mode(L.BlendingMode.Multiply)
    return m


def build_set(name):
    scene = _scene()
    grp = _new_group(name)
    pos = L.InsertPosition.inside_node(grp, L.NodeStack.Substack)
    log = []
    last = None

    def nxt():
        return pos if last is None else L.InsertPosition.above_node(last)

    def marks(kind, title, **kw):
        nonlocal last
        path = f"{WEAR}/{name}_{kind}.png"
        if not os.path.exists(path):
            return
        lay = _layer(title, nxt(), **kw)
        sp_finish.bitmap_mask(lay, path)
        last = lay
        log.append(kind)

    # снизу вверх: кромки и полировка (само покрытие) → царапины и затёртости → пыль → жир (самое свежее, сверху)
    if name in EDGE_MESHES:
        lay = _layer("Кромки стали — вытерто о кобуру и руки", nxt(), rough=EDGES["rough"], color=EDGES["color"],
                     cmode=L.BlendingMode.SoftLight, cop=EDGES["cop"])
        g = sp_lib.mask_generator(lay, "mg_curvature/mg_curvature",
                                  sp_finish._curv({"global_balance": 0.72, "global_contrast": 0.5}))
        _tile(g, EDGE_TILE, scene)
        sp_lib.only_meshes(lay, EDGE_MESHES[name])
        last = lay
        log.append("edges")
    marks("bare", "Затёртости до металла — мягко, за годы (пальцы, кобура, зуб задержки)", rough=BARE["rough"],
          rmode=L.BlendingMode.Normal, rop=BARE["cop"], color=BARE["color"], cop=BARE["cop"], metal=BARE["metal"])
    marks("polish", "Заполировано контактом (ладонь, ствол о затвор)", rough=POLISH["rough"], color=POLISH["color"],
          cmode=L.BlendingMode.SoftLight, cop=POLISH["cop"])
    marks("scuff", "Затёртости от шахты — матовые пятна трения", rough=SCUFF["rough"], color=SCUFF["color"],
          cmode=L.BlendingMode.LinearDodge, cop=SCUFF["cop"])
    marks("scratch", "Царапины — светлые матовые риски", rough=SCRATCH["rough"], color=SCRATCH["color"],
          cmode=L.BlendingMode.LinearDodge, cop=SCRATCH["cop"], height=SCRATCH["height"])
    marks("brass", "Латунь — мазки от вылетающих гильз", rough=BRASS["rough"], rmode=L.BlendingMode.Normal,
          rop=BRASS["cop"], color=BRASS["color"], cop=BRASS["cop"], metal=BRASS["metal"])
    if name in DUST_SETS:
        lay = _layer("Пыль в углублениях", nxt(), rough=DUST["rough"], rmode=L.BlendingMode.Normal, rop=DUST["rop"],
                     color=DUST["color"], cop=DUST["cop"])
        g = sp_lib.mask_generator(lay, "mg_ambient_occlusion/mg_ambient_occlusion", {"ao_invert": 1})
        _tile(g, DUST_TILE, scene)
        last = lay
        lay = _layer("Пылинки и крупинки", nxt(), rough=0.8, rmode=L.BlendingMode.Normal, rop=0.5,
                     color=(0.62, 0.60, 0.56), cop=0.22)
        g = sp_lib.mask_generator(lay, "mg_ambient_occlusion/mg_ambient_occlusion", {"ao_invert": 1})
        lv = L.insert_levels_effect(L.InsertPosition.above_node(g))      # шире затенения: крупинки и рядом с углом
        _tile(lv, SPECK_TILE, scene, rot=1.1)
        last = lay
        log.append("dust")
    marks("oil", "Масло — подтёки и плёнка у выбрасывателя", rough=OIL["rough"], rmode=L.BlendingMode.Normal,
          rop=OIL["rop"], color=OIL["color"], cmode=L.BlendingMode.Multiply, cop=OIL["cop"])
    marks("grease", "Жир — засаленные следы пальцев (блестящий градиентный след)", rough=GREASE["rough"],
          rmode=L.BlendingMode.Normal, rop=GREASE["rop"], color=GREASE["color"], cmode=L.BlendingMode.LinearDodge,
          cop=GREASE["cop"])
    return f"{name}: " + " ".join(log)


def build(only=None):
    """Группы износа по наборам; итог — _wear_done.txt (когда Painter досчитает), проект сохраняется."""
    log = []
    for t in TS.all_texture_sets():
        if only and t.name() not in only:
            continue
        log.append(build_set(t.name()))

    def done():
        P.save()
        return " | ".join(log)
    sp_lib.when_idle(done, "_wear_done.txt")
    return " | ".join(log)


def show(on=True, only=None):
    """Включить или выключить группу износа (сравнение с заводской отделкой)."""
    out = []
    for t in TS.all_texture_sets():
        if only and t.name() not in only:
            continue
        for n in L.get_root_layer_nodes(t.get_stack()):
            if n.get_name() == GROUP:
                n.set_visible(bool(on))
                out.append(t.name())
    return f"износ {'включён' if on else 'выключен'}: " + " ".join(out)
