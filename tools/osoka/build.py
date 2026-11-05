# «Осока» (ПЗРК по образцу 9К333 «Верба»): сборка high-poly из частей. Запуск (из папки RING):
# "D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/osoka/build.py -- <out.blend> [части через запятую]
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bpy  # noqa: E402
import importlib  # noqa: E402

PARTS = ("tube", "saddle", "launcher", "power", "sling", "missile", "rig")
for mod in ("lib", "dims") + tuple("part_" + p for p in PARTS):
    if mod in sys.modules:
        importlib.reload(sys.modules[mod])
import lib  # noqa: E402

COLLS = ["Tube", "Caps", "Saddle", "Sights", "Launcher", "Power", "Sling", "Missile", "Rig"]


def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.unit_settings.system = "METRIC"
    sc.unit_settings.scale_length = 1.0
    sc.unit_settings.length_unit = "MILLIMETERS"


# детали, прилегающие к трубе снаружи: из них вычитается объём трубы (канал под ракету R 38.6, у хомута ГСН — R 45),
# иначе литьё, короб и бобышки проходили сквозь стенку трубы в ракету (check_overlaps, v01)
HUG = ("Saddle_body", "Saddle_side_rib", "Box_upper", "Box_rear_plate", "Box_seam_lip", "Lid_front_boss",
       "Lid_mid_boss", "Rear_sight_base", "Tube_clamp_0_ear", "Tube_clamp_1_ear", "Tube_rear_bracket", "Front_sight_base",
       "Dust_cover_base", "Lid_top_boss", "Sling_loop_base", "Launcher_tab_", "Saddle_right_flange", "Saddle_right_boss",
       "Front_right_boss", "Mount_plate")


def flat_normals():
    """Большие плоские грани после булевых (боковины рамы с вырезами) показывались «пилой»: нормали вершин по краю
    грани усреднялись со скруглёнными кромками и тянулись клиньями через всю грань (владелец о v04). Взвешенные по
    площади нормали оставляют большую грань плоской (нарезка сеткой на раме давала дыры — не годится)."""
    for o in list(bpy.data.objects):
        if o.type != "MESH" or o.get("_fin") or o.name.startswith(("Missile_", "Sling_strap")):
            continue
        if any(len(p.vertices) > 12 for p in o.data.polygons):
            # большие многоугольники — на треугольники самим (уши): показ Blender бил их с перехлёстом — тёмная
            # «пила» на ровной боковине (рама рукояти, v04–v05)
            import bmesh
            bm = bmesh.new(); bm.from_mesh(o.data)
            big = [f for f in bm.faces if len(f.verts) > 12]
            bmesh.ops.triangulate(bm, faces=big, quad_method="BEAUTY", ngon_method="EAR_CLIP")
            bm.to_mesh(o.data); bm.free()
            lib.weighted(o)
            lib.apply_all(o)


def hug_tube():
    # литьё пускового механизма обжимается раньше — в part_launcher, до литых надписей
    for o in list(bpy.data.objects):
        if o.type != "MESH" or not o.name.startswith(HUG):
            continue
        print("HUG", o.name, lib.hug_tube(o))


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    out_path = os.path.abspath(argv[0])
    stages = argv[1].split(",") if len(argv) > 1 else list(PARTS)
    reset_scene()
    top = lib.collection("OSOKA")
    ctx = {"coll": {n: lib.collection(n, top) for n in COLLS}, "parts": {}}
    for p in PARTS:
        if p == "rig":
            hug_tube()
            flat_normals()
        if p in stages:
            path = os.path.join(HERE, "part_" + p + ".py")
            if not os.path.exists(path):
                print("PART_MISSING", p)
                continue
            m = importlib.import_module("part_" + p)
            ctx["parts"][p] = m.build(ctx)
            print("PART_DONE", p)
    if "rig" not in stages:
        hug_tube()
        flat_normals()
    tri = sum(lib.tris(o) for o in bpy.data.objects if o.type == "MESH")
    print("OSOKA_TRIS", tri, "OBJECTS", sum(1 for o in bpy.data.objects if o.type == "MESH"))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=out_path, compress=True)
    print("SAVED", out_path)


main()
