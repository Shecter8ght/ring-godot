# ВСС-М v8: основа материалов в открытом проекте Painter БЕЗ пересборки стека — для наборов с ручной работой владельца
# (слои «РУКАМИ», sp_manual_prep.py; sp_lib.clear на них останавливается). Заливкам основы и производным от неё цветам
# (истончилось, царапины, масло, отпечатки, пыль, грязь…) задаются значения из sp_stacks — те же константы и формулы,
# что при сборке стека; маски, слои рисования и всё остальное не трогаются. 27.10: сталь — вариант A (воронение
# 0.22 / металл 0.9), чёрные неметаллы (цевьё, магазины, резина, Cerakote) — по правилу PBR, 0.15–0.2 sRGB.
# Задание моста: перед exec задать BASE_SETS = ["receiver"] или ["steel_parts", "suppressor", …]; затем проект
# сохраняется и наборы выгружаются в обычные папки export (sp_receiver/export или sp_parts/export).
import importlib
import sys

TOOLS = "E:/Games/RING-godot/tools/vss_m_v8"
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)
import sp_lib  # noqa: E402
import sp_stacks as S  # noqa: E402
importlib.reload(sp_lib)
importlib.reload(S)
import substance_painter.layerstack as L  # noqa: E402
import substance_painter.project as P  # noqa: E402

CH = sp_lib.CH
OUT = {"receiver": "E:/Games/RING-godot/_asset_src/vss_m_v8/sp_receiver/export"}
PARTS_OUT = "E:/Games/RING-godot/_asset_src/vss_m_v8/sp_parts/export"


def mix(a, b, t):
    return tuple(x + (y - x) * t for x, y in zip(a, b))


def coated_spec(coat, bare, parts):
    """Значения слоёв sp_stacks.coated: (группа, слой) → каналы."""
    c, r, m = coat
    g = "Покрытие и износ"
    spec = {(g, "01 Покрытие"): {"color": c, "rough": r, "metal": m},
            (g, "02б Пятна тона и блеска"): {"color": mix(c, (0.22, 0.22, 0.22), 0.3), "rough": r + 0.1},
            (g, "03 Блеск пятнами"): {"rough": r + 0.07},
            (g, "04 Протёрто до блеска"): {"rough": max(0.12, r - 0.08)},
            (g, "05 Покрытие истончилось"): {"color": mix(c, bare[0], 0.4), "rough": (r + bare[1]) / 2,
                                            "metal": (m + bare[2]) / 2},
            (g, "10 Царапины"): {"color": mix(c, bare[0], 0.8)},
            ("", "13 Масло"): {"color": mix(c, (0.0, 0.0, 0.0), 0.3)},
            ("", "14 Отпечатки жирные"): {"color": mix(c, (0.2, 0.19, 0.18), 0.4)}}
    for label, _names, col, ro, me in parts:
        spec[(g, "01 Основа: " + label)] = {"color": col, "rough": ro, "metal": me}
    return spec


def cerakote_spec(rails=True):
    """sp_stacks.cerakote: у заднего прицела (внутри мелкой стали) планок нет — нет и слоя «05б»."""
    g = "Cerakote H-146"
    spec = {(g, "01 Cerakote"): {"color": S.CK_COLOR},
            (g, "05 Промежуточный слой: углы"): {"color": S.CK_INTER},
            ("", "07 Пыль в углах"): {"color": S.CK_DUST},
            ("", "08 Засохшее масло"): {"color": S.CK_OIL}}
    if rails:
        spec[(g, "05б Промежуточный слой: планки вдоль")] = {"color": S.CK_INTER}
    return spec


def mag_spec():
    g = "Полиамид"
    return {(g, "01 Полиамид"): {"color": S.MAG["base"]},
            (g, "05 Губки и упор затёрты до блеска"): {"color": S.MAG["lips"]},
            (g, "06 Белёсые потёртости кромок"): {"color": S.MAG["scuff"]},
            (g, "07 Царапины"): {"color": S.MAG["scratch"]},
            ("", "08 Грязь в углах"): {"color": S.MAG["dirt"]},
            ("", "09 Пыль в рёбрах"): {"color": S.MAG["dust"]}}


SPEC = {
    "receiver": coated_spec(S.STEEL_COAT, S.STEEL_BARE, S.RECEIVER_PARTS),
    "steel_parts": {**coated_spec(S.STEEL_COAT, S.STEEL_BARE, S.STEEL_PARTS_PARTS), **cerakote_spec(rails=False)},
    "suppressor": coated_spec(S.SUPPRESSOR_COAT, S.STEEL_BARE, []),
    "sleeve": cerakote_spec(),
    "handguard": {("Полимер", "01 Полимер"): {"color": S.POLY["base"]},
                  ("Полимер", "03б Пыль в порах шагрени"): {"color": S.POLY["pore_dust"]},
                  ("Полимер", "06 Царапины"): {"color": S.POLY["scratch"]},
                  ("Полимер", "07 Затёртые кромки"): {"color": S.POLY["edge"]},
                  ("", "08 Грязь в углах"): {"color": S.POLY["dirt"]},
                  ("", "09 Пыль в углах"): {"color": S.POLY["dust"]},
                  ("", "10 Отпечатки жирные"): {"color": S.POLY["prints"]}},
    "magazine": mag_spec(),
    "magazine_30": mag_spec(),
    "rubber": {("", "01 Резина"): {"color": S.RUBBER["base"]},
               ("", "03 Потёртости"): {"color": S.RUBBER["scuff"]},
               ("", "04 Залоснённые кромки"): {"color": S.RUBBER["edge"]},
               ("", "05 Пыль в углублениях"): {"color": S.RUBBER["dust"]}},
}


def setv(layer, ch):
    if "color" in ch:
        layer.set_source(CH.BaseColor, sp_lib._val(tuple(min(0.95, x) for x in ch["color"])))
    if "rough" in ch:
        layer.set_source(CH.SpecularRoughness, sp_lib._val(min(0.95, max(0.06, ch["rough"])), data=True))
    if "metal" in ch:
        layer.set_source(CH.BaseMetalness, sp_lib._val(min(1.0, max(0.0, ch["metal"])), data=True))


def resolve(set_name):
    """Слои набора по (группа, имя); отсутствующие — списком (тогда ничего не меняем ни в одном наборе)."""
    roots = L.get_root_layer_nodes(sp_lib.stack_by_name(set_name))
    hits, missing = [], []
    for (grp, name), ch in SPEC[set_name].items():
        pool = roots
        if grp:
            gs = [n for n in roots if n.get_name() == grp]
            pool = gs[0].sub_layers() if gs else []
        hit = [n for n in pool if n.get_name() == name]
        if hit:
            hits.append((hit[0], ch))
        else:
            missing.append(f"{set_name}: {grp}/{name}")
    return hits, missing


sets = list(BASE_SETS)  # noqa: F821
BASE_SETS = None                 # глобальные переменные моста общие для заданий — сбрасываем
plan = {s: resolve(s) for s in sets}
missing = [m for _h, ms in plan.values() for m in ms]
if missing:
    raise RuntimeError(f"не найдены слои: {missing}")
for s, (hits, _m) in plan.items():
    for layer, ch in hits:
        setv(layer, ch)
    print(s, "задано слоёв", len(hits))


def _finish(names=tuple(sets)):
    P.save()
    return [(n, str(sp_lib.export(OUT.get(n, PARTS_OUT), n)[0])) for n in names]


sp_lib.when_idle(_finish)
