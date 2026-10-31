"""Транспорт «Проспекта»: игровая сетка LOD0 и файлы для Substance Painter.

    blender --background --factory-startup --python-exit-code 1 --python tools/prospekt_vehicles/game_kit.py -- \
        <класс> <папка Painter> <игровой .blend> [семьи через запятую]
    … game_kit.py -- fbx <папка Painter> <игровой .blend>      — только FBX игровой сетки из готового .blend

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
import vuv  # noqa: E402
from specs import CLASSES  # noqa: E402
from specs_bus import BOXES  # noqa: E402

INTERIOR = ("Dashboard", "Instrument_Hood", "Center_Stack", "Center_Screen", "Steering_", "Seat", "Headrest", "Console",
            "Floor", "Headliner", "Door_Card", "Parcel_Shelf", "Cargo_Cover", "Visor", "Mirror_Inner", "Trunk_Tub",
            "Trunk_Wall", "Sill_Tread", "Dash_Beam", "Driver_", "Dash", "Passenger_", "Handrails", "Ceiling", "Step_",
            # партия 2: кабина и отсек фургона и скорой
            "Cab_", "Partition_", "Wheel_Boxes", "Cargo_", "Stretcher_", "Med_", "Oxygen")
UNDER = ("Liner_", "Under_Tray", "Exhaust", "Frame", "Rear_Axle", "Fuel_Tank", "Rear_Springs", "Mudflap",
         # низ перевёрнутого автобуса (build_bus.underbody)
         "Front_Axle", "Knuckles", "Tie_Rod", "Air_Bags", "Shocks", "Engine_Sump", "Muffler", "Air_Tanks")
GLASS_MATS = ("glass", "lamp_glass", "lamp_red", "glass_broken", "display", "lamp_blue")
SET_RES = {"Body": 11, "Interior": 10, "Wheel": 10, "Under": 9}


def set_res(cls: str, ts: str) -> int:
    """Размер карты набора, пикс (как RES в sp_family.sh): у автобуса салон 2K, у коробчатых низ 1K."""
    if ts.startswith("Body"):
        return 2048
    if ts == "Interior":
        return 2048 if cls == "bus12" else 1024
    if ts == "Under":
        return 1024 if cls in BOXES else 512
    return 1024
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

    kit, hinges, S, (field, surf, views) = bc.build_kit(spec)
    wreck = bc.make_wreck(kit, spec, field, surf, views, S)
    burnt, dz = bc.make_burnt(kit, spec, field, surf, views, S)
    if spec.get("special"):
        # такси и полиция: навесное на крыше этой же сборки (подробной и игровой — по своей крыше); у битого такси
        # плафон опрокинут; сгоревших нет
        import vspecial
        kit = vspecial.add_to_kit(kit, spec["special"])
        wreck = vspecial.add_to_kit(wreck, spec["special"], knocked=spec["special"] == "taxi")
    return {"clean": (kit, cp.wheel_parts(spec, "clean")), "wreck": (wreck, cp.wreck_wheel(spec)),
            "burnt": (burnt, cp.burnt_wheel(spec))}, hinges, dz


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
    if spec.get("overturned"):
        # перевёрнутый автобус: деформация одним полем по координатам — подробная и игровая совпадают
        return {"over": (bb.overturned(parts, spec, S, surf), vbus.truck_wheel(spec))}, hinges, 0.0
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


def material(name: str, rgb=(0.5, 0.5, 0.5)) -> bpy.types.Material:
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.diffuse_color = (*rgb, 1.0)
    return m


def outward(ob) -> None:
    """Нормали наружу: тела вращения wheel.revolve при порядке профиля carparts выходят нормалями внутрь (протектор
    смотрел к оси) — запекание и плотность развёртки по видимости путали стороны, в игре — отсечение изнанки."""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.to_mesh(ob.data)
    bm.free()


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
        outward(ob)
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


def export_low(sets: dict, path: Path, scratch) -> list:
    """FBX игровой сетки для Painter: слитые копии по (набор, материал детали) — по имени сетки Painter маскирует слои;
    краска кузова — по панелям («Body__paint__Hood»): панели разводятся оттенком и блеском (справка навыка)."""
    low_objs = []
    for ts, objs in sets.items():
        if ts == "Glass":
            continue
        bymat: dict = {}
        for o in objs:
            key = o["mat"]
            if ts.startswith("Body") and key == "paint":
                key = "paint__" + o.name.split(":", 1)[1]
            bymat.setdefault(key, []).append(o)
        for mat, group in bymat.items():
            low_objs.append(merged_copy(group, f"{ts}__{mat}", ts, scratch))
    for o in low_objs:
        smooth_normals(o)                         # слитые копии — заново (bmesh теряет пометки)
    export_fbx(low_objs, path)
    return low_objs


def fbx_only(sp_dir: Path, game_blend: Path) -> None:
    """Режим «fbx»: только перевыгрузка игровой сетки для Painter из готового .blend (развёртка и сетка не меняются)."""
    bpy.ops.wm.open_mainfile(filepath=str(game_blend))
    scratch = bpy.data.collections.new("_painter")
    bpy.context.scene.collection.children.link(scratch)
    for col in [c for c in bpy.data.collections if c.name.startswith("LOD0_")]:
        sets: dict = {}
        for o in col.objects:
            sets.setdefault(o["tex_set"], []).append(o)
        export_low(sets, sp_dir / f"{col.name[5:]}_low.fbx", scratch)
        print("FBX", col.name[5:], "сеток", sum(1 for _ in scratch.objects))
        for o in list(scratch.objects):
            bpy.data.objects.remove(o)


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1:]
    if argv[0] == "fbx":                          # game_kit.py -- fbx <папка Painter> <игровой .blend>
        fbx_only(Path(argv[1]), Path(argv[2]))
        return
    cls, sp_dir, game_blend = argv[0], Path(argv[1]), Path(argv[2])
    box = cls in BOXES
    spec = BOXES[cls] if box else CLASSES[cls]
    only = argv[3].split(",") if len(argv) > 3 else \
        (["over"] if spec.get("overturned") else ["clean"]) if box else \
        (["clean", "wreck"] if spec.get("special") else ["clean", "wreck", "burnt"])
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
    uv_report: dict = {}
    for fam in only:
        col = bpy.data.collections.new(f"LOD0_{fam}")
        bpy.context.scene.collection.children.link(col)
        sets = build_family(fam, lo[fam][0], lo[fam][1], col, wheel_x, split)
        fam_objs = [o for objs in sets.values() for o in objs]
        for ts, objs in sets.items():
            if ts == "Glass":
                continue
            uv_report[f"{fam}:{ts}"] = vuv.unwrap_set(ts, objs, fam_objs, set_res(cls, ts), sp_dir / "uv", f"{fam}_{ts}")
        n_wheels = (6 if spec.get("dual_rear") else 4) if box else 4
        tris = sum(len(o.data.polygons) for objs in sets.values() for o in objs if o["group"] != "wheel") + \
            n_wheels * sum(len(o.data.polygons) for o in sets.get("Wheel", []))
        report[fam] = tris
        print(f"LOD0 {fam}: треугольников {tris:,} (с колёсами: {n_wheels})")
        top = sorted(((len(o.data.polygons), o.name) for objs in sets.values() for o in objs), reverse=True)[:30]
        print("  самые тяжёлые:", ", ".join(f"{n.split(':', 1)[1]} {c}" for c, n in top))
        low_objs = export_low(sets, sp_dir / f"{fam}_low.fbx", scratch)
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
    scn["uv_report"] = json.dumps(uv_report, ensure_ascii=False)
    scn["wheel_x"] = float(wheel_x)
    game_blend.parent.mkdir(parents=True, exist_ok=True)
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(game_blend))
    print("сохранено:", game_blend)


if __name__ == "__main__":
    main()
