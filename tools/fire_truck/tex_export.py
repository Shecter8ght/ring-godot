"""Пожарная АЦ: выгрузка развёрнутой формы для Substance Painter.

- Проекты Painter (`PROJECTS`): по 3–4 набора текстур, чтобы видеопамяти (RTX 4050, 6 ГБ) хватало на стек; в FBX
  проекта — по одной детали на сетку (связанные копии и двери «открыто» — та же сетка, развёртка общая).
- Для запекания затенённости — вся машина «high» своим вариантом: `high_closed.fbx` («Целая») и `high_open.fbx`
  («Отсеки открыты»), без стёкол и линз (иначе салон и отсеки чернеют). Сетка та же, что у проекта: нормаль не
  запекается, затенённость и кривизна — с учётом соседних узлов.

blender --background <FireTanker_uv_v01.blend> --factory-startup --python-exit-code 1 --python
    tools/fire_truck/tex_export.py -- [проект,проект] [high]
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

import tex_sets as T  # noqa: E402

PROJECTS, HIGH_OF = T.PROJECTS, T.HIGH_OF
CLOSED, OPEN = "Целая", "Отсеки открыты"
OUT = T.SP


def slot(o) -> str:
    """Слот отделки — заново по правилам tex_sets (их правят после развёртки); половины кузова — из свойства."""
    if T.base_name(o.name) in ("body_L", "body_R", "top_band_L", "top_band_R"):
        return o.get("ft_slot", "paint_red")
    return T.slot_of(o.name, o.get("ft_mat", ""), o.get("ft_set", ""))


def export(objs, path: str) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.hide_set(False)
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.export_scene.fbx(filepath=path, use_selection=True, object_types={"MESH"}, apply_unit_scale=True,
                             apply_scale_options="FBX_SCALE_UNITS", use_mesh_modifiers=False, mesh_smooth_type="FACE",
                             use_tspace=True, axis_forward="-Z", axis_up="Y", bake_space_transform=False,
                             path_mode="STRIP", embed_textures=False)
    print("FBX", path, len(objs), flush=True)


def main():
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    only = a[0].split(",") if a and a[0] else list(PROJECTS)
    do_high = "high" in a[1:] or not a
    os.makedirs(OUT, exist_ok=True)
    # всё раскрыть: скрытую коллекцию «Отсеки открыты» выгрузка не может выделить, и её детали пропадали из FBX
    def walk(lc):
        lc.exclude = False
        lc.hide_viewport = False
        for ch in lc.children:
            walk(ch)
    walk(bpy.context.view_layer.layer_collection)
    for c in bpy.data.collections:
        c.hide_viewport = False
        c.hide_select = False
    for o in bpy.data.objects:
        o.hide_viewport = False
        o.hide_select = False
        o.hide_set(False)
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    # одна деталь на сетку: предпочтительно из «Целой» (двери закрыты)
    first = {}
    for o in sorted(meshes, key=lambda o: (CLOSED not in [c.name for c in o.users_collection], o.name)):
        first.setdefault(o.data.name, o)
    info_path = f"{OUT}/meshes.json"
    info = json.load(open(info_path, encoding="utf-8")) if os.path.exists(info_path) else {}
    for proj in only:
        sets = PROJECTS[proj]
        objs = [o for o in first.values() if o.get("ft_set") in sets]
        export(objs, f"{OUT}/{proj}.fbx")
        # для стека Painter: деталь → слот отделки по наборам, наибольший размер сцены проекта (мм) — масштаб
        # трёхпроекционных узоров у Painter считается от него
        pts = []
        for o in objs:
            for c in o.bound_box:
                pts.append(o.matrix_world @ Vector(c))
        size = max(max(q[i] for q in pts) - min(q[i] for q in pts) for i in range(3)) * 1000.0
        info[proj] = {"bbox_mm": round(size, 1),
                      "sets": {st: {o.name: slot(o) for o in objs if o.get("ft_set") == st} for st in sets}}
    with open(info_path, "w", encoding="utf-8", newline=chr(10)) as f:
        json.dump(info, f, ensure_ascii=False, indent=1)
    if do_high:
        for var, coll in (("closed", CLOSED), ("open", OPEN)):
            names = {o.name for o in bpy.data.collections[coll].all_objects}
            objs = [o for o in meshes if o.name in names and o.get("ft_set") != "glass"]
            export(objs, f"{OUT}/high_{var}.fbx")


if __name__ == "__main__":
    main()
