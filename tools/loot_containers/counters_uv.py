"""Опоры касс v01 (прилавок торговый ПТ_, кассовый бокс КБ_), отделка: производственная развёртка принятой формы и FBX для Painter.
Приёмы — как у lc_uv.py (партия 1): сетки наборов «<объект>[__<метка>]», набор текстур — материал с именем набора.

  "D:/ПРОГРАММЫ/Blender 5/blender.exe" --background "E:/Models Blender/ENVIRONMENT/RING_Loot_Containers/models/RING_Loot_Counters_v01.blend" \
      --python-exit-code 1 --python tools/loot_containers/counters_uv.py [-- набор …]

Форма принята 2026-11-13 и не меняется: модификаторы запекаются (как есть), объект с двумя слотами материала (пласть / кромка ПВХ)
режется по слоту на две сетки «<объект>» и «<объект>__кромка» (разная отделка). Добавлены только тонкие пластинки печати
(наклейка-инвентарник на боковине прилавка, 0,4 мм над поверхностью). Многоугольники — в треугольники.
Выход: RING_Loot_Counters_uv_v01.blend рядом с формой (коллекции «Развёртка_v01/<набор>»), _asset_src/loot_containers/sp_counters/<набор>.fbx,
pieces_counters.json, plates_counters.json.
"""
import json
import math
import os
import re
import sys

import bmesh
import bpy
from mathutils import Vector as V

ROOT_DIR = "E:/Games/RING-godot/_asset_src/loot_containers"
OUT_FBX = ROOT_DIR + "/sp_counters"
ITEMS = {"cn_counter": ("Прилавок торговый", "ПТ_прилавок"), "cn_checkout": ("Кассовый бокс", "КБ_кассовый_бокс")}
GAMES = list(ITEMS)
RES = {"cn_counter": 2048, "cn_checkout": 2048}
EDGE_SLOT_TAG = "кромка"
# крупнее в развёртке то, что разглядывают вблизи (линейный коэффициент к общей плотности)
SCALE = {"ПТ_столешница": 1.5, "ПТ_столешница__кромка": 1.3, "ПТ_накладка_полоса": 1.4, "ПТ_панель_передняя": 1.2,
         "ПТ_наклейка_инвентарник": 4.0, "ПТ_монетница": 1.5, "КБ_стол_кассира": 1.4, "КБ_стол_кассира__кромка": 1.3,
         "КБ_столешница_нержавейка": 1.5, "КБ_столешница_сканер": 1.5, "КБ_лента_транспортёра": 1.5, "КБ_табличка_панели": 4.0,
         "КБ_борта_пластик": 1.4, "КБ_корпус": 1.1, "КБ_ящик_лицо": 1.0,
         # круг 2: узкие полосы кромок крупнее — сколы на них без «лесенки» пикселей
         "ПТ_столешница__кромка": 3.0, "КБ_стол_кассира__кромка": 2.5}
EDGE_SCALE = 2.0   # прочие «…__кромка» (торцы ЛДСП 16 мм)


def scale_for(name: str) -> float:
    """Множитель плотности по имени сетки; суффикс «.001» (имя занято объектом формы в том же файле) не мешает."""
    base = name.rsplit(".", 1)[0] if name.rsplit(".", 1)[-1].isdigit() else name
    if base in SCALE:
        return SCALE[base]
    return EDGE_SCALE if base.endswith("__" + EDGE_SLOT_TAG) else 1.0


def clean_normals(me) -> None:
    """Без своих нормалей: Bevel с «harden normals» оставлял custom_normal, и на треугольниках плиты с вырезами (сканер,
    кабельные выводы) нормали интерполировались волной — «плавленое» отражение нержавейки. Плоские грани — плоско,
    острые рёбра по углу 30°."""
    if "custom_normal" in me.attributes:
        me.attributes.remove(me.attributes["custom_normal"])
    for p in me.polygons:
        p.use_smooth = True
    me.set_sharp_from_angle(angle=math.radians(30))

# пластинки печати: (набор, имя, центр в осях корня, нормаль, «вправо», ширина мм, высота мм, толщина мм)
PLATES = {"cn_counter": [("ПТ_наклейка_инвентарник", (-0.75, -0.10, 0.56), (-1, 0, 0), (0, 1, 0), 100, 60, 0.4)]}


def piece_mesh(ob, dg, to, mat_idx):
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), depsgraph=dg)
    bm = bmesh.new()
    bm.from_mesh(me)
    bpy.data.meshes.remove(me)
    bm.faces.ensure_lookup_table()
    drop = [f for f in bm.faces if f.material_index != mat_idx]
    if drop:
        bmesh.ops.delete(bm, geom=drop, context="FACES")
    bm.transform(to @ ob.matrix_world)
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    return bm


def plate_bm(c, n, right, w_mm, h_mm, t_mm):
    n, right = V(n).normalized(), V(right).normalized()
    up = n.cross(right).normalized()
    hw, hh, t = w_mm / 2000.0, h_mm / 2000.0, t_mm / 1000.0
    bm = bmesh.new()
    vs = []
    c0 = V(c) + n * 0.00003
    for dz in (0.0, t):
        for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            vs.append(bm.verts.new(c0 + right * (sx * hw) + up * (sy * hh) + n * dz))
    bm.faces.new(vs[0:4][::-1])
    bm.faces.new(vs[4:8])
    for k in range(4):
        bm.faces.new((vs[k], vs[(k + 1) % 4], vs[4 + (k + 1) % 4], vs[4 + k]))
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    return bm


def _uv_area(pts) -> float:
    s = 0.0
    for i in range(len(pts)):
        a, b = pts[i], pts[(i + 1) % len(pts)]
        s += a.x * b.y - b.x * a.y
    return s / 2


def main() -> None:
    only = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    os.makedirs(OUT_FBX, exist_ok=True)
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    top = bpy.data.collections.new("Развёртка_v01")
    bpy.context.scene.collection.children.link(top)
    pieces_json, plates_json = {}, {}
    for game, (cname, rname) in ITEMS.items():
        if only and game not in only:
            continue
        src = bpy.data.collections[cname]
        root = next(o for o in src.objects if o.name == rname)
        to = root.matrix_world.inverted()
        coll = bpy.data.collections.new(game)
        top.children.link(coll)
        objs = []
        for ob in sorted(src.objects, key=lambda o: o.name):
            if ob.type != "MESH" or ob.hide_render:
                continue
            nslots = len(ob.data.materials)
            for si in range(max(1, nslots)):
                bm = piece_mesh(ob, dg, to, si)
                if not bm.faces:
                    bm.free()
                    continue
                name = ob.name + ("__" + EDGE_SLOT_TAG if si == 1 else "")
                nm = bpy.data.meshes.new(name)
                bm.to_mesh(nm)
                bm.free()
                clean_normals(nm)
                o2 = bpy.data.objects.new(name, nm)
                coll.objects.link(o2)
                objs.append(o2)
        info = {}
        for (pname, c, n, right, w, h, t) in PLATES.get(game, []):
            bm = plate_bm(c, n, right, w, h, t)
            nm = bpy.data.meshes.new(pname)
            bm.to_mesh(nm)
            bm.free()
            o2 = bpy.data.objects.new(pname, nm)
            coll.objects.link(o2)
            objs.append(o2)
            info[pname] = {"center": list(V(c)), "normal": list(n), "right": list(right), "w": w, "h": h}
        plates_json[game] = info
        bpy.ops.object.select_all(action="DESELECT")
        for ob in objs:
            for uv in list(ob.data.uv_layers):
                ob.data.uv_layers.remove(uv)
            ob.data.uv_layers.new(name="UVMap")
            ob.select_set(True)
        bpy.context.view_layer.objects.active = objs[0]
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.uv.smart_project(angle_limit=math.radians(66.0), island_margin=0.003, area_weight=0.0, correct_aspect=True,
                                 scale_to_bounds=False)
        bpy.ops.uv.average_islands_scale()
        bpy.ops.object.mode_set(mode="OBJECT")
        for ob in objs:
            k = scale_for(ob.name)
            if abs(k - 1.0) < 1e-6:
                continue
            bm = bmesh.new()
            bm.from_mesh(ob.data)
            bm.faces.ensure_lookup_table()
            uv = bm.loops.layers.uv.active
            # острова — по связности граней (одна сетка = несколько островов): масштаб каждого от своего центра
            seen = set()
            for f0 in bm.faces:
                if f0.index in seen:
                    continue
                stack, isl = [f0], []
                seen.add(f0.index)
                while stack:
                    f = stack.pop()
                    isl.append(f)
                    for lp in f.loops:
                        for g in lp.edge.link_faces:
                            if g.index in seen:
                                continue
                            # соседи по общему UV-ребру (не по ребру сетки): сравниваем концы в UV
                            a = [l2 for l2 in g.loops if l2.edge == lp.edge]
                            if a and (a[0][uv].uv - lp.link_loop_next[uv].uv).length < 1e-6 and (a[0].link_loop_next[uv].uv - lp[uv].uv).length < 1e-6:
                                seen.add(g.index)
                                stack.append(g)
                loops = [lp for f in isl for lp in f.loops]
                c = sum((lp[uv].uv for lp in loops), V((0.0, 0.0))) / len(loops)
                for lp in loops:
                    lp[uv].uv = c + (lp[uv].uv - c) * k
            bm.to_mesh(ob.data)
            bm.free()
        bpy.ops.object.select_all(action="DESELECT")
        for ob in objs:
            ob.select_set(True)
        bpy.context.view_layer.objects.active = objs[0]
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.uv.select_all(action="SELECT")
        bpy.ops.uv.pack_islands(rotate=True, margin=0.0025)
        bpy.ops.object.mode_set(mode="OBJECT")
        mat = bpy.data.materials.get(game) or bpy.data.materials.new(game)
        for ob in objs:
            ob.data.materials.clear()
            ob.data.materials.append(mat)
        res = RES[game]
        dens, fill = {}, 0.0
        for ob in objs:
            bm = bmesh.new()
            bm.from_mesh(ob.data)
            uv = bm.loops.layers.uv.active
            ua = sum(abs(_uv_area([lp[uv].uv for lp in f.loops])) for f in bm.faces)
            wa = sum(f.calc_area() for f in bm.faces)
            bm.free()
            fill += ua
            if wa > 1e-6:
                dens[ob.name] = math.sqrt(ua / wa) * res
        ds = sorted(dens.values())
        print(f"DENS {game} ({res}): медиана {ds[len(ds) // 2]:.0f} пикс/м; мин {ds[0]:.0f} ({min(dens, key=dens.get)}), макс {ds[-1]:.0f}; "
              f"заполнение {fill * 100:.1f} %")
        bpy.ops.object.select_all(action="DESELECT")
        for ob in objs:
            ob.select_set(True)
        bpy.context.view_layer.objects.active = objs[0]
        bpy.ops.export_scene.fbx(filepath=f"{OUT_FBX}/{game}.fbx", use_selection=True, apply_unit_scale=True,
                                 bake_space_transform=False, object_types={"MESH"}, mesh_smooth_type="FACE",
                                 use_mesh_modifiers=False, axis_forward="-Z", axis_up="Y")
        tris = sum(len(p.vertices) - 2 for ob in objs for p in ob.data.polygons)
        pieces_json[game] = sorted(o.name for o in objs)
        print(f"UV {game}: {len(objs)} сеток, {tris} треуг.", flush=True)
        coll.hide_viewport = True
    for fn, d in (("pieces_counters.json", pieces_json), ("plates_counters.json", plates_json)):
        p = f"{ROOT_DIR}/{fn}"
        if only and os.path.exists(p):
            old = json.load(open(p, encoding="utf-8"))
            old.update(d)
            d = old
        with open(p, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(d, fh, ensure_ascii=False, indent=1)
    out = bpy.data.filepath.replace("_v01.blend", "_uv_v01.blend")
    bpy.ops.wm.save_as_mainfile(filepath=out, copy=True, compress=True)
    print("saved", out)


if __name__ == "__main__":
    main()
