"""Контейнеры для лута, партия 1: производственная развёртка принятых форм и FBX для Painter (этап 1 текстур).

  "D:/ПРОГРАММЫ/Blender 5/blender.exe" --background "E:/Models Blender/ENVIRONMENT/RING_Loot_Containers/models/RING_Loot_Containers_v01.blend" \
      --python-exit-code 1 --python tools/loot_containers/lc_uv.py [-- набор …]

Форма принята владельцем 2026-11-13 — сетки не меняются (модификаторы применяются, как в партии общежития). Набор текстур —
по предмету (материал с именем набора), детали — сетками «<объект>[__<метка>]»: объект формы целиком или его часть по
метке (снаружи / внутри, шкала лимба, клавиши по цветам, личинка, ручка и рамка ящика, ярлычки папок). Так у одного листа
оболочки разные отделки по сторонам. Развёртка делается на ОТКРЫТОМ состоянии (в нём есть всё: папки, органайзер,
подсумки; внутренности не закрыты дверцами при запекании затенения), закрытое состояние берёт те же UV по номеру петли
(топология одна) и лежит в коллекции «<набор>__closed» для файла просмотра. Мелкое, что читают вблизи (шкала лимба,
клавиши, шильдики, наклейки), развёрнуто крупнее. Шильдики и наклейки-инструкции — тонкие пластинки, которых в форме не
было (добавлены только в этом файле, 0,5–0,8 мм над поверхностью; форма v01 не тронута).
Выход: RING_Loot_Containers_uv_v01.blend рядом с формой, _asset_src/loot_containers/sp/<набор>.fbx, pieces.json, plates.json.
"""
import json
import math
import os
import re
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector as V
from mathutils.bvhtree import BVHTree

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dorm_modules"))
import furniture2_uv as F2  # noqa: E402  (uv_islands)

ROOT_DIR = "E:/Games/RING-godot/_asset_src/loot_containers"
OUT_FBX = ROOT_DIR + "/sp"

# набор: (корень закрытого, корень открытого состояния)
ITEMS = {
    "lc_safe": ("СН_сейф_напольный", "СН_сейф_напольный_открыт"),
    "lc_cell": ("СЯ_сейф_ячейка", "СЯ_сейф_ячейка_открыт"),
    "lc_gun": ("ОШ_шкаф_оружейный", "ОШ_шкаф_оружейный_открыт"),
    "lc_file": ("КШ_шкаф_картотечный", "КШ_шкаф_картотечный_открыт"),
    "lc_cash": ("КМ_кассовое_место", "КМ_кассовое_место_лоток_выдвинут"),
    "lc_bag": ("МС_сумка_укладка", "МС_сумка_укладка_раскрыта"),
    "lc_aid": ("АП_аптечка_настенная", "АП_аптечка_настенная_открыта"),
}
GAMES = list(ITEMS)  # для print_bake.py
RES = {"lc_safe": 2048, "lc_cell": 1024, "lc_gun": 4096, "lc_file": 4096, "lc_cash": 2048, "lc_bag": 2048, "lc_aid": 1024}


# --------------------------------------------------------------------------------------------- метки частей объекта
# сигнатура: tagger(name, c, n, bb) — центр и нормаль грани в осях ОБЪЕКТА (поза закрытого состояния), bb = (min, max)

def shell_inout(name, c, n, bb):
    """Оболочка с толщиной (Solidify): грани, смотрящие к середине объёма, — внутренние."""
    mid = (bb[0] + bb[1]) / 2
    return "внутри" if (c - mid).dot(n) < 0 else ""


def door_back(name, c, n, bb):
    return "внутри" if n.y > 0.5 else ""


def dial(name, c, n, bb):
    """Лимб: шкала — плоское кольцо r 30…41 мм на лице (и торцы рисок на нём) чёрное; накладка, ручка-набор — хром."""
    cx, cz = (bb[0].x + bb[1].x) / 2, bb[0].z + (bb[1].x - bb[0].x) / 2   # без треугольника-указателя сверху
    r = math.hypot(c.x - cx, c.z - cz)
    return "шкала" if (0.0298 < r < 0.0412 and n.y < -0.5) else ""


def lock_handle(name, c, n, bb):
    """Ручка-замок оружейного шкафа: личинка на конце рычага (r 4,5 мм) — хром, остальное чёрный пластик."""
    return "личинка" if (math.hypot(c.x + 0.085, c.z) < 0.0065 and c.y < bb[0].y + 0.0035) else ""


def drawer_face(name, c, n, bb):
    """Лицо ящика картотеки: стакан ручки-скобы за окном (x ±70, z 94…125 мм от оси лица) — анодированный алюминий,
    приподнятая рамка этикетки (y < 0) — никель."""
    if abs(c.x) < 0.0705 and 0.0945 < c.z < 0.1255 and c.y > 0.002:
        return "ручка"
    if c.y < -0.0004 and abs(c.x) < 0.0455 and 0.031 < c.z < 0.071:
        return "рамка"
    return ""


def tray_face(name, c, n, bb):
    """Лицо лотка кассы: замок справа (цилиндр r 10,5 мм, выступает на 4 мм) — никель."""
    return "замок" if (math.hypot(c.x - 0.163, c.z + 0.006) < 0.0115 and c.y < -0.0008) else ""


KB_P0 = V((0.0, -0.20, 0.135))
KB_SL = V((0.0, 0.03 + 0.20, 0.078 - 0.035))


def kb_cell(c):
    t = (c - KB_P0).dot(KB_SL.normalized())
    row = int(round((t - 0.018) / 0.0345))
    col = int(round((c.x + 0.15) / 0.0273))
    return row, col


def keys(name, c, n, bb):
    """Клавиатура: тёмно-серые, светлый цифровой блок (ряды 1–4, колонки 8–11), цветные: СБРОС, ОПЛАТА, ИТОГ."""
    row, col = kb_cell(c)
    if (row, col) == (5, 0):
        return "красная"
    if (row, col) == (5, 1):
        return "зелёная"
    if (row, col) == (5, 2):
        return "синяя"
    if 1 <= row <= 4 and 8 <= col <= 11:
        return "светлые"
    return "тёмные"


def folder_tabs(name, c, n, bb):
    return ("ярлык%d" % (int(round((c.x + 0.105) / 0.07)) % 4,))


TAGGERS = {
    "СН_корпус": shell_inout, "СН_дверца": door_back, "СН_лимб": dial,
    "ОШ_ручка_замок": lock_handle,
    "КШ_ящик_верхний_лицо": drawer_face, "КШ_ящик_второй_лицо": drawer_face,
    "КШ_ящик_третий_лицо": drawer_face, "КШ_ящик_нижний_лицо": drawer_face,
    "КШ_папки_ярлыки": folder_tabs,
    "КМ_лоток_лицо": tray_face, "КМ_клавиатура": keys,
    "МС_клапан": shell_inout, "МС_корпус": shell_inout,
}

# крупнее в развёртке то, что разглядывают вблизи и где печать (линейный коэффициент к общей плотности набора)
SCALE = {"СН_лимб__шкала": 4.0, "СН_лимб": 2.5, "КМ_клавиатура__тёмные": 3.5, "КМ_клавиатура__светлые": 3.5,
         "КМ_клавиатура__красная": 3.5, "КМ_клавиатура__зелёная": 3.5, "КМ_клавиатура__синяя": 3.5,
         "КШ_ящик_верхний_лицо": 1.6, "КШ_ящик_второй_лицо": 1.6,
         "КШ_ящик_третий_лицо": 1.6, "КШ_ящик_нижний_лицо": 1.6, "АП_дверца": 1.6, "МС_клапан": 1.3,
         "КМ_аппарат_корпус": 1.6, "КМ_лоток_лицо": 1.6, "КМ_принтер_крышка": 1.3}


def scale_for(piece: str) -> float:
    for k in (piece, piece.split("__")[0]):
        if k in SCALE:
            return SCALE[k]
    if "шильдик" in piece:
        return 6.0
    if "наклейка" in piece:
        return 3.0
    return 1.0


# ------------------------------------------------------------------------------------------ шильдики и наклейки
# (имя, объект-родитель, начало луча в осях родителя, направление луча, ширина мм, высота мм, толщина мм, «вверх»)
PLATES = {
    "lc_safe": [("СН_шильдик", "СН_дверца", (0.23, -0.2, 0.625), (0, 1, 0), 80, 22, 0.8, (0, 0, 1)),
                ("СН_наклейка_инструкция", "СН_дверца", (0.36, 0.3, 0.57), (0, -1, 0), 110, 70, 0.3, (0, 0, 1))],
    "lc_cell": [("СЯ_шильдик", "СЯ_дверца", (0.15, -0.2, 0.19), (0, 1, 0), 46, 14, 0.8, (0, 0, 1))],
    "lc_gun": [("ОШ_шильдик", "ОШ_створка_лев", (0.19, -0.3, 1.30), (0, 1, 0), 80, 24, 0.8, (0, 0, 1)),
               ("ОШ_наклейка_опись", "ОШ_створка_лев", (0.21, 0.3, 0.95), (0, -1, 0), 150, 110, 0.3, (0, 0, 1))],
    "lc_file": [("КШ_шильдик", "КШ_корпус", (0.0, -0.5, 0.07), (0, 1, 0), 60, 16, 0.8, (0, 0, 1))],
    "lc_cash": [("КМ_шильдик", "КМ_аппарат_корпус", (0.0, -0.5, 0.115), (0, 1, 0), 70, 14, 0.8, (0, 0, 1))],
}


# якоря печати (центр, нормаль, «вверх» в осях КОРНЯ открытого состояния — по ним lc_prints.py кладёт рисунки на подвижные
# детали): «front_circle» — круглая накладка на лице (центр по ширине и низу), «front» / «top» — центр лица / верха
ANCHORS = {"lc_safe": [("dial", "СН_лимб", "front_circle")], "lc_bag": [("flap", "МС_клапан", "top")],
           "lc_aid": [("door", "АП_дверца", "front")]}


def shell_mesh(ob, dg):
    return bpy.data.meshes.new_from_object(ob.evaluated_get(dg), depsgraph=dg)


def bm_plate(center, n, up, w_mm, h_mm, t_mm):
    """Тонкая коробка w × h × t мм: лицо смотрит по n, низ — на поверхности (глубже на 0,05 мм, чтобы не было щели)."""
    n = V(n).normalized()
    right = V(up).cross(n)
    if right.length < 1e-6:
        right = V((1, 0, 0))
    right.normalize()
    upv = n.cross(right).normalized()
    bm = bmesh.new()
    hw, hh, t = w_mm / 2000.0, h_mm / 2000.0, t_mm / 1000.0
    c0 = V(center) - n * 0.00005
    vs = []
    for dz in (0.0, t):
        for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            vs.append(bm.verts.new(c0 + right * (sx * hw) + upv * (sy * hh) + n * dz))
    bm.faces.new(vs[0:4][::-1])
    bm.faces.new(vs[4:8])
    for k in range(4):
        bm.faces.new((vs[k], vs[(k + 1) % 4], vs[4 + (k + 1) % 4], vs[4 + k]))
    bm.normal_update()
    return bm


def main() -> None:
    only = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    os.makedirs(OUT_FBX, exist_ok=True)
    for o in bpy.data.objects:   # исходные объекты формы — с префиксом (в копии файла), чтобы у сеток набора были чистые имена
        o.name = "_src_" + o.name
    dg = bpy.context.evaluated_depsgraph_get()
    top = bpy.data.collections.get("Развёртка_v01") or bpy.data.collections.new("Развёртка_v01")
    if top.name not in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.link(top)
    pieces_json, plates_json = {}, {}
    for game, (rc, ro) in ITEMS.items():
        if only and game not in only:
            continue
        root_c, root_o = bpy.data.objects["_src_" + rc], bpy.data.objects["_src_" + ro]
        coll = bpy.data.collections.new(game)
        collc = bpy.data.collections.new(game + "__closed")
        top.children.link(coll)
        top.children.link(collc)
        twin = {re.sub(r"\.\d+$", "", o.name[5:]): o for o in root_c.children_recursive if o.type == "MESH"}
        to_o, to_c = root_o.matrix_world.inverted(), root_c.matrix_world.inverted()
        objs, closed_objs = [], []   # (открытая деталь, закрытая или None)
        pairs = []
        for ob in root_o.children_recursive:
            if ob.type != "MESH" or ob.hide_render:
                continue
            base = re.sub(r"\.\d+$", "", ob.name[5:])
            c_ob = twin.get(base)
            me_o = shell_mesh(ob, dg)
            me_c = shell_mesh(c_ob, dg) if c_ob is not None else None
            if me_c is not None and (len(me_c.polygons) != len(me_o.polygons) or len(me_c.vertices) != len(me_o.vertices)):
                print("  топология не совпала", base, len(me_o.polygons), len(me_c.polygons))
                me_c = None
            tagger = TAGGERS.get(base)
            groups = {}
            bbv = [v.co for v in me_o.vertices]
            bb = (V((min(v.x for v in bbv), min(v.y for v in bbv), min(v.z for v in bbv))),
                  V((max(v.x for v in bbv), max(v.y for v in bbv), max(v.z for v in bbv))))
            for p in me_o.polygons:
                tag = tagger(base, p.center, p.normal, bb) if tagger else ""
                groups.setdefault(tag, []).append(p.index)
            for tag, idxs in groups.items():
                name = base + (f"__{tag}" if tag else "")
                for which, me, ob2, to in (("o", me_o, ob, to_o), ("c", me_c, c_ob, to_c)):
                    if me is None:
                        continue
                    bm = bmesh.new()
                    bm.from_mesh(me)
                    bm.faces.ensure_lookup_table()
                    keep = set(idxs)
                    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.index not in keep], context="FACES")
                    bm.transform(to @ ob2.matrix_world)
                    nm = bpy.data.meshes.new(name)
                    bm.to_mesh(nm)
                    bm.free()
                    o2 = bpy.data.objects.new(name if which == "o" else "c:" + name, nm)
                    (coll if which == "o" else collc).objects.link(o2)
                    (objs if which == "o" else closed_objs).append(o2)
                pairs.append(name)
            bpy.data.meshes.remove(me_o)
            if me_c is not None:
                bpy.data.meshes.remove(me_c)
        # шильдики и наклейки
        plate_info = {}
        for (pname, par, org, dr, w, h, t, up) in PLATES.get(game, []):
            pob_o = next(o for o in root_o.children_recursive if re.sub(r"\.\d+$", "", o.name[5:]) == par)
            pob_c = twin[par]
            me = shell_mesh(pob_o, dg)
            bm = bmesh.new()
            bm.from_mesh(me)
            bvh = BVHTree.FromBMesh(bm)
            hit, nrm, _, _ = bvh.ray_cast(V(org), V(dr))
            if hit is None:
                print("  НЕТ ПОПАДАНИЯ", game, pname)
                bm.free()
                bpy.data.meshes.remove(me)
                continue
            if nrm.dot(V(dr)) > 0:
                nrm = -nrm
            pbm = bm_plate(hit, nrm, up, w, h, t)
            for which, ob2, to, cl in (("o", pob_o, to_o, coll), ("c", pob_c, to_c, collc)):
                b2 = pbm.copy()
                b2.transform(to @ ob2.matrix_world)
                nm = bpy.data.meshes.new(pname)
                b2.to_mesh(nm)
                b2.free()
                o2 = bpy.data.objects.new(pname if which == "o" else "c:" + pname, nm)
                cl.objects.link(o2)
                (objs if which == "o" else closed_objs).append(o2)
            # поза в осях корня открытого состояния — для печати (print_bake / lc_prints)
            m = to_o @ pob_o.matrix_world
            cw = m @ (V(hit) + V(nrm).normalized() * (t / 1000.0))
            nw = (m.to_3x3() @ V(nrm)).normalized()
            rw = (m.to_3x3() @ V(up).cross(nrm)).normalized()
            plate_info[pname] = {"center": list(cw), "normal": list(nw), "right": list(rw), "w": w, "h": h}
            pbm.free()
            bm.free()
            bpy.data.meshes.remove(me)
        for (aname, par, kind) in ANCHORS.get(game, []):
            pob_o = next(o for o in root_o.children_recursive if re.sub(r"\.\d+$", "", o.name[5:]) == par)
            me = shell_mesh(pob_o, dg)
            xs = [v.co for v in me.vertices]
            mn = V((min(v.x for v in xs), min(v.y for v in xs), min(v.z for v in xs)))
            mx = V((max(v.x for v in xs), max(v.y for v in xs), max(v.z for v in xs)))
            bpy.data.meshes.remove(me)
            if kind == "front_circle":
                pt, nrm, up = V(((mn.x + mx.x) / 2, mn.y, mn.z + (mx.x - mn.x) / 2)), V((0, -1, 0)), V((0, 0, 1))
            elif kind == "front":
                pt, nrm, up = V(((mn.x + mx.x) / 2, mn.y, (mn.z + mx.z) / 2)), V((0, -1, 0)), V((0, 0, 1))
            else:
                pt, nrm, up = V(((mn.x + mx.x) / 2, (mn.y + mx.y) / 2, mx.z)), V((0, 0, 1)), V((0, 1, 0))
            m = to_o @ pob_o.matrix_world
            m3 = m.to_3x3()
            plate_info[aname] = {"center": list(m @ pt), "normal": list((m3 @ nrm).normalized()),
                                 "right": list((m3 @ up.cross(nrm)).normalized()), "up": list((m3 @ up).normalized()),
                                 "w": 0, "h": 0}
        plates_json[game] = plate_info
        # развёртка
        bpy.ops.object.select_all(action="DESELECT")
        for ob in objs:
            for uv in list(ob.data.uv_layers):
                ob.data.uv_layers.remove(uv)
            ob.data.uv_layers.new(name="UVMap")
            ob.select_set(True)
        bpy.context.view_layer.objects.active = objs[0]
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.uv.smart_project(angle_limit=math.radians(66.0), island_margin=0.004, area_weight=0.0, correct_aspect=True,
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
            for isl in F2.uv_islands(bm, uv):
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
        # UV на закрытое состояние (та же топология и порядок петель)
        by_name = {o.name: o for o in objs}
        for co in closed_objs:
            src = by_name[co.name[2:]]
            co.data.uv_layers.new(name="UVMap")
            n = len(co.data.loops)
            assert n == len(src.data.loops), (co.name, n, len(src.data.loops))
            buf = [0.0] * (2 * n)
            src.data.uv_layers[0].data.foreach_get("uv", buf)
            co.data.uv_layers[0].data.foreach_set("uv", buf)
        mat = bpy.data.materials.get(game) or bpy.data.materials.new(game)
        for ob in objs + closed_objs:
            ob.data.materials.clear()
            ob.data.materials.append(mat)
        # плотность: пикс/м по площади
        res = RES[game]
        dens = {}
        for ob in objs:
            bm = bmesh.new()
            bm.from_mesh(ob.data)
            uv = bm.loops.layers.uv.active
            ua = sum(abs(_uv_area([lp[uv].uv for lp in f.loops])) for f in bm.faces)
            wa = sum(f.calc_area() for f in bm.faces)
            bm.free()
            if wa > 1e-6:
                dens[ob.name] = math.sqrt(ua / wa) * res
        tot_uv = sum(1 for _ in dens)
        print(f"DENS {game} ({res}): медиана {sorted(dens.values())[len(dens) // 2]:.0f} пикс/м; "
              f"мин {min(dens.values()):.0f} ({min(dens, key=dens.get)}), макс {max(dens.values()):.0f} ({max(dens, key=dens.get)})")
        # FBX открытого состояния
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
        collc.hide_viewport = True
    if only:
        old = {}
        for fn, d in (("pieces.json", pieces_json), ("plates.json", plates_json)):
            p = f"{ROOT_DIR}/{fn}"
            if os.path.exists(p):
                old = json.load(open(p, encoding="utf-8"))
                old.update(d)
                d.clear()
                d.update(old)
    for fn, d in (("pieces.json", pieces_json), ("plates.json", plates_json)):
        with open(f"{ROOT_DIR}/{fn}", "w", encoding="utf-8", newline="\n") as fh:
            json.dump(d, fh, ensure_ascii=False, indent=1)
    out = bpy.data.filepath.replace("_v01.blend", "_uv_v01.blend")
    bpy.ops.wm.save_as_mainfile(filepath=out, copy=True, compress=True)
    print("saved", out)


def _uv_area(pts) -> float:
    s = 0.0
    for i in range(len(pts)):
        a, b = pts[i], pts[(i + 1) % len(pts)]
        s += a.x * b.y - b.x * a.y
    return s / 2


if __name__ == "__main__":
    main()
