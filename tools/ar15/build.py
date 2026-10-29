# AR-15 «Fab-сборка»: сборка геометрии из частей. Запуск:
# blender --background --factory-startup --python-exit-code 1 --python tools/ar15/build.py -- <out.blend> [стадии через запятую]
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bpy  # noqa: E402
import importlib  # noqa: E402

PARTS = ("upper", "lower", "bolt", "front", "muzzle", "sights", "stock", "grip", "magazine", "rig")
for mod in ("lib",) + tuple("part_" + p for p in PARTS):
    if mod in sys.modules:
        importlib.reload(sys.modules[mod])
import lib  # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
COLLS = ["Upper", "Lower", "Fire_control", "Bolt_group", "Charging_handle", "Barrel", "Handguard", "Muzzle", "Suppressor",
         "Stock", "Grip", "Magazine", "Sights", "Rig"]


def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.unit_settings.system = "METRIC"
    sc.unit_settings.scale_length = 1.0
    sc.unit_settings.length_unit = "MILLIMETERS"


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    out_path = argv[0] if argv else os.path.join(ROOT, "_asset_src", "ar15", "AR15_geometry.blend")
    stages = argv[1].split(",") if len(argv) > 1 else list(PARTS)
    reset_scene()
    top = lib.collection("AR15")
    ctx = {"coll": {n: lib.collection(n, top) for n in COLLS}, "parts": {}}
    for p in PARTS:
        if p in stages:
            m = importlib.import_module("part_" + p)
            ctx["parts"][p] = m.build(ctx)
            print("PART_DONE", p)
    tri = sum(lib.tris(o) for o in bpy.data.objects if o.type == "MESH")
    print("AR15_TRIS", tri, "OBJECTS", sum(1 for o in bpy.data.objects if o.type == "MESH"))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=out_path, compress=True)
    print("SAVED", out_path)


main()
