"""Мебель общежития: варианты отделки в файле просмотра этапа 1 — после finish_review.py (тот же файл).

  "D:/ПРОГРАММЫ/Blender 5/blender.exe" --background "<RING_Dorm_Furniture_textured_v01.blend>" --python-exit-code 1 \
      --python tools/dorm_modules/furniture_review.py -- <папка карт>

Варианты (variants слотов finish-spec.json, выгрузка furniture_sp.py variants → <папка карт>/<предмет>__<код>) — копии
предмета рядами перед ним (по 2,4 м к зрителю), с подписью на полу: код и название отделки. Пол студии вытягивается.
"""
import json
import os
import sys

import bpy
from mathutils import Matrix

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import finish_review as R  # noqa: E402

CATALOG = "E:/Games/RING-godot/tools/asset_kit/finish/finishes.json"
STEP = 2.4


def main() -> None:
    maps_root = sys.argv[sys.argv.index("--") + 1]
    titles = {f["code"]: f["title"] for f in json.load(open(CATALOG, encoding="utf-8"))["finishes"]}
    top = bpy.data.collections.get("Варианты отделки")
    if top is None:
        top = bpy.data.collections.new("Варианты отделки")
        bpy.context.scene.collection.children.link(top)
    for c in list(top.children):
        for ob in list(c.objects):
            bpy.data.objects.remove(ob)
        bpy.data.collections.remove(c)
    rows = 0
    for game_coll in bpy.data.collections["Развёртка_v01"].children:
        game = game_coll.name
        variants = sorted(d.split("__", 1)[1] for d in os.listdir(maps_root) if d.startswith(game + "__"))
        for k, code in enumerate(variants):
            coll = bpy.data.collections.new(f"{game} · {code}")
            top.children.link(coll)
            shift = Matrix.Translation((0.0, -STEP * (k + 1), 0.0))
            maps_dir = os.path.join(maps_root, f"{game}__{code}")
            mat = None
            xs = []
            for ob in game_coll.objects:
                if ob.type != "MESH":
                    continue
                new = ob.copy()
                new.data = ob.data.copy()
                coll.objects.link(new)
                new.matrix_world = shift @ ob.matrix_world
                low = ob.name.lower()
                if not any(key in low for key in R.GLASS + R.GLOW):
                    mat = mat or R.material(f"{game}__{code}", maps_dir, prefix=game)
                    new.data.materials.clear()
                    new.data.materials.append(mat)
                xs.append(new.matrix_world.translation)
            # подпись на полу перед предметом
            cu = bpy.data.curves.new(f"подпись {game} {code}", "FONT")
            # код — коротко (соседние подписи не налезают), название — в имени коллекции
            cu.body = code
            cu.size = 0.06
            coll.name = f"{game} · {code} · {titles.get(code, '')}"
            cu.align_x = "CENTER"
            txt = bpy.data.objects.new(f"подпись {game} {code}", cu)
            coll.objects.link(txt)
            c = xs[0] if xs else shift.translation
            txt.location = (c.x, c.y - 1.15, 0.002)
            txt.data.materials.append(bpy.data.materials.get("Подпись") or _label_mat())
            rows = max(rows, k + 1)
            print("VARIANT", game, code, flush=True)
    floor = bpy.data.objects.get("студия_пол")
    if floor is not None and rows:
        lo = -3.0 - STEP * rows
        for v in floor.data.vertices:
            if v.co.y < -2.0:
                v.co.y = lo
    bpy.ops.wm.save_mainfile(compress=True)
    print("saved", bpy.data.filepath)


def _label_mat():
    m = bpy.data.materials.new("Подпись")
    m.use_nodes = True
    b = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    b.inputs["Base Color"].default_value = (0.9, 0.85, 0.3, 1.0)
    b.inputs["Roughness"].default_value = 0.6
    return m


if __name__ == "__main__":
    main()
