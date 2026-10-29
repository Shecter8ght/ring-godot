# Задание Painter: битая — Body: краска как у целой + удар (ARGS: color, fi — инверсия «перёд», li — «лево»;
# livery — начало пути картинок ливреи, как у sp/stack_car.py: такси и полиция партии 2).
import importlib
import os

import substance_painter.layerstack as L
import substance_painter.textureset as TS

import sp_lib
import vstacks
importlib.reload(vstacks)

color = tuple(float(c) for c in ARGS.get("color", "0.86,0.86,0.84").split(","))
path = f"{ARGS['livery']}_Body.png" if "livery" in ARGS else ""
livery = vstacks.bitmap(path) if path and os.path.exists(path) else None
for t in TS.all_texture_sets():
    st = t.get_stack()
    sp_lib.clear(st)
    probe = sp_lib.fill("_probe", L.InsertPosition.from_textureset_stack(st), rough=0.5)
    probe.set_geometry_mask_type(L.GeometryMaskType.Mesh)
    have = set(probe.get_geometry_mask_enabled_meshes())
    L.delete_node(probe)
    if t.name() == "Body":
        vstacks.body_clean(st, color, have, "Body", livery)
        vstacks.body_wreck_damage(st, have, int(ARGS.get("fi", 0)), int(ARGS.get("li", 0)))
    elif t.name() == "Interior":
        vstacks.interior_clean(st, have)
    elif t.name() == "Wheel":
        vstacks.wheel_clean(st, have)
    elif t.name() == "Under":
        vstacks.under_clean(st, have)
    print(t.name(), "слоёв:", len(L.get_root_layer_nodes(st)))
