# ПП по мотивам KRISS Vector Gen II (wpn_smg_03): сборка high-poly из частей. Запуск (из папки RING):
# "D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/smg03/build.py -- <out.blend> [части через запятую]
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bpy  # noqa: E402
import importlib  # noqa: E402

PARTS = ("receiver", "barrel", "bolt", "controls", "sights", "stock", "magazine", "pins", "stamps", "rig")
for mod in ("lib",) + tuple("part_" + p for p in PARTS):
    if mod in sys.modules:
        importlib.reload(sys.modules[mod])
import lib  # noqa: E402

COLLS = ["Receiver", "Trigger_housing", "Barrel", "Bolt_group", "Controls", "Sights", "Stock", "Magazine", "Pins", "Rig"]
# детали без общей фаски (тела вращения с собственными фасками, пружины, патроны)
SKIP_SWEEP = ("Spring", "Round_", "Case_", "Bullet_")


def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.unit_settings.system = "METRIC"
    sc.unit_settings.scale_length = 1.0
    sc.unit_settings.length_unit = "MILLIMETERS"


def sweep_edges():
    """Общее скругление всех деталей, которые не скруглили сами (требование владельца: острых граней нет)."""
    done = set()
    for o in list(bpy.data.objects):
        if o.type != "MESH" or o.get("_fin") or o.name.startswith(SKIP_SWEEP) or o.data.name in done:
            continue
        if len(o.data.polygons) < 6:
            continue
        done.add(o.data.name)
        dims = o.dimensions
        w = max(0.08, min(0.4, min(d for d in dims if d > 1e-6) * 1000 * 0.04))
        lib.finish(o, w=w, seg=2, angle=40)
        print("SWEEP", o.name, round(w, 2))


def drop_wire():
    """Тела вращения с точками на оси оставляли ребро вдоль оси без граней — убрать (и вершины без рёбер); мелкие дыры —
    заделать."""
    import bmesh
    done = set()
    for o in bpy.data.objects:
        if o.type != "MESH" or o.data.name in done:
            continue
        done.add(o.data.name)
        bm = bmesh.new(); bm.from_mesh(o.data)
        wire = [e for e in bm.edges if not e.link_faces]
        changed = False
        if wire:
            bmesh.ops.delete(bm, geom=wire, context="EDGES")
            loose = [v for v in bm.verts if not v.link_edges]
            if loose:
                bmesh.ops.delete(bm, geom=loose, context="VERTS")
            changed = True
        # мелкие дыры (точное булево изредка оставляет в дне буквы гравировки дыру в доли миллиметра) — заделать;
        # незамкнутых оболочек по замыслу у этой модели нет
        border = [e for e in bm.edges if len(e.link_faces) == 1]
        if border:
            res = bmesh.ops.holes_fill(bm, edges=border, sides=16)
            if res["faces"]:
                print("HOLES_FILLED", o.name, len(res["faces"]))
                changed = True
        if changed:
            bm.to_mesh(o.data)
        bm.free()
        if changed and o.get("_fin"):
            # перенос через bmesh сбрасывает свои нормали — взвешенные заново
            lib.weighted(o)
            lib.apply_all(o)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    out_path = argv[0] if argv else os.path.join(lib.HERE, "..", "..", "_asset_src", "smg03", "SMG03_geometry.blend")
    out_path = os.path.abspath(out_path)
    stages = argv[1].split(",") if len(argv) > 1 else list(PARTS)
    reset_scene()
    top = lib.collection("SMG03")
    ctx = {"coll": {n: lib.collection(n, top) for n in COLLS}, "parts": {}}
    for p in PARTS:
        if p in stages:
            if p == "rig":
                sweep_edges()
            m = importlib.import_module("part_" + p)
            ctx["parts"][p] = m.build(ctx)
            print("PART_DONE", p)
    if "rig" not in stages:
        sweep_edges()
    drop_wire()
    tri = sum(lib.tris(o) for o in bpy.data.objects if o.type == "MESH")
    print("SMG03_TRIS", tri, "OBJECTS", sum(1 for o in bpy.data.objects if o.type == "MESH"))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=out_path, compress=True)
    print("SAVED", out_path)


main()
