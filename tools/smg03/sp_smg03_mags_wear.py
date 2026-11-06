# ИЗЛОМ-45 (wpn_smg_03): магазины v2, этап 2 — износ в Painter (проект sp_smg03_mags.py) поверх принятой заводской
# отделки PL-BLK-SMO. Ориентир владельца (06.11, кадр Road to Vostok: снаряжают магазин AR) — светлые продольные полосы
# в верхней части, где магазин трётся о шахту, по рёбрам и кромкам, рвано; на донышке — потёртые углы и рёбра
# участками. Рисунок задан руками в tools/smg03/wear_mags.py (маски _asset_src/smg03/tex_mags/wear/<набор>_<место>.png),
# здесь — только материал следов: полимер, заглаженный до блеска и светлее, в сердцевинах сильных полос и на кромках
# губок — сталь вкладыша (у Glock полимер поверх стальной коробки), латунь от гильз на губках, донышко — затёрто
# светлее и матовее, царапины.
#
# Общие слои износа корпуса v3 (тон, вариации цвета, блеск разводами, пыль в углублениях) — те же
# (sp_smg03_wear.build_set); генераторные кромки и царапины по всему полимеру сняты — на магазинах износ только
# в местах из списка.
#   … sp_run.py -c "import sys; sys.path.insert(0, r'E:/Games/RING-godot/tools/smg03'); import sp_smg03_mags_wear as W;
#                   print(W.build())"     → _wear_done.txt, проект сохраняется
import os

import substance_painter.layerstack as L

import sp_finish
import sp_lib
import sp_smg03
import sp_smg03_mags
import sp_smg03_wear as SW
from sp_lib import fill, mask_proc

ZONES = sp_smg03_mags.TEX + "/wear"
# генераторные слои общего износа, которых на магазинах нет (износ — только по маскам мест)
DROP = ("кромки — poly, редко", "царапины — poly, редкие")
STEEL = ((0.56, 0.56, 0.57), 0.30, 1.0)          # сталь вкладыша, вытертая
SMUDGE = SW.SMUDGE


def _use():
    sp_smg03_mags.use()
    SW.ZONES = ZONES
    SW.MASKS = sp_smg03_mags.TEX + "/masks"


def _group(setname):
    st = sp_lib.stack_by_name(setname)
    return [n for n in L.get_root_layer_nodes(st) if n.get_name() == SW.GROUP][0]


def _top_child(grp):
    """Верхний слой группы — по нему ставится следующий (above_node)."""
    subs = grp.sub_layers()
    return subs[-1] if subs else None


def _drop_generic(grp):
    n = 0
    for lay in list(grp.sub_layers()):
        if lay.get_name() in DROP:
            L.delete_node(lay)
            n += 1
    return n


def build_set(setname, scene):
    SW.build_set(setname, scene)
    grp = _group(setname)
    dropped = _drop_generic(grp)
    subs = grp.sub_layers()
    # порядок sub_layers: проверка, какой конец — верх (по имени первого слоя общего износа)
    first_name = "тон — чуть светлее и теплее"
    top_is_last = subs and subs[0].get_name() == first_name
    st = {"last": subs[-1] if top_is_last else subs[0]}
    body = [m for c, v in SW._classes(setname).items() if c != "round" for m in v]
    log = [f"{setname}: общих снято {dropped}"]

    def add(name, zone, **ch):
        if not os.path.exists(f"{ZONES}/{setname}_{zone}.png"):
            return None
        lay = fill(name, L.InsertPosition.above_node(st["last"]), **ch)
        st["last"] = lay
        SW._zone(lay, setname, zone)
        sp_lib.only_meshes(lay, body)
        log.append(name)
        return lay

    # 1. шахта — заглажено широко: полимер светлее и глаже
    lay = add("шахта — заглажено", "polish", color=(0.15, 0.15, 0.155), rough=0.28)
    if lay:
        sp_lib.lop(lay, 0.85)
    # 2. шахта — продольные полосы (главное по ориентиру): светлый блестящий полимер, внутри — темнее мазками
    lay = add("шахта — полосы", "streaks", color=(0.36, 0.36, 0.37), rough=0.22, height=0.4988)
    lay = add("шахта — полосы, тёмное внутри", "streaks", color=(0.19, 0.19, 0.20), rough=0.30)
    if lay:
        mask_proc(lay, SMUDGE, {"Balance": 0.45, "Contrast": 0.5}, scale=scene / 6.0,
                  blend=L.BlendingMode.Multiply, above=SW._last_mask(lay))
        sp_lib.lop(lay, 0.55)
    # 3. дорожка защёлки и кромки окон
    lay = add("защёлка — дорожка и кромки окон", "catch", color=(0.27, 0.27, 0.28), rough=0.26)
    # 4. губки — заглажено затвором
    lay = add("губки — заглажено затвором", "lips", color=(0.19, 0.19, 0.20), rough=0.30)
    # 5. донышко — затёрто светлее и матовее (удары о землю, а не скольжение)
    lay = add("донышко — потёрты углы и рёбра", "bottom", color=(0.38, 0.375, 0.365), rough=0.64, height=0.4985)
    lay = add("донышко — царапины", "bottom_scr", color=(0.38, 0.38, 0.38), rough=0.55, height=0.4975)
    # 6. на 30 — рукав: упор в низ шахты, где держат
    lay = add("рукав — упор в низ шахты", "rim", color=(0.36, 0.36, 0.355), rough=0.58, height=0.4985)
    lay = add("рукав — где держат", "hand", color=(0.22, 0.22, 0.225), rough=0.28)
    if lay:
        sp_lib.lop(lay, 0.8)
    # 7. сталь вкладыша — сердцевины сильных полос, кромки губок, кромка окна защёлки; тёмные мазки по стали
    col, rough, metal = STEEL
    lay = add("до стали вкладыша", "bare", color=col, rough=rough, metal=metal, height=0.4975)
    if lay:
        sp_finish._mfilter(SW._last_mask(lay), "histogram_scan", {"Position": 0.42, "Contrast": 0.75})
    lay = add("сталь — тёмные мазки", "bare", color=(0.34, 0.34, 0.35), rough=0.45, metal=1.0)
    if lay:
        sp_finish._mfilter(SW._last_mask(lay), "histogram_scan", {"Position": 0.42, "Contrast": 0.75})
        mask_proc(lay, SMUDGE, {"Balance": 0.45, "Contrast": 0.5}, scale=scene / 5.0,
                  blend=L.BlendingMode.Multiply, above=SW._last_mask(lay))
        sp_lib.lop(lay, 0.6)
    # 8. латунь от гильз на внутренних кромках губок — мазками
    lay = add("губки — латунь от гильз", "brass", color=(0.60, 0.46, 0.24), rough=0.40, metal=0.8)
    if lay:
        mask_proc(lay, SMUDGE, {"Balance": 0.5, "Contrast": 0.5}, scale=scene / 4.0,
                  blend=L.BlendingMode.Multiply, above=SW._last_mask(lay))
        sp_lib.lop(lay, 0.65)
    log.append(f"верх группы — {'последний' if top_is_last else 'первый'} в sub_layers")
    return " | ".join(log)


def build(only=None):
    _use()
    import substance_painter.textureset as TS
    scene = sp_smg03._scene_mm()
    log = []
    for t in TS.all_texture_sets():
        if only and t.name() not in only:
            continue
        log.append(build_set(t.name(), scene))

    def done():
        import substance_painter.project as P
        P.save()
        return " || ".join(log)
    sp_lib.when_idle(done, "_wear_done.txt")
    return " || ".join(log)


def export(out_dir, only=None):
    _use()
    return sp_smg03_mags.export(out_dir, only)
