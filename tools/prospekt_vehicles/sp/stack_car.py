# Задание Painter: стеки слоёв семьи clean (легковая и коробчатая) — ARGS: color — цвет краски «r,g,b» (sRGB 0–1);
# livery — начало пути картинок ливреи («…/livery_clean»: файл <начало>_<набор>.png, livery.py), where — так же маски мест
# ссадин (перевёрнутый автобус). Нет файла набора — краска однотонная, как у партии 1.
# wheel — колесо «стиль:вариант» (wheel_looks.stack_arg: cap / steel / alloy и вариант отделки).
import importlib
import os

import substance_painter.layerstack as L
import substance_painter.textureset as TS

import sp_lib
import vstacks
importlib.reload(vstacks)

color = tuple(float(c) for c in ARGS.get("color", "0.85,0.85,0.83").split(","))


def picture(key, name):
    path = f"{ARGS[key]}_{name}.png" if key in ARGS else ""
    return vstacks.bitmap(path) if path and os.path.exists(path) else None


for t in TS.all_texture_sets():
    st = t.get_stack()
    sp_lib.clear(st)
    probe = sp_lib.fill("_probe", L.InsertPosition.from_textureset_stack(st), rough=0.5)
    probe.set_geometry_mask_type(L.GeometryMaskType.Mesh)
    have = set(probe.get_geometry_mask_enabled_meshes())
    L.delete_node(probe)
    name = t.name()
    if name.startswith("Body"):
        vstacks.body_clean(st, color, have, name, picture("livery", name), picture("where", name))
    elif name == "Interior":
        # seat_plastic — цвет пластика «сидений» салона: у скорой это кислородные баллоны (синие)
        sp = ARGS.get("seat_plastic")
        vstacks.interior_clean(st, have, *([tuple(float(c) for c in sp.split(","))] if sp else []))
    elif name == "Wheel":
        vstacks.wheel_clean(st, have, ARGS.get("wheel"))     # «стиль:вариант» (wheel_looks.CAR_WHEELS)
    elif name == "Under":
        vstacks.under_clean(st, have)
    rest = vstacks.uncovered(st, have)
    if rest:                                     # новый материал без стека — тёмным пластиком, и сказать об этом
        print("  без своего слоя:", rest)
        vstacks.plastic(st, rest, name="Прочее (без своего стека)")
    print(name, "слоёв:", len(L.get_root_layer_nodes(st)), sorted(have))
