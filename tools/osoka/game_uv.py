# «Осока»: развёртка игровой сетки по нормам проекта (общий модуль tools/asset_kit/uv.py) и наборы текстур для Painter.
# "D:/ПРОГРАММЫ/Blender 5/blender.exe" -b <work/osoka_game_v01.blend> --python tools/osoka/game_uv.py -- <out.blend>
# Наборы: «Труба» (труба, крышки, ремень, источник питания) 4K, «Механизм» (литьё, накладка, короб, прицельные,
# мелкие детали) 4K, «Ракета» 2K. Прижатые во всех позах грани (труба под накладкой и хомутами…) удаляются, скрытые
# ужимаются, у глаза стрелка — плотнее (точка глаза у целика слева, вид вдоль трубы). Длинные детали (труба, корпус
# ракеты, ремень) режутся на куски по длине — остров в полтора метра не лёг бы в атлас с нужной плотностью.
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import bpy  # noqa: E402
import bmesh  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402
from asset_kit import uv as kit_uv  # noqa: E402

UV = "GameUV"
SETS = {"Tube": 4096, "Launcher": 4096, "Missile": 2048}
# длинные детали: шаг кусков по X, мм (геометрия режется плоскостями, где длинные грани без вершин)
LONG = {"Tube_body": 380.0, "Missile_body": 400.0, "Sling_strap": 300.0}
BISECT = ("Tube_body", "Missile_body")
# глаз стрелка: у целика слева (ADS) и чуть дальше и выше (от бедра — ПЗРК на плече, вид вдоль трубы), +X — к раструбу
EYES = [kit_uv.Eye((1.00, 0.10, 0.12), name="плечо"),
        kit_uv.Eye((1.10, 0.066, 0.058), k_max=kit_uv.ADS_K, name="в прицел")]
# позы для лучей видимости: что открывается при работе с ПЗРК (крышки сняты, механизм отстыкован, прицельные сложены…)
POSES = {"rest": {}, "caps_off": {"front_cap": 1.0, "rear_cap": 1.0}, "detach": {"launcher_detach": 1.0},
         "power_out": {"power_out": 1.0}, "sights_down": {"front_sight": 0.0, "rear_sight": 0.0},
         "dust_open": {"dust_cover": 1.0}, "lever": {"lever": 1.0}, "trigger": {"trigger": 1.0}}


def log(*a):
    print("GAME_UV", *a, flush=True)


def set_of(name):
    if name.startswith("Missile"):
        return "Missile"
    if name.startswith(("Tube_", "Front_cap", "Rear_cap", "Sling_strap", "Sling_pad", "Power_source", "Power_socket")):
        return "Tube"
    return "Launcher"


def controls(state):
    ctrl = bpy.data.objects["OSOKA_Controls"]
    base = {"front_sight": 1.0, "rear_sight": 1.0}
    for k in list(ctrl.keys()):
        if not k.startswith("_"):
            ctrl[k] = base.get(k, 0.0)
    for k, v in state.items():
        ctrl[k] = v
    ctrl.update_tag()
    bpy.context.scene.frame_set(1)
    bpy.context.view_layer.update()


def bisect_long(objs):
    for o in objs:
        if o.name not in BISECT:
            continue
        step = LONG[o.name] * 0.001
        bm = bmesh.new(); bm.from_mesh(o.data)
        xs = [v.co.x for v in bm.verts]
        x = min(xs) + step
        n = 0
        while x < max(xs) - step * 0.3:
            geom = list(bm.verts) + list(bm.edges) + list(bm.faces)
            bmesh.ops.bisect_plane(bm, geom=geom, dist=1e-6, plane_co=(x, 0, 0), plane_no=(1, 0, 0))
            x += step; n += 1
        bm.to_mesh(o.data); bm.free()
        log("bisect", o.name, n)


def unwrap(objs):
    kit_uv.smart_unwrap(objs, UV)
    # длинные детали — по кускам: каждый кусок своим умным проецированием (острова не идут через границу куска)
    for o in objs:
        if o.name not in LONG:
            continue
        step = LONG[o.name] * 0.001
        bpy.ops.object.select_all(action="DESELECT")
        o.select_set(True)
        bpy.context.view_layer.objects.active = o
        bpy.ops.object.mode_set(mode="EDIT")
        bm = bmesh.from_edit_mesh(o.data)
        mw = o.matrix_world
        x0 = min((mw @ v.co).x for v in bm.verts)
        slabs = sorted({int(((mw @ f.calc_center_median()).x - x0) // step) for f in bm.faces})
        for s in slabs:
            for f in bm.faces:
                f.select = int(((mw @ f.calc_center_median()).x - x0) // step) == s
            bmesh.update_edit_mesh(o.data)
            bpy.ops.uv.smart_project(angle_limit=kit_uv.SHARP, island_margin=0.0, area_weight=0.0, correct_aspect=True,
                                     scale_to_bounds=False)
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.uv.select_all(action="SELECT")
        bpy.ops.uv.average_islands_scale()
        bpy.ops.object.mode_set(mode="OBJECT")
        log("slabs", o.name, len(slabs))


def pose_mats(objs):
    """{поза: {имя: матрица из покоя в позу}} — по ригу OSOKA_Controls."""
    controls({})
    rest = {o.name: o.matrix_world.copy() for o in objs}
    out = {}
    for pn, st in POSES.items():
        controls(st)
        out[pn] = {o.name: o.matrix_world @ rest[o.name].inverted() for o in objs}
    controls({})
    return out


def drop_contact(objs, cls):
    """Прижатые во всех позах грани — прочь (норма проекта); классы — без них."""
    out = []
    n = 0
    for o, c in zip(objs, cls):
        idx = np.flatnonzero(c == kit_uv.CONTACT)
        if len(idx) and len(idx) < len(o.data.polygons):
            bm = bmesh.new(); bm.from_mesh(o.data); bm.faces.ensure_lookup_table()
            bmesh.ops.delete(bm, geom=[bm.faces[i] for i in idx], context="FACES")
            bm.to_mesh(o.data); bm.free()
            n += len(idx)
            out.append(np.delete(c, idx))
        else:
            out.append(c)
    log("contact_faces_dropped", n)
    return out


def harden_keep(objs):
    """Шов с изломом больше 30° — жёсткий (как asset_kit.uv.harden_on_seams), но прежние жёсткие рёбра игровой сетки
    остаются: harden_on_seams делал гладким всё, что не шов, — граница плоской боковины и скругления снова стала гладкой,
    нормали потянулись по длинным треугольникам боковин (клин на рукояти справа, полосы по коробу в карте нормалей —
    проба текстур v1). Нормали — заново по площади граней."""
    import lib
    lim = math.radians(30.0)
    for o in objs:
        bm = bmesh.new(); bm.from_mesh(o.data)
        uvl = bm.loops.layers.uv[UV]
        for e in bm.edges:
            if len(e.link_faces) != 2:
                e.smooth = False
                continue
            f1, f2 = e.link_faces
            u1 = {l.vert.index: l[uvl].uv for l in f1.loops}
            u2 = {l.vert.index: l[uvl].uv for l in f2.loops}
            seam = any((u1[v.index] - u2[v.index]).length > 1e-6 for v in e.verts)
            if seam and e.calc_face_angle(0.0) > lim:
                e.smooth = False
        bm.to_mesh(o.data); bm.free()
        o.modifiers.clear()
        lib.weighted(o)
        lib.apply_all(o)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    out_path = os.path.abspath(argv[0])
    controls({})
    meshes = [o for o in bpy.data.objects if o.type == "MESH" and len(o.data.polygons)]
    for o in meshes:
        for lay in list(o.data.uv_layers):
            if lay.name != UV:
                o.data.uv_layers.remove(lay)
    bisect_long(meshes)
    unwrap(meshes)
    report = {}
    poses = None
    for sname, size in SETS.items():
        objs = [o for o in meshes if set_of(o.name) == sname]
        if sname == "Missile":
            # ракету в игре видно в полёте со всех сторон — ровная плотность, без глаза и лучей
            cls = None
            eyes = []
        else:
            if poses is None:
                poses = pose_mats(meshes)
            cls = kit_uv.visibility(objs, poses, node_of=lambda o: o.name)
            cls = drop_contact(objs, cls)
            eyes = EYES
        rep = kit_uv.layout(objs, size, uv=UV, classes=cls, eyes=eyes, log=log)
        ok = kit_uv.verify(objs, size, uv=UV)
        rep["verify"] = ok
        report[sname] = rep
        # набор текстур = материал для Painter; прежний материал детали — в свойстве (слот отделки)
        mat = bpy.data.materials.get("Osoka_" + sname) or bpy.data.materials.new("Osoka_" + sname)
        for o in objs:
            o["finish_material"] = ",".join(s.material.name for s in o.material_slots if s.material)
            o.data.materials.clear()
            o.data.materials.append(mat)
        log("SET", sname, size, {k: rep[k] for k in ("px_mm", "fill", "islands", "packed_islands", "k_visible")})
    harden_keep(meshes)
    tri = 0
    for o in meshes:
        o.data.calc_loop_triangles(); tri += len(o.data.loop_triangles)
    hand = sum(len(o.data.loop_triangles) for o in meshes if set_of(o.name) != "Missile")
    log("TRIS", tri, "HANDS", hand)
    report["tris_hands"] = hand
    with open(os.path.splitext(out_path)[0] + "_uv.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(report, f, ensure_ascii=False, indent=1, default=str)
    bpy.ops.wm.save_as_mainfile(filepath=out_path, compress=True)
    log("SAVED", out_path)


main()
