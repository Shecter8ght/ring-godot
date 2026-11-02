"""Вещи общежития, партия 3: файл просмотра текстур — наборы развёртки с картами Painter в студии.

  "D:/ПРОГРАММЫ/Blender 5/blender.exe" --background "<RING_Dorm_Items_uv_v01.blend>" --python-exit-code 1 \
      --python tools/dorm_modules/items3_review.py -- <папка карт> <выход .blend>

Каждое состояние формы — на своём месте из файла формы и уже с текстурами: открытые крышки, лотки, раскрытый чемодан,
вскрытый корпус ПК, закрытый ноутбук, упавшая картина — те же сетки набора в позе из формы (вершины берутся у
соответствующих сеток формы: топология та же, развёртка набора); разбитые стёкла и экраны, полупустая сумка, открытая
коробка, сорванная таблица, листы в тубусе — свои сетки набора. Варианты отделки и печати — копиями: напольное —
рядами впереди, настенное — на стене правее, с подписью кода. Стекло и прозрачный скотч — прозрачные. Форма из файла
удаляется (она в RING_Dorm_Items_v01.blend).
"""
import json
import math
import os
import sys

import bpy
from mathutils import Matrix

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_furniture as B  # noqa: E402
import electrics_uv as E  # noqa: E402
import finish_review as R  # noqa: E402
import items3_uv as U  # noqa: E402
import mlib as L  # noqa: E402

CATALOG = "E:/Games/RING-godot/tools/asset_kit/finish/finishes.json"
WALL = 1.4
# позы без своей развёртки: корни формы, где те же детали стоят иначе
POSES = {"it_ammo": ["ЯП_ящик_патроны_открыт"], "it_zip": ["ЯЗ_ящик_ЗИП_открыт"], "it_trunk": ["МС_сундук_открыт"],
         "it_toolbox": ["ИЯ_ящик_инструменты_открыт"], "it_suitcase": ["ЧМ_чемодан_раскрыт"],
         "it_frame": ["КР_картина_упала"], "it_pc": ["ПК_системный_блок_вскрыт"], "it_laptop": ["НБ_ноутбук_закрыт"]}
SEE = ("Стекло", "Стекло_тёмное", "Скотч_прозрачный")


def slot(ob) -> str:
    return ob.name.split(".")[0].split("__")[0]


def key(ob) -> str:
    return ob.name.split(".")[0]


def seethrough(mat) -> None:
    b = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    b.inputs["Transmission Weight"].default_value = 1.0
    b.inputs["IOR"].default_value = 1.5
    mat.surface_render_method = "DITHERED"


def apply_maps(objs, game, maps_dir) -> None:
    cache = {}
    for ob in objs:
        glass = slot(ob) in SEE
        if glass not in cache:
            m = R.material(f"{os.path.basename(maps_dir)}{'_стекло' if glass else ''}", maps_dir, prefix=game)
            if glass:
                seethrough(m)
            cache[glass] = m
        ob.data.materials.clear()
        ob.data.materials.append(cache[glass])
        for p in ob.data.polygons:
            p.use_smooth = True
        ob.data.set_sharp_from_angle(angle=math.radians(40))


def label(coll, text, at) -> None:
    cu = bpy.data.curves.new(f"подпись {text}", "FONT")
    cu.body = text
    cu.size = 0.05
    cu.align_x = "CENTER"
    t = bpy.data.objects.new(f"подпись {text}", cu)
    coll.objects.link(t)
    t.location = at
    t.data.materials.append(bpy.data.materials.get("Подпись") or L.material("Подпись", (0.9, 0.9, 0.85), 0.6))


def pose_meshes(game, root_name, exclude) -> dict:
    """Сетки корня формы теми же ключами, что у набора (без сдвигов), без деталей exclude (их заменяют свои сетки
    варианта): ключ → объект."""
    spec = U.ITEMS[game][0][2]
    hidden = []
    root = bpy.data.objects[root_name]
    for ob in root.children_recursive:
        if exclude is not None and (not exclude or ob.name.startswith(exclude)) and not ob.hide_render:
            ob.hide_render = True
            hidden.append(ob)
    coll = bpy.data.collections.new("__поза__")
    bpy.context.scene.collection.children.link(coll)
    objs = E.build_item("__поза__", U.resolve([(root_name, None, spec)]), coll)
    for ob in hidden:
        ob.hide_render = False
    return {key(o): o for o in objs}, coll


def posed_copy(base, src, coll, m) -> bpy.types.Object | None:
    """Копия сетки набора в позе src (та же топология): вершины — у src, развёртка и материал — у набора."""
    if src is None or len(src.data.vertices) != len(base.data.vertices) or \
            len(src.data.polygons) != len(base.data.polygons):
        return None
    me = base.data.copy()
    co = [0.0] * (3 * len(src.data.vertices))
    src.data.vertices.foreach_get("co", co)
    me.vertices.foreach_set("co", co)
    me.update()
    ob = bpy.data.objects.new(base.name + " · поза", me)
    coll.objects.link(ob)
    ob.matrix_world = m
    return ob


def drop(coll) -> None:
    for ob in list(coll.objects):
        me = ob.data
        bpy.data.objects.remove(ob)
        if me is not None and me.users == 0:
            bpy.data.meshes.remove(me)
    bpy.data.collections.remove(coll)


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1:]
    maps_root, out = argv[0], argv[1]
    titles = {f["code"]: f["title"] for f in json.load(open(CATALOG, encoding="utf-8"))["finishes"]}
    top = bpy.data.collections["Развёртка_v01"]
    top.hide_viewport = False
    top.hide_render = False
    states = bpy.data.collections.new("Состояния формы")
    bpy.context.scene.collection.children.link(states)
    var_top = bpy.data.collections.new("Варианты отделки и печати")
    bpy.context.scene.collection.children.link(var_top)
    x_wall = max(o.matrix_world.translation.x for o in bpy.data.objects if o.parent is None and o.type == "EMPTY") + 1.0
    for game, spec in U.ITEMS.items():
        coll = bpy.data.collections[game]
        coll.hide_viewport = False
        coll.hide_render = False
        objs = [o for o in coll.objects if o.type == "MESH"]
        maps = os.path.join(maps_root, game)
        if not os.path.exists(os.path.join(maps, f"{game}_baseColor.png")):
            print("нет карт", game, flush=True)
            continue
        root0 = bpy.data.objects[spec[0][0]]
        m0 = root0.matrix_world.copy()
        tags = {t for _, _, t in spec[1:] if isinstance(t, str)}
        base = [o for o in objs if not ("__" in key(o) and key(o).split("__")[-1] in tags)]
        for ob in objs:
            ob.matrix_world = m0
        apply_maps(objs, game, maps)
        # свои сетки вариантов формы — на месте своего корня, остальное — в позе этого корня
        for root_name, prefixes, tag in spec[1:] + [(p, None, None) for p in POSES.get(game, [])]:
            mv = bpy.data.objects[root_name].matrix_world.copy()
            sc = bpy.data.collections.new(f"{game} · {root_name}")
            states.children.link(sc)
            exclude = None if not isinstance(tag, str) else (prefixes or ())
            posed, tmp = pose_meshes(game, root_name, exclude)
            made = []
            for ob in base:
                c = posed_copy(ob, posed.get(key(ob)), sc, mv)
                if c is not None:
                    made.append(c)
            drop(tmp)
            apply_maps(made, game, maps)
            if isinstance(tag, str):
                for ob in objs:
                    if key(ob).endswith("__" + tag):
                        off = U.OFFSETS.get(game, {}).get(key(ob), (0.0, 0.0, 0.0))
                        ob.matrix_world = mv @ Matrix.Translation([-v for v in off])
            print("STATE", game, root_name, len(made), "деталей", flush=True)
        # варианты отделки и печати — копиями
        variants = sorted(d.split("__", 1)[1] for d in os.listdir(maps_root) if d.startswith(game + "__"))
        wall = m0.translation.y > WALL - 0.3 and m0.translation.z > 0.5
        size = max((max(v.co.x for v in o.data.vertices) - min(v.co.x for v in o.data.vertices)) for o in base)
        for k, code in enumerate(variants):
            vc = bpy.data.collections.new(f"{game} · {code} · {titles.get(code, '')}")
            var_top.children.link(vc)
            if wall:
                mv = Matrix.Translation((x_wall + size / 2, m0.translation.y, m0.translation.z)) @ \
                    m0.to_3x3().to_4x4()
                x_wall += size + 0.4
                lab = (mv.translation.x, WALL - 0.4, 0.002)
            elif size < 0.32:
                mv = Matrix.Translation((m0.translation.x + (k - (len(variants) - 1) / 2) * (size + 0.12), -1.0, 0.0)) @ \
                    m0.to_3x3().to_4x4()
                lab = (mv.translation.x, -1.0 - 0.25, 0.002)
            else:
                mv = Matrix.Translation((m0.translation.x, -1.0 - 0.95 * k, 0.0)) @ m0.to_3x3().to_4x4()
                lab = (mv.translation.x, mv.translation.y - 0.4, 0.002)
            copies = []
            for ob in base:
                c = ob.copy()
                c.data = ob.data.copy()
                vc.objects.link(c)
                c.matrix_world = mv
                copies.append(c)
            apply_maps(copies, game, os.path.join(maps_root, f"{game}__{code}"))
            label(vc, code if code not in titles else f"{code} · {titles[code]}", lab)
        print("REVIEW", game, len(objs), "деталей, варианты", variants, flush=True)
    # форма — в своём файле: здесь удаляется (студия остаётся)
    for c in [c for c in bpy.data.collections if c.name.startswith("Партия3_")]:
        for ob in list(c.all_objects):
            bpy.data.objects.remove(ob)
        for sub in list(c.children_recursive):
            bpy.data.collections.remove(sub)
        bpy.data.collections.remove(c)
    span = x_wall + 0.5
    for ob in list(bpy.data.objects):
        if ob.name.startswith(("студия_", "Студия_свет", "Камера_обзор")):
            bpy.data.objects.remove(ob)
    B.studio(L.collection("Студия"), span)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.samples = 128
    for scr in bpy.data.screens:
        for area in scr.areas:
            if area.type == "VIEW_3D":
                for sp in area.spaces:
                    if sp.type == "VIEW_3D":
                        sp.shading.type = "RENDERED"
    bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
    print("saved", out)


if __name__ == "__main__":
    main()
