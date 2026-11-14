"""Модели Sketchfab (CC-BY), скачанные владельцем, → игровые GLB для зоны 1. bpy.

"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python tools/import_sketchfab.py [-- имя ...]

Исходники: _asset_src/Zone01/Sketchfab/<статус>/<категория>/<модель>/gltf/scene.gltf (распаковывает
tools/sketchfab_library.py). Здесь для каждой модели: взять нужные объекты, привести к реальному
размеру (сканы часто в сантиметрах), упростить тяжёлый скан до бюджета, срезать «землю» под сканом,
поставить основание в ноль (центр по X/Z, низ по Y), экспорт GLB с текстурами внутри.
Пишет assets/zone01/models/sf_<имя>.glb и assets/zone01/models/sketchfab.json (размеры, коллизии,
автор, лицензия, ссылка — их же берёт CREDITS и список библиотеки).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "_asset_src/Zone01/Sketchfab"
OUT = ROOT / "assets/zone01/models"

# имя в игре: (папка-модель в библиотеке, фильтр объектов (подстроки, пусто — все), ось и размер, м,
#              бюджет треугольников, срезать землю под сканом, м от низа)
MODELS = {
    "vaz2104": ("ВАЗ 2104 скан", [], ("x", 4.2), 60000, 0.0),
    # -1 — срезать плиту земли под сканом автоматически (по высоте её верха)
    "car_burned": ("Сгоревшая машина", [], ("x", 4.3), 80000, -1.0),
    "dumpster_a": ("Мусорный бак зелёный", ["=trash_can_finish_trash_can_mat_0", "=cap_trash_can_mat_0"] +
                   [f"=wheel_{i}_trash_can_mat_0" for i in range(1, 5)], ("y", 1.3), 8000, 0.0),
    "dumpster_b": ("Мусорный бак зелёный", ["=trash_can_finish_trash_can_mat_0.001", "=cap_trash_can_mat_0.001"] +
                   [f"=wheel_{i}_trash_can_mat_0.001" for i in range(1, 5)], ("y", 1.3), 8000, 0.0),
    "dumpster_tipped": ("Мусорный бак зелёный", ["=trash_can_finish1_trash_can_mat_0", "=cap1_trash_can_mat_0"] +
                        [f"=wheel_{i}_trash_can_mat_0" for i in range(5, 9)], None, 8000, 0.0),
    "dead_tree": ("Сухое дерево", ["Object_2"], ("y", 7.5), 20000, 0.0),
    "wood_block": ("Деревянный брусок", [], None, 1000, 0.0),
    "garage_row": ("Гаражи кирпичные", [], None, 5000, 0.0),
    "panel12": ("Панельная 12 этажей", ["LOD0"], None, 8000, 0.0),
    "panel5_brutal": ("Панельная 5 этажей", ["Object_5"], ("y", 16.0), 20000, 0.0),
    # снаряжение (ItemModels: иконки, предметы на полу): плитоносец ~52 см по высоте
    "plate_carrier": ("Плитник", [], ("y", 0.52), 20000, 0.0),
}


def find_source(label: str) -> Path | None:
    for meta in LIB.rglob("_модель.json"):
        info = json.loads(meta.read_text(encoding="utf-8"))
        if info.get("name") == label:
            return meta.parent
    return None


def extent(obj) -> tuple[Vector, Vector]:
    """Рамка по вершинам (bound_box после правки меша бывает устаревшей)."""
    vs = [v.co for v in obj.data.vertices]
    return (Vector((min(v.x for v in vs), min(v.y for v in vs), min(v.z for v in vs))),
            Vector((max(v.x for v in vs), max(v.y for v in vs), max(v.z for v in vs))))


def tris(o) -> int:
    return sum(len(p.vertices) - 2 for p in o.data.polygons)


def build(name: str, spec: tuple) -> dict | None:
    label, picks, size, budget, cut = spec
    src = find_source(label)
    if src is None or not (src / "gltf/scene.gltf").exists():
        print("SKETCHFAB нет исходника", name, label, flush=True)
        return None
    info = json.loads((src / "_модель.json").read_text(encoding="utf-8"))
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(src / "gltf/scene.gltf"))
    objs = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    if picks:
        # «=имя» — точное имя объекта, иначе подстрока
        objs = [o for o in objs if any(o.name == p[1:] if p.startswith("=") else p in o.name for p in picks)]
    for o in list(bpy.context.scene.objects):
        if o not in objs and o.type == "MESH":
            bpy.data.objects.remove(o, do_unlink=True)
    # трансформы иерархии — в вершины, родители-пустышки прочь
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    for o in list(bpy.context.scene.objects):
        if o.type != "MESH":
            bpy.data.objects.remove(o, do_unlink=True)
    if len(objs) > 1:
        bpy.ops.object.join()
    obj = bpy.context.view_layer.objects.active
    obj.name = f"sf_{name}"
    # реальный размер: Blender Z — вверх; «y» в описании — высота
    lo, hi = extent(obj)
    dims = {"x": hi.x - lo.x, "z": hi.y - lo.y, "y": hi.z - lo.z}
    if size:
        k = size[1] / max(dims[size[0]], 1e-6)
        obj.data.transform(Matrix.Scale(k, 4))
    # срез земли под сканом (плита, на которой стоит машина): cut < 0 — верх плиты ищется сам как
    # самая частая высота почти горизонтальных граней в нижних 40 см
    if cut < 0.0:
        zmin = min(v.co.z for v in obj.data.vertices)
        bins: dict[int, float] = {}
        for poly in obj.data.polygons:
            if poly.normal.z > 0.9 and poly.center.z < zmin + 0.4:
                k = int((poly.center.z - zmin) / 0.02)
                bins[k] = bins.get(k, 0.0) + poly.area
        top = (max(bins, key=bins.get) + 1) * 0.02 if bins else 0.0
        cut = top + 0.04
        print("SKETCHFAB срез плиты", name, round(cut, 3), flush=True)
    if cut > 0.0:
        zmin = min(v.co.z for v in obj.data.vertices)
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        kill = [f for f in bm.faces if max(v.co.z for v in f.verts) < zmin + cut]
        bmesh.ops.delete(bm, geom=kill, context="FACES")
        bm.to_mesh(obj.data)
        bm.free()
    if tris(obj) > budget:
        m = obj.modifiers.new("dec", "DECIMATE")
        m.ratio = budget / tris(obj)
        bpy.ops.object.modifier_apply(modifier="dec")
    lo, hi = extent(obj)
    obj.data.transform(Matrix.Translation((-(lo.x + hi.x) * 0.5, -(lo.y + hi.y) * 0.5, -lo.z)))
    lo, hi = extent(obj)
    sx, sz, sy = hi.x - lo.x, hi.y - lo.y, hi.z
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.ops.export_scene.gltf(filepath=str(OUT / f"sf_{name}.glb"), export_format="GLB", use_selection=True,
                              export_yup=True, export_texcoords=True, export_normals=True, export_materials="EXPORT",
                              export_image_format="AUTO", export_animations=False)
    n = tris(obj)
    print("SKETCHFAB", name, n, [round(sx, 2), round(sy, 2), round(sz, 2)], flush=True)
    return dict(triangles=n, size=[round(sx, 2), round(sy, 2), round(sz, 2)],
                collisions=[dict(pos=[0, round(sy * 0.5, 3), 0], size=[round(sx * 0.92, 3), round(sy, 3), round(sz * 0.92, 3)], yaw=0)],
                title=info.get("title"), author=info.get("author"), license=info.get("license"), source=info.get("url"),
                library=info.get("name"))


def main() -> None:
    only = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    path = OUT / "sketchfab.json"
    manifest = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    for name, spec in MODELS.items():
        if only and name not in only:
            continue
        r = build(name, spec)
        if r:
            manifest[f"sf_{name}"] = r
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


main()
