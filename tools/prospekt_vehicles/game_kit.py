"""Транспорт «Проспекта»: игровая сетка LOD0 и файлы для Substance Painter.

    blender --background --factory-startup --python-exit-code 1 --python tools/prospekt_vehicles/game_kit.py -- \
        <класс> <папка Painter> <игровой .blend> [семьи через запятую]

Классы: легковые specs.CLASSES (sedan, hatch, wagon, suv) и «коробчатые» specs_bus.BOXES (bus12, paz, gazel). У коробчатых
одна семья clean (целый и с открытыми дверями); кузов длиннее LONG_BODY делится на два набора BodyA / BodyB (левый борт
с передом и правый с задом и крышей) — иначе на 2K карте у 12-метрового автобуса мало точек на метр; колесо — наружное,
внутреннее колесо пары в игре — его зеркальная копия.

Одна и та же раскладка собирается дважды: подробно (источник запекания) и грубо (игровая сетка, vq.set_quality).
Семьи: clean — целый и открытый (одна геометрия, у открытого повёрнуты створки), wreck — битый, burnt — сгоревший.
Наборы текстур: Body (кузов снаружи, 2K), Interior (салон, 1K), Wheel (одно колесо на все места, 1K), Under (низ, 512);
стёкла и линзы фонарей — простой прозрачный материал Glass без карт.
Для Painter: <семья>_low.fbx — игровая сетка, слитая по (набор, материал детали): сетки «Body__paint», «Body__trim_black»
и т. п. — по их именам Painter маскирует слои; <семья>_high.fbx — подробная форма (без стёкол).
Колесо в FBX — одно, в стороне от кузова (x = +3,5 м), чтобы запекание AO не задевало кузов.
Игровой .blend: детали LOD0 по семьям (коллекции «LOD0_clean» и т. д.) с развёрткой — из них потом варианты и glTF.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import bmesh
import bpy
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import vlib  # noqa: E402,F401
import vq  # noqa: E402
from specs import CLASSES  # noqa: E402
from specs_bus import BOXES  # noqa: E402

INTERIOR = ("Dashboard", "Instrument_Hood", "Center_Stack", "Center_Screen", "Steering_", "Seat", "Headrest", "Console",
            "Floor", "Headliner", "Door_Card", "Parcel_Shelf", "Cargo_Cover", "Visor", "Mirror_Inner", "Trunk_Tub",
            "Trunk_Wall", "Sill_Tread", "Dash_Beam", "Driver_", "Dash", "Passenger_", "Handrails", "Ceiling", "Step_")
UNDER = ("Liner_", "Under_Tray", "Exhaust", "Frame", "Rear_Axle", "Fuel_Tank", "Rear_Springs", "Mudflap")
GLASS_MATS = ("glass", "lamp_glass", "lamp_red", "glass_broken", "display")
SET_RES = {"Body": 11, "Interior": 10, "Wheel": 10, "Under": 9}
LONG_BODY = 6.5          # м: длиннее — два набора кузова


def tex_set(name: str, mat: str) -> str:
    if mat in GLASS_MATS:
        return "Glass"
    if name.startswith("Exhaust_Tip"):
        return "Body"
    if name.startswith(INTERIOR):
        return "Interior"
    if name.startswith(UNDER):
        return "Under"
    return "Body"


def families(spec: dict):
    """Детали всех семей при текущем качестве: {семья: (детали, колесо)}; колесо — детали одного колеса."""
    import build_car as bc
    import carparts as cp
    import vdamage as vd

    kit, hinges, S, (field, surf, views) = bc.build_kit(spec)
    wparts = cp.wheel_parts(spec)
    wreck = bc.make_wreck(kit, spec, field, surf, views, S)
    burnt, dz = bc.make_burnt(kit, spec, field, surf, views, S)
    keep = ("Rim_Barrel", "Rim_Face", "Rim_Holes", "Brake_Disc", "Caliper", "Rim_Spokes", "Rim_Hub", "Lug_Nuts")
    recolor = {"rim_steel": "rust", "rim_alloy": "burnt_light", "brake": "rust", "steel_dark": "rust", "mesh_black": "burnt"}
    w_burnt = [(n, recolor.get(m, m), V, F) for n, m, V, F in wparts if n.startswith(keep)]
    w_flat = [(n, m, vd.flat_tire(V, spec["tire_r"], 0.05) if n == "Tire" else V, F) for n, m, V, F in wparts]
    return {"clean": (kit, wparts), "wreck": (wreck, w_flat), "burnt": (burnt, w_burnt)}, hinges, dz


def bus_families(spec: dict):
    """Коробчатая: детали кузова, мелочи и салон при текущем качестве; одна семья clean, колесо — наружное."""
    import build_bus as bb
    import vbus
    from surface import Surface
    from vfield import BoxField

    field = BoxField(spec)
    surf = Surface(field)
    views = vlib.make_views(spec)
    vbus.DEBUG.clear()
    parts, S = vbus.build(surf, field, spec, views)
    for name, view, outer, holes in vbus.DEBUG:
        print("  НЕ СОБРАНА:", name, view)
    parts += vbus.details(surf, field, spec, views, S)
    parts += vbus.interior(field, spec, S)
    hinges = bb.hinges(spec, S, surf, views)
    return {"clean": (parts, vbus.truck_wheel(spec))}, hinges, 0.0


def body_half(ts: str, V) -> str:
    """Длинный кузов: левый борт и всё переднее — BodyA, правый борт, зад и крыша — BodyB."""
    if ts != "Body":
        return ts
    c = np.asarray(V, float).mean(0)
    if abs(c[0]) > 0.3:
        return "BodyA" if c[0] > 0 else "BodyB"
    return "BodyA" if c[1] < 0 else "BodyB"


def mesh_obj(name: str, V, F, col) -> bpy.types.Object:
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(map(float, v)) for v in V], [], [tuple(int(i) for i in f) for f in F])
    me.validate()
    ob = bpy.data.objects.new(name, me)
    col.objects.link(ob)
    return ob


def triangulate(ob) -> None:
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.triangulate(bm, faces=bm.faces[:], quad_method="BEAUTY", ngon_method="BEAUTY")
    bm.to_mesh(ob.data)
    bm.free()


def unwrap(objs, margin: float = 0.003) -> None:
    """Общая развёртка набора: умная проекция, одинаковая плотность, плотная упаковка."""
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
        if not o.data.uv_layers:
            o.data.uv_layers.new(name="UVMap")
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(55.0), island_margin=margin, area_weight=0.0,
                             correct_aspect=True, scale_to_bounds=False)
    bpy.ops.uv.average_islands_scale()
    bpy.ops.uv.pack_islands(margin=margin, rotate=True, shape_method="CONCAVE")
    bpy.ops.object.mode_set(mode="OBJECT")


def material(name: str, rgb=(0.5, 0.5, 0.5)) -> bpy.types.Material:
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.diffuse_color = (*rgb, 1.0)
    return m


def build_family(fam: str, parts, wheel, col, wheel_x: float = 3.5, split: bool = False) -> dict:
    """Детали семьи → объекты с набором текстур в свойстве; колесо — отдельно в стороне. Возвращает {набор: [объекты]}."""
    sets: dict = {}
    for name, mat, V, F, grp in parts:
        if V is None or len(V) == 0:
            continue
        ts = tex_set(name, mat)
        if split:
            ts = body_half(ts, V)
        ob = mesh_obj(f"{fam}:{name}", V, F, col)
        ob["tex_set"], ob["mat"], ob["group"] = ts, mat, grp
        triangulate(ob)
        smooth_normals(ob)
        sets.setdefault(ts, []).append(ob)
    for name, mat, V, F in wheel:
        ts = "Glass" if mat in GLASS_MATS else "Wheel"
        ob = mesh_obj(f"{fam}:Wheel_{name}", V + np.array([wheel_x, 0, 0]), F, col)
        ob["tex_set"], ob["mat"], ob["group"] = ts, mat, "wheel"
        triangulate(ob)
        smooth_normals(ob)
        sets.setdefault(ts, []).append(ob)
    return sets


def merged_copy(objs, name: str, mat_name: str, col) -> bpy.types.Object:
    """Копии объектов, слитые в одну сетку (для Painter: имя сетки = маска слоя)."""
    bm = bmesh.new()
    for o in objs:
        tmp = bmesh.new()
        tmp.from_mesh(o.data)
        tmp.transform(o.matrix_world)
        me = bpy.data.meshes.new("_tmp")
        tmp.to_mesh(me)
        tmp.free()
        bm.from_mesh(me)
        bpy.data.meshes.remove(me)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(material(mat_name))
    ob = bpy.data.objects.new(name, me)
    col.objects.link(ob)
    return ob


def export_fbx(objs, path: Path) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.fbx(filepath=str(path), use_selection=True, apply_unit_scale=True,
                             apply_scale_options="FBX_SCALE_UNITS", mesh_smooth_type="FACE", use_mesh_modifiers=True,
                             axis_forward="-Z", axis_up="Y", object_types={"MESH"}, bake_anim=False)


def smooth_normals(ob, angle: float = 50.0) -> None:
    """Гладко, но рёбра круче angle — резкие (кромки панелей, торцы накладок): иначе нормали «перетекают» через угол."""
    for p in ob.data.polygons:
        p.use_smooth = True
    ob.data.set_sharp_from_angle(angle=math.radians(angle))


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1:]
    cls, sp_dir, game_blend = argv[0], Path(argv[1]), Path(argv[2])
    box = cls in BOXES
    spec = BOXES[cls] if box else CLASSES[cls]
    only = argv[3].split(",") if len(argv) > 3 else (["clean"] if box else ["clean", "wreck", "burnt"])
    fams = bus_families if box else families
    split = box and spec["length"] > LONG_BODY
    wheel_x = spec["width"] / 2 + 2.0 if box else 3.5
    bpy.ops.wm.read_factory_settings(use_empty=True)
    vq.set_quality("high")
    hi, hinges, dz = fams(spec)
    vq.set_quality("low")
    vq.Q["h"] = spec.get("lod_h", vq.Q["h"])      # крупные кузова — шаг сетки панелей чуть больше
    vq.Q["strip"] = spec.get("lod_strip", vq.Q["strip"])    # и шаг накладок (уплотнители окон автобуса)
    lo, _, _ = fams(spec)
    vq.set_quality("high")
    scratch = bpy.data.collections.new("_painter")
    bpy.context.scene.collection.children.link(scratch)
    report = {}
    for fam in only:
        col = bpy.data.collections.new(f"LOD0_{fam}")
        bpy.context.scene.collection.children.link(col)
        sets = build_family(fam, lo[fam][0], lo[fam][1], col, wheel_x, split)
        for ts, objs in sets.items():
            if ts == "Glass":
                continue
            unwrap(objs)
        n_wheels = (6 if spec.get("dual_rear") else 4) if box else 4
        tris = sum(len(o.data.polygons) for objs in sets.values() for o in objs if o["group"] != "wheel") + \
            n_wheels * sum(len(o.data.polygons) for o in sets.get("Wheel", []))
        report[fam] = tris
        print(f"LOD0 {fam}: треугольников {tris:,} (с колёсами: {n_wheels})")
        top = sorted(((len(o.data.polygons), o.name) for objs in sets.values() for o in objs), reverse=True)[:30]
        print("  самые тяжёлые:", ", ".join(f"{n.split(':', 1)[1]} {c}" for c, n in top))
        # FBX низкой: слить по (набор, материал детали)
        low_objs = []
        for ts, objs in sets.items():
            if ts == "Glass":
                continue
            bymat: dict = {}
            for o in objs:
                bymat.setdefault(o["mat"], []).append(o)
            for mat, group in bymat.items():
                low_objs.append(merged_copy(group, f"{ts}__{mat}", ts, scratch))
        for o in low_objs:
            smooth_normals(o)                     # слитые копии — заново (bmesh теряет пометки)
        export_fbx(low_objs, sp_dir / f"{fam}_low.fbx")
        # FBX высокой: подробная форма тех же деталей (без стёкол), колесо в той же стороне
        hcol = bpy.data.collections.new(f"_high_{fam}")
        bpy.context.scene.collection.children.link(hcol)
        hsets = build_family(fam + "_hi", [p for p in hi[fam][0] if p[1] not in GLASS_MATS],
                             [w for w in hi[fam][1] if w[1] not in GLASS_MATS], hcol, wheel_x, split)
        hobjs = []
        for ts, objs in hsets.items():
            hobjs.append(merged_copy(objs, f"{ts}__high", ts, scratch))
        for o in hobjs:
            smooth_normals(o)
        export_fbx(hobjs, sp_dir / f"{fam}_high.fbx")
        for o in list(hcol.objects):
            bpy.data.objects.remove(o)
        bpy.data.collections.remove(hcol)
        for o in low_objs + hobjs:
            bpy.data.objects.remove(o)
    bpy.data.collections.remove(scratch)
    scn = bpy.context.scene
    import json
    scn["hinges"] = json.dumps({k: [list(map(float, a)), list(map(float, ax)), float(s)] for k, (a, ax, s) in hinges.items()})
    scn["burnt_dz"] = float(dz)
    scn["lod0_tris"] = report
    scn["vehicle_class"] = cls
    scn["wheel_x"] = float(wheel_x)
    game_blend.parent.mkdir(parents=True, exist_ok=True)
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(game_blend))
    print("сохранено:", game_blend)


if __name__ == "__main__":
    main()
