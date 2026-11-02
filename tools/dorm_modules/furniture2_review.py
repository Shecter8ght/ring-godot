"""Мебель общежития, партия 2: файл просмотра текстур — наборы развёртки с картами Painter в студии.

  "D:/ПРОГРАММЫ/Blender 5/blender.exe" --background "<RING_Dorm_Furniture2_uv_v01.blend>" --python-exit-code 1 \
      --python tools/dorm_modules/furniture2_review.py -- <папка карт> <выход .blend>

Предметы — в ряд по оси X; плита, тумбы, раковина, унитаз, кабинка — у стены студии, шкафчик, полка и зеркало — на
ней, кастрюля и чайник — на конфорках, сковорода — на столе-тумбе; варианты отделки — копиями правее основного
с подписью кода на полу. Ещё копии: плита с откинутой дверцей (камера духовки), раковина с отбитым углом. Стекло
дверцы духовки — прозрачное; зеркало — металл из карт (GL-MIR).
"""
import json
import math
import os
import sys

import bpy
from mathutils import Matrix, Vector as V

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_furniture as B  # noqa: E402
from furniture2_uv import OFFSETS  # noqa: E402
import finish_review as R  # noqa: E402
import mlib as L  # noqa: E402

CATALOG = "E:/Games/RING-godot/tools/asset_kit/finish/finishes.json"
WALL = 1.4                       # стена студии (build_furniture.studio)
# набор: (как стоит: «floor» — середина опоры на полу, «counter» — задом к стене, «wall_hung» — середина верха у стены
# на высоте, «wall_floor» — на полу у стены), ширина места по X, высота подвеса
PLACE = {"furn_stove": ("counter", 0.6, 0), "furn_sink": ("counter", 0.9, 0), "furn_counter": ("counter", 0.9, 0),
         "furn_dining": ("floor", 1.3, 0), "furn_wallcab": ("wall_hung", 0.9, 1.75), "furn_dishrack": ("wall_hung", 0.9, 1.75),
         "furn_can": ("floor", 0.35, 0), "furn_bucket": ("floor", 0.4, 0),
         "furn_basin": ("wall_floor", 0.7, 0), "furn_mirror": ("wall_hung", 0.55, 1.6),
         "furn_toilet": ("wall_floor", 0.6, 0), "furn_stall": ("wall_floor", 1.3, 0)}
# посуда — на других предметах (набор, смещение от его корня)
ON = {"furn_pot": ("furn_stove", (-0.11, -0.1, 0.862)), "furn_kettle": ("furn_stove", (0.11, 0.12, 0.862)),
      "furn_pan": ("furn_counter", (0.05, -0.05, 0.852))}
DEPTH = {"furn_stove": 0.6, "furn_sink": 0.6, "furn_counter": 0.6}
STALL_HALF = 0.55                # крайняя перегородка — правая стенка кабинки (в форме у неё свой корень)
OVEN_HINGE = (-0.3 + 0.02, 0.2)  # ось дверцы духовки: y лица корпуса, z низа дверцы (build_furniture2.stove)


def seethrough(mat) -> None:
    b = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    b.inputs["Transmission Weight"].default_value = 1.0
    b.inputs["IOR"].default_value = 1.5
    b.inputs["Roughness"].default_value = 0.03
    for lnk in list(b.inputs["Roughness"].links):
        mat.node_tree.links.remove(lnk)
    mat.surface_render_method = "DITHERED"


def apply_maps(objs, game, maps_dir, prefix=None, code=None) -> None:
    cache = {}
    for ob in objs:
        key = "glass" if ob.name.split(".")[0].split("__")[0] == "Стекло" else ""
        if key not in cache:
            m = R.material(f"{game}{'__' + code if code else ''}{'_стекло' if key else ''}", maps_dir, prefix=prefix)
            if key:
                seethrough(m)
            cache[key] = m
        ob.data.materials.clear()
        ob.data.materials.append(cache[key])
        for p in ob.data.polygons:
            p.use_smooth = True
        ob.data.set_sharp_from_angle(angle=math.radians(40))


def label(coll, text, at):
    cu = bpy.data.curves.new(f"подпись {text}", "FONT")
    cu.body = text
    cu.size = 0.06
    cu.align_x = "CENTER"
    t = bpy.data.objects.new(f"подпись {text}", cu)
    coll.objects.link(t)
    t.location = at
    t.data.materials.append(bpy.data.materials.get("Подпись") or L.material("Подпись", (0.9, 0.9, 0.85), 0.6))


def placement(game, x) -> Matrix:
    how, _, z = PLACE[game]
    if how == "counter":
        return Matrix.Translation((x, WALL - DEPTH[game] / 2, 0))
    if how == "wall_hung":
        return Matrix.Translation((x, WALL, z))
    if how == "wall_floor":
        return Matrix.Translation((x, WALL, 0))
    return Matrix.Translation((x, 0.0, 0))


def local_fix(ob) -> Matrix:
    """Поправка детали внутри набора: сдвиг на время текстур (furniture2_uv.OFFSETS) обратно; крайняя перегородка —
    справа у кабинки."""
    name = ob.name.split(".")[0]
    for offs in OFFSETS.values():
        if name in offs:
            back = Matrix.Translation([-v for v in offs[name]])
            return Matrix.Translation((STALL_HALF, 0, 0)) @ back if name.endswith("__крайняя") else back
    return Matrix.Identity(4)


def copy_set(objs, coll, m, keep=lambda o: True):
    out = []
    for ob in objs:
        if not keep(ob):
            continue
        new = ob.copy()
        new.data = ob.data.copy()
        coll.objects.link(new)
        new.matrix_world = m @ local_fix(ob)
        out.append(new)
    return out


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1:]
    maps_root, out = argv[0], argv[1]
    titles = {f["code"]: f["title"] for f in json.load(open(CATALOG, encoding="utf-8"))["finishes"]}
    keep_names = set(PLACE) | set(ON)
    for o in list(bpy.data.objects):
        if not any(c.name in keep_names or c.name == "Развёртка_v01" for c in o.users_collection):
            bpy.data.objects.remove(o)
    top = bpy.data.collections["Развёртка_v01"]
    top.hide_viewport = False
    top.hide_render = False
    var_top = bpy.data.collections.new("Варианты отделки")
    bpy.context.scene.collection.children.link(var_top)
    roots = {}
    x = 0.0

    def base_keep(o):
        n = o.name.split(".")[0]
        return not (n.endswith("__отбита") or n.endswith("__оборвана"))

    for game in PLACE:
        coll = bpy.data.collections[game]
        coll.hide_viewport = False
        coll.hide_render = False
        objs = [o for o in coll.objects if o.type == "MESH"]
        width = PLACE[game][1]
        m = placement(game, x + width / 2)
        roots[game] = m
        for ob in objs:
            ob.matrix_world = m @ local_fix(ob)
            ob.hide_render = not base_keep(ob)
            ob.hide_set(not base_keep(ob))
        apply_maps(objs, game, os.path.join(maps_root, game))
        x += width + 0.3
        variants = sorted(d.split("__", 1)[1] for d in os.listdir(maps_root) if d.startswith(game + "__"))
        extra = []
        if game == "furn_stove":
            extra.append(("дверца откинута", None))
        if game == "furn_basin":
            extra.append(("отбит угол", None))
        for code, _ in [(v, None) for v in variants] + extra:
            vc = bpy.data.collections.new(f"{game} · {code} · {titles.get(code, '')}")
            var_top.children.link(vc)
            mv = placement(game, x + width / 2)
            if code == "отбит угол":
                copies = copy_set(objs, vc, mv, keep=lambda o: o.name.split(".")[0] != "Фаянс"
                                  and not o.name.split(".")[0].endswith("__оборвана"))
                for c in copies:
                    c.hide_render = False
                apply_maps(copies, game, os.path.join(maps_root, game), prefix=game)
            elif code == "дверца откинута":
                copies = copy_set(objs, vc, mv, keep=base_keep)
                y0, z0 = OVEN_HINGE
                hinge = Matrix.Translation((0, y0, z0)) @ Matrix.Rotation(math.radians(88), 4, "X") @ \
                    Matrix.Translation((0, -y0, -z0))
                for c in copies:
                    if c.name.split(".")[0].endswith("__дверца"):
                        c.matrix_world = mv @ hinge
                apply_maps(copies, game, os.path.join(maps_root, game), prefix=game)
            else:
                copies = copy_set(objs, vc, mv, keep=base_keep)
                apply_maps(copies, game, os.path.join(maps_root, f"{game}__{code}"), prefix=game, code=code)
            p = mv.translation
            label(vc, code, (p.x, (WALL - 0.75) if PLACE[game][0] != "floor" else p.y - 0.6, 0.002))
            x += width + 0.3
        print("REVIEW", game, len(objs), "деталей, варианты", variants, flush=True)
    # посуда: на конфорках и на столе-тумбе (с вариантами — рядом на полу впереди)
    for game, (host, off) in ON.items():
        coll = bpy.data.collections[game]
        coll.hide_viewport = False
        coll.hide_render = False
        objs = [o for o in coll.objects if o.type == "MESH"]
        m = roots[host] @ Matrix.Translation(off)
        for ob in objs:
            ob.matrix_world = m
        apply_maps(objs, game, os.path.join(maps_root, game))
        variants = sorted(d.split("__", 1)[1] for d in os.listdir(maps_root) if d.startswith(game + "__"))
        for k, code in enumerate(variants):
            vc = bpy.data.collections.new(f"{game} · {code} · {titles.get(code, '')}")
            var_top.children.link(vc)
            base = roots[host].translation
            mv = Matrix.Translation((base.x - 0.25 + k * 0.35, base.y - 1.0 - (0.4 if game == "furn_kettle" else 0.0), 0))
            copies = copy_set(objs, vc, mv)
            apply_maps(copies, game, os.path.join(maps_root, f"{game}__{code}"), prefix=game, code=code)
            label(vc, code, (mv.translation.x, mv.translation.y - 0.2, 0.002))
        print("REVIEW", game, len(objs), "деталей, варианты", variants, flush=True)
    span = x + 0.5
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
