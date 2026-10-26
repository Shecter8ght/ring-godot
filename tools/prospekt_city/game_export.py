"""«Проспект», ограждения и город: игровые варианты → glTF в игру и индекс моделей.

    blender --background --factory-startup --python-exit-code 1 --python tools/prospekt_city/game_export.py -- \
        <модуль> <игровой .blend (game_apply.py)> [вариант …]

Каждый вариант («LOD0 | …», корень с model_id) сводится в одну сетку (MallFiller берёт первую MeshInstance3D сцены;
поверхности — по материалам) в осях варианта и выгружается в assets/models/prospekt_city/<ID>.gltf (+ .bin, карты WebP
не больше 2K в textures/ — общие для вариантов одного набора). Индекс — data/urban95_models.json (общий с Urban 95:
MallFiller и tools/build_prospekt.py читают один файл; чужие записи не трогаются): габарит в игровых осях, число
треугольников, ящики коллизии GAME["solids"] модуля (если заданы — вместо габарита), уровни детализации GAME["lods"]
(вариант → [(вариант-уровень, дальность конца), …] от ближнего к дальнему).
"""
from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import bmesh
import bpy

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
OUT = ROOT / "assets" / "models" / "prospekt_city"
INDEX = ROOT / "data" / "urban95_models.json"
MAX_TEX = 2048


def gcoords(c) -> list:
    """Blender (x, y, z) → игра (x, z, −y)."""
    return [round(c[0], 4), round(c[2], 4), round(-c[1], 4)]


def flatten(col: bpy.types.Collection, root: bpy.types.Object, name: str) -> bpy.types.Object:
    inv = root.matrix_world.inverted()
    bm = bmesh.new()
    mats: list = []
    for o in col.objects:
        if o.type != "MESH":
            continue
        me = o.data.copy()
        me.transform(inv @ o.matrix_world)
        if (inv @ o.matrix_world).determinant() < 0:
            me.flip_normals()
        remap = []
        for m in me.materials:
            if m not in mats:
                mats.append(m)
            remap.append(mats.index(m))
        for p in me.polygons:
            p.material_index = remap[p.material_index] if remap else 0
        bm.from_mesh(me)
        bpy.data.meshes.remove(me)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for m in mats:
        me.materials.append(m)
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1:]
    mod = importlib.import_module(argv[0])
    bpy.ops.wm.open_mainfile(filepath=argv[1])
    wanted = set(argv[2:])
    for img in bpy.data.images:
        if img.size[0] > MAX_TEX or img.size[1] > MAX_TEX:
            k = MAX_TEX / max(img.size[0], img.size[1])
            img.scale(int(img.size[0] * k), int(img.size[1] * k))
    index = json.loads(INDEX.read_text(encoding="utf-8")) if INDEX.exists() else {"_comment": "", "models": {}}
    OUT.mkdir(parents=True, exist_ok=True)
    solids = mod.GAME.get("solids", {})
    lods = mod.GAME.get("lods", {})
    cells = mod.GAME.get("cells", {})
    for col in list(bpy.context.scene.collection.children):
        roots = [o for o in col.objects if o.type == "EMPTY" and o.get("model_id")]
        if not roots:
            continue
        root = roots[0]
        mid, key = root["model_id"], root["variant"]
        if wanted and mid not in wanted and key not in wanted:
            continue
        ob = flatten(col, root, mid)
        ob.data.calc_loop_triangles()
        tris = len(ob.data.loop_triangles)
        xs = [v.co.x for v in ob.data.vertices]
        ys = [v.co.y for v in ob.data.vertices]
        zs = [v.co.z for v in ob.data.vertices]
        lo, hi = (min(xs), min(zs), -max(ys)), (max(xs), max(zs), -min(ys))
        bpy.ops.object.select_all(action="DESELECT")
        ob.select_set(True)
        bpy.context.view_layer.objects.active = ob
        bpy.ops.export_scene.gltf(filepath=str(OUT / f"{mid}.gltf"), export_format="GLTF_SEPARATE",
                                  export_texture_dir="textures", use_selection=True, export_apply=True, export_yup=True,
                                  export_texcoords=True, export_normals=True, export_tangents=False,
                                  export_materials="EXPORT", export_image_format="WEBP", export_image_quality=90,
                                  export_cameras=False, export_lights=False, export_animations=False)
        title = mod.VARIANTS.get(key) or mod.GAME.get("extra", {}).get(key, key)
        info = {"id": mid, "name": f"{mod.META['title']} · {title}", "file": f"res://assets/models/prospekt_city/{mid}.gltf",
                "triangles": tris, "materials": len(ob.data.materials),
                "aabb": {"center": [round((lo[i] + hi[i]) * 0.5, 4) for i in range(3)],
                         "size": [round(hi[i] - lo[i], 4) for i in range(3)]},
                "root_offset": [0, 0, 0], "source": "tools/prospekt_city"}
        if key in solids:
            info["solids"] = [[gcoords(c), [round(s[0], 4), round(s[2], 4), round(s[1], 4)]] for c, s in solids[key]]
        if key in lods:
            # уровни детализации (MallFiller: [{file, end}] от ближнего к дальнему) — другие варианты того же модуля
            info["lods"] = [{"file": f"res://assets/models/prospekt_city/{mod.GAME['ids'][k]}.gltf", "end": float(end)}
                            for k, end in lods[key]]
        if key in cells:
            info["cell"] = float(cells[key])     # клетка пачки: дальность уровней считается от её центра
        index["models"][mid] = info
        print(f"glTF {mid}: {tris} треугольников, материалов {len(ob.data.materials)}, габарит {info['aabb']['size']}")
        bpy.data.objects.remove(ob, do_unlink=True)
    # индекс общий с другими сессиями (транспорт, растения): перечитать свежий, добавить свои записи, записать;
    # запись иногда отказывает (Errno 22 — файл занят другой записью) — повторить
    import time
    mine = {k: v for k, v in index["models"].items() if v.get("source") == "tools/prospekt_city"}
    for attempt in range(10):
        try:
            fresh = json.loads(INDEX.read_text(encoding="utf-8")) if INDEX.exists() else {"_comment": "", "models": {}}
            fresh["models"].update(mine)
            INDEX.write_text(json.dumps(fresh, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
            break
        except OSError as e:
            print("индекс занят, повтор:", e)
            time.sleep(1.0 + attempt)


main()
