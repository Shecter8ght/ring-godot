# «Осока», тепловизор ПН-36Т «ПОЛЫНЬ»: развёртка игровой сетки по нормам проекта (общий модуль tools/asset_kit/uv.py) —
# как у «Осоки» (game_uv.py): один набор текстур «Polyn» 4K. Прижатые во всех позах грани удаляются, скрытые ужимаются,
# у глаза стрелка — плотнее. Позы — по ригу THERMAL_Controls (крышка объектива, переключатель).
# "D:/ПРОГРАММЫ/Blender 5/blender.exe" -b <work/thermal_game_v01.blend> --python tools/osoka/sight_uv.py -- <out.blend>
# Оси файла прицела: начало — точка крепления (середина лапы на основании «Осоки», x 1214, y 2, z 49.5 «Осоки»), +X вперёд.
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
from asset_kit import uv as kit_uv  # noqa: E402

UV = "GameUV"
SET, SIZE = "Polyn", 4096
# глаз стрелка в осях прицела, м: в прицел — у наглазника (раструб x 1065, ось окуляра y 48, z 136 «Осоки»); от бедра —
# дальше, выше и левее (ПЗРК на плече, прицел перед лицом)
EYES = [kit_uv.Eye((-0.159, 0.046, 0.0865), k_max=kit_uv.ADS_K, name="в прицел"),
        kit_uv.Eye((-0.30, 0.10, 0.12), name="от бедра")]
POSES = {"rest": {}, "cap_open": {"cap": 1.0}, "off": {"mode": 0.0}, "day": {"mode": 0.5}}


def log(*a):
    print("SIGHT_UV", *a, flush=True)


def controls(state):
    ctrl = bpy.data.objects["THERMAL_Controls"]
    base = {"mode": 1.0, "cap": 0.0}
    for k, v in base.items():
        ctrl[k] = v
    for k, v in state.items():
        ctrl[k] = v
    ctrl.update_tag()
    bpy.context.scene.frame_set(1)
    bpy.context.view_layer.update()


def pose_mats(objs):
    controls({})
    rest = {o.name: o.matrix_world.copy() for o in objs}
    out = {}
    for pn, st in POSES.items():
        controls(st)
        out[pn] = {o.name: o.matrix_world @ rest[o.name].inverted() for o in objs}
    controls({})
    return out


def drop_contact(objs, cls):
    """Прижатые во всех позах грани — прочь (норма проекта)."""
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
    """Шов с изломом больше 30° — жёсткий, прежние жёсткие рёбра остаются (как game_uv.harden_keep «Осоки»)."""
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
    meshes = [o for o in bpy.data.objects if o.type == "MESH" and len(o.data.polygons) and not o.name.endswith("_HP")]
    for o in meshes:
        for lay in list(o.data.uv_layers):
            if lay.name != UV:
                o.data.uv_layers.remove(lay)
    tri0 = sum(len(o.data.polygons) for o in meshes)
    kit_uv.smart_unwrap(meshes, UV)
    poses = pose_mats(meshes)
    cls = kit_uv.visibility(meshes, poses, node_of=lambda o: o.name)
    cls = drop_contact(meshes, cls)
    # сшивка островов даёт +0.6 % заполнения (63.5 → 64.2 %, проба 2026-11-07); пробы — SIGHT_UV_OPTS='{"hidden_pool": true}'
    opts = json.loads(os.environ.get("SIGHT_UV_OPTS", "{\"stitch\": true}"))
    rep = kit_uv.layout(meshes, SIZE, uv=UV, classes=cls, eyes=EYES, log=log, **opts)
    rep["verify"] = kit_uv.verify(meshes, SIZE, uv=UV)
    mat = bpy.data.materials.get("Polyn_" + SET) or bpy.data.materials.new("Polyn_" + SET)
    for o in meshes:
        o["finish_material"] = ",".join(s.material.name for s in o.material_slots if s.material)
        o.data.materials.clear()
        o.data.materials.append(mat)
    log("SET", SET, SIZE, {k: rep.get(k) for k in ("px_mm", "fill", "islands", "packed_islands", "k_visible")})
    harden_keep(meshes)
    tri = 0
    for o in meshes:
        o.data.calc_loop_triangles(); tri += len(o.data.loop_triangles)
    log("TRIS", tri, "faces_before", tri0)
    # формат отчёта — как у «Осоки» ({набор: отчёт}): его читает game_tex.py (через sight_tex.py)
    with open(os.path.splitext(out_path)[0] + "_uv.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump({SET: rep, "tris": tri}, f, ensure_ascii=False, indent=1, default=str)
    bpy.ops.wm.save_as_mainfile(filepath=out_path, compress=True)
    log("SAVED", out_path)


main()
