# Задание Painter: сгоревшая — Body, Interior, Wheel, Under (ARGS: color — цвет краски, что осталась внизу).
import importlib

import substance_painter.layerstack as L
import substance_painter.textureset as TS

import sp_lib
import vstacks
importlib.reload(vstacks)

color = tuple(float(c) for c in ARGS.get("color", "0.86,0.86,0.84").split(","))
for t in TS.all_texture_sets():
    st = t.get_stack()
    sp_lib.clear(st)
    probe = sp_lib.fill("_probe", L.InsertPosition.from_textureset_stack(st), rough=0.5)
    probe.set_geometry_mask_type(L.GeometryMaskType.Mesh)
    have = set(probe.get_geometry_mask_enabled_meshes())
    L.delete_node(probe)
    name = t.name()
    if name == "Body":
        vstacks.body_burnt(st, color, have)
    else:
        vstacks.any_burnt(st, name, have, "Каркасы и железо" if name == "Interior" else "Железо")
    print(name, "слоёв:", len(L.get_root_layer_nodes(st)), sorted(have))
