# Задание Painter: стеки колёс v2 (проект wheels_kit.py: наборы WheelCap, WheelSteel, WheelAlloy). ARGS: styles —
# «Набор=стиль,…» (cap, steel, alloy); набор без записи — по материалам (литой, если есть rim_alloy).
import importlib

import substance_painter.layerstack as L
import substance_painter.textureset as TS

import sp_lib
import vstacks
importlib.reload(vstacks)

styles = dict(p.split("=") for p in ARGS.get("styles", "").split(",") if "=" in p)

for t in TS.all_texture_sets():
    st = t.get_stack()
    sp_lib.clear(st)
    probe = sp_lib.fill("_probe", L.InsertPosition.from_textureset_stack(st), rough=0.5)
    probe.set_geometry_mask_type(L.GeometryMaskType.Mesh)
    have = set(probe.get_geometry_mask_enabled_meshes())
    L.delete_node(probe)
    name = t.name()
    style = styles.get(name) or ("alloy" if vstacks.pick(have, name, "rim_alloy") else "steel")
    vstacks.wheel(st, have, name, style)
    rest = vstacks.uncovered(st, have)
    if rest:
        print("  без своего слоя:", rest)
        vstacks.plastic(st, rest, name="Прочее (без своего стека)")
    print(name, style, "слоёв:", len(L.get_root_layer_nodes(st)), sorted(have))
