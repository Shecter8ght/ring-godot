# «Осока», тепловизор ПН-36Т «ПОЛЫНЬ», этап 2 — износ (навык weapon-asset-wear) в Substance Painter поверх принятой
# заводской отделки v1: группа «Этап 2 — износ» над «Этап 1 — заводская отделка» (выключается целиком). Кирпичики — те же,
# что у «Осоки» (tools/osoka/sp_osoka_wear.py: тон SoftLight множителем, жир, полировка, стёртое до алюминия с ободком
# и рисками по генератору кромок в маске места, пыль по AO); места — tools/osoka/sight_wear_zones.py
# (_asset_src/osoka_polyn/tex/wear/Polyn_<место>.png). Интервью 2026-11-07: «Как у «Осоки»», прибор многоразовый,
# следы — лицо и руки, установка на трубу, удары и сумка, пыль и тон краски.
#
#   … sp_run.py -c "import sys; sys.path.insert(0, r'E:/Games/RING-godot/tools/osoka'); import sp_polyn, sp_polyn_wear; print(sp_polyn_wear.build())"
#   → метка _wear_done.txt, проект сохраняется копией Polyn_wear_v1.spp
import substance_painter.layerstack as L
import substance_painter.textureset as TS

import sp_finish
import sp_lib
import sp_polyn  # noqa: F401  (пути набора Polyn в sp_osoka — до импорта кирпичиков)
import sp_osoka
import sp_osoka_wear as WK
from sp_lib import CH, fill, only_meshes

SET = "Polyn"
WK.ZONES = sp_osoka.TEX + "/wear"
PROJECT = sp_osoka.TEX + "/sp/Polyn_wear_v1.spp"
BLACK_PAINT = (0.105, 0.105, 0.11)     # основа CK-BLK-RGH (стёртая надпись открывает её)
STEEL = ((0.56, 0.56, 0.55), 0.32, 1.0)    # вершины рифления головок винтов — светлая сталь


def bare(add, name, level, label, meshes=None, metal=None):
    """Стёрто до металла (как sp_osoka_wear._bare), но без тёмного ободка: на чёрной краске и анодировании он не нужен
    и с генератором кромок давал тёмные пятна по стенкам."""
    col, rough, met = metal or WK.ALU
    lay = add(label, color=col, rough=rough, metal=met, height=0.4975)
    WK._mew(lay, level)
    WK._zone(lay, SET, name, L.BlendingMode.Multiply)
    sc = add(f"{label} — риски внутри", color=WK.ALU_DARK, rough=0.5, metal=1.0)
    WK._mew(sc, level)
    WK._zone(sc, SET, name, L.BlendingMode.Multiply)
    sp_lib.mask_proc(sc, "grunge_scratches_fine/grunge_scratches_fine", WK.SCR,
                     scale=sp_osoka._json("scene.json")["size_mm"] / 30.0, blend=L.BlendingMode.Multiply,
                     above=WK._last_mask(sc))
    sp_lib.lop(sc, 0.6)
    for n in (lay, sc):
        if meshes:
            only_meshes(n, meshes)
    return lay


def build_set():
    ms = WK._meshes(SET)
    paint = ms.get("body", [])
    rub = ms.get("rubber", [])
    metal = ms.get("metal", [])
    plastic = ms.get("plastic", [])
    brass = ms.get("brass", [])
    pos = WK._new_group(SET)
    st = {"last": None}

    def add(name, **ch):
        lay = fill(name, L.InsertPosition.above_node(st["last"]) if st["last"] else pos, **ch)
        st["last"] = lay
        return lay

    z = lambda lay, name, blend=None: WK._zone(lay, SET, name, blend)  # noqa: E731
    log = []
    # 0. надписи стёрты пальцами (у переключателя сильнее) — открывают чёрную краску
    lay = add("надписи — стёрто пальцами", color=BLACK_PAINT, rough=0.76)
    z(lay, "marking_rub")
    sp_lib.lop(lay, 0.8)
    # 1. тон чёрной краски: выгорело сверху, снизу холоднее, пятна четырёх оттенков (на чёрном — заметно слабее, чем
    # на оливе «Осоки»: множители больше)
    # проба 1 (множители 1.35–1.45) увела чёрный в буро-серый — у чёрного тон держится мягче
    for name, color, op, label in (
            ("sun", (1.16, 1.12, 1.06), 0.5, "тон — выгорело сверху (светлее, теплее)"),
            ("low", (0.92, 0.95, 0.99), 0.45, "тон — снизу темнее, холоднее"),
            ("warm_light", (1.10, 1.07, 1.02), 0.35, "тон — пятна тёплые светлые"),
            ("warm_dark", (0.95, 0.91, 0.87), 0.3, "тон — пятна тёплые тёмные (бурые)"),
            ("cool_light", (1.05, 1.08, 1.11), 0.3, "тон — пятна холодные светлые (серые)"),
            ("cool_dark", (0.93, 0.95, 0.97), 0.25, "тон — пятна холодные тёмные")):
        if WK._tint(add, SET, name, color, op, label):
            only_meshes(st["last"], paint)
    lay = add("блеск — разводы протирки", rough=0.55)
    z(lay, "wipe")
    sp_lib.lop(lay, 0.5)
    only_meshes(lay, paint)
    log.append("тон и блеск")
    # 2. пыль: в углах и щелях (по AO), пятнами на крыше; на резине слабее
    lay = add("пыль в углах и щелях", color=WK.DUST, rough=0.92)
    z(lay, "cavity")
    sp_lib.lop(lay, 0.25)
    only_meshes(lay, [m for m in paint + metal + plastic + brass + ms.get("bracket", []) + ms.get("steel", [])])
    lay = add("пыль в углах — резина", color=WK.DUST, rough=0.92)
    z(lay, "cavity")
    sp_lib.lop(lay, 0.12)
    only_meshes(lay, rub)
    lay = add("пыль на крыше", color=WK.DUST, rough=0.88)
    z(lay, "dust")
    sp_lib.lop(lay, 0.1)
    only_meshes(lay, paint + ms.get("bracket", []))
    log.append("пыль")
    # 3. лицо и руки
    WK._prints(add, SET, "face_oil", 0.7, "наглазник — засален лицом")
    WK._polish(add, SET, "focus", 0.45, (1.08, 1.08, 1.06), 0.55, "кольцо фокуса — пальцы")
    WK._polish(add, SET, "batt", 0.45, (1.08, 1.08, 1.06), 0.5, "крышка отсека — пальцы")
    WK._polish(add, SET, "keys", 0.4, (1.1, 1.1, 1.08), 0.7, "кнопки — центр")
    WK._polish(add, SET, "cap_tab", 0.42, (1.1, 1.1, 1.08), 0.65, "крышка объектива — язычок под пальцем")
    WK._polish(add, SET, "switch", 0.35, (1.15, 1.13, 1.08), 0.6, "переключатель — рычажок и латунь по ходу")
    bare(add, "diopter", 0.3, "кольцо диоптрий — вершины рифления", meshes=metal)
    WK._prints(add, SET, "prints_left", 0.55, "левый бок — отпечатки и разводы")
    WK._prints(add, SET, "prints_right", 0.55, "правый бок — отпечатки и разводы")
    log.append("лицо и руки")
    # 4. установка на трубу: губки лапы, рельс, губки площадки — кромки до алюминия; риски по лапе; головки винтов
    bare(add, "mount_bare", 0.35, "кронштейн и рельс — кромки (ставят и снимают)",
             meshes=ms.get("bracket", []) + metal)
    lay = add("лапа — риски вдоль трубы", color=WK.ALU_DARK, rough=0.45, metal=1.0)
    z(lay, "mount_scuff")
    sp_finish._mfilter(WK._last_mask(lay), "histogram_scan", {"Position": 0.5, "Contrast": 0.7})
    sp_lib.lop(lay, 0.6)
    bare(add, "knobs", 0.35, "головки прижимных винтов — вершины рифления", meshes=ms.get("steel", []),
             metal=STEEL)
    log.append("установка")
    # 5. удары и сумка: выступающие рёбра корпуса, кромка оправы объектива, край крышки отсека — местами до алюминия
    bare(add, "bumps", 0.3, "удары и сумка — выступающие кромки", meshes=paint + metal)
    lay = add("резина — ссадины", color=(0.22, 0.22, 0.21), rough=0.8)
    z(lay, "rubber_scuff")
    sp_lib.lop(lay, 0.25)
    only_meshes(lay, rub)
    lay = add("грязь кольцом у крепежа и кнопок", color=WK.GRIME, rough=0.92)
    z(lay, "rings")
    sp_lib.lop(lay, 0.55)
    lay = add("акцент — царапина на правом боку", color=(0.42, 0.42, 0.41), rough=0.55, height=0.4985)
    z(lay, "accent")
    sp_finish._mfilter(WK._last_mask(lay), "histogram_scan", {"Position": 0.45, "Contrast": 0.7})
    only_meshes(lay, paint)
    log.append("удары и сумка")
    return f"{SET}: " + ", ".join(log)


def build():
    log = [build_set()]

    def done():
        sp_finish.save_as(PROJECT)
        return " | ".join(log)
    sp_lib.when_idle(done, "_wear_done.txt")
    return " | ".join(log)
