"""Транспорт «Проспекта»: колёса v2 с отделкой на просмотр — игровая сетка трёх колёс, файлы для Painter, сборка с картами.

    blender --background --factory-startup --python-exit-code 1 --python tools/prospekt_vehicles/wheels_kit.py -- \
        kit <папка Painter> <игровой .blend>
    … wheels_kit.py -- textured <игровой .blend> <папка карт> <выход .blend>

kit — три колеса (колпак и штамповка R15 как у седана, литой R16 как у хэтчбека) дважды: подробно (источник запекания:
протектор и надписи боковины — vwheels.tire_high) и грубо (игровая сетка, развёртка vuv под 1K). Каждое колесо — свой
набор текстур (WheelCap, WheelSteel, WheelAlloy), сетки для Painter — «Набор__материал», как у машин (game_kit). Колёса
стоят вдоль Y через GAP: сцена размером с машину, чтобы масштаб процедурных масок и луч запекания были те же, что в
наборе Wheel машины. textured — карты Painter (glTF: цвет, AO+шероховатость+металл, нормали OpenGL) на игровую сетку: все варианты отделки
(wheel_looks.py — цвет, глянец, износ) рядом, вьюпорт сразу в Material Preview.
"""
from __future__ import annotations

import sys
from pathlib import Path

import bpy
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import vlib  # noqa: E402,F401 — модули купе (wheel, parts)
import vq  # noqa: E402
import vuv  # noqa: E402
import carparts as cp  # noqa: E402
import game_kit as gk  # noqa: E402
import vwheels  # noqa: E402
from specs import CLASSES  # noqa: E402

DESIGNS = [("Колпак", "cap", "sedan", "WheelCap"), ("Штамповка", "steel", "sedan", "WheelSteel"),
           ("Литой", "alloy", "hatch", "WheelAlloy")]
GAP = 3.0
VAR_GAP = 0.85        # м — варианты отделки одного колеса в файле просмотра
RES = 1024


def wheel(style: str, spec: dict) -> list:
    """Детали колеса при текущем качестве vq: шина, обод, тормоз, лицо нового образца."""
    R, W, rim_r = spec["tire_r"], spec["tire_w"], spec["rim_d_in"] * 0.0127
    parts = vwheels.tire(R, W, rim_r, 32)
    # обод — свой материал (та же краска, что у лица диска, но задиры от бордюров — только на его закраине)
    parts.append(("Rim_Barrel", "rim_barrel", *cp.rim_barrel(rim_r, W, 16 if vq.low() else cp.SEG)))
    disc, hat, cal = cp.brake_parts(rim_r)
    parts += [("Brake_Disc", "brake", *disc), ("Brake_Hat", "brake_hat", *hat), ("Caliper", "steel_dark", *cal)]
    return parts + vwheels.face(style, rim_r, W, spec)


def outward(ob) -> None:
    """Нормали наружу: тела вращения wheel.revolve при порядке профиля carparts выходят нормалями внутрь (протектор
    смотрел к оси) — запекание и плотность развёртки по видимости иначе путают стороны; в игре — отсечение изнанки."""
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.to_mesh(ob.data)
    bm.free()


def place(parts, i: int, R: float, col, tag: str, ts: str) -> list:
    objs = []
    for name, mat, V, F in parts:
        # сдвиг — положением объекта, не вершинами: развёртка режет кольца по углу вокруг своей оси X
        ob = gk.mesh_obj(f"{tag}:{name}", np.asarray(V, float), F, col)
        ob.location = (0.0, i * GAP, R)
        ob["tex_set"], ob["mat"], ob["group"] = ts, mat, "wheel"
        gk.triangulate(ob)
        outward(ob)
        gk.smooth_normals(ob)
        objs.append(ob)
    bpy.context.view_layer.update()               # matrix_world по новому положению — до слияния копий для FBX
    return objs


def kit(sp_dir: Path, game_blend: Path) -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sets, hi_objs = {}, []
    scratch = bpy.data.collections.new("_painter")
    bpy.context.scene.collection.children.link(scratch)
    hcol = bpy.data.collections.new("_high")
    bpy.context.scene.collection.children.link(hcol)
    report = {}
    for i, (title, style, cls, ts) in enumerate(DESIGNS):
        spec = CLASSES[cls]
        vq.set_quality("low")
        col = bpy.data.collections.new(title)
        bpy.context.scene.collection.children.link(col)
        objs = place(wheel(style, spec), i, spec["tire_r"], col, style, ts)
        sets[ts] = objs
        uv = vuv.unwrap_set(ts, objs, objs, RES, sp_dir / "uv", f"wheels_{style}")
        tris = sum(len(o.data.polygons) for o in objs)
        vq.set_quality("high")
        hparts = place(wheel(style, spec), i, spec["tire_r"], hcol, style + "_hi", ts)
        htris = sum(len(o.data.polygons) for o in hparts)
        hi_objs.append(gk.merged_copy(hparts, f"{ts}__high", ts, scratch))
        for o in hparts:
            bpy.data.objects.remove(o)
        report[ts] = {"low_tris": tris, "high_tris": htris, **uv}
        print(f"{title}: игровая {tris:,} треугольников, подробная {htris:,}; развёртка {uv}")
    low = gk.export_low(sets, sp_dir / "wheels_low.fbx", scratch)
    for o in hi_objs:
        gk.smooth_normals(o)
    gk.export_fbx(hi_objs, sp_dir / "wheels_high.fbx")
    for o in low + hi_objs:
        bpy.data.objects.remove(o)
    bpy.data.collections.remove(scratch)
    bpy.data.collections.remove(hcol)
    import json
    bpy.context.scene["wheels_report"] = json.dumps(report, ensure_ascii=False)
    game_blend.parent.mkdir(parents=True, exist_ok=True)
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(game_blend))
    print("сохранено:", game_blend)


def _image(path: Path, data: bool):
    img = bpy.data.images.load(str(path), check_existing=True)
    if data:
        img.colorspace_settings.name = "Non-Color"
    return img


def material(ts: str, key: str, maps: Path) -> bpy.types.Material:
    """Материал варианта по картам Painter (пресет glTF, файлы «<набор>_<вариант>_…»): цвет, ORM (R — AO, G —
    шероховатость, B — металл), нормали."""
    m = bpy.data.materials.new(f"SP_{ts}_{key}")
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    col = nt.nodes.new("ShaderNodeTexImage")
    col.image = _image(maps / f"{ts}_{key}_baseColor.png", False)
    nt.links.new(col.outputs["Color"], bsdf.inputs["Base Color"])
    orm = nt.nodes.new("ShaderNodeTexImage")
    orm.image = _image(maps / f"{ts}_{key}_occlusionRoughnessMetallic.png", True)
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(orm.outputs["Color"], sep.inputs["Color"])
    nt.links.new(sep.outputs["Green"], bsdf.inputs["Roughness"])
    nt.links.new(sep.outputs["Blue"], bsdf.inputs["Metallic"])
    nrm = nt.nodes.new("ShaderNodeTexImage")
    nrm.image = _image(maps / f"{ts}_{key}_normal.png", True)
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nt.links.new(nrm.outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    for k, n in enumerate((col, orm, sep, nrm, nm)):
        n.location = (-700 + 150 * (k % 2), 300 - 220 * k)
    return m


def textured(game_blend: Path, maps: Path, out: Path) -> None:
    """Все варианты отделки (wheel_looks) рядом: у каждого колеса — подколлекции вариантов вдоль Y через VAR_GAP,
    первый — на месте игровой сетки, остальные — копии объектов с материалом своего варианта."""
    import wheel_looks
    bpy.ops.wm.open_mainfile(filepath=str(game_blend))
    for title, style, cls, ts in DESIGNS:
        col = bpy.data.collections[title]
        base = [o for o in col.objects if o.type == "MESH" and "tex_set" in o]
        for j, lk in enumerate(wheel_looks.LOOKS[style]):
            sub = bpy.data.collections.new(lk["name"])
            col.children.link(sub)
            mat = material(ts, lk["key"], maps)
            for o in base:
                c = o if j == 0 else o.copy()
                if j:
                    c.location.y += j * VAR_GAP
                    c.name = f"{style}_{lk['key']}:{o.name.split(':', 1)[1]}"
                    c["look"] = lk["key"]
                else:
                    col.objects.unlink(o)
                    o["look"] = lk["key"]
                sub.objects.link(c)
                if not c.material_slots:              # сетка у копий общая — материал варианта на объекте
                    c.data.materials.append(None)
                c.material_slots[0].link = "OBJECT"
                c.material_slots[0].material = mat
    for scr in bpy.data.screens:                  # владелец смотрит сам — сразу с картами
        for ar in scr.areas:
            for sp in ar.spaces:
                if sp.type == "VIEW_3D":
                    sp.shading.type = "MATERIAL"
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(out), relative_remap=True)
    print("сохранено:", out)


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1:]
    if argv[0] == "kit":
        kit(Path(argv[1]), Path(argv[2]))
    elif argv[0] == "textured":
        textured(Path(argv[1]), Path(argv[2]), Path(argv[3]))


if __name__ == "__main__":
    main()
