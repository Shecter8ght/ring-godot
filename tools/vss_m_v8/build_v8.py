# ВСС-М v8: сборка геометрии из частей. Запуск:
# blender --background --factory-startup --python-exit-code 1 --python tools/vss_m_v8/build_v8.py -- <out.blend> [стадии]
# Деревянный приклад с затыльником берётся из принятой v7 (_asset_src/vss_fit_v7/VSS_Fit_v7.blend) без изменений.
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bpy  # noqa: E402
import importlib  # noqa: E402
import lib  # noqa: E402

for mod in ("lib", "part_stock", "part_receiver", "part_bolt", "part_controls", "part_front", "part_magazine", "part_stamps", "part_rig"):
    if mod in sys.modules:
        importlib.reload(sys.modules[mod])

ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
V7 = os.path.join(ROOT, "_asset_src", "vss_fit_v7", "VSS_Fit_v7.blend")
STOCK_PARTS = []   # затыльник и приклад v8 строятся заново (part_stock) по контурам v7


def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.unit_settings.system = "METRIC"
    sc.unit_settings.scale_length = 1.0
    sc.unit_settings.length_unit = "MILLIMETERS"


def append_stock(coll):
    with bpy.data.libraries.load(V7, link=False) as (src, dst):
        dst.objects = [n for n in src.objects if n in STOCK_PARTS]
    out = []
    for o in dst.objects:
        if o is None:
            continue
        mw = o.matrix_world.copy()
        o.parent = None
        o.matrix_world = mw
        coll.objects.link(o)
        # материалы v7 заменяем нейтральными v8 по назначению
        name = "Wood_stock" if "Wood_stock" in o.name else "Rubber" if "butt_pad" in o.name else "Steel_black"
        o.data = o.data.copy()
        o.data.materials.clear()
        o.data.materials.append(lib.material(name))
        out.append(o)
    return out


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    out_path = argv[0] if argv else os.path.join(ROOT, "_asset_src", "vss_m_v8", "VSS_M_v8_geometry.blend")
    stages = set(argv[1].split(",")) if len(argv) > 1 else {"receiver", "bolt", "controls", "front", "magazine", "stamps", "rig"}
    reset_scene()
    top = lib.collection("VSS_M_v8")
    names = ["Receiver", "Stock", "Bolt_group", "Controls", "Front", "Suppressor", "Rail_sleeve", "Magazines", "Rig"]
    ctx = {"coll": {n: lib.collection(n, top) for n in names}, "parts": {}}
    ctx["parts"]["stock"] = append_stock(ctx["coll"]["Stock"])
    import part_stock
    ctx["parts"]["stock_v8"] = part_stock.build(ctx)
    import part_receiver
    ctx["parts"]["receiver"] = part_receiver.build(ctx)
    if "bolt" in stages:
        import part_bolt
        ctx["parts"]["bolt"] = part_bolt.build(ctx)
    if "controls" in stages:
        import part_controls
        ctx["parts"]["controls"] = part_controls.build(ctx)
    if "front" in stages:
        import part_front
        ctx["parts"]["front"] = part_front.build(ctx)
    if "magazine" in stages:
        import part_magazine
        ctx["parts"]["magazine"] = part_magazine.build(ctx)
    if "rig" in stages:
        import part_rig
        part_rig.build(ctx)
    tri = 0
    for o in bpy.data.objects:
        if o.type == "MESH":
            tri += lib.tris(o)
    print("V8_TRIS", tri, "OBJECTS", sum(1 for o in bpy.data.objects if o.type == "MESH"))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=out_path, compress=True)
    print("SAVED", out_path)


main()
