# Задание Painter: стеки слоёв семьи clean (легковая и коробчатая) — ARGS: color — цвет краски «r,g,b» (sRGB 0–1).
import importlib

import substance_painter.layerstack as L
import substance_painter.textureset as TS

import sp_lib
import vstacks
importlib.reload(vstacks)

color = tuple(float(c) for c in ARGS.get("color", "0.85,0.85,0.83").split(","))
for t in TS.all_texture_sets():
    st = t.get_stack()
    sp_lib.clear(st)
    probe = sp_lib.fill("_probe", L.InsertPosition.from_textureset_stack(st), rough=0.5)
    probe.set_geometry_mask_type(L.GeometryMaskType.Mesh)
    have = set(probe.get_geometry_mask_enabled_meshes())
    L.delete_node(probe)
    name = t.name()
    if name.startswith("Body"):
        vstacks.body_clean(st, color, have, name)
    elif name == "Interior":
        vstacks.interior_clean(st, have)
    elif name == "Wheel":
        vstacks.wheel_clean(st, have)
    elif name == "Under":
        vstacks.under_clean(st, have)
    rest = vstacks.uncovered(st, have)
    if rest:                                     # новый материал без стека — тёмным пластиком, и сказать об этом
        print("  без своего слоя:", rest)
        vstacks.plastic(st, rest, name="Прочее (без своего стека)")
    print(name, "слоёв:", len(L.get_root_layer_nodes(st)), sorted(have))
